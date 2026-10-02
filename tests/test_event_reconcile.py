"""Tests for discovery seeding and the pure disk-against-document reconcile."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.errors import ReconcileError
from auto_reel_ng.event.discovery import (
    ClipOrder,
    FolderNameProblem,
    SortMethod,
    is_reelignored,
    parse_folder_name,
    scan_event,
    seed_document,
)
from auto_reel_ng.event.reconcile import (
    ClipStatus,
    add_clip,
    ignore_clip,
    reconcile,
)
from auto_reel_ng.reel.document import DEFAULT_CHAPTER_NAME, Chapter, ClipRef, ReelDocument


def _touch(path: Path) -> None:
    """Create an empty placeholder file (scan only checks name/extension)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _make_event(tmp_path: Path, name: str = "2024-06-21 - Midsummer - Dalarna") -> Path:
    event = tmp_path / name
    _touch(event / "00400.mp4")
    _touch(event / "00401.mp4")
    _touch(event / "Reception" / "00500.mp4")
    _touch(event / "notes.txt")  # non-video, ignored by the scan
    return event


# --------------------------------------------------------------------------- #
# Seeding (5.1, 5.3)
# --------------------------------------------------------------------------- #


def test_subdirectories_seed_chapters(tmp_path: Path) -> None:
    doc = seed_document(_make_event(tmp_path))
    names = [c.name for c in doc.chapters]
    assert DEFAULT_CHAPTER_NAME in names
    assert "Reception" in names

    default_chapter = doc.chapter(DEFAULT_CHAPTER_NAME)
    assert default_chapter is not None
    assert [r.identity for r in default_chapter.clips] == ["00400.mp4", "00401.mp4"]

    reception = doc.chapter("Reception")
    assert reception is not None
    assert [r.identity for r in reception.clips] == ["Reception/00500.mp4"]


def test_folder_name_seeds_metadata(tmp_path: Path) -> None:
    doc = seed_document(_make_event(tmp_path))
    assert doc.metadata.title == "Midsummer"
    assert doc.metadata.date == date(2024, 6, 21)
    assert doc.metadata.location == "Dalarna"


def test_parse_well_formed_name_has_no_problems() -> None:
    parsed = parse_folder_name("2024-06-21 - Midsummer - Dalarna")
    assert parsed.date == date(2024, 6, 21)
    assert parsed.title == "Midsummer"
    assert parsed.location == "Dalarna"
    assert parsed.problems == ()


def test_parse_impossible_date_keeps_title_and_location() -> None:
    parsed = parse_folder_name("2019-04-31 - Golfträning med Emil - Tjörn")
    assert parsed.date is None
    assert parsed.problems == (FolderNameProblem.IMPOSSIBLE_DATE,)
    assert parsed.raw_date == "2019-04-31"
    assert parsed.title == "Golfträning med Emil"
    assert parsed.location == "Tjörn"


def test_parse_year_only_keeps_title() -> None:
    parsed = parse_folder_name("2004 - Yngve berättar om skövde")
    assert parsed.date is None
    assert parsed.problems == (FolderNameProblem.YEAR_ONLY,)
    assert parsed.raw_date == "2004"
    assert parsed.title == "Yngve Berättar om Skövde"
    assert parsed.location is None


def test_parse_name_without_date_is_a_title() -> None:
    parsed = parse_folder_name("Blandat")
    assert parsed.date is None
    assert parsed.problems == (FolderNameProblem.NO_DATE,)
    assert parsed.title == "Blandat"


def test_parse_date_without_title_states_no_title() -> None:
    parsed = parse_folder_name("2024-06-21 - ")
    assert parsed.date == date(2024, 6, 21)
    assert parsed.title is None
    assert parsed.problems == (FolderNameProblem.NO_TITLE,)


def test_parse_double_space_before_separator_splits_cleanly() -> None:
    parsed = parse_folder_name("Lasse 78 år  - Kungälv")
    assert parsed.title == "Lasse 78 År"
    assert parsed.location == "Kungälv"


@pytest.mark.parametrize(
    ("name", "title"),
    [
        ("2019-04-31 - Golfträning", "Golfträning"),
        ("2004 - Yngve", "Yngve"),
        ("Blandat", "Blandat"),
        ("2024-06-21", None),
    ],
)
def test_seeding_never_fabricates_a_title(tmp_path: Path, name: str, title: Optional[str]) -> None:
    event_dir = tmp_path / name
    event_dir.mkdir()
    assert seed_document(event_dir).metadata.title == title


def test_non_video_files_are_not_scanned(tmp_path: Path) -> None:
    listing = scan_event(_make_event(tmp_path))
    assert "notes.txt" not in listing.identities


# --------------------------------------------------------------------------- #
# A folder the disk will not let us search is not an empty event
# --------------------------------------------------------------------------- #

skip_as_root = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")


@contextmanager
def _mode(path: Path, mode: int) -> Iterator[None]:
    """``path`` at ``mode`` (``0600``: listable, not searchable), restored for cleanup."""
    path.chmod(mode)
    try:
        yield
    finally:
        path.chmod(0o755)


@skip_as_root
def test_an_unsearchable_event_folder_fails_the_scan_and_the_seed(tmp_path: Path) -> None:
    event = _make_event(tmp_path, "2024-06-21 - Fest")
    with _mode(event, 0o600):
        with pytest.raises(PermissionError):
            scan_event(event)
        with pytest.raises(PermissionError):
            seed_document(event)


@skip_as_root
def test_an_unsearchable_chapter_subfolder_fails_the_scan_naming_it(tmp_path: Path) -> None:
    event = _make_event(tmp_path, "2024-06-21 - Fest")
    with _mode(event / "Reception", 0o600):
        with pytest.raises(PermissionError, match="Reception"):
            scan_event(event)


@skip_as_root
def test_a_symlinked_clip_into_an_unsearchable_folder_fails_the_scan(tmp_path: Path) -> None:
    event = _make_event(tmp_path, "2024-06-21 - Fest")
    vault = tmp_path / "vault"
    _touch(vault / "target.mp4")
    (event / "linked.mp4").symlink_to(vault / "target.mp4")
    with _mode(vault, 0o600):
        with pytest.raises(PermissionError, match="linked.mp4"):
            scan_event(event)


def test_entries_the_disk_says_are_absent_are_skipped(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Fest"
    _touch(event / "real.mp4")
    _touch(event / "notes.txt")
    (event / "dangling.mp4").symlink_to(tmp_path / "gone.mp4")
    assert scan_event(event).identities == ("real.mp4",)


@skip_as_root
def test_is_reelignored_stays_lenient_for_the_ingest_walk(tmp_path: Path) -> None:
    event = _make_event(tmp_path, "2024-06-21 - Fest")
    _touch(event / ".reelignore")
    assert is_reelignored(event) is True
    with _mode(event, 0o600):
        assert is_reelignored(event) is False


def test_empty_document_yields_all_new(tmp_path: Path) -> None:
    listing = scan_event(_make_event(tmp_path))
    result = reconcile(listing.identities, None)
    assert set(result.new) == {"00400.mp4", "00401.mp4", "Reception/00500.mp4"}
    assert result.missing == ()
    assert result.active == ()
    assert all(s is ClipStatus.NEW for s in result.classification.values())


# --------------------------------------------------------------------------- #
# Reconcile classification (5.2)
# --------------------------------------------------------------------------- #


def test_reconcile_classifies_new_missing_active_ignored(tmp_path: Path) -> None:
    doc = seed_document(_make_event(tmp_path))
    # Drop a disk clip and add one not referenced; ignore another.
    doc = ignore_clip(doc, "extra.mp4")
    disk = ["00400.mp4", "Reception/00500.mp4", "extra.mp4", "brandnew.mp4"]

    result = reconcile(disk, doc)
    assert result.active == ("00400.mp4", "Reception/00500.mp4")
    assert result.missing == ("00401.mp4",)  # referenced, not on disk
    assert result.new == ("brandnew.mp4",)  # on disk, unreferenced, not ignored
    assert result.ignored == ("extra.mp4",)  # on disk, in ignore


def test_reconcile_does_not_mutate_document(tmp_path: Path) -> None:
    doc = seed_document(_make_event(tmp_path))
    before = doc.to_dict()
    reconcile(["totally_new.mp4"], doc)
    assert doc.to_dict() == before


# --------------------------------------------------------------------------- #
# Apply operations (5.4)
# --------------------------------------------------------------------------- #


def test_add_places_new_clip_into_chapter_without_moving_files(tmp_path: Path) -> None:
    event = _make_event(tmp_path)
    doc = seed_document(event)

    # A clip the document does not yet reference is added to a named chapter.
    updated = add_clip(doc, "late_arrival.mp4", "Reception")

    reception = updated.chapter("Reception")
    assert reception is not None
    assert "late_arrival.mp4" in [r.identity for r in reception.clips]
    # Source files are untouched on disk.
    assert not (event / "late_arrival.mp4").exists()


def test_add_to_missing_chapter_fails(tmp_path: Path) -> None:
    doc = seed_document(_make_event(tmp_path))
    with pytest.raises(ReconcileError, match="does not exist"):
        add_clip(doc, "x.mp4", "NoSuchChapter")


def test_add_already_referenced_clip_fails(tmp_path: Path) -> None:
    doc = seed_document(_make_event(tmp_path))
    with pytest.raises(ReconcileError, match="already referenced"):
        add_clip(doc, "00400.mp4", "Reception")


def test_ignore_records_clip_and_round_trips_to_ignored(tmp_path: Path) -> None:
    doc = seed_document(_make_event(tmp_path))
    updated = ignore_clip(doc, "junk.mp4")
    assert "junk.mp4" in updated.ignore

    # A subsequent reconcile classifies it IGNORED rather than NEW.
    result = reconcile(["junk.mp4"], updated)
    assert result.ignored == ("junk.mp4",)
    assert result.new == ()


def test_ignore_referenced_clip_fails(tmp_path: Path) -> None:
    doc = seed_document(_make_event(tmp_path))
    with pytest.raises(ReconcileError, match="referenced in a chapter"):
        ignore_clip(doc, "00400.mp4")


def test_ignore_is_idempotent(tmp_path: Path) -> None:
    doc = ignore_clip(seed_document(_make_event(tmp_path)), "junk.mp4")
    again = ignore_clip(doc, "junk.mp4")
    assert again.ignore.count("junk.mp4") == 1


# --------------------------------------------------------------------------- #
# Legacy folder conventions: original/, .reelignore, one level deep
# --------------------------------------------------------------------------- #


def _make_converted_event(tmp_path: Path, originals: str = "original") -> Path:
    event = tmp_path / "2017-07-20 - Båttur"
    _touch(event / "00400.mp4")
    _touch(event / "00401.mp4")
    _touch(event / originals / "00400.MTS")
    _touch(event / originals / "00401.MTS")
    return event


def test_originals_folder_is_not_a_chapter(tmp_path: Path) -> None:
    doc = seed_document(_make_converted_event(tmp_path))
    assert [c.name for c in doc.chapters] == [DEFAULT_CHAPTER_NAME]
    default_chapter = doc.chapter(DEFAULT_CHAPTER_NAME)
    assert default_chapter is not None
    assert [r.identity for r in default_chapter.clips] == ["00400.mp4", "00401.mp4"]
    assert reconcile(scan_event(tmp_path / "2017-07-20 - Båttur").identities, doc).new == ()


def test_originals_folder_is_matched_regardless_of_case(tmp_path: Path) -> None:
    listing = scan_event(_make_converted_event(tmp_path, originals="Original"))
    assert listing.identities == ("00400.mp4", "00401.mp4")


def test_reelignored_chapter_is_skipped_and_sibling_kept(tmp_path: Path) -> None:
    event = tmp_path / "2017-07-07 - Verona"
    _touch(event / "2017-07-06" / "00100.mp4")
    _touch(event / "dålig-kvalitet" / "00200.mp4")
    _touch(event / "dålig-kvalitet" / ".reelignore")
    listing = scan_event(event)
    assert listing.by_chapter == (("2017-07-06", ("2017-07-06/00100.mp4",)),)


def test_originals_nested_in_a_chapter_stay_undiscovered(tmp_path: Path) -> None:
    event = tmp_path / "2017-07-07 - Verona"
    _touch(event / "2017-07-10" / "00300.mp4")
    _touch(event / "2017-07-10" / "original" / "00300.MTS")
    assert scan_event(event).identities == ("2017-07-10/00300.mp4",)


def test_directory_named_reelignore_is_not_the_marker(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch(event / "Reception" / "00500.mp4")
    (event / "Reception" / ".reelignore").mkdir()
    assert scan_event(event).identities == ("Reception/00500.mp4",)


def test_document_listing_an_original_reconciles_it_missing(tmp_path: Path) -> None:
    event = _make_converted_event(tmp_path)
    original = event / "original" / "00400.MTS"
    original.write_bytes(b"camera-original")
    doc = ReelDocument(
        chapters=(
            Chapter(name=DEFAULT_CHAPTER_NAME, clips=(ClipRef("00400.mp4"),)),
            Chapter(name="original", clips=(ClipRef("original/00400.MTS"),)),
        )
    )
    before = doc.to_dict()

    result = reconcile(scan_event(event).identities, doc)

    assert result.missing == ("original/00400.MTS",)
    assert result.classification["original/00400.MTS"] is ClipStatus.MISSING
    assert doc.to_dict() == before
    assert original.read_bytes() == b"camera-original"


# --------------------------------------------------------------------------- #
# Clip order (clip-order)
# --------------------------------------------------------------------------- #


def _touch_at(path: Path, when: datetime) -> None:
    """Create a placeholder clip with modification time ``when``."""
    _touch(path)
    stamp = when.timestamp()
    os.utime(path, (stamp, stamp))


def _default_clips(doc: ReelDocument) -> list[str]:
    chapter = doc.chapter(DEFAULT_CHAPTER_NAME)
    assert chapter is not None
    return [r.identity for r in chapter.clips]


def test_datetime_order_interleaves_two_cameras(tmp_path: Path) -> None:
    event = tmp_path / "2024-04-20 - Lasse 80 år"
    _touch_at(event / "S1600003.MP4", datetime(2024, 4, 20, 14, 32))
    _touch_at(event / "P1110550.MP4", datetime(2024, 4, 20, 16, 36))
    _touch_at(event / "S1600005.MP4", datetime(2024, 4, 20, 16, 35))
    assert _default_clips(seed_document(event)) == [
        "S1600003.MP4",
        "S1600005.MP4",
        "P1110550.MP4",
    ]


def test_filename_order_is_natural_and_ignores_case(tmp_path: Path) -> None:
    event = tmp_path / "2022-04-03 - Olika djur"
    for name in ("IMG_4933.mp4", "img_4863.mp4", "clip10.mp4", "clip2.mp4"):
        _touch(event / name)
    doc = seed_document(event, order=ClipOrder(method=SortMethod.FILENAME))
    assert _default_clips(doc) == ["clip2.mp4", "clip10.mp4", "img_4863.mp4", "IMG_4933.mp4"]


def test_equal_mtimes_fall_back_to_filename_order(tmp_path: Path) -> None:
    event = tmp_path / "2024-01-01 - Tie"
    when = datetime(2024, 1, 1, 12, 0)
    for name in ("clip10.mp4", "CLIP2.mp4", "clip1.mp4"):
        _touch_at(event / name, when)
    assert _default_clips(seed_document(event)) == ["clip1.mp4", "CLIP2.mp4", "clip10.mp4"]


@pytest.mark.parametrize("method", list(SortMethod))
def test_reverse_flips_the_order(tmp_path: Path, method: SortMethod) -> None:
    event = tmp_path / "2024-01-01 - Reverse"
    _touch_at(event / "a.mp4", datetime(2024, 1, 1, 10, 0))
    _touch_at(event / "b.mp4", datetime(2024, 1, 1, 11, 0))
    _touch_at(event / "c.mp4", datetime(2024, 1, 1, 12, 0))
    forward = _default_clips(seed_document(event, order=ClipOrder(method=method)))
    backward = _default_clips(seed_document(event, order=ClipOrder(method=method, reverse=True)))
    assert forward == ["a.mp4", "b.mp4", "c.mp4"]
    assert backward == list(reversed(forward))


def test_clip_order_keeps_chapter_order(tmp_path: Path) -> None:
    event = tmp_path / "2024-01-01 - Chapters"
    _touch_at(event / "Zeta" / "z.mp4", datetime(2024, 1, 1, 9, 0))
    _touch_at(event / "Alpha" / "b.mp4", datetime(2024, 1, 1, 11, 0))
    _touch_at(event / "Alpha" / "a.mp4", datetime(2024, 1, 1, 12, 0))
    _touch_at(event / "root.mp4", datetime(2024, 1, 1, 13, 0))
    doc = seed_document(event)
    assert [c.name for c in doc.chapters] == [DEFAULT_CHAPTER_NAME, "Alpha", "Zeta"]
    alpha = doc.chapter("Alpha")
    assert alpha is not None
    assert [r.identity for r in alpha.clips] == ["Alpha/b.mp4", "Alpha/a.mp4"]


def _custom(order: dict[str, int], *, reverse: bool = False) -> ClipOrder:
    return ClipOrder(method=SortMethod.CUSTOM, reverse=reverse, custom_order=order)


def test_custom_order_places_listed_clips_first(tmp_path: Path) -> None:
    event = tmp_path / "2024-01-01 - Custom"
    for name in ("d.mp4", "c.mp4", "b.mp4", "a.mp4"):
        _touch(event / name)
    doc = seed_document(event, order=_custom({"c.mp4": 1, "a.mp4": 2}))
    assert _default_clips(doc) == ["c.mp4", "a.mp4", "b.mp4", "d.mp4"]


def test_custom_order_reverse_flips_it(tmp_path: Path) -> None:
    event = tmp_path / "2024-01-01 - Custom"
    for name in ("d.mp4", "c.mp4", "b.mp4", "a.mp4"):
        _touch(event / name)
    doc = seed_document(event, order=_custom({"c.mp4": 1, "a.mp4": 2}, reverse=True))
    assert _default_clips(doc) == ["d.mp4", "b.mp4", "a.mp4", "c.mp4"]


def test_custom_order_keys_on_the_file_name_per_chapter(tmp_path: Path) -> None:
    event = tmp_path / "2024-01-01 - Custom"
    for name in ("x/a.mp4", "x/b.mp4", "b.mp4", "a.mp4"):
        _touch(event / name)
    doc = seed_document(event, order=_custom({"b.mp4": 1, "a.mp4": 1}))
    # Equal positions fall back to the filename order; each chapter is ordered alone.
    assert _default_clips(doc) == ["a.mp4", "b.mp4"]
    chapter = doc.chapter("x")
    assert chapter is not None
    assert [r.identity for r in chapter.clips] == ["x/a.mp4", "x/b.mp4"]
