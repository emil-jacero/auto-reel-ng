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


def _video_stream_count(runtime: FfmpegRuntime, path: Path) -> int:
    """Count the video streams in ``path`` (a conforming movie has exactly one)."""
    result = runtime.run_ffprobe(
        [
            "-v",
            "error",
            "-select_streams",
            "v",
            "-show_entries",
            "stream=index",
            "-print_format",
            "json",
            str(path),
        ]
    )
    try:
        return len(json.loads(result.stdout).get("streams", []))
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return 0


def verify_output(runtime: FfmpegRuntime, path: Path, target: TargetSpec) -> ClipMetadata:
    """Re-probe ``path`` and assert it matches ``target``; return its metadata.

    Raises:
        RenderVerificationError: if the file is not a single continuous video
            stream matching the target resolution, codec, pixel format, and SAR.
    """
    path = Path(path)
    # This catches the spike's failure mode — a broken concat that muxes at exit 0
    # with mismatched resolution/SAR — by asserting one stream that matches the
    # target. It does not detect per-frame variable resolution *within* a single
    # stream; the whole-set equivalence pre-flight (concat.is_copy_uniform) is the
    # primary guard against that, and this re-probe is the backstop.
    streams = _video_stream_count(runtime, path)
    if streams != 1:
        raise RenderVerificationError(
            f"{path.name}: expected a single video stream, found {streams}"
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
