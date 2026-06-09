"""Tests for the pluggable ingest layouts (D-6): walks, year filter, registry."""

from __future__ import annotations

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
