"""The segment list: the renderer's spine (decision **D-A**).

The unit of work is a :class:`Segment`, not a clip. Flattening a
:class:`~auto_reel_ng.event.plan.RenderPlan` yields an ordered list where an
untrimmed clip becomes one segment and a trimmed clip becomes one segment per
**kept span** (the footage between/around the removed :class:`Trim` spans), in
source-time order. Chapter membership is recorded on every segment so chapter
boundaries are recoverable after flattening.

A segment is either a **source** segment (a span of a real clip, carrying its
identity, kept-span in/out and resolved rotation) or a **synthetic** segment
(produced by a decorator, e.g. a title card), identified by a producer reference
rather than a source path. Both kinds are peers and must conform to the same
target spec before concatenation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from ..errors import RenderError
from ..event.plan import RenderPlan
from ..probe.metadata import ClipMetadata
from ..reel.document import Trim


@dataclass(frozen=True)
class OverlaySpec:
    """An image/source composited onto a segment over an active time range.

    The shape is deliberately minimal for v1 (decision: finalized with #5 when
    real overlay content exists): a ``source`` to composite, an ``x``/``y``
    position expressed as ffmpeg overlay expressions, and a ``[start, end)``
    active window in segment-local seconds (``end`` ``None`` means "to the end").

    An overlay may instead name a registered ``producer`` with its opaque
    ``producer_config`` (a decorator is pure and cannot render): the render
    materializes it into ``source``/``end``/fades before the segment's command is
    built (:func:`~auto_reel_ng.render.producers.materialize_overlay`). A nonzero
    ``fade_in``/``fade_out`` (or a materialized producer) makes it a *timed* overlay: a still shown over
    ``[start, end)``, faded in and out on its alpha channel.
    """

    source: str = ""
    x: str = "0"
    y: str = "0"
    start: float = 0.0
    end: Optional[float] = None
    producer: Optional[str] = None
    producer_config: Optional[object] = None
    fade_in: float = 0.0
    fade_out: float = 0.0
    #: Set when a producer materialized the overlay: it is a looped still even with no fades.
    timed: bool = False

    @property
    def is_timed(self) -> bool:
        """True for a producer-materialized or fading overlay: a looped, alpha-faded still."""
        return self.timed or self.fade_in > 0.0 or self.fade_out > 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging and golden tests."""
        return {
            "source": self.source,
            "x": self.x,
            "y": self.y,
            "start": self.start,
            "end": self.end,
            "producer": self.producer,
            "producer_config": _payload_to_dict(self.producer_config),
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
        }


@dataclass(frozen=True)
class Segment:  # pylint: disable=too-many-instance-attributes
    """One unit of work in the render: a source span or a synthetic producer.

    A **source** segment carries ``identity``/``source_path`` and (for a trimmed
    clip) a numeric kept-span ``start``/``end`` in source seconds; ``is_full_clip``
    is true only when the clip had no cut spans. A **synthetic** segment carries a
    ``producer`` reference and ``duration`` instead, with no source identity, plus
    an opaque ``producer_config`` payload the keyed producer interprets (the core
    never inspects it, keeping the seam generic). ``overlays`` is a first-class
    field; any non-empty overlay list makes the segment copy-ineligible.
    ``copy_eligible`` is decided later (see :mod:`auto_reel_ng.render.normalize`)
    and recorded here.
    """

    chapter: str
    identity: Optional[str] = None
    source_path: Optional[Path] = None
    start: Optional[float] = None
    end: Optional[float] = None
    #: An extra clockwise turn on top of the clip's display rotation (``reel-document``).
    rotate: Optional[int] = None
    is_full_clip: bool = False
    producer: Optional[str] = None
    duration: Optional[float] = None
    producer_config: Optional[object] = None
    overlays: tuple[OverlaySpec, ...] = ()
    copy_eligible: bool = False

    @property
    def is_synthetic(self) -> bool:
        """True when this segment is produced by a decorator rather than a clip."""
        return self.producer is not None

    @property
    def is_trimmed(self) -> bool:
        """True when this source segment is a kept span of a larger clip."""
        return not self.is_synthetic and not self.is_full_clip

    @property
    def span_duration(self) -> Optional[float]:
        """The segment's intended duration in seconds, if numerically known."""
        if self.is_synthetic:
            return self.duration
        if self.start is not None and self.end is not None:
            return self.end - self.start
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging and golden tests."""
        return {
            "chapter": self.chapter,
            "identity": self.identity,
            "source_path": str(self.source_path) if self.source_path is not None else None,
            "start": self.start,
            "end": self.end,
            "rotate": self.rotate,
            "is_full_clip": self.is_full_clip,
            "producer": self.producer,
            "duration": self.duration,
            "producer_config": _payload_to_dict(self.producer_config),
            "overlays": [o.to_dict() for o in self.overlays],
            "copy_eligible": self.copy_eligible,
        }


def _payload_to_dict(payload: Optional[object]) -> Any:
    """Render an opaque ``producer_config`` payload for logging, if it can serialize."""
    if payload is None:
        return None
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return repr(payload)


def kept_spans(cut_spans: Sequence[Trim], duration: float) -> list[tuple[float, float]]:
    """Return the kept ``[start, end)`` spans left after removing ``cut_spans``.

    Cut spans are the footage to *remove*; the kept spans are the complement
    within ``[0, duration)`` of the *union* of the cuts. Overlapping or touching
    cuts are joined as one removal, whatever order they are listed in (overlap is
    not an error), so the result is a disjoint, source-time-ordered list. A clip
    whose cuts cover its whole duration yields an empty list (the clip
    contributes no segment).
    """
    cuts = sorted((max(0.0, t.start), min(duration, t.end)) for t in cut_spans)
    merged: list[tuple[float, float]] = []
    for start, end in cuts:
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    kept: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor:
            kept.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < duration:
        kept.append((cursor, duration))
    return kept


def build_segments(
    plan: RenderPlan,
    event_dir: Path,
    clip_facts: Optional[Mapping[str, ClipMetadata]] = None,
) -> tuple[Segment, ...]:
    """Flatten ``plan`` into a deterministic, fully-ordered list of segments.

    The flattening follows the plan's chapter and clip order exactly and never
    consults folder structure. A clip with ``cut_spans`` needs its probed
    duration (from ``clip_facts``) to realize its kept spans; an untrimmed clip
    does not. Raises :class:`RenderError` for a trimmed clip with no facts.
    """
    event_dir = Path(event_dir)
    segments: list[Segment] = []
    for chapter in plan.chapters:
        for clip in chapter.clips:
            source_path = event_dir / clip.identity
            if not clip.cut_spans:
                segments.append(
                    Segment(
                        chapter=chapter.name,
                        identity=clip.identity,
                        source_path=source_path,
                        rotate=clip.rotate,
                        is_full_clip=True,
                    )
                )
                continue

            facts = clip_facts.get(clip.identity) if clip_facts is not None else None
            if facts is None:
                raise RenderError(
                    f"build_segments: trimmed clip {clip.identity!r} in chapter "
                    f"{chapter.name!r} requires probed duration to realize its kept spans"
                )
            for start, end in kept_spans(clip.cut_spans, facts.duration):
                segments.append(
                    Segment(
                        chapter=chapter.name,
                        identity=clip.identity,
                        source_path=source_path,
                        start=start,
                        end=end,
                        rotate=clip.rotate,
                        is_full_clip=False,
                    )
                )
    return tuple(segments)


__all__ = ["OverlaySpec", "Segment", "kept_spans", "build_segments"]
