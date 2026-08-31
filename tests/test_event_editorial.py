"""Tests for the editorial write operation (D-E1 apply-onto-raw engine op)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from auto_reel_ng.errors import ReelParseError
from auto_reel_ng.event.editorial import REEL_FILENAME, apply_editorial_write
from auto_reel_ng.event.resolution import resolve
from auto_reel_ng.reel.document import ReelDocument
from auto_reel_ng.reel.parser import load_document
from auto_reel_ng.staleness.fingerprint import compute_fingerprint
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
