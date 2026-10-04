"""The decorator seam: pluggable "look" features (decision **D-B**).

A decorator is a pure transform ``(plan, target, segments) -> segments``. Two
shapes cover every look feature foreseen: an **inserter** adds one or more
synthetic segments at a defined position (title card, intro, outro, transition
bumper), and an **attacher** adds an :class:`OverlaySpec` to existing segments
(title-over-footage, watermark, lower-third). Decorators are selected by name
from the resolved ``look``/config and live in a name-keyed registry, so new
decorators slot in without changing the pipeline core. ``none`` is the no-op; the ``title`` decorator is on by default (D-25).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable, Literal, Mapping, Optional, Sequence

from ..errors import RenderError
from ..event.plan import RenderPlan
from .segments import OverlaySpec, Segment

if TYPE_CHECKING:  # pragma: no cover - import cycle only needed for typing
    from .target import TargetSpec

#: A decorator is a pure transform over the segment list.
Decorator = Callable[[RenderPlan, "TargetSpec", tuple[Segment, ...]], tuple[Segment, ...]]

#: Factory signatures for the two decorator shapes.
SegmentProducer = Callable[[RenderPlan, "TargetSpec"], Segment]
Positioner = Callable[[tuple[Segment, ...]], int]
OverlayProducer = Callable[[RenderPlan, "TargetSpec", Segment], Optional[OverlaySpec]]
SegmentPredicate = Callable[[Segment, int], bool]

_REGISTRY: dict[str, Decorator] = {}


def register_decorator(name: str, decorator: Decorator) -> None:
    """Register ``decorator`` under ``name`` (last registration wins)."""
    _REGISTRY[name] = decorator


def get_decorator(name: str) -> Decorator:
    """Return the decorator registered under ``name``, or fail loud.

    Raises:
        RenderError: naming the unknown decorator and the registered names, so a
            misconfigured look fails loud rather than silently skipping a feature.
    """
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise RenderError(
            f"unknown decorator {name!r}; registered decorators: {sorted(_REGISTRY)}"
        ) from exc


def none_decorator(
    plan: RenderPlan, target: "TargetSpec", segments: tuple[Segment, ...]
) -> tuple[Segment, ...]:
    """The default decorator: return the segment list unchanged."""
    del plan, target  # a no-op consults neither
    return segments


def make_inserter(produce: SegmentProducer, position: Positioner) -> Decorator:
    """Build an **inserter** decorator that adds a synthetic segment.

    ``produce`` builds the synthetic :class:`Segment`; ``position`` chooses the
    insertion index against the current list (e.g. ``lambda segs: 0`` to prepend).
    """

    def decorator(
        plan: RenderPlan, target: "TargetSpec", segments: tuple[Segment, ...]
    ) -> tuple[Segment, ...]:
        new_segment = produce(plan, target)
        index = position(segments)
        return tuple(segments[:index]) + (new_segment,) + tuple(segments[index:])

    return decorator


def make_attacher(overlay_for: OverlayProducer, predicate: SegmentPredicate) -> Decorator:
    """Build an **attacher** decorator that adds an :class:`OverlaySpec`.

    ``predicate(segment, index)`` selects which segments to decorate;
    ``overlay_for`` builds the overlay (or returns ``None`` to skip one).
    """

    def decorator(
        plan: RenderPlan, target: "TargetSpec", segments: tuple[Segment, ...]
    ) -> tuple[Segment, ...]:
        out: list[Segment] = []
        for index, segment in enumerate(segments):
            if predicate(segment, index):
                overlay = overlay_for(plan, target, segment)
                if overlay is not None:
                    segment = replace(segment, overlays=segment.overlays + (overlay,))
            out.append(segment)
        return tuple(out)

    return decorator


#: The decorators in force when neither the event nor the project names any (D-25): the
#: opening card and each named chapter's card.
DEFAULT_DECORATORS: tuple[str, ...] = ("title",)


def _decorator_list(raw: object) -> tuple[str, ...]:
    """``raw`` (a ``look.decorators`` value) as names, or fail loud on a non-list."""
    if not isinstance(raw, (list, tuple)):
        raise RenderError(f"look.decorators must be a list of names, got {raw!r}")
    return tuple(str(name) for name in raw)


def resolve_decorator_names(look: Mapping[str, object]) -> tuple[str, ...]:
    """Resolve the ordered decorator names from the resolved ``look`` (D-2, D-25).

    ``look.decorators`` is an ordered list of names. Absent (or null) from the merged look
    means :data:`DEFAULT_DECORATORS`, so title cards are on unless the author opts out; an
    explicit list keeps its meaning, so ``[]``, ``[none]`` and any list without ``title``
    produce no card. A non-list value fails loud.
    """
    raw = look.get("decorators")
    if raw is None:
        return DEFAULT_DECORATORS
    return _decorator_list(raw)


@dataclass(frozen=True)
class TitleCardsState:
    """Whether a render draws title cards and which layer decided it."""

    enabled: bool
    source: Literal["event", "project", "default"]


def title_cards_state(
    event_look: Mapping[str, object], project_look: Mapping[str, object]
) -> TitleCardsState:
    """Whether title cards are on, and whether the event, the project or the default decided.

    ``event_look`` is the event ``reel.yaml`` ``look`` and ``project_look`` the ``config.yaml``
    one; a key at a time, the event wins (D-J). The names come from
    :func:`resolve_decorator_names` over the same merge ``resolve()`` performs, so the render and
    this report cannot disagree. Probe-free and read-only.
    """
    merged = {**project_look, **event_look}  # the merge resolve() performs (top level, event wins)
    source: Literal["event", "project", "default"]
    if merged.get("decorators") is None:
        source = "default"
    elif event_look.get("decorators") is not None:
        source = "event"
    else:
        source = "project"
    return TitleCardsState("title" in resolve_decorator_names(merged), source)


def apply_decorators(
    names: Sequence[str],
    plan: RenderPlan,
    target: "TargetSpec",
    segments: tuple[Segment, ...],
) -> tuple[Segment, ...]:
    """Apply the named decorators in order; an unknown name fails loud."""
    for name in names:
        decorator = get_decorator(name)
        segments = tuple(decorator(plan, target, segments))
    return segments


register_decorator("none", none_decorator)


__all__ = [
    "Decorator",
    "register_decorator",
    "get_decorator",
    "none_decorator",
    "make_inserter",
    "make_attacher",
    "resolve_decorator_names",
    "apply_decorators",
]
