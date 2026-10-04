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

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..errors import RenderError
from .segments import OverlaySpec, Segment

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


def materialize_overlay(overlay: OverlaySpec, target: "TargetSpec", dest: Path) -> OverlaySpec:
    """Turn a producer-backed overlay into a plain one: its image, window and fades.

    Asks the registered producer (the one that serves inserted segments too) to render
    the overlay's image to ``dest``, and returns a copy whose ``source`` is that image,
    whose window is ``[0, duration)`` and whose fades are the produced timings. An overlay
    without a producer is returned as it is.

    Raises:
        RenderError: the overlay names a producer that is not registered.
    """
    if overlay.producer is None:
        return overlay
    producer = get_producer(overlay.producer)
    carrier = Segment(
        chapter="", producer=overlay.producer, producer_config=overlay.producer_config
    )
    produced = producer(carrier, target, dest)
    return replace(
        overlay,
        source=str(produced.image_path),
        start=0.0,
        end=produced.duration,
        fade_in=produced.fade_in,
        fade_out=produced.fade_out,
        timed=True,
    )


__all__ = [
    "ProducedSegment",
    "materialize_overlay",
    "Producer",
    "register_producer",
    "get_producer",
]
