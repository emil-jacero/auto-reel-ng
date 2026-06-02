"""Tests for the round-trip writer and the auto-reel legacy importer."""

from __future__ import annotations

from datetime import date

from auto_reel_ng.reel.legacy import import_legacy
from auto_reel_ng.reel.parser import loads_document
from auto_reel_ng.reel.writer import dumps_document, write_document

HANDWRITTEN = """\
# Midsummer 2024 — hand-authored reel
version: 0
metadata:
  title: Midsummer   # event title
  date: 2024-06-21
  location: Dalarna
look:
  font: Inter        # opaque to v0
chapters:
  - name: ""         # default chapter (root clips)
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
    title: true
ignore:
  - junk/IMG_0001.mp4
"""


def test_unchanged_document_round_trips_byte_stable() -> None:
    doc = loads_document(HANDWRITTEN)
    assert dumps_document(doc) == HANDWRITTEN


def test_writer_always_emits_version_zero(tmp_path) -> None:
    doc = loads_document("version: 0\nmetadata:\n  title: X\n")
    out = tmp_path / "reel.yaml"
    write_document(doc, out)
    text = out.read_text(encoding="utf-8")
    assert "version: 0" in text


def test_round_trip_preserves_comments_and_key_order() -> None:
    doc = loads_document(HANDWRITTEN)
    rewritten = dumps_document(doc)
    assert "# Midsummer 2024 — hand-authored reel" in rewritten
    assert "# default chapter (root clips)" in rewritten
    # key order: version precedes metadata precedes chapters
    assert rewritten.index("version:") < rewritten.index("metadata:") < rewritten.index("chapters:")


def test_legacy_metadata_and_title_card_are_mapped() -> None:
    legacy = {
        "metadata": {"title": "Midsummer", "date": date(2024, 6, 21), "location": "Dalarna"},
        "description": "A long summer day.",
        "title_card": {"font": "Inter", "font_size": 70},
    }
    result = import_legacy(legacy)
    doc = result.document

    assert doc.version == 0
    assert doc.metadata.title == "Midsummer"
    assert doc.metadata.date == date(2024, 6, 21)
    assert doc.metadata.location == "Dalarna"
    assert doc.metadata.description == "A long summer day."
    # title_card maps to the opaque look, unchanged.
    assert doc.look["font"] == "Inter"
    assert doc.look["font_size"] == 70
    assert result.unmapped == ()


def test_top_level_title_overrides_metadata_title() -> None:
    legacy = {"metadata": {"title": "Event", "date": date(2024, 1, 1)}, "title": "Override Title"}
    doc = import_legacy(legacy).document
    assert doc.metadata.title == "Override Title"


def test_unmappable_custom_order_is_reported_not_dropped() -> None:
    legacy = {
        "metadata": {"title": "Event"},
        "sort": {"method": "custom", "custom_order": ["b.mp4", "a.mp4"]},
    }
    result = import_legacy(legacy)
    joined = " ".join(result.unmapped)
    assert "custom" in joined
    assert "custom_order" in joined
    # The document is still produced; the drop is surfaced, not silent.
    assert result.document.metadata.title == "Event"


def test_unknown_legacy_key_is_reported() -> None:
    legacy = {"metadata": {"title": "Event"}, "mystery_field": 123}
    result = import_legacy(legacy)
    assert any("mystery_field" in u for u in result.unmapped)


def test_missing_version_routes_to_legacy_import() -> None:
    # No version key => handled as legacy, yielding a v0 document.
    doc = loads_document("metadata:\n  title: Legacy Event\n  date: 2024-06-21\n")
    assert doc.version == 0
    assert doc.metadata.title == "Legacy Event"


def test_seeded_document_serializes_from_typed_model() -> None:
    # A document with no source structure (_data is None) serializes canonically.
    from auto_reel_ng.reel.document import Chapter, ClipRef, Metadata, ReelDocument

    doc = ReelDocument(
        metadata=Metadata(title="Built", date=date(2024, 6, 21)),
        chapters=(Chapter(name="", clips=(ClipRef("00400.mp4"),)),),
    )
    text = dumps_document(doc)
    assert text.startswith("version: 0")
    assert "00400.mp4" in text
    # Re-parsing the serialized form yields an equivalent document.
    assert loads_document(text).referenced_identities() == ("00400.mp4",)
