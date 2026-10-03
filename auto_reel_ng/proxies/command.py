"""The ffmpeg arguments that make a proxy (D-21): one pure builder per encode path.

Two paths, both encoding with libx264:

* **hybrid** decodes and scales on the accelerator, downloads the frames and encodes on the
  CPU. It is used only where it is proven: an unrotated, SDR, 8-bit H.264 or HEVC clip the
  selected profile decodes in hardware, on a hardware frame context for which this module
  owns a verified scale filter (:data:`HARDWARE_SCALE_FILTERS`; one row today, added to only
  after a vendor's path is measured on that hardware, Principle III).
* **CPU** decodes in software (which applies the container's display rotation before the
  filter graph), tone-maps an HDR clip, scales to the exact planned size and encodes. It is
  the guaranteed fallback and the only path on a host with no usable accelerator.

Nothing here touches the file system or starts a process. No vendor is named: the location of
the decode fragment's frames is the capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from ..accel.models import FrameLocation, OpClass, OpParams
from ..accel.pixfmt import pix_fmt_traits
from ..accel.profiles import AccelProfile
from ..accel.profiles.cpu import CPU_TONEMAP_FILTER
from ..probe.metadata import ClipMetadata
from . import spec

#: Source codecs the hybrid path may decode on the accelerator (8-bit, per the profile).
HYBRID_CODECS = frozenset({"h264", "hevc"})

#: Where the accelerator's decoded frames live -> the scale filter that resizes them to an
#: exact size (no aspect option, so a non-square pixel is resolved by the planned size) and
#: leaves them as ``nv12`` for the download. Verified rows only.
HARDWARE_SCALE_FILTERS = {FrameLocation.VAAPI: "scale_vaapi=w={w}:h={h}:format=nv12"}

#: The bridge from hardware frames to system memory (the render's own ``hwdownload`` chain).
HARDWARE_DOWNLOAD = "hwdownload,format=nv12"


class EncodePath(str, Enum):
    """How a proxy is encoded; recorded in the entry's facts."""

    HYBRID = "hybrid"
    CPU = "cpu"


@dataclass(frozen=True)
class ProxyCommand:
    """One ffmpeg invocation: its arguments, its path and the size it should produce."""

    args: tuple[str, ...]
    path: EncodePath
    width: int
    height: int
    #: The source's probed duration, which the progress fraction is measured against.
    duration: float


def plan_encode(
    clip: ClipMetadata, profile: AccelProfile, *, render_node: Optional[str] = None
) -> EncodePath:
    """The encode path for ``clip`` on ``profile``: ``HYBRID`` only where all conditions hold.

    All of: the clip is 8-bit; the profile decodes the clip's codec and pixel format on its
    hardware (its own answer, D-18); the clip is H.264 or HEVC; it carries no display rotation
    (GPU rotation of an HEVC clip produced a wrong picture without an error); it is not HDR
    (every GPU tone-map path faults on the supported hardware); and the profile's decoded
    frames live where :data:`HARDWARE_SCALE_FILTERS` has a verified scale filter. Everything
    else is ``CPU``.
    """
    if clip.video_codec not in HYBRID_CODECS or clip.is_hdr:
        return EncodePath.CPU
    if (clip.rotation or 0) % 360 != 0:
        return EncodePath.CPU
    traits = pix_fmt_traits(clip.pix_fmt) if clip.pix_fmt else None
    if traits is None or traits[0] != 8:  # 8-bit only; an unknown format is not guessed at
        return EncodePath.CPU
    if not profile.can_hw_decode(clip.video_codec, clip.pix_fmt):
        return EncodePath.CPU
    decode = profile.fragment(OpClass.DECODE, OpParams(render_node=render_node))
    if decode.frames_out not in HARDWARE_SCALE_FILTERS:
        return EncodePath.CPU
    return EncodePath.HYBRID


def build_proxy_command(  # pylint: disable=too-many-arguments
    clip: ClipMetadata,
    *,
    source: Path,
    output: Path,
    path: EncodePath,
    profile: AccelProfile,
    render_node: Optional[str] = None,
    size: tuple[int, int],
) -> ProxyCommand:
    """The ffmpeg arguments that encode ``source`` into ``output`` on ``path`` at ``size``.

    ``size`` is the planned display size (:func:`~.spec.proxy_dimensions`). The hybrid path
    takes the profile's own decode flags, so the device recipe lives in one place. A clip
    without audio gets no audio options at all (no silence is synthesised), and the audio
    encoder is always :data:`~.spec.PROXY_AUDIO_ENCODER`.

    Raises:
        ValueError: ``path`` is ``HYBRID`` but the profile's decode frames have no verified
            scale filter (the planner never returns that).
    """
    width, height = size
    args: list[str] = ["-hide_banner", "-nostdin", "-y"]
    if path is EncodePath.HYBRID:
        decode = profile.fragment(OpClass.DECODE, OpParams(render_node=render_node))
        scale = HARDWARE_SCALE_FILTERS.get(decode.frames_out)
        if scale is None:
            raise ValueError(f"no verified hardware scale filter for {decode.frames_out.value}")
        args += decode.input_flags
        video_filter = ",".join([scale.format(w=width, h=height), HARDWARE_DOWNLOAD, "setsar=1"])
    else:
        steps = [CPU_TONEMAP_FILTER] if clip.is_hdr else []
        steps += [f"scale={width}:{height}:flags=bicubic", "setsar=1"]
        video_filter = ",".join(steps)
    args += ["-i", str(source), "-map", "0:v:0", "-vf", video_filter]
    args += ["-fps_mode", "passthrough"]
    args += [
        "-c:v",
        "libx264",
        "-preset",
        spec.PROXY_PRESET,
        "-crf",
        str(spec.PROXY_CRF),
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-bf",
        str(spec.PROXY_BFRAMES),
        "-g",
        str(spec.gop_frames(clip.fps)),
        "-sc_threshold",
        "0",
    ]
    if clip.has_audio:
        args += [
            "-map",
            "0:a:0",
            "-c:a",
            spec.PROXY_AUDIO_ENCODER,
            "-b:a",
            spec.PROXY_AUDIO_BITRATE,
            "-ac",
            str(spec.PROXY_AUDIO_CHANNELS),
        ]
    args += ["-movflags", "+faststart", str(output)]
    return ProxyCommand(
        args=tuple(args), path=path, width=width, height=height, duration=clip.duration
    )


__all__ = [
    "HARDWARE_DOWNLOAD",
    "HARDWARE_SCALE_FILTERS",
    "HYBRID_CODECS",
    "EncodePath",
    "ProxyCommand",
    "build_proxy_command",
    "plan_encode",
]
