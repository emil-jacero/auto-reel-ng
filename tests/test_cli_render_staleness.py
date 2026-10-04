"""End-to-end staleness-gate tests for ``render`` (task 3.1): real ffmpeg, no mocks.

Unlike ``test_cli_render.py`` (which mocks the engine to test CLI wiring), these
exercise the actual gate: a real first render, a real no-op second run, a real
edit-triggers-re-render, and ``--force``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.staleness.manifest import read_manifest


def _project(tmp_path: Path, make_clip, *, name: str = "2024-06-21 - Party") -> tuple[Path, Path]:
    root = tmp_path / "proj"
    event_dir = root / "2024" / name
    event_dir.mkdir(parents=True)
    clip = make_clip("00400.mp4", width=320, height=240, fps=30, duration=1.0)
    clip.rename(event_dir / "00400.mp4")
    return root, event_dir


def test_unchanged_project_renders_nothing_on_second_run(
    runtime: FfmpegRuntime, make_clip, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, event_dir = _project(tmp_path, make_clip)

    assert main(["render", str(root)]) == 0
    first_out = capsys.readouterr().out
    assert "OK" in first_out
    output_path = default_output_dir(root) / "2024" / "2024-06-21 - Party.mp4"
    assert output_path.exists()  # default output dir is <root>/output
    manifest = read_manifest(event_dir)
    assert manifest is not None

    assert main(["render", str(root)]) == 0
    second_out = capsys.readouterr().out
    assert "FRESH" in second_out
    assert "OK" not in second_out


def test_editing_reel_yaml_triggers_only_that_events_re_render(
    runtime: FfmpegRuntime, make_clip, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, event_dir = _project(tmp_path, make_clip)
    assert main(["render", str(root)]) == 0
    capsys.readouterr()

    reel_path = event_dir / "reel.yaml"
    text = reel_path.read_text(encoding="utf-8")
    reel_path.write_text(text.replace("Party", "Party Renamed"), encoding="utf-8")

    assert main(["render", str(root)]) == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "FRESH" not in out


def test_force_re_renders_a_fresh_event_and_replaces_output(
    runtime: FfmpegRuntime, make_clip, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, event_dir = _project(tmp_path, make_clip)
    assert main(["render", str(root)]) == 0
    capsys.readouterr()
    manifest_before = read_manifest(event_dir)
    assert manifest_before is not None

    assert main(["render", str(root), "--force"]) == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "FRESH" not in out
    manifest_after = read_manifest(event_dir)
    assert manifest_after is not None
    # Same inputs -> same fingerprint, but the manifest was rewritten by the forced render.
    assert manifest_after.fingerprint == manifest_before.fingerprint


def _scan_line(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    """The one staleness line ``scan`` prints for a single-event project."""
    assert main(["scan", str(root)]) == 0
    lines = [line.strip() for line in capsys.readouterr().out.splitlines()]
    return next(line for line in lines if line == "fresh" or line.startswith("stale: "))


def test_retitle_scans_as_renamed_and_render_keeps_the_old_movie(
    runtime: FfmpegRuntime, make_clip, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A retitle reads ``output_renamed``; no render (failed, ok, forced) touches the old movie."""
    root, event_dir = _project(tmp_path, make_clip)
    year_dir = default_output_dir(root) / "2024"
    assert main(["render", str(root)]) == 0
    capsys.readouterr()
    old = year_dir / "2024-06-21 - Party.mp4"
    old_stat = old.stat()

    reel_path = event_dir / "reel.yaml"
    reel_path.write_text(
        reel_path.read_text(encoding="utf-8").replace("Party", "Party Renamed"), encoding="utf-8"
    )
    assert _scan_line(root, capsys) == (
        "stale: editorial, output_renamed "
        "(was '2024-06-21 - Party.mp4', now '2024-06-21 - Party Renamed.mp4')"
    )

    # A failed render (an unreadable clip) changes nothing: no new movie, same manifest.
    clip = event_dir / "00400.mp4"
    clip_bytes = clip.read_bytes()
    manifest_before = read_manifest(event_dir)
    clip.write_bytes(b"")
    assert main(["render", str(root)]) == 1
    capsys.readouterr()
    assert read_manifest(event_dir) == manifest_before
    new = year_dir / "2024-06-21 - Party Renamed.mp4"
    assert not new.exists()
    assert (old.stat().st_size, old.stat().st_mtime_ns) == (old_stat.st_size, old_stat.st_mtime_ns)
    assert _scan_line(root, capsys) == (
        "stale: editorial, clip_set, output_renamed "
        "(was '2024-06-21 - Party.mp4', now '2024-06-21 - Party Renamed.mp4')"
    )

    # A successful render writes the new name beside the old movie and records it.
    clip.write_bytes(clip_bytes)
    assert main(["render", str(root)]) == 0
    capsys.readouterr()
    assert new.exists()
    assert (old.stat().st_size, old.stat().st_mtime_ns) == (old_stat.st_size, old_stat.st_mtime_ns)
    manifest = read_manifest(event_dir)
    assert manifest is not None
    assert manifest.output == "2024-06-21 - Party Renamed.mp4"
    assert _scan_line(root, capsys) == "fresh"

    # A forced render after another rename keeps both earlier movies, its own previous
    # movie (the one its manifest records) included.
    new_stat = new.stat()
    reel_path.write_text(
        reel_path.read_text(encoding="utf-8").replace("Party Renamed", "Fest"), encoding="utf-8"
    )
    assert main(["render", str(root), "--force"]) == 0
    capsys.readouterr()
    assert sorted(path.name for path in year_dir.iterdir()) == [
        "2024-06-21 - Fest-poster.jpg",
        "2024-06-21 - Fest.mp4",
        "2024-06-21 - Party Renamed-poster.jpg",
        "2024-06-21 - Party Renamed.mp4",
        "2024-06-21 - Party-poster.jpg",
        "2024-06-21 - Party.mp4",
    ]
    assert (new.stat().st_size, new.stat().st_mtime_ns) == (new_stat.st_size, new_stat.st_mtime_ns)
    assert (old.stat().st_size, old.stat().st_mtime_ns) == (old_stat.st_size, old_stat.st_mtime_ns)


def test_removed_overwrite_flag_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["render", str(tmp_path), "--overwrite"])
    assert exc.value.code != 0
