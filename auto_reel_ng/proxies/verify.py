"""Post-encode verification: a proxy is probed and compared with its source before it is
published (D-21, Principle I).

The research found a silent wrong output (GPU rotation of an HEVC clip gave a picture with
SSIM 0.47 and no error). The encode ladder keeps such clips off the hardware, and this check
is the structural net under it: streams, size, pixel shape, duration and frame count. It
cannot see a correctly sized and timed proxy of a wrong picture; the real-encode tests cover
that by pixel position. No tolerance is widened and no check is skipped except the one whose
input does not exist (a container that declares no frame count).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ..errors import FfmpegError, ProxyError
from ..ffmpeg.runtime import FfmpegRuntime
from . import spec

logger = logging.getLogger(__name__)

#: A sample aspect ratio ffprobe may report for square pixels (x264 may leave it unset).
_SQUARE = (None, "N/A", "0:1", "1:1")


@dataclass(frozen=True)
class ExpectedProxy:
    """What a proxy of one clip must look like, taken from the source's probe and the plan."""

    #: Names the clip in a failure.
    clip: str
    #: The planned display size.
    width: int
    height: int
    #: The source's VIDEO-stream duration in seconds (the proxy's video stream is compared with
    #: it). The container's duration is wrong for this: it spans the longest stream from the
    #: earliest start, so audio outrunning the video or a late video start inflates it.
    duration: float
    has_audio: bool
    #: The source container's declared video frame count, or ``None`` (check skipped).
    declared_frames: Optional[int]
    #: The encode path, named in a failure.
    path: str


def verify_proxy(staged: Path, *, expected: ExpectedProxy, runtime: FfmpegRuntime) -> int:
    """Probe the encoded file ``staged`` and check it against ``expected``.

    Returns the proxy's video frame count (the facts' ``frames``).

    Raises:
        ProxyError: a check failed, naming the check, the value found, the value expected and
            the encode path; or the file cannot be probed.
    """
    document = _probe(staged, expected, runtime)
    streams = document.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]

    _check(expected, "video streams", len(videos), 1)
    video = videos[0]
    _check(expected, "video codec", video.get("codec_name"), "h264")
    _check(expected, "pixel format", video.get("pix_fmt"), "yuv420p")
    _check(
        expected,
        "dimensions",
        f"{video.get('width')}x{video.get('height')}",
        f"{expected.width}x{expected.height}",
    )
    sar = video.get("sample_aspect_ratio")
    if sar not in _SQUARE:
        _fail(expected, "pixel aspect ratio", sar, "1:1")

    _check(expected, "audio streams", len(audios), 1 if expected.has_audio else 0)
    if expected.has_audio:
        _check(expected, "audio codec", audios[0].get("codec_name"), spec.PROXY_AUDIO_ENCODER)
        _check(expected, "audio channels", audios[0].get("channels"), spec.PROXY_AUDIO_CHANNELS)

    duration = _number(video.get("duration"))
    if duration is None:
        _fail(expected, "video duration", video.get("duration"), f"{expected.duration:.3f}s")
    elif abs(duration - expected.duration) > spec.DURATION_TOLERANCE + 1e-9:
        _fail(
            expected,
            "video duration",
            f"{duration:.3f}s",
            f"{expected.duration:.3f}s within {spec.DURATION_TOLERANCE * 1000:.0f} ms",
        )

    frames = _packets(video)
    if frames is None:
        _fail(expected, "video frames", video.get("nb_read_packets"), "a packet count")
    if expected.declared_frames is None:
        logger.debug(
            "%s: the source declares no frame count; the frame-count check was not possible",
            expected.clip,
        )
    else:
        _check(expected, "video frames", frames, expected.declared_frames)
    assert frames is not None  # _fail raised above otherwise
    return frames


def _probe(staged: Path, expected: ExpectedProxy, runtime: FfmpegRuntime) -> dict[str, Any]:
    """ffprobe of the staged file with a packet count (no decoding); a failure is a ProxyError."""
    args = [
        "-v",
        "error",
        "-count_packets",
        "-show_streams",
        "-show_format",
        "-print_format",
        "json",
        str(staged),
    ]
    try:
        parsed = json.loads(runtime.run_ffprobe(args).stdout)
    except FfmpegError as exc:
        raise ProxyError(expected.clip, f"the encoded proxy cannot be probed: {exc}") from exc
    except ValueError as exc:
        raise ProxyError(expected.clip, f"the encoded proxy's probe is unreadable: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProxyError(expected.clip, "the encoded proxy's probe is not an object")
    return parsed


def _number(value: object) -> Optional[float]:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _packets(video: dict[str, Any]) -> Optional[int]:
    try:
        return int(video["nb_read_packets"])
    except (KeyError, TypeError, ValueError):
        return None


def _check(expected: ExpectedProxy, check: str, found: object, wanted: object) -> None:
    if found != wanted:
        _fail(expected, check, found, wanted)


def _fail(expected: ExpectedProxy, check: str, found: object, wanted: object) -> None:
    raise ProxyError(
        expected.clip,
        f"the encoded proxy failed the {check} check: found {found}, expected {wanted} "
        f"({expected.path} path)",
    )


__all__ = ["ExpectedProxy", "verify_proxy"]
