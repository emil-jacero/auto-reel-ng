"""Render pipeline tests: golden command strings (no GPU) + runtime integration.

The pure builders (segments, decorators, target spec, normalize commands, copy
eligibility, ffmetadata) are golden-tested without a GPU, matching the accel
layer's style. The assembly/verify helpers and a full end-to-end render are
exercised against a real (CPU) ffmpeg via the shared fixtures; a GPU-marked
end-to-end covers the hardware path on the AMD host.
"""

from __future__ import annotations

import dataclasses
import json
import unicodedata
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Optional

import pytest

from auto_reel_ng.accel import detect_capabilities, select_profile
from auto_reel_ng.accel.models import (
    AcceleratorCapabilities,
    Device,
    OpParams,
    Vendor,
)
from auto_reel_ng.accel.profiles import CPUProfile, VaapiProfile
from auto_reel_ng.accel.profiles.cpu import CPU_TONEMAP_FILTER
from auto_reel_ng.errors import RenderCancelledError, RenderError, RenderVerificationError
from auto_reel_ng.event import seed_document
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.probe import probe_media
from auto_reel_ng.probe.metadata import AudioStream, ClipMetadata
from auto_reel_ng.reel.document import Metadata, Trim
from auto_reel_ng.render import (
    HDR_SLOWNESS_WARNING,
    BatchOutcome,
    OverlaySpec,
    RenderJob,
    RenderOptions,
    Segment,
    TargetSpec,
    aggregate_chapter_durations,
    apply_decorators,
    build_concat_command,
    build_concat_list,
    build_ffmetadata,
    build_normalize_command,
    build_segments,
    copy_eligible,
    decide_copy_eligibility,
    derive_target,
    find_output_collisions,
    is_copy_uniform,
    kept_spans,
    make_attacher,
    make_inserter,
)
from auto_reel_ng.render import orchestrator as orch
from auto_reel_ng.render import (
    output_filename,
    output_relpath,
    render_batch,
    render_movie,
    resolve_decorator_names,
    resolve_target,
    verify_output,
)
from auto_reel_ng.render.normalize import NormalizeCommand, _needs_pad

# --------------------------------------------------------------------------- #
# Fixtures / factories                                                         #
# --------------------------------------------------------------------------- #


def _amd_caps() -> AcceleratorCapabilities:
    return AcceleratorCapabilities(
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


def _amd_profile() -> VaapiProfile:
    return VaapiProfile(_amd_caps())


def _clip(
    identity: str = "clip.mp4",
    *,
    width: int = 1920,
    height: int = 1080,
    fps: float = 30.0,
    codec: str = "h264",
    pix_fmt: str = "yuv420p",
    sar: Optional[str] = None,
    is_hdr: bool = False,
    audio: bool = True,
    duration: float = 10.0,
) -> ClipMetadata:
    return ClipMetadata(
        path=Path(identity),
        duration=duration,
        fps=fps,
        video_codec=codec,
        profile="high",
        width=width,
        height=height,
        sample_aspect_ratio=sar,
        display_aspect_ratio=None,
        pix_fmt=pix_fmt,
        video_bitrate=None,
        rotation=None,
        color_transfer="smpte2084" if is_hdr else None,
        is_hdr=is_hdr,
        audio=AudioStream("aac", 48000, 2, "stereo") if audio else None,
        creation_time=None,
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


def _source_segment(**overrides: object) -> Segment:
    base: dict[str, object] = dict(
        chapter="",
        identity="clip.mp4",
        source_path=Path("/ev/clip.mp4"),
        is_full_clip=True,
    )
    base.update(overrides)
    return Segment(**base)  # type: ignore[arg-type]


def _subseq(haystack: tuple[str, ...], needle: list[str]) -> bool:
    """True if ``needle`` appears as a contiguous subsequence of ``haystack``."""
    n = len(needle)
    return any(list(haystack[i : i + n]) == needle for i in range(len(haystack) - n + 1))


# --------------------------------------------------------------------------- #
# 2. Segment list                                                             #
# --------------------------------------------------------------------------- #


def test_untrimmed_clip_yields_one_segment() -> None:
    plan = RenderPlan(chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),))
    segments = build_segments(plan, Path("/ev"))
    assert len(segments) == 1
    assert segments[0].is_full_clip
    assert segments[0].source_path == Path("/ev/a.mp4")
    assert segments[0].start is None and segments[0].end is None


def test_mid_clip_cut_yields_two_segments() -> None:
    clip = ResolvedClip(identity="a.mp4", cut_spans=(Trim(start=4.0, end=6.0),))
    plan = RenderPlan(chapters=(ResolvedChapter(name="", clips=(clip,)),))
    facts = {"a.mp4": _clip("a.mp4", duration=10.0)}
    segments = build_segments(plan, Path("/ev"), facts)
    assert [(s.start, s.end) for s in segments] == [(0.0, 4.0), (6.0, 10.0)]
    assert all(s.is_trimmed for s in segments)


def test_overlapping_cuts_yield_disjoint_segments_in_source_order() -> None:
    clip = ResolvedClip(
        identity="a.mp4", cut_spans=(Trim(start=1.0, end=3.0), Trim(start=2.0, end=5.0))
    )
    plan = RenderPlan(chapters=(ResolvedChapter(name="", clips=(clip,)),))
    facts = {"a.mp4": _clip("a.mp4", duration=10.0)}
    segments = build_segments(plan, Path("/ev"), facts)
    spans = [(s.start, s.end) for s in segments]
    assert spans == [(0.0, 1.0), (5.0, 10.0)]
    assert all(s.is_trimmed for s in segments)
    # No footage appears in two segments.
    assert all(a_end <= b_start for (_, a_end), (b_start, _) in zip(spans, spans[1:]))


def test_kept_spans_complement() -> None:
    assert kept_spans((Trim(0.0, 2.0),), 10.0) == [(2.0, 10.0)]
    assert kept_spans((Trim(8.0, 10.0),), 10.0) == [(0.0, 8.0)]
    # Overlapping cuts merge.
    assert kept_spans((Trim(1.0, 3.0), Trim(2.0, 4.0)), 10.0) == [(0.0, 1.0), (4.0, 10.0)]


def test_kept_spans_joins_overlapping_touching_nested_and_unsorted_cuts() -> None:
    """Cuts are one union removal: overlap is accepted, never an error or a double render."""
    expected = [(0.0, 1.0), (5.0, 10.0)]
    assert kept_spans((Trim(1.0, 3.0), Trim(2.0, 5.0)), 10.0) == expected
    # Touching cuts leave no zero-length kept span between them.
    assert kept_spans((Trim(1.0, 3.0), Trim(3.0, 5.0)), 10.0) == expected
    # A cut inside another adds nothing.
    assert kept_spans((Trim(1.0, 9.0), Trim(2.0, 3.0)), 10.0) == [(0.0, 1.0), (9.0, 10.0)]
    # The listed order does not matter.
    assert kept_spans((Trim(5.0, 8.0), Trim(1.0, 3.0), Trim(2.0, 6.0)), 10.0) == [
        (0.0, 1.0),
        (8.0, 10.0),
    ]


def test_two_chapters_preserve_order() -> None:
    plan = RenderPlan(
        chapters=(
            ResolvedChapter(name="Intro", clips=(ResolvedClip(identity="a.mp4"),)),
            ResolvedChapter(
                name="Main",
                clips=(ResolvedClip(identity="b.mp4"), ResolvedClip(identity="c.mp4")),
            ),
        )
    )
    segments = build_segments(plan, Path("/ev"))
    assert [(s.chapter, s.identity) for s in segments] == [
        ("Intro", "a.mp4"),
        ("Main", "b.mp4"),
        ("Main", "c.mp4"),
    ]


def test_segment_construction_is_deterministic() -> None:
    plan = RenderPlan(
        chapters=(
            ResolvedChapter(name="c1", clips=(ResolvedClip(identity="a.mp4"),)),
            ResolvedChapter(name="c2", clips=(ResolvedClip(identity="b.mp4"),)),
        )
    )
    first = build_segments(plan, Path("/ev"))
    second = build_segments(plan, Path("/ev"))
    assert first == second


def test_trimmed_clip_without_facts_fails_loud() -> None:
    clip = ResolvedClip(identity="a.mp4", cut_spans=(Trim(1.0, 2.0),))
    plan = RenderPlan(chapters=(ResolvedChapter(name="", clips=(clip,)),))
    with pytest.raises(RenderError, match="requires probed duration"):
        build_segments(plan, Path("/ev"))


# --------------------------------------------------------------------------- #
# 3. Decorator seam                                                           #
# --------------------------------------------------------------------------- #


def test_inserter_adds_synthetic_segment_at_position() -> None:
    segments = (_source_segment(),)
    inserter = make_inserter(
        produce=lambda plan, target: Segment(chapter="", producer="title-card", duration=3.0),
        position=lambda segs: 0,
    )
    out = inserter(RenderPlan(), _target(), segments)
    assert len(out) == 2
    assert out[0].is_synthetic and out[0].producer == "title-card"
    assert out[1] is segments[0]


def test_attacher_adds_overlay_and_marks_ineligible() -> None:
    segments = (_source_segment(),)
    attacher = make_attacher(
        overlay_for=lambda plan, target, seg: OverlaySpec(source="title.png"),
        predicate=lambda seg, idx: idx == 0,
    )
    out = attacher(RenderPlan(), _target(), segments)
    assert len(out[0].overlays) == 1
    # A segment carrying an overlay is not copy-eligible.
    assert copy_eligible(out[0], _clip(), _target()) is False


def test_none_decorator_is_noop() -> None:
    segments = (_source_segment(), _source_segment(identity="b.mp4"))
    out = apply_decorators(("none",), RenderPlan(), _target(), segments)
    assert out == segments


def test_unknown_decorator_fails_loud() -> None:
    with pytest.raises(RenderError, match="unknown decorator 'bogus'"):
        apply_decorators(("bogus",), RenderPlan(), _target(), (_source_segment(),))


def test_resolve_decorator_names_defaults_to_none() -> None:
    assert resolve_decorator_names({}) == ("none",)
    assert resolve_decorator_names({"decorators": ["title", "watermark"]}) == ("title", "watermark")
    with pytest.raises(RenderError, match="must be a list"):
        resolve_decorator_names({"decorators": "title"})


# --------------------------------------------------------------------------- #
# 4. Target spec                                                              #
# --------------------------------------------------------------------------- #


def test_target_resolution_and_fps_from_look_not_first_clip() -> None:
    look = {"target_resolution": [1920, 1080], "fps": 30}
    target = derive_target(look, [_clip(fps=25.0)], _amd_profile())
    assert (target.width, target.height, target.fps) == (1920, 1080, 30.0)
    assert target.video_codec == "h264"
    assert target.video_encoder == "h264_vaapi"
    assert target.sample_aspect_ratio == "1:1"


def test_portrait_first_clip_does_not_make_a_portrait_canvas() -> None:
    clips = [_clip("phone.mp4", width=720, height=1280), _clip("cam.mp4")]
    target = derive_target({}, clips, _amd_profile())
    assert (target.width, target.height) == (1920, 1080)


def test_4k_clips_do_not_make_a_4k_canvas_by_default() -> None:
    clips = [_clip("uhd.mp4", width=3840, height=2160), _clip("hd.mp4")]
    target = derive_target({}, clips, _amd_profile())
    assert (target.width, target.height) == (1920, 1080)


def test_highest_clip_fps_wins_by_default() -> None:
    clips = [_clip("a.mp4", fps=25.0), _clip("b.mp4", fps=50.0), _clip("c.mp4", fps=30.0)]
    assert derive_target({}, clips, _amd_profile()).fps == 50.0


def test_look_fps_overrides_clip_fps() -> None:
    assert derive_target({"fps": 30}, [_clip(fps=25.0)], _amd_profile()).fps == 30.0


def test_look_target_resolution_overrides_default() -> None:
    target = derive_target({"target_resolution": [3840, 2160]}, [_clip()], _amd_profile())
    assert (target.width, target.height) == (3840, 2160)


@pytest.mark.parametrize(
    ("look", "key"),
    [
        ({"fps": "fifty"}, "look.fps"),
        ({"fps": 0}, "look.fps"),
        ({"fps": True}, "look.fps"),
        ({"fps": "25"}, "look.fps"),
        ({"target_resolution": [1920, 0]}, "look.target_resolution"),
        ({"target_resolution": [1920]}, "look.target_resolution"),
        ({"target_resolution": ["1920", "1080"]}, "look.target_resolution"),
    ],
)
def test_malformed_look_canvas_keys_fail_loud(look: dict[str, object], key: str) -> None:
    with pytest.raises(RenderError, match=key):
        derive_target(look, [_clip()], _amd_profile())


def test_uniform_default_canvas_keeps_copy_path() -> None:
    facts = {name: _clip(name, fps=50.0) for name in ("a.mp4", "b.mp4")}
    plan = RenderPlan(
        chapters=(
            ResolvedChapter(
                name="", clips=(ResolvedClip(identity="a.mp4"), ResolvedClip(identity="b.mp4"))
            ),
        ),
    )
    target = resolve_target(plan, _amd_profile(), facts)
    assert (target.width, target.height, target.fps) == (1920, 1080, 50.0)
    decided = decide_copy_eligibility(build_segments(plan, Path("/ev"), facts), facts, target)
    assert decided and all(segment.copy_eligible for segment in decided)


def test_resolve_target_fails_loud_on_any_unprobed_clip() -> None:
    plan = RenderPlan(
        chapters=(
            ResolvedChapter(
                name="", clips=(ResolvedClip(identity="a.mp4"), ResolvedClip(identity="b.mp4"))
            ),
        ),
    )
    with pytest.raises(RenderError, match="'b.mp4' has no probed metadata"):
        resolve_target(plan, _amd_profile(), {"a.mp4": _clip("a.mp4")})


def test_av1_target_honored_when_profile_supports_it() -> None:
    target = derive_target({"video_codec": "av1"}, [_clip()], _amd_profile())
    assert target.video_codec == "av1"
    assert target.video_encoder == "av1_vaapi"


def test_unencodable_codec_fails_loud() -> None:
    with pytest.raises(RenderError, match="no usable hardware or CPU encoder"):
        derive_target({"video_codec": "vp9"}, [_clip()], CPUProfile())


# --------------------------------------------------------------------------- #
# 5. Per-segment normalize (golden command strings, no GPU)                   #
# --------------------------------------------------------------------------- #


def test_amd_vaapi_normalize_chain() -> None:
    segment = _source_segment()
    command = build_normalize_command(
        segment, _clip(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    args = command.args
    assert _subseq(args, ["-hwaccel", "vaapi"])
    # An exact 16:9 clip fills the canvas: scale_vaapi alone, no pad, no transfer.
    assert _subseq(
        args,
        ["-vf", "scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease"],
    )
    assert _subseq(args, ["-c:v", "h264_vaapi"])
    assert _subseq(args, ["-map", "0:v:0"]) and _subseq(args, ["-map", "0:a:0"])
    assert _subseq(args, ["-c:a", "aac", "-ar", "48000", "-ac", "2"])
    assert _subseq(args, ["-r", "30"])
    assert not command.warnings


def _vf(command: NormalizeCommand) -> str:
    return command.args[command.args.index("-vf") + 1]


def _faulty_fill_profile() -> VaapiProfile:
    return VaapiProfile(dataclasses.replace(_amd_caps(), pad_fill_ok=False))


def test_portrait_clip_with_faulty_fill_pads_on_cpu() -> None:
    command = build_normalize_command(
        _source_segment(),
        _clip(width=1440, height=1920),
        _target(),
        _faulty_fill_profile(),
        Path("/t/seg.mp4"),
    )
    assert _vf(command) == (
        "hwdownload,format=nv12,"
        "scale=w=1920:h=1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,"
        "format=nv12,hwupload"
    )


@pytest.mark.parametrize("size", [(3840, 2160), (1920, 1080), (1280, 720)])
def test_exact_16_9_clip_stays_on_gpu_with_faulty_fill(size: tuple[int, int]) -> None:
    width, height = size
    command = build_normalize_command(
        _source_segment(),
        _clip(width=width, height=height),
        _target(),
        _faulty_fill_profile(),
        Path("/t/seg.mp4"),
    )
    assert _vf(command) == "scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease"


def test_portrait_clip_with_correct_fill_pads_on_gpu() -> None:
    command = build_normalize_command(
        _source_segment(),
        _clip(width=1440, height=1920),
        _target(),
        _amd_profile(),
        Path("/t/seg.mp4"),
    )
    assert _vf(command) == (
        "scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease,"
        "pad_vaapi=w=1920:h=1080:x=(ow-iw)/2:y=(oh-ih)/2:color=black"
    )


@pytest.mark.parametrize(
    ("clip", "rotate", "expected"),
    [
        (_clip(width=1920, height=1088), None, True),  # 30/17, not exactly 16/9
        (_clip(width=3840, height=2160), None, False),
        (_clip(width=1280, height=720), None, False),
        (_clip(width=1440, height=1920), None, True),
        (_clip(width=1920, height=1080), 90, True),  # segment rotation -> portrait
        (dataclasses.replace(_clip(), rotation=270), None, True),  # clip metadata rotation
        (dataclasses.replace(_clip(), rotation=90), 180, False),  # segment rotate wins
        (_clip(width=1920, height=1080, sar="N/A"), None, False),
        # Anamorphic 16:9 display: no scale honours SAR, so the pixels still need bars.
        (_clip(width=1440, height=1080, sar="4:3"), None, True),
        (_clip(width=1920, height=1080, sar="4:3"), None, True),
    ],
)
def test_needs_pad(clip: ClipMetadata, rotate: Optional[int], expected: bool) -> None:
    assert _needs_pad(clip, rotate, _target()) is expected


def test_hardware_decode_shares_one_named_device_with_filters() -> None:
    # A CPU transpose between VAAPI decode and encode must hwupload back: the decode
    # names one device, used for decode and the filter graph; no second is opened.
    command = build_normalize_command(
        _source_segment(rotate=90), _clip(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    args = command.args
    assert args.count("-init_hw_device") == 1
    assert list(args[1:11]) == [
        "-init_hw_device",
        "vaapi=va:/dev/dri/renderD128",
        "-filter_hw_device",
        "va",
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        "va",
        "-hwaccel_output_format",
        "vaapi",
    ]
    assert "format=nv12,hwupload" in _vf(command)


def test_hardware_decode_without_a_known_node_uses_the_default_device() -> None:
    caps = dataclasses.replace(_amd_caps(), device=None)
    command = build_normalize_command(
        _source_segment(), _clip(), _target(), VaapiProfile(caps), Path("/t/seg.mp4")
    )
    assert command.args.count("-init_hw_device") == 1
    assert _subseq(command.args, ["-init_hw_device", "vaapi=va", "-filter_hw_device", "va"])


def test_software_decode_names_the_device_hwupload_needs() -> None:
    # Hardware decode unusable but the VAAPI encoder usable: frames are decoded to
    # system memory and uploaded, so the command must open the device itself.
    profile = VaapiProfile(dataclasses.replace(_amd_caps(), decode_method=None))
    command = build_normalize_command(
        _source_segment(), _clip(), _target(), profile, Path("/t/seg.mp4")
    )
    args = command.args
    assert "-hwaccel" not in args
    vf = args[args.index("-vf") + 1]
    assert vf.startswith("format=nv12,hwupload,scale_vaapi=")
    assert list(args[1:5]) == [
        "-init_hw_device",
        "vaapi=va:/dev/dri/renderD128",
        "-filter_hw_device",
        "va",
    ]
    assert args.count("-init_hw_device") == 1
    assert args.index("-init_hw_device") < args.index("-i")


def test_vaapi_upload_device_without_a_known_node_uses_the_default() -> None:
    caps = dataclasses.replace(_amd_caps(), device=None)
    assert VaapiProfile(caps).upload_device_flags(OpParams()) == (
        "-init_hw_device",
        "vaapi=va",
        "-filter_hw_device",
        "va",
    )


def test_hardware_encode_omits_software_pix_fmt() -> None:
    # ffmpeg >= 8 rejects an explicit ``-pix_fmt yuv420p`` against a VAAPI encoder
    # (it consumes GPU surfaces); the CPU path must still set it.
    vaapi = build_normalize_command(
        _source_segment(), _clip(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    assert "-pix_fmt" not in vaapi.args
    cpu = build_normalize_command(
        _source_segment(), _clip(), _target(), CPUProfile(), Path("/t/seg.mp4")
    )
    assert _subseq(cpu.args, ["-pix_fmt", "yuv420p"])


def test_hdr_uses_cpu_tonemap_with_transfers_and_warns() -> None:
    segment = _source_segment()
    command = build_normalize_command(
        segment, _clip(is_hdr=True), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    vf = command.args[command.args.index("-vf") + 1]
    assert "scale_vaapi" in vf
    assert "hwdownload,format=nv12" in vf
    assert CPU_TONEMAP_FILTER in vf
    assert vf.endswith("format=nv12,hwupload")
    assert HDR_SLOWNESS_WARNING in command.warnings


def test_sdr_clip_is_not_tonemapped() -> None:
    command = build_normalize_command(
        _source_segment(), _clip(is_hdr=False), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    vf = command.args[command.args.index("-vf") + 1]
    assert "tonemap" not in vf
    assert "zscale" not in vf


def test_rotation_falls_back_to_cpu_transpose() -> None:
    segment = _source_segment(rotate=90)
    command = build_normalize_command(
        segment, _clip(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    vf = command.args[command.args.index("-vf") + 1]
    # decode is VAAPI -> CPU transpose forces a download, then upload back for scale_vaapi.
    assert vf.startswith("hwdownload,format=nv12,transpose=1,format=nv12,hwupload,scale_vaapi")


def test_overlay_uses_cpu_bridge_filter_complex() -> None:
    segment = _source_segment(overlays=(OverlaySpec(source="title.png", x="10", y="20"),))
    command = build_normalize_command(
        segment, _clip(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    assert "-filter_complex" in command.args
    graph = command.args[command.args.index("-filter_complex") + 1]
    assert "hwdownload,format=nv12" in graph  # bridge down to CPU for overlay
    assert "overlay=x=10:y=20" in graph
    assert "format=nv12,hwupload" in graph  # back up for VAAPI encode
    assert _subseq(command.args, ["-i", "title.png"])


def test_overlay_free_segment_stays_on_vf_path() -> None:
    command = build_normalize_command(
        _source_segment(), _clip(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    assert "-filter_complex" not in command.args
    assert "-vf" in command.args


def test_video_only_clip_gets_synthesized_silence() -> None:
    command = build_normalize_command(
        _source_segment(), _clip(audio=False), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    joined = " ".join(command.args)
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in joined
    assert _subseq(command.args, ["-map", "1:a:0"])


def test_kept_span_realized_with_input_seek_and_duration() -> None:
    segment = _source_segment(is_full_clip=False, start=3.2, end=8.0)
    command = build_normalize_command(
        segment, _clip(), _target(), _amd_profile(), Path("/t/seg.mp4")
    )
    assert _subseq(command.args, ["-ss", "3.2"])
    assert _subseq(command.args, ["-t", "4.8"])
    assert command.duration == pytest.approx(4.8)


def test_synthetic_segment_normalize_fails_loud() -> None:
    segment = Segment(chapter="", producer="title-card", duration=3.0)
    with pytest.raises(RenderError, match="synthetic segment"):
        build_normalize_command(segment, _clip(), _target(), _amd_profile(), Path("/t/seg.mp4"))


# --------------------------------------------------------------------------- #
# 6. Copy eligibility                                                         #
# --------------------------------------------------------------------------- #


def test_conforming_untouched_clip_is_copy_eligible() -> None:
    assert copy_eligible(_source_segment(), _clip(), _target()) is True


def test_trimmed_overlaid_rotated_mismatched_are_ineligible() -> None:
    target = _target()
    assert (
        copy_eligible(_source_segment(is_full_clip=False, start=1.0, end=2.0), _clip(), target)
        is False
    )
    assert (
        copy_eligible(_source_segment(overlays=(OverlaySpec("x.png"),)), _clip(), target) is False
    )
    assert copy_eligible(_source_segment(rotate=90), _clip(), target) is False
    assert copy_eligible(_source_segment(), _clip(width=1280, height=720), target) is False
    assert copy_eligible(_source_segment(), _clip(is_hdr=True), target) is False
    assert copy_eligible(_source_segment(), _clip(audio=False), target) is False


def test_synthetic_segment_never_copy_eligible() -> None:
    segment = Segment(chapter="", producer="title-card", duration=3.0)
    assert copy_eligible(segment, None, _target()) is False


def test_decide_copy_eligibility_sets_flag() -> None:
    segments = (_source_segment(), _source_segment(identity="b.mp4", rotate=90))
    facts = {"clip.mp4": _clip(), "b.mp4": _clip("b.mp4")}
    decided = decide_copy_eligibility(segments, facts, _target())
    assert decided[0].copy_eligible is True
    assert decided[1].copy_eligible is False


# --------------------------------------------------------------------------- #
# 7. Movie assembly (pure parts)                                              #
# --------------------------------------------------------------------------- #


def test_aggregate_chapter_durations_sums_per_chapter_in_order() -> None:
    segments = (
        Segment(chapter="Intro", identity="a"),
        Segment(chapter="Main", identity="b"),
        Segment(chapter="Main", identity="c"),
    )
    pairs = aggregate_chapter_durations(segments, [2.0, 3.0, 1.5])
    assert pairs == [("Intro", 2.0), ("Main", 4.5)]


def test_build_ffmetadata_cumulative_chapters() -> None:
    meta = build_ffmetadata([("Intro", 2.0), ("Main", 3.0)])
    assert ";FFMETADATA1" in meta
    assert meta.count("[CHAPTER]") == 2
    assert "START=0\nEND=2000" in meta
    assert "START=2000\nEND=5000" in meta
    assert "title=Intro" in meta and "title=Main" in meta


def test_build_concat_list_and_command() -> None:
    listing = build_concat_list([Path("/t/a.mp4"), Path("/t/b.mp4")])
    assert listing.splitlines() == ["file /t/a.mp4", "file /t/b.mp4"]
    cmd = build_concat_command(
        Path("/t/list.txt"), Path("/o/out.mp4"), metadata_file=Path("/t/c.ff")
    )
    assert _subseq(cmd, ["-f", "concat", "-safe", "0", "-i", "/t/list.txt"])
    assert _subseq(cmd, ["-map_chapters", "1"])
    assert _subseq(cmd, ["-c", "copy"])


def test_output_filename_with_and_without_location() -> None:
    assert (
        output_filename(Metadata(title="Midsummer", location="Dalarna"))
        == "Midsummer - Dalarna.mp4"
    )
    assert output_filename(Metadata(title="Midsummer")) == "Midsummer.mp4"


def test_output_filename_prefixes_a_dated_event_with_its_iso_date() -> None:
    dated = Metadata(title="Midsummer", date=date(2024, 6, 21), location="Dalarna")
    assert output_filename(dated) == "2024-06-21 - Midsummer - Dalarna.mp4"


def test_output_relpath_uses_the_metadata_year() -> None:
    dated = Metadata(title="Midsummer", date=date(2024, 6, 21), location="Dalarna")
    assert output_relpath(dated) == PurePosixPath("2024/2024-06-21 - Midsummer - Dalarna.mp4")
    no_location = Metadata(title="Julafton", date=date(2023, 12, 24))
    assert output_relpath(no_location) == PurePosixPath("2023/2023-12-24 - Julafton.mp4")


def test_output_relpath_undated_event_sits_at_the_root() -> None:
    assert output_relpath(Metadata(title="Sommarlov")) == PurePosixPath("Sommarlov.mp4")


def test_output_relpath_reproduces_a_legacy_archive_name(tmp_path: Path) -> None:
    event_dir = tmp_path / "2017-07-20 - Båttur med Liljan och Ralf"
    event_dir.mkdir()
    (event_dir / "a.mp4").write_bytes(b"")
    metadata = seed_document(event_dir).metadata
    assert output_relpath(metadata) == PurePosixPath(
        "2017/2017-07-20 - Båttur med Liljan och Ralf.mp4"
    )


def test_find_output_collisions_same_year_pair() -> None:
    claims = {
        "a": PurePosixPath("2024/Midsommar.mp4"),
        "b": PurePosixPath("2024/Midsommar.mp4"),
        "c": PurePosixPath("2024/Kalas.mp4"),
    }
    assert find_output_collisions(claims) == {"a": ("b",), "b": ("a",)}


def test_find_output_collisions_ignores_case_and_normalization() -> None:
    nfd = unicodedata.normalize("NFD", "2024/Göteborg.mp4")
    claims = {
        "upper": PurePosixPath("2024/Midsommar.mp4"),
        "lower": PurePosixPath("2024/midsommar.mp4"),
        "nfc": PurePosixPath("2024/Göteborg.mp4"),
        "nfd": PurePosixPath(nfd),
    }
    result = find_output_collisions(claims)
    assert result["upper"] == ("lower",)
    assert result["nfc"] == ("nfd",)


def test_find_output_collisions_different_years_and_three_way() -> None:
    assert not find_output_collisions(
        {"y23": PurePosixPath("2023/Midsommar.mp4"), "y24": PurePosixPath("2024/Midsommar.mp4")}
    )
    same = PurePosixPath("2024/Kalas.mp4")
    result = find_output_collisions({"a": same, "b": same, "c": same})
    assert result == {"a": ("b", "c"), "b": ("a", "c"), "c": ("a", "b")}
    assert not find_output_collisions({})


# --------------------------------------------------------------------------- #
# 7/8. Assembly + orchestration against a real (CPU) ffmpeg                   #
# --------------------------------------------------------------------------- #


def test_is_copy_uniform_matches_and_mismatches(runtime, make_clip) -> None:
    a = make_clip("a.mp4", width=320, height=240)
    b = make_clip("b.mp4", width=320, height=240)
    c = make_clip("c.mp4", width=640, height=480)
    assert is_copy_uniform(runtime, [a, b]) is True
    assert is_copy_uniform(runtime, [a, c]) is False


def test_verify_output_accepts_conforming_and_rejects_mismatch(runtime, make_clip) -> None:
    clip = make_clip("v.mp4", width=320, height=240, fps=30)
    facts = probe_media(clip, runtime=runtime)
    good = _target(
        width=320,
        height=240,
        fps=facts.fps,
        video_codec=facts.video_codec,
        video_encoder="libx264",
        pix_fmt=facts.pix_fmt or "yuv420p",
    )
    assert verify_output(runtime, clip, good).width == 320
    bad = _target(width=1920, height=1080, video_encoder="libx264")
    with pytest.raises(RenderVerificationError, match="does not match target spec"):
        verify_output(runtime, clip, bad)


def _two_chapter_plan(look: dict) -> RenderPlan:
    return RenderPlan(
        metadata=Metadata(title="Movie", location="Home"),
        look=look,
        chapters=(
            ResolvedChapter(name="Intro", clips=(ResolvedClip(identity="a.mp4"),)),
            ResolvedChapter(name="Main", clips=(ResolvedClip(identity="b.mp4"),)),
        ),
    )


def test_end_to_end_cpu_render_with_chapters(runtime, make_clip, tmp_path) -> None:
    event_dir = tmp_path
    clip_a = make_clip("a.mp4", width=320, height=240, fps=30, duration=1.0)
    clip_b = make_clip("b.mp4", width=320, height=240, fps=30, duration=1.0)
    facts = {
        "a.mp4": probe_media(clip_a, runtime=runtime),
        "b.mp4": probe_media(clip_b, runtime=runtime),
    }
    # Target larger than source -> forces a real normalize (scale+pad) per segment.
    plan = _two_chapter_plan({"target_resolution": [640, 480], "video_codec": "h264"})
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=event_dir,
        output_dir=out_dir,
        clip_facts=facts,
        runtime=runtime,
    )
    result = render_movie(plan, CPUProfile(), options)

    assert result.output_path == out_dir / "Movie - Home.mp4"
    assert result.output_path.exists()
    # Verified to match the 640x480 target.
    assert probe_media(result.output_path, runtime=runtime).width == 640
    # Two chapters reached the container.
    chapters = json.loads(
        runtime.run_ffprobe(
            ["-v", "error", "-show_chapters", "-print_format", "json", str(result.output_path)]
        ).stdout
    )["chapters"]
    assert [c["tags"]["title"] for c in chapters] == ["Intro", "Main"]


def test_render_finalizes_into_a_created_year_folder(
    runtime, make_clip, tmp_path, monkeypatch
) -> None:
    clip = make_clip("a.mp4", width=320, height=240, fps=30, duration=1.0)
    facts = {"a.mp4": probe_media(clip, runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie", date=date(2024, 6, 21)),
        look={"target_resolution": [320, 240], "video_codec": "h264"},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    dry = render_movie(
        plan,
        CPUProfile(),
        RenderOptions(
            event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime, dry_run=True
        ),
    )
    assert dry.output_path == out_dir / "2024" / "2024-06-21 - Movie.mp4"
    assert not (out_dir / "2024").exists()

    seen_parts: list[Path] = []
    real_replace = orch.os.replace

    def _spy_replace(src: Path, dst: Path) -> None:
        seen_parts.append(Path(src))
        real_replace(src, dst)

    monkeypatch.setattr(orch.os, "replace", _spy_replace)
    result = render_movie(
        plan,
        CPUProfile(),
        RenderOptions(event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime),
    )

    assert result.output_path == out_dir / "2024" / "2024-06-21 - Movie.mp4"
    assert result.output_path.exists()
    # The .part sat beside the final path, so the finalizing rename stayed in one dir.
    assert [part.parent for part in seen_parts] == [out_dir / "2024"]


@pytest.mark.has_ffmpeg
def test_canvas_ignores_portrait_low_fps_first_clip(runtime, make_clip, tmp_path) -> None:
    # A portrait 25 fps clip first must not decide the canvas: the look pins the
    # resolution (kept small for speed) and the fps defaults to the highest clip's.
    make_clip("a.mp4", width=360, height=640, fps=25, duration=1.0)
    make_clip("b.mp4", width=640, height=360, fps=50, duration=1.0)
    facts = {name: probe_media(tmp_path / name, runtime=runtime) for name in ("a.mp4", "b.mp4")}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 360]},
        chapters=(
            ResolvedChapter(
                name="", clips=(ResolvedClip(identity="a.mp4"), ResolvedClip(identity="b.mp4"))
            ),
        ),
    )
    options = RenderOptions(
        event_dir=tmp_path, output_dir=tmp_path / "out", clip_facts=facts, runtime=runtime
    )
    result = render_movie(plan, CPUProfile(), options)

    rendered = probe_media(result.output_path, runtime=runtime)
    assert (rendered.width, rendered.height) == (640, 360)
    # Probe reports avg_frame_rate; on a 2 s output the join's timestamp gap pulls it
    # just under 50 (r_frame_rate is 50/1). The tolerance still separates 50 from 25.
    assert rendered.fps == pytest.approx(50.0, abs=1.0)


def test_mismatch_forces_reencode_before_join(runtime, make_clip, tmp_path, monkeypatch) -> None:
    # The lone segment is copy-eligible (640x480 conforming), so it would normally
    # be stream-copied as-is. Force the equivalence pre-flight to report the set
    # non-uniform on its first check; the orchestrator must then re-encode the
    # copied segment to the uniform target before joining (movie-assembly:
    # "Mismatch forces re-encode rather than a silent-broken copy").
    clip_a = make_clip("a.mp4", width=640, height=480, fps=30, duration=1.0)
    probed = probe_media(clip_a, runtime=runtime)
    facts = {"a.mp4": probed}
    # Match the target's audio params to the clip's so it is fully conforming and
    # therefore copy-eligible (make_clip emits 44.1kHz mono).
    assert probed.audio is not None
    look = {
        "target_resolution": [640, 480],
        "video_codec": "h264",
        "audio_sample_rate": probed.audio.sample_rate,
        "audio_channels": probed.audio.channels,
    }
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look=look,
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    # Sanity: the segment really is copy-eligible, so the re-encode branch is reachable.
    target = derive_target(plan.look, [probed], CPUProfile())
    assert copy_eligible(_source_segment(source_path=clip_a), probed, target) is True

    calls = {"n": 0}

    def _flaky_uniform(_rt: object, _paths: object) -> bool:
        calls["n"] += 1
        return calls["n"] != 1  # False on the first check, True after re-encoding

    monkeypatch.setattr(orch, "is_copy_uniform", _flaky_uniform)
    options = RenderOptions(
        event_dir=tmp_path, output_dir=tmp_path / "out", clip_facts=facts, runtime=runtime
    )
    result = render_movie(plan, CPUProfile(), options)

    assert calls["n"] >= 2  # re-checked after the re-encode pass
    assert result.output_path.exists()
    assert probe_media(result.output_path, runtime=runtime).width == 640


def test_trimmed_clip_chapter_boundary_uses_measured_duration(runtime, make_clip, tmp_path) -> None:
    # A 2.0s clip trimmed to ~1.0s kept: the chapter boundary must follow the
    # measured intermediate duration (~1.0s), not the 2.0s nominal source length
    # (movie-assembly: "Chapter boundaries follow measured, not nominal, durations").
    clip = make_clip("a.mp4", width=320, height=240, fps=30, duration=2.0)
    facts = {"a.mp4": probe_media(clip, runtime=runtime)}
    trimmed = ResolvedClip(identity="a.mp4", cut_spans=(Trim(start=0.5, end=1.5),))
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [320, 240]},
        chapters=(ResolvedChapter(name="Only", clips=(trimmed,)),),
    )
    options = RenderOptions(
        event_dir=tmp_path, output_dir=tmp_path / "out", clip_facts=facts, runtime=runtime
    )
    result = render_movie(plan, CPUProfile(), options)
    chapters = json.loads(
        runtime.run_ffprobe(
            ["-v", "error", "-show_chapters", "-print_format", "json", str(result.output_path)]
        ).stdout
    )["chapters"]
    assert len(chapters) == 1
    assert float(chapters[0]["end_time"]) == pytest.approx(1.0, abs=0.25)


def test_existing_output_not_overwritten(runtime, make_clip, tmp_path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    existing = out_dir / "Movie.mp4"
    existing.write_text("untouched")
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime
    )
    result = render_movie(plan, CPUProfile(), options)
    assert result.skipped is True
    assert existing.read_text() == "untouched"


def test_dry_run_produces_commands_and_no_output(runtime, make_clip, tmp_path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime, dry_run=True
    )
    result = render_movie(plan, CPUProfile(), options)
    assert result.dry_run is True
    assert result.commands  # at least the normalize + concat commands
    assert not (out_dir / "Movie.mp4").exists()
    assert not out_dir.exists()


# --------------------------------------------------------------------------- #
# 8. Failure isolation                                                        #
# --------------------------------------------------------------------------- #


def test_batch_isolates_one_failing_event(runtime, make_clip, tmp_path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    good_plan = RenderPlan(
        metadata=Metadata(title="Good"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    bad_plan = RenderPlan(
        metadata=Metadata(title="Bad"),
        look={"target_resolution": [640, 480], "decorators": ["does-not-exist"]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    base = dict(event_dir=tmp_path, clip_facts=facts, runtime=runtime, dry_run=True)
    jobs = [
        RenderJob(bad_plan, CPUProfile(), RenderOptions(output_dir=tmp_path / "b", **base)),
        RenderJob(good_plan, CPUProfile(), RenderOptions(output_dir=tmp_path / "g", **base)),
    ]
    outcomes = render_batch(jobs)
    assert isinstance(outcomes[0], BatchOutcome)
    assert outcomes[0].error is not None and "does-not-exist" in outcomes[0].error
    assert outcomes[1].result is not None and outcomes[1].result.dry_run


def test_failed_render_removes_half_written_output(
    runtime, make_clip, tmp_path, monkeypatch
) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime
    )

    def _boom(*_args: object, **_kwargs: object) -> ClipMetadata:
        raise RenderVerificationError("simulated broken output")

    monkeypatch.setattr(orch, "verify_output", _boom)
    with pytest.raises(RenderVerificationError):
        render_movie(plan, CPUProfile(), options)
    # The half-written output was removed rather than presented as success, and no
    # leftover .part remains either (movie-assembly: atomic finalize cleanup).
    assert not (out_dir / "Movie.mp4").exists()
    assert not (out_dir / "Movie.mp4.part").exists()


def test_atomic_finalize_temp_file_shares_output_directory(
    runtime, make_clip, tmp_path, monkeypatch
) -> None:
    # The finalizing os.replace must be a same-filesystem rename, so the .part
    # concat target has to live in the output directory, never the scratch tmpdir
    # (movie-assembly: "Temporary output shares the output directory").
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime
    )

    captured: dict[str, Path] = {}
    real_verify = orch.verify_output

    def _spy_verify(rt: object, path: Path, tgt: object) -> ClipMetadata:
        captured["part_path"] = path
        return real_verify(rt, path, tgt)

    monkeypatch.setattr(orch, "verify_output", _spy_verify)
    result = render_movie(plan, CPUProfile(), options)

    assert captured["part_path"].parent == out_dir
    assert captured["part_path"].name == "Movie.mp4.part"
    assert result.output_path.exists()
    assert not captured["part_path"].exists()  # renamed away, not left behind


def test_hard_kill_leftover_part_does_not_fool_skip_check(runtime, make_clip, tmp_path) -> None:
    # Simulate a hard kill (SIGKILL/OOM/power loss) that struck after the concat
    # wrote the .part file but before the atomic rename: only the .part exists,
    # never the final path. skip-if-exists must not be fooled by the leftover
    # .part into skipping the re-render, and the stale .part must not survive.
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    leftover_part = out_dir / "Movie.mp4.part"
    leftover_part.write_bytes(b"truncated garbage from a killed process")
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime
    )

    result = render_movie(plan, CPUProfile(), options)

    assert result.skipped is False
    assert result.output_path.exists()
    assert not leftover_part.exists()


def test_resolve_target_matches_derive_target() -> None:
    facts = {"a.mp4": _clip("a.mp4")}
    plan = RenderPlan(
        look={"target_resolution": [1920, 1080]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    assert resolve_target(plan, _amd_profile(), facts) == derive_target(
        plan.look, [facts["a.mp4"]], _amd_profile()
    )


# --------------------------------------------------------------------------- #
# 9. Cooperative cancellation (job-scheduler, D-S6)                           #
# --------------------------------------------------------------------------- #


def test_cancel_before_first_segment_renders_nothing(runtime, make_clip, tmp_path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=out_dir,
        clip_facts=facts,
        runtime=runtime,
        should_cancel=lambda: True,
    )
    with pytest.raises(RenderCancelledError):
        render_movie(plan, CPUProfile(), options)
    assert not (out_dir / "Movie.mp4").exists()
    assert not (out_dir / "Movie.mp4.part").exists()


def test_cancel_stops_before_the_next_segment(runtime, make_clip, tmp_path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240, duration=1.0)
    clip_b = make_clip("b.mp4", width=320, height=240, duration=1.0)
    facts = {
        "a.mp4": probe_media(clip_a, runtime=runtime),
        "b.mp4": probe_media(clip_b, runtime=runtime),
    }
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(
            ResolvedChapter(name="Intro", clips=(ResolvedClip(identity="a.mp4"),)),
            ResolvedChapter(name="Main", clips=(ResolvedClip(identity="b.mp4"),)),
        ),
    )
    out_dir = tmp_path / "out"
    # Cancel takes effect once the first segment (index 0) has already started, so
    # segment 1 is never begun.
    seen: list[int] = []

    def _cancel_after_first() -> bool:
        return len(seen) >= 1

    real_build = orch._build_segment_command

    def _spy_build(index, *args, **kwargs):
        seen.append(index)
        return real_build(index, *args, **kwargs)

    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=out_dir,
        clip_facts=facts,
        runtime=runtime,
        should_cancel=_cancel_after_first,
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orch, "_build_segment_command", _spy_build)
        with pytest.raises(RenderCancelledError):
            render_movie(plan, CPUProfile(), options)

    assert seen == [0]
    assert not (out_dir / "Movie.mp4").exists()
    assert not (out_dir / "Movie.mp4.part").exists()


def test_cancel_requested_pre_render_never_starts(runtime, tmp_path) -> None:
    # should_cancel already true when render_movie is invoked (e.g. the job's
    # cancel_requested flag was set while queued): the very first segment boundary
    # check catches it, so no ffmpeg process is ever spawned.
    facts = {"missing.mp4": _clip("missing.mp4", width=320, height=240)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="missing.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=out_dir,
        clip_facts=facts,
        runtime=runtime,
        should_cancel=lambda: True,
    )
    with pytest.raises(RenderCancelledError):
        render_movie(plan, CPUProfile(), options)


def test_normalize_failure_is_surfaced_naming_segment(runtime, tmp_path) -> None:
    # The clip's facts mark it non-eligible (size mismatch) so it must normalize,
    # but the source file does not exist on disk -> ffmpeg exits non-zero. The
    # engine must raise a typed RenderError naming the segment, never drop it
    # (clip-normalize: "Normalize failure is surfaced, not swallowed").
    facts = {"missing.mp4": _clip("missing.mp4", width=320, height=240)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="missing.mp4"),)),),
    )
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime
    )
    with pytest.raises(RenderError, match=r"normalize failed for segment 0 .'missing.mp4'."):
        render_movie(plan, CPUProfile(), options)
    assert not (out_dir / "Movie.mp4").exists()


# --------------------------------------------------------------------------- #
# 8.3 GPU integration (skipped without a usable hardware accelerator)         #
# --------------------------------------------------------------------------- #


@pytest.mark.gpu
def test_end_to_end_hardware_render(runtime, make_clip, tmp_path) -> None:
    inventory = detect_capabilities(runtime)
    profile = select_profile(inventory)
    if profile.vendor is Vendor.CPU:
        pytest.skip("no usable hardware accelerator on this host")

    clip_a = make_clip("a.mp4", width=1280, height=720, fps=30, duration=1.0)
    clip_b = make_clip("b.mp4", width=1280, height=720, fps=30, duration=1.0)
    facts = {
        "a.mp4": probe_media(clip_a, runtime=runtime),
        "b.mp4": probe_media(clip_b, runtime=runtime),
    }
    plan = _two_chapter_plan({"target_resolution": [1920, 1080], "video_codec": "h264"})
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime
    )
    result = render_movie(plan, profile, options)
    assert result.output_path.exists()
    facts_out = probe_media(result.output_path, runtime=runtime)
    assert (facts_out.width, facts_out.height) == (1920, 1080)
    chapters = json.loads(
        runtime.run_ffprobe(
            ["-v", "error", "-show_chapters", "-print_format", "json", str(result.output_path)]
        ).stdout
    )["chapters"]
    assert len(chapters) == 2


# --------------------------------------------------------------------------- #
# vaapi-pad-fill: real-hardware checks (gpu marker)                           #
# --------------------------------------------------------------------------- #


def _region_stats(runtime, video: Path, crop: str) -> dict[str, float]:
    """Mean Y/U/V of ``crop`` (``w:h:x:y``) in the first frame of ``video``."""
    result = runtime.run(
        [
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            f"crop={crop},signalstats,metadata=mode=print:file=-",
            "-f",
            "null",
            "-",
        ]
    )
    stats: dict[str, float] = {}
    for line in result.stdout.splitlines():
        for key in ("YAVG", "UAVG", "VAVG"):
            prefix = f"lavfi.signalstats.{key}="
            if line.startswith(prefix):
                stats[key] = float(line[len(prefix) :])
    assert set(stats) == {"YAVG", "UAVG", "VAVG"}, result.stdout
    return stats


def _hardware_profile(runtime) -> VaapiProfile:
    profile = select_profile(detect_capabilities(runtime))
    if not isinstance(profile, VaapiProfile):
        pytest.skip(f"needs a VAAPI profile; this host selected {profile.vendor.value}")
    if "h264" not in profile.capabilities.usable_encoders:
        pytest.skip("no hardware h264 encoder on this host")
    return profile


def _render_one(runtime, profile: VaapiProfile, clip: Path, tmp_path: Path, **seg) -> Path:
    facts = probe_media(clip, runtime=runtime)
    target = _target(
        width=640,
        height=360,
        video_encoder=profile.capabilities.usable_encoders["h264"],
    )
    output = tmp_path / "seg.mp4"
    segment = _source_segment(identity=clip.name, source_path=clip, **seg)
    command = build_normalize_command(segment, facts, target, profile, output)
    runtime.run(list(command.args))
    meta = probe_media(output, runtime=runtime)
    assert (meta.width, meta.height) == (640, 360)
    return output


@pytest.mark.gpu
def test_detection_reports_faulty_pad_fill_on_mesa(runtime) -> None:
    inventory = detect_capabilities(runtime, force_refresh=True)
    amd = inventory.accelerator(Vendor.AMD)
    if amd is None or amd.pad_filter is None:
        pytest.skip("no AMD VAAPI pad on this host; the Mesa pad_vaapi fill defect is AMD-only")
    # exp 006: pad_vaapi runs (normalize usable) but paints its padded region green.
    assert amd.pad_filter == "pad_vaapi"
    assert amd.pad_fill_ok is False


@pytest.mark.gpu
def test_portrait_clip_gets_black_bars_on_the_detected_profile(runtime, tmp_path: Path) -> None:
    profile = _hardware_profile(runtime)
    clip = tmp_path / "portrait.mp4"
    runtime.run(
        ["-y", "-f", "lavfi", "-i", "color=white:size=360x640:rate=30:duration=1"]
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)]
    )
    output = _render_one(runtime, profile, clip, tmp_path)

    corner = _region_stats(runtime, output, "64:64:0:0")  # inside the left pillar
    assert abs(corner["UAVG"] - 128) <= 8, corner
    assert abs(corner["VAVG"] - 128) <= 8, corner
    assert corner["YAVG"] <= 24, corner


@pytest.mark.gpu
def test_rotated_clip_renders_through_the_vaapi_profile(runtime, tmp_path: Path) -> None:
    # CPU transpose between VAAPI decode and VAAPI encode: must hwupload back through
    # the shared named device instead of failing with "A hardware device reference
    # is required to upload frames to".
    profile = _hardware_profile(runtime)
    clip = tmp_path / "landscape.mp4"
    runtime.run(
        ["-y", "-f", "lavfi", "-i", "color=white:size=640x360:rate=30:duration=1"]
        + ["-vf", "drawbox=x=0:y=180:w=640:h=180:color=black:t=fill"]
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)]
    )
    output = _render_one(runtime, profile, clip, tmp_path, rotate=90)

    # transpose=1 turns clockwise: the white top half becomes the right half of a
    # portrait picture, pillarboxed (~203 px wide) in the middle of the 640x360 canvas.
    left = _region_stats(runtime, output, "40:200:240:80")
    right = _region_stats(runtime, output, "40:200:360:80")
    assert left["YAVG"] < 64 < 192 < right["YAVG"], (left, right)
    corner = _region_stats(runtime, output, "64:64:0:0")
    assert abs(corner["UAVG"] - 128) <= 8, corner
