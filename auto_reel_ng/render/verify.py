"""Post-render output verification (movie-assembly, decision **D-D**).

A stream-copy concat can mux at exit 0 yet produce a player-broken
(variable-resolution/aspect) file. So after assembly the produced file is
re-probed and asserted against the target spec — resolution, codec, pixel
format, SAR, and a single continuous video stream — and a typed
:class:`RenderVerificationError` is raised rather than reporting a broken render
as success.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import RenderVerificationError
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe import probe_media
from ..probe.metadata import ClipMetadata
from .normalize import _normalize_sar
from .target import TargetSpec


def _video_streams(runtime: FfmpegRuntime, path: Path) -> tuple[list[str], list[str]]:
    """The codec names of ``path``'s ``(movie, cover)`` video streams.

    A cover is a video stream with the ``attached_pic`` disposition; it is not the movie's
    video stream. A conforming movie has exactly one movie stream.
    """
    result = runtime.run_ffprobe(
        [
            "-v",
            "error",
            "-select_streams",
            "v",
            "-show_entries",
            "stream=index,codec_name:stream_disposition=attached_pic",
            "-print_format",
            "json",
            str(path),
        ]
    )
    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return [], []
    movie: list[str] = []
    covers: list[str] = []
    for stream in streams:
        attached = (stream.get("disposition") or {}).get("attached_pic")
        (covers if attached else movie).append(str(stream.get("codec_name")))
    return movie, covers


def verify_output(
    runtime: FfmpegRuntime, path: Path, target: TargetSpec, *, cover: bool = False
) -> ClipMetadata:
    """Re-probe ``path`` and assert it matches ``target``; return its metadata.

    Raises:
        RenderVerificationError: if the file is not a single continuous video
            stream matching the target resolution, codec, pixel format, and SAR; or, when
            ``cover`` is set, if the file does not have exactly one ``mjpeg`` ``attached_pic``
            stream. A cover is never counted as the movie's video stream or checked against
            the target.
    """
    path = Path(path)
    # This catches the spike's failure mode — a broken concat that muxes at exit 0
    # with mismatched resolution/SAR — by asserting one stream that matches the
    # target. It does not detect per-frame variable resolution *within* a single
    # stream; the whole-set equivalence pre-flight (concat.is_copy_uniform) is the
    # primary guard against that, and this re-probe is the backstop.
    movie, covers = _video_streams(runtime, path)
    if len(movie) != 1:
        raise RenderVerificationError(
            f"{path.name}: expected a single video stream, found {len(movie)}"
        )
    if cover and covers != ["mjpeg"]:
        raise RenderVerificationError(
            f"{path.name}: expected exactly one mjpeg cover stream, found "
            f"{len(covers)}{' (' + ', '.join(covers) + ')' if covers else ''}"
        )

    facts = probe_media(path, runtime=runtime)
    mismatches: list[str] = []
    if facts.width != target.width or facts.height != target.height:
        mismatches.append(
            f"resolution {facts.width}x{facts.height} != {target.width}x{target.height}"
        )
    if facts.video_codec != target.video_codec:
        mismatches.append(f"codec {facts.video_codec!r} != {target.video_codec!r}")
    if facts.pix_fmt != target.pix_fmt:
        mismatches.append(f"pix_fmt {facts.pix_fmt!r} != {target.pix_fmt!r}")
    if _normalize_sar(facts.sample_aspect_ratio) != target.sample_aspect_ratio:
        mismatches.append(f"SAR {facts.sample_aspect_ratio!r} != {target.sample_aspect_ratio!r}")
    if mismatches:
        raise RenderVerificationError(
            f"{path.name}: output does not match target spec: {'; '.join(mismatches)}"
        )
    return facts


__all__ = ["verify_output"]
