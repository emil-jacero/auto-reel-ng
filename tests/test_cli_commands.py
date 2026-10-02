"""Tests for the scan / analyze / import subcommands and CLI option precedence."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import Mock

import pytest

from auto_reel_ng.analysis import Segment, SegmentKind
from auto_reel_ng.cli import commands, context
from auto_reel_ng.cli.adoption import persist, prepare_event
from auto_reel_ng.cli.main import main
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
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

    monkeypatch.setattr(commands, "FfmpegRuntime", lambda *a, **k: Mock())
    monkeypatch.setattr(
        commands,
        "analyze_event",
        lambda *a, **k: {"00400.mp4": [Segment(0.0, 1.0, SegmentKind.BLACK, 0.9)]},
    )

    assert main(["analyze", str(root)]) == 0
    out = capsys.readouterr().out
    assert "black" in out.lower()
    assert (event / "reel.yaml").read_text(encoding="utf-8") == before  # untouched


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
