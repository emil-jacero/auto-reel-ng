"""Chapter times (change render-chapter-times): pure arithmetic, no ffmpeg.

The recorded numbers must be the ``[CHAPTER]`` marker numbers, so these tests pin the one boundary
rule both ``build_ffmetadata`` and ``chapter_times`` use.
"""

from __future__ import annotations

import re

import pytest

from auto_reel_ng.errors import RenderError
from auto_reel_ng.render.chapters import (
    aggregate_chapter_durations,
    build_ffmetadata,
    chapter_times,
)
from auto_reel_ng.render.segments import Segment
from auto_reel_ng.render.title import TITLE_PRODUCER
from auto_reel_ng.staleness.manifest import ChapterTime, TitleCardSpan


def _clip(chapter: str, identity: str = "a") -> Segment:
    return Segment(chapter=chapter, identity=identity)


def _card(chapter: str) -> Segment:
    return Segment(chapter=chapter, producer=TITLE_PRODUCER, duration=3.0)


def test_a_trimmed_chapter_and_a_second_chapter() -> None:
    segments = [_clip("A", "a1"), _clip("A", "a2"), _clip("B", "b")]

    times = chapter_times(segments, [1.0, 0.5, 2.0])

    assert times == (
        ChapterTime(name="A", start_ms=0, end_ms=1500),
        ChapterTime(name="B", start_ms=1500, end_ms=3500),
    )


def test_a_measured_duration_is_recorded_as_measured() -> None:
    (only,) = chapter_times([_clip("A")], [0.967])

    assert (only.start_ms, only.end_ms) == (0, 967)


def test_a_title_card_in_the_second_chapter() -> None:
    segments = [_clip("A"), _card("B"), _clip("B", "b")]

    first, second = chapter_times(segments, [2.0, 3.0, 1.0])

    assert (second.start_ms, second.end_ms) == (2000, 6000)
    assert second.title_card == TitleCardSpan(start_ms=2000, end_ms=5000)
    assert first.title_card is None


def test_a_card_after_an_earlier_clip_starts_inside_the_chapter() -> None:
    segments = [_clip("A", "a1"), _card("A"), _clip("A", "a2")]

    (chapter,) = chapter_times(segments, [1.0, 3.0, 2.0])

    assert chapter.title_card == TitleCardSpan(start_ms=1000, end_ms=4000)
    assert (chapter.start_ms, chapter.end_ms) == (0, 6000)


def test_no_card_means_none() -> None:
    assert [c.title_card for c in chapter_times([_clip("A"), _clip("B")], [1.0, 1.0])] == [
        None,
        None,
    ]


@pytest.mark.parametrize("awkward", [0.0004, 0.0005, 1.0005, 0.0015, 2.9995])
def test_a_card_span_never_pokes_out_of_its_chapter(awkward: float) -> None:
    segments = [_clip("A", "a1"), _clip("A", "a2"), _card("A"), _clip("A", "a3"), _clip("B")]

    first, _second = chapter_times(segments, [awkward, 0.0005, awkward, 0.0004, awkward])

    card = first.title_card
    assert card is not None
    assert first.start_ms <= card.start_ms <= card.end_ms <= first.end_ms
    assert abs((card.end_ms - card.start_ms) - round(awkward * 1000)) <= 1


def _markers(text: str) -> list[tuple[int, int]]:
    starts = [int(v) for v in re.findall(r"^START=(\d+)$", text, re.MULTILINE)]
    ends = [int(v) for v in re.findall(r"^END=(\d+)$", text, re.MULTILINE)]
    return list(zip(starts, ends))


@pytest.mark.parametrize(
    "durations",
    [[1.0, 0.5, 2.0], [0.0004, 0.0005, 1.0005], [0.967, 1.0335, 0.0015]],
)
def test_chapter_times_equal_the_ffmetadata_markers(durations: list[float]) -> None:
    segments = [_clip("A", "a1"), _clip("A", "a2"), _clip("B")]

    times = chapter_times(segments, durations)
    markers = _markers(build_ffmetadata(aggregate_chapter_durations(segments, durations)))

    assert [(c.start_ms, c.end_ms) for c in times] == markers
    assert [c.name for c in times] == ["A", "B"]


def test_ffmetadata_output_is_unchanged() -> None:
    assert build_ffmetadata([("Intro", 2.0), ("Ma=in", 3.0)]) == (
        ";FFMETADATA1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Intro\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=2000\nEND=5000\ntitle=Ma\\=in\n"
    )


def test_two_cards_in_one_chapter_raise() -> None:
    segments = [_card("A"), _clip("A"), _card("A")]

    with pytest.raises(RenderError, match="more than one title card"):
        chapter_times(segments, [1.0, 1.0, 1.0])


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        chapter_times([_clip("A")], [1.0, 2.0])
