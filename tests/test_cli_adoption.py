"""Tests for the NEW-clip adoption policy (D-CLI3): seed / adopt / report MISSING.

These operate at the document level with empty placeholder files (the scan only
reads name/extension), so no ffmpeg is involved.
"""

from __future__ import annotations

from pathlib import Path

from auto_reel_ng.cli.adoption import REEL_FILENAME, persist, prepare_event
from auto_reel_ng.reel.document import DEFAULT_CHAPTER_NAME


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_seed_on_first_scan(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer - Dalarna"
    _touch(event / "00400.mp4")

    prepared = prepare_event(event)

    assert prepared.seeded is True
    assert prepared.document.metadata.title == "Midsummer"
    assert "00400.mp4" in prepared.document.referenced_identities()
    # prepare_event itself never writes; persistence is a separate, explicit step.
    assert not (event / REEL_FILENAME).exists()


def test_adopt_new_clip_into_default_chapter(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    persist(prepare_event(event))  # seed + write a reel.yaml referencing 00400
    assert (event / REEL_FILENAME).exists()

    _touch(event / "00401.mp4")  # a new clip appears on disk
    prepared = prepare_event(event)

    assert prepared.seeded is False
    assert "00401.mp4" in prepared.adopted
    assert "00401.mp4" in prepared.document.referenced_identities()
    default = prepared.document.chapter(DEFAULT_CHAPTER_NAME)
    assert default is not None
    assert "00401.mp4" in [ref.identity for ref in default.clips]


def test_missing_clip_reported_not_removed(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    persist(prepare_event(event))

    (event / "00400.mp4").unlink()  # still referenced in reel.yaml, gone from disk
    prepared = prepare_event(event)

    assert "00400.mp4" in prepared.reconcile.missing
    assert "00400.mp4" in prepared.document.referenced_identities()  # not removed


def test_scan_mode_does_not_adopt(tmp_path: Path) -> None:
    event = tmp_path / "2024-06-21 - Midsummer"
    _touch(event / "00400.mp4")
    persist(prepare_event(event))
    _touch(event / "00401.mp4")

    prepared = prepare_event(event, adopt=False)

    assert prepared.adopted == ()
    assert "00401.mp4" in prepared.reconcile.new
    assert "00401.mp4" not in prepared.document.referenced_identities()
