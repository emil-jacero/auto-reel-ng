"""``facts.json``: what the proxy run learned about the clip, written beside the proxy (D-21).

A reader (the timeline, the read model) lays out a clip from these facts with one ``stat`` and
one JSON read, no probe. The duration is the **source's** probed duration, never the proxy's:
a proxy container is up to 21 ms longer (AAC priming) and cuts (D-14) refer to the source.
A value the probe could not give is ``null``, never a default; a file that is damaged, lacks
a key or was made under another proxy version reads as absent, never as defaults.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Optional

from ..errors import FfmpegError, ProxyError
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe.metadata import ClipMetadata
from . import spec

logger = logging.getLogger(__name__)

#: How far a clip's average and container frame rates may differ (relative) before it is
#: called variable-frame-rate: one percent.
VFR_THRESHOLD = 0.01


@dataclass(frozen=True)
class SourceFacts:
    """What the one extra ffprobe call of a run reports about the source's video stream."""

    #: The container's frame rate as an exact rational (``r_frame_rate``).
    fps_num: int
    fps_den: int
    #: True when the average rate differs from the container's by more than one percent;
    #: ``None`` when the container gives no average rate to compare.
    vfr: Optional[bool]
    #: The frame count the container declares (``nb_frames``), or ``None``.
    declared_frames: Optional[int]
    #: The video stream's own duration in seconds (``stream=duration``), or ``None`` when the
    #: container gives none. Not the container's: that spans the longest stream from the
    #: earliest start, so audio running past the video or a late video start inflates it.
    video_duration: Optional[float] = None


@dataclass(frozen=True)
class ProxyFacts:  # pylint: disable=too-many-instance-attributes
    """The contents of ``facts.json`` (spec: clip-proxies, "The facts about the clip")."""

    proxy_version: int
    #: The source's probed duration in seconds.
    duration: float
    fps_num: int
    fps_den: int
    vfr: Optional[bool]
    #: The proxy's own video frame count.
    frames: int
    width: int
    height: int
    source_width: int
    source_height: int
    rotation: Optional[int]
    audio_codec: Optional[str]
    #: ``"hybrid"`` or ``"cpu"``: the path that produced the published proxy.
    encode_path: str
    fallback_reason: Optional[str]

    def to_json(self) -> dict[str, Any]:
        """The JSON object: ``fps`` as ``{"num", "den"}``, everything else flat."""
        return {
            "proxy_version": self.proxy_version,
            "duration": self.duration,
            "fps": {"num": self.fps_num, "den": self.fps_den},
            "vfr": self.vfr,
            "frames": self.frames,
            "width": self.width,
            "height": self.height,
            "source_width": self.source_width,
            "source_height": self.source_height,
            "rotation": self.rotation,
            "audio_codec": self.audio_codec,
            "encode_path": self.encode_path,
            "fallback_reason": self.fallback_reason,
        }

    @classmethod
    def from_json(cls, document: object) -> Optional[ProxyFacts]:
        """The facts in ``document``, or ``None`` when it is not a complete, well-typed object.

        Strict: a missing key, a wrong type (a bool is not a number), another
        ``proxy_version``, a non-finite duration, a non-positive size or a rotation outside
        ``[0, 360)`` (the probe's range) is absence, never a default. The cache writer and the
        read model share this, so both call the same entries usable.
        """
        if not isinstance(document, Mapping):
            return None
        try:
            fps = document["fps"]
            facts = cls(
                proxy_version=_int(document["proxy_version"]),
                duration=_positive_number(document["duration"]),
                fps_num=_int(fps["num"]),
                fps_den=_int(fps["den"]),
                vfr=_optional(document["vfr"], bool),
                frames=_int(document["frames"]),
                width=_int(document["width"]),
                height=_int(document["height"]),
                source_width=_int(document["source_width"]),
                source_height=_int(document["source_height"]),
                rotation=_optional(document["rotation"], int),
                audio_codec=_optional(document["audio_codec"], str),
                encode_path=_text(document["encode_path"]),
                fallback_reason=_optional(document["fallback_reason"], str),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if facts.proxy_version != spec.PROXY_VERSION or facts.fps_den <= 0 or facts.fps_num <= 0:
            return None
        if not math.isfinite(facts.duration) or facts.width <= 0 or facts.height <= 0:
            return None
        if facts.rotation is not None and not 0 <= facts.rotation < 360:
            return None
        return facts


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("not an integer")
    return value


def _positive_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
        raise TypeError("not a positive number")
    return float(value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("not a string")
    return value


def _optional(value: object, kind: type) -> Any:
    """``value`` when it is ``None`` or exactly a ``kind`` (an int is not a bool)."""
    if value is None:
        return None
    if kind is int:
        return _int(value)
    if not isinstance(value, kind):
        raise TypeError(f"not a {kind.__name__}")
    return value


def read_source_facts(source: Path, runtime: FfmpegRuntime, *, clip: str) -> SourceFacts:
    """The source's container frame rate, variability and declared frame count (one ffprobe).

    ``clip`` names the clip in a failure. The engine's main probe carries neither the
    container's ``r_frame_rate`` nor ``nb_frames``, so this is the one more small call.

    Raises:
        ProxyError: ffprobe fails, or reports no usable frame rate.
    """
    args = [
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=r_frame_rate,avg_frame_rate,nb_frames,duration",
        "-of",
        "json",
        str(source),
    ]
    try:
        document = json.loads(runtime.run_ffprobe(args).stdout)
        stream = document["streams"][0]
    except FfmpegError as exc:
        raise ProxyError(clip, f"ffprobe could not read the frame rate: {exc}") from exc
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProxyError(clip, f"ffprobe gave no video stream facts: {exc}") from exc
    rate = _rational(stream.get("r_frame_rate"))
    average = _rational(stream.get("avg_frame_rate"))
    if rate is None:
        rate = average  # the container names no base rate; the average is all it has
    if rate is None:
        raise ProxyError(
            clip,
            f"ffprobe reported no usable frame rate (r_frame_rate={stream.get('r_frame_rate')!r}, "
            f"avg_frame_rate={stream.get('avg_frame_rate')!r})",
        )
    vfr: Optional[bool] = None
    if average is not None:
        vfr = abs(average - rate) / rate > VFR_THRESHOLD
    return SourceFacts(
        fps_num=rate.numerator,
        fps_den=rate.denominator,
        vfr=vfr,
        declared_frames=_declared_frames(stream.get("nb_frames")),
        video_duration=_stream_duration(stream.get("duration")),
    )


def _rational(value: object) -> Optional[Fraction]:
    """``"30000/1001"`` as an exact fraction; ``None`` for ``0/0``, ``N/A`` or garbage."""
    if not isinstance(value, str) or "/" not in value:
        return None
    num_text, _, den_text = value.partition("/")
    try:
        num, den = int(num_text), int(den_text)
    except ValueError:
        return None
    if num <= 0 or den <= 0:
        return None
    return Fraction(num, den)


def _stream_duration(value: object) -> Optional[float]:
    """The video stream's duration in seconds, or ``None`` for ``N/A``, garbage or non-positive."""
    if not isinstance(value, str):
        return None
    try:
        seconds = float(value)
    except ValueError:  # "N/A"
        return None
    return seconds if math.isfinite(seconds) and seconds > 0 else None


def _declared_frames(value: object) -> Optional[int]:
    """The container's declared frame count, or ``None`` when it declares none."""
    if not isinstance(value, str):
        return None
    try:
        count = int(value)
    except ValueError:  # "N/A"
        return None
    return count if count > 0 else None


def make_facts(  # pylint: disable=too-many-arguments
    *,
    clip: ClipMetadata,
    source: SourceFacts,
    frames: int,
    size: tuple[int, int],
    encode_path: str,
    fallback_reason: Optional[str],
) -> ProxyFacts:
    """The facts of a published proxy, from the run's own probe of the source."""
    return ProxyFacts(
        proxy_version=spec.PROXY_VERSION,
        duration=clip.duration,
        fps_num=source.fps_num,
        fps_den=source.fps_den,
        vfr=source.vfr,
        frames=frames,
        width=size[0],
        height=size[1],
        source_width=clip.width,
        source_height=clip.height,
        rotation=clip.rotation,
        audio_codec=clip.audio.codec if clip.audio is not None else None,
        encode_path=encode_path,
        fallback_reason=fallback_reason,
    )


def write_facts(directory: Path, facts: ProxyFacts) -> Path:
    """Write ``facts`` as sorted-key JSON to ``<directory>/facts.json`` and ``fsync`` it.

    Meant for the hidden build directory: the file becomes visible with the rest of the entry
    when the directory is renamed. An :class:`OSError` propagates.
    """
    path = Path(directory) / spec.FACTS_FILENAME
    text = json.dumps(facts.to_json(), sort_keys=True, indent=2) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)  # umask applies
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def read_facts(path: Path) -> Optional[ProxyFacts]:
    """The facts in the file ``path``, or ``None`` when absent, unreadable or not valid facts.

    Reads one file and runs no process. A damaged file is never turned into defaults, and
    this never raises for the file's content.
    """
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:  # ValueError: invalid JSON or text
        logger.debug("Cannot use the proxy facts %s: %s", path, exc)
        return None
    facts = ProxyFacts.from_json(document)
    if facts is None:
        logger.debug("The proxy facts %s are incomplete or from another version", path)
    return facts


__all__ = [
    "VFR_THRESHOLD",
    "ProxyFacts",
    "SourceFacts",
    "make_facts",
    "read_facts",
    "read_source_facts",
    "write_facts",
]
