"""Per-segment normalize command builder + copy-eligibility (clip-normalize).

Composes the ffmpeg command that turns one :class:`Segment` into a
target-conforming intermediate: decode, fix rotation and pixel aspect, scale +
letterbox/pillarbox pad to the canvas, tonemap HDR->SDR, composite overlays,
normalize audio (or synthesize silence), and encode — every fragment requested
from the selected :class:`AccelProfile`, with explicit hardware<->system
transfers (decision **D-C/D-F**) and a guaranteed CPU fallback for every op.

The builder is **pure** (decision **D-G**): it returns a :class:`NormalizeCommand`
of ffmpeg args without touching the filesystem, so it is golden-string testable
without a GPU. The side-effecting run lives in the orchestrator.

Also decides, per segment, whether it can skip normalization entirely — the
stream-copy fast path (decision **D-D**) — from probe data alone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Optional

from ..accel.models import FrameLocation, OpClass, OpParams
from ..accel.profiles.base import AccelProfile, needs_transfer
from ..errors import RenderError
from ..probe.metadata import ClipMetadata
from .producers import ProducedSegment
from .segments import OverlaySpec, Segment
from .target import TargetSpec

logger = logging.getLogger(__name__)

#: Logged (and carried on the command) when an HDR clip must tonemap on the CPU.
HDR_SLOWNESS_WARNING = (
    "HDR clip tonemapped on the CPU (no usable hardware tonemap); this segment "
    "will render substantially slower than realtime"
)


@dataclass(frozen=True)
class NormalizeCommand:
    """A pure description of one segment's normalize invocation.

    ``args`` are the ffmpeg arguments after the binary; ``duration`` is the
    expected output length (for the ``-progress`` fraction); ``warnings`` carries
    any loud advisories (e.g. CPU HDR tonemap) for the caller to surface.
    """

    args: tuple[str, ...]
    output_path: Path
    duration: float
    warnings: tuple[str, ...] = ()
    #: Whether the decode runs on the accelerator (its DECODE fragment leaves frames in
    #: hardware memory). The orchestrator retries only such a command in software.
    hardware_decode: bool = False


@dataclass(frozen=True)
class _Stage:
    """One video-filter stage with its frame locations, for transfer insertion."""

    filter: Optional[str]
    frames_in: FrameLocation
    frames_out: FrameLocation


def _fmt(value: float) -> str:
    """Format a numeric ffmpeg argument compactly and deterministically."""
    return f"{value:g}"


def _channel_layout(channels: int) -> str:
    """Map a channel count to an ffmpeg channel-layout name for ``anullsrc``."""
    return {1: "mono", 2: "stereo", 6: "5.1", 8: "7.1"}.get(channels, "stereo")


def _transpose_filter(rotate: int) -> str:
    """CPU transpose chain that uprights ``rotate`` degrees of display rotation."""
    mapping = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}
    normalized = rotate % 360
    if normalized not in mapping:
        raise RenderError(f"unsupported rotation {rotate!r}; expected 90, 180, or 270")
    return mapping[normalized]


def _transfer_filter(name: str) -> str:
    """Expand a transfer marker into a concrete bridging filter."""
    if name == "hwdownload":
        return "hwdownload,format=nv12"
    if name == "hwupload":
        return "format=nv12,hwupload"
    return name  # pragma: no cover - needs_transfer only emits the two above


def _upload_device_flags(profile: AccelProfile, params: OpParams) -> tuple[str, ...]:
    """The profile's upload-device flags, or a loud error when it has none.

    Called only for a chain that uploads system frames with no hardware decode to
    open a device, where ffmpeg would otherwise fail with "A hardware device
    reference is required to upload frames to".
    """
    flags = profile.upload_device_flags(params)
    if not flags:
        raise RenderError(
            f"the {profile.vendor.value} profile has no verified device for uploading "
            "system-memory frames to its hardware encoder; render with --device cpu"
        )
    return flags


def _overlay_enable(overlay: OverlaySpec) -> Optional[str]:
    """Return an ``enable=`` timeline expression for ``overlay``, or ``None``."""
    if overlay.start <= 0.0 and overlay.end is None:
        return None
    if overlay.end is None:
        return f"gte(t,{_fmt(overlay.start)})"
    return f"between(t,{_fmt(overlay.start)},{_fmt(overlay.end)})"


def _needs_pad(clip: ClipMetadata, rotate: Optional[int], target: TargetSpec) -> bool:
    """Whether normalizing ``clip`` onto the canvas leaves a region to pad.

    Compared as exact ratios, so a 1920x1088 clip needs padding and every exact 16:9
    size does not. Both the pixel aspect (what the aspect-preserving scale sees; no
    scale honours SAR) and the display aspect (SAR applied) must match the canvas.
    The segment's explicit ``rotate`` wins over the clip's own rotation metadata.
    """
    quarter_turn = (rotate or clip.rotation or 0) % 180 == 90
    width, height = (clip.height, clip.width) if quarter_turn else (clip.width, clip.height)
    canvas = Fraction(target.width, target.height)
    sar = Fraction(_normalize_sar(clip.sample_aspect_ratio).replace(":", "/"))
    pixel_aspect = Fraction(width, height)
    return pixel_aspect != canvas or pixel_aspect * sar != canvas


def _canvas_stages(
    segment: Segment, clip: ClipMetadata, profile: AccelProfile, params: OpParams
) -> list[_Stage]:
    """Build the rotation -> normalize -> tonemap video stages (design order)."""
    stages: list[_Stage] = []
    if segment.rotate:
        stages.append(
            _Stage(_transpose_filter(segment.rotate), FrameLocation.SYSTEM, FrameLocation.SYSTEM)
        )
    normalize = profile.fragment(OpClass.NORMALIZE, params)
    stages.append(_Stage(normalize.filter, normalize.frames_in, normalize.frames_out))
    if clip.is_hdr:
        tonemap = profile.fragment(OpClass.TONEMAP, params)
        stages.append(_Stage(tonemap.filter, tonemap.frames_in, tonemap.frames_out))
    return stages


def _compose_linear(stages: list[_Stage], start_loc: FrameLocation, end_loc: FrameLocation) -> str:
    """Compose ``stages`` into a comma-joined filter chain, inserting transfers."""
    parts: list[str] = []
    loc = start_loc
    for stage in stages:
        transfer = needs_transfer(loc, stage.frames_in)
        if transfer is not None:
            parts.append(_transfer_filter(transfer))
        if stage.filter:
            parts.append(stage.filter)
        loc = stage.frames_out
    transfer = needs_transfer(loc, end_loc)
    if transfer is not None:
        parts.append(_transfer_filter(transfer))
    return ",".join(parts)


def _build_video_graph(
    segment: Segment,
    clip: ClipMetadata,
    profile: AccelProfile,
    params: OpParams,
    *,
    decode_out: FrameLocation,
    encode_in: FrameLocation,
) -> tuple[str, str, list[str], Optional[str]]:
    """Return ``(flag, value, extra_input_args, map_label)`` for the video chain.

    Overlay-free segments use a linear ``-vf`` chain on the hardware path; a
    segment carrying overlays switches to ``-filter_complex`` with a CPU bridge
    around the overlay (the AMD path, ``can_overlay_hw=False``).
    """
    canvas = _canvas_stages(segment, clip, profile, params)
    if not segment.overlays:
        return ("-vf", _compose_linear(canvas, decode_out, encode_in), [], None)

    overlay_fragment = profile.fragment(OpClass.OVERLAY, params)
    overlay_loc = overlay_fragment.frames_in
    pre = _compose_linear(canvas, decode_out, overlay_loc)

    chains: list[str] = []
    current = "0:v"
    if pre:
        chains.append(f"[0:v]{pre}[vbase]")
        current = "vbase"

    extra_inputs: list[str] = []
    for index, overlay in enumerate(segment.overlays):
        input_index = 1 + index
        extra_inputs += ["-i", overlay.source]
        expr = f"{overlay_fragment.filter}=x={overlay.x}:y={overlay.y}"
        enable = _overlay_enable(overlay)
        if enable is not None:
            expr += f":enable='{enable}'"
        out_label = f"vo{index}"
        chains.append(f"[{current}][{input_index}:v]{expr}[{out_label}]")
        current = out_label

    tail = needs_transfer(overlay_loc, encode_in)
    if tail is not None:
        chains.append(f"[{current}]{_transfer_filter(tail)}[vout]")
        current = "vout"

    return ("-filter_complex", ";".join(chains), extra_inputs, f"[{current}]")


def build_normalize_command(
    segment: Segment,
    clip: ClipMetadata,
    target: TargetSpec,
    profile: AccelProfile,
    output_path: Path,
    *,
    render_node: Optional[str] = None,
    force_software_decode: bool = False,
) -> NormalizeCommand:
    """Build the ffmpeg command that normalizes ``segment`` to ``target``.

    Realizes the kept span via in/out seeking, composes the video chain from
    profile fragments with explicit transfers, normalizes audio to the target
    params (synthesizing silence for video-only clips), and encodes to the
    target codec. A synthetic segment is rejected here: it is materialized through
    its producer and built by :func:`build_synthetic_normalize_command` instead, so
    routing a synthetic segment through the source path fails loud rather than
    silently mis-encoding it.

    The decode is chosen per clip: a clip the profile reports as not hardware-decodable
    (its codec or pixel format is outside the accelerator's decoder), or any clip when
    ``force_software_decode`` is set, is decoded in software and uploaded through the
    ordinary frame-location transfers. A hardware-decodable clip is unchanged, and so is
    every clip on a profile that has no upload device to offer (it is never moved to a
    software decode it cannot upload from, short of ``force_software_decode``).
    """
    if segment.is_synthetic:
        raise RenderError(
            f"synthetic segment (producer {segment.producer!r}) must be built via "
            f"build_synthetic_normalize_command, not the source-segment path"
        )

    params = OpParams(
        width=target.width,
        height=target.height,
        codec=target.video_codec,
        render_node=render_node,
        fill_color=target.fill_color,
        needs_pad=_needs_pad(clip, segment.rotate, target),
    )
    # A software decode feeding a hardware encoder needs an upload device. A profile with
    # no verified recipe for one (NVIDIA, Intel) keeps attempting its own hardware decode,
    # exactly as before this choice existed; only a forced retry asks it for software.
    can_upload = bool(profile.upload_device_flags(params))
    hw_decodable = profile.can_hw_decode(clip.video_codec, clip.pix_fmt) or not can_upload
    if not hw_decodable and profile.fragment(OpClass.DECODE, params).frames_out is not (
        FrameLocation.SYSTEM
    ):
        # Expected, not an error: the accelerator decodes some codecs, just not this one.
        logger.info(
            "%s: %s %s is not hardware-decodable on the %s profile; decoding in software",
            segment.identity,
            clip.video_codec,
            clip.pix_fmt or "(unknown pix_fmt)",
            profile.vendor.value,
        )
    params = replace(params, software_decode=force_software_decode or not hw_decodable)
    decode = profile.fragment(OpClass.DECODE, params)
    encode = profile.fragment(OpClass.ENCODE, params)

    warnings: list[str] = []
    if clip.is_hdr:
        tonemap = profile.fragment(OpClass.TONEMAP, params)
        if tonemap.frames_in is FrameLocation.SYSTEM and tonemap.frames_out is FrameLocation.SYSTEM:
            warnings.append(HDR_SLOWNESS_WARNING)
            logger.warning("%s: %s", segment.identity, HDR_SLOWNESS_WARNING)

    flag, value, overlay_inputs, map_label = _build_video_graph(
        segment, clip, profile, params, decode_out=decode.frames_out, encode_in=encode.frames_in
    )

    duration = segment.span_duration if segment.span_duration is not None else clip.duration

    # A software decode opens no device, so a chain that uploads to a hardware
    # encoder must name one; a hardware decode names its own, shared with filters.
    device_flags: tuple[str, ...] = ()
    if decode.frames_out is FrameLocation.SYSTEM and _transfer_filter("hwupload") in value:
        device_flags = _upload_device_flags(profile, params)

    args: list[str] = ["-y", *device_flags, *decode.input_flags]
    if segment.start is not None:
        args += ["-ss", _fmt(segment.start)]
    args += ["-i", str(segment.source_path)]
    args += overlay_inputs

    silence_input_index = 1 + len(segment.overlays)
    if clip.has_audio:
        audio_map = "0:a:0"
    else:
        layout = _channel_layout(target.audio_channels)
        args += [
            "-f",
            "lavfi",
            "-t",
            _fmt(duration),
            "-i",
            f"anullsrc=channel_layout={layout}:sample_rate={target.audio_sample_rate}",
        ]
        audio_map = f"{silence_input_index}:a:0"

    if value:
        args += [flag, value]
    args += ["-map", map_label if map_label is not None else "0:v:0"]
    args += ["-map", audio_map]

    args += ["-r", _fmt(target.fps)]
    args += list(encode.output_flags)
    # A software -pix_fmt is only valid when the encoder ingests system frames. A
    # hardware encoder (VAAPI/CUDA/QSV) consumes GPU surfaces, and ffmpeg >= 8
    # rejects an explicit ``-pix_fmt yuv420p`` against them ("Incompatible pixel
    # format ... for codec 'h264_vaapi'"); let ffmpeg select the surface format.
    if encode.frames_in is FrameLocation.SYSTEM:
        args += ["-pix_fmt", target.pix_fmt]
    if segment.is_trimmed:
        args += ["-t", _fmt(duration)]
    args += [
        "-c:a",
        target.audio_codec,
        "-ar",
        str(target.audio_sample_rate),
        "-ac",
        str(target.audio_channels),
    ]
    args += [str(output_path)]

    return NormalizeCommand(
        args=tuple(args),
        output_path=Path(output_path),
        duration=duration,
        warnings=tuple(warnings),
        hardware_decode=decode.frames_out is not FrameLocation.SYSTEM,
    )


def build_synthetic_normalize_command(
    segment: Segment,
    produced: ProducedSegment,
    target: TargetSpec,
    profile: AccelProfile,
    output_path: Path,
    *,
    render_node: Optional[str] = None,
) -> NormalizeCommand:
    """Build the ffmpeg command that encodes a materialized synthetic segment (D-D).

    Loops the producer's rendered image for the segment duration, applies a
    fade-in/fade-out over the producer-supplied timings, synthesizes a silent audio
    track at the target audio params (the same path video-only clips use), and
    encodes to the target codec/pix_fmt/fps/resolution. The path is **overlay-free**
    — it never uses ``overlay``/``overlay_vaapi`` or a CPU overlay bridge — so the
    card renders fully through the encode on every vendor, including AMD where
    ``overlay_vaapi`` is unavailable.
    """
    if not segment.is_synthetic:
        raise RenderError(
            f"build_synthetic_normalize_command requires a synthetic segment, got {segment!r}"
        )

    params = OpParams(
        width=target.width,
        height=target.height,
        codec=target.video_codec,
        render_node=render_node,
        fill_color=target.fill_color,
    )
    encode = profile.fragment(OpClass.ENCODE, params)
    duration = produced.duration

    # See build_normalize_command: emit a software -pix_fmt only for a system-frame
    # encoder; a hardware encoder consumes GPU surfaces and ffmpeg >= 8 rejects it.
    pix_fmt_flags: tuple[str, ...] = (
        ("-pix_fmt", target.pix_fmt) if encode.frames_in is FrameLocation.SYSTEM else ()
    )

    # A static image stays in system memory: a CPU scale+pad guard conforms it to
    # the canvas (a no-op when it was authored on-size), then fades, then — only if
    # the encoder wants hardware frames — a single hwupload. No overlay anywhere.
    filters = [
        f"scale={target.width}:{target.height}:force_original_aspect_ratio=decrease",
        f"pad={target.width}:{target.height}:(ow-iw)/2:(oh-ih)/2:{target.fill_color}",
        "setsar=1",
    ]
    if produced.fade_in > 0.0:
        filters.append(f"fade=t=in:st=0:d={_fmt(produced.fade_in)}")
    if produced.fade_out > 0.0:
        start = max(0.0, duration - produced.fade_out)
        filters.append(f"fade=t=out:st={_fmt(start)}:d={_fmt(produced.fade_out)}")
    transfer = needs_transfer(FrameLocation.SYSTEM, encode.frames_in)
    device_flags: tuple[str, ...] = ()
    if transfer is not None:
        filters.append(_transfer_filter(transfer))
        # The image never passed through a hardware decoder, so nothing has opened
        # a device for hwupload to upload into.
        device_flags = _upload_device_flags(profile, params)
    vf = ",".join(filters)

    layout = _channel_layout(target.audio_channels)
    args: list[str] = [
        "-y",
        *device_flags,
        "-loop",
        "1",
        "-t",
        _fmt(duration),
        "-i",
        str(produced.image_path),
        "-f",
        "lavfi",
        "-t",
        _fmt(duration),
        "-i",
        f"anullsrc=channel_layout={layout}:sample_rate={target.audio_sample_rate}",
        "-vf",
        vf,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-r",
        _fmt(target.fps),
        *encode.output_flags,
        *pix_fmt_flags,
        "-t",
        _fmt(duration),
        "-c:a",
        target.audio_codec,
        "-ar",
        str(target.audio_sample_rate),
        "-ac",
        str(target.audio_channels),
        str(output_path),
    ]
    return NormalizeCommand(
        args=tuple(args),
        output_path=Path(output_path),
        duration=duration,
    )


def _normalize_sar(sample_aspect_ratio: Optional[str]) -> str:
    """Treat an absent/``N/A`` SAR as square (1:1) for equivalence comparison."""
    if sample_aspect_ratio is None or sample_aspect_ratio in ("", "N/A", "0:1"):
        return "1:1"
    return sample_aspect_ratio


def copy_eligible(segment: Segment, clip: Optional[ClipMetadata], target: TargetSpec) -> bool:
    """Decide whether ``segment`` can skip normalization (the stream-copy path).

    Copy-eligible only when the segment is a **source** segment that is
    **untrimmed**, has **no overlays**, needs **no rotation or tonemap**, and
    whose probed video and audio parameters already equal the target spec.
    Synthetic segments are never eligible.
    """
    if segment.is_synthetic or not segment.is_full_clip:
        return False
    if segment.overlays or segment.rotate:
        return False
    if clip is None or clip.is_hdr or clip.audio is None:
        return False
    video_ok = (
        clip.width == target.width
        and clip.height == target.height
        and _normalize_sar(clip.sample_aspect_ratio) == target.sample_aspect_ratio
        and clip.pix_fmt == target.pix_fmt
        and clip.video_codec == target.video_codec
        and abs(clip.fps - target.fps) <= 1e-3
    )
    audio_ok = (
        clip.audio.codec == target.audio_codec
        and clip.audio.sample_rate == target.audio_sample_rate
        and clip.audio.channels == target.audio_channels
    )
    return video_ok and audio_ok


def decide_copy_eligibility(
    segments: tuple[Segment, ...],
    clip_facts: Mapping[str, ClipMetadata],
    target: TargetSpec,
) -> tuple[Segment, ...]:
    """Return ``segments`` with each ``copy_eligible`` flag decided from probe data."""
    decided: list[Segment] = []
    for segment in segments:
        clip = clip_facts.get(segment.identity) if segment.identity is not None else None
        decided.append(replace(segment, copy_eligible=copy_eligible(segment, clip, target)))
    return tuple(decided)


__all__ = [
    "NormalizeCommand",
    "HDR_SLOWNESS_WARNING",
    "build_normalize_command",
    "build_synthetic_normalize_command",
    "copy_eligible",
    "decide_copy_eligibility",
]
