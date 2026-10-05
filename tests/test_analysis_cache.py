"""Sidecar-cache tests: cold-write, warm-read, invalidation, corrupt recovery (task 6.x).

``analyze_clip`` (the only ffmpeg-touching step) is stubbed with a call-counting fake,
so these run headless. The fake stands in for detection; the assertions are about the
cache's read/write/invalidate behavior and that a warm hit skips detection entirely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import pytest

from auto_reel_ng.analysis import cache as cache_module
from auto_reel_ng.analysis.cache import analyze_event, cache_dir, read_entry
from auto_reel_ng.analysis.models import AnalysisConfig, Segment, SegmentKind
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime

SEGMENTS = [Segment(start=0.0, end=3.0, kind=SegmentKind.BLACK, confidence=0.5)]


class CountingDetector:
    """A stubbed ``analyze_clip`` recording how many clips it was asked to detect."""

    def __init__(self) -> None:
        self.calls: List[Path] = []

    def __call__(
        self,
        path: Path,
        *,
        runtime: Optional[FfmpegRuntime] = None,
        config: Optional[AnalysisConfig] = None,
    ) -> List[Segment]:
        self.calls.append(Path(path))
        return list(SEGMENTS)


@pytest.fixture
def event_dir(tmp_path: Path) -> Path:
    """An event directory holding one root-level clip file (contents irrelevant here)."""
    (tmp_path / "clip.mp4").write_bytes(b"a-fake-clip")
    return tmp_path


def _install_detector(monkeypatch: pytest.MonkeyPatch) -> CountingDetector:
    detector = CountingDetector()
    monkeypatch.setattr(cache_module, "analyze_clip", detector)
    return detector


def test_cold_run_writes_cache(event_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cold run detects each clip and persists an entry under .auto-reel/cache/."""
    detector = _install_detector(monkeypatch)

    results = analyze_event(event_dir)

    assert results == {"clip.mp4": SEGMENTS}
    assert detector.calls == [event_dir / "clip.mp4"]
    entries = list(cache_dir(event_dir).glob("*.json"))
    assert len(entries) == 1


def test_warm_run_reads_cache_without_detection(
    event_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second run over an unchanged clip returns cached segments and runs no detection."""
    detector = _install_detector(monkeypatch)
    analyze_event(event_dir)  # cold: writes the entry
    assert len(detector.calls) == 1

    detector.calls.clear()
    results = analyze_event(event_dir)  # warm: must not detect again

    assert results == {"clip.mp4": SEGMENTS}
    assert detector.calls == []


def test_modified_clip_reruns_detection(event_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Changing the clip's content-change signal invalidates the entry and re-detects."""
    detector = _install_detector(monkeypatch)
    analyze_event(event_dir)
    assert len(detector.calls) == 1

    # Change the clip's size (and thus the signal); the cached entry is now stale.
    (event_dir / "clip.mp4").write_bytes(b"a-fake-clip-but-longer-now")
    detector.calls.clear()
    analyze_event(event_dir)

    assert detector.calls == [event_dir / "clip.mp4"]


def test_corrupt_entry_recovers(event_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unparseable cache entry is treated as cold: detection re-runs and rewrites it."""
    detector = _install_detector(monkeypatch)
    analyze_event(event_dir)
    entry = next(iter(cache_dir(event_dir).glob("*.json")))

    entry.write_text("{ this is not valid json", encoding="utf-8")
    detector.calls.clear()
    results = analyze_event(event_dir)

    assert detector.calls == [event_dir / "clip.mp4"]
    assert results == {"clip.mp4": SEGMENTS}
    # A fresh, valid entry was written back.
    import json  # noqa: PLC0415

    assert json.loads(entry.read_text(encoding="utf-8"))["identity"] == "clip.mp4"


def test_entry_roundtrips_segments(event_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Segments written to an entry deserialize back to equal Segment values."""
    _install_detector(monkeypatch)
    analyze_event(event_dir)

    signal = cache_module.clip_signal(event_dir / "clip.mp4")
    assert read_entry(event_dir, "clip.mp4", signal) == SEGMENTS


def test_signal_mismatch_returns_none() -> None:
    """read_entry treats a differing signal as stale (returns None)."""
    # No entry written at all -> also None (missing entry is cold).
    assert read_entry(Path("/no/such/event"), "clip.mp4", {"size": 1, "mtime_ns": 1}) is None


# -- analysis-job: atomic writes, failure markers, force (task 1.1) -----------------------


def _signal(event_dir: Path) -> dict[str, object]:
    return cache_module.clip_signal(event_dir / "clip.mp4")


def test_failed_replace_keeps_previous_entry_and_no_temporary_file(
    event_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write that fails at the rename leaves the old entry intact and removes its temp file."""
    signal = _signal(event_dir)
    cache_module.write_entry(event_dir, "clip.mp4", signal, SEGMENTS)

    def broken_replace(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(cache_module.os, "replace", broken_replace)
    with pytest.raises(OSError, match="disk full"):
        cache_module.write_entry(event_dir, "clip.mp4", signal, [])

    assert read_entry(event_dir, "clip.mp4", signal) == SEGMENTS
    assert [p.name for p in cache_dir(event_dir).iterdir() if ".part" in p.name] == []


def test_write_entry_goes_through_a_temporary_file(
    event_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The entry is renamed into place from a temporary file in the same directory."""
    seen: list[tuple[Path, Path]] = []
    real_replace = cache_module.os.replace

    def spying_replace(src: str, dst: str) -> None:
        seen.append((Path(src), Path(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(cache_module.os, "replace", spying_replace)
    path = cache_module.write_entry(event_dir, "clip.mp4", _signal(event_dir), SEGMENTS)

    assert len(seen) == 1
    src, dst = seen[0]
    assert dst == path and src.parent == path.parent and ".part-" in src.name
    assert not src.exists()


def test_failure_marker_round_trips_and_is_not_an_entry(event_dir: Path) -> None:
    """A marker carries its cause for the same signal and reads as no result."""
    signal = _signal(event_dir)
    cache_module.write_failure(event_dir, "clip.mp4", signal, "cannot probe")

    assert cache_module.read_failure(event_dir, "clip.mp4", signal) == "cannot probe"
    assert read_entry(event_dir, "clip.mp4", signal) is None


def test_failure_marker_with_an_old_signal_is_ignored(event_dir: Path) -> None:
    """A marker written for an earlier version of the clip does not apply to the new one."""
    old = _signal(event_dir)
    cache_module.write_failure(event_dir, "clip.mp4", old, "cannot probe")

    new = {**old, "size": 999}
    assert cache_module.read_failure(event_dir, "clip.mp4", new) is None


def test_success_replaces_a_failure_marker(event_dir: Path) -> None:
    """Writing an entry over a marker leaves the entry and no marker."""
    signal = _signal(event_dir)
    cache_module.write_failure(event_dir, "clip.mp4", signal, "cannot probe")
    cache_module.write_entry(event_dir, "clip.mp4", signal, SEGMENTS)

    assert read_entry(event_dir, "clip.mp4", signal) == SEGMENTS
    assert cache_module.read_failure(event_dir, "clip.mp4", signal) is None
    assert len(list(cache_dir(event_dir).glob("*.json"))) == 1


def test_an_entry_is_not_a_failure(event_dir: Path) -> None:
    """``read_failure`` answers ``None`` for a normal entry and for a missing one."""
    signal = _signal(event_dir)
    assert cache_module.read_failure(event_dir, "clip.mp4", signal) is None
    cache_module.write_entry(event_dir, "clip.mp4", signal, SEGMENTS)
    assert cache_module.read_failure(event_dir, "clip.mp4", signal) is None


def test_a_leftover_temporary_file_is_never_read(
    event_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A killed writer's ``*.part-*`` file is not an entry: the clip is still cold."""
    detector = _install_detector(monkeypatch)
    entry = cache_module._entry_path(event_dir, "clip.mp4")  # pylint: disable=protected-access
    entry.parent.mkdir(parents=True)
    leftover = entry.with_name(entry.name + ".part-123-abc")
    leftover.write_text('{"version": 1, "segments": [', encoding="utf-8")

    results = analyze_event(event_dir)

    assert detector.calls == [event_dir / "clip.mp4"]
    assert results == {"clip.mp4": SEGMENTS}
    assert leftover.exists()  # left alone, never read


def test_force_reruns_detection_on_a_warm_cache(
    event_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``force=True`` ignores a current entry and detects again."""
    detector = _install_detector(monkeypatch)
    analyze_event(event_dir)
    detector.calls.clear()

    analyze_event(event_dir, force=True)

    assert detector.calls == [event_dir / "clip.mp4"]


def test_an_entry_of_the_previous_format_still_reads(event_dir: Path) -> None:
    """An entry exactly as the pre-marker build wrote it is still a hit."""
    signal = _signal(event_dir)
    entry = cache_module._entry_path(event_dir, "clip.mp4")  # pylint: disable=protected-access
    entry.parent.mkdir(parents=True)
    entry.write_text(
        json.dumps(
            {
                "version": 1,
                "identity": "clip.mp4",
                "signal": signal,
                "segments": [{"start": 0.0, "end": 3.0, "kind": "black", "confidence": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    assert read_entry(event_dir, "clip.mp4", signal) == SEGMENTS


# --------------------------------------------------------------------------- #
# entry_state / pending_clips (analysis-auto-sweep 1.1): the one stat-only rule the analysis
# job and the automatic sweep share.
# --------------------------------------------------------------------------- #


def _forbid_media_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every ffmpeg/ffprobe start and every content hash raise."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a media read or process was started: {args!r}")

    import subprocess  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(cache_module, "analyze_clip", refuse)
    monkeypatch.setattr(cache_module, "_content_hash", refuse)


def _event_of_five(tmp_path: Path) -> Path:
    """current.mp4 (entry), stale.mp4 (entry for an old signal), new.mp4 (nothing),
    failed.mp4 (marker for its signal), refailed.mp4 (marker for an old signal)."""
    event = tmp_path / "event"
    event.mkdir()
    for name in ("current", "stale", "new", "failed", "refailed"):
        (event / f"{name}.mp4").write_bytes(name.encode())
    signal = cache_module.clip_signal
    cache_module.write_entry(event, "current.mp4", signal(event / "current.mp4"), SEGMENTS)
    cache_module.write_entry(event, "stale.mp4", signal(event / "stale.mp4"), SEGMENTS)
    cache_module.write_failure(event, "failed.mp4", signal(event / "failed.mp4"), "moov missing")
    cache_module.write_failure(
        event, "refailed.mp4", signal(event / "refailed.mp4"), "moov missing"
    )
    (event / "stale.mp4").write_bytes(b"stale, re-copied and longer")
    (event / "refailed.mp4").write_bytes(b"refailed, now a good copy")
    return event


def test_entry_state_tells_current_failed_and_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = _event_of_five(tmp_path)
    _forbid_media_reads(monkeypatch)
    states = {
        name: cache_module.entry_state(event, name, cache_module.clip_signal(event / name))
        for name in ("current.mp4", "stale.mp4", "new.mp4", "failed.mp4", "refailed.mp4")
    }
    assert {name: state.kind for name, state in states.items()} == {
        "current.mp4": cache_module.EntryKind.CURRENT,
        "stale.mp4": cache_module.EntryKind.MISSING,
        "new.mp4": cache_module.EntryKind.MISSING,
        "failed.mp4": cache_module.EntryKind.FAILED,
        "refailed.mp4": cache_module.EntryKind.MISSING,
    }
    assert states["failed.mp4"].failure == "moov missing"
    assert states["current.mp4"].failure is None and states["new.mp4"].failure is None


def test_pending_clips_are_the_missing_ones_found_without_media_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = _event_of_five(tmp_path)
    before = {p: p.stat().st_mtime_ns for p in event.rglob("*")}
    _forbid_media_reads(monkeypatch)
    assert cache_module.pending_clips(event) == ["new.mp4", "refailed.mp4", "stale.mp4"]
    assert {p: p.stat().st_mtime_ns for p in event.rglob("*")} == before  # nothing written


def test_pending_clips_of_a_fully_analyzed_event_is_empty(tmp_path: Path) -> None:
    event = tmp_path / "event"
    (event / "Chapter").mkdir(parents=True)
    (event / "a.mp4").write_bytes(b"a")
    (event / "Chapter" / "b.mov").write_bytes(b"b")
    for identity in ("a.mp4", "Chapter/b.mov"):
        cache_module.write_entry(event, identity, cache_module.clip_signal(event / identity), [])
    assert cache_module.pending_clips(event) == []


def test_a_corrupt_entry_is_missing(tmp_path: Path) -> None:
    event = tmp_path / "event"
    event.mkdir()
    (event / "a.mp4").write_bytes(b"a")
    path = cache_module.write_entry(event, "a.mp4", cache_module.clip_signal(event / "a.mp4"), [])
    path.write_text("{not json", encoding="utf-8")
    assert cache_module.pending_clips(event) == ["a.mp4"]


def test_pending_clips_of_an_unlistable_event_raises(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        cache_module.pending_clips(tmp_path / "gone")
