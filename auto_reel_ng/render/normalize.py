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
from ..accel.profiles.cpu import CPUProfile
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
class AudioSidecar:
    """A second output of a normalize command: the audio of a whole segment, encoded once.

    A segment split at its card window is encoded as two video-only pieces; the one command that
    encodes the later piece also cuts the audio of the *whole* segment (``start`` seconds into
    the clip, ``duration`` long; ``None`` start for a whole clip) from the source into ``path``,
    in parallel with its video. A join then copies video and audio together, with no second AAC
    stream and so no encoder-delay gap inside continuous footage.
    """

    path: Path
    start: Optional[float]
    duration: float


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


def display_turn(clip: ClipMetadata) -> int:
    """The clockwise turn (0/90/180/270) that applies the clip's own display rotation.

    The probe reports the display matrix's angle, which is counter-clockwise (a phone
    clip with matrix -90 probes as 270), so the turn that uprights it is the complement.
    This and :func:`total_turn` are the only readers of ``clip.rotation`` for a render.
    """
    return (360 - (clip.rotation or 0)) % 360


def total_turn(clip: ClipMetadata, rotate: Optional[int]) -> int:
    """The clockwise turn the engine applies: display rotation plus the segment's ``rotate``.

    ``rotate`` is an *extra* turn on top of how the clip plays (``reel-document``), so the
    two add modulo 360 instead of one replacing the other.
    """
    return (display_turn(clip) + (rotate or 0)) % 360


def _transpose_filter(turn: int) -> str:
    """CPU transpose chain for a clockwise ``turn`` of 90, 180 or 270 degrees."""
    mapping = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}
    normalized = turn % 360
    if normalized not in mapping:
        raise RenderError(f"unsupported rotation {turn!r}; expected 90, 180, or 270")
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


#: A window shorter than the asked one by less than this is not a clamp (probe rounding).
_CLAMP_TOLERANCE_S = 1e-3


def _clamp_timed_overlays(
    segment: Segment, duration: float
) -> tuple[tuple[OverlaySpec, ...], list[str]]:
    """Clamp each timed overlay's window to the segment's ``duration``; collect the warnings.

    A timed overlay (one that fades) shows from the segment's start for its ``end`` seconds. When
    that is longer than the segment the window becomes the segment's length, the fades shrink
    together (the same proportional rule as the title card's own fade clamp) so their sum fits the
    window, and a warning names the segment, the asked and the shown seconds. Other overlays pass
    through untouched.

    Raises:
        RenderError: a timed overlay that does not start at the segment's start.
    """
    out: list[OverlaySpec] = []
    warnings: list[str] = []
    for overlay in segment.overlays:
        if not overlay.is_timed:
            out.append(overlay)
            continue
        if overlay.start != 0.0:
            raise RenderError(
                f"segment {segment.identity}: a timed overlay starts at the segment's start, "
                f"got start={overlay.start}"
            )
        asked = overlay.end if overlay.end is not None else duration
        window = min(asked, duration)
        fade_in, fade_out = overlay.fade_in, overlay.fade_out
        if asked - window > _CLAMP_TOLERANCE_S:
            warnings.append(
                f"segment {segment.identity}: overlay shown for {_fmt(window)} s of the "
                f"{_fmt(asked)} s asked, the segment is only {_fmt(window)} s long"
            )
        if fade_in + fade_out > window:
            scale = window / (fade_in + fade_out)
            fade_in, fade_out = fade_in * scale, fade_out * scale
        out.append(replace(overlay, end=window, fade_in=fade_in, fade_out=fade_out))
    return tuple(out), warnings


def _clamped(segment: Segment, duration: float, warnings: list[str]) -> Segment:
    """``segment`` with its timed overlays clamped; the clamp warnings are logged and appended."""
    overlays, clamp_warnings = _clamp_timed_overlays(segment, duration)
    for warning in clamp_warnings:
        logger.warning("%s", warning)
    warnings.extend(clamp_warnings)
    return replace(segment, overlays=overlays)


def _timed_overlay_chain(overlay: OverlaySpec, input_index: int, label: str) -> str:
    """The filter chain that turns the looped card still into an alpha-faded overlay stream."""
    window = overlay.end if overlay.end is not None else 0.0
    parts = ["format=rgba"]
    if overlay.fade_in > 0.0:
        parts.append(f"fade=t=in:st=0:d={_fmt(overlay.fade_in)}:alpha=1")
    if overlay.fade_out > 0.0:
        parts.append(
            f"fade=t=out:st={_fmt(max(0.0, window - overlay.fade_out))}"
            f":d={_fmt(overlay.fade_out)}:alpha=1"
        )
    return f"[{input_index}:v]{','.join(parts)}[{label}]"


def _needs_pad(clip: ClipMetadata, turn: int, target: TargetSpec) -> bool:
    """Whether normalizing ``clip`` onto the canvas leaves a region to pad.

    Compared as exact ratios, so a 1920x1088 clip needs padding and every exact 16:9
    size does not. Both the pixel aspect (what the aspect-preserving scale sees; no
    scale honours SAR) and the display aspect (SAR applied) must match the canvas.
    ``turn`` is the clockwise total (:func:`total_turn`): a quarter turn swaps width and
    height, and a clip turned back to its stored orientation is judged by its stored shape.
    """
    quarter_turn = turn % 180 == 90
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
    if (clip.rotation or 0) % 90:
        raise RenderError(
            f"{clip.path.name}: display rotation {clip.rotation} is not a multiple of 90; "
            "only quarter turns can be normalized"
        )
    turn = total_turn(clip, segment.rotate)
    if turn:
        stages.append(_Stage(_transpose_filter(turn), FrameLocation.SYSTEM, FrameLocation.SYSTEM))
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
    fps: float,
) -> tuple[str, str, list[str], Optional[str]]:
    """Return ``(flag, value, extra_input_args, map_label)`` for the video chain.

    Overlay-free segments use a linear ``-vf`` chain on the hardware path; a
    segment carrying overlays switches to ``-filter_complex`` with a CPU bridge
    around the overlay (the AMD path, ``can_overlay_hw=False``). A *timed* overlay (it fades) is a
    still looped for its window at ``fps``, faded on its alpha channel and composited with the CPU
    ``overlay`` whatever the profile; every overlay of such a segment then uses the CPU one.
    """
    canvas = _canvas_stages(segment, clip, profile, params)
    if not segment.overlays:
        return ("-vf", _compose_linear(canvas, decode_out, encode_in), [], None)

    timed = any(overlay.is_timed for overlay in segment.overlays)
    overlay_fragment = (CPUProfile() if timed else profile).fragment(OpClass.OVERLAY, params)
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
        overlay_stream = f"{input_index}:v"
        if overlay.is_timed:
            window = overlay.end if overlay.end is not None else 0.0
            extra_inputs += ["-loop", "1", "-framerate", _fmt(fps), "-t", _fmt(window)]
            chains.append(_timed_overlay_chain(overlay, input_index, f"ov{index}"))
            overlay_stream = f"ov{index}"
        extra_inputs += ["-i", overlay.source]
        expr = f"{overlay_fragment.filter}=x={overlay.x}:y={overlay.y}"
        if overlay.is_timed:
            # The default output format makes a following ``format=nv12,hwupload`` fail on
            # Mesa ("Failed to upload frame"); ``auto`` keeps the base picture's format.
            expr += ":format=auto"
        enable = _overlay_enable(overlay)
        if enable is not None:
            expr += f":enable='{enable}'"
        out_label = f"vo{index}"
        chains.append(f"[{current}][{overlay_stream}]{expr}[{out_label}]")
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
    audio: bool | AudioSidecar = True,
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

    ``audio=False`` writes a video-only intermediate (``-an``: no audio map, no silence input).
    It is for a piece of a segment split at its card window, whose audio is encoded once for
    the whole segment: an :class:`AudioSidecar` as ``audio`` writes a video-only intermediate
    and adds that audio as a second output of the one command, and
    :func:`~auto_reel_ng.render.card_window.build_join_command` copies it in beside the joined
    video.
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
        needs_pad=_needs_pad(clip, total_turn(clip, segment.rotate), target),
    )
    if display_turn(clip) and segment.rotate:
        logger.info(
            "%s: display rotation %d + rotate %d = a %d degree clockwise turn",
            segment.identity,
            display_turn(clip),
            segment.rotate,
            total_turn(clip, segment.rotate),
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

    duration = segment.span_duration if segment.span_duration is not None else clip.duration
    segment = _clamped(segment, duration, warnings)

    flag, value, overlay_inputs, map_label = _build_video_graph(
        segment,
        clip,
        profile,
        params,
        decode_out=decode.frames_out,
        encode_in=encode.frames_in,
        fps=target.fps,
    )

    # A software decode opens no device, so a chain that uploads to a hardware
    # encoder must name one; a hardware decode names its own, shared with filters.
    device_flags: tuple[str, ...] = ()
    if decode.frames_out is FrameLocation.SYSTEM and _transfer_filter("hwupload") in value:
        device_flags = _upload_device_flags(profile, params)

    args: list[str] = ["-y", *device_flags, *decode.input_flags]
    if display_turn(clip):
        # The engine applies the display rotation itself (in the filter chain, the same on
        # every profile); ffmpeg's own would run twice on the CPU and not at all on VAAPI.
        args.append("-noautorotate")
    if segment.start is not None:
        args += ["-ss", _fmt(segment.start)]
    args += ["-i", str(segment.source_path)]
    args += overlay_inputs

    extra_args, audio_map = _extra_audio_input(
        clip,
        target,
        audio,
        input_index=1 + len(segment.overlays),
        duration=duration,
        source=segment.source_path,
    )
    args += extra_args

    if value:
        args += [flag, value]
    args += ["-map", map_label if map_label is not None else "0:v:0"]
    if audio is True:
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
    args += list(_audio_encode_flags(target)) if audio is True else ["-an"]
    args += [str(output_path)]
    if isinstance(audio, AudioSidecar):
        args += ["-map", audio_map, *_audio_encode_flags(target), str(audio.path)]

    return NormalizeCommand(
        args=tuple(args),
        output_path=Path(output_path),
        duration=duration,
        warnings=tuple(warnings),
        hardware_decode=decode.frames_out is not FrameLocation.SYSTEM,
    )


def _extra_audio_input(
    clip: ClipMetadata,
    target: TargetSpec,
    audio: bool | AudioSidecar,
    *,
    input_index: int,
    duration: float,
    source: Optional[Path],
) -> tuple[list[str], str]:
    """The extra input arguments a command's audio needs, and the stream label to map for it.

    A muxed track (``audio`` true) of a clip without audio gets synthesized silence as input
    ``input_index``; a sidecar reads the clip again for its audio alone (the hardware-decode
    flags belong to the first input only) or, for a clip without audio, silence of its length.
    """
    if isinstance(audio, AudioSidecar) and clip.has_audio:
        args: list[str] = []
        if audio.start is not None:
            args += ["-ss", _fmt(audio.start)]
        return [*args, "-t", _fmt(audio.duration), "-i", str(source)], f"{input_index}:a:0"
    if audio is False or clip.has_audio:
        return [], "0:a:0"
    length = audio.duration if isinstance(audio, AudioSidecar) else duration
    layout = _channel_layout(target.audio_channels)
    silence = f"anullsrc=channel_layout={layout}:sample_rate={target.audio_sample_rate}"
    return ["-f", "lavfi", "-t", _fmt(length), "-i", silence], f"{input_index}:a:0"


def _audio_encode_flags(target: TargetSpec) -> tuple[str, ...]:
    """The audio codec, rate and channel flags every normalize command ends with."""
    return (
        "-c:a",
        target.audio_codec,
        "-ar",
        str(target.audio_sample_rate),
        "-ac",
        str(target.audio_channels),
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
    A clip with a display rotation, or a segment with a ``rotate`` that is not a
    multiple of 360, needs rotation even when the two cancel: a stream copy would
    carry the display matrix into the movie. Synthetic segments are never eligible.
    """
    if segment.is_synthetic or not segment.is_full_clip:
        return False
    if segment.overlays or (segment.rotate or 0) % 360:
        return False
    if clip is None or clip.is_hdr or clip.audio is None or display_turn(clip):
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
    "AudioSidecar",
    "NormalizeCommand",
    "HDR_SLOWNESS_WARNING",
    "build_normalize_command",
    "build_synthetic_normalize_command",
    "copy_eligible",
    "decide_copy_eligibility",
    "display_turn",
    "total_turn",
]
