"""The analysis state rule (``analysis-enqueue-api``): stat + JSON only, never guessed.

No database and no ffmpeg: entries and failure markers are written with the cache's own
writers, and any process the reads start fails the test.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from auto_reel_ng.analysis import state as state_module
from auto_reel_ng.analysis.cache import (
    EntryFileKind,
    _entry_path,
    clip_signal,
    inspect_entry,
    pending_clips,
    write_entry,
    write_failure,
)
from auto_reel_ng.analysis.models import Segment, SegmentKind
from auto_reel_ng.analysis.state import (
    ClipAnalysis,
    ClipAnalysisState,
    clip_analysis_states,
    event_disk_state,
    needs_analysis,
)
from auto_reel_ng.errors import AnalysisStateError

NEVER = ClipAnalysisState.NEVER
STALE = ClipAnalysisState.STALE
CURRENT = ClipAnalysisState.CURRENT
FAILED = ClipAnalysisState.FAILED

SEGMENTS = [Segment(start=0.0, end=2.5, kind=SegmentKind.BLACK, confidence=0.9)]


@pytest.fixture(autouse=True)
def no_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading a state starts no process: ffmpeg, ffprobe or anything else fails the test."""

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(f"the state read started a process: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)


@pytest.fixture
def event(tmp_path: Path) -> Path:
    """An event with two root clips and one in a chapter folder."""
    event_dir = tmp_path / "2023-06-23 - Midsommar - Dalarna"
    (event_dir / "chapter").mkdir(parents=True)
    for identity in ("C0001.MP4", "C0002.MP4", "chapter/C0003.MP4"):
        (event_dir / identity).write_bytes(f"clip {identity}".encode())
    return event_dir


def _analyze(event_dir: Path, identity: str) -> None:
    write_entry(event_dir, identity, clip_signal(event_dir / identity), SEGMENTS)


def _fail(event_dir: Path, identity: str, cause: str = "moov atom not found") -> None:
    write_failure(event_dir, identity, clip_signal(event_dir / identity), cause)


def _replace(clip: Path) -> None:
    """Replace the clip by another file (another size and mtime): its signal changes."""
    clip.write_bytes(clip.read_bytes() + b" re-exported")
    stat = clip.stat()
    os.utime(clip, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))


def _states(event_dir: Path) -> Dict[str, ClipAnalysisState]:
    return {clip.identity: clip.state for clip in clip_analysis_states(event_dir)}


def _snapshot(root: Path) -> List[Tuple[str, int]]:
    return sorted((str(p.relative_to(root)), p.stat().st_mtime_ns) for p in root.rglob("*"))


# --------------------------------------------------------------------------- #
# Per clip
# --------------------------------------------------------------------------- #


def test_a_clip_analyzed_as_it_is_now_is_current_with_its_segments(event: Path) -> None:
    _analyze(event, "C0001.MP4")

    first, *_rest = clip_analysis_states(event)

    assert first.identity == "C0001.MP4" and first.state is CURRENT
    assert list(first.segments) == SEGMENTS and first.detail is None


def test_nothing_on_disk_is_never(event: Path) -> None:
    assert _states(event) == {"C0001.MP4": NEVER, "C0002.MP4": NEVER, "chapter/C0003.MP4": NEVER}


def test_a_failure_marker_for_the_current_signal_is_failed_with_its_cause(event: Path) -> None:
    _fail(event, "C0002.MP4", "moov atom not found")

    clip = {c.identity: c for c in clip_analysis_states(event)}["C0002.MP4"]

    assert clip.state is FAILED and clip.detail == "moov atom not found"
    assert clip.segments == ()


def test_an_entry_or_a_marker_of_an_older_signal_is_stale(event: Path) -> None:
    _analyze(event, "C0001.MP4")
    _fail(event, "C0002.MP4")
    _replace(event / "C0001.MP4")
    _replace(event / "C0002.MP4")

    states = _states(event)

    assert states["C0001.MP4"] is STALE and states["C0002.MP4"] is STALE


def test_a_truncated_entry_and_an_entry_of_another_version_are_stale(event: Path) -> None:
    _analyze(event, "C0001.MP4")
    _analyze(event, "C0002.MP4")
    first = _entry_path(event, "C0001.MP4")
    first.write_text(first.read_text()[:20])
    second = _entry_path(event, "C0002.MP4")
    second.write_text(second.read_text().replace('"version": 1', '"version": 99'))

    states = _states(event)

    assert states["C0001.MP4"] is STALE and states["C0002.MP4"] is STALE


def test_an_entry_that_cannot_be_read_raises_and_reports_no_state(event: Path) -> None:
    _analyze(event, "C0001.MP4")
    entry = _entry_path(event, "C0001.MP4")
    entry.chmod(0)
    try:
        with pytest.raises(AnalysisStateError, match="C0001.MP4"):
            clip_analysis_states(event)
    finally:
        entry.chmod(0o644)


def test_a_clip_that_cannot_be_statted_raises(event: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(path: Path, **kwargs: Any) -> Dict[str, object]:
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(state_module, "clip_signal", denied)

    with pytest.raises(AnalysisStateError, match="cannot stat"):
        clip_analysis_states(event)


def test_an_event_folder_that_cannot_be_listed_raises_its_os_error(event: Path) -> None:
    event.chmod(0)
    try:
        with pytest.raises(OSError):
            clip_analysis_states(event)
    finally:
        event.chmod(0o755)


def test_ignored_and_chapter_folder_clips_are_included_and_reel_yaml_is_not_read(
    event: Path,
) -> None:
    # A reel.yaml that does not parse, and that would not list any of these clips anyway.
    (event / "reel.yaml").write_text("version: 0\nmetadata: [unterminated\n")

    assert list(_states(event)) == ["C0001.MP4", "C0002.MP4", "chapter/C0003.MP4"]


def test_reading_the_state_writes_nothing(event: Path) -> None:
    _analyze(event, "C0001.MP4")
    _fail(event, "C0002.MP4")
    before = _snapshot(event)

    clip_analysis_states(event)

    assert _snapshot(event) == before


# --------------------------------------------------------------------------- #
# Per event
# --------------------------------------------------------------------------- #


def _clips(*states: ClipAnalysisState) -> List[ClipAnalysis]:
    return [ClipAnalysis(identity=f"{i}.mp4", state=s) for i, s in enumerate(states)]


@pytest.mark.parametrize(
    ("states", "expected", "needs"),
    [
        ((), CURRENT, False),
        ((CURRENT, CURRENT), CURRENT, False),
        ((NEVER, NEVER), NEVER, True),
        ((CURRENT, NEVER), STALE, True),
        ((CURRENT, STALE), STALE, True),
        ((FAILED, NEVER), STALE, True),
        ((CURRENT, FAILED), FAILED, False),
        ((FAILED,), FAILED, False),
    ],
)
def test_the_event_state_is_the_first_rule_that_holds(
    states: Tuple[ClipAnalysisState, ...], expected: ClipAnalysisState, needs: bool
) -> None:
    clips = _clips(*states)

    assert event_disk_state(clips) is expected
    assert needs_analysis(clips) is needs


def test_a_failed_clip_stays_failed_until_it_changes(event: Path) -> None:
    _analyze(event, "C0001.MP4")
    _analyze(event, "chapter/C0003.MP4")
    _fail(event, "C0002.MP4")

    clips = clip_analysis_states(event)
    assert event_disk_state(clips) is FAILED and not needs_analysis(clips)

    _replace(event / "C0002.MP4")
    clips = clip_analysis_states(event)
    assert event_disk_state(clips) is STALE and needs_analysis(clips)


def test_a_new_clip_makes_an_analyzed_event_stale(event: Path) -> None:
    for identity in ("C0001.MP4", "C0002.MP4", "chapter/C0003.MP4"):
        _analyze(event, identity)
    assert event_disk_state(clip_analysis_states(event)) is CURRENT

    (event / "C0004.MP4").write_bytes(b"a new clip")
    clips = clip_analysis_states(event)

    assert {c.identity: c.state for c in clips}["C0004.MP4"] is NEVER
    assert event_disk_state(clips) is STALE and needs_analysis(clips)


def test_an_event_with_no_clips_is_current_and_needs_nothing(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("no clips here")

    clips = clip_analysis_states(tmp_path)

    assert clips == [] and event_disk_state(clips) is CURRENT and not needs_analysis(clips)


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        ({"never": 1, "stale": 0, "current": 0, "failed": 0}, True),
        ({"never": 0, "stale": 1, "current": 1, "failed": 0}, True),
        ({"never": 0, "stale": 0, "current": 2, "failed": 0}, False),
        ({"never": 0, "stale": 0, "current": 1, "failed": 1}, False),
    ],
)
def test_needs_analysis_selects_never_and_stale_events_only(
    tmp_path: Path, kinds: Dict[str, int], expected: bool
) -> None:
    for kind, count in kinds.items():
        for index in range(count):
            identity = f"{kind}{index}.mp4"
            (tmp_path / identity).write_bytes(identity.encode())
            if kind in ("stale", "current"):
                _analyze(tmp_path, identity)
            if kind == "failed":
                _fail(tmp_path, identity)
            if kind == "stale":
                _replace(tmp_path / identity)

    assert needs_analysis(clip_analysis_states(tmp_path)) is expected


# --------------------------------------------------------------------------- #
# inspect_entry
# --------------------------------------------------------------------------- #


def test_inspect_entry_tells_every_kind_apart(event: Path) -> None:
    signal = clip_signal(event / "C0001.MP4")
    other = {**signal, "size": -1}

    assert inspect_entry(event, "C0001.MP4", signal).kind is EntryFileKind.ABSENT
    write_entry(event, "C0001.MP4", signal, SEGMENTS)
    result = inspect_entry(event, "C0001.MP4", signal)
    assert result.kind is EntryFileKind.RESULT and result.segments == SEGMENTS
    assert inspect_entry(event, "C0001.MP4", other).kind is EntryFileKind.OTHER
    write_failure(event, "C0001.MP4", signal, "boom")
    failure = inspect_entry(event, "C0001.MP4", signal)
    assert failure.kind is EntryFileKind.FAILURE and failure.failure == "boom"
    assert inspect_entry(event, "C0001.MP4", other).kind is EntryFileKind.OTHER
    _entry_path(event, "C0001.MP4").write_bytes(b"\xff\xfe not text")
    assert inspect_entry(event, "C0001.MP4", signal).kind is EntryFileKind.OTHER
    _entry_path(event, "C0001.MP4").write_text('{"version": 1, "signal": %s, "segments": 3}' % "{}")
    assert inspect_entry(event, "C0001.MP4", {}).kind is EntryFileKind.OTHER


# The sweep's rule (analysis-auto-sweep) and this one agree


def test_never_and_stale_are_exactly_the_clips_the_sweep_finds_pending(event: Path) -> None:
    """``never``/``stale`` here is ``missing`` in ``cache.entry_state``: one selection rule."""
    (event / "C0004.MP4").write_bytes(b"clip C0004.MP4")
    _analyze(event, "C0001.MP4")  # current
    _fail(event, "C0002.MP4")  # failed
    _analyze(event, "chapter/C0003.MP4")
    _replace(event / "chapter" / "C0003.MP4")  # stale
    # C0004.MP4: never
    clips = clip_analysis_states(event)
    due = [c.identity for c in clips if c.state in (NEVER, STALE)]
    assert due == pending_clips(event)
    assert sorted(due) == ["C0004.MP4", "chapter/C0003.MP4"]
    assert needs_analysis(clips) is bool(pending_clips(event))
