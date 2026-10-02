"""Tests for the editorial write operation (D-E1 apply-onto-raw engine op)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.errors import EventMetadataError, ReelParseError
from auto_reel_ng.event.discovery import ClipOrder
from auto_reel_ng.event.editorial import REEL_FILENAME, apply_editorial_write
from auto_reel_ng.event.metadata import load_event_document, require_processable
from auto_reel_ng.event.resolution import resolve
from auto_reel_ng.reel.document import ReelDocument
from auto_reel_ng.reel.parser import load_document, loads_document
from auto_reel_ng.staleness.fingerprint import compute_fingerprint, editorial_hash
from auto_reel_ng.staleness.gate import evaluate
from auto_reel_ng.staleness.manifest import write_manifest

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

SIMPLE = """\
version: 0
metadata:
  title: Original
  date: 2024-06-21
  location: Somewhere
chapters:
  - name: ""
    clips:
      - a.mp4
      - b.mp4
  - name: Reception
    clips:
      - Reception/c.mp4
"""


def _write_event(tmp_path: Path, text: str) -> Path:
    event_dir = tmp_path / "event"
    event_dir.mkdir()
    (event_dir / REEL_FILENAME).write_text(text, encoding="utf-8")
    return event_dir


def _desired_from(document: ReelDocument) -> dict:
    """The document's current state as a desired-state mapping (round-trip no-op input)."""
    data = document.to_dict()
    data.pop("version", None)
    return data


# --------------------------------------------------------------------------- #
# 1.2 Comment/key-order preservation
# --------------------------------------------------------------------------- #


def test_hand_authored_comments_survive_title_only_edit(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, HANDWRITTEN)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    desired["metadata"]["title"] = "Midsummer Party"

    apply_editorial_write(event_dir, desired)

    text = (event_dir / REEL_FILENAME).read_text(encoding="utf-8")
    original_lines = HANDWRITTEN.splitlines()
    new_lines = text.splitlines()
    assert len(original_lines) == len(new_lines)

    diffs = [(o, n) for o, n in zip(original_lines, new_lines) if o != n]
    assert len(diffs) == 1
    old_line, new_line = diffs[0]
    assert "title: Midsummer" in old_line
    assert "title: Midsummer Party" in new_line
    assert "# event title" in new_line  # the line's own comment survives the edit


# --------------------------------------------------------------------------- #
# 1.3 Write surface
# --------------------------------------------------------------------------- #


def test_metadata_edit_is_persisted(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    desired["metadata"]["title"] = "Renamed"
    desired["metadata"]["location"] = "Elsewhere"

    result = apply_editorial_write(event_dir, desired)
    assert result.metadata.title == "Renamed"
    assert result.metadata.location == "Elsewhere"

    reloaded = load_document(event_dir / REEL_FILENAME)
    assert reloaded.metadata.title == "Renamed"
    assert reloaded.metadata.location == "Elsewhere"


def test_reorder_within_chapter_is_persisted(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    default_chapter = next(c for c in desired["chapters"] if c["name"] == "")
    default_chapter["clips"] = list(reversed(default_chapter["clips"]))

    apply_editorial_write(event_dir, desired)

    reloaded = load_document(event_dir / REEL_FILENAME)
    chapter = reloaded.chapter("")
    assert chapter is not None
    assert [r.identity for r in chapter.clips] == ["b.mp4", "a.mp4"]


def test_move_clip_across_chapters_is_persisted(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    default_chapter = next(c for c in desired["chapters"] if c["name"] == "")
    reception = next(c for c in desired["chapters"] if c["name"] == "Reception")
    default_chapter["clips"].remove("b.mp4")
    reception["clips"].append("b.mp4")

    apply_editorial_write(event_dir, desired)

    reloaded = load_document(event_dir / REEL_FILENAME)
    default = reloaded.chapter("")
    updated_reception = reloaded.chapter("Reception")
    assert default is not None and updated_reception is not None
    assert [r.identity for r in default.clips] == ["a.mp4"]
    assert [r.identity for r in updated_reception.clips] == ["Reception/c.mp4", "b.mp4"]


def test_look_override_persists_on_document_with_none(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)  # no look section yet
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    desired["look"] = {"font": "Inter", "font_size": 70}

    result = apply_editorial_write(event_dir, desired)
    assert result.look == {"font": "Inter", "font_size": 70}

    reloaded = load_document(event_dir / REEL_FILENAME)
    assert reloaded.look == {"font": "Inter", "font_size": 70}
    assert "look:" in (event_dir / REEL_FILENAME).read_text(encoding="utf-8")

    # ...and resolution layers the persisted override over the project config.yaml
    # defaults (D-2): the event wins key by key, project-only keys carry through.
    plan = resolve(reloaded, look_defaults={"font": "DejaVu Sans", "background": "#101010"})
    assert plan.look == {"font": "Inter", "font_size": 70, "background": "#101010"}


def test_ignore_is_persisted(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    desired["ignore"] = ["junk.mp4"]

    result = apply_editorial_write(event_dir, desired)
    assert result.ignore == ("junk.mp4",)

    reloaded = load_document(event_dir / REEL_FILENAME)
    assert reloaded.ignore == ("junk.mp4",)


# --------------------------------------------------------------------------- #
# 1.4 Round-trip no-op
# --------------------------------------------------------------------------- #


def test_round_trip_noop_is_byte_identical(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, HANDWRITTEN)
    original_text = (event_dir / REEL_FILENAME).read_text(encoding="utf-8")
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))

    apply_editorial_write(event_dir, desired)

    assert (event_dir / REEL_FILENAME).read_text(encoding="utf-8") == original_text


# --------------------------------------------------------------------------- #
# 1.5 Fresh-build fallback
# --------------------------------------------------------------------------- #


def test_fresh_build_fallback_when_no_reel_yaml(tmp_path: Path) -> None:
    event_dir = tmp_path / "event"
    event_dir.mkdir()
    desired = {
        "metadata": {"title": "New Event", "date": date(2024, 6, 21), "location": "Dalarna"},
        "chapters": [{"name": "", "clips": ["a.mp4"]}],
    }

    result = apply_editorial_write(event_dir, desired)
    assert result.metadata.title == "New Event"
    chapter = result.chapter("")
    assert chapter is not None
    assert [r.identity for r in chapter.clips] == ["a.mp4"]

    reloaded = load_document(event_dir / REEL_FILENAME)
    assert reloaded.metadata.title == "New Event"
    text = (event_dir / REEL_FILENAME).read_text(encoding="utf-8")
    assert text.startswith("version: 0")


# --------------------------------------------------------------------------- #
# 1.6 Fail-loud, non-destructive validation
# --------------------------------------------------------------------------- #


def test_invalid_cross_reference_is_rejected_without_writing(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)
    original_text = (event_dir / REEL_FILENAME).read_text(encoding="utf-8")
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    # A clip properties entry with no chapter reference is a dangling reference.
    desired["clips"] = {
        "nowhere.mp4": {"trims": [], "title": None, "rotate": None, "exclude": False}
    }

    with pytest.raises(ReelParseError, match="dangling"):
        apply_editorial_write(event_dir, desired)

    assert (event_dir / REEL_FILENAME).read_text(encoding="utf-8") == original_text


# --------------------------------------------------------------------------- #
# 1.7 MISSING clip is preserved, never rejected or dropped; no probe/filesystem check
# --------------------------------------------------------------------------- #


def test_missing_clip_reference_is_preserved_not_rejected(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    default_chapter = next(c for c in desired["chapters"] if c["name"] == "")
    default_chapter["clips"].append("never_existed.mp4")

    result = apply_editorial_write(event_dir, desired)
    assert "never_existed.mp4" in result.referenced_identities()
    # The operation performed no probe/scan: the phantom reference was never
    # touched on disk, and no file was created for it.
    assert not (event_dir / "never_existed.mp4").exists()


# --------------------------------------------------------------------------- #
# 1.8 No manifest, no job, output untouched; staleness moves to editorial
# --------------------------------------------------------------------------- #


def test_write_creates_no_manifest_and_moves_staleness_to_editorial(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)
    output = tmp_path / "output.mp4"
    output.write_bytes(b"already-rendered")

    document = load_document(event_dir / REEL_FILENAME)
    ffmpeg_version = (7, 1)
    fingerprint = compute_fingerprint(
        document, event_dir=event_dir, look_defaults={}, ffmpeg_version=ffmpeg_version
    )
    write_manifest(event_dir, fingerprint, output=output.name, engine_identity="test")
    assert evaluate(event_dir, output, fingerprint).stale is False

    manifest_path = event_dir / ".auto-reel" / "cache" / "render-manifest.json"
    manifest_before = manifest_path.read_text(encoding="utf-8")

    desired = _desired_from(document)
    desired["metadata"]["title"] = "Changed"
    apply_editorial_write(event_dir, desired)

    # The manifest is untouched (byte-identical) and the output file is untouched.
    assert manifest_path.read_text(encoding="utf-8") == manifest_before
    assert output.read_bytes() == b"already-rendered"

    reloaded = load_document(event_dir / REEL_FILENAME)
    new_fingerprint = compute_fingerprint(
        reloaded, event_dir=event_dir, look_defaults={}, ffmpeg_version=ffmpeg_version
    )
    verdict = evaluate(event_dir, output, new_fingerprint)
    assert verdict.stale is True
    assert "editorial" in verdict.reasons


# --------------------------------------------------------------------------- #
# Resolved-metadata refusal (editorial-client-contract 1.2)
# --------------------------------------------------------------------------- #

TODAY = date(2026, 9, 29)


def _event_folder(tmp_path: Path, name: str, text: Optional[str] = None) -> Path:
    event_dir = tmp_path / name
    event_dir.mkdir(parents=True)
    if text is not None:
        (event_dir / REEL_FILENAME).write_text(text, encoding="utf-8")
    return event_dir


def test_undated_folder_without_a_date_is_refused(tmp_path: Path) -> None:
    event_dir = _event_folder(tmp_path, "Blandat", "version: 0\nmetadata:\n  title: Blandat\n")
    before = (event_dir / REEL_FILENAME).read_bytes()

    with pytest.raises(EventMetadataError, match="no date"):
        apply_editorial_write(event_dir, {"metadata": {"title": "Blandat"}}, today=TODAY)

    assert (event_dir / REEL_FILENAME).read_bytes() == before


def test_future_date_is_refused(tmp_path: Path) -> None:
    event_dir = _event_folder(tmp_path, "Blandat")
    desired = {"metadata": {"title": "Blandat", "date": "2026-09-30"}}

    with pytest.raises(EventMetadataError, match="2026-09-30 is in the future"):
        apply_editorial_write(event_dir, desired, today=TODAY)

    assert not (event_dir / REEL_FILENAME).exists()


def test_authored_date_fixes_a_year_only_folder(tmp_path: Path) -> None:
    event_dir = _event_folder(tmp_path, "2004 - Yngve berättar om skövde")
    desired = {"metadata": {"date": "2004-05-01"}}

    apply_editorial_write(event_dir, desired, today=TODAY)

    document, seeded = load_event_document(event_dir, order=ClipOrder())
    assert not seeded
    assert document.metadata.date == date(2004, 5, 1)
    require_processable(event_dir, document.metadata, today=TODAY)


def test_authored_date_fixes_an_impossible_folder_date(tmp_path: Path) -> None:
    event_dir = _event_folder(tmp_path, "2019-04-31 - Golfträning med Emil - Tjörn")

    apply_editorial_write(event_dir, {"metadata": {"date": "2019-04-30"}}, today=TODAY)

    assert load_document(event_dir / REEL_FILENAME).metadata.date == date(2019, 4, 30)


def test_folder_name_supplies_the_date_a_title_only_state_omits(tmp_path: Path) -> None:
    event_dir = _event_folder(tmp_path, "2024-06-21 - Trip")

    result = apply_editorial_write(event_dir, {"metadata": {"title": "Trip"}}, today=TODAY)

    assert result.metadata.date is None  # the authored document, never the resolution
    assert "date" not in (event_dir / REEL_FILENAME).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# List-entry comments (editorial-chapter-roundtrip)
# --------------------------------------------------------------------------- #

#: The dev library's ``2024-09-01 - Sommarlov`` reel.yaml, byte for byte
#: (``scripts/make_dev_library.py``): one clip entry carries an end-of-line comment.
SOMMARLOV = """\
version: 0
metadata:
  title: Sommarlov
  date: 2024-09-01
chapters:
  - name: ''
    clips:
      - s1710002.mp4
      - s1710004.mp4
      - borttagen.mp4  # MISSING
"""

#: The editorial-write spec's annotated Sommarlov: every kind of list-entry comment.
SOMMARLOV_ANNOTATED = """\
version: 0
metadata:
  title: Sommarlov
  date: 2024-09-01
chapters:
  - name: ''   # the root clips
    clips:
      # the opening shot
      - s1710002.mp4   # first
      # before second
      - s1710004.mp4   # second
      - borttagen.mp4  # MISSING
  # between chapters
  - name: Kvällen
    clips:
      - Kvällen/b.mp4  # sunset
      - Kvällen/c.mp4
ignore:
  - junk.mp4  # never render
"""

#: The Sommarlov metadata alone, for documents that differ only in their lists.
SOMMARLOV_METADATA = "version: 0\nmetadata:\n  title: Sommarlov\n  date: 2024-09-01\n"

#: An ignore list alone: a header comment, an end-of-line comment, a blank line, and
#: a closing comment after the list.
IGNORE_ONLY = """\
version: 0
metadata:
  title: Sommarlov
  date: 2024-09-01
ignore:
  # dismissed by hand
  - junk.mp4  # never render

  - blurry.mp4
# end of reel
"""


#: SOMMARLOV_ANNOTATED's two chapters, each through the comment lines after its clips.
ROOT_CHAPTER = """\
  - name: ''   # the root clips
    clips:
      # the opening shot
      - s1710002.mp4   # first
      # before second
      - s1710004.mp4   # second
      - borttagen.mp4  # MISSING
  # between chapters
"""
KVALLEN_CHAPTER = """\
  - name: Kvällen
    clips:
      - Kvällen/b.mp4  # sunset
      - Kvällen/c.mp4
"""


def _annotated(root: str = ROOT_CHAPTER, kvallen: str = KVALLEN_CHAPTER) -> str:
    """SOMMARLOV_ANNOTATED with its chapters replaced; every other line as authored."""
    chapters = ROOT_CHAPTER + KVALLEN_CHAPTER
    assert SOMMARLOV_ANNOTATED.count(chapters) == 1
    return SOMMARLOV_ANNOTATED.replace(chapters, root + kvallen)


def _without_comments(text: str) -> str:
    """``text`` without its comments and blank lines (no fixture value holds a ``#``)."""
    lines = (line.split("#", 1)[0].rstrip() for line in text.splitlines())
    return "".join(f"{line}\n" for line in lines if line)


def _assert_write(event_dir: Path, desired: dict, expected: str) -> None:
    """Apply ``desired``: the whole file must read ``expected``, and a second apply is a no-op.

    The returned document must hash like the same state written without a comment, so
    comments move neither the fingerprint's editorial component nor the ETag.
    """
    document = apply_editorial_write(event_dir, desired)
    assert (event_dir / REEL_FILENAME).read_text(encoding="utf-8") == expected
    assert editorial_hash(document) == editorial_hash(loads_document(_without_comments(expected)))

    apply_editorial_write(event_dir, desired)
    assert (event_dir / REEL_FILENAME).read_text(encoding="utf-8") == expected


def _annotated_event(tmp_path: Path, text: str = SOMMARLOV_ANNOTATED) -> tuple[Path, dict]:
    event_dir = _write_event(tmp_path, text)
    return event_dir, _desired_from(load_document(event_dir / REEL_FILENAME))


def _chapter_clips(desired: dict, name: str) -> list:
    """The clip list of the desired state's chapter ``name`` (mutable in place)."""
    return next(c for c in desired["chapters"] if c["name"] == name)["clips"]


@pytest.mark.parametrize(
    "text",
    [
        SOMMARLOV,
        SOMMARLOV_ANNOTATED,
        IGNORE_ONLY,
        # A rebuilt list would write this entry unquoted: only leaving it alone keeps it.
        SOMMARLOV.replace("      - s1710004.mp4\n", '      - "s1710004.mp4"\n'),
        SOMMARLOV_METADATA + "ignore: []\n",
        SOMMARLOV_METADATA + "ignore:\n",
        SOMMARLOV_METADATA + "chapters: []\n",
        SOMMARLOV_METADATA + "chapters:\n",
        SOMMARLOV + "  - name: Kvällen\n",
        SOMMARLOV + "  - name: Kvällen\n    clips:\n",
    ],
    ids=[
        "sommarlov",
        "annotated",
        "ignore_only",
        "quoted_entry",
        "empty_ignore",
        "bare_ignore",
        "empty_chapters",
        "bare_chapters",
        "chapter_without_clips",
        "chapter_with_bare_clips",
    ],
)
def test_round_trip_noop_leaves_lists_as_written(tmp_path: Path, text: str) -> None:
    event_dir = _write_event(tmp_path, text)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))

    apply_editorial_write(event_dir, desired)

    assert (event_dir / REEL_FILENAME).read_text(encoding="utf-8") == text


def test_reordering_one_chapter_leaves_the_other_untouched(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SOMMARLOV_ANNOTATED)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    _chapter_clips(desired, "Kvällen").reverse()

    apply_editorial_write(event_dir, desired)

    text = (event_dir / REEL_FILENAME).read_text(encoding="utf-8")
    kvallen = "  - name: Kvällen\n"
    assert text.split(kvallen)[0] == SOMMARLOV_ANNOTATED.split(kvallen)[0]
    chapter = load_document(event_dir / REEL_FILENAME).chapter("Kvällen")
    assert chapter is not None
    assert [r.identity for r in chapter.clips] == ["Kvällen/c.mp4", "Kvällen/b.mp4"]


def test_reorder_moves_each_clips_comments_with_it(tmp_path: Path) -> None:
    event_dir, desired = _annotated_event(tmp_path)
    _chapter_clips(desired, "")[:] = ["borttagen.mp4", "s1710004.mp4", "s1710002.mp4"]

    root = (
        "  - name: ''   # the root clips\n"
        "    clips:\n"
        "      - borttagen.mp4  # MISSING\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "      # the opening shot\n"
        "      - s1710002.mp4   # first\n"
        "  # between chapters\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root))


def test_clip_moved_to_another_chapter_keeps_its_comment(tmp_path: Path) -> None:
    event_dir, desired = _annotated_event(tmp_path)
    _chapter_clips(desired, "").remove("borttagen.mp4")
    _chapter_clips(desired, "Kvällen").insert(0, "borttagen.mp4")

    root = (
        "  - name: ''   # the root clips\n"
        "    clips:\n"
        "      # the opening shot\n"
        "      - s1710002.mp4   # first\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "  # between chapters\n"
    )
    kvallen = (
        "  - name: Kvällen\n"
        "    clips:\n"
        "      - borttagen.mp4  # MISSING\n"
        "      - Kvällen/b.mp4  # sunset\n"
        "      - Kvällen/c.mp4\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root, kvallen=kvallen))


def test_removing_a_clip_drops_only_its_own_comments(tmp_path: Path) -> None:
    event_dir, desired = _annotated_event(tmp_path)
    _chapter_clips(desired, "").remove("s1710002.mp4")

    root = (
        "  - name: ''   # the root clips\n"
        "    clips:\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "      - borttagen.mp4  # MISSING\n"
        "  # between chapters\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root))


def test_added_clip_carries_no_comment(tmp_path: Path) -> None:
    event_dir, desired = _annotated_event(tmp_path)
    _chapter_clips(desired, "").insert(1, "ny.mp4")

    root = (
        "  - name: ''   # the root clips\n"
        "    clips:\n"
        "      # the opening shot\n"
        "      - s1710002.mp4   # first\n"
        "      - ny.mp4\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "      - borttagen.mp4  # MISSING\n"
        "  # between chapters\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root))


def test_comment_after_the_last_clip_stays_at_the_end(tmp_path: Path) -> None:
    event_dir, desired = _annotated_event(tmp_path)
    _chapter_clips(desired, "")[:] = ["borttagen.mp4", "s1710002.mp4", "s1710004.mp4"]

    root = (
        "  - name: ''   # the root clips\n"
        "    clips:\n"
        "      - borttagen.mp4  # MISSING\n"
        "      # the opening shot\n"
        "      - s1710002.mp4   # first\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "  # between chapters\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root))


def test_renamed_chapter_is_written_fresh_without_clip_comments(tmp_path: Path) -> None:
    event_dir, desired = _annotated_event(tmp_path)
    next(c for c in desired["chapters"] if c["name"] == "Kvällen")["name"] = "Natten"

    kvallen = "  - name: Natten\n    clips:\n      - Kvällen/b.mp4\n      - Kvällen/c.mp4\n"
    _assert_write(event_dir, desired, _annotated(kvallen=kvallen))


def test_changed_ignore_list_keeps_its_entries_comments(tmp_path: Path) -> None:
    event_dir, desired = _annotated_event(tmp_path, IGNORE_ONLY)
    desired["ignore"] = ["blurry.mp4", "junk.mp4", "ny.mp4"]

    expected = IGNORE_ONLY.replace(
        "  # dismissed by hand\n  - junk.mp4  # never render\n\n  - blurry.mp4\n",
        "\n  - blurry.mp4\n  # dismissed by hand\n  - junk.mp4  # never render\n  - ny.mp4\n",
    )
    assert expected != IGNORE_ONLY
    _assert_write(event_dir, desired, expected)


def test_emptied_chapter_keeps_the_comment_that_follows_it(tmp_path: Path) -> None:
    event_dir, desired = _annotated_event(tmp_path)
    original = _desired_from(load_document(event_dir / REEL_FILENAME))
    moved = _chapter_clips(desired, "")[:]
    _chapter_clips(desired, "").clear()
    _chapter_clips(desired, "Kvällen")[:0] = moved

    root = "  - name: ''   # the root clips\n    clips: []\n  # between chapters\n"
    kvallen = (
        "  - name: Kvällen\n"
        "    clips:\n"
        "      # the opening shot\n"
        "      - s1710002.mp4   # first\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "      - borttagen.mp4  # MISSING\n"
        "      - Kvällen/b.mp4  # sunset\n"
        "      - Kvällen/c.mp4\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root, kvallen=kvallen))

    # Moving them back restores the file: '# between chapters' now sits between the two
    # chapter entries, where only an unchanged chapter sequence keeps it.
    _assert_write(event_dir, original, SOMMARLOV_ANNOTATED)


def test_commented_clip_moved_into_a_flow_list_turns_it_block_style(tmp_path: Path) -> None:
    flow = "  - name: Kvällen\n    clips: [Kvällen/b.mp4, Kvällen/c.mp4]\n"
    event_dir, desired = _annotated_event(tmp_path, _annotated(kvallen=flow))
    _chapter_clips(desired, "").remove("s1710002.mp4")
    _chapter_clips(desired, "Kvällen").insert(1, "s1710002.mp4")

    root = (
        "  - name: ''   # the root clips\n"
        "    clips:\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "      - borttagen.mp4  # MISSING\n"
        "  # between chapters\n"
    )
    kvallen = (
        "  - name: Kvällen\n"
        "    clips:\n"
        "      - Kvällen/b.mp4\n"
        "      # the opening shot\n"
        "      - s1710002.mp4   # first\n"
        "      - Kvällen/c.mp4\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root, kvallen=kvallen))
    reloaded = load_document(event_dir / REEL_FILENAME)
    assert [c.to_dict() for c in reloaded.chapters] == desired["chapters"]


def test_flow_list_with_no_comment_to_carry_keeps_its_style(tmp_path: Path) -> None:
    """The lines after a flow list follow the comment after its ``]``, and stay there."""
    flow = (
        "  - name: Kvällen\n"
        "    clips: [Kvällen/b.mp4, Kvällen/c.mp4]  # evening\n"
        "# dismissed clips\n"
    )
    event_dir, desired = _annotated_event(tmp_path, _annotated(kvallen=flow))
    _chapter_clips(desired, "Kvällen").reverse()

    reordered = (
        "  - name: Kvällen\n"
        "    clips: [Kvällen/c.mp4, Kvällen/b.mp4]  # evening\n"
        "# dismissed clips\n"
    )
    _assert_write(event_dir, desired, _annotated(kvallen=reordered))


def test_key_line_comment_stays_on_the_key_line(tmp_path: Path) -> None:
    keyed = ROOT_CHAPTER.replace("    clips:\n", "    clips:   # root list\n")
    event_dir, desired = _annotated_event(tmp_path, _annotated(root=keyed))
    original = _desired_from(load_document(event_dir / REEL_FILENAME))
    _chapter_clips(desired, "")[:] = ["borttagen.mp4", "s1710004.mp4", "s1710002.mp4"]

    root = (
        "  - name: ''   # the root clips\n"
        "    clips:   # root list\n"
        "      - borttagen.mp4  # MISSING\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "      # the opening shot\n"
        "      - s1710002.mp4   # first\n"
        "  # between chapters\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root))
    _assert_write(event_dir, original, _annotated(root=keyed))


@pytest.mark.parametrize(
    "kvallen",
    [
        KVALLEN_CHAPTER,
        "  - name: Kvällen\n    clips: [Kvällen/b.mp4, Kvällen/c.mp4]\n",
        "  - name: Kvällen\n    clips: [Kvällen/b.mp4, Kvällen/c.mp4]  # evening\n",
    ],
    ids=["block", "flow", "flow_with_comment"],
)
def test_appended_chapter_keeps_the_lines_between_existing_chapters(
    tmp_path: Path, kvallen: str
) -> None:
    """GUI slice D appends a disk chapter the document does not name; nothing else moves.

    The comment after the last chapter still introduces what follows the chapters.
    """
    flow_root = (
        "  - name: ''   # the root clips\n"
        "    clips: [s1710002.mp4, s1710004.mp4, borttagen.mp4]\n"
        "  # between chapters\n"
    )
    dismissed = "# dismissed clips\n"
    text = _annotated(root=flow_root, kvallen=kvallen + dismissed)
    event_dir, desired = _annotated_event(tmp_path, text)
    desired["chapters"].append({"name": "Natten", "clips": ["Natten/d.mp4"]})

    natten = "  - name: Natten\n    clips:\n      - Natten/d.mp4\n"
    expected = _annotated(root=flow_root, kvallen=kvallen + natten + dismissed)
    _assert_write(event_dir, desired, expected)


def test_non_canonical_entry_counts_as_a_change(tmp_path: Path) -> None:
    """``./s1710002.mp4`` is not its identity as written, so its list is rewritten canonically."""
    text = SOMMARLOV.replace("      - s1710002.mp4\n", "      - ./s1710002.mp4\n")
    assert text != SOMMARLOV
    event_dir = _write_event(tmp_path, text)
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    assert _chapter_clips(desired, "")[0] == "s1710002.mp4"

    _assert_write(event_dir, desired, SOMMARLOV)


def test_emptied_ignore_keeps_the_comment_that_follows_it(tmp_path: Path) -> None:
    lists = "ignore:\n  - j.mp4  # jay\n# how the clips are ordered\nsort:\n  method: filename\n"
    event_dir, desired = _annotated_event(tmp_path, SOMMARLOV_METADATA + lists)
    desired["ignore"] = []

    emptied = "ignore: []\n# how the clips are ordered\nsort:\n  method: filename\n"
    _assert_write(event_dir, desired, SOMMARLOV_METADATA + emptied)


def test_flow_list_keeps_the_comment_above_it(tmp_path: Path) -> None:
    """It stays the list's own header, and tops the list when a commented clip turns it block."""
    flow = (
        "  - name: Kvällen\n"
        "    clips:\n"
        "      # the evening\n"
        "        [Kvällen/b.mp4, Kvällen/c.mp4]\n"
    )
    event_dir, desired = _annotated_event(tmp_path, _annotated(kvallen=flow))
    _chapter_clips(desired, "Kvällen").reverse()

    reordered = flow.replace("[Kvällen/b.mp4, Kvällen/c.mp4]", "[Kvällen/c.mp4, Kvällen/b.mp4]")
    _assert_write(event_dir, desired, _annotated(kvallen=reordered))

    _chapter_clips(desired, "").remove("s1710002.mp4")
    _chapter_clips(desired, "Kvällen").insert(1, "s1710002.mp4")
    root = (
        "  - name: ''   # the root clips\n"
        "    clips:\n"
        "      # before second\n"
        "      - s1710004.mp4   # second\n"
        "      - borttagen.mp4  # MISSING\n"
        "  # between chapters\n"
    )
    kvallen = (
        "  - name: Kvällen\n"
        "    clips:\n"
        "      # the evening\n"
        "      - Kvällen/c.mp4\n"
        "      # the opening shot\n"
        "      - s1710002.mp4   # first\n"
        "      - Kvällen/b.mp4\n"
    )
    _assert_write(event_dir, desired, _annotated(root=root, kvallen=kvallen))


# --------------------------------------------------------------------------- #
# Value validation reaches every writer through build_document
# --------------------------------------------------------------------------- #

IGNORING = """\
version: 0
metadata:
  title: Original
chapters:
  - name: ""
    clips: [a.mp4]
ignore:
  - x.mp4   # first
"""


def test_a_duplicate_ignore_entry_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, IGNORING)
    original = (event_dir / REEL_FILENAME).read_bytes()
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    desired["ignore"] = ["x.mp4", "x.mp4"]

    with pytest.raises(ReelParseError, match="duplicate ignore entry 'x.mp4'"):
        apply_editorial_write(event_dir, desired)

    assert (event_dir / REEL_FILENAME).read_bytes() == original


def test_a_lone_surrogate_title_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    event_dir = _write_event(tmp_path, SIMPLE)
    original = (event_dir / REEL_FILENAME).read_bytes()
    desired = _desired_from(load_document(event_dir / REEL_FILENAME))
    desired["metadata"] = {"title": "Fest \ud800", "date": date(2024, 6, 21)}

    with pytest.raises(ReelParseError, match="metadata.title.*lone surrogate"):
        apply_editorial_write(event_dir, desired)

    assert (event_dir / REEL_FILENAME).read_bytes() == original
