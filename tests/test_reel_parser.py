"""Tests for the fail-loud v0 ``reel.yaml`` parser/validator."""

from __future__ import annotations

from datetime import date

import pytest

from auto_reel_ng.errors import ReelError, ReelParseError
from auto_reel_ng.reel.parser import loads_document

VALID_DOC = """\
version: 0
metadata:
  title: Midsummer
  date: 2024-06-21
  location: Dalarna
  description: A long summer day.
look:
  font: Inter
  unknown_future_key: 42
chapters:
  - name: ""
    clips:
      - 00400.mp4
      - 00401.mp4
  - name: Reception
    clips:
      - Reception/00400.mp4
clips:
  00400.mp4:
    trims:
      - {in: 0, out: 3.2, reason: black}
      - {in: 58.1, out: 60.0, reason: freeze}
    title: true
  Reception/00400.mp4:
    exclude: true
    rotate: 90
ignore:
  - junk/IMG_0001.mp4
"""


def test_valid_document_parses_to_expected_model() -> None:
    doc = loads_document(VALID_DOC)

    assert doc.version == 0
    assert doc.metadata.title == "Midsummer"
    assert doc.metadata.date == date(2024, 6, 21)
    assert doc.metadata.location == "Dalarna"
    assert doc.metadata.description == "A long summer day."

    # look is carried opaquely, including a field v0 does not model.
    assert doc.look["font"] == "Inter"
    assert doc.look["unknown_future_key"] == 42

    # Chapters keep document order and reference identities only.
    assert [c.name for c in doc.chapters] == ["", "Reception"]
    assert [r.identity for r in doc.chapters[0].clips] == ["00400.mp4", "00401.mp4"]
    assert [r.identity for r in doc.chapters[1].clips] == ["Reception/00400.mp4"]

    # Properties live in the clips map keyed by the same identity.
    props = doc.clips["00400.mp4"]
    assert props.title is True
    assert [(t.start, t.end, t.reason) for t in props.trims] == [
        (0.0, 3.2, "black"),
        (58.1, 60.0, "freeze"),
    ]
    reception = doc.clips["Reception/00400.mp4"]
    assert reception.exclude is True
    assert reception.rotate == 90

    assert doc.ignore == ("junk/IMG_0001.mp4",)


def test_properties_survive_a_reorder() -> None:
    # The same clip ("a.mp4") with the same `clips` entry, but moved to a different
    # chapter and position. Because properties are keyed by identity (D-B), the
    # property record is unaffected by where the clip is referenced.
    before = loads_document("""\
version: 0
chapters:
  - name: ""
    clips: [a.mp4, b.mp4]
clips:
  a.mp4:
    trims:
      - {in: 0, out: 2.0, reason: black}
""")
    after = loads_document("""\
version: 0
chapters:
  - name: ""
    clips: [b.mp4]
  - name: Reception
    clips: [a.mp4]
clips:
  a.mp4:
    trims:
      - {in: 0, out: 2.0, reason: black}
""")
    # The clip's position genuinely changed (default chapter -> Reception).
    assert before.chapters[0].clips[0].identity == "a.mp4"
    assert after.chapters[1].clips[0].identity == "a.mp4"
    # ...but its properties record is identical and still carries the trims.
    assert before.clips["a.mp4"] == after.clips["a.mp4"]
    assert [(t.start, t.end, t.reason) for t in after.clips["a.mp4"].trims] == [(0.0, 2.0, "black")]


def test_same_basename_in_different_subdirs_are_distinct() -> None:
    text = """\
version: 0
chapters:
  - name: Reception
    clips: [Reception/00400.mp4]
  - name: Speeches
    clips: [Speeches/00400.mp4]
"""
    doc = loads_document(text)
    identities = doc.referenced_identities()
    assert identities == ("Reception/00400.mp4", "Speeches/00400.mp4")
    assert len(set(identities)) == 2


def test_unknown_version_is_rejected() -> None:
    with pytest.raises(ReelParseError, match="unsupported version"):
        loads_document("version: 99\n")


def test_invalid_trim_out_le_in_is_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
clips:
  a.mp4:
    trims:
      - {in: 5.0, out: 5.0}
"""
    with pytest.raises(ReelParseError) as exc:
        loads_document(text)
    assert "a.mp4" in str(exc.value)
    assert "out" in str(exc.value)


def test_negative_time_is_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
clips:
  a.mp4:
    trims:
      - {in: -1.0, out: 2.0}
"""
    with pytest.raises(ReelParseError, match="non-negative"):
        loads_document(text)


def test_dangling_clip_properties_are_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
clips:
  b.mp4:
    title: true
"""
    with pytest.raises(ReelParseError, match="dangling"):
        loads_document(text)


def test_duplicate_identity_is_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
  - name: Two
    clips: [a.mp4]
"""
    with pytest.raises(ReelParseError, match="duplicate clip reference"):
        loads_document(text)


def test_ignore_conflicting_with_structure_is_rejected() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
ignore:
  - a.mp4
"""
    with pytest.raises(ReelParseError, match="both referenced"):
        loads_document(text)


def test_malformed_yaml_is_rejected() -> None:
    with pytest.raises(ReelParseError, match="malformed YAML"):
        loads_document("version: 0\n  bad: : :\n")


def test_reel_parse_error_is_a_reel_error() -> None:
    assert issubclass(ReelParseError, ReelError)


def test_sort_rule_loads() -> None:
    from auto_reel_ng.reel.document import ClipOrder, SortMethod

    doc = loads_document("version: 0\nsort:\n  method: filename\n  reverse: true\n")
    assert doc.sort == ClipOrder(method=SortMethod.FILENAME, reverse=True)


def test_sort_is_optional() -> None:
    assert loads_document("version: 0\n").sort is None


def test_custom_sort_with_custom_order_loads() -> None:
    from auto_reel_ng.reel.document import SortMethod

    doc = loads_document("version: 0\nsort:\n  method: custom\n  custom_order: {a.mp4: 2}\n")
    assert doc.sort is not None
    assert doc.sort.method is SortMethod.CUSTOM
    assert dict(doc.sort.custom_order) == {"a.mp4": 2}


@pytest.mark.parametrize(
    ("sort", "field"),
    [
        ("{method: shuffle}", "sort.method"),
        ("{reverse: 1}", "sort.reverse"),
        ("{custom_order: {a.mp4: 1}}", "sort.custom_order"),
        ("{method: filename, custom_order: {a.mp4: 1}}", "sort.custom_order"),
        ("{method: custom, custom_order: {a.mp4: first}}", "sort.custom_order"),
        ("{method: custom, custom_order: [a.mp4]}", "sort.custom_order"),
        ("[filename]", "sort"),
    ],
)
def test_malformed_sort_fails_loud_naming_the_field(sort: str, field: str) -> None:
    with pytest.raises(ReelParseError, match=field.replace(".", r"\.")):
        loads_document(f"version: 0\nsort: {sort}\n")
