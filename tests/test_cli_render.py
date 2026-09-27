"""Tests for the ``render`` command, mocking the engine at the render_batch boundary.

The pre-render engine seams (runtime construction, capability detection, profile
selection, probing) and ``render_batch`` itself are patched, so these run without
ffmpeg and exercise the CLI wiring: job building, dry-run, per-event isolation, and
the exit code (D-CLI5).
"""

from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import Mock

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.cli import build as build_module
from auto_reel_ng.cli import commands
from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.errors import ProbeError
from auto_reel_ng.render import BatchOutcome, RenderJob, RenderResult


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _project(tmp_path: Path, *event_names: str) -> Path:
    root = tmp_path / "proj"
    for name in event_names:
        _touch(root / "2024" / name / "00400.mp4")
    return root


@pytest.fixture
def patched_engine(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Patch the heavy engine seams so render runs without a real ffmpeg."""
    monkeypatch.setattr(
        commands, "FfmpegRuntime", lambda *a, **k: Mock(name="runtime", version=(7, 1))
    )
    monkeypatch.setattr(commands, "detect_capabilities", lambda *a, **k: Mock(name="inventory"))
    monkeypatch.setattr(commands, "select_profile", lambda *a, **k: CPUProfile())
    monkeypatch.setattr(build_module, "probe_media", lambda *a, **k: Mock(name="clip_meta"))
    return monkeypatch


def test_render_two_events_succeeds(
    tmp_path: Path, patched_engine: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A", "2024-06-22 - B")
    seen: dict[str, List[RenderJob]] = {}

    def fake_batch(jobs: List[RenderJob]) -> List[BatchOutcome]:
        seen["jobs"] = jobs
        return [
            BatchOutcome(job=job, result=RenderResult(output_path=job.options.output_dir / "m.mp4"))
            for job in jobs
        ]

    patched_engine.setattr(commands, "render_batch", fake_batch)
    assert main(["render", str(root)]) == 0
    assert len(seen["jobs"]) == 2
    assert capsys.readouterr().out.count("OK") == 2
    # No -o and no config.yaml output: the default sits beside the root, not inside it.
    assert {job.options.output_dir for job in seen["jobs"]} == {tmp_path / "proj-output"}


def test_render_dry_run_prints_commands_and_writes_nothing(
    tmp_path: Path, patched_engine: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A")

    def fake_batch(jobs: List[RenderJob]) -> List[BatchOutcome]:
        assert all(job.options.dry_run for job in jobs)
        return [
            BatchOutcome(
                job=job,
                result=RenderResult(
                    output_path=job.options.output_dir / "m.mp4",
                    dry_run=True,
                    commands=(("ffmpeg", "-i", "in.mp4", "out.mp4"),),
                ),
            )
            for job in jobs
        ]

    patched_engine.setattr(commands, "render_batch", fake_batch)
    assert main(["render", str(root), "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "ffmpeg -i in.mp4 out.mp4" in out
    # dry-run writes nothing: no persisted reel.yaml, no output directory.
    assert not (root / "2024" / "2024-06-21 - A" / "reel.yaml").exists()
    assert not (default_output_dir(root)).exists()


def test_render_one_bad_event_does_not_abort_the_batch(
    tmp_path: Path, patched_engine: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A", "2024-06-22 - B")

    def fake_batch(jobs: List[RenderJob]) -> List[BatchOutcome]:
        outcomes: List[BatchOutcome] = []
        for index, job in enumerate(jobs):
            if index == 0:
                outcomes.append(BatchOutcome(job=job, error="normalize failed"))
            else:
                outcomes.append(
                    BatchOutcome(
                        job=job, result=RenderResult(output_path=job.options.output_dir / "b.mp4")
                    )
                )
        return outcomes

    patched_engine.setattr(commands, "render_batch", fake_batch)
    assert main(["render", str(root)]) == 1  # non-zero because one event errored

    out = capsys.readouterr().out
    assert "ERROR" in out and "normalize failed" in out
    assert "OK" in out  # the other event still rendered


def test_render_isolates_a_build_failure(
    tmp_path: Path, patched_engine: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A", "2024-06-22 - B")

    def fake_probe(path: Path, **_: object) -> Mock:
        if "B" in str(path):
            raise ProbeError("unprobeable clip")
        return Mock()

    patched_engine.setattr(build_module, "probe_media", fake_probe)
    patched_engine.setattr(
        commands,
        "render_batch",
        lambda jobs: [
            BatchOutcome(job=job, result=RenderResult(output_path=job.options.output_dir / "a.mp4"))
            for job in jobs
        ],
    )
    assert main(["render", str(root)]) == 1

    out = capsys.readouterr().out
    assert "ERROR" in out and "unprobeable clip" in out
    assert "OK" in out  # event A still built and rendered


def test_render_device_override_threads_to_profile(
    tmp_path: Path, patched_engine: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    captured: dict[str, object] = {}

    def fake_select(inventory: object, *, override: object = None, **_: object) -> CPUProfile:
        captured["override"] = override
        return CPUProfile()

    patched_engine.setattr(commands, "select_profile", fake_select)
    patched_engine.setattr(
        commands,
        "render_batch",
        lambda jobs: [
            BatchOutcome(job=job, result=RenderResult(output_path=job.options.output_dir / "a.mp4"))
            for job in jobs
        ],
    )
    assert main(["render", str(root), "--device", "cpu"]) == 0
    assert captured["override"] == "cpu"


def test_build_render_job_is_the_shared_d_s1_build_path(
    tmp_path: Path, patched_engine: pytest.MonkeyPatch
) -> None:
    # `build_render_job` (D-S1) is the shared prepare/adopt -> persist -> probe ->
    # resolve helper the job-scheduler worker also builds on (via
    # `prepare_and_persist` + `build_render_job_from_event`); `cmd_render` itself
    # now gates through `_staleness_filter` before calling those same halves. This
    # locks in "no behavior change to the standalone helper" as a regression guard.
    root = _project(tmp_path, "2024-06-21 - A")
    event_dir = root / "2024" / "2024-06-21 - A"
    output_dir = tmp_path / "out"

    job, event = build_module.build_render_job(
        event_dir,
        output_dir=output_dir,
        runtime=commands.FfmpegRuntime(),
        profile=CPUProfile(),
        render_node=None,
        look_defaults={},
    )

    assert job.options.event_dir == event_dir
    assert job.options.output_dir == output_dir
    assert job.options.overwrite is False
    assert job.options.dry_run is False
    assert job.profile.vendor.value == "cpu"
    assert (event_dir / "reel.yaml").exists()  # persisted, same as _build_job
    assert event.seeded  # no reel.yaml existed yet, so the document was seeded


def test_default_output_year_folders_are_not_scanned_as_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # headless-cli spec: rendered year folders are never scanned back in as events.
    root = _project(tmp_path, "2024-06-21 - Midsommar")
    rendered = tmp_path / "proj-output" / "2024" / "2024-06-21 - Midsommar.mp4"
    _touch(rendered)  # what a default-output render leaves behind

    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Midsommar" in out
    assert "[" + str(root / "2024" / "2024-06-21 - Midsommar") + "]" in out
    assert str(rendered.parent) not in out
