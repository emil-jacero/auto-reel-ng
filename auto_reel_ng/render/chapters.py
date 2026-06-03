"""Real ``ffmetadata`` ``[CHAPTER]`` markers from measured durations (movie-assembly).

auto-reel wrote chapters that never reached the container. Here the chapter
boundaries are computed from the **measured** durations of the produced
intermediates (probed, not nominal), so the chapter timeline exactly matches the
concatenated segment timeline, and the metadata is muxed into the output.
"""

from __future__ import annotations

from typing import Sequence

from .segments import Segment


def aggregate_chapter_durations(
    segments: Sequence[Segment], durations: Sequence[float]
) -> list[tuple[str, float]]:
    """Sum measured ``durations`` per chapter, preserving first-seen chapter order.

    ``durations[i]`` is the measured length of ``segments[i]``'s intermediate.
    Because flattening keeps each chapter's segments contiguous and in order, the
    cumulative chapter boundaries equal the cumulative segment timeline.
    """
    if len(segments) != len(durations):
        raise ValueError("segments and durations must be the same length")
    order: list[str] = []
    totals: dict[str, float] = {}
    for segment, duration in zip(segments, durations):
        if segment.chapter not in totals:
            order.append(segment.chapter)
            totals[segment.chapter] = 0.0
        totals[segment.chapter] += duration
    return [(name, totals[name]) for name in order]


def _escape(value: str) -> str:
    """Escape the ffmetadata special characters (``=``, ``;``, ``#``, ``\\``, NL)."""
    out = value.replace("\\", "\\\\")
    for special in ("=", ";", "#", "\n"):
        out = out.replace(special, "\\" + special)
    return out


def build_ffmetadata(chapters: Sequence[tuple[str, float]]) -> str:
    """Build an ``ffmetadata`` document with one ``[CHAPTER]`` per entry.

    ``chapters`` is an ordered list of ``(name, measured_duration_seconds)``.
    Start/end timestamps are cumulative, in a 1/1000 (millisecond) timebase.
    """
    lines = [";FFMETADATA1"]
    cursor_ms = 0
    for name, duration in chapters:
        start = cursor_ms
        end = cursor_ms + round(duration * 1000)
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start}",
            f"END={end}",
            f"title={_escape(name)}",
        ]
        cursor_ms = end
    return "\n".join(lines) + "\n"


__all__ = ["aggregate_chapter_durations", "build_ffmetadata"]
