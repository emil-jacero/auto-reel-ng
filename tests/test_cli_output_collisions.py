"""Batch commands refuse colliding output paths (headless-cli spec, output-path-year-folder).

``render`` runs with the heavy engine seams patched (as in ``test_cli_render.py``)
so the tests cover the CLI's collision handling, not ffmpeg.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Iterator, List
from unittest.mock import Mock

import pytest

from auto_reel_ng.accel.profiles.cpu import CPUProfile
from auto_reel_ng.cli import build as build_module
from auto_reel_ng.cli import commands
from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.persistence.job_store import Submission
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


# --------------------------------------------------------------------------- #
# an event the process cannot read is that event's error, in every batch command
# --------------------------------------------------------------------------- #

REEL = "version: 0\nmetadata:\n  title: Real\n  date: 2024-09-09\n"
LOCKED = "2024-09-09 - Locked"


class _Store:
    """A job store that accepts every submission, for ``enqueue`` without Postgres."""

    def __init__(self) -> None:
        self.submitted: List[str] = []

    def submit(self, project_root: str, event_dir: str, **kwargs: Any) -> Submission:
        self.submitted.append(event_dir)
        return Submission(job_id=uuid.uuid4(), created=True)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch, rendered: List[RenderJob]) -> _Store:
    fake = _Store()
    monkeypatch.setattr(commands, "_job_store", lambda project_root: fake)
    return fake


@pytest.fixture
def locked(root: Path) -> Iterator[Path]:
    """Hand back a factory-less event folder; every mode is restored afterwards."""
    event_dir = _add_event(root, "2024", LOCKED)
    yield event_dir
    event_dir.chmod(0o755)


def _lock(event_dir: Path, mode: str) -> None:
    if mode == "000":  # cannot be listed, and holds no reel.yaml to say what it is
        event_dir.chmod(0o000)
    elif mode == "600":  # can be listed, nothing in it can be looked up
        (event_dir / "reel.yaml").write_text(REEL, encoding="utf-8")
        event_dir.chmod(0o600)
    else:  # "300": can be searched, cannot be listed
        (event_dir / "reel.yaml").write_text(REEL, encoding="utf-8")
        event_dir.chmod(0o300)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
@pytest.mark.parametrize("mode", ["000", "600", "300"])
@pytest.mark.parametrize(
    "argv",
    [
        ["scan"],
        ["render", "--dry-run"],
        ["enqueue"],
        ["adopt-renders", "--dry-run"],
    ],
    ids=lambda argv: argv[0],
)
def test_an_unreadable_sibling_is_its_own_error_and_the_rest_are_handled(
    root: Path,
    rendered: List[RenderJob],
    store: _Store,
    locked: Path,
    capsys: pytest.CaptureFixture[str],
    argv: List[str],
    mode: str,
) -> None:
    _add_event(root, "2024", "2024-08-01 - Kalas")
    _add_event(root, "2024", "2024-08-02 - Krabbor")
    _lock(locked, mode)

    code = main([argv[0], str(root), *argv[1:]])

    out = capsys.readouterr().out
    assert code == 1
    assert out.count("ERROR") == 1
    assert f"ERROR  {LOCKED}:" in out
    assert "Kalas" in out and "Krabbor" in out
    assert "Real" not in out  # a 0600 event is not listed under any title
    if argv[0] == "enqueue":
        assert sorted(store.submitted) == ["2024/2024-08-01 - Kalas", "2024/2024-08-02 - Krabbor"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unsearchable_event_is_not_listed_under_its_folder_name(
    root: Path, rendered: List[RenderJob], locked: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _lock(locked, "600")

    assert main(["scan", str(root)]) == 1

    out = capsys.readouterr().out
    assert "Locked  [" not in out  # the folder-name title it would be seeded with
    assert "(no clips)" not in out


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_colliding_pair_is_still_refused_beside_an_unreadable_sibling(
    root: Path,
    rendered: List[RenderJob],
    locked: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _add_event(root, "2024", "2024-06-21 - Midsommar")
    _add_event(root, "2024", "2024-06-21 - midsommar")
    _lock(locked, "000")

    assert main(["render", str(root), "--dry-run"]) == 1

    out = capsys.readouterr().out
    assert "ERROR  2024-06-21 - Midsommar: output path" in out
    assert "ERROR  2024-06-21 - midsommar: output path" in out
    assert f"ERROR  {LOCKED}:" in out
    assert out.count("ERROR") == 3
