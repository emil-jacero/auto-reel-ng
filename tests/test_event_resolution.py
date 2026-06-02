"""Tests for resolving a document into a fully-explicit render plan."""

from __future__ import annotations

import pytest

from auto_reel_ng.errors import ReelError
from auto_reel_ng.event.resolution import resolve
from auto_reel_ng.reel.parser import loads_document

TWO_CHAPTERS = """\
version: 0
look:
  font: Inter
chapters:
  - name: ""
    clips:
      - 00400.mp4
      - 00401.mp4
  - name: Reception
    clips:
      - Reception/00500.mp4
      - Reception/00501.mp4
clips:
  00401.mp4:
    trims:
      - {in: 0, out: 2.0, reason: black}
"""


def test_plan_lists_clips_explicitly_in_document_order() -> None:
    plan = resolve(loads_document(TWO_CHAPTERS))
    assert [c.name for c in plan.chapters] == ["", "Reception"]
    assert [c.identity for c in plan.chapters[0].clips] == ["00400.mp4", "00401.mp4"]
    assert [c.identity for c in plan.chapters[1].clips] == [
        "Reception/00500.mp4",
        "Reception/00501.mp4",
    ]


def test_repeated_resolution_is_identical() -> None:
    doc = loads_document(TWO_CHAPTERS)
    assert resolve(doc) == resolve(doc)


def test_cut_spans_are_carried_into_the_plan() -> None:
    plan = resolve(loads_document(TWO_CHAPTERS))
    clip = plan.chapters[0].clips[1]
    assert clip.identity == "00401.mp4"
    assert [(t.start, t.end, t.reason) for t in clip.cut_spans] == [(0.0, 2.0, "black")]


def test_excluded_clip_is_absent_from_plan_but_kept_in_document() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4, b.mp4]
clips:
  b.mp4:
    exclude: true
"""
    doc = loads_document(text)
    plan = resolve(doc)
    assert [c.identity for c in plan.chapters[0].clips] == ["a.mp4"]
    # Still recorded in the document.
    assert "b.mp4" in doc.clips
    assert doc.chapters[0].clips[1].identity == "b.mp4"


def test_rotate_override_is_applied() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4]
clips:
  a.mp4:
    rotate: 90
"""
    plan = resolve(loads_document(text))
    assert plan.chapters[0].clips[0].rotate == 90


def test_first_clip_is_title_by_default() -> None:
    plan = resolve(loads_document(TWO_CHAPTERS))
    first_chapter = plan.chapters[0]
    assert first_chapter.clips[0].is_title is True
    assert first_chapter.clips[1].is_title is False
    assert first_chapter.title_clip is first_chapter.clips[0]


def test_explicit_title_override_wins() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4, b.mp4, c.mp4]
clips:
  b.mp4:
    title: true
"""
    plan = resolve(loads_document(text))
    clips = plan.chapters[0].clips
    assert clips[0].is_title is False
    assert clips[1].is_title is True
    assert clips[2].is_title is False


def test_title_false_excludes_clip_from_baseline() -> None:
    text = """\
version: 0
chapters:
  - name: ""
    clips: [a.mp4, b.mp4]
clips:
  a.mp4:
    title: false
"""
    plan = resolve(loads_document(text))
    clips = plan.chapters[0].clips
    assert clips[0].is_title is False
    assert clips[1].is_title is True  # baseline skips the title:false clip


def test_default_only_look_key_is_carried_through() -> None:
    plan = resolve(loads_document(TWO_CHAPTERS), look_defaults={"resolution": "1080p"})
    assert plan.look["resolution"] == "1080p"  # default-only key carried
    assert plan.look["font"] == "Inter"  # document key present


def test_document_look_key_overrides_default() -> None:
    plan = resolve(loads_document(TWO_CHAPTERS), look_defaults={"font": "Arial", "fps": 25})
    assert plan.look["font"] == "Inter"  # document wins
    assert plan.look["fps"] == 25  # default-only carried


def test_absent_defaults_are_tolerated() -> None:
    plan = resolve(loads_document(TWO_CHAPTERS), look_defaults=None)
    assert plan.look == {"font": "Inter"}


def test_clip_facts_missing_for_included_clip_fails_loud() -> None:
    doc = loads_document(TWO_CHAPTERS)
    with pytest.raises(ReelError, match="no probed metadata"):
        resolve(doc, clip_facts={})  # empty facts => every included clip is unknown
