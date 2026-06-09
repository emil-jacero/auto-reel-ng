"""The segment-producer seam: name-keyed materialization of synthetic segments.

Parallel to the decorator registry (decision **D-C**), a **producer** materializes
a synthetic :class:`~auto_reel_ng.render.segments.Segment` into the inputs the
normalize step needs — a rendered image (or source) path, the segment duration,
and the fade-in/out timing — without itself invoking encoding (that is
``clip-normalize``'s job). New producers register by name without touching the
pipeline core, so future synthetic look features (intro, outro, transition
bumpers) reuse the seam. The title card registers the first producer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..errors import RenderError
from .segments import Segment

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .target import TargetSpec


@dataclass(frozen=True)
class ProducedSegment:
    """A materialized synthetic segment: the asset plus the timing normalize needs.

    ``image_path`` is the rendered card (or any image/source) to loop; ``duration``
    is the segment length in seconds; ``fade_in``/``fade_out`` are the fade
    durations the normalize step turns into ``fade=t=in``/``fade=t=out``. It carries
    everything required to encode to the target spec and nothing about encoding.
    """

    image_path: Path
    duration: float
    fade_in: float = 0.0
    fade_out: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug/golden logging."""
        return {
            "image_path": str(self.image_path),
            "duration": self.duration,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
        }


#: A producer renders a synthetic segment's asset to ``dest`` and describes it.
Producer = Callable[[Segment, "TargetSpec", Path], ProducedSegment]

_REGISTRY: dict[str, Producer] = {}


def register_producer(name: str, producer: Producer) -> None:
    """Register ``producer`` under ``name`` (last registration wins)."""
    _REGISTRY[name] = producer


def get_producer(name: str) -> Producer:
    """Return the producer registered under ``name``, or fail loud.

    Dropping a synthetic segment would change the edit, so an unregistered
    producer raises a typed error naming the unknown producer and the registered
    names rather than silently skipping the segment.
    """
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise RenderError(
            f"unknown segment producer {name!r}; registered producers: {sorted(_REGISTRY)}"
        ) from exc


__all__ = [
    "ProducedSegment",
    "Producer",
    "register_producer",
    "get_producer",
]
