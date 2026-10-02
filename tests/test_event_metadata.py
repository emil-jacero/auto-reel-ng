"""Tests for event metadata resolution (reel.yaml over folder name) and the processable rule."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from auto_reel_ng.cli.adoption import persist, prepare_event
from auto_reel_ng.errors import EventMetadataError, ReelParseError
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.event.discovery import parse_folder_name
from auto_reel_ng.event.metadata import (
    REEL_FILENAME,
    load_authored_document,
    load_event_document,
    reel_exists,
    require_processable,
    resolve_metadata,
)
from auto_reel_ng.reel.document import Metadata

TODAY = date(2026, 9, 27)


def _event(tmp_path: Path, name: str, reel_yaml: str | None = None) -> Path:
    event_dir = tmp_path / name
    event_dir.mkdir()
    (event_dir / "00400.mp4").write_bytes(b"")
    if reel_yaml is not None:
        (event_dir / REEL_FILENAME).write_text(reel_yaml, encoding="utf-8")
    return event_dir


def _metadata_on_disk(event_dir: Path) -> dict:
    data = YAML(typ="safe").load((event_dir / REEL_FILENAME).read_text(encoding="utf-8"))
    return dict(data.get("metadata") or {})


# --------------------------------------------------------------------------- #
# resolve_metadata
# --------------------------------------------------------------------------- #


def test_authored_fields_win_per_field() -> None:
    folder = parse_folder_name("2024-06-21 - Midsummer - Dalarna")
    authored = Metadata(title="Midsommar", date=None, location=None, description="d")
    resolved = resolve_metadata(authored, folder)
    assert resolved.title == "Midsommar"
    assert resolved.date == date(2024, 6, 21)
    assert resolved.location == "Dalarna"
    assert resolved.description == "d"


def test_blank_authored_value_counts_as_unset() -> None:
    folder = parse_folder_name("2024-06-21 - Midsummer - Dalarna")
    resolved = resolve_metadata(Metadata(title="  ", location=""), folder)
    assert resolved.title == "Midsummer"
    assert resolved.location == "Dalarna"


def test_folder_rename_changes_only_unset_fields() -> None:
    authored = Metadata(title="Golf", date=date(2019, 4, 30))
    before = resolve_metadata(authored, parse_folder_name("2019-04-31 - Golfträning"))
    after = resolve_metadata(authored, parse_folder_name("2019-04-31 - Golfträning - Tjörn"))
    assert (before.title, before.date, before.location) == ("Golf", date(2019, 4, 30), None)
    assert (after.title, after.date, after.location) == ("Golf", date(2019, 4, 30), "Tjörn")


# --------------------------------------------------------------------------- #
# load_event_document
# --------------------------------------------------------------------------- #


def test_legacy_reel_yaml_without_date_takes_folder_date(tmp_path: Path) -> None:
    event_dir = _event(
        tmp_path, "2025-01-13 - Resa till Gran Canaria", "title: Resa till Gran Canaria\n"
    )
    document, seeded = load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)
    assert seeded is False
    assert document.metadata.date == date(2025, 1, 13)
    assert document.metadata.title == "Resa till Gran Canaria"


def test_reel_yaml_date_beats_impossible_folder_date(tmp_path: Path) -> None:
    event_dir = _event(
        tmp_path,
        "2019-04-31 - Golfträning med Emil - Tjörn",
        "version: 0\nmetadata:\n  date: 2019-04-30\n",
    )
    document, _ = load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)
    assert document.metadata.date == date(2019, 4, 30)
    assert document.metadata.title == "Golfträning med Emil"
    require_processable(event_dir, document.metadata, today=TODAY)


@pytest.mark.parametrize(
    "reel_yaml",
    [
        "title: Resa till Gran Canaria\n",  # legacy (no raw structure)
        "version: 0\nmetadata:\n  title: Resa\n",  # v0
    ],
)
def test_resolution_is_never_persisted(tmp_path: Path, reel_yaml: str) -> None:
    event_dir = _event(tmp_path, "2025-01-13 - Resa till Gran Canaria", reel_yaml)
    prepared = prepare_event(
        event_dir, order=DEFAULT_CLIP_ORDER
    )  # 00400.mp4 is NEW -> adopted -> changed
    assert prepared.adopted == ("00400.mp4",)
    assert prepared.document.metadata.date == date(2025, 1, 13)

    assert persist(prepared) is not None
    assert "date" not in _metadata_on_disk(event_dir)
    assert "00400.mp4" in (event_dir / REEL_FILENAME).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# require_processable
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("name", "phrase"),
    [
        ("2019-04-31 - Golfträning", "2019-04-31 is not a real date"),
        ("2004 - Yngve berättar om skövde", "year only"),
        ("Blandat", "no date"),
    ],
)
def test_missing_date_names_the_folder_problem(tmp_path: Path, name: str, phrase: str) -> None:
    event_dir = _event(tmp_path, name)
    document, _ = load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)
    with pytest.raises(EventMetadataError) as info:
        require_processable(event_dir, document.metadata, today=TODAY)
    assert phrase in info.value.reason
    assert "metadata.date" in info.value.reason
    assert name in str(info.value)


def test_missing_title_is_rejected(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21")
    document, _ = load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)
    with pytest.raises(EventMetadataError, match="no title.*metadata.title"):
        require_processable(event_dir, document.metadata, today=TODAY)


def test_future_date_is_rejected(tmp_path: Path) -> None:
    tomorrow = TODAY + timedelta(days=1)
    event_dir = _event(tmp_path, f"{tomorrow.isoformat()} - Framtid")
    document, _ = load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)
    with pytest.raises(EventMetadataError, match="in the future"):
        require_processable(event_dir, document.metadata, today=TODAY)
    require_processable(event_dir, document.metadata, today=tomorrow)


def test_reel_yaml_date_fixes_a_year_only_folder(tmp_path: Path) -> None:
    event_dir = _event(
        tmp_path, "2004 - Yngve berättar om skövde", "version: 0\nmetadata:\n  date: 2004-05-01\n"
    )
    document, _ = load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)
    require_processable(event_dir, document.metadata, today=TODAY)


# --------------------------------------------------------------------------- #
# reel_exists / load_authored_document: a refusal from the disk is not "absent"
# --------------------------------------------------------------------------- #

skip_as_root = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")

_REAL_REEL = "version: 0\nmetadata:\n  title: Real\nchapters: []\n"


@contextmanager
def _mode(path: Path, mode: int) -> Iterator[None]:
    path.chmod(mode)
    try:
        yield
    finally:
        path.chmod(0o755 if path.is_dir() else 0o644)


def test_reel_exists_is_true_for_a_present_file(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21 - Fest", _REAL_REEL)
    assert reel_exists(event_dir / REEL_FILENAME) is True


def test_reel_exists_is_false_for_a_missing_file(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21 - Fest")
    assert reel_exists(event_dir / REEL_FILENAME) is False


def test_reel_exists_is_false_when_the_parent_is_a_regular_file(tmp_path: Path) -> None:
    not_a_dir = tmp_path / "plain"
    not_a_dir.write_text("x", encoding="utf-8")
    assert reel_exists(not_a_dir / REEL_FILENAME) is False


def test_reel_exists_follows_symlinks(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21 - Fest")
    (event_dir / REEL_FILENAME).symlink_to(tmp_path / "nowhere.yaml")
    assert reel_exists(event_dir / REEL_FILENAME) is False
    (event_dir / REEL_FILENAME).unlink()
    target = tmp_path / "real.yaml"
    target.write_text(_REAL_REEL, encoding="utf-8")
    (event_dir / REEL_FILENAME).symlink_to(target)
    assert reel_exists(event_dir / REEL_FILENAME) is True


@skip_as_root
def test_reel_exists_raises_for_a_folder_that_cannot_be_searched(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21 - Fest", _REAL_REEL)
    with _mode(event_dir, 0o600), pytest.raises(PermissionError):
        reel_exists(event_dir / REEL_FILENAME)


@skip_as_root
def test_an_unsearchable_folder_never_seeds_over_its_reel_yaml(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21 - Fest", _REAL_REEL)
    with _mode(event_dir, 0o600):
        with pytest.raises(PermissionError):
            load_authored_document(event_dir, order=DEFAULT_CLIP_ORDER)
        with pytest.raises(PermissionError):
            load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)


def test_a_searchable_folder_without_a_reel_yaml_still_seeds(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21 - Fest")
    document, seeded = load_authored_document(event_dir, order=DEFAULT_CLIP_ORDER)
    assert seeded is True
    assert [c.identity for ch in document.chapters for c in ch.clips] == ["00400.mp4"]


@skip_as_root
def test_an_unreadable_reel_yaml_in_a_searchable_folder_is_a_parse_error(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21 - Fest", _REAL_REEL)
    with _mode(event_dir / REEL_FILENAME, 0o000):
        with pytest.raises(ReelParseError, match=REEL_FILENAME):
            load_authored_document(event_dir, order=DEFAULT_CLIP_ORDER)
