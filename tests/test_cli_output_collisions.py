"""Batch commands refuse colliding output paths (headless-cli spec, output-path-year-folder).

``render`` runs with the heavy engine seams patched (as in ``test_cli_render.py``)
so the tests cover the CLI's collision handling, not ffmpeg.
"""

from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import Mock

import pytest

from auto_reel_ng.accel.profiles.cpu import CPUProfile
from auto_reel_ng.cli import build as build_module
from auto_reel_ng.cli import commands
from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.render import BatchOutcome, RenderJob, RenderResult
from auto_reel_ng.staleness.manifest import read_manifest


def _touch(path: Path, content: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _add_event(root: Path, year: str, name: str) -> Path:
    event_dir = root / year / name
    _touch(event_dir / "00400.mp4")
    return event_dir


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "proj"


@pytest.fixture
def rendered(monkeypatch: pytest.MonkeyPatch) -> List[RenderJob]:
    """Patch the engine seams; collect every job that reaches ``render_batch``."""
    monkeypatch.setattr(
        commands, "FfmpegRuntime", lambda *a, **k: Mock(name="runtime", version=(7, 1))
    )
    monkeypatch.setattr(commands, "detect_capabilities", lambda *a, **k: Mock(name="inventory"))
    monkeypatch.setattr(commands, "select_profile", lambda *a, **k: CPUProfile())
    monkeypatch.setattr(build_module, "probe_media", lambda *a, **k: Mock(name="clip_meta"))
    seen: List[RenderJob] = []

    def fake_batch(jobs: List[RenderJob]) -> List[BatchOutcome]:
        seen.extend(jobs)
        return [
            BatchOutcome(job=job, result=RenderResult(output_path=job.options.output_dir / "m.mp4"))
            for job in jobs
        ]

    monkeypatch.setattr(commands, "render_batch", fake_batch)
    return seen


def test_same_year_pair_is_refused_and_the_rest_renders(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    _add_event(root, "2024", "2024-06-21 - Midsommar")
    _add_event(root, "2024", "2024-06-21 - midsommar")
    kalas = _add_event(root, "2024", "2024-08-01 - Kalas")

    assert main(["render", str(root)]) == 1

    out = capsys.readouterr().out
    shared = "output path 2024/2024-06-21 - Midsommar.mp4"
    assert f"ERROR  2024-06-21 - Midsommar: {shared}" in out
    assert "also claimed by 2024-06-21 - midsommar" in out
    assert f"ERROR  2024-06-21 - midsommar: {shared}" in out
    assert [job.options.event_dir for job in rendered] == [kalas]


def test_fresh_owner_is_protected_from_a_new_sibling(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    owner = _add_event(root, "2024", "2024-06-21 - Midsommar")
    output = default_output_dir(root) / "2024" / "2024-06-21 - Midsommar.mp4"
    _touch(output, b"the 2024-06-21 movie")
    assert main(["adopt-renders", str(root)]) == 0  # owner is now fresh
    owner_manifest = read_manifest(owner)
    assert owner_manifest is not None

    sibling = _add_event(root, "2024", "2024-06-21 - midsommar")
    assert main(["render", str(root)]) == 1

    assert output.read_bytes() == b"the 2024-06-21 movie"
    assert rendered == []
    assert read_manifest(sibling) is None
    assert read_manifest(owner) == owner_manifest
    assert capsys.readouterr().out.count("ERROR") == 2


@pytest.mark.parametrize("flag", ["--force", "--dry-run"])
def test_force_and_dry_run_still_refuse(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str], flag: str
) -> None:
    _add_event(root, "2024", "2024-06-21 - Midsommar")
    _add_event(root, "2024", "2024-06-21 - midsommar")

    assert main(["render", str(root), flag]) == 1

    assert rendered == []
    assert capsys.readouterr().out.count("ERROR") == 2


def test_letter_case_only_difference_collides(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    _add_event(root, "2024", "2024-06-21 - Midsommar")
    other = _add_event(root, "2024", "2024-06-21 - Midsommarfest")
    (other / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: midsommar\n  date: 2024-06-21\n", encoding="utf-8"
    )

    assert main(["render", str(root)]) == 1
    assert rendered == []


def test_same_title_in_different_years_does_not_collide(
    root: Path, rendered: List[RenderJob]
) -> None:
    _add_event(root, "2023", "2023-06-23 - Midsommar")
    _add_event(root, "2024", "2024-06-21 - Midsommar")

    assert main(["render", str(root)]) == 0
    assert len(rendered) == 2


def test_same_title_on_different_dates_does_not_collide(
    root: Path, rendered: List[RenderJob]
) -> None:
    _add_event(root, "2024", "2024-06-21 - Midsommar")
    _add_event(root, "2024", "2024-06-22 - Midsommar")

    assert main(["render", str(root)]) == 0
    assert len(rendered) == 2


def test_two_reel_yaml_events_with_same_date_and_title_collide(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("a", "b"):
        event_dir = _add_event(root, "2024", name)
        (event_dir / "reel.yaml").write_text(
            "version: 0\nmetadata:\n  title: Blandat\n  date: 2024-11-02\n", encoding="utf-8"
        )

    assert main(["render", str(root)]) == 1

    out = capsys.readouterr().out
    assert "ERROR  a: output path 2024/2024-11-02 - Blandat.mp4" in out
    assert "ERROR  b: output path 2024/2024-11-02 - Blandat.mp4" in out
    assert rendered == []


def test_adopt_renders_refuses_a_shared_output(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _add_event(root, "2024", "2024-06-21 - Midsommar")
    second = _add_event(root, "2024", "2024-06-21 - midsommar")
    _touch(default_output_dir(root) / "2024" / "2024-06-21 - Midsommar.mp4")

    assert main(["adopt-renders", str(root)]) == 1

    assert read_manifest(first) is None
    assert read_manifest(second) is None
    assert capsys.readouterr().out.count("ERROR") == 2
