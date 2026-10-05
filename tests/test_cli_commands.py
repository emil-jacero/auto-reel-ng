"""Tests for the scan / analyze / import subcommands and CLI option precedence."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError

from auto_reel_ng.analysis import Segment, SegmentKind
from auto_reel_ng.cli import analyze as analyze_cli
from auto_reel_ng.cli import commands, context
from auto_reel_ng.cli.adoption import persist, prepare_event
from auto_reel_ng.cli.main import main
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.persistence.engine import make_engine, make_session_factory
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Base, Job, JobKind, JobStatus
from auto_reel_ng.reel import load_document


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


# --------------------------------------------------------------------------- #
# scan / list (6.1)
# --------------------------------------------------------------------------- #


def test_scan_lists_events_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")

    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Midsummer" in out
    assert "NEW" in out  # no reel.yaml yet -> reconcile against empty -> NEW
    assert not (event / "reel.yaml").exists()  # scan never writes


def test_scan_reports_missing_clip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))  # reel.yaml referencing 00400
    (event / "00400.mp4").unlink()  # now absent from disk

    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert "MISSING" in out


def test_list_alias_works(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - Midsummer" / "00400.mp4")
    assert main(["list", str(root)]) == 0


def test_scan_reports_staleness_with_reasons(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")

    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert "stale: no_manifest" in out


def test_scan_skips_reelignored_event_and_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    ignored = root / "2017" / "2017-07-07 - Verona"
    _touch(ignored / "00100.mp4")
    _touch(ignored / ".reelignore")
    event = root / "2017" / "2017-07-20 - Båttur"
    _touch(event / "00400.mp4")
    _touch(event / "original" / "00400.MTS")

    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Båttur" in out
    assert "00400.mp4" in out
    assert "Verona" not in out
    assert "original" not in out


def test_scan_lists_a_symlinked_alias_once_under_its_real_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    kalas = root / "2024" / "2024-07-20 - Kalas"
    _touch(kalas / "a.mp4")
    (root / "2024" / "2024-07-20 - Fest").symlink_to(kalas, target_is_directory=True)

    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert out.count("2024-07-20 - Kalas") == 1
    assert "Fest" not in out
    assert not (kalas / "reel.yaml").exists()


def test_scan_never_writes_a_manifest(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")

    assert main(["scan", str(root)]) == 0
    assert not (event / ".auto-reel" / "cache" / "render-manifest.json").exists()


# --------------------------------------------------------------------------- #
# analyze (6.2)
# --------------------------------------------------------------------------- #


def test_analyze_prints_and_leaves_reel_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))
    before = (event / "reel.yaml").read_text(encoding="utf-8")

    monkeypatch.setattr(analyze_cli, "FfmpegRuntime", lambda *a, **k: Mock())
    monkeypatch.setattr(
        analyze_cli,
        "analyze_event",
        lambda *a, **k: {"00400.mp4": [Segment(0.0, 1.0, SegmentKind.BLACK, 0.9)]},
    )

    assert main(["analyze", str(root)]) == 0
    out = capsys.readouterr().out
    assert "black" in out.lower()
    assert (event / "reel.yaml").read_text(encoding="utf-8") == before  # untouched


def _never_run_ffmpeg(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("ffmpeg/ffprobe must not be touched")


def test_analyze_force_reruns_detection_inline_on_a_warm_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    calls: list[bool] = []

    def fake_analyze_event(*_a: object, force: bool = False, **_k: object) -> object:
        calls.append(force)
        return {"00400.mp4": []}

    monkeypatch.setattr(analyze_cli, "FfmpegRuntime", lambda *a, **k: Mock())
    monkeypatch.setattr(analyze_cli, "analyze_event", fake_analyze_event)

    assert main(["analyze", str(root)]) == 0
    assert main(["analyze", str(root), "--force"]) == 0

    assert calls == [False, True]  # no flag behaves as before; --force ignores the cache


@pytest.fixture
def analysis_store(postgres_container: str, monkeypatch: pytest.MonkeyPatch) -> JobStore:
    """A job store on the test container, with ``DATABASE_URL`` pointing the CLI at it."""
    monkeypatch.setenv("DATABASE_URL", postgres_container)
    engine = make_engine(postgres_container)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(Job.__table__.delete())
    return JobStore(make_session_factory(engine))


@pytest.mark.requires_db
def test_analyze_enqueue_twice_queues_one_job_and_runs_nothing(
    tmp_path: Path,
    analysis_store: JobStore,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    before = sorted(p.relative_to(root) for p in root.rglob("*"))
    monkeypatch.setattr(analyze_cli, "FfmpegRuntime", _never_run_ffmpeg)
    monkeypatch.setattr(analyze_cli, "analyze_event", _never_run_ffmpeg)

    assert main(["analyze", str(root), "--enqueue"]) == 0
    first = capsys.readouterr().out
    assert main(["analyze", str(root), "--enqueue"]) == 0
    second = capsys.readouterr().out

    jobs = analysis_store.list_by_status(JobStatus.QUEUED, kind=JobKind.ANALYSIS)
    assert len(jobs) == 1 and jobs[0].force is False
    assert jobs[0].event_dir == "2024/2024-06-21 - Midsummer"
    assert f"queued  2024/2024-06-21 - Midsummer  {jobs[0].id}" in first
    assert f"active  2024/2024-06-21 - Midsummer  {jobs[0].id}" in second
    assert sorted(p.relative_to(root) for p in root.rglob("*")) == before  # no file written


@pytest.mark.requires_db
def test_analyze_enqueue_force_stores_force(
    tmp_path: Path, analysis_store: JobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - Midsummer" / "00400.mp4")
    monkeypatch.setattr(analyze_cli, "FfmpegRuntime", _never_run_ffmpeg)

    assert main(["analyze", str(root), "--enqueue", "--force"]) == 0

    jobs = analysis_store.list_by_status(JobStatus.QUEUED, kind=JobKind.ANALYSIS)
    assert [job.force for job in jobs] == [True]


def test_analyze_enqueue_reports_an_unreachable_database_as_enqueue_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - Midsummer" / "00400.mp4")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody:x@127.0.0.1:9/none")
    monkeypatch.setattr(commands, "FfmpegRuntime", lambda *a, **k: Mock(version=(8, 0)))
    monkeypatch.setattr(analyze_cli, "FfmpegRuntime", _never_run_ffmpeg)
    outcomes = []
    for argv in (["enqueue", str(root)], ["analyze", str(root), "--enqueue"]):
        with pytest.raises(Exception) as excinfo:  # pylint: disable=broad-exception-caught
            main(argv)
        outcomes.append(type(excinfo.value))

    assert outcomes[0] is outcomes[1]
    assert issubclass(outcomes[1], OperationalError)


# --------------------------------------------------------------------------- #
# import (6.3)
# --------------------------------------------------------------------------- #


def test_import_legacy_metadata_roundtrip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Whatever"
    event.mkdir(parents=True)
    (event / "metadata.yaml").write_text(
        "metadata:\n  title: Beach Day\n  location: Varberg\n", encoding="utf-8"
    )

    assert main(["import", str(root)]) == 0

    reel = event / "reel.yaml"
    assert reel.exists()
    document = load_document(reel)
    assert document.metadata.title == "Beach Day"
    assert document.metadata.location == "Varberg"
    assert "imported" in capsys.readouterr().out


def test_import_does_not_clobber_v2_reel(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Whatever"
    _touch(event / "00400.mp4")
    persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))  # a v2 reel.yaml exists
    (event / "metadata.yaml").write_text("metadata:\n  title: Other\n", encoding="utf-8")
    before = (event / "reel.yaml").read_text(encoding="utf-8")

    assert main(["import", str(root)]) == 0
    assert (event / "reel.yaml").read_text(encoding="utf-8") == before  # not clobbered
    assert "SKIP" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI > config precedence (D-CLI2)
# --------------------------------------------------------------------------- #


def test_cli_layout_overrides_config(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "config.yaml").write_text("layout: year-event\n", encoding="utf-8")
    (root / "2024-06-21 - X").mkdir()  # an event directly under root (flat shape)

    args = argparse.Namespace(root=str(root), output=None, years=None, layout="flat")
    ctx = context.project_context(args)

    assert ctx.layout_name == "flat"  # CLI flag wins over config.yaml
    assert len(ctx.events) == 1


def test_config_layout_used_when_no_cli_override(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "config.yaml").write_text("layout: flat\n", encoding="utf-8")
    (root / "2024-06-21 - X").mkdir()

    args = argparse.Namespace(root=str(root), output=None, years=None, layout=None)
    ctx = context.project_context(args)

    assert ctx.layout_name == "flat"


# --------------------------------------------------------------------------- #
# scan names the old and the new movie file of a renamed event
# --------------------------------------------------------------------------- #

_GRILLNING = "2024-06-27 - Grillning med Grannar"


def _render_record(root: Path, event_dir: Path) -> Path:
    """Adopt ``event_dir`` and leave a manifest + movie at its current fingerprint (no real
    render). Returns the movie."""
    from auto_reel_ng.config import default_output_dir
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event = prepare_event(event_dir, order=DEFAULT_CLIP_ORDER, adopt=True)
    persist(event)
    version = FfmpegRuntime().version
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(root)),
        ffmpeg_version=version,
    )
    movie = default_output_dir(root) / output_relpath(event.document.metadata)
    movie.parent.mkdir(parents=True, exist_ok=True)
    movie.write_bytes(b"rendered")
    write_manifest(
        event_dir, fingerprint, output=movie.name, engine_identity=engine_identity(version)
    )
    return movie


def _retitle(event_dir: Path, old: str, new: str) -> None:
    reel = event_dir / "reel.yaml"
    text = reel.read_text(encoding="utf-8")
    assert f"title: {old}\n" in text
    reel.write_text(text.replace(f"title: {old}\n", f"title: {new}\n"), encoding="utf-8")


def _stale_line(capsys: pytest.CaptureFixture[str]) -> str:
    lines = [line.strip() for line in capsys.readouterr().out.splitlines()]
    (line,) = [line for line in lines if line == "fresh" or line.startswith("stale: ")]
    return line


def test_scan_names_the_old_and_new_movie_of_a_renamed_event(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / _GRILLNING
    _touch(event / "00400.mp4")
    movie = _render_record(root, event)
    _retitle(event, "Grillning med Grannar", "Grillkväll med grannarna")

    assert main(["scan", str(root)]) == 0

    assert _stale_line(capsys) == (
        "stale: editorial, output_renamed "
        "(was '2024-06-27 - Grillning med Grannar.mp4', "
        "now '2024-06-27 - Grillkväll med grannarna.mp4')"
    )
    assert movie.read_bytes() == b"rendered"  # scan renders and deletes nothing
    assert [p.name for p in movie.parent.iterdir()] == [movie.name]


def test_scan_quotes_names_with_an_apostrophe_in_single_quotes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / _GRILLNING
    _touch(event / "00400.mp4")
    _render_record(root, event)
    _retitle(event, "Grillning med Grannar", "Mom's party")

    assert main(["scan", str(root)]) == 0

    assert _stale_line(capsys) == (
        "stale: editorial, output_renamed "
        "(was '2024-06-27 - Grillning med Grannar.mp4', "
        "now '2024-06-27 - Mom's party.mp4')"
    )


def test_scan_prints_a_deleted_movie_as_output_without_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / _GRILLNING
    _touch(event / "00400.mp4")
    _render_record(root, event).unlink()

    assert main(["scan", str(root)]) == 0

    assert _stale_line(capsys) == "stale: output"


def test_scan_prints_a_fresh_event_as_before(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / _GRILLNING
    _touch(event / "00400.mp4")
    _render_record(root, event)

    assert main(["scan", str(root)]) == 0

    assert _stale_line(capsys) == "fresh"
