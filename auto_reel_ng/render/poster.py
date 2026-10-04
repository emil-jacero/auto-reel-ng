"""The event poster frame: choose it, extract it, embed it as the movie's cover (D-26).

A render of an event with a played clip writes ``<movie stem>-poster.jpg`` beside the movie and
embeds the same image in the movie as an ``attached_pic`` stream. The frame is the operator's
``poster: {clip, at}`` (``at`` seconds into the ORIGINAL clip, before trims) or, by default,
the first played clip at the thumbnail position.

The frame is extracted on the CPU whatever the profile: it is one frame, so every profile shares
the one path and there is nothing to fall back from. The rotation is the renderer's own
(:func:`.normalize.total_turn`, autorotate off), so the poster is upright by the same turn the
movie shows. A time with no frame is a :class:`PosterFrameError`, never another time or a
placeholder (Principle I). ffmpeg is only ever spawned through :class:`FfmpegRuntime` (VI).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, NamedTuple, Optional

from ..accel.profiles.cpu import CPU_TONEMAP_FILTER
from ..errors import FfmpegError, PosterFrameError, RenderError, RenderVerificationError
from ..event.plan import RenderPlan
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe.metadata import ClipMetadata
from ..thumbs.settings import DEFAULT_POSITION
from .normalize import _transpose_filter, total_turn
from .target import TargetSpec

logger = logging.getLogger(__name__)

#: JPEG quality for the poster (``-q:v``; 2 is near the top of mjpeg's scale).
POSTER_QUALITY = 2

_JPEG_MAGIC = b"\xff\xd8\xff"


@dataclass(frozen=True)
class PosterChoice:
    """The frame a render writes: a played clip, a time in the original clip, and a turn."""

    identity: str
    at: float
    rotate: Optional[int]
    source: Literal["explicit", "default"]


class PosterResolution(NamedTuple):
    """What :func:`resolve_poster` decided: the frame (``None`` for no poster) and its warnings."""

    choice: Optional[PosterChoice]
    warnings: tuple[str, ...] = ()


def poster_path(output_path: Path) -> Path:
    """``<movie stem>-poster.jpg`` beside ``output_path`` (the Jellyfin/Plex/Kodi convention)."""
    return output_path.with_name(f"{output_path.stem}-poster.jpg")


def poster_part_path(output_path: Path) -> Path:
    """The atomic-finalize temporary of the poster: ``<stem>-poster.jpg.part``."""
    return poster_path(output_path).with_name(poster_path(output_path).name + ".part")


def cover_part_path(output_path: Path) -> Path:
    """The temporary of the movie with its cover embedded: ``<movie>.cover.part``."""
    return output_path.with_name(output_path.name + ".cover.part")


def resolve_poster(
    plan: RenderPlan,
    clip_facts: Mapping[str, ClipMetadata],
    *,
    position: float = DEFAULT_POSITION,
) -> PosterResolution:
    """The poster frame for ``plan`` and the warnings for a fallback.

    No ``poster``: the first played clip at ``position`` of its probed duration. A ``poster``
    whose clip the movie does not play (missing, ignored, excluded) falls back to that default
    with one warning naming the clip and the reason; the render goes on. A played clip whose
    ``at`` is not less than its probed duration raises :class:`PosterFrameError`, before anything
    is encoded. No played clip: no poster.
    """
    played = [(clip.identity, clip.rotate) for chapter in plan.chapters for clip in chapter.clips]
    if not played:
        return PosterResolution(None)
    warnings: list[str] = []
    poster = plan.poster
    if poster is not None:
        match = next((entry for entry in played if entry[0] == poster.clip), None)
        if match is not None:
            duration = clip_facts[match[0]].duration
            if poster.at >= duration:
                raise PosterFrameError(
                    f"poster frame of {poster.clip!r} at {poster.at:g}s does not exist: "
                    f"the clip lasts {duration:g}s; choose a time before the end"
                )
            return PosterResolution(PosterChoice(match[0], poster.at, match[1], "explicit"))
        reason = plan.poster_unplayed or "not played by the movie"
        warnings.append(
            f"poster clip {poster.clip!r} is {reason}; using the first played clip's frame"
        )
        logger.warning(warnings[-1])
    identity, rotate = played[0]
    return PosterResolution(
        PosterChoice(identity, position * clip_facts[identity].duration, rotate, "default"),
        tuple(warnings),
    )


def poster_args(
    clip: ClipMetadata, choice: PosterChoice, *, target: TargetSpec, output: Path
) -> list[str]:
    """The ffmpeg arguments that write the poster frame of ``clip`` as a JPEG at ``output``.

    Input seek lands on the frame at ``choice.at`` of the ORIGINAL clip. Autorotate is off and
    the renderer's transpose chain applies the display rotation plus ``rotate`` (D-23); an HDR
    clip is tone-mapped first, as the renderer and the thumbnails do; pixels are made square,
    then the frame is fitted into and padded to the movie's size.
    """
    filters: list[str] = []
    if clip.is_hdr:
        filters.append(CPU_TONEMAP_FILTER)
    turn = total_turn(clip, choice.rotate)
    if turn:
        filters.append(_transpose_filter(turn))
    filters += [
        "scale=trunc(iw*sar/2)*2:ih",
        f"scale={target.width}:{target.height}:force_original_aspect_ratio=decrease",
        f"pad={target.width}:{target.height}:(ow-iw)/2:(oh-ih)/2:{target.fill_color}",
        "setsar=1",
    ]
    return [
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-noautorotate",
        "-ss",
        f"{choice.at:.3f}",
        "-i",
        str(clip.path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-frames:v",
        "1",
        "-vf",
        ",".join(filters),
        "-c:v",
        "mjpeg",
        "-q:v",
        str(POSTER_QUALITY),
        "-f",
        "image2",
        "-update",
        "1",
        "-y",
        str(output),
    ]


def extract_poster(
    runtime: FfmpegRuntime,
    clip: ClipMetadata,
    choice: PosterChoice,
    *,
    target: TargetSpec,
    output: Path,
) -> None:
    """Write the poster frame to ``output`` and verify it; no frame raises, never a stand-in."""
    # A ``.part`` left by a killed render must never pass as this render's frame.
    output.unlink(missing_ok=True)
    no_frame = f"no poster frame at {choice.at:g}s of {choice.identity!r} (the clip lasts {clip.duration:g}s)"
    try:
        runtime.run(poster_args(clip, choice, target=target, output=output))
    except FfmpegError as exc:
        raise PosterFrameError(f"{no_frame}: {exc}") from exc
    if not output.is_file() or output.stat().st_size == 0:
        raise PosterFrameError(f"{no_frame}: ffmpeg exited 0 but wrote no image")
    verify_poster(runtime, output, target)


def verify_poster(runtime: FfmpegRuntime, path: Path, target: TargetSpec) -> None:
    """Assert ``path`` is one JPEG frame of the target's size, else raise.

    Raises:
        RenderVerificationError: not a JPEG, not one ``mjpeg`` frame, or not the target size.
    """
    with path.open("rb") as handle:
        magic = handle.read(len(_JPEG_MAGIC))
    if magic != _JPEG_MAGIC:
        raise RenderVerificationError(f"{path.name}: not a JPEG image")
    result = runtime.run_ffprobe(
        [
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,width,height",
            "-print_format",
            "json",
            str(path),
        ]
    )
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "mjpeg":
        raise RenderVerificationError(f"{path.name}: expected one mjpeg frame, found {streams}")
    size = (streams[0].get("width"), streams[0].get("height"))
    if size != (target.width, target.height):
        raise RenderVerificationError(
            f"{path.name}: poster is {size[0]}x{size[1]}, expected {target.width}x{target.height}"
        )


def embed_cover_args(movie: Path, poster: Path, output: Path) -> tuple[str, ...]:
    """The ffmpeg arguments that copy ``movie`` and add ``poster`` as its ``attached_pic`` cover.

    Every movie stream, the chapters and the metadata are copied unchanged (a stream copy, I/O
    only); ``+faststart`` is applied again. The container is forced to ``mp4`` so a ``.part``
    output still muxes, and the image is read as ``image2`` for the same reason.
    """
    return (
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-i",
        str(movie),
        "-f",
        "image2",
        "-i",
        str(poster),
        "-map",
        "0",
        "-map",
        "1:v",
        "-c",
        "copy",
        "-disposition:v:1",
        "attached_pic",
        "-map_metadata",
        "0",
        "-map_chapters",
        "0",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        str(output),
    )


def embed_cover(runtime: FfmpegRuntime, movie: Path, poster: Path, output: Path) -> None:
    """Write ``output``: ``movie`` with ``poster`` embedded as its cover."""
    try:
        runtime.run(embed_cover_args(movie, poster, output))
    except FfmpegError as exc:
        raise RenderError(f"{movie.name}: embedding the cover failed: {exc}") from exc


__all__ = [
    "POSTER_QUALITY",
    "PosterChoice",
    "PosterResolution",
    "cover_part_path",
    "embed_cover",
    "embed_cover_args",
    "extract_poster",
    "poster_args",
    "poster_part_path",
    "poster_path",
    "resolve_poster",
    "verify_poster",
]
