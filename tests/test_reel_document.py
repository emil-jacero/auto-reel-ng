"""Tests for the ``ReelDocument`` chapter lookup (chapter-name-rules-engine)."""

from __future__ import annotations

from auto_reel_ng.reel.document import Chapter, ReelDocument

DOCUMENT = ReelDocument(
    chapters=(
        Chapter(name=""),
        Chapter(name="Party"),
        Chapter(name="Straße"),
        Chapter(name="Dag 2"),
    )
)


def test_the_exact_name_is_found() -> None:
    assert DOCUMENT.chapter("Party") is DOCUMENT.chapters[1]


def test_a_case_variant_finds_the_chapter_by_str_casefold() -> None:
    assert DOCUMENT.chapter("party") is DOCUMENT.chapters[1]
    assert DOCUMENT.chapter("PARTY") is DOCUMENT.chapters[1]
    assert DOCUMENT.chapter("STRASSE") is DOCUMENT.chapters[2]  # casefold folds the sharp s


def test_the_exact_name_wins_over_a_case_variant() -> None:
    # Such a document cannot be loaded (names are casefold-unique) but can be built in memory.
    exact = Chapter(name="party")
    other = Chapter(name="Party")
    assert ReelDocument(chapters=(other, exact)).chapter("party") is exact


def test_the_empty_name_finds_only_the_default_chapter() -> None:
    assert DOCUMENT.chapter("") is DOCUMENT.chapters[0]
    assert ReelDocument(chapters=(Chapter(name="Party"),)).chapter("") is None


def test_an_absent_or_padded_name_finds_nothing() -> None:
    assert DOCUMENT.chapter("Reception") is None
    assert DOCUMENT.chapter("Party ") is None
    assert DOCUMENT.chapter(" party") is None
