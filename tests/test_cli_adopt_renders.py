"""Tests for the ``adopt-renders`` subcommand (task 7.1): manifest adoption, never renders."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main
from auto_reel_ng.staleness.manifest import read_manifest


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _project(tmp_path: Path, *event_names: str) -> Path:
    root = tmp_path / "proj"
    for name in event_names:
        _touch(root / "2024" / name / "00400.mp4")
    return root


def test_adopt_renders_writes_a_manifest_for_an_existing_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    event_dir = root / "2024" / "2024-06-21 - Party"
    # A pre-existing output from before change-detection: no manifest yet.
    _touch(root / "output" / "Party.mp4")

    assert main(["adopt-renders", str(root)]) == 0
    out = capsys.readouterr().out
    assert "1 adopted, 0 already fresh, 0 unrendered" in out

    manifest = read_manifest(event_dir)
    assert manifest is not None
    assert manifest.output == "Party.mp4"


def test_adopt_renders_never_writes_the_output_file(tmp_path: Path) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    output_path = root / "output" / "Party.mp4"
    _touch(output_path)
    original = output_path.read_bytes()

    assert main(["adopt-renders", str(root)]) == 0

    assert output_path.read_bytes() == original


def test_adopt_renders_skips_an_unrendered_event(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    event_dir = root / "2024" / "2024-06-21 - Party"

    assert main(["adopt-renders", str(root)]) == 0
    out = capsys.readouterr().out
    assert "0 adopted, 0 already fresh, 1 unrendered" in out
    assert read_manifest(event_dir) is None


def test_adopt_renders_is_idempotent_and_reports_already_fresh(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    _touch(root / "output" / "Party.mp4")

    assert main(["adopt-renders", str(root)]) == 0
    capsys.readouterr()
    assert main(["adopt-renders", str(root)]) == 0

    out = capsys.readouterr().out
    assert "0 adopted, 1 already fresh, 0 unrendered" in out


def test_adopted_archive_evaluates_fresh_on_subsequent_scan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    _touch(root / "output" / "Party.mp4")

    assert main(["adopt-renders", str(root)]) == 0
    capsys.readouterr()

    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert "fresh" in out
    assert "stale" not in out
