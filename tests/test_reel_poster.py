"""Tests for the event ``poster`` in ``reel.yaml``: loading, the hash and every writer."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest

from auto_reel_ng.errors import ReelParseError
from auto_reel_ng.event.editorial import REEL_FILENAME, apply_editorial_write
from auto_reel_ng.reel import Chapter, ClipRef, Poster, ReelDocument
from auto_reel_ng.reel.parser import load_document, loads_document
from auto_reel_ng.reel.writer import dumps_document
from auto_reel_ng.staleness.fingerprint import _hash_json, editorial_hash

PLAIN = "version: 0\nchapters:\n  - name: ''\n    clips: [a.mp4]\n"

POSTERED = """\
version: 0
metadata:
  title: Midsummer
  date: 2024-06-21
poster:
  clip: a.mp4   # the cheers
  # right after the toast
  at: 3         # intro
chapters:
  - name: ""
    clips:
      - a.mp4
"""


def _doc(poster_block: str) -> ReelDocument:
    return loads_document(
        f"version: 0\n{poster_block}chapters:\n  - name: ''\n    clips: [a.mp4]\n"
    )


def _fails(poster_block: str, *needles: str) -> None:
    with pytest.raises(ReelParseError) as caught:
        _doc(poster_block)
    for needle in needles:
        assert needle in str(caught.value)


def test_a_poster_loads() -> None:
    doc = _doc("poster: {clip: 2024/s1710002.mp4, at: 12.5}\n")
    assert doc.poster == Poster(clip="2024/s1710002.mp4", at=12.5)


def test_time_zero_is_valid() -> None:
    assert _doc("poster: {clip: a.mp4, at: 0}\n").poster == Poster("a.mp4", 0.0)


def test_an_integer_time_is_a_float() -> None:
    poster = _doc("poster: {clip: a.mp4, at: 3}\n").poster
    assert poster is not None and isinstance(poster.at, float) and math.isfinite(poster.at)


def test_no_poster_and_a_null_poster_are_the_default() -> None:
    assert loads_document(PLAIN).poster is None
    assert _doc("poster:\n").poster is None


def test_a_negative_time_fails_naming_the_key() -> None:
    _fails("poster: {clip: a.mp4, at: -1}\n", "poster.at")


def test_a_missing_clip_fails_naming_the_key() -> None:
    _fails("poster: {at: 3}\n", "poster.clip")


def test_a_missing_time_fails_naming_the_key() -> None:
    _fails("poster: {clip: a.mp4}\n", "poster.at")


def test_an_unknown_key_fails_naming_it() -> None:
    _fails("poster: {clip: a.mp4, at: 3, label: x}\n", "poster.label")


@pytest.mark.parametrize("at", ["true", "'3'", ".nan", ".inf", "[1]"])
def test_a_time_that_is_not_a_finite_number_fails(at: str) -> None:
    _fails(f"poster: {{clip: a.mp4, at: {at}}}\n", "poster.at")


@pytest.mark.parametrize("clip", ["''", "'  '", "5", "/abs.mp4", "../x.mp4"])
def test_a_clip_that_is_not_an_identity_fails(clip: str) -> None:
    _fails(f"poster: {{clip: {clip}, at: 1}}\n", "poster.clip")


@pytest.mark.parametrize("block", ["poster: 3\n", "poster: [a]\n", "poster: {}\n"])
def test_a_poster_that_is_not_a_full_mapping_fails(block: str) -> None:
    _fails(block, "poster")


def test_a_clip_that_is_not_on_disk_still_loads() -> None:
    assert _doc("poster: {clip: nowhere/x.mp4, at: 1}\n").poster is not None


def test_a_document_without_a_poster_hashes_as_before() -> None:
    doc = loads_document(PLAIN)
    before_posters = {
        "version": 0,
        "metadata": {"title": None, "date": None, "location": None, "description": None},
        "look": {},
        "chapters": [{"name": "", "clips": ["a.mp4"]}],
        "clips": {},
        "ignore": [],
    }
    assert doc.to_dict() == before_posters
    assert editorial_hash(doc) == _hash_json(before_posters)


def test_adding_or_changing_a_poster_changes_the_hash() -> None:
    plain = editorial_hash(loads_document(PLAIN))
    three = editorial_hash(_doc("poster: {clip: a.mp4, at: 3}\n"))
    four = editorial_hash(_doc("poster: {clip: a.mp4, at: 4}\n"))
    assert len({plain, three, four}) == 3
    assert three == editorial_hash(_doc("poster: {clip: a.mp4, at: 3.0}\n"))


# -- writers ---------------------------------------------------------------- #


def test_a_commented_poster_round_trips_byte_stable() -> None:
    assert dumps_document(loads_document(POSTERED)) == POSTERED


def test_a_typed_document_writes_its_poster_before_chapters() -> None:
    doc = ReelDocument(
        poster=Poster("a.mp4", 2.5), chapters=(Chapter(name="", clips=(ClipRef("a.mp4"),)),)
    )
    text = dumps_document(doc)
    assert text == (
        "version: 0\nposter:\n  clip: a.mp4\n  at: 2.5\n"
        "chapters:\n  - name: ''\n    clips:\n      - a.mp4\n"
    )
    assert loads_document(text).poster == doc.poster


def _event(tmp_path: Path, text: str = POSTERED) -> Path:
    event = tmp_path / "event"
    event.mkdir()
    (event / REEL_FILENAME).write_text(text, encoding="utf-8")
    return event


def _write(event: Path, **changes: object) -> ReelDocument:
    desired = load_document(event / REEL_FILENAME).to_dict()
    desired.pop("version")
    desired.pop("poster", None)
    desired.update(changes)
    return apply_editorial_write(event, desired, today=date(2030, 1, 1))


def test_a_write_that_omits_the_poster_keeps_it_and_its_comments(tmp_path: Path) -> None:
    event = _event(tmp_path)
    mtime = (event / REEL_FILENAME).stat().st_mtime_ns
    _write(event)
    assert (event / REEL_FILENAME).read_text() == POSTERED
    assert (event / REEL_FILENAME).stat().st_mtime_ns == mtime


def test_a_write_that_changes_something_else_keeps_the_poster(tmp_path: Path) -> None:
    event = _event(tmp_path)
    _write(event, metadata={"title": "Midsummer", "date": date(2024, 6, 21), "location": "X"})
    text = (event / REEL_FILENAME).read_text()
    assert (
        "  clip: a.mp4   # the cheers\n  # right after the toast\n  at: 3         # intro\n" in text
    )
    assert "location: X" in text


def test_a_null_poster_keeps_it(tmp_path: Path) -> None:
    event = _event(tmp_path)
    _write(event, poster=None)
    assert (event / REEL_FILENAME).read_text() == POSTERED


def test_an_empty_poster_removes_it(tmp_path: Path) -> None:
    event = _event(tmp_path)
    doc = _write(event, poster={})
    assert doc.poster is None
    assert "poster" not in (event / REEL_FILENAME).read_text()
    assert load_document(event / REEL_FILENAME).poster is None


def test_a_changed_time_is_merged_keeping_the_clip_as_written(tmp_path: Path) -> None:
    event = _event(tmp_path)
    doc = _write(event, poster={"clip": "a.mp4", "at": 9})
    assert doc.poster == Poster("a.mp4", 9.0)
    text = (event / REEL_FILENAME).read_text()
    assert "  clip: a.mp4   # the cheers\n" in text
    assert "  at: 9" in text and "# intro" in text
    assert "  at: 3" not in text


def test_an_equal_poster_writes_nothing(tmp_path: Path) -> None:
    event = _event(tmp_path)
    mtime = (event / REEL_FILENAME).stat().st_mtime_ns
    _write(event, poster={"clip": "a.mp4", "at": 3.0})
    assert (event / REEL_FILENAME).stat().st_mtime_ns == mtime


def test_a_poster_is_added_before_the_chapters(tmp_path: Path) -> None:
    event = _event(tmp_path, "version: 0\nmetadata:\n  title: T\n  date: 2024-06-21\n" + PLAIN[11:])
    _write(event, poster={"clip": "a.mp4", "at": 1})
    text = (event / REEL_FILENAME).read_text()
    assert text.index("poster:") < text.index("chapters:")
    assert load_document(event / REEL_FILENAME).poster == Poster("a.mp4", 1.0)


def test_an_invalid_poster_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    event = _event(tmp_path)
    path = event / REEL_FILENAME
    before, mtime = path.read_bytes(), path.stat().st_mtime_ns
    with pytest.raises(ReelParseError, match=r"poster\.at"):
        _write(event, poster={"clip": "a.mp4", "at": -2})
    assert path.read_bytes() == before and path.stat().st_mtime_ns == mtime
