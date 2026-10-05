"""The impure detection runner: probe, run two ffmpeg passes, parse, resolve.

This is the only module in the layer that touches ffmpeg. It composes the pure
pieces — :mod:`.filters` (args), :mod:`.parser` (log -> segments), :mod:`.overlap`
(precedence) — around exactly two :class:`FfmpegRuntime` invocations per clip
(decision D-AN2). It fails loud (D-AN6): an ffmpeg non-zero exit or an undecodable
clip raises :class:`AnalysisError` naming the clip, never a silent empty result.

A caller that wants them (the worker's ``analysis`` job) passes a progress callback and
a cancel check: both passes then run through
:meth:`~auto_reel_ng.ffmpeg.runtime.FfmpegRuntime.run_with_progress`, pass 1 filling the
clip's fraction ``0.0–0.5`` and pass 2 ``0.5–1.0``, and a cancel ends the running ffmpeg
and raises the engine's cancellation (never an :class:`AnalysisError`). Without either
hook the passes run as they always have.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional, Union

from ..errors import AnalysisError, FfmpegCancelledError, FfmpegError, ProbeError
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe.media import get_default_runtime, probe_media
from .filters import pass1_args, pass2_args
from .models import AnalysisConfig, Segment
from .overlap import resolve_overlap
from .parser import parse_pass1, parse_pass2

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]
#: Receives the fraction of one clip's analysis done, ``0.0–1.0``, non-decreasing.
ClipProgress = Callable[[float], None]
#: Answers whether the analysis must stop now.
CancelCheck = Callable[[], bool]

#: Seconds a hooked pass may go without its output time advancing before it is killed as
#: stalled (the proxy encode's limit; not imported, ``analysis`` does not depend on ``proxies``).
ANALYSIS_STALL_TIMEOUT_S = 600.0


def analyze_clip(
    path: PathLike,
    *,
    runtime: Optional[FfmpegRuntime] = None,
    config: Optional[AnalysisConfig] = None,
    on_progress: Optional[ClipProgress] = None,
    should_cancel: Optional[CancelCheck] = None,
) -> List[Segment]:
    """Detect black/white/freeze spans in one clip and return resolved segments.

    Runs exactly two ffmpeg passes (pass 1 = black+freeze, pass 2 = white), parses
    each log, applies ``black``/``white`` > ``freeze`` precedence, and returns the
    segments sorted by start. Ordinary footage yields an empty list.

    Args:
        path: The clip to analyze.
        runtime: ffmpeg runtime to use; the shared default is built if omitted.
        config: Detection thresholds; experiment-005 defaults if omitted.
        on_progress: Receives the clip's fraction done (pass 1 ``0.0–0.5``, pass 2
            ``0.5–1.0``, ``1.0`` only once both passes ended). Without a probed duration no
            fraction is computed and only ``1.0`` is reported, at the end.
        should_cancel: Polled about once a second during each pass and checked between
            them; true kills the running ffmpeg.

    Raises:
        AnalysisError: if the clip cannot be probed or either ffmpeg pass fails or stalls.
        FfmpegCancelledError: ``should_cancel`` answered true.
    """
    clip_path = Path(path)
    runtime = runtime or get_default_runtime()
    config = config or AnalysisConfig()

    duration = _probe_duration(clip_path, runtime)
    hooked = on_progress is not None or should_cancel is not None

    def run(args: List[str], label: str, start: float) -> str:
        if not hooked:
            return _run_pass(runtime, args, clip_path, label)
        return _run_hooked_pass(
            runtime,
            args,
            clip_path,
            label,
            duration=duration,
            on_progress=_scaled(on_progress, start) if duration else None,
            should_cancel=should_cancel,
        )

    pass1_log = run(pass1_args(str(clip_path), config), "black/freeze", 0.0)
    if should_cancel is not None and should_cancel():
        raise FfmpegCancelledError(f"analysis of {clip_path} canceled between passes")
    pass2_log = run(pass2_args(str(clip_path), config), "white", 0.5)

    segments = parse_pass1(
        pass1_log, min_duration=config.min_duration, clip_duration=duration
    ) + parse_pass2(pass2_log, min_duration=config.min_duration)

    if on_progress is not None:
        on_progress(1.0)
    return resolve_overlap(segments)


def _scaled(on_progress: Optional[ClipProgress], start: float) -> Optional[ClipProgress]:
    """Map one pass's ``0.0–1.0`` onto its half of the clip, ``1.0`` withheld for the end."""
    if on_progress is None:
        return None
    callback = on_progress

    def report(fraction: float) -> None:
        value = start + 0.5 * fraction
        if value < 1.0:  # 1.0 is reported once the clip's segments are parsed
            callback(value)

    return report


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


def _run_hooked_pass(  # pylint: disable=too-many-arguments
    runtime: FfmpegRuntime,
    args: List[str],
    clip_path: Path,
    label: str,
    *,
    duration: Optional[float],
    on_progress: Optional[ClipProgress],
    should_cancel: Optional[CancelCheck],
) -> str:
    """Run one pass cancellably with progress; return its stderr.

    The cancellation is caught first and re-raised as is: it subclasses ``FfmpegError``,
    and it is not a failure of the clip.
    """
    try:
        return runtime.run_with_progress(
            args,
            duration=duration or 0.0,
            on_progress=on_progress,
            stall_timeout=ANALYSIS_STALL_TIMEOUT_S,
            should_cancel=should_cancel,
        )
    except FfmpegCancelledError:
        raise
    except FfmpegError as exc:
        raise AnalysisError(f"ffmpeg {label} detection pass failed for {clip_path}: {exc}") from exc
