"""A video-background title card: an overlay attached to the chapter's first segment.

Covers the overlay mechanics (a producer-backed ``OverlaySpec`` materialized when the
command is built; the timed, alpha-faded, CPU-composited overlay and its clamp), the
transparent card canvas, and real renders that prove the movie length is unchanged and the
text is on the footage during the card's window and gone after it.
"""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.accel import detect_capabilities, select_profile
from auto_reel_ng.accel.models import AcceleratorCapabilities, Device, Vendor
from auto_reel_ng.accel.profiles import CPUProfile, NvencProfile, VaapiProfile
from auto_reel_ng.errors import FontResolutionError, RenderError
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.probe import probe_media
from auto_reel_ng.probe.metadata import AudioStream, ClipMetadata
from auto_reel_ng.reel.card import ChapterCard
from auto_reel_ng.reel.document import Metadata
from auto_reel_ng.render import (
    ProducedSegment,
    RenderOptions,
    Segment,
    TargetSpec,
)
from auto_reel_ng.render import orchestrator as orch
from auto_reel_ng.render import producers, render_movie
from auto_reel_ng.render.normalize import build_normalize_command
from auto_reel_ng.render.producers import materialize_overlay
from auto_reel_ng.render.segments import OverlaySpec
from auto_reel_ng.render.title import TitleCardContent, parse_title_card_config

# --------------------------------------------------------------------------- #
# Factories                                                                    #
# --------------------------------------------------------------------------- #


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


def _caps(*, can_overlay_hw: bool, vendor: Vendor = Vendor.AMD) -> AcceleratorCapabilities:
    return AcceleratorCapabilities(
        vendor=vendor,
        usable=True,
        device=Device(
            id="pci-0000:03:00.0",
            vendor=vendor,
            name="gpu",
            render_node="/dev/dri/renderD128",
        ),
        pad_filter="pad_vaapi" if vendor is Vendor.AMD else "pad",
        can_overlay_hw=can_overlay_hw,
        can_tonemap_hw=False,
        usable_encoders={"h264": "h264_vaapi" if vendor is Vendor.AMD else "h264_nvenc"},
        decode_method="vaapi" if vendor is Vendor.AMD else "cuda",
        hw_decode={"h264": 8},
    )


def _amd() -> VaapiProfile:
    return VaapiProfile(_caps(can_overlay_hw=False))


def _clip(duration: float = 10.0, *, audio: bool = True) -> ClipMetadata:
    return ClipMetadata(
        path=Path("clip.mp4"),
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
        audio=AudioStream("aac", 48000, 2, "stereo") if audio else None,
        creation_time=None,
    )


def _segment(**overrides: object) -> Segment:
    base: dict[str, object] = dict(
        chapter="",
        identity="clip.mp4",
        source_path=Path("/ev/clip.mp4"),
        is_full_clip=True,
    )
    base.update(overrides)
    return Segment(**base)  # type: ignore[arg-type]


def _card_overlay(**overrides: object) -> OverlaySpec:
    base: dict[str, object] = dict(
        source="/t/card.png", start=0.0, end=7.0, fade_in=2.0, fade_out=2.0
    )
    base.update(overrides)
    return OverlaySpec(**base)  # type: ignore[arg-type]


def _graph(args: tuple[str, ...]) -> str:
    return args[args.index("-filter_complex") + 1]


def _build(segment: Segment, profile, clip: Optional[ClipMetadata] = None):
    return build_normalize_command(segment, clip or _clip(), _target(), profile, Path("/t/seg.mp4"))


# --------------------------------------------------------------------------- #
# 1.1 The overlay spec and its materialization                                 #
# --------------------------------------------------------------------------- #


def test_an_overlay_spec_built_the_old_way_serializes_its_old_keys() -> None:
    overlay = OverlaySpec(source="title.png", x="10", y="20")
    data = overlay.to_dict()
    assert {k: data[k] for k in ("source", "x", "y", "start", "end")} == {
        "source": "title.png",
        "x": "10",
        "y": "20",
        "start": 0.0,
        "end": None,
    }
    assert (data["producer"], data["fade_in"], data["fade_out"]) == (None, 0.0, 0.0)
    assert not overlay.is_timed


def test_a_materialized_overlay_with_no_fades_is_still_timed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def produce(segment: Segment, target: TargetSpec, dest: Path) -> ProducedSegment:
        return ProducedSegment(image_path=dest, duration=4.0, fade_in=0.0, fade_out=0.0)

    monkeypatch.setitem(producers._REGISTRY, "flat-card", produce)  # pylint: disable=W0212
    overlay = OverlaySpec(producer="flat-card")
    assert not overlay.is_timed
    assert materialize_overlay(overlay, _target(), tmp_path / "c.png").is_timed


def test_an_overlay_with_a_fade_is_timed() -> None:
    assert OverlaySpec(fade_in=0.5).is_timed and OverlaySpec(fade_out=0.5).is_timed


class _Payload:
    def to_dict(self) -> dict[str, str]:
        return {"p": "payload"}


@pytest.fixture
def fake_producer(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Segment, Path]]:
    calls: list[tuple[Segment, Path]] = []

    def produce(segment: Segment, target: TargetSpec, dest: Path) -> ProducedSegment:
        calls.append((segment, dest))
        dest.write_bytes(b"png")
        return ProducedSegment(image_path=dest, duration=4.0, fade_in=1.0, fade_out=0.5)

    monkeypatch.setitem(producers._REGISTRY, "fake-card", produce)  # pylint: disable=W0212
    return calls


def test_a_producer_backed_overlay_materializes_into_image_window_and_fades(
    fake_producer, tmp_path: Path
) -> None:
    payload = _Payload()
    overlay = OverlaySpec(producer="fake-card", producer_config=payload, x="5")
    out = materialize_overlay(overlay, _target(), tmp_path / "card.png")
    assert (out.source, out.start, out.end) == (str(tmp_path / "card.png"), 0.0, 4.0)
    assert (out.fade_in, out.fade_out, out.x) == (1.0, 0.5, "5")
    segment, dest = fake_producer[0]
    assert (segment.producer, segment.producer_config, dest) == (
        "fake-card",
        payload,
        tmp_path / "card.png",
    )
    assert (tmp_path / "card.png").read_bytes() == b"png"


def test_an_overlay_without_a_producer_is_returned_as_it_is(tmp_path: Path) -> None:
    overlay = OverlaySpec(source="title.png")
    assert materialize_overlay(overlay, _target(), tmp_path / "x.png") is overlay


def test_an_unregistered_overlay_producer_fails_loud_naming_it_and_the_registered(
    tmp_path: Path,
) -> None:
    with pytest.raises(RenderError, match=r"unknown segment producer 'nope'.*registered.*title"):
        materialize_overlay(OverlaySpec(producer="nope"), _target(), tmp_path / "x.png")


def _options(tmp_path: Path, **kw: object) -> RenderOptions:
    return RenderOptions(
        event_dir=Path("/ev"),
        output_dir=tmp_path / "out",
        clip_facts={"clip.mp4": _clip()},
        runtime=None,  # type: ignore[arg-type]  # a command is built, never run
        **kw,  # type: ignore[arg-type]
    )


def test_building_a_segment_command_materializes_its_overlays_into_the_scratch_dir(
    fake_producer, tmp_path: Path
) -> None:
    segment = _segment(overlays=(OverlaySpec(producer="fake-card", producer_config=_Payload()),))
    command = orch._build_segment_command(  # pylint: disable=protected-access
        3,
        segment,
        target=_target(),
        profile=CPUProfile(),
        options=_options(tmp_path),
        scratch=tmp_path,
    )
    png = tmp_path / "card_003_0.png"
    assert png.exists() and str(png) in command.args
    assert "-i" in command.args and command.args[command.args.index(str(png)) - 1] == "-i"


def test_a_planned_command_names_a_real_card_image(fake_producer, tmp_path: Path) -> None:
    segment = _segment(overlays=(OverlaySpec(producer="fake-card", producer_config=_Payload()),))
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    result = orch._plan_only(  # pylint: disable=protected-access
        (segment,),
        _target(),
        CPUProfile(),
        _options(tmp_path, dry_run=True, temp_dir=scratch),
        tmp_path / "out" / "Movie.mp4",
    )
    png = scratch / "card_000_0.png"
    assert png.exists()
    assert any(str(png) in command for command in result.commands)


# --------------------------------------------------------------------------- #
# 1.2 The timed overlay graph                                                  #
# --------------------------------------------------------------------------- #

_TIMED_CHAIN = (
    "[1:v]format=rgba,fade=t=in:st=0:d=2:alpha=1,fade=t=out:st=5:d=2:alpha=1[ov0];"
    "[vbase][ov0]overlay=x=0:y=0:format=auto:enable='between(t,0,7)'[vo0]"
)


def test_a_timed_overlay_on_the_amd_profile_bridges_to_the_cpu_around_a_looped_faded_still() -> (
    None
):
    command = _build(_segment(overlays=(_card_overlay(),)), _amd())
    args = command.args
    graph = _graph(args)
    assert "-loop 1 -framerate 30 -t 7 -i /t/card.png".split() == list(
        args[args.index("-loop") : args.index("-loop") + 8]
    )
    assert graph == (
        "[0:v]scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease,"
        "hwdownload,format=nv12[vbase];" + _TIMED_CHAIN + ";[vo0]format=nv12,hwupload[vout]"
    )
    assert args[args.index("-map") + 1] == "[vout]"
    assert command.warnings == () and command.duration == 10.0


def test_a_timed_overlay_on_the_cpu_profile_has_no_transfers() -> None:
    graph = _graph(_build(_segment(overlays=(_card_overlay(),)), CPUProfile()).args)
    assert graph == (
        "[0:v]scale=w=1920:h=1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1[vbase];" + _TIMED_CHAIN
    )
    assert "hwdownload" not in graph and "hwupload" not in graph


def test_a_timed_overlay_never_uses_a_hardware_overlay_filter() -> None:
    profile = NvencProfile(_caps(can_overlay_hw=True, vendor=Vendor.NVIDIA))
    graph = _graph(_build(_segment(overlays=(_card_overlay(),)), profile).args)
    assert "overlay=x=0:y=0:format=auto:enable='between(t,0,7)'" in graph
    assert "overlay_cuda" not in graph and "overlay_qsv" not in graph


def test_the_silence_input_follows_the_card_input() -> None:
    args = _build(_segment(overlays=(_card_overlay(),)), CPUProfile(), _clip(audio=False)).args
    assert args[args.index("-map", args.index("-map") + 1) + 1] == "2:a:0"
    assert args.index("/t/card.png") < args.index("-f")


def test_a_trimmed_span_shorter_than_the_card_clamps_the_window_and_warns_once() -> None:
    segment = _segment(is_full_clip=False, start=1.0, end=4.0, overlays=(_card_overlay(),))
    command = _build(segment, CPUProfile())
    graph = _graph(command.args)
    assert "-t 3 -i /t/card.png" in " ".join(command.args)
    assert (
        "fade=t=in:st=0:d=1.5:alpha=1,fade=t=out:st=1.5:d=1.5:alpha=1[ov0]" in graph
        and "enable='between(t,0,3)'" in graph
    )
    assert command.warnings == (
        "segment clip.mp4: overlay shown for 3 s of the 7 s asked, the segment is only 3 s long",
    )
    assert command.duration == 3.0


def test_a_full_clip_shorter_than_the_card_takes_its_window_from_the_probe() -> None:
    command = _build(_segment(overlays=(_card_overlay(),)), CPUProfile(), _clip(duration=4.0))
    assert "-t 4 -i /t/card.png" in " ".join(command.args)
    assert "between(t,0,4)" in _graph(command.args)
    assert len(command.warnings) == 1 and "4 s of the 7 s" in command.warnings[0]


def test_a_card_that_fits_exactly_does_not_warn() -> None:
    command = _build(_segment(overlays=(_card_overlay(),)), CPUProfile(), _clip(duration=7.0))
    assert command.warnings == ()


def test_a_zero_second_fade_side_is_left_out() -> None:
    graph = _graph(_build(_segment(overlays=(_card_overlay(fade_in=0.0),)), CPUProfile()).args)
    assert "format=rgba,fade=t=out:st=5:d=2:alpha=1[ov0]" in graph
    assert "fade=t=in" not in graph


def test_a_timed_overlay_must_start_with_the_segment() -> None:
    with pytest.raises(RenderError, match="starts at the segment's start"):
        _build(_segment(overlays=(_card_overlay(start=1.0),)), CPUProfile())


def test_a_timed_overlay_with_both_fades_zero_is_looped_with_no_fade_filters() -> None:
    overlay = _card_overlay(fade_in=0.0, fade_out=0.0, timed=True)
    command = _build(_segment(overlays=(overlay,)), _amd())
    graph = _graph(command.args)
    assert "-loop" in command.args
    assert "[1:v]format=rgba[ov0]" in graph and "fade=" not in graph
    assert ":format=auto" in graph


def test_a_timed_overlay_with_both_fades_zero_is_clamped_to_the_segment() -> None:
    from auto_reel_ng.render.normalize import _clamp_timed_overlays  # pylint: disable=C0415

    overlay = _card_overlay(fade_in=0.0, fade_out=0.0, timed=True)
    out, warnings = _clamp_timed_overlays(_segment(overlays=(overlay,)), 3.0)
    assert out[0].end == 3.0 and len(warnings) == 1


def test_an_overlay_without_fades_keeps_the_old_graph() -> None:
    plain = OverlaySpec(source="title.png", x="10", y="20")
    command = _build(_segment(overlays=(plain,)), _amd())
    assert "-loop" not in command.args and "-framerate" not in command.args
    assert _graph(command.args) == (
        "[0:v]scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease,"
        "hwdownload,format=nv12[vbase];[vbase][1:v]overlay=x=10:y=20[vo0];"
        "[vo0]format=nv12,hwupload[vout]"
    )


# --------------------------------------------------------------------------- #
# 2.1 The transparent canvas                                                   #
# --------------------------------------------------------------------------- #


def _render_png(config_map: dict, tmp_path: Path, name: str, **content: object):
    import cairo  # pylint: disable=import-outside-toplevel

    from auto_reel_ng.render.title import render_title_card  # pylint: disable=C0415

    dest = tmp_path / name
    render_title_card(
        parse_title_card_config(config_map),
        TitleCardContent(heading="Midsommar", **content),  # type: ignore[arg-type]
        _target(width=320, height=240),
        dest,
    )
    surface = cairo.ImageSurface.create_from_png(str(dest))
    data = bytes(surface.get_data())
    stride = surface.get_stride()
    return data, stride, dest.read_bytes()


def _alpha(data: bytes, stride: int, x: int, y: int) -> int:
    return data[y * stride + x * 4 + 3]


@pytest.mark.has_fonts
def test_a_video_card_is_transparent_outside_the_text_and_opaque_on_it(
    has_fonts: None, tmp_path: Path
) -> None:
    data, stride, _ = _render_png({"background": "video"}, tmp_path, "v.png")
    assert all(_alpha(data, stride, x, y) == 0 for x, y in ((0, 0), (319, 0), (0, 239), (319, 239)))
    alphas = [_alpha(data, stride, x, y) for y in range(240) for x in range(320)]
    assert max(alphas) == 255 and sum(a == 255 for a in alphas) > 200


@pytest.mark.has_fonts
def test_a_video_cards_opaque_pixels_are_the_black_cards_text_pixels(
    has_fonts: None, tmp_path: Path
) -> None:
    video, stride, _ = _render_png({"background": "video"}, tmp_path, "v.png")
    black, _, _ = _render_png({"background": "black"}, tmp_path, "b.png")

    def lit(data: bytes) -> set[tuple[int, int]]:
        return {
            (x, y)
            for y in range(240)
            for x in range(320)
            if data[y * stride + x * 4 + 2] > 200  # white text on the black card (premultiplied)
        }

    text_on_black = lit(black)
    assert text_on_black
    opaque_video = {
        (x, y)
        for y in range(240)
        for x in range(320)
        if _alpha(video, stride, x, y) == 255 and video[y * stride + x * 4 + 2] > 200
    }
    assert opaque_video == text_on_black
    # A black card stays opaque everywhere: the background is painted as before.
    assert _alpha(black, stride, 0, 0) == 255


@pytest.mark.has_fonts
def test_a_black_card_does_not_change_with_the_background_field_spelt_out(
    has_fonts: None, tmp_path: Path
) -> None:
    explicit, _, png_a = _render_png({"background": "black"}, tmp_path, "a.png")
    default, _, png_b = _render_png({}, tmp_path, "b.png")
    assert explicit == default and png_a == png_b


@pytest.mark.has_fonts
def test_a_video_card_with_an_unresolvable_font_still_fails_loud(
    has_fonts: None, tmp_path: Path
) -> None:
    from auto_reel_ng.render.title import (  # pylint: disable=import-outside-toplevel
        TitleCardConfig,
        render_title_card,
    )

    config = TitleCardConfig(background="video", font_family="No Such Family ZZZ")
    with pytest.raises(FontResolutionError, match="No Such Family ZZZ"):
        render_title_card(
            config,
            TitleCardContent(heading="Hej"),
            _target(width=320, height=240),
            tmp_path / "x.png",
        )


# --------------------------------------------------------------------------- #
# 3 Real renders                                                               #
# --------------------------------------------------------------------------- #

_WINDOW = 7.0
_W, _H = 640, 360


def _grey_clip(runtime, path: Path, duration: float) -> Path:
    runtime.run(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x606060:s={_W}x{_H}:r=30:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ]
    )
    return path


def _event(
    runtime, tmp_path: Path, name: str, *, duration: float, video_card: bool, fade: float = 2.0
):
    event = tmp_path / name
    event.mkdir()
    _grey_clip(runtime, event / "a.mp4", duration)
    facts = {"a.mp4": probe_media(event / "a.mp4", runtime=runtime)}
    card = ChapterCard(background="video", duration=_WINDOW) if video_card else None
    plan = RenderPlan(
        metadata=Metadata(title="Movie", date=date(2024, 6, 21), location=""),
        look={
            "decorators": ["title"] if video_card else ["none"],
            "target_resolution": [_W, _H],
            "video_codec": "h264",
            "title_card": {"fade_in": fade, "fade_out": fade, "text_color": "#FFFFFF"},
        },
        chapters=(
            ResolvedChapter(
                name="",
                clips=(ResolvedClip(identity="a.mp4", is_title=True),),
                card=card,
            ),
        ),
    )
    options = RenderOptions(
        event_dir=event, output_dir=event / "out", clip_facts=facts, runtime=runtime
    )
    return plan, options


def _luma_at(runtime, movie: Path, seconds: float) -> list[int]:
    """The luma plane of the frame at ``seconds`` in the middle band of the picture (text band)."""
    result = subprocess.run(
        [
            runtime.ffmpeg_path,
            "-v",
            "error",
            "-ss",
            f"{seconds}",
            "-i",
            str(movie),
            "-frames:v",
            "1",
            "-vf",
            f"crop={_W}:{_H // 3}:0:{_H // 3},format=gray",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return list(result.stdout)


def _bright(luma: list[int]) -> int:
    return sum(1 for v in luma if v > 200)


def _footage(luma: list[int]) -> int:
    """Pixels still showing the mid-grey footage (0x60 = 96), not a black fill."""
    return sum(1 for v in luma if 80 <= v <= 112)


def _render_pair(runtime, tmp_path: Path, profile, duration: float, fade: float = 2.0):
    plan, options = _event(runtime, tmp_path, "card", duration=duration, video_card=True, fade=fade)
    control_plan, control_options = _event(
        runtime, tmp_path, "control", duration=duration, video_card=False
    )
    result = render_movie(plan, profile, options)
    control = render_movie(control_plan, profile, control_options)
    return result, control


def _assert_card_over_footage(runtime, result, control, duration: float) -> None:
    movie, ref = result.output_path, control.output_path
    frame = 1.0 / 30
    assert probe_media(movie, runtime=runtime).duration == pytest.approx(
        probe_media(ref, runtime=runtime).duration, abs=frame * 1.5
    )
    shown = min(_WINDOW, duration)
    mid = shown / 2
    assert _bright(_luma_at(runtime, movie, mid)) > _bright(_luma_at(runtime, ref, mid)) + 300
    # The footage shows through around the text: the card is not a black frame with text.
    assert _footage(_luma_at(runtime, movie, mid)) > 0.8 * _footage(_luma_at(runtime, ref, mid))
    if duration > _WINDOW + 0.5:
        after = _WINDOW + 1.0
        assert _bright(_luma_at(runtime, movie, after)) == _bright(_luma_at(runtime, ref, after))


def _chapter_marks(runtime, movie: Path) -> list[tuple[str, str, str]]:
    probe = runtime.run_ffprobe(
        ["-v", "error", "-show_chapters", "-print_format", "json", str(movie)]
    )
    return [
        (c["start_time"], c["end_time"], c.get("tags", {}).get("title", ""))
        for c in json.loads(probe.stdout)["chapters"]
    ]


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_a_video_card_is_on_the_footage_for_its_window_and_adds_no_time(
    has_fonts: None, runtime, tmp_path: Path
) -> None:
    result, control = _render_pair(runtime, tmp_path, CPUProfile(), 12.0)
    assert result.warnings == ()
    _assert_card_over_footage(runtime, result, control, 12.0)
    assert _chapter_marks(runtime, result.output_path) == _chapter_marks(
        runtime, control.output_path
    )


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_a_video_card_on_a_clip_shorter_than_it_clamps_and_warns(
    has_fonts: None, runtime, tmp_path: Path
) -> None:
    result, control = _render_pair(runtime, tmp_path, CPUProfile(), 3.0)
    assert len(result.warnings) == 1
    assert "3 s of the 7 s asked" in result.warnings[0]
    _assert_card_over_footage(runtime, result, control, 3.0)
    assert probe_media(result.output_path, runtime=runtime).duration == pytest.approx(3.0, abs=0.15)


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_a_video_card_records_no_title_card_span(has_fonts: None, runtime, tmp_path: Path) -> None:
    from auto_reel_ng.event.resolution import resolve  # pylint: disable=C0415
    from auto_reel_ng.reel.parser import loads_document  # pylint: disable=C0415
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint  # pylint: disable=C0415
    from auto_reel_ng.staleness.manifest import read_manifest  # pylint: disable=C0415

    event = tmp_path / "ev"
    event.mkdir()
    _grey_clip(runtime, event / "a.mp4", 3.0)
    facts = {"a.mp4": probe_media(event / "a.mp4", runtime=runtime)}
    document = loads_document(
        "version: 0\nmetadata:\n  title: Movie\nlook:\n  decorators: [title]\n"
        "  target_resolution: [640, 360]\nchapters:\n"
        "  - name: ''\n    card: {background: video, duration: 2}\n    clips: [a.mp4]\n"
    )
    fingerprint = compute_fingerprint(
        document, event_dir=event, look_defaults={}, ffmpeg_version=runtime.version
    )
    options = RenderOptions(
        event_dir=event,
        output_dir=event / "out",
        clip_facts=facts,
        runtime=runtime,
        fingerprint=fingerprint,
    )
    render_movie(resolve(document), CPUProfile(), options)
    manifest = read_manifest(event)
    assert manifest is not None and manifest.chapters is not None
    assert [c.title_card for c in manifest.chapters] == [None]


@pytest.mark.gpu
@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_a_video_card_renders_on_the_hardware_profile(
    has_fonts: None, runtime, tmp_path: Path
) -> None:
    profile = select_profile(detect_capabilities(runtime))
    if profile.vendor is Vendor.CPU:
        pytest.skip("no usable hardware accelerator on this host")
    result, control = _render_pair(runtime, tmp_path, profile, 12.0)
    assert result.warnings == ()
    _assert_card_over_footage(runtime, result, control, 12.0)
    assert probe_media(result.output_path, runtime=runtime).width == _W


@pytest.mark.gpu
@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_a_clamped_video_card_renders_on_the_hardware_profile(
    has_fonts: None, runtime, tmp_path: Path
) -> None:
    profile = select_profile(detect_capabilities(runtime))
    if profile.vendor is Vendor.CPU:
        pytest.skip("no usable hardware accelerator on this host")
    result, control = _render_pair(runtime, tmp_path, profile, 3.0)
    assert len(result.warnings) == 1
    _assert_card_over_footage(runtime, result, control, 3.0)


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_a_video_card_with_no_fades_clamps_and_warns_on_the_cpu(
    has_fonts: None, runtime, tmp_path: Path
) -> None:
    result, control = _render_pair(runtime, tmp_path, CPUProfile(), 3.0, fade=0.0)
    assert len(result.warnings) == 1 and "3 s of the 7 s asked" in result.warnings[0]
    _assert_card_over_footage(runtime, result, control, 3.0)


@pytest.mark.gpu
@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
@pytest.mark.parametrize("duration", [12.0, 3.0])
def test_a_video_card_with_no_fades_renders_on_the_hardware_profile(
    has_fonts: None, runtime, tmp_path: Path, duration: float
) -> None:
    profile = select_profile(detect_capabilities(runtime))
    if profile.vendor is Vendor.CPU:
        pytest.skip("no usable hardware accelerator on this host")
    result, control = _render_pair(runtime, tmp_path, profile, duration, fade=0.0)
    _assert_card_over_footage(runtime, result, control, duration)
