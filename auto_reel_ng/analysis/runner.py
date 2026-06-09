"""The impure detection runner: probe, run two ffmpeg passes, parse, resolve.

This is the only module in the layer that touches ffmpeg. It composes the pure
pieces — :mod:`.filters` (args), :mod:`.parser` (log -> segments), :mod:`.overlap`
(precedence) — around exactly two :class:`FfmpegRuntime` invocations per clip
(decision D-AN2). It fails loud (D-AN6): an ffmpeg non-zero exit or an undecodable
clip raises :class:`AnalysisError` naming the clip, never a silent empty result.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

from ..errors import AnalysisError, FfmpegError, ProbeError
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe.media import get_default_runtime, probe_media
from .filters import pass1_args, pass2_args
from .models import AnalysisConfig, Segment
from .overlap import resolve_overlap
from .parser import parse_pass1, parse_pass2

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def analyze_clip(
    path: PathLike,
    *,
    runtime: Optional[FfmpegRuntime] = None,
    config: Optional[AnalysisConfig] = None,
) -> List[Segment]:
    """Detect black/white/freeze spans in one clip and return resolved segments.

    Runs exactly two ffmpeg passes (pass 1 = black+freeze, pass 2 = white), parses
    each log, applies ``black``/``white`` > ``freeze`` precedence, and returns the
    segments sorted by start. Ordinary footage yields an empty list.

    Args:
        path: The clip to analyze.
        runtime: ffmpeg runtime to use; the shared default is built if omitted.
        config: Detection thresholds; experiment-005 defaults if omitted.

    Raises:
        AnalysisError: if the clip cannot be probed or either ffmpeg pass fails.
    """
    clip_path = Path(path)
    runtime = runtime or get_default_runtime()
    config = config or AnalysisConfig()

    duration = _probe_duration(clip_path, runtime)

    pass1_log = _run_pass(runtime, pass1_args(str(clip_path), config), clip_path, "black/freeze")
    pass2_log = _run_pass(runtime, pass2_args(str(clip_path), config), clip_path, "white")

    segments = parse_pass1(
        pass1_log, min_duration=config.min_duration, clip_duration=duration
    ) + parse_pass2(pass2_log, min_duration=config.min_duration)

    return resolve_overlap(segments)


def _probe_duration(clip_path: Path, runtime: FfmpegRuntime) -> Optional[float]:
    """Probe the clip's duration via ``ClipMetadata``; raise AnalysisError on failure."""
    try:
        return probe_media(clip_path, runtime=runtime).duration
    except ProbeError as exc:
        raise AnalysisError(f"Cannot analyze undecodable clip {clip_path}: {exc}") from exc


def _run_pass(runtime: FfmpegRuntime, args: List[str], clip_path: Path, label: str) -> str:
    """Run one detection pass and return its stderr, raising AnalysisError on failure."""
    try:
        result = runtime.run(args)
    except FfmpegError as exc:
        raise AnalysisError(f"ffmpeg {label} detection pass failed for {clip_path}: {exc}") from exc
    # Detector log lines (black_start, freeze_start, ...) are written to stderr.
    return result.stderr
