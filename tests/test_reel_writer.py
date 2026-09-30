"""Tests for the round-trip writer and the auto-reel legacy importer."""

from __future__ import annotations

import os
import stat
from datetime import date

import pytest

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


def test_sort_block_round_trips_byte_stable() -> None:
    text = "version: 0\nsort:\n  method: filename\n  reverse: true  # newest name first\n"
    assert dumps_document(loads_document(text)) == text


def test_fresh_document_emits_its_sort_rule() -> None:
    from types import MappingProxyType

    from auto_reel_ng.reel.document import ClipOrder, ReelDocument, SortMethod

    rule = ClipOrder(
        method=SortMethod.CUSTOM, reverse=False, custom_order=MappingProxyType({"b.mp4": 1})
    )
    text = dumps_document(ReelDocument(sort=rule))
    assert "sort:\n  method: custom\n  reverse: false\n  custom_order:\n    b.mp4: 1\n" in text
    assert loads_document(text).sort == rule


def test_fresh_document_without_sort_omits_it() -> None:
    from auto_reel_ng.reel.document import ReelDocument

    assert "sort" not in dumps_document(ReelDocument())


def test_dated_legacy_title_splits_off_the_date() -> None:
    result = import_legacy({"title": "2025-01-13 - Resa till Gran Canaria"})
    assert result.document.metadata.title == "Resa till Gran Canaria"
    assert result.document.metadata.date == date(2025, 1, 13)
    assert result.unmapped == ()


def test_dated_legacy_title_with_the_same_date_splits() -> None:
    legacy = {"title": "2025-01-13 - Resa", "metadata": {"date": date(2025, 1, 13)}}
    doc = import_legacy(legacy).document
    assert (doc.metadata.title, doc.metadata.date) == ("Resa", date(2025, 1, 13))


def test_dated_legacy_title_with_a_different_date_is_kept_verbatim() -> None:
    legacy = {"title": "2025-01-13 - Resa", "metadata": {"date": date(2025, 1, 14)}}
    doc = import_legacy(legacy).document
    assert (doc.metadata.title, doc.metadata.date) == ("2025-01-13 - Resa", date(2025, 1, 14))


def test_legacy_title_with_an_impossible_date_is_kept_verbatim() -> None:
    doc = import_legacy({"title": "2019-04-31 - X"}).document
    assert (doc.metadata.title, doc.metadata.date) == ("2019-04-31 - X", None)


def test_dated_legacy_title_loads_from_disk_text() -> None:
    doc = loads_document('title: "2025-01-13 - Resa till Gran Canaria"\n')
    assert (doc.metadata.title, doc.metadata.date) == ("Resa till Gran Canaria", date(2025, 1, 13))


def test_legacy_metadata_block_title_is_never_split() -> None:
    doc = import_legacy({"metadata": {"title": "2025-01-13 - Resa"}}).document
    assert (doc.metadata.title, doc.metadata.date) == ("2025-01-13 - Resa", None)


def test_legacy_custom_sort_is_carried() -> None:
    from auto_reel_ng.reel.document import ClipOrder, SortMethod

    legacy = {"sort": {"method": "custom", "custom_order": {"b.mp4": 1}, "reverse": True}}
    result = import_legacy(legacy)
    assert result.document.sort == ClipOrder(
        method=SortMethod.CUSTOM, reverse=True, custom_order={"b.mp4": 1}
    )
    assert not any("sort" in u for u in result.unmapped)


def test_legacy_sort_survives_a_write() -> None:
    doc = loads_document("sort:\n  method: filename\n  reverse: true\n")
    assert loads_document(dumps_document(doc)).sort == doc.sort


def test_unknown_legacy_sort_method_is_reported_and_not_carried() -> None:
    result = import_legacy({"sort": {"method": "random"}})
    assert any("sort.method" in u for u in result.unmapped)
    assert result.document.sort is None


def test_legacy_custom_order_without_custom_is_reported() -> None:
    from auto_reel_ng.reel.document import SortMethod

    result = import_legacy({"sort": {"method": "filename", "custom_order": {"a.mp4": 1}}})
    assert any("sort.custom_order" in u for u in result.unmapped)
    assert result.document.sort is not None
    assert result.document.sort.method is SortMethod.FILENAME


# --------------------------------------------------------------------------- #
# Atomic replacement (editorial-client-contract 1.1)
# --------------------------------------------------------------------------- #

PREVIOUS = "version: 0\nmetadata:\n  title: Before\n"


def _leftovers(folder) -> list:
    return sorted(p.name for p in folder.glob(".reel.yaml.*.tmp"))


def test_successful_write_leaves_no_temporary_file(tmp_path) -> None:
    out = tmp_path / "reel.yaml"
    out.write_text(PREVIOUS, encoding="utf-8")
    write_document(loads_document("version: 0\nmetadata:\n  title: After\n"), out)
    assert "title: After" in out.read_text(encoding="utf-8")
    assert _leftovers(tmp_path) == []


def test_each_write_uses_a_unique_temporary_name(tmp_path, monkeypatch) -> None:
    sources: list = []
    real_replace = os.replace

    def recording_replace(src, dst):  # type: ignore[no-untyped-def]
        sources.append(os.fspath(src))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", recording_replace)
    out = tmp_path / "reel.yaml"
    doc = loads_document(PREVIOUS)
    write_document(doc, out)
    write_document(doc, out)
    assert len(sources) == 2
    assert sources[0] != sources[1]
    assert all(os.path.basename(s).startswith(".reel.yaml.") for s in sources)


def test_failed_write_keeps_previous_document_and_removes_temporary(tmp_path, monkeypatch) -> None:
    out = tmp_path / "reel.yaml"
    out.write_text(PREVIOUS, encoding="utf-8")
    before = out.read_bytes()

    def failing_fsync(fd: int) -> None:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(OSError, match="Input/output error"):
        write_document(loads_document("version: 0\nmetadata:\n  title: After\n"), out)

    assert out.read_bytes() == before
    assert _leftovers(tmp_path) == []


def test_read_only_folder_raises_and_touches_nothing(tmp_path) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    out = tmp_path / "reel.yaml"
    out.write_text(PREVIOUS, encoding="utf-8")
    before = out.read_bytes()
    mode = tmp_path.stat().st_mode
    tmp_path.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(OSError):
            write_document(loads_document("version: 0\nmetadata:\n  title: After\n"), out)
    finally:
        tmp_path.chmod(mode)
    assert out.read_bytes() == before
    assert _leftovers(tmp_path) == []
