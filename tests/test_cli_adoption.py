"""Tests for the NEW-clip adoption policy (D-CLI3): seed / adopt / report MISSING.

These operate at the document level with empty placeholder files (the scan only
reads name/extension), so no ffmpeg is involved.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from auto_reel_ng.cli.adoption import REEL_FILENAME, persist, prepare_event
from auto_reel_ng.event import DEFAULT_CLIP_ORDER, ClipOrder, SortMethod
from auto_reel_ng.reel import write_document
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
