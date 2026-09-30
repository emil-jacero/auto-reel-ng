"""Tests for ``auto-reel thumbs``: what it walks, what it prints, and that it never
writes into the library (D-11, headless-cli).

The unit tests replace ``FfmpegRuntime`` with a ``Mock`` and ``thumbnail_for`` with a
fake that writes bytes at the real cache path (or raises ``ThumbnailError`` for a
zero-byte clip). The last test runs the real extraction over a read-only library.
"""

from __future__ import annotations

import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from unittest.mock import Mock

import pytest

from auto_reel_ng.cli import thumbnails as thumbs_cli
from auto_reel_ng.cli.main import main
from auto_reel_ng.errors import ThumbnailCacheError, ThumbnailError
from auto_reel_ng.thumbs import thumbnail_path

GRILLNING = "2024/2024-06-27 - Grillning med grannar"
TRASIG = "2024/2024-10-05 - Trasig"
SOMMARLOV = "2024/2024-09-01 - Sommarlov"
TJORN = "2024/2024-08-20 - Två kapitel - Tjörn"
MIDSOMMAR = "2023/2023-06-23 - Midsommar - Dalarna"
VERONA = "2017/2017-07-07 - Verona"
OMOJLIGT = "2024/2024-02-30 - Omöjligt datum"

#: The Sommarlov document from ``tests/test_event_editorial.py``: one MISSING clip.
SOMMARLOV_REEL = """\
version: 0
metadata:
  title: Sommarlov
  date: 2024-09-01
chapters:
  - name: ''
    clips:
      - s1710002.mp4
      - s1710004.mp4
      - borttagen.mp4  # MISSING
"""

#: Tjörn: a root chapter and ``Kvällen/``, with the root ``s1710004.mp4`` IGNORED.
TJORN_REEL = """\
version: 0
metadata:
  title: Två kapitel
  date: 2024-08-20
  location: Tjörn
chapters:
  - name: ''
    clips:
      - s1710001.mp4
  - name: Kvällen
    clips:
      - Kvällen/s1710002.mp4
      - Kvällen/s1710003.mp4
      - Kvällen/s1710004.mp4
ignore:
  - s1710004.mp4
"""

Snapshot = Dict[str, Tuple[int, int, Optional[bytes]]]


def _write(path: Path, data: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _build_library(root: Path) -> None:
    """A year-event library shaped like the dev library (``make_dev_library.py``)."""
    for name in ("s1710001.mp4", "s1710002.mp4", "s1710003.mp4", "s1710004.mp4"):
        _write(root / GRILLNING / name, f"grill {name}".encode())
    _write(root / TRASIG / "trasig.mp4")  # zero bytes
    _write(root / SOMMARLOV / "reel.yaml", SOMMARLOV_REEL.encode())
    for name in ("s1710002.mp4", "s1710004.mp4"):
        _write(root / SOMMARLOV / name, f"sommar {name}".encode())
    _write(root / TJORN / "reel.yaml", TJORN_REEL.encode())
    for name in ("s1710001.mp4", "s1710004.mp4"):
        _write(root / TJORN / name, f"tjorn {name}".encode())
    for name in ("s1710002.mp4", "s1710003.mp4", "s1710004.mp4"):
        _write(root / TJORN / "Kvällen" / name, f"kvall {name}".encode())
    _write(root / MIDSOMMAR / "s1710001.mp4", b"midsommar")
    _write(root / MIDSOMMAR / "original" / "C0001.MTS", b"camera original")
    _write(root / VERONA / "00100.mp4", b"verona")
    _write(root / VERONA / ".reelignore")
    _write(root / OMOJLIGT / "s1710001.mp4", b"omojligt")


def _snapshot(root: Path) -> Snapshot:
    """Every path under ``root`` (dirs included) with size, mtime_ns and reel.yaml bytes."""
    snapshot: Snapshot = {}
    for directory, dirnames, filenames in os.walk(root):
        for name in [*dirnames, *filenames]:
            path = Path(directory) / name
            info = path.lstat()
            data = path.read_bytes() if name == "reel.yaml" else None
            snapshot[str(path.relative_to(root))] = (info.st_size, info.st_mtime_ns, data)
    return snapshot


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The library at ``tmp_path/library``; the cache defaults to its sibling ``xdg``."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    root = tmp_path / "library"
    _build_library(root)
    return root


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "xdg" / "auto-reel" / "thumbnails"


FakeCalls = List[Path]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Callable[..., FakeCalls]:
    """Install a Mock runtime and a fake ``thumbnail_for``; returns its recorded clips."""

    def install(error: Optional[BaseException] = None) -> FakeCalls:
        calls: FakeCalls = []

        def fake_thumbnail_for(
            clip: Path, *, position: float, cache_dir: Path, runtime: object = None
        ) -> Path:
            calls.append(clip)
            if error is not None:
                raise error
            if clip.stat().st_size == 0:
                raise ThumbnailError(str(clip), "File is empty (zero bytes)")
            target = thumbnail_path(clip, position=position, cache_dir=cache_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"\xff\xd8fake\xff\xd9")
            return target

        monkeypatch.setattr(thumbs_cli, "FfmpegRuntime", lambda *a, **k: Mock())
        monkeypatch.setattr(thumbs_cli, "thumbnail_for", fake_thumbnail_for)
        return calls

    return install


def _identities(calls: FakeCalls, root: Path) -> set[str]:
    return {str(clip.relative_to(root)) for clip in calls}


def _error_lines(out: str) -> List[str]:
    return [line for line in out.splitlines() if line.startswith("ERROR  ")]


# --------------------------------------------------------------------------- #
# the walk, the output, the exit code
# --------------------------------------------------------------------------- #


def test_thumbs_fills_the_cache_and_reports_the_broken_clip(
    library: Path,
    cache_dir: Path,
    fake: Callable[..., FakeCalls],
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake()

    assert main(["thumbs", str(library)]) == 1

    out = capsys.readouterr().out
    assert _error_lines(out) == [
        "ERROR  2024-10-05 - Trasig/trasig.mp4: File is empty (zero bytes)"
    ]
    lines = out.splitlines()
    for event_line in (
        "2023-06-23 - Midsommar - Dalarna: 1 clip, 1 generated",
        "2024-02-30 - Omöjligt datum: 1 clip, 1 generated",
        "2024-06-27 - Grillning med grannar: 4 clips, 4 generated",
        "2024-08-20 - Två kapitel - Tjörn: 5 clips, 5 generated",
        "2024-09-01 - Sommarlov: 2 clips, 2 generated",
        "2024-10-05 - Trasig: 1 clip, 1 failed",
    ):
        assert event_line in lines
    # The ERROR line comes before its event's line, and the summary comes last.
    assert lines.index(_error_lines(out)[0]) < lines.index("2024-10-05 - Trasig: 1 clip, 1 failed")
    assert lines[-1] == (
        f"thumbnails: 14 clips in 6 events: 13 generated, 0 cached, 1 failed (cache: {cache_dir})"
    )
    assert len(list(cache_dir.glob("*.jpg"))) == 13


def test_thumbs_requests_every_clip_on_disk_and_nothing_else(
    library: Path, fake: Callable[..., FakeCalls]
) -> None:
    calls = fake()
    main(["thumbs", str(library)])

    identities = _identities(calls, library)
    assert identities == {
        f"{MIDSOMMAR}/s1710001.mp4",
        f"{OMOJLIGT}/s1710001.mp4",
        *(f"{GRILLNING}/s171000{n}.mp4" for n in range(1, 5)),
        f"{TJORN}/s1710001.mp4",
        f"{TJORN}/s1710004.mp4",  # IGNORED in reel.yaml, still on disk
        f"{TJORN}/Kvällen/s1710002.mp4",
        f"{TJORN}/Kvällen/s1710003.mp4",
        f"{TJORN}/Kvällen/s1710004.mp4",
        f"{SOMMARLOV}/s1710002.mp4",
        f"{SOMMARLOV}/s1710004.mp4",
        f"{TRASIG}/trasig.mp4",
    }
    assert not any("borttagen" in i or "original" in i or "Verona" in i for i in identities)


def test_a_second_run_counts_every_success_as_cached(
    library: Path,
    cache_dir: Path,
    fake: Callable[..., FakeCalls],
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake()
    main(["thumbs", str(library)])
    capsys.readouterr()

    calls = fake()
    assert main(["thumbs", str(library)]) == 1

    out = capsys.readouterr().out
    assert _identities(calls, library) == {f"{TRASIG}/trasig.mp4"}
    assert "2024-06-27 - Grillning med grannar: 4 clips, 4 cached" in out.splitlines()
    assert out.splitlines()[-1] == (
        f"thumbnails: 14 clips in 6 events: 0 generated, 13 cached, 1 failed (cache: {cache_dir})"
    )
    assert len(_error_lines(out)) == 1


def test_the_library_is_left_untouched(library: Path, fake: Callable[..., FakeCalls]) -> None:
    fake()
    before = _snapshot(library)
    main(["thumbs", str(library)])
    assert _snapshot(library) == before


def test_a_clip_that_vanishes_before_its_stat_is_one_failure(
    library: Path,
    fake: Callable[..., FakeCalls],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = fake()
    vanished = library / GRILLNING / "s1710003.mp4"

    def flaky_thumbnail_path(clip: Path, *, position: float, cache_dir: Path) -> Path:
        if clip == vanished:
            raise FileNotFoundError(2, "No such file or directory", str(clip))
        return thumbnail_path(clip, position=position, cache_dir=cache_dir)

    monkeypatch.setattr(thumbs_cli, "thumbnail_path", flaky_thumbnail_path)

    assert main(["thumbs", str(library)]) == 1

    out = capsys.readouterr().out
    assert (
        "ERROR  2024-06-27 - Grillning med grannar/s1710003.mp4: cannot stat the clip: "
        "No such file or directory"
    ) in _error_lines(out)
    assert "2024-06-27 - Grillning med grannar: 4 clips, 3 generated, 1 failed" in out
    assert f"{SOMMARLOV}/s1710002.mp4" in _identities(calls, library)  # the run continued
    assert out.splitlines()[-1].startswith("thumbnails: 14 clips in 6 events: 12 generated")


def test_an_unreadable_event_folder_is_reported_and_the_run_continues(
    library: Path,
    fake: Callable[..., FakeCalls],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = fake()
    unreadable = library / GRILLNING
    real_scan_event = thumbs_cli.scan_event

    def flaky_scan_event(event_dir: Path):  # type: ignore[no-untyped-def]
        if event_dir == unreadable:
            raise PermissionError(13, "Permission denied", str(event_dir))
        return real_scan_event(event_dir)

    monkeypatch.setattr(thumbs_cli, "scan_event", flaky_scan_event)

    assert main(["thumbs", str(library)]) == 1

    out = capsys.readouterr().out
    assert (
        "ERROR  2024-06-27 - Grillning med grannar: cannot list event folder: Permission denied"
    ) in out.splitlines()
    assert f"{SOMMARLOV}/s1710002.mp4" in _identities(calls, library)  # the run continued
    assert out.splitlines()[-1].startswith(
        "thumbnails: 10 clips in 6 events: 9 generated, 0 cached, 1 failed, 1 event unreadable"
    )


def test_no_events_is_not_an_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake: Callable[..., FakeCalls],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    empty = tmp_path / "empty"
    empty.mkdir()
    calls = fake()

    assert main(["thumbs", str(empty)]) == 0

    assert "No events found under" in capsys.readouterr().out
    assert calls == []


# --------------------------------------------------------------------------- #
# arguments, settings, and errors that stop the run
# --------------------------------------------------------------------------- #


def test_a_non_positive_job_count_is_a_usage_error(
    library: Path, fake: Callable[..., FakeCalls]
) -> None:
    calls = fake()
    with pytest.raises(SystemExit) as exc:
        main(["thumbs", str(library), "--jobs", "0"])
    assert exc.value.code == 2
    assert calls == []


def test_an_invalid_position_stops_before_any_extraction(
    library: Path, fake: Callable[..., FakeCalls], capsys: pytest.CaptureFixture[str]
) -> None:
    (library / "config.yaml").write_text("thumbnails:\n  position: 1.5\n", encoding="utf-8")
    calls = fake()

    assert main(["thumbs", str(library)]) == 1

    captured = capsys.readouterr()
    assert "error: thumbnails.position" in captured.err
    assert calls == []


def test_an_unwritable_cache_stops_the_run_with_one_error(
    library: Path,
    tmp_path: Path,
    fake: Callable[..., FakeCalls],
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = tmp_path / "read-only" / "thumbs"
    fake(error=ThumbnailCacheError(f"{cache}: cannot write thumbnails: [Errno 30] Read-only"))

    assert main(["thumbs", str(library)]) == 1

    captured = capsys.readouterr()
    errors = [line for line in captured.err.splitlines() if line.startswith("error:")]
    assert errors == [f"error: {cache}: cannot write thumbnails: [Errno 30] Read-only"]
    assert _error_lines(captured.out) == []


def test_an_unreadable_cache_stops_the_run_with_one_error(
    library: Path,
    cache_dir: Path,
    fake: Callable[..., FakeCalls],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = fake()
    real_is_file = Path.is_file

    def is_file(self: Path) -> bool:  # Python 3.13 raises on an unsearchable directory
        if self.parent == cache_dir:
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", is_file)

    assert main(["thumbs", str(library)]) == 1

    captured = capsys.readouterr()
    errors = [line for line in captured.err.splitlines() if line.startswith("error:")]
    assert len(errors) == 1
    assert errors[0].startswith(f"error: {cache_dir}: cannot read thumbnails")
    assert _error_lines(captured.out) == []
    assert calls == []


class _RecordingExecutor(ThreadPoolExecutor):
    """A real pool that records the arguments of every ``shutdown`` call."""

    shutdowns: List[Dict[str, bool]] = []

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        type(self).shutdowns.append({"wait": wait, "cancel_futures": cancel_futures})
        super().shutdown(wait=wait, cancel_futures=cancel_futures)


def test_an_interrupt_cancels_the_queued_clips_and_propagates(
    library: Path, fake: Callable[..., FakeCalls], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake(error=KeyboardInterrupt())
    monkeypatch.setattr(_RecordingExecutor, "shutdowns", [])
    monkeypatch.setattr(thumbs_cli, "ThreadPoolExecutor", _RecordingExecutor)

    with pytest.raises(KeyboardInterrupt):
        main(["thumbs", str(library)])

    assert _RecordingExecutor.shutdowns
    assert _RecordingExecutor.shutdowns[0]["cancel_futures"] is True


# --------------------------------------------------------------------------- #
# end to end: the real extraction over a read-only library (4.2)
# --------------------------------------------------------------------------- #


@pytest.mark.has_ffmpeg
def test_thumbs_end_to_end_over_a_read_only_library(
    tmp_path: Path,
    make_clip,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    cache_dir = tmp_path / "xdg" / "auto-reel" / "thumbnails"
    (tmp_path / "clips").mkdir()
    first = make_clip("clips/s1710001.mp4", width=1920, height=1080, duration=1.5)
    second = make_clip("clips/s1710002.mp4", width=1920, height=1080, duration=1.5)
    broken = tmp_path / "clips" / "trasig.mp4"
    broken.write_bytes(b"")

    root = tmp_path / "library"
    links = {
        root / GRILLNING / "s1710001.mp4": first,
        root / GRILLNING / "s1710002.mp4": second,
        root / TJORN / "Kvällen" / "grillen, del 1.mp4": first,  # the same clip, second event
        root / TRASIG / "trasig.mp4": broken,
    }
    for link, target in links.items():
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)

    directories = [Path(d) for d, _dirs, _files in os.walk(root)]
    modes = {d: d.stat().st_mode for d in directories}
    for directory in directories:  # like the MOL drive mounted read-only
        directory.chmod(modes[directory] & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        before = _snapshot(root)

        assert main(["thumbs", str(root), "--jobs", "2"]) == 1
        out = capsys.readouterr().out
        assert len(_error_lines(out)) == 1
        assert _error_lines(out) == [
            "ERROR  2024-10-05 - Trasig/trasig.mp4: File is empty (zero bytes)"
        ]
        assert "2024-08-20 - Två kapitel - Tjörn: 1 clip, 1 cached" in out.splitlines()
        assert len(list(cache_dir.glob("*.jpg"))) == 2  # one per distinct target
        assert list(cache_dir.glob(".*.tmp")) == []

        assert main(["thumbs", str(root), "--jobs", "2"]) == 1
        out = capsys.readouterr().out
        assert out.splitlines()[-1] == (
            f"thumbnails: 4 clips in 3 events: 0 generated, 3 cached, 1 failed (cache: {cache_dir})"
        )
        assert _snapshot(root) == before
    finally:
        for directory in reversed(directories):
            directory.chmod(modes[directory])
