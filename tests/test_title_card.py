"""Title-card tests: config, content, producer seam, decorator, synthetic encode.

The pure layers (config parsing, text composition, producer registry, the title
decorator, and the synthetic normalize command) are golden-tested without a GPU
or fonts, matching the render layer's style. The Cairo+Pango renderer and the
full end-to-end render are gated behind the ``has_fonts`` fixture (and a real CPU
ffmpeg) so the suite passes on a host lacking the system libraries.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.accel import detect_capabilities, select_profile
from auto_reel_ng.accel.models import AcceleratorCapabilities, Device, Vendor
from auto_reel_ng.accel.profiles import CPUProfile, NvencProfile, QsvProfile, VaapiProfile
from auto_reel_ng.errors import FontResolutionError, RenderError, TitleCardError
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.event.resolution import resolve
from auto_reel_ng.probe import probe_media
from auto_reel_ng.probe.metadata import AudioStream, ClipMetadata
from auto_reel_ng.reel.card import ChapterCard
from auto_reel_ng.reel.document import Chapter, ClipRef, Metadata, ReelDocument, Trim
from auto_reel_ng.render import (
    ProducedSegment,
    RenderOptions,
    Segment,
    TargetSpec,
    apply_decorators,
    build_segments,
    build_synthetic_normalize_command,
    get_producer,
    register_producer,
    render_movie,
    resolve_decorator_names,
    title_cards_state,
)
from auto_reel_ng.render.title import (
    TitleCardConfig,
    TitleCardContent,
    TitleCardRequest,
    compose_content,
    parse_title_card_config,
    registered_families,
)
from auto_reel_ng.render.title import render as card_render
from auto_reel_ng.render.title import resolve_card, resolve_card_config, title_card_lines
from auto_reel_ng.render.title.decorator import TITLE_PRODUCER

# --------------------------------------------------------------------------- #
# Fixtures / factories (mirrors tests/test_render.py)                         #
# --------------------------------------------------------------------------- #


def _amd_profile() -> VaapiProfile:
    return VaapiProfile(
        AcceleratorCapabilities(
            vendor=Vendor.AMD,
            usable=True,
            device=Device(
                id="pci-0000:03:00.0",
                vendor=Vendor.AMD,
                name="RX 9070 XT",
                render_node="/dev/dri/renderD128",
            ),
            pad_filter="pad_vaapi",
            can_overlay_hw=False,
            can_tonemap_hw=False,
            usable_encoders={"h264": "h264_vaapi", "hevc": "hevc_vaapi", "av1": "av1_vaapi"},
            decode_method="vaapi",
        )
    )


def _target(**overrides: object) -> TargetSpec:
    base: dict[str, object] = dict(
        width=1920,
        height=1080,
        fps=30.0,
        video_codec="h264",
        video_encoder="h264_vaapi",
        pix_fmt="yuv420p",
        sample_aspect_ratio="1:1",
        fill_color="black",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
    )
    base.update(overrides)
    return TargetSpec(**base)  # type: ignore[arg-type]


def _subseq(haystack: tuple[str, ...], needle: list[str]) -> bool:
    n = len(needle)
    return any(list(haystack[i : i + n]) == needle for i in range(len(haystack) - n + 1))


def _title_segment(**overrides: object) -> Segment:
    base: dict[str, object] = dict(chapter="", producer=TITLE_PRODUCER, duration=7.0)
    base.update(overrides)
    return Segment(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 2. Title-card config                                                        #
# --------------------------------------------------------------------------- #


def test_defaults_applied_when_title_card_silent() -> None:
    config = parse_title_card_config(None)
    assert config.duration == 7.0
    assert (config.fade_in, config.fade_out) == (2.0, 2.0)
    assert config.font_family is None
    assert config.resolved_family == "DejaVu Sans"


def test_partial_config_keeps_defaults_for_absent_fields() -> None:
    config = parse_title_card_config({"duration": 5.0, "font_family": "Inter"})
    assert config.duration == 5.0
    assert config.font_family == "Inter"
    assert config.fade_in == 2.0  # untouched default


def test_registered_family_is_canonicalised_ignoring_case() -> None:
    config = parse_title_card_config({"font_family": "barlow condensed"})
    assert config.font_family == "Barlow Condensed"
    assert config.resolved_family == "Barlow Condensed"


def test_unregistered_family_is_refused_naming_field_value_and_choices() -> None:
    with pytest.raises(TitleCardError) as excinfo:
        parse_title_card_config({"font_family": "Papyrus"})
    message = str(excinfo.value)
    assert "look.title_card.font_family" in message
    assert "'Papyrus'" in message
    for family in registered_families():
        assert family in message
    assert len(registered_families()) == 9


def test_null_family_means_the_default() -> None:
    config = parse_title_card_config({"font_family": None})
    assert config.font_family is None
    assert config.resolved_family == "DejaVu Sans"


def test_non_string_family_is_still_a_type_error() -> None:
    with pytest.raises(TitleCardError, match="must be a str"):
        parse_title_card_config({"font_family": 12})


def test_fades_clamped_to_duration() -> None:
    config = parse_title_card_config({"duration": 4.0, "fade_in": 3.0, "fade_out": 3.0})
    assert config.fade_in + config.fade_out == pytest.approx(4.0)
    assert config.fade_in == pytest.approx(2.0) and config.fade_out == pytest.approx(2.0)


def test_malformed_value_fails_loud_naming_field() -> None:
    with pytest.raises(TitleCardError, match=r"look\.title_card\.duration"):
        parse_title_card_config({"duration": "soon"})
    with pytest.raises(TitleCardError, match=r"look\.title_card\.title_font_size"):
        parse_title_card_config({"title_font_size": "big"})
    with pytest.raises(TitleCardError, match=r"position"):
        parse_title_card_config({"position": "sideways"})


def test_config_to_dict_round_trips_fields() -> None:
    config = parse_title_card_config({"duration": 6.0})
    assert config.to_dict()["duration"] == 6.0


# --------------------------------------------------------------------------- #
# 3. Content composition (structural, no fonts)                               #
# --------------------------------------------------------------------------- #


def _opening_plan(**card: object) -> RenderPlan:
    """A plan whose default chapter has the given ``card`` overrides and full event metadata."""
    return RenderPlan(
        metadata=Metadata(
            title="Midsommar",
            date=date(2024, 6, 21),
            location="Dalarna",
            description="Familjen",
        ),
        chapters=(ResolvedChapter(name="", clips=(), card=ChapterCard(**card) if card else None),),
    )


def test_card_lines_are_the_heading_then_the_subtitle() -> None:
    lines = title_card_lines(TitleCardContent(heading="Midsommar", subtitle="Hos mormor"))
    assert lines == ["Midsommar", "Hos mormor"]


def test_an_empty_subtitle_gives_one_line() -> None:
    assert title_card_lines(TitleCardContent(heading="Midsommar")) == ["Midsommar"]
    assert title_card_lines(TitleCardContent(heading="Midsommar", subtitle="")) == ["Midsommar"]


def test_opening_card_shows_the_title_only_not_date_place_or_description() -> None:
    plan = _opening_plan()
    content = compose_content(plan, plan.chapters[0])
    assert content == TitleCardContent(heading="Midsommar", subtitle="")
    lines = title_card_lines(content)
    assert lines == ["Midsommar"]
    assert not any("2024" in line or "Plats" in line or "Familjen" in line for line in lines)


def test_opening_card_carries_a_free_text_subtitle() -> None:
    plan = _opening_plan(subtitle="Hos mormor")
    content = compose_content(plan, plan.chapters[0])
    assert (content.heading, content.subtitle) == ("Midsommar", "Hos mormor")
    assert title_card_lines(content) == ["Midsommar", "Hos mormor"]


def test_named_chapter_card_uses_the_chapter_name_and_no_subtitle() -> None:
    plan = RenderPlan(
        metadata=Metadata(title="Midsommar", location="Dalarna"),
        chapters=(ResolvedChapter(name="Reception", clips=()),),
    )
    content = compose_content(plan, plan.chapters[0])
    assert content == TitleCardContent(heading="Reception", subtitle="")


def test_a_card_title_overrides_the_heading_without_renaming_the_chapter() -> None:
    plan = RenderPlan(
        metadata=Metadata(title="Midsommar"),
        chapters=(
            ResolvedChapter(name="Reception", clips=(), card=ChapterCard(title="Mottagningen")),
        ),
    )
    chapter = plan.chapters[0]
    assert compose_content(plan, chapter).heading == "Mottagningen"
    assert chapter.name == "Reception"


def test_a_card_with_no_heading_fails_loud_naming_the_chapter() -> None:
    plan = RenderPlan(chapters=(ResolvedChapter(name="", clips=()),))
    with pytest.raises(TitleCardError, match="default chapter"):
        compose_content(plan, plan.chapters[0])
    blank = RenderPlan(
        metadata=Metadata(title="  "), chapters=(ResolvedChapter(name="", clips=()),)
    )
    with pytest.raises(TitleCardError, match="no heading"):
        compose_content(blank, blank.chapters[0])


# --------------------------------------------------------------------------- #
# 3b. A card's effective style (defaults < look.title_card < card)            #
# --------------------------------------------------------------------------- #


def test_defaults_event_style_and_card_compose_in_order() -> None:
    look = {"title_font_size": 80, "text_color": "#CCCCCC", "position": "top"}
    card = ChapterCard(text_color="#FFD700", duration=3.0)
    config = resolve_card_config(look, card)
    assert config.title_font_size == 80  # the event-wide layer over the default 96
    assert config.text_color == "#FFD700"  # the card over the event-wide layer
    assert config.position == "top"
    assert config.subtitle_font_size == 48  # untouched default
    assert config.duration == 3.0
    plain = resolve_card_config(look, None)
    assert (plain.title_font_size, plain.text_color, plain.duration) == (80, "#CCCCCC", 7.0)


def test_a_short_card_clamps_the_default_fades_once() -> None:
    config = resolve_card_config(None, ChapterCard(duration=1.0))
    assert (config.fade_in, config.fade_out) == (pytest.approx(0.5), pytest.approx(0.5))
    assert config.fade_in + config.fade_out <= 1.0 + 1e-9


def test_a_longer_card_is_not_left_with_fades_shrunk_for_the_event_wide_duration() -> None:
    look = {"duration": 3.0}  # the default 2 s fades would clamp to 1.5 s each at 3 s
    assert resolve_card_config(look, None).fade_in == pytest.approx(1.5)
    config = resolve_card_config(look, ChapterCard(duration=10.0))
    assert (config.fade_in, config.fade_out) == (2.0, 2.0)


def test_the_event_wide_style_is_not_mutated_by_a_card() -> None:
    look = {"duration": 3.0}
    resolve_card_config(look, ChapterCard(duration=10.0, text_color="#FFD700"))
    assert look == {"duration": 3.0}


def test_background_defaults_to_black_and_video_parses() -> None:
    assert parse_title_card_config(None).background == "black"
    assert parse_title_card_config({"background": "video"}).background == "video"
    assert resolve_card_config(None, ChapterCard(background="video")).background == "video"
    assert (
        resolve_card_config({"background": "video"}, ChapterCard(background="black")).background
        == "black"
    )


def test_an_unknown_background_fails_loud_naming_the_field_and_the_allowed_values() -> None:
    with pytest.raises(TitleCardError) as caught:
        parse_title_card_config({"background": "transparent"})
    message = str(caught.value)
    assert "look.title_card.background" in message and "black" in message and "video" in message
    with pytest.raises(TitleCardError, match=r"look\.title_card\.background"):
        resolve_card_config({"background": "transparent"}, None)


def test_resolve_card_config_refuses_a_non_mapping_event_style() -> None:
    with pytest.raises(TitleCardError, match="must be a mapping"):
        resolve_card_config(["duration", 3], None)  # type: ignore[arg-type]


def test_resolution_reads_no_media(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("resolve_card must not start a process or write an image")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(card_render, "render_title_card", forbidden)
    plan = _opening_plan(subtitle="Hos mormor", duration=4.0)
    request = resolve_card(plan, plan.chapters[0])
    assert request.config.duration == 4.0
    assert request.content == TitleCardContent(heading="Midsommar", subtitle="Hos mormor")


# --------------------------------------------------------------------------- #
# 4. Producer seam                                                            #
# --------------------------------------------------------------------------- #


def test_producer_resolved_by_name() -> None:
    assert get_producer(TITLE_PRODUCER) is not None


def test_unknown_producer_fails_loud() -> None:
    with pytest.raises(RenderError, match=r"unknown segment producer 'bogus'"):
        get_producer("bogus")


def test_new_producer_registered_without_core_changes() -> None:
    # The registry is generic: a producer registered under a fresh name resolves
    # by that name and materializes a segment, with no change to the segment or
    # normalize core. Restore the registry afterwards so the suite stays isolated.
    from auto_reel_ng.render import producers as producers_module

    def _dummy(segment: Segment, target: TargetSpec, dest: Path) -> ProducedSegment:
        del segment, target  # a stand-in producer needs neither for this test
        return ProducedSegment(image_path=dest, duration=2.0, fade_in=0.1, fade_out=0.1)

    assert "intro" not in producers_module._REGISTRY  # truly a new name
    register_producer("intro", _dummy)
    try:
        resolved = get_producer("intro")
        assert resolved is _dummy
        produced = resolved(
            Segment(chapter="", producer="intro", duration=2.0),
            _target(width=320, height=240),
            Path("/t/intro.png"),
        )
        assert produced.image_path == Path("/t/intro.png") and produced.duration == 2.0
    finally:
        del producers_module._REGISTRY["intro"]


def test_title_producer_requires_request_payload() -> None:
    producer = get_producer(TITLE_PRODUCER)
    with pytest.raises(TitleCardError, match="TitleCardRequest"):
        producer(_title_segment(producer_config=None), _target(), Path("/t/card.png"))


@pytest.mark.has_fonts
def test_title_producer_yields_image_duration_and_fades(has_fonts: None, tmp_path: Path) -> None:
    config = parse_title_card_config({"duration": 3.0, "fade_in": 0.5, "fade_out": 0.5})
    content = TitleCardContent(heading="Midsommar", subtitle="Hos mormor")
    segment = _title_segment(
        duration=3.0, producer_config=TitleCardRequest(config=config, content=content)
    )
    producer = get_producer(TITLE_PRODUCER)
    dest = tmp_path / "card.png"
    produced = producer(segment, _target(width=320, height=240), dest)
    assert produced.image_path == dest and dest.exists()
    assert produced.duration == 3.0
    assert (produced.fade_in, produced.fade_out) == (0.5, 0.5)


# --------------------------------------------------------------------------- #
# 5. Title decorator (inserter)                                               #
# --------------------------------------------------------------------------- #


def _plan(look: dict, *chapters: ResolvedChapter) -> RenderPlan:
    return RenderPlan(
        metadata=Metadata(title="Movie", date=date(2024, 6, 21), location="Home"),
        look=look,
        chapters=chapters,
    )


def test_title_segment_inserted_before_default_chapter_title_clip() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4", is_title=True),)),
    )
    segments = build_segments(plan, Path("/ev"))
    out = apply_decorators(("title",), plan, _target(), segments)
    assert out[0].is_synthetic and out[0].producer == TITLE_PRODUCER
    assert out[0].chapter == ""
    assert out[1].identity == "a.mp4"
    request = out[0].producer_config
    assert isinstance(request, TitleCardRequest)
    assert request.content.heading == "Movie"  # default chapter -> event title


def test_per_chapter_title_segments_for_two_chapters() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(name="Intro", clips=(ResolvedClip(identity="a.mp4", is_title=True),)),
        ResolvedChapter(name="Main", clips=(ResolvedClip(identity="b.mp4", is_title=True),)),
    )
    segments = build_segments(plan, Path("/ev"))
    out = apply_decorators(("title",), plan, _target(), segments)
    synthetic = [s for s in out if s.is_synthetic]
    assert len(synthetic) == 2
    # Each card sits immediately before its chapter's title clip and carries the name.
    assert out[0].is_synthetic and out[1].identity == "a.mp4"
    assert out[2].is_synthetic and out[3].identity == "b.mp4"
    headings = [s.producer_config.content.heading for s in synthetic]  # type: ignore[union-attr]
    assert headings == ["Intro", "Main"]  # both chapters are named -> chapter-name headings


def test_no_title_decorator_means_no_card() -> None:
    plan = _plan(
        {},
        ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4", is_title=True),)),
    )
    segments = build_segments(plan, Path("/ev"))
    out = apply_decorators(("none",), plan, _target(), segments)
    assert not any(s.is_synthetic for s in out)


def test_chapter_without_title_clip_gets_no_card() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4", is_title=False),)),
    )
    segments = build_segments(plan, Path("/ev"))
    out = apply_decorators(("title",), plan, _target(), segments)
    assert not any(s.is_synthetic for s in out)


def _three_chapters(**looks: object) -> RenderPlan:
    """Three titled chapters: the default one with a 3 s card, one with 10 s, one with none."""
    return _plan(
        {"decorators": ["title"], **looks},
        ResolvedChapter(
            name="",
            clips=(ResolvedClip(identity="a.mp4", is_title=True),),
            card=ChapterCard(duration=3.0),
        ),
        ResolvedChapter(
            name="Intro",
            clips=(ResolvedClip(identity="b.mp4", is_title=True),),
            card=ChapterCard(duration=10.0),
        ),
        ResolvedChapter(name="Main", clips=(ResolvedClip(identity="c.mp4", is_title=True),)),
    )


def _cards(plan: RenderPlan) -> list[Segment]:
    out = apply_decorators(("title",), plan, _target(), build_segments(plan, Path("/ev")))
    return [s for s in out if s.is_synthetic]


def test_each_chapters_card_has_its_own_length() -> None:
    cards = _cards(_three_chapters(title_card={"duration": 6.0}))
    assert [c.duration for c in cards] == [3.0, 10.0, 6.0]
    assert [c.producer_config.config.duration for c in cards] == [3.0, 10.0, 6.0]  # type: ignore[union-attr]


def test_the_event_wide_default_length_is_seven_seconds() -> None:
    assert [c.duration for c in _cards(_three_chapters())] == [3.0, 10.0, 7.0]


def test_a_chapters_card_overrides_apply_to_that_chapter_only() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="One",
            clips=(ResolvedClip(identity="a.mp4", is_title=True),),
            card=ChapterCard(font_family="Source Serif 4", text_color="#FFD700"),
        ),
        ResolvedChapter(name="Two", clips=(ResolvedClip(identity="b.mp4", is_title=True),)),
    )
    one, two = (c.producer_config.config for c in _cards(plan))  # type: ignore[union-attr]
    assert (one.font_family, one.text_color) == ("Source Serif 4", "#FFD700")
    assert (two.font_family, two.text_color) == (None, "#FFFFFF")


def test_a_cards_text_travels_on_its_segment() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="Reception",
            clips=(ResolvedClip(identity="a.mp4", is_title=True),),
            card=ChapterCard(title="Mottagningen", subtitle="Efteråt"),
        ),
    )
    (card,) = _cards(plan)
    assert card.chapter == "Reception"  # the chapter keeps its name; only the heading changes
    assert card.producer_config.content == TitleCardContent("Mottagningen", "Efteråt")  # type: ignore[union-attr]


def _video(**fields: object) -> ChapterCard:
    return ChapterCard(background="video", **fields)  # type: ignore[arg-type]


def _decorated(plan: RenderPlan, clip_facts: Optional[dict[str, ClipMetadata]] = None):
    segments = build_segments(plan, Path("/ev"), clip_facts)
    return apply_decorators(("title",), plan, _target(), segments)


def test_a_video_card_is_attached_to_the_title_clip_and_inserts_nothing() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="",
            clips=(ResolvedClip(identity="a.mp4", is_title=True),),
            card=_video(duration=5.0),
        ),
    )
    out = _decorated(plan)
    assert [s.identity for s in out] == ["a.mp4"] and not any(s.is_synthetic for s in out)
    (overlay,) = out[0].overlays
    assert (overlay.producer, overlay.start, overlay.end) == (TITLE_PRODUCER, 0.0, 5.0)
    assert (overlay.fade_in, overlay.fade_out) == (2.0, 2.0)
    request = overlay.producer_config
    assert isinstance(request, TitleCardRequest) and request.config.background == "video"
    assert out[0].duration is None  # the segment's length is untouched


def test_the_event_wide_video_background_attaches_to_every_chapter() -> None:
    plan = _plan(
        {"decorators": ["title"], "title_card": {"background": "video"}},
        ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4", is_title=True),)),
        ResolvedChapter(name="Two", clips=(ResolvedClip(identity="b.mp4", is_title=True),)),
    )
    out = _decorated(plan)
    assert [len(s.overlays) for s in out] == [1, 1] and not any(s.is_synthetic for s in out)


def test_a_black_plan_is_unchanged_by_the_overlay_support() -> None:
    plan = _three_chapters()
    out = _decorated(plan)
    assert [s.is_synthetic for s in out] == [True, False, True, False, True, False]
    assert not any(s.overlays for s in out)


def test_a_mixed_plan_attaches_the_video_card_and_inserts_the_black_one() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="",
            clips=(ResolvedClip(identity="a.mp4", is_title=True),),
            card=_video(),
        ),
        ResolvedChapter(name="Two", clips=(ResolvedClip(identity="b.mp4", is_title=True),)),
    )
    out = _decorated(plan)
    assert [(s.is_synthetic, s.identity, len(s.overlays)) for s in out] == [
        (False, "a.mp4", 1),
        (True, None, 0),
        (False, "b.mp4", 0),
    ]
    assert out[1].chapter == "Two"


def _clip_facts(identity: str, duration: float) -> ClipMetadata:
    return ClipMetadata(
        path=Path(identity),
        duration=duration,
        fps=30.0,
        video_codec="h264",
        profile="high",
        width=1920,
        height=1080,
        sample_aspect_ratio="1:1",
        display_aspect_ratio=None,
        pix_fmt="yuv420p",
        video_bitrate=None,
        rotation=None,
        color_transfer=None,
        is_hdr=False,
        audio=AudioStream("aac", 48000, 2, "stereo"),
        creation_time=None,
    )


def test_a_partially_cut_video_title_clip_gets_one_overlay_on_its_first_kept_span() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="",
            clips=(
                ResolvedClip(
                    identity="a.mp4",
                    is_title=True,
                    cut_spans=(Trim(start=0.0, end=2.0), Trim(start=5.0, end=6.0)),
                ),
            ),
            card=_video(),
        ),
    )
    out = _decorated(plan, {"a.mp4": _clip_facts("a.mp4", 10.0)})
    assert [(s.start, s.end, len(s.overlays)) for s in out] == [(2.0, 5.0, 1), (6.0, 10.0, 0)]


def test_a_wholly_cut_video_title_clip_moves_the_overlay_to_the_next_segment() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="",
            clips=(
                ResolvedClip(
                    identity="a.mp4", is_title=True, cut_spans=(Trim(start=0.0, end=10.0),)
                ),
                ResolvedClip(identity="b.mp4"),
            ),
            card=_video(),
        ),
    )
    out = _decorated(plan, {"a.mp4": _clip_facts("a.mp4", 10.0)})
    assert [(s.identity, len(s.overlays)) for s in out] == [("b.mp4", 1)]


def test_a_video_chapter_without_footage_or_title_clip_gets_no_overlay() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="Cut",
            clips=(
                ResolvedClip(
                    identity="a.mp4", is_title=True, cut_spans=(Trim(start=0.0, end=10.0),)
                ),
            ),
            card=_video(),
        ),
        ResolvedChapter(
            name="Plain",
            clips=(ResolvedClip(identity="b.mp4", is_title=False),),
            card=_video(),
        ),
    )
    out = _decorated(plan, {"a.mp4": _clip_facts("a.mp4", 10.0)})
    assert [(s.identity, s.overlays) for s in out] == [("b.mp4", ())]


def test_a_video_card_on_a_later_explicit_title_clip_attaches_to_that_clip() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="",
            clips=(
                ResolvedClip(identity="a.mp4", is_title=False),
                ResolvedClip(identity="b.mp4", is_title=True),
            ),
            card=_video(),
        ),
    )
    out = _decorated(plan)
    assert [(s.identity, len(s.overlays)) for s in out] == [("a.mp4", 0), ("b.mp4", 1)]


def test_the_decorator_stays_a_pure_function_for_a_video_card() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="", clips=(ResolvedClip(identity="a.mp4", is_title=True),), card=_video()
        ),
    )
    segments = build_segments(plan, Path("/ev"))
    first = apply_decorators(("title",), plan, _target(), segments)
    assert first == apply_decorators(("title",), plan, _target(), segments)
    assert segments[0].overlays == ()  # the input is not mutated


def test_a_black_card_over_an_event_wide_video_background_is_allowed() -> None:
    plan = _plan(
        {"decorators": ["title"], "title_card": {"background": "video"}},
        ResolvedChapter(
            name="",
            clips=(ResolvedClip(identity="a.mp4", is_title=True),),
            card=ChapterCard(background="black"),
        ),
    )
    assert len(_cards(plan)) == 1


def test_a_card_with_no_heading_fails_the_decorator() -> None:
    plan = RenderPlan(
        look={"decorators": ["title"]},
        chapters=(
            ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4", is_title=True),)),
        ),
    )
    with pytest.raises(TitleCardError, match="no heading"):
        apply_decorators(("title",), plan, _target(), build_segments(plan, Path("/ev")))


def test_a_bad_event_wide_style_still_fails_the_decorator() -> None:
    plan = _plan(
        {"decorators": ["title"], "title_card": {"background": "transparent"}},
        ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4", is_title=False),)),
    )
    with pytest.raises(TitleCardError, match=r"look\.title_card\.background"):
        apply_decorators(("title",), plan, _target(), build_segments(plan, Path("/ev")))


def _facts(*identities: str, duration: float = 10.0) -> dict[str, ClipMetadata]:
    """Probe facts for ``identities`` (cuts need the probed duration)."""
    return {
        identity: ClipMetadata(
            path=Path(identity),
            duration=duration,
            fps=30.0,
            video_codec="h264",
            profile="high",
            width=1920,
            height=1080,
            sample_aspect_ratio=None,
            display_aspect_ratio=None,
            pix_fmt="yuv420p",
            video_bitrate=None,
            rotation=None,
            color_transfer=None,
            is_hdr=False,
            audio=AudioStream("aac", 48000, 2, "stereo"),
            creation_time=None,
        )
        for identity in identities
    }


def _decorate(plan: RenderPlan, *identities: str) -> tuple[Segment, ...]:
    segments = build_segments(plan, Path("/ev"), _facts(*identities))
    return apply_decorators(("title",), plan, _target(), segments)


def _order(out: tuple[Segment, ...]) -> list[str]:
    return ["<card>" if s.is_synthetic else s.identity or "?" for s in out]


def test_fully_cut_title_clip_moves_card_to_next_clip() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="Ch1",
            clips=(
                ResolvedClip(identity="a.mp4", is_title=True, cut_spans=(Trim(0.0, 10.0),)),
                ResolvedClip(identity="b.mp4"),
            ),
        ),
    )
    out = _decorate(plan, "a.mp4", "b.mp4")
    assert _order(out) == ["<card>", "b.mp4"]
    assert out[0].chapter == "Ch1"
    request = out[0].producer_config
    assert isinstance(request, TitleCardRequest)
    assert request.content.heading == "Ch1"


def test_fully_cut_later_title_clip_anchors_at_chapter_start() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="Ch1",
            clips=(
                ResolvedClip(identity="a.mp4"),
                ResolvedClip(identity="b.mp4"),
                ResolvedClip(identity="c.mp4", is_title=True, cut_spans=(Trim(0.0, 10.0),)),
            ),
        ),
    )
    out = _decorate(plan, "a.mp4", "b.mp4", "c.mp4")
    assert _order(out) == ["<card>", "a.mp4", "b.mp4"]


def test_fully_cut_chapter_gets_no_card_and_other_chapter_keeps_its_own() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="Gone",
            clips=(
                ResolvedClip(identity="a.mp4", is_title=True, cut_spans=(Trim(0.0, 10.0),)),
                ResolvedClip(identity="b.mp4", cut_spans=(Trim(0.0, 12.0),)),
            ),
        ),
        ResolvedChapter(name="Kept", clips=(ResolvedClip(identity="c.mp4", is_title=True),)),
    )
    out = _decorate(plan, "a.mp4", "b.mp4", "c.mp4")
    assert _order(out) == ["<card>", "c.mp4"]
    assert [s.chapter for s in out] == ["Kept", "Kept"]


def test_partially_cut_title_clip_keeps_anchor_with_one_card() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="Ch1",
            clips=(
                ResolvedClip(identity="x.mp4"),
                ResolvedClip(
                    identity="a.mp4",
                    is_title=True,
                    cut_spans=(Trim(0.0, 3.0), Trim(5.0, 6.0)),
                ),
            ),
        ),
    )
    out = _decorate(plan, "x.mp4", "a.mp4")
    # Two kept spans (3-5, 6-10) yield one card, immediately before the first kept span.
    assert _order(out) == ["x.mp4", "<card>", "a.mp4", "a.mp4"]
    assert sum(1 for s in out if s.is_synthetic) == 1


def test_chapter_without_title_clip_stays_cardless_when_clips_are_cut() -> None:
    plan = _plan(
        {"decorators": ["title"]},
        ResolvedChapter(
            name="Ch1",
            clips=(
                ResolvedClip(identity="a.mp4", cut_spans=(Trim(0.0, 10.0),)),
                ResolvedClip(identity="b.mp4"),
            ),
        ),
    )
    out = _decorate(plan, "a.mp4", "b.mp4")
    assert _order(out) == ["b.mp4"]


# --------------------------------------------------------------------------- #
# 6. Synthetic normalize command (golden strings, no GPU)                     #
# --------------------------------------------------------------------------- #


def _produced(**overrides: object) -> ProducedSegment:
    base: dict[str, object] = dict(
        image_path=Path("/t/card.png"), duration=7.0, fade_in=2.0, fade_out=2.0
    )
    base.update(overrides)
    return ProducedSegment(**base)  # type: ignore[arg-type]


def test_synthetic_command_loops_image_encodes_target_and_has_silent_audio() -> None:
    command = build_synthetic_normalize_command(
        _title_segment(), _produced(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    args = command.args
    assert _subseq(args, ["-loop", "1"])
    assert _subseq(args, ["-t", "7", "-i", "/t/card.png"])
    assert _subseq(args, ["-c:v", "h264_vaapi"])
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in " ".join(args)
    assert _subseq(args, ["-map", "0:v:0"]) and _subseq(args, ["-map", "1:a:0"])
    assert _subseq(args, ["-c:a", "aac", "-ar", "48000", "-ac", "2"])
    assert _subseq(args, ["-r", "30"])
    assert command.duration == pytest.approx(7.0)


def test_synthetic_command_applies_configured_fades() -> None:
    command = build_synthetic_normalize_command(
        _title_segment(),
        _produced(duration=7.0, fade_in=2.0, fade_out=2.0),
        _target(),
        _amd_profile(),
        Path("/t/seg.mp4"),
    )
    vf = command.args[command.args.index("-vf") + 1]
    assert "fade=t=in:st=0:d=2" in vf
    assert "fade=t=out:st=5:d=2" in vf


def test_synthetic_command_omits_fades_when_zero() -> None:
    command = build_synthetic_normalize_command(
        _title_segment(),
        _produced(fade_in=0.0, fade_out=0.0),
        _target(),
        _amd_profile(),
        Path("/t/seg.mp4"),
    )
    vf = command.args[command.args.index("-vf") + 1]
    assert "fade=t=in" not in vf and "fade=t=out" not in vf


def test_synthetic_path_uses_no_overlay_on_amd() -> None:
    # can_overlay_hw is False on AMD; the card must still encode with no overlay op.
    command = build_synthetic_normalize_command(
        _title_segment(), _produced(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    assert "-filter_complex" not in command.args
    assert "overlay" not in " ".join(command.args)
    # VAAPI encode wants hardware frames: a single upload bridge, never an overlay.
    vf = command.args[command.args.index("-vf") + 1]
    assert vf.endswith("format=nv12,hwupload")


def test_synthetic_command_opens_the_device_hwupload_needs() -> None:
    # The card image never passes a hardware decoder, so nothing opens a device for
    # hwupload; without these flags ffmpeg rejects the command outright.
    command = build_synthetic_normalize_command(
        _title_segment(), _produced(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    args = command.args
    assert list(args[1:5]) == [
        "-init_hw_device",
        "vaapi=va:/dev/dri/renderD128",
        "-filter_hw_device",
        "va",
    ]
    assert args.index("-init_hw_device") < args.index("-i")


def test_synthetic_command_honors_an_explicit_render_node() -> None:
    command = build_synthetic_normalize_command(
        _title_segment(),
        _produced(),
        _target(),
        _amd_profile(),
        Path("/t/seg.mp4"),
        render_node="/dev/dri/renderD129",
    )
    assert _subseq(command.args, ["-init_hw_device", "vaapi=va:/dev/dri/renderD129"])


def test_synthetic_command_system_frame_encoder_opens_no_device() -> None:
    # NVENC ingests system-memory frames, so there is no upload and no device flag.
    caps = dataclasses.replace(
        _amd_profile().capabilities,
        vendor=Vendor.NVIDIA,
        device=None,
        usable_encoders={"h264": "h264_nvenc"},
        decode_method="cuda",
    )
    command = build_synthetic_normalize_command(
        _title_segment(),
        _produced(),
        _target(video_encoder="h264_nvenc"),
        NvencProfile(caps),
        Path("/t/seg.mp4"),
    )
    assert "-init_hw_device" not in command.args
    assert "hwupload" not in " ".join(command.args)


def test_synthetic_command_without_a_verified_upload_device_fails_loud() -> None:
    # QSV encoders want QSV frames, but no upload recipe has been verified on real
    # Intel hardware: refuse at build time rather than hand ffmpeg a broken command.
    caps = dataclasses.replace(
        _amd_profile().capabilities,
        vendor=Vendor.INTEL,
        usable_encoders={"h264": "h264_qsv"},
        decode_method="qsv",
    )
    with pytest.raises(RenderError, match=r"intel profile has no verified device.*--device cpu"):
        build_synthetic_normalize_command(
            _title_segment(),
            _produced(),
            _target(video_encoder="h264_qsv"),
            QsvProfile(caps),
            Path("/t/seg.mp4"),
        )


def test_synthetic_command_honors_av1_target_codec() -> None:
    command = build_synthetic_normalize_command(
        _title_segment(),
        _produced(),
        _target(video_codec="av1", video_encoder="av1_vaapi"),
        _amd_profile(),
        Path("/t/seg.mp4"),
    )
    assert _subseq(command.args, ["-c:v", "av1_vaapi"])


def test_synthetic_command_cpu_target_needs_no_hwupload() -> None:
    command = build_synthetic_normalize_command(
        _title_segment(),
        _produced(),
        _target(video_encoder="libx264"),
        CPUProfile(),
        Path("/t/seg.mp4"),
    )
    vf = command.args[command.args.index("-vf") + 1]
    assert "hwupload" not in vf
    assert _subseq(command.args, ["-c:v", "libx264"])


def test_synthetic_builder_rejects_source_segment() -> None:
    source = Segment(chapter="", identity="a.mp4", source_path=Path("/ev/a.mp4"), is_full_clip=True)
    with pytest.raises(RenderError, match="requires a synthetic segment"):
        build_synthetic_normalize_command(
            source, _produced(), _target(), _amd_profile(), Path("/t/seg.mp4")
        )


@pytest.mark.gpu
def test_synthetic_segment_encodes_on_the_hardware_profile(runtime, tmp_path: Path) -> None:
    # The card image starts in system memory; a hardware encoder that wants GPU
    # frames needs a device to upload into. A plain PNG stands in for the card so
    # the test exercises the encode path without Cairo/Pango or fonts.
    profile = select_profile(detect_capabilities(runtime))
    if profile.vendor is Vendor.CPU:
        pytest.skip("no usable hardware accelerator on this host")
    encoder = profile.capabilities.usable_encoders.get("h264")  # type: ignore[attr-defined]
    if encoder is None:
        pytest.skip("no hardware h264 encoder on this host")

    card = tmp_path / "card.png"
    runtime.run(["-y", "-f", "lavfi", "-i", "color=c=navy:s=640x360", "-frames:v", "1", str(card)])
    target = _target(width=640, height=360, video_encoder=encoder)
    output = tmp_path / "seg.mp4"
    command = build_synthetic_normalize_command(
        _title_segment(duration=1.0),
        _produced(image_path=card, duration=1.0, fade_in=0.25, fade_out=0.25),
        target,
        profile,
        output,
    )
    runtime.run(list(command.args))

    meta = probe_media(output, runtime=runtime)
    assert (meta.width, meta.height) == (640, 360)
    assert meta.video_codec == "h264"
    assert meta.has_audio
    assert meta.duration == pytest.approx(1.0, abs=0.1)


# --------------------------------------------------------------------------- #
# 3/4. Cairo + Pango renderer (gated behind has_fonts)                        #
# --------------------------------------------------------------------------- #


def _render(config: TitleCardConfig, content: TitleCardContent, target: TargetSpec, dest: Path):
    from auto_reel_ng.render.title import render_title_card

    return render_title_card(config, content, target, dest)


@pytest.mark.has_fonts
def test_rendered_card_is_target_resolution_and_rgba(has_fonts: None, tmp_path: Path) -> None:
    import cairo

    # Render over a translucent background so the alpha channel is retained (Cairo
    # losslessly collapses a fully-opaque ARGB32 surface to RGB on write); the
    # renderer always composes on an RGBA ARGB32 surface.
    dest = tmp_path / "card.png"
    _render(
        parse_title_card_config({"background_opacity": 0.5}),
        TitleCardContent(heading="Hej"),
        _target(width=320, height=240),
        dest,
    )
    surface = cairo.ImageSurface.create_from_png(str(dest))
    assert (surface.get_width(), surface.get_height()) == (320, 240)
    assert surface.get_format() == cairo.FORMAT_ARGB32


@pytest.mark.has_fonts
def test_bundled_default_renders_without_config(has_fonts: None, tmp_path: Path) -> None:
    dest = tmp_path / "card.png"
    out = _render(
        parse_title_card_config(None),
        TitleCardContent(heading="Midsommar", subtitle="Dalarna"),
        _target(width=320, height=240),
        dest,
    )
    assert out == dest and dest.exists()


@pytest.mark.has_fonts
def test_unresolved_font_family_fails_loud(has_fonts: None, tmp_path: Path) -> None:
    # The parser now refuses an unregistered family, so build the config directly: the
    # renderer's own fail-loud check must still stop a substituted font.
    config = TitleCardConfig(font_family="No Such Family ZZZ")
    with pytest.raises(FontResolutionError, match="No Such Family ZZZ"):
        _render(
            config,
            TitleCardContent(heading="Hej"),
            _target(width=320, height=240),
            tmp_path / "card.png",
        )


# --------------------------------------------------------------------------- #
# 7. End-to-end orchestration (gated behind has_fonts + real ffmpeg)          #
# --------------------------------------------------------------------------- #


@pytest.mark.has_fonts
def test_end_to_end_render_inserts_title_card_segment(
    has_fonts: None, runtime, make_clip, tmp_path
) -> None:
    clip = make_clip("a.mp4", width=320, height=240, fps=30, duration=1.0)
    facts = {"a.mp4": probe_media(clip, runtime=runtime)}
    look = {
        "decorators": ["title"],
        "target_resolution": [320, 240],
        "video_codec": "h264",
        "title_card": {"duration": 1.0, "fade_in": 0.2, "fade_out": 0.2},
    }
    plan = RenderPlan(
        metadata=Metadata(title="Movie", date=date(2024, 6, 21), location="Home"),
        look=look,
        chapters=(
            ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4", is_title=True),)),
        ),
    )
    # The decorated plan puts the synthetic card first.
    decorated = apply_decorators(
        ("title",), plan, _target(width=320, height=240), build_segments(plan, tmp_path, facts)
    )
    assert decorated[0].is_synthetic

    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime
    )
    result = render_movie(plan, CPUProfile(), options)
    assert result.output_path.exists()
    # The chapter duration accounts for the inserted ~1s card on top of the ~1s clip.
    out_facts = probe_media(result.output_path, runtime=runtime)
    assert out_facts.duration == pytest.approx(2.0, abs=0.4)
    assert (out_facts.width, out_facts.height) == (320, 240)


@pytest.mark.has_fonts
def test_end_to_end_render_records_the_title_card_span(
    has_fonts: None, runtime, make_clip, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Change render-chapter-times: the card's span is recorded inside its own chapter."""
    from auto_reel_ng.reel.document import ReelDocument
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint
    from auto_reel_ng.staleness.manifest import read_manifest

    clip_a = make_clip("a.mp4", width=320, height=240, fps=30, duration=2.0)
    clip_b = make_clip("b.mp4", width=320, height=240, fps=30, duration=1.0)
    facts = {
        "a.mp4": probe_media(clip_a, runtime=runtime),
        "b.mp4": probe_media(clip_b, runtime=runtime),
    }
    metadata = Metadata(title="Movie", date=date(2024, 6, 21), location="Home")
    plan = RenderPlan(
        metadata=metadata,
        look={
            "decorators": ["title"],
            "target_resolution": [320, 240],
            "video_codec": "h264",
            "title_card": {"duration": 1.0, "fade_in": 0.2, "fade_out": 0.2},
        },
        chapters=(
            ResolvedChapter(name="First", clips=(ResolvedClip(identity="a.mp4"),)),
            ResolvedChapter(name="Second", clips=(ResolvedClip(identity="b.mp4", is_title=True),)),
        ),
    )
    fingerprint = compute_fingerprint(
        ReelDocument(metadata=metadata),
        event_dir=tmp_path,
        look_defaults={},
        ffmpeg_version=runtime.version,
    )
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=tmp_path / "out",
        clip_facts=facts,
        runtime=runtime,
        fingerprint=fingerprint,
    )

    # The orchestrator measures each joined segment once, in order: a.mp4, the card, b.mp4.
    from auto_reel_ng.render import orchestrator as orch

    measured: list[float] = []
    real_probe = orch.probe_media

    def _spy(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        facts_ = real_probe(path, *args, **kwargs)
        measured.append(facts_.duration)
        return facts_

    monkeypatch.setattr(orch, "probe_media", _spy)
    render_movie(plan, CPUProfile(), options)
    assert len(measured) == 3

    manifest = read_manifest(tmp_path)
    assert manifest is not None and manifest.chapters is not None
    first, second = manifest.chapters
    assert (first.name, second.name) == ("First", "Second")
    assert first.title_card is None
    card = second.title_card
    assert card is not None
    # The card leads its chapter (the title clip is the chapter's first clip) and is ~1 s long.
    assert card.start_ms == second.start_ms == first.end_ms
    assert second.start_ms <= card.start_ms <= card.end_ms <= second.end_ms
    # The span is the card segment's measured duration (within a millisecond), and the chapter's
    # start is the measured duration of everything before it.
    card_ms = measured[1] * 1000
    assert card.end_ms - card.start_ms == pytest.approx(card_ms, abs=1)
    assert card.start_ms == pytest.approx(measured[0] * 1000, abs=1)
    assert second.end_ms - card.end_ms == pytest.approx(measured[2] * 1000, abs=1)
    assert card_ms == pytest.approx(1000, abs=40)


def test_an_unregistered_card_font_fails_loud_when_the_card_is_resolved() -> None:
    # The card's font is checked against the bundled registry when its style is parsed
    # (title-card-fonts), so a typo never reaches the renderer.
    with pytest.raises(TitleCardError, match="No Such Family ZZZ"):
        resolve_card_config(None, ChapterCard(font_family="No Such Family ZZZ"))


# --------------------------------------------------------------------------- #
# 8. A real render of per-card length, text and style from a reel.yaml          #
# --------------------------------------------------------------------------- #

CARD_REEL = """\
version: 0
metadata:
  title: Movie
  date: 2024-06-21
  location: Home
look:
  decorators: [title]
  target_resolution: [320, 240]
  video_codec: h264
  title_card: {fade_in: 0.2, fade_out: 0.2}
chapters:
  - name: ""
    card: {subtitle: Hos mormor, duration: 3}
    clips: [a.mp4]
  - name: Reception
    card: {title: Mottagningen, duration: 5, position: bottom}
    clips: [b.mp4]
"""


def _card_event(runtime, make_clip, tmp_path: Path, reel_text: str):  # type: ignore[no-untyped-def]
    """Resolve ``reel_text`` against two synthetic clips; return the plan and render options."""
    from auto_reel_ng.event.resolution import resolve
    from auto_reel_ng.reel.parser import loads_document
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint

    clips = {"a.mp4": make_clip("a.mp4", fps=30, duration=1.0), "b.mp4": make_clip("b.mp4", fps=30)}
    facts = {name: probe_media(path, runtime=runtime) for name, path in clips.items()}
    document = loads_document(reel_text)
    plan = resolve(document)
    fingerprint = compute_fingerprint(
        document, event_dir=tmp_path, look_defaults={}, ffmpeg_version=runtime.version
    )
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=tmp_path / "out",
        clip_facts=facts,
        runtime=runtime,
        fingerprint=fingerprint,
    )
    return plan, options


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_a_render_draws_each_card_at_its_own_length_and_keeps_the_chapter_names(
    has_fonts: None, runtime, make_clip, tmp_path: Path
) -> None:
    from auto_reel_ng.staleness.manifest import read_manifest

    plan, options = _card_event(runtime, make_clip, tmp_path, CARD_REEL)
    result = render_movie(plan, CPUProfile(), options)
    assert result.output_path.exists()

    manifest = read_manifest(tmp_path)
    assert manifest is not None and manifest.chapters is not None
    spans = {c.name: c.title_card for c in manifest.chapters}
    assert spans[""] is not None and spans["Reception"] is not None
    frame = 1000 / 30
    assert spans[""].end_ms - spans[""].start_ms == pytest.approx(3000, abs=frame)  # type: ignore[union-attr]
    assert spans["Reception"].end_ms - spans["Reception"].start_ms == pytest.approx(  # type: ignore[union-attr]
        5000, abs=frame
    )

    probe = runtime.run_ffprobe(
        ["-v", "error", "-show_chapters", "-print_format", "json", str(result.output_path)]
    )
    titles = [c.get("tags", {}).get("title", "") for c in json.loads(probe.stdout)["chapters"]]
    assert titles[1] == "Reception"  # the card says "Mottagningen"; the chapter keeps its name
    assert "Mottagningen" not in titles


# --------------------------------------------------------------------------- #
# title-card-write-api: the in-memory entry point and the helpers the API uses #
# --------------------------------------------------------------------------- #


@pytest.mark.has_fonts
def test_render_card_png_equals_the_file_a_render_writes(has_fonts: None, tmp_path: Path) -> None:
    from auto_reel_ng.render.title import render_card_png

    config = parse_title_card_config({"font_family": "DejaVu Sans"})
    content = TitleCardContent(heading="Midsommar", subtitle="Dalarna")
    dest = tmp_path / "card.png"
    _render(config, content, _target(width=1920, height=1080), dest)
    assert dest.read_bytes() == render_card_png(config, content, 1920, 1080)


@pytest.mark.has_fonts
def test_zero_opacity_background_is_transparent_except_the_text(
    has_fonts: None, tmp_path: Path
) -> None:
    import cairo

    from auto_reel_ng.render.title import render_card_png

    config = parse_title_card_config({"background_opacity": 0})
    data = render_card_png(config, TitleCardContent(heading="HELLO"), 640, 360)
    path = tmp_path / "t.png"
    path.write_bytes(data)
    surface = cairo.ImageSurface.create_from_png(str(path))
    assert surface.get_format() == cairo.FORMAT_ARGB32
    pixels = surface.get_data()
    stride = surface.get_stride()

    def alpha(x: int, y: int) -> int:
        return int(pixels[y * stride + x * 4 + 3])

    assert alpha(2, 2) == 0
    assert max(alpha(x, 180) for x in range(640)) > 0  # the text row has opaque pixels


@pytest.mark.has_fonts
def test_render_card_png_fails_loud_on_an_unresolvable_family(has_fonts: None) -> None:
    from auto_reel_ng.render.title import render_card_png

    with pytest.raises(FontResolutionError, match="No Such Family ZZZ"):
        render_card_png(
            TitleCardConfig(font_family="No Such Family ZZZ"), TitleCardContent(heading="x"), 64, 64
        )


def test_look_resolution_default_pair_and_fail_loud() -> None:
    from auto_reel_ng.render.target import look_resolution

    assert look_resolution({}) == (1920, 1080)
    assert look_resolution({"target_resolution": [1280, 720]}) == (1280, 720)
    with pytest.raises(RenderError, match="look.target_resolution"):
        look_resolution({"target_resolution": [0, 1080]})


def test_overlay_config_is_transparent_only_for_a_video_card() -> None:
    from auto_reel_ng.render.title import overlay_config

    black = parse_title_card_config({"background": "black"})
    video = parse_title_card_config({"background": "video"})
    assert overlay_config(black) == black
    assert overlay_config(video).background_opacity == 0.0
    assert dataclasses.replace(overlay_config(video), background_opacity=1.0) == video


def test_check_card_styles_names_the_event_style_field_and_the_chapter_font() -> None:
    from auto_reel_ng.render.title import check_card_styles

    check_card_styles({"title_font_size": 80}, {"": ChapterCard(font_family="DejaVu Sans")})
    with pytest.raises(TitleCardError, match=r"look\.title_card\.title_font_size"):
        check_card_styles({"title_font_size": "big"}, {})
    with pytest.raises(TitleCardError, match=r"'Dag 2'.*card\.font_family.*Comic Sans"):
        check_card_styles(None, {"Dag 2": ChapterCard(font_family="Comic Sans")})


# --------------------------------------------------------------------------- #
# title-cards-default-on (D-25): absent look.decorators means [title]         #
# --------------------------------------------------------------------------- #


def _two_chapter_document(event_look: Optional[dict] = None) -> ReelDocument:
    return ReelDocument(
        metadata=Metadata(title="Movie", date=date(2024, 6, 21), location="Home"),
        look=event_look or {},
        chapters=(
            Chapter(name="", clips=(ClipRef("a.mp4"),)),
            Chapter(name="Main", clips=(ClipRef("b.mp4"),)),
        ),
    )


def _cards_through_the_render_path(
    event_look: Optional[dict] = None, project_look: Optional[dict] = None
) -> list[Segment]:
    """The synthetic segments ``render_movie`` would build: its own three calls, in its order."""
    plan = resolve(_two_chapter_document(event_look), look_defaults=project_look)
    segments = build_segments(plan, Path("/ev"))
    names = resolve_decorator_names(plan.look)
    return [s for s in apply_decorators(names, plan, _target(), segments) if s.is_synthetic]


def test_with_no_decorators_anywhere_every_chapter_gets_a_card() -> None:
    cards = _cards_through_the_render_path()
    assert [c.chapter for c in cards] == ["", "Main"]
    assert all(c.producer == TITLE_PRODUCER for c in cards)


@pytest.mark.parametrize("explicit", [[], ["none"]])
def test_an_explicit_list_without_title_in_the_event_means_no_cards(explicit: list) -> None:
    assert _cards_through_the_render_path(event_look={"decorators": explicit}) == []


def test_a_project_empty_list_wins_over_the_default() -> None:
    assert _cards_through_the_render_path(project_look={"decorators": []}) == []


def test_an_event_title_list_wins_over_a_project_empty_list() -> None:
    cards = _cards_through_the_render_path(
        event_look={"decorators": ["title"]}, project_look={"decorators": []}
    )
    assert len(cards) == 2


def test_title_cards_state_reports_the_deciding_layer() -> None:
    assert title_cards_state({}, {}) == title_cards_state({"decorators": None}, {})
    assert (title_cards_state({}, {}).enabled, title_cards_state({}, {}).source) == (
        True,
        "default",
    )
    project_off = title_cards_state({}, {"decorators": []})
    assert (project_off.enabled, project_off.source) == (False, "project")
    event_on = title_cards_state({"decorators": ["title"]}, {"decorators": []})
    assert (event_on.enabled, event_on.source) == (True, "event")
    event_off = title_cards_state({"decorators": ["none"]}, {"decorators": ["title"]})
    assert (event_off.enabled, event_off.source) == (False, "event")
    other = title_cards_state({"decorators": ["watermark"]}, {})
    assert (other.enabled, other.source) == (False, "event")


def test_title_cards_state_agrees_with_the_render_when_the_event_says_null() -> None:
    """A null event value overrides the project's list in the merge, so both read `default`."""
    state = title_cards_state({"decorators": None}, {"decorators": []})
    assert (state.enabled, state.source) == (True, "default")
    assert len(_cards_through_the_render_path({"decorators": None}, {"decorators": []})) == 2


def test_title_cards_state_fails_loud_on_a_non_list() -> None:
    with pytest.raises(RenderError, match="look.decorators"):
        title_cards_state({"decorators": "title"}, {})
    with pytest.raises(RenderError, match="look.decorators"):
        title_cards_state({}, {"decorators": "title"})
