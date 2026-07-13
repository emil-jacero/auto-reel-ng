"""End-to-end staleness-gate tests for ``render`` (task 3.1): real ffmpeg, no mocks.

Unlike ``test_cli_render.py`` (which mocks the engine to test CLI wiring), these
exercise the actual gate: a real first render, a real no-op second run, a real
edit-triggers-re-render, and ``--force``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main
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
    output_path = root / "output" / "Party.mp4"
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


def test_removed_overwrite_flag_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["render", str(tmp_path), "--overwrite"])
    assert exc.value.code != 0
