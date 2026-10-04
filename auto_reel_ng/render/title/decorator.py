"""The ``title`` decorator + producer registrations (decisions **D-C/D-E**).

Importing this module registers two seams: the ``title`` **producer** (which
renders the card image via :func:`render_title_card` and returns a
:class:`ProducedSegment`) and the ``title`` **decorator** (which places one card per chapter at the chapter's title
clip, or at the chapter's first surviving segment when cuts remove that clip entirely: an
inserted synthetic segment immediately before it for a ``black`` card, or an overlay attached
to it for a ``video`` card, so no time is added).
The card config is parsed from ``look.title_card`` at decorate time and carried on
the synthetic segment as an opaque :class:`TitleCardRequest` the producer
interprets.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional

from ...errors import TitleCardError
from ...event.plan import RenderPlan, ResolvedChapter
from ..decorators import register_decorator
from ..producers import ProducedSegment, register_producer
from ..segments import OverlaySpec, Segment
from .config import TitleCardConfig, resolve_card_config
from .content import TitleCardContent, compose_content
from .render import render_title_card

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..target import TargetSpec

#: The registry key shared by the ``title`` decorator and the ``title`` producer.
TITLE_PRODUCER = "title"


@dataclass(frozen=True)
class TitleCardRequest:
    """The opaque payload a title segment carries for the ``title`` producer."""

    config: TitleCardConfig
    content: TitleCardContent

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug/golden logging."""
        return {"config": self.config.to_dict(), "content": self.content.to_dict()}


def _look_title_card(look: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """Return the opaque ``look.title_card`` sub-map, or ``None`` when absent."""
    raw = look.get("title_card")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TitleCardError(f"look.title_card must be a mapping, got {raw!r}")
    return raw


def resolve_card(plan: RenderPlan, chapter: ResolvedChapter) -> TitleCardRequest:
    """The effective config and text of ``chapter``'s card: what a render draws.

    The config layers the engine defaults, ``plan.look["title_card"]`` (the event-wide style)
    and the chapter's ``card`` overrides, parsed once; the content is the card's heading and
    subtitle. The one place that decides what a card looks like, shared by the decorator and
    any later read of "what will this card show". It probes no media, renders no image and
    touches no database.

    Raises:
        TitleCardError: a malformed ``look.title_card`` value, or a card with no heading.
    """
    config = resolve_card_config(_look_title_card(plan.look), chapter.card)
    return TitleCardRequest(config=config, content=compose_content(plan, chapter))


def title_producer(segment: Segment, target: "TargetSpec", dest: Path) -> ProducedSegment:
    """Materialize a title segment: render its card image and describe its timing.

    Renders only the asset (decision **D-C**): the card PNG at the target
    resolution, returning the duration and fade timings the normalize step needs.
    It never encodes.
    """
    request = segment.producer_config
    if not isinstance(request, TitleCardRequest):
        raise TitleCardError(f"title producer requires a TitleCardRequest payload, got {request!r}")
    config = request.config
    render_title_card(config, request.content, target, dest)
    return ProducedSegment(
        image_path=dest,
        duration=config.duration,
        fade_in=config.fade_in,
        fade_out=config.fade_out,
    )


def _chapter_by_name(plan: RenderPlan, name: str) -> Optional[ResolvedChapter]:
    """Return the plan chapter with ``name``, or ``None``."""
    for chapter in plan.chapters:
        if chapter.name == name:
            return chapter
    return None


def _anchor_indexes(
    title_identities: Mapping[str, str], segments: tuple[Segment, ...]
) -> dict[str, int]:
    """Map each chapter with a title clip to the index of the segment its card precedes.

    The anchor is the title clip's first segment (for a partially cut clip, its first
    kept span). When cuts leave the title clip with no segment, it is the chapter's
    first surviving source segment instead. A chapter with no source segment has no
    anchor, so it gets no card.
    """
    title_anchor: dict[str, int] = {}
    first_source: dict[str, int] = {}
    for index, segment in enumerate(segments):
        if segment.is_synthetic or segment.chapter not in title_identities:
            continue
        first_source.setdefault(segment.chapter, index)
        if segment.identity == title_identities[segment.chapter]:
            title_anchor.setdefault(segment.chapter, index)
    return {chapter: title_anchor.get(chapter, index) for chapter, index in first_source.items()}


def _card_requests(plan: RenderPlan, anchors: Mapping[str, int]) -> dict[str, TitleCardRequest]:
    """Each anchored chapter's card, resolved before any segment is built or encoded."""
    requests: dict[str, TitleCardRequest] = {}
    for name in anchors:
        chapter = _chapter_by_name(plan, name)
        if chapter is not None:
            requests[name] = resolve_card(plan, chapter)
    return requests


def _attached(segment: Segment, request: TitleCardRequest) -> Segment:
    """``segment`` with the card attached as a timed overlay over its first ``duration`` seconds.

    The overlay names the ``title`` producer and carries the same request an inserted card
    would, so the render materializes it into a transparent image when the command is built.
    Nothing about the segment's length changes.
    """
    config = request.config
    overlay = OverlaySpec(
        producer=TITLE_PRODUCER,
        producer_config=request,
        start=0.0,
        end=config.duration,
        fade_in=config.fade_in,
        fade_out=config.fade_out,
    )
    return replace(segment, overlays=segment.overlays + (overlay,))


def title_decorator(
    plan: RenderPlan, target: "TargetSpec", segments: tuple[Segment, ...]
) -> tuple[Segment, ...]:
    """Place each titled chapter's card at its anchor (D-E): inserted, or attached over video.

    A chapter whose card has the background ``video`` gets no segment: the card is attached to
    its anchor segment as a timed overlay over the segment's first ``duration`` seconds, adding
    no time (``clip-normalize`` clamps it to a shorter segment). For every other chapter that
    resolved a title clip, a synthetic segment carrying the
    ``title`` producer, the chapter's own card duration, and its :class:`TitleCardRequest`
    (:func:`resolve_card`: the event-wide style with the chapter's ``card`` overrides) is
    placed immediately before that clip's first segment, recording the chapter it precedes so
    chapter durations stay correct.
    When cuts remove the title clip entirely (it contributes no segment), the card
    opens the chapter's first surviving source segment instead; a chapter with no
    surviving segment gets no card and stays absent from the movie. The result is a
    pure function of ``(plan, segments)``.
    """
    del target  # the card is authored against the target at materialize time
    resolve_card_config(_look_title_card(plan.look), None)  # a bad event-wide style fails loud
    title_identities: dict[str, str] = {}
    for chapter in plan.chapters:
        clip = chapter.title_clip
        if clip is not None:
            title_identities[chapter.name] = clip.identity

    anchors = _anchor_indexes(title_identities, segments)
    requests = _card_requests(plan, anchors)
    result: list[Segment] = []
    inserted: set[str] = set()
    for index, segment in enumerate(segments):
        if (
            not segment.is_synthetic
            and anchors.get(segment.chapter) == index
            and segment.chapter not in inserted
        ):
            request = requests.get(segment.chapter)
            if request is not None and request.config.background == "video":
                result.append(_attached(segment, request))
                inserted.add(segment.chapter)
                continue
            if request is not None:
                result.append(
                    Segment(
                        chapter=segment.chapter,
                        producer=TITLE_PRODUCER,
                        duration=request.config.duration,
                        producer_config=request,
                    )
                )
                inserted.add(segment.chapter)
        result.append(segment)
    return tuple(result)


register_producer(TITLE_PRODUCER, title_producer)
register_decorator("title", title_decorator)


__all__ = [
    "TITLE_PRODUCER",
    "TitleCardRequest",
    "resolve_card",
    "title_producer",
    "title_decorator",
]
