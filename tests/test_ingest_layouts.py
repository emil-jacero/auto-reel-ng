"""Tests for the pluggable ingest layouts (D-6): walks, year filter, registry."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from auto_reel_ng.ingest import (
    LayoutError,
    flat_layout,
    get_layout,
    layout_names,
    register_layout,
    year_event_layout,
)


def _mkevent(root: Path, *parts: str) -> Path:
    event = root.joinpath(*parts)
    event.mkdir(parents=True, exist_ok=True)
    return event


# --------------------------------------------------------------------------- #
# year-event walk + metadata hints
# --------------------------------------------------------------------------- #


def test_year_event_walks_year_then_event(tmp_path: Path) -> None:
    a = _mkevent(tmp_path, "2024", "2024-06-21 - Midsummer - Dalarna")
    b = _mkevent(tmp_path, "2023", "2023-12-24 - Christmas")
    refs = list(year_event_layout(tmp_path))
    assert {r.event_dir for r in refs} == {a, b}


def test_year_event_yields_folder_metadata_hint(tmp_path: Path) -> None:
    _mkevent(tmp_path, "2024", "2024-06-21 - Midsummer - Dalarna")
    (ref,) = list(year_event_layout(tmp_path))
    assert ref.metadata_hint is not None
    assert ref.metadata_hint.title == "Midsummer"
    assert ref.metadata_hint.location == "Dalarna"


def test_year_filter_restricts_the_walk(tmp_path: Path) -> None:
    keep = _mkevent(tmp_path, "2024", "2024-06-21 - Midsummer")
    _mkevent(tmp_path, "2023", "2023-12-24 - Christmas")
    refs = list(year_event_layout(tmp_path, years=["2024"]))
    assert [r.event_dir for r in refs] == [keep]


def test_no_year_filter_yields_all_years(tmp_path: Path) -> None:
    _mkevent(tmp_path, "2024", "2024-06-21 - A")
    _mkevent(tmp_path, "2023", "2023-12-24 - B")
    assert len(list(year_event_layout(tmp_path))) == 2


# --------------------------------------------------------------------------- #
# flat walk
# --------------------------------------------------------------------------- #


def test_flat_walks_immediate_subdirs(tmp_path: Path) -> None:
    a = _mkevent(tmp_path, "2024-06-21 - Midsummer")
    b = _mkevent(tmp_path, "2023-12-24 - Christmas")
    refs = list(flat_layout(tmp_path))
    assert {r.event_dir for r in refs} == {a, b}


def test_flat_does_not_descend_a_year_level(tmp_path: Path) -> None:
    _mkevent(tmp_path, "2024", "2024-06-21 - Midsummer")
    refs = list(flat_layout(tmp_path))
    assert [r.event_dir.name for r in refs] == ["2024"]


# --------------------------------------------------------------------------- #
# .reelignore: an ignored event directory is not an event
# --------------------------------------------------------------------------- #


def test_year_event_skips_a_reelignored_event(tmp_path: Path) -> None:
    verona = _mkevent(tmp_path, "2017", "2017-07-07 - Verona")
    (verona / ".reelignore").touch()
    batt = _mkevent(tmp_path, "2017", "2017-07-20 - Båttur")
    assert [r.event_dir for r in year_event_layout(tmp_path)] == [batt]


def test_flat_skips_a_reelignored_event(tmp_path: Path) -> None:
    ignored = _mkevent(tmp_path, "2024-06-21 - Midsummer")
    (ignored / ".reelignore").touch()
    keep = _mkevent(tmp_path, "2023-12-24 - Christmas")
    assert [r.event_dir for r in flat_layout(tmp_path)] == [keep]


def test_marker_at_year_or_root_level_has_no_effect(tmp_path: Path) -> None:
    a = _mkevent(tmp_path, "2024", "2024-06-21 - A")
    b = _mkevent(tmp_path, "2023", "2023-12-24 - B")
    (tmp_path / ".reelignore").touch()
    (tmp_path / "2024" / ".reelignore").touch()
    assert {r.event_dir for r in year_event_layout(tmp_path)} == {a, b}


def test_skipped_event_is_logged_once_at_info(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    verona = _mkevent(tmp_path, "2017", "2017-07-07 - Verona")
    (verona / ".reelignore").touch()
    _mkevent(tmp_path, "2017", "2017-07-20 - Båttur")

    with caplog.at_level(logging.INFO, logger="auto_reel_ng.ingest.layouts"):
        list(year_event_layout(tmp_path))

    skips = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(skips) == 1
    assert skips[0].getMessage() == f"skipping {verona}: .reelignore"


def test_removing_the_marker_restores_the_event(tmp_path: Path) -> None:
    event = _mkevent(tmp_path, "2017", "2017-07-07 - Verona")
    marker = event / ".reelignore"
    marker.touch()
    assert not list(year_event_layout(tmp_path))

    marker.unlink()
    assert [r.event_dir for r in year_event_layout(tmp_path)] == [event]


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #


def test_builtins_are_registered() -> None:
    assert "year-event" in layout_names()
    assert "flat" in layout_names()
    assert get_layout("year-event") is year_event_layout
    assert get_layout("flat") is flat_layout


def test_unknown_layout_fails_loud() -> None:
    with pytest.raises(LayoutError) as exc:
        get_layout("does-not-exist")
    assert "does-not-exist" in str(exc.value)


def test_register_custom_layout() -> None:
    def _custom(root: Path, years: object = None) -> list:
        return []

    register_layout("custom-test-layout", _custom)
    assert get_layout("custom-test-layout") is _custom
