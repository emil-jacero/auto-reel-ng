"""Tests for the ``adopt-renders`` subcommand (task 7.1): manifest adoption, never renders."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
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
    _touch(default_output_dir(root) / "2024" / "2024-06-21 - Party.mp4")

    assert main(["adopt-renders", str(root)]) == 0
    out = capsys.readouterr().out
    assert "1 adopted, 0 already fresh, 0 unrendered" in out

    manifest = read_manifest(event_dir)
    assert manifest is not None
    assert manifest.output == "2024-06-21 - Party.mp4"


def test_adopt_renders_never_writes_the_output_file(tmp_path: Path) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    output_path = default_output_dir(root) / "2024" / "2024-06-21 - Party.mp4"
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


@pytest.mark.parametrize("dry_run", [False, True])
def test_adopt_renders_does_not_adopt_a_folder_at_the_output_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], dry_run: bool
) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    event_dir = root / "2024" / "2024-06-21 - Party"
    folder = default_output_dir(root) / "2024" / "2024-06-21 - Party.mp4"
    _touch(folder / "inside.txt")

    assert main(["adopt-renders", str(root), *(["--dry-run"] if dry_run else [])]) == 0

    out = capsys.readouterr().out
    verb = "would adopt" if dry_run else "adopted"
    assert f"0 {verb}, 0 already fresh, 1 unrendered" in out
    assert "unrendered, nothing to adopt" in out
    assert read_manifest(event_dir) is None
    assert (folder / "inside.txt").is_file()


def test_adopt_renders_is_idempotent_and_reports_already_fresh(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    _touch(default_output_dir(root) / "2024" / "2024-06-21 - Party.mp4")

    assert main(["adopt-renders", str(root)]) == 0
    capsys.readouterr()
    assert main(["adopt-renders", str(root)]) == 0

    out = capsys.readouterr().out
    assert "0 adopted, 1 already fresh, 0 unrendered" in out


def test_adopted_archive_evaluates_fresh_on_subsequent_scan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - Party")
    _touch(default_output_dir(root) / "2024" / "2024-06-21 - Party.mp4")

    assert main(["adopt-renders", str(root)]) == 0
    capsys.readouterr()

    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert "fresh" in out
    assert "stale" not in out


# --------------------------------------------------------------------------- #
# --dry-run: the same evaluation, no writes                                   #
# --------------------------------------------------------------------------- #

_RENDERED = ("2024-06-21 - Party", "2024-07-14 - Kalas", "2024-08-01 - Resa")


def _archive(tmp_path: Path) -> Path:
    """Three events with an output at their derived path, one without."""
    root = _project(tmp_path, *_RENDERED, "2024-09-01 - Unrendered")
    for name in _RENDERED:
        _touch(default_output_dir(root) / "2024" / f"{name}.mp4")
    return root


def test_adopt_renders_dry_run_reports_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _archive(tmp_path)

    assert main(["adopt-renders", str(root), "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "3 would adopt, 0 already fresh, 1 unrendered (dry run: nothing written)" in out
    assert out.count("would adopt at current fingerprint") == 3
    for event_dir in (root / "2024").iterdir():
        assert not (event_dir / ".auto-reel").exists()
        assert not (event_dir / "reel.yaml").exists()


def test_adopt_renders_after_a_dry_run_adopts_exactly_those_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _archive(tmp_path)
    assert main(["adopt-renders", str(root), "--dry-run"]) == 0
    capsys.readouterr()

    assert main(["adopt-renders", str(root)]) == 0

    assert "3 adopted, 0 already fresh, 1 unrendered" in capsys.readouterr().out
    adopted = {d.name for d in (root / "2024").iterdir() if read_manifest(d) is not None}
    assert adopted == set(_RENDERED)


def test_adopt_renders_dry_run_still_refuses_a_collision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - Party", "2024-06-21 - party")
    _touch(default_output_dir(root) / "2024" / "2024-06-21 - Party.mp4")

    assert main(["adopt-renders", str(root), "--dry-run"]) == 1

    out = capsys.readouterr().out
    assert out.count("ERROR") == 2
    assert "(dry run: nothing written)" in out


def test_adopt_renders_dry_run_completes_on_a_read_only_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _archive(tmp_path)
    tree = [p for p in tmp_path.rglob("*")]
    for path in tree:
        path.chmod(path.stat().st_mode & ~0o222)
    try:
        assert main(["adopt-renders", str(root), "--dry-run"]) == 0
    finally:
        for path in tree:
            path.chmod(path.stat().st_mode | 0o200)

    assert "3 would adopt" in capsys.readouterr().out
