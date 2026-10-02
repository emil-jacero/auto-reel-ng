"""Tests for the NEW-clip adoption policy (D-12, amends D-CLI3): seed / adopt / report MISSING.

These operate at the document level with empty placeholder files (the scan only
reads name/extension), so no ffmpeg is involved.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from auto_reel_ng.cli.adoption import REEL_FILENAME, persist, place_disk_clips, prepare_event
from auto_reel_ng.errors import ReconcileError, ReelParseError
from auto_reel_ng.event import DEFAULT_CLIP_ORDER, ClipOrder, SortMethod, scan_event, seed_document
from auto_reel_ng.ingest import get_layout
from auto_reel_ng.reel import load_document, write_document
from auto_reel_ng.reel.document import DEFAULT_CHAPTER_NAME, Chapter, ClipRef, ReelDocument


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_seed_on_first_scan(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer - Dalarna"
    _touch(event / "00400.mp4")

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)

    assert prepared.seeded is True
    assert prepared.document.metadata.title == "Midsummer"
    assert "00400.mp4" in prepared.document.referenced_identities()
    # prepare_event itself never writes; persistence is a separate, explicit step.
    assert not (event / REEL_FILENAME).exists()


def test_adopt_new_clip_into_default_chapter(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    # seed + write a reel.yaml referencing 00400
    persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))
    assert (event / REEL_FILENAME).exists()

    _touch(event / "00401.mp4")  # a new clip appears on disk
    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)

    assert prepared.seeded is False
    assert "00401.mp4" in prepared.adopted
    assert "00401.mp4" in prepared.document.referenced_identities()
    default = prepared.document.chapter(DEFAULT_CHAPTER_NAME)
    assert default is not None
    assert "00401.mp4" in [ref.identity for ref in default.clips]


def test_missing_clip_reported_not_removed(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))

    (event / "00400.mp4").unlink()  # still referenced in reel.yaml, gone from disk
    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)

    assert "00400.mp4" in prepared.reconcile.missing
    assert "00400.mp4" in prepared.document.referenced_identities()  # not removed


def test_scan_mode_does_not_adopt(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))
    _touch(event / "00401.mp4")

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER, adopt=False)

    assert prepared.adopted == ()
    assert "00401.mp4" in prepared.reconcile.new
    assert "00401.mp4" not in prepared.document.referenced_identities()


def _touch_at(path: Path, hour: int) -> None:
    _touch(path)
    stamp = datetime(2024, 6, 21, hour).timestamp()
    os.utime(path, (stamp, stamp))


def _default_clips(event: Path) -> list[str]:
    chapter = prepare_event(event, order=DEFAULT_CLIP_ORDER, adopt=False).document.chapter(
        DEFAULT_CHAPTER_NAME
    )
    assert chapter is not None
    return [ref.identity for ref in chapter.clips]


def test_hand_order_kept_and_new_clips_appended_in_rule_order(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    for name, hour in (("a.mp4", 10), ("b.mp4", 11), ("c.mp4", 12)):
        _touch_at(event / name, hour)
    hand_ordered = Chapter(
        name=DEFAULT_CHAPTER_NAME, clips=tuple(ClipRef(n) for n in ("c.mp4", "a.mp4", "b.mp4"))
    )
    write_document(ReelDocument(chapters=(hand_ordered,)), event / REEL_FILENAME)
    # Two NEW clips whose mtimes contradict their names (and precede the existing ones).
    _touch_at(event / "d.mp4", 9)
    _touch_at(event / "e.mp4", 8)

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)
    persist(prepared)

    assert prepared.adopted == ("e.mp4", "d.mp4")
    assert _default_clips(event) == ["c.mp4", "a.mp4", "b.mp4", "e.mp4", "d.mp4"]


def test_new_clips_appended_in_configured_rule_order(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch_at(event / "a.mp4", 10)
    persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))
    _touch_at(event / "clip10.mp4", 8)
    _touch_at(event / "clip2.mp4", 9)

    persist(prepare_event(event, order=ClipOrder(method=SortMethod.FILENAME)))

    assert _default_clips(event) == ["a.mp4", "clip2.mp4", "clip10.mp4"]


def test_legacy_event_sort_overrides_the_library_rule(tmp_path: Path) -> None:
    legacy = tmp_path / "2024-06-21 - Legacy"
    sibling = tmp_path / "2024-06-21 - Sibling"
    for event in (legacy, sibling):
        _touch_at(event / "b.mp4", 9)
        _touch_at(event / "a.mp4", 10)
    (legacy / REEL_FILENAME).write_text("sort:\n  method: filename\n", encoding="utf-8")

    adopted = prepare_event(legacy, order=DEFAULT_CLIP_ORDER)
    seeded = prepare_event(sibling, order=DEFAULT_CLIP_ORDER)

    assert adopted.seeded is False
    assert adopted.adopted == ("a.mp4", "b.mp4")
    assert seeded.seeded is True
    assert seeded.document.referenced_identities() == ("b.mp4", "a.mp4")


def test_v0_event_sort_orders_new_clips_after_existing_ones(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch_at(event / "z.mp4", 12)
    (event / REEL_FILENAME).write_text(
        'version: 0\nchapters:\n  - name: ""\n    clips:\n      - z.mp4\n'
        "sort:\n  method: filename\n",
        encoding="utf-8",
    )
    _touch_at(event / "clip10.mp4", 8)
    _touch_at(event / "clip2.mp4", 9)

    persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))

    assert _default_clips(event) == ["z.mp4", "clip2.mp4", "clip10.mp4"]
    assert "sort:\n  method: filename\n" in (event / REEL_FILENAME).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Placement by folder (D-12): place_disk_clips, and prepare_event adopting by it
# --------------------------------------------------------------------------- #

TVA_KAPITEL = "2024-08-20 - Två kapitel - Tjörn"

# The `2024-08-20 - Två kapitel - Tjörn` reel.yaml the spec scenarios start from.
TVA_KAPITEL_REEL = """version: 0
metadata:
  title: Två Kapitel
chapters:
- name: ''
  clips:
  - s1710001.mp4
- name: Kvällen
  clips:
  - Kvällen/s1710002.mp4
  - Kvällen/s1710003.mp4
"""

# What `import` writes for a legacy document, or a GUI metadata-only first save.
NO_CHAPTERS_REEL = "version: 0\nmetadata:\n  title: Utan Kapitel\n"


def _event(root: Path, reel: str, clips: dict[str, int]) -> Path:
    """An event folder holding ``clips`` (identity -> mtime hour) and a literal ``reel.yaml``."""
    event = root / TVA_KAPITEL
    for identity, hour in clips.items():
        _touch_at(event / identity, hour)
    (event / REEL_FILENAME).write_text(reel, encoding="utf-8")
    return event


def _place(
    event: Path, identities: tuple[str, ...], order: ClipOrder = DEFAULT_CLIP_ORDER
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    document = load_document(event / REEL_FILENAME)
    return place_disk_clips(document, scan_event(event), identities, event_dir=event, order=order)


def _chapters(document: ReelDocument) -> list[tuple[str, list[str]]]:
    return [
        (chapter.name, [ref.identity for ref in chapter.clips]) for chapter in document.chapters
    ]


def test_place_a_clip_into_the_folder_chapter_the_document_names(tmp_path: Path) -> None:
    clips = {"s1710001.mp4": 9, "Kvällen/s1710002.mp4": 10, "Kvällen/s1710003.mp4": 11}
    event = _event(tmp_path, TVA_KAPITEL_REEL, {**clips, "Kvällen/s1710004.mp4": 12})

    assert _place(event, ("Kvällen/s1710004.mp4",)) == (("Kvällen", ("Kvällen/s1710004.mp4",)),)


def test_place_a_clip_whose_folder_has_no_chapter_into_the_default_chapter(tmp_path: Path) -> None:
    reel = "version: 0\nchapters:\n- name: ''\n  clips:\n  - s1710001.mp4\n"
    event = _event(
        tmp_path, reel, {"s1710001.mp4": 9, "Dag 2/s1710002.mp4": 10, "s1710003.mp4": 11}
    )

    assert _place(event, ("Dag 2/s1710002.mp4",)) == (("", ("Dag 2/s1710002.mp4",)),)
    assert _place(event, ("s1710003.mp4",)) == (("", ("s1710003.mp4",)),)


def test_place_a_document_naming_no_chapters_as_its_seed(tmp_path: Path) -> None:
    clips = {"s1710001.mp4": 9, "Kvällen/s1710003.mp4": 10, "Kvällen/s1710002.mp4": 11}
    event = _event(tmp_path, NO_CHAPTERS_REEL, clips)

    placed = _place(event, tuple(sorted(clips)))

    assert placed == (
        ("", ("s1710001.mp4",)),
        ("Kvällen", ("Kvällen/s1710003.mp4", "Kvällen/s1710002.mp4")),
    )
    seeded = seed_document(event, order=DEFAULT_CLIP_ORDER)
    assert [(name, list(group)) for name, group in placed] == _chapters(seeded)
    assert _place(event, ("Kvällen/s1710002.mp4",)) == (("Kvällen", ("Kvällen/s1710002.mp4",)),)


def test_place_clips_from_two_folders_into_one_chapter_in_rule_order(tmp_path: Path) -> None:
    reel = "version: 0\nchapters:\n- name: Kvällen\n  clips:\n  - Kvällen/a.mp4\n"
    clips = {"Kvällen/a.mp4": 8, "b.mp4": 12, "Dag 2/c.mp4": 11, "Kvällen/d.mp4": 13}
    event = _event(tmp_path, reel, clips)

    assert _place(event, ("b.mp4", "Dag 2/c.mp4")) == (("", ("Dag 2/c.mp4", "b.mp4")),)
    assert _place(event, ("b.mp4", "Dag 2/c.mp4", "Kvällen/d.mp4")) == (
        ("Kvällen", ("Kvällen/d.mp4",)),
        ("", ("Dag 2/c.mp4", "b.mp4")),
    )


def test_place_by_the_documents_own_sort(tmp_path: Path) -> None:
    reel = (
        "version: 0\nchapters:\n- name: Kvällen\n  clips:\n  - Kvällen/a.mp4\n"
        "sort:\n  method: filename\n"
    )
    event = _event(tmp_path, reel, {"Kvällen/a.mp4": 8, "b.mp4": 12, "Dag 2/c.mp4": 11})

    assert _place(event, ("b.mp4", "Dag 2/c.mp4")) == (("", ("b.mp4", "Dag 2/c.mp4")),)


def test_place_a_clip_the_listing_does_not_hold_fails_loud(tmp_path: Path) -> None:
    event = _event(tmp_path, TVA_KAPITEL_REEL, {"s1710001.mp4": 9})

    with pytest.raises(ReconcileError, match="Kvällen/s1710009.mp4"):
        _place(event, ("Kvällen/s1710009.mp4",))


def test_new_clip_joins_its_folders_chapter(tmp_path: Path) -> None:
    clips = {"s1710001.mp4": 9, "Kvällen/s1710002.mp4": 10, "Kvällen/s1710003.mp4": 11}
    event = _event(tmp_path, TVA_KAPITEL_REEL, {**clips, "Kvällen/s1710004.mp4": 12})

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)

    assert prepared.adopted == ("Kvällen/s1710004.mp4",)
    assert _chapters(prepared.authored) == [
        ("", ["s1710001.mp4"]),
        ("Kvällen", ["Kvällen/s1710002.mp4", "Kvällen/s1710003.mp4", "Kvällen/s1710004.mp4"]),
    ]


def test_new_clips_in_a_folder_without_a_chapter_join_the_default_chapter(tmp_path: Path) -> None:
    reel = "version: 0\nchapters:\n- name: ''\n  clips:\n  - s1710001.mp4\n"
    clips = {"s1710001.mp4": 9, "Dag 2/s1710003.mp4": 10, "Dag 2/s1710002.mp4": 11}
    event = _event(tmp_path, reel, clips)

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)
    persist(prepared)

    assert _chapters(load_document(event / REEL_FILENAME)) == [
        ("", ["s1710001.mp4", "Dag 2/s1710003.mp4", "Dag 2/s1710002.mp4"]),
    ]


def test_clips_from_two_folders_enter_the_default_chapter_in_rule_order(tmp_path: Path) -> None:
    reel = "version: 0\nchapters:\n- name: Kvällen\n  clips:\n  - Kvällen/a.mp4\n"
    event = _event(tmp_path, reel, {"Kvällen/a.mp4": 8, "b.mp4": 12, "Dag 2/c.mp4": 11})

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)

    assert prepared.adopted == ("Dag 2/c.mp4", "b.mp4")
    assert _chapters(prepared.authored) == [
        ("Kvällen", ["Kvällen/a.mp4"]),
        ("", ["Dag 2/c.mp4", "b.mp4"]),
    ]


def test_document_naming_no_chapters_is_seeded_like_a_new_event(tmp_path: Path) -> None:
    clips = {"s1710001.mp4": 9, "Kvällen/s1710003.mp4": 10, "Kvällen/s1710002.mp4": 11}
    event = _event(tmp_path, NO_CHAPTERS_REEL, clips)

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)
    persist(prepared)

    seeded = seed_document(event, order=DEFAULT_CLIP_ORDER)
    assert prepared.authored.chapters == seeded.chapters
    assert _chapters(prepared.authored) == [
        ("", ["s1710001.mp4"]),
        ("Kvällen", ["Kvällen/s1710003.mp4", "Kvällen/s1710002.mp4"]),
    ]
    written = (event / REEL_FILENAME).read_text(encoding="utf-8")
    assert written.startswith(NO_CHAPTERS_REEL)  # metadata as written, nothing resolved
    assert "date:" not in written and "location:" not in written


def test_a_clip_adopted_earlier_stays_where_it_is(tmp_path: Path) -> None:
    reel = TVA_KAPITEL_REEL.replace(
        "  - s1710001.mp4\n", "  - s1710001.mp4\n  - Kvällen/s1710004.mp4\n"
    )
    clips = {"s1710001.mp4": 9, "Kvällen/s1710002.mp4": 10, "Kvällen/s1710003.mp4": 11}
    event = _event(tmp_path, reel, {**clips, "Kvällen/s1710004.mp4": 12})
    before = (event / REEL_FILENAME).read_bytes()

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)

    assert prepared.adopted == ()
    assert prepared.changed is False
    assert persist(prepared) is None
    assert (event / REEL_FILENAME).read_bytes() == before


# --------------------------------------------------------------------------- #
# a folder reaches a chapter exactly, then ignoring case (chapter-name-rules-engine)
# --------------------------------------------------------------------------- #

PARTY_REEL = "version: 0\nchapters:\n- name: Party\n  clips:\n  - Party/a.mp4\n"


def test_a_folder_matches_a_chapter_ignoring_case(tmp_path: Path) -> None:
    event = _event(tmp_path, PARTY_REEL, {"Party/a.mp4": 9, "party/b.mp4": 10})

    assert _place(event, ("party/b.mp4",)) == (("Party", ("party/b.mp4",)),)
    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)
    persist(prepared)
    assert prepared.adopted == ("party/b.mp4",)
    assert _chapters(load_document(event / REEL_FILENAME)) == [
        ("Party", ["Party/a.mp4", "party/b.mp4"])
    ]


def test_a_folder_reaches_only_its_one_matching_chapter(tmp_path: Path) -> None:
    reel = "version: 0\nchapters:\n- name: Party\n  clips: []\n- name: PARTY2\n  clips: []\n"
    event = _event(tmp_path, reel, {"Party/a.mp4": 9, "PARTY2/b.mp4": 10})

    assert _place(event, ("Party/a.mp4", "PARTY2/b.mp4")) == (
        ("Party", ("Party/a.mp4",)),
        ("PARTY2", ("PARTY2/b.mp4",)),
    )


def test_a_padded_folder_name_falls_to_the_default_chapter(tmp_path: Path) -> None:
    event = _event(tmp_path, PARTY_REEL, {"Party/a.mp4": 9, "Party /b.mp4": 10})

    prepared = prepare_event(event, order=DEFAULT_CLIP_ORDER)
    persist(prepared)

    assert _chapters(load_document(event / REEL_FILENAME)) == [
        ("Party", ["Party/a.mp4"]),
        ("", ["Party /b.mp4"]),
    ]


def test_the_events_detail_places_a_case_variant_folder_under_its_chapter(tmp_path: Path) -> None:
    from auto_reel_ng.api import events_read

    event = _event(tmp_path, PARTY_REEL, {"Party/a.mp4": 9, "party/b.mp4": 10})
    document, listing, result = events_read._load_for_reconcile(event, DEFAULT_CLIP_ORDER)

    chapters = events_read._build_chapters(document, listing, result, event, DEFAULT_CLIP_ORDER)

    assert [(c.name, [(clip.identity, clip.status) for clip in c.clips]) for c in chapters] == [
        ("Party", [("Party/a.mp4", "active"), ("party/b.mp4", "new")])
    ]


@pytest.mark.parametrize(
    "folders",
    [
        pytest.param(("Party", "party"), id="case-variant"),
        pytest.param(("Party", "Party "), id="trailing-space"),
    ],
)
def test_seeding_refuses_folders_that_make_invalid_chapter_names(
    tmp_path: Path, folders: tuple[str, ...]
) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    for folder in folders:
        _touch(event / folder / "a.mp4")

    with pytest.raises(ReelParseError, match="chapters\\[\\d\\]"):
        persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))

    assert not (event / REEL_FILENAME).exists()


def test_seeding_a_metadata_only_document_refuses_case_variant_folders(tmp_path: Path) -> None:
    event = _event(tmp_path, NO_CHAPTERS_REEL, {"Party/a.mp4": 9, "party/b.mp4": 10})
    before = (event / REEL_FILENAME).read_bytes()

    with pytest.raises(ReelParseError, match="duplicate chapter name"):
        persist(prepare_event(event, order=DEFAULT_CLIP_ORDER))

    assert (event / REEL_FILENAME).read_bytes() == before


# --------------------------------------------------------------------------- #
# a symlinked alias of an event never seeds the shared reel.yaml (layout-alias-dedupe)
# --------------------------------------------------------------------------- #


def _kalas_and_fest(root: Path) -> Path:
    kalas = root / "2024" / "2024-07-20 - Kalas"
    _touch(kalas / "a.mp4")
    (root / "2024" / "2024-07-20 - Fest").symlink_to(kalas, target_is_directory=True)
    return kalas


def _prepare_and_persist_every_event(root: Path) -> None:
    for ref in get_layout("year-event")(root):
        persist(prepare_event(ref.event_dir, order=DEFAULT_CLIP_ORDER))


def test_alias_does_not_seed_its_own_name_into_the_targets_reel_yaml(tmp_path: Path) -> None:
    kalas = _kalas_and_fest(tmp_path)

    _prepare_and_persist_every_event(tmp_path)

    assert load_document(kalas / REEL_FILENAME).metadata.title == "Kalas"


def test_alias_leaves_an_existing_reel_yaml_byte_identical(tmp_path: Path) -> None:
    kalas = _kalas_and_fest(tmp_path)
    _prepare_and_persist_every_event(tmp_path)
    before = (kalas / REEL_FILENAME).read_bytes()

    _prepare_and_persist_every_event(tmp_path)

    assert (kalas / REEL_FILENAME).read_bytes() == before
