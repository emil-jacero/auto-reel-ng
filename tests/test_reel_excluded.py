"""The one exclusion rule (reel/document.py ``is_excluded``)."""

from __future__ import annotations

from auto_reel_ng.reel import ClipProperties, is_excluded


def test_only_a_clip_marked_exclude_is_excluded() -> None:
    clips = {"a.mp4": ClipProperties(exclude=True), "b.mp4": ClipProperties()}

    assert is_excluded(clips, "a.mp4") is True
    assert is_excluded(clips, "b.mp4") is False
    assert is_excluded(clips, "unlisted.mp4") is False
    assert is_excluded({}, "a.mp4") is False
