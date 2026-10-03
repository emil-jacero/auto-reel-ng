"""Tests for a chapter's ``card`` in ``reel.yaml``: loading, validation and the editorial hash."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from auto_reel_ng.errors import ReelParseError
from auto_reel_ng.reel import ChapterCard
from auto_reel_ng.reel.card import (
    CARD_BACKGROUNDS,
    CARD_KEYS,
    CARD_MAX_DURATION,
    CARD_MAX_FONT_SIZE,
    CARD_MIN_DURATION,
    CARD_MIN_FONT_SIZE,
    CARD_POSITIONS,
)
from auto_reel_ng.reel.parser import loads_document
from auto_reel_ng.staleness.fingerprint import _hash_json, editorial_hash

#: The full card the README documents; the README test checks the same text is there.
FULL_CARD = """\
card:
  title: Midsommar 2024
  subtitle: Hos mormor
  duration: 5
  background: black
  font_family: DejaVu Serif
  title_font_size: 110
  subtitle_font_size: 50
  text_color: "#FFD700"
  position: bottom
"""


def _reel(card_block: str, *, name: str = '""') -> str:
    """A one-chapter document whose chapter ``name`` carries ``card_block`` (a YAML mapping)."""
    indented = "".join(f"    {line}\n" for line in card_block.splitlines())
    return f"version: 0\nchapters:\n  - name: {name}\n{indented}    clips:\n      - a.mp4\n"


def _card(card_body: str) -> ChapterCard | None:
    """Load a document whose default chapter has ``card:`` followed by ``card_body``."""
    return loads_document(_reel(f"card:\n{card_body}")).chapters[0].card


def _fails(card_body: str, *needles: str) -> str:
    with pytest.raises(ReelParseError) as caught:
        loads_document(_reel(f"card:\n{card_body}"))
    message = str(caught.value)
    for needle in needles:
        assert needle in message
    return message


def test_a_full_card_loads() -> None:
    doc = loads_document(_reel(FULL_CARD))
    assert doc.chapters[0].card == ChapterCard(
        title="Midsommar 2024",
        subtitle="Hos mormor",
        duration=5.0,
        background="black",
        font_family="DejaVu Serif",
        title_font_size=110,
        subtitle_font_size=50,
        text_color="#FFD700",
        position="bottom",
    )


def test_the_readme_documents_the_same_full_card() -> None:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    indented = "".join(f"    {line}\n" for line in FULL_CARD.splitlines())
    assert indented in readme


@pytest.mark.parametrize("block", ["card: {}", "card:", "card: null"])
def test_an_empty_or_null_card_means_no_overrides(block: str) -> None:
    assert loads_document(_reel(block)).chapters[0].card is None


def test_a_chapter_without_a_card_has_none() -> None:
    assert (
        loads_document("version: 0\nchapters:\n  - name: ''\n    clips: [a.mp4]\n").chapters[0].card
        is None
    )


def test_a_card_on_a_named_chapter_belongs_to_that_chapter() -> None:
    text = (
        "version: 0\nchapters:\n  - name: ''\n    clips: [a.mp4]\n"
        "  - name: Reception\n    card: {duration: 3}\n    clips: [Reception/b.mp4]\n"
    )
    doc = loads_document(text)
    assert doc.chapters[0].card is None
    assert doc.chapters[1].card == ChapterCard(duration=3.0)


def test_an_unknown_key_fails_loud_and_lists_the_allowed_keys() -> None:
    message = _fails("  titel: Hej\n", "chapters[0].card.titel")
    for key in CARD_KEYS:
        assert key in message
    assert CARD_KEYS == (
        "title",
        "subtitle",
        "duration",
        "background",
        "font_family",
        "title_font_size",
        "subtitle_font_size",
        "text_color",
        "position",
    )


@pytest.mark.parametrize("value", ["0.1", "600", ".inf", "-.inf", ".nan", "0.49", "60.5", "0"])
def test_a_duration_out_of_range_fails_loud(value: str) -> None:
    _fails(f"  duration: {value}\n", "chapters[0].card.duration")


def test_the_duration_bounds_are_pinned_at_their_edges() -> None:
    assert (CARD_MIN_DURATION, CARD_MAX_DURATION) == (0.5, 60.0)
    assert _card("  duration: 0.5\n") == ChapterCard(duration=0.5)
    assert _card("  duration: 60\n") == ChapterCard(duration=60.0)
    assert _card("  duration: 7.25\n") == ChapterCard(duration=7.25)


def test_a_huge_integer_duration_fails_loud_not_with_an_overflow() -> None:
    _fails(f"  duration: {10**400}\n", "chapters[0].card.duration")


@pytest.mark.parametrize(
    "line", ["title_font_size: true", "duration: false", "subtitle_font_size: false"]
)
def test_a_boolean_is_not_a_number(line: str) -> None:
    _fails(f"  {line}\n", f"chapters[0].card.{line.split(':')[0]}")


def test_a_float_font_size_fails_loud() -> None:
    _fails("  title_font_size: 96.5\n", "chapters[0].card.title_font_size")


@pytest.mark.parametrize(
    "line", ["subtitle_font_size: 7", "title_font_size: 401", "title_font_size: 0"]
)
def test_a_font_size_outside_8_to_400_fails_loud(line: str) -> None:
    _fails(f"  {line}\n", f"chapters[0].card.{line.split(':')[0]}")


def test_the_font_size_bounds_are_pinned_at_their_edges() -> None:
    assert (CARD_MIN_FONT_SIZE, CARD_MAX_FONT_SIZE) == (8, 400)
    assert _card("  title_font_size: 8\n  subtitle_font_size: 400\n") == ChapterCard(
        title_font_size=8, subtitle_font_size=400
    )


@pytest.mark.parametrize(
    "line", ['title: "   "', 'title: ""', 'font_family: ""', 'font_family: "  "']
)
def test_a_blank_title_or_font_fails_loud(line: str) -> None:
    _fails(f"  {line}\n", f"chapters[0].card.{line.split(':')[0]}")


def test_a_subtitle_may_be_empty() -> None:
    assert _card('  subtitle: ""\n') == ChapterCard(subtitle="")


@pytest.mark.parametrize("colour", ["red", '"#FFF"', '"#GG0000"', '"FFD700"', '"#FFD7000"', "12"])
def test_a_malformed_colour_fails_loud(colour: str) -> None:
    _fails(f"  text_color: {colour}\n", "chapters[0].card.text_color")


def test_a_colour_in_either_case_loads() -> None:
    assert _card('  text_color: "#ffd700"\n') == ChapterCard(text_color="#ffd700")
    assert _card('  text_color: "#FfD700"\n') == ChapterCard(text_color="#FfD700")


def test_an_unquoted_colour_fails_loud_instead_of_reading_as_unset() -> None:
    message = _fails("  text_color: #FFD700\n", "chapters[0].card.text_color", "null")
    assert "quoted" in message


def test_a_null_value_fails_loud() -> None:
    _fails("  subtitle:\n", "chapters[0].card.subtitle", "null")
    _fails("  duration: null\n", "chapters[0].card.duration", "null")


def test_a_card_that_is_not_a_mapping_fails_loud() -> None:
    with pytest.raises(ReelParseError) as caught:
        loads_document(_reel("card: [title, Hej]"))
    assert "chapters[0].card" in str(caught.value)
    assert "must be a mapping" in str(caught.value)


def test_the_error_names_the_chapter_index() -> None:
    text = (
        "version: 0\nchapters:\n  - name: ''\n    clips: [a.mp4]\n"
        "  - name: B\n    card: {duration: 0}\n    clips: [B/b.mp4]\n"
    )
    with pytest.raises(ReelParseError, match=r"chapters\[1\]\.card\.duration"):
        loads_document(text)


def test_background_and_position_accept_only_their_sets() -> None:
    assert CARD_BACKGROUNDS == ("black", "video")
    assert CARD_POSITIONS == ("center", "top", "bottom")
    for value in CARD_BACKGROUNDS:
        assert _card(f"  background: {value}\n") == ChapterCard(background=value)
    for value in CARD_POSITIONS:
        assert _card(f"  position: {value}\n") == ChapterCard(position=value)
    _fails("  background: transparent\n", "chapters[0].card.background", "black", "video")
    _fails("  position: middle\n", "chapters[0].card.position", "center", "top", "bottom")
    _fails("  position: 3\n", "chapters[0].card.position")


def test_the_font_family_is_not_checked_against_fonts_at_load() -> None:
    assert _card("  font_family: Not A Real Font\n") == ChapterCard(font_family="Not A Real Font")


def test_a_card_to_dict_lists_only_set_fields_in_key_order() -> None:
    card = ChapterCard(position="top", title="A", duration=3.0)
    assert list(card.to_dict()) == ["title", "duration", "position"]
    assert ChapterCard().to_dict() == {}


def test_a_chapter_key_outside_card_stays_ignored() -> None:
    doc = loads_document(
        "version: 0\nchapters:\n  - name: ''\n    colour: red\n    clips: [a.mp4]\n"
    )
    assert doc.chapters[0].card is None


def test_the_duration_is_finite_after_loading() -> None:
    card = _card("  duration: 5\n")
    assert card is not None and card.duration is not None and math.isfinite(card.duration)


def test_a_document_without_a_card_hashes_as_before() -> None:
    doc = loads_document("version: 0\nchapters:\n  - name: ''\n    clips: [a.mp4]\n")
    before_cards = {
        "version": 0,
        "metadata": {"title": None, "date": None, "location": None, "description": None},
        "look": {},
        "chapters": [{"name": "", "clips": ["a.mp4"]}],
        "clips": {},
        "ignore": [],
    }
    assert doc.to_dict() == before_cards
    assert "card" not in doc.chapters[0].to_dict()
    assert editorial_hash(doc) == _hash_json(before_cards)


def test_a_document_that_adds_a_card_hashes_differently() -> None:
    plain = loads_document("version: 0\nchapters:\n  - name: ''\n    clips: [a.mp4]\n")
    carded = loads_document(
        "version: 0\nchapters:\n  - name: ''\n    card: {duration: 3}\n    clips: [a.mp4]\n"
    )
    assert editorial_hash(plain) != editorial_hash(carded)
    assert carded.chapters[0].to_dict()["card"] == {"duration": 3.0}


def test_an_empty_card_hashes_like_no_card() -> None:
    plain = loads_document("version: 0\nchapters:\n  - name: ''\n    clips: [a.mp4]\n")
    empty = loads_document(
        "version: 0\nchapters:\n  - name: ''\n    card: {}\n    clips: [a.mp4]\n"
    )
    assert editorial_hash(plain) == editorial_hash(empty)


def test_the_design_document_records_the_card_decision_once() -> None:
    hld = (Path(__file__).resolve().parents[1] / "docs" / "high-level-design.md").read_text(
        encoding="utf-8"
    )
    entries = [line for line in hld.splitlines() if line.startswith("- **D-24")]
    assert len(entries) == 1
    assert "title-card-model" in entries[0]
