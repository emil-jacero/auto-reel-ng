"""The decorator seam: pluggable "look" features (decision **D-B**).

A decorator is a pure transform ``(plan, target, segments) -> segments``. Two
shapes cover every look feature foreseen: an **inserter** adds one or more
synthetic segments at a defined position (title card, intro, outro, transition
bumper), and an **attacher** adds an :class:`OverlaySpec` to existing segments
(title-over-footage, watermark, lower-third). Decorators are selected by name
from the resolved ``look``/config and live in a name-keyed registry, so new
decorators slot in without changing the pipeline core. v1 ships only ``none``;
the title change (#5) registers real decorators.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Callable, Mapping, Optional, Sequence

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


def resolve_decorator_names(look: Mapping[str, object]) -> tuple[str, ...]:
    """Resolve the ordered decorator names from the resolved ``look`` (D-2).

    ``look.decorators`` is an ordered list of names; absent means the ``none``
    default. A non-list value fails loud.
    """
    raw = look.get("decorators")
    if raw is None:
        return ("none",)
    if not isinstance(raw, (list, tuple)):
        raise RenderError(f"look.decorators must be a list of names, got {raw!r}")
    return tuple(str(name) for name in raw)


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
