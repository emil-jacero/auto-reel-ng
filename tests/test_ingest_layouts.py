"""Tests for the pluggable ingest layouts (D-6): walks, year filter, registry."""

from __future__ import annotations

import logging
import os
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
# aliases of one real event directory are walked once
# --------------------------------------------------------------------------- #

LOGGER = "auto_reel_ng.ingest.layouts"


def _alias_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_symlinked_alias_beside_its_target_is_dropped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    kalas = _mkevent(tmp_path, "2024", "2024-07-20 - Kalas")
    (tmp_path / "2024" / "2024-07-20 - Fest").symlink_to(kalas, target_is_directory=True)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        refs = list(year_event_layout(tmp_path))

    assert [r.event_dir for r in refs] == [kalas]
    fest = tmp_path / "2024" / "2024-07-20 - Fest"
    assert _alias_warnings(caplog) == [f"skipping {fest}: alias of {kalas} (-> {kalas.resolve()})"]


def test_the_real_directory_wins_even_when_the_alias_sorts_first(tmp_path: Path) -> None:
    kalas = _mkevent(tmp_path, "2024-07-20 - Kalas")
    (tmp_path / "2024-07-20 - Fest").symlink_to(kalas, target_is_directory=True)
    assert [r.event_dir for r in flat_layout(tmp_path)] == [kalas]


def test_alias_in_another_year_is_dropped_under_a_year_filter(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    target = _mkevent(tmp_path, "2024", "2024-07-20 - Kalas")
    _mkevent(tmp_path, "2025")
    alias = tmp_path / "2025" / "2024-07-20 - Kalas"
    alias.symlink_to(target, target_is_directory=True)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        refs = list(year_event_layout(tmp_path, years=["2025"]))

    assert refs == []
    assert _alias_warnings(caplog) == [f"skipping {alias}: alias of {target} (-> {target})"]


def test_symlinked_year_directory_yields_each_event_once_under_the_real_year(
    tmp_path: Path,
) -> None:
    a = _mkevent(tmp_path, "2024", "2024-06-21 - A")
    b = _mkevent(tmp_path, "2024", "2024-07-04 - B")
    (tmp_path / "2023").symlink_to(tmp_path / "2024", target_is_directory=True)
    assert [r.event_dir for r in year_event_layout(tmp_path)] == [a, b]


def test_filtering_on_a_symlinked_year_name_yields_nothing_and_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    a = _mkevent(tmp_path, "2024", "2024-06-21 - A")
    (tmp_path / "2023").symlink_to(tmp_path / "2024", target_is_directory=True)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        refs = list(year_event_layout(tmp_path, years=["2023"]))

    assert refs == []
    assert _alias_warnings(caplog) == [
        f"skipping {tmp_path / '2023' / a.name}: alias of {a} (-> {a})"
    ]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unreadable_year_outside_the_filter_is_skipped_not_fatal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    kept = _mkevent(tmp_path, "2024", "2024-07-20 - Kalas")
    locked = _mkevent(tmp_path, "2023")
    locked.chmod(0o000)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER):
            refs = list(year_event_layout(tmp_path, years=["2024"]))
    finally:
        locked.chmod(0o755)

    assert [r.event_dir for r in refs] == [kept]
    assert any(str(locked) in r.getMessage() for r in caplog.records)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unreadable_selected_year_still_fails_loud(tmp_path: Path) -> None:
    _mkevent(tmp_path, "2024", "2024-07-20 - Kalas")
    locked = _mkevent(tmp_path, "2023")
    locked.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            list(year_event_layout(tmp_path, years=["2023"]))
        with pytest.raises(PermissionError):
            list(year_event_layout(tmp_path))
    finally:
        locked.chmod(0o755)


def test_root_behind_a_symlink_still_keeps_the_canonical_path(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    kalas = _mkevent(real_root, "2024", "2024-07-20 - Kalas")
    (real_root / "2024" / "2024-07-20 - Fest").symlink_to(kalas, target_is_directory=True)
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)

    refs = list(year_event_layout(linked_root))
    assert [r.event_dir for r in refs] == [linked_root / "2024" / "2024-07-20 - Kalas"]


def test_unduplicated_symlink_to_an_outside_directory_is_kept_silently(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    outside = _mkevent(tmp_path, "elsewhere", "2024-07-20 - Kalas")
    root = tmp_path / "proj"
    _mkevent(root, "2024")
    link = root / "2024" / "2024-07-20 - Kalas"
    link.symlink_to(outside, target_is_directory=True)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        refs = list(year_event_layout(root))

    assert [r.event_dir for r in refs] == [link]
    assert caplog.records == []


def test_two_symlinks_to_an_outside_target_keep_the_first_in_walk_order(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    outside = _mkevent(tmp_path, "elsewhere", "Kalas")
    root = tmp_path / "proj"
    root.mkdir()
    first, second = root / "A", root / "B"
    first.symlink_to(outside, target_is_directory=True)
    second.symlink_to(outside, target_is_directory=True)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        refs = list(flat_layout(root))

    assert [r.event_dir for r in refs] == [first]
    assert _alias_warnings(caplog) == [f"skipping {second}: alias of {first} (-> {outside})"]


def test_an_ignored_target_takes_its_aliases_with_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    kalas = _mkevent(tmp_path, "2024", "2024-07-20 - Kalas")
    (kalas / ".reelignore").touch()
    (tmp_path / "2024" / "2024-07-20 - Fest").symlink_to(kalas, target_is_directory=True)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        refs = list(year_event_layout(tmp_path))

    assert refs == []
    assert {r.levelno for r in caplog.records} == {logging.INFO}
    assert len(caplog.records) == 2


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
