"""Real ``ffmetadata`` ``[CHAPTER]`` markers from measured durations (movie-assembly).

auto-reel wrote chapters that never reached the container. Here the chapter
boundaries are computed from the **measured** durations of the produced
intermediates (probed, not nominal), so the chapter timeline exactly matches the
concatenated segment timeline, and the metadata is muxed into the output.
"""

from __future__ import annotations

from typing import Optional, Sequence

from ..errors import RenderError
from ..staleness.manifest import ChapterTime, TitleCardSpan
from .segments import Segment
from .title import TITLE_PRODUCER


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


def _chapter_bounds_ms(chapters: Sequence[tuple[str, float]]) -> list[tuple[str, int, int]]:
    """The one boundary rule: ``(name, start_ms, end_ms)``, cumulative, 1/1000 timebase.

    Each chapter's length is ``round(duration * 1000)`` and each start is the previous end. The
    ``[CHAPTER]`` markers and the recorded chapter times both come from here, so they cannot differ.
    """
    bounds: list[tuple[str, int, int]] = []
    cursor_ms = 0
    for name, duration in chapters:
        end = cursor_ms + round(duration * 1000)
        bounds.append((name, cursor_ms, end))
        cursor_ms = end
    return bounds


def build_ffmetadata(chapters: Sequence[tuple[str, float]]) -> str:
    """Build an ``ffmetadata`` document with one ``[CHAPTER]`` per entry.

    ``chapters`` is an ordered list of ``(name, measured_duration_seconds)``.
    Start/end timestamps are cumulative, in a 1/1000 (millisecond) timebase.
    """
    lines = [";FFMETADATA1"]
    for name, start, end in _chapter_bounds_ms(chapters):
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start}",
            f"END={end}",
            f"title={_escape(name)}",
        ]
    return "\n".join(lines) + "\n"


def _title_card_spans(
    segments: Sequence[Segment], durations: Sequence[float]
) -> dict[str, tuple[float, float]]:
    """Per chapter with a title card: ``(seconds before the card, seconds through its end)``.

    Both are running sums in segment order, the order :func:`aggregate_chapter_durations` adds in,
    so the second never exceeds the chapter's total. More than one card in a chapter is refused.
    """
    running: dict[str, float] = {}
    spans: dict[str, tuple[float, float]] = {}
    for segment, duration in zip(segments, durations):
        before = running.get(segment.chapter, 0.0)
        after = before + duration
        running[segment.chapter] = after
        if segment.producer != TITLE_PRODUCER:
            continue
        if segment.chapter in spans:
            raise RenderError(f"chapter {segment.chapter!r} has more than one title card")
        spans[segment.chapter] = (before, after)
    return spans


def chapter_times(
    segments: Sequence[Segment], durations: Sequence[float]
) -> tuple[ChapterTime, ...]:
    """The chapter times of the movie ``segments`` concatenate, from their measured ``durations``.

    One entry per chapter in movie order, with the same start/end the ``[CHAPTER]`` markers carry
    (:func:`build_ffmetadata` uses the same boundary rule). A chapter's title-card span is its start
    plus the measured seconds before the card, to its start plus those and the card's own seconds,
    each rounded to milliseconds once from the exact sum, so it lies inside the chapter. Raises
    ``ValueError`` if ``segments`` and ``durations`` differ in length (from the aggregation) and
    :class:`RenderError` for a chapter with two title cards.
    """
    pairs = aggregate_chapter_durations(segments, durations)
    spans = _title_card_spans(segments, durations)
    result: list[ChapterTime] = []
    for name, start, end in _chapter_bounds_ms(pairs):
        card: Optional[TitleCardSpan] = None
        if name in spans:
            before, after = spans[name]
            card = TitleCardSpan(start + round(before * 1000), start + round(after * 1000))
        result.append(ChapterTime(name=name, start_ms=start, end_ms=end, title_card=card))
    return tuple(result)


__all__ = ["aggregate_chapter_durations", "build_ffmetadata", "chapter_times"]
