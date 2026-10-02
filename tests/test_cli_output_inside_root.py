"""An output directory inside the walked root is refused before anything runs.

(``project-config`` "The output directory never lies inside the walked root";
``headless-cli`` "Default output directory sits outside the project root".)
The engine seams are patched as in ``test_cli_output_collisions.py``, so these cover
the CLI's refusal, not ffmpeg.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock

import pytest

from auto_reel_ng.accel.profiles.cpu import CPUProfile
from auto_reel_ng.cli import build as build_module
from auto_reel_ng.cli import commands
from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.render import BatchOutcome, RenderJob, RenderResult

REFUSAL = "inside the walked root"
BOGUS_EVENT = "ERROR  2024: no date"


def _touch(path: Path, content: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _snapshot(root: Path) -> Dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A year-event library whose earlier movie already sits in ``<root>/out``."""
    project = tmp_path / "proj"
    _touch(project / "2024" / "2024-07-20 - A" / "a.mp4")
    _touch(project / "out" / "2024" / "2024-07-20 - A.mp4", b"movie")
    return project


@pytest.fixture
def rendered(monkeypatch: pytest.MonkeyPatch) -> List[RenderJob]:
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


def test_scan_refuses_an_output_inside_the_root_and_walks_nothing(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _snapshot(root)

    assert main(["scan", str(root), "-o", str(root / "out")]) == 1

    captured = capsys.readouterr()
    assert REFUSAL in captured.err
    assert str(root / "out") in captured.err
    assert BOGUS_EVENT not in captured.out
    assert captured.out == ""
    assert _snapshot(root) == before


def test_flat_layout_never_lists_the_output_as_an_event(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["scan", str(root), "--layout", "flat", "-o", str(root / "out")]) == 1

    captured = capsys.readouterr()
    assert REFUSAL in captured.err
    assert "out" not in captured.out


def test_render_into_the_root_itself_renders_nothing(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    before = _snapshot(root)

    assert main(["render", str(root), "-o", str(root)]) == 1

    assert REFUSAL in capsys.readouterr().err
    assert rendered == []
    assert _snapshot(root) == before


def test_a_nested_relative_output_is_refused(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(root)  # a relative -o is relative to the cwd
    assert main(["scan", str(root), "-o", "out/renders"]) == 1
    assert REFUSAL in capsys.readouterr().err


def test_config_output_inside_the_root_is_refused_by_every_walking_command(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (root / "config.yaml").write_text("output: out\n", encoding="utf-8")

    def no_store(*_a: object, **_k: object) -> None:
        raise AssertionError("the job store must not be reached")

    monkeypatch.setattr(commands, "_job_store", no_store)
    for command in ("scan", "enqueue", "thumbs", "render", "analyze", "adopt-renders"):
        assert main([command, str(root)]) == 1, command
        assert REFUSAL in capsys.readouterr().err, command


def test_serve_fails_at_startup_without_building_the_app(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (root / "config.yaml").write_text("output: out\n", encoding="utf-8")

    def reached(*_a: object, **_k: object) -> None:
        raise AssertionError("serve must fail before creating the app or binding a port")

    monkeypatch.setattr(commands, "create_app", reached)
    monkeypatch.setattr(commands, "ServiceServer", reached)

    assert main(["serve", str(root)]) == 1
    assert REFUSAL in capsys.readouterr().err


def test_input_dir_keeps_an_output_beside_it_valid(
    rendered: List[RenderJob], tmp_path: Path
) -> None:
    library = tmp_path / "library"
    _touch(library / "media" / "2024" / "2024-07-20 - A" / "a.mp4")
    (library / "config.yaml").write_text("input: media\noutput: out\n", encoding="utf-8")

    assert main(["render", str(library)]) == 0
    assert {job.options.output_dir for job in rendered} == {library / "out"}


def test_sibling_default_and_explicit_sibling_output_are_unchanged(
    rendered: List[RenderJob], tmp_path: Path
) -> None:
    library = tmp_path / "library"
    _touch(library / "2024" / "2024-07-20 - A" / "a.mp4")

    assert main(["render", str(library)]) == 0
    assert {job.options.output_dir for job in rendered} == {default_output_dir(library)}

    rendered.clear()
    assert main(["render", str(library), "--force", "-o", str(tmp_path / "movies")]) == 0
    assert {job.options.output_dir for job in rendered} == {tmp_path / "movies"}
