"""The render orchestrator: pure builders + a thin runner (decision **D-G**).

Drives one movie end-to-end — resolve -> build segments -> apply decorators ->
derive target -> per-segment normalize/copy -> assemble -> verify — running
commands through :class:`FfmpegRuntime` and forwarding its ``-progress``
callback. Intermediates live in an ephemeral per-render temp dir that is cleaned
up afterwards. A batch entry isolates per-event failures: one bad event is
reported with its cause and does not abort the rest, and a failed render never
leaves a half-written output presented as success.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

from ..accel.profiles.base import AccelProfile
from ..errors import EngineError, RenderError
from ..event.plan import RenderPlan
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe import probe_media
from ..probe.metadata import ClipMetadata
from ..reel.document import Metadata
from .chapters import aggregate_chapter_durations, build_ffmetadata
from .concat import build_concat_command, build_concat_list, is_copy_uniform
from .decorators import apply_decorators, resolve_decorator_names
from .normalize import build_normalize_command, decide_copy_eligibility
from .segments import Segment, build_segments
from .target import TargetSpec, derive_target
from .verify import verify_output

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]


@dataclass
class RenderOptions:  # pylint: disable=too-many-instance-attributes
    """Inputs and switches for one movie render.

    ``event_dir`` roots clip identities to files; ``clip_facts`` carries the
    probed metadata keyed by identity; ``runtime`` runs the commands. ``overwrite``
    replaces an existing output, ``dry_run`` builds + reports commands without
    executing or writing, ``render_node`` targets a specific GPU, ``on_progress``
    receives an overall 0.0-1.0 fraction, and ``temp_dir`` overrides the base for
    the ephemeral per-render scratch directory.
    """

    event_dir: Path
    output_dir: Path
    clip_facts: Mapping[str, ClipMetadata]
    runtime: FfmpegRuntime
    overwrite: bool = False
    dry_run: bool = False
    render_node: Optional[str] = None
    on_progress: Optional[ProgressCallback] = None
    temp_dir: Optional[Path] = None


@dataclass(frozen=True)
class RenderResult:
    """The outcome of a single movie render."""

    output_path: Path
    skipped: bool = False
    dry_run: bool = False
    commands: tuple[tuple[str, ...], ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderJob:
    """One unit of batch work: a plan, the selected profile, and its options."""

    plan: RenderPlan
    profile: AccelProfile
    options: RenderOptions


@dataclass(frozen=True)
class BatchOutcome:
    """Per-event batch result: a success carries ``result``, a failure ``error``."""

    job: RenderJob
    result: Optional[RenderResult] = None
    error: Optional[str] = None


def output_filename(metadata: Metadata) -> str:
    """Build the ``<title> - <location>.mp4`` name (location omitted when absent)."""
    title = metadata.title or "Untitled"
    if metadata.location:
        return f"{title} - {metadata.location}.mp4"
    return f"{title}.mp4"


def _first_clip_facts(plan: RenderPlan, clip_facts: Mapping[str, ClipMetadata]) -> ClipMetadata:
    """Return the probed facts of the plan's first clip, or fail loud."""
    for chapter in plan.chapters:
        for clip in chapter.clips:
            facts = clip_facts.get(clip.identity)
            if facts is None:
                raise RenderError(
                    f"first clip {clip.identity!r} has no probed metadata; cannot derive target"
                )
            return facts
    raise RenderError("render plan has no clips to render")


class _Progress:
    """Maps per-step fractions into one overall 0.0-1.0 callback."""

    def __init__(self, total_steps: int, callback: Optional[ProgressCallback]) -> None:
        self._total = max(1, total_steps)
        self._callback = callback

    def step(self, index: int) -> Optional[ProgressCallback]:
        """Return a callback scaling a step's local fraction into the global one."""
        if self._callback is None:
            return None
        callback = self._callback
        total = self._total

        def scaled(local: float) -> None:
            callback(min(1.0, (index + local) / total))

        return scaled

    def complete(self, index: int) -> None:
        """Report a step finished (used for instant copy-eligible/concat steps)."""
        if self._callback is not None:
            self._callback(min(1.0, (index + 1) / self._total))


def render_movie(plan: RenderPlan, profile: AccelProfile, options: RenderOptions) -> RenderResult:
    """Render one movie from ``plan`` using ``profile``; verify before reporting success.

    Honors overwrite/skip and dry-run. On any failure after the output file was
    created, the partial output is removed so a failed render is never presented
    as a successful one, then the error is re-raised.
    """
    target = derive_target(plan.look, _first_clip_facts(plan, options.clip_facts), profile)

    segments = build_segments(plan, options.event_dir, options.clip_facts)
    names = resolve_decorator_names(plan.look)
    segments = apply_decorators(names, plan, target, segments)
    segments = decide_copy_eligibility(segments, options.clip_facts, target)
    if not segments:
        raise RenderError("render plan produced no segments to render")

    output_path = Path(options.output_dir) / output_filename(plan.metadata)

    if options.dry_run:
        return _plan_only(segments, target, profile, options, output_path)

    if output_path.exists() and not options.overwrite:
        logger.info("Output %s exists and overwrite not requested; skipping", output_path)
        return RenderResult(output_path=output_path, skipped=True)

    try:
        return _execute(segments, target, profile, options, output_path)
    except BaseException:
        # Never present a half-written output as a finished render.
        if output_path.exists():
            output_path.unlink()
        raise


def _plan_only(
    segments: tuple[Segment, ...],
    target: TargetSpec,
    profile: AccelProfile,
    options: RenderOptions,
    output_path: Path,
) -> RenderResult:
    """Build and report the planned commands without executing or writing (dry-run)."""
    scratch = Path(options.temp_dir) if options.temp_dir else Path("dry-run")
    commands: list[tuple[str, ...]] = []
    warnings: list[str] = []
    intermediates: list[Path] = []
    for index, segment in enumerate(segments):
        if segment.copy_eligible and segment.source_path is not None:
            intermediates.append(segment.source_path)
            continue
        clip = options.clip_facts.get(segment.identity) if segment.identity else None
        if clip is None:
            raise RenderError(f"segment {index} has no clip facts to plan a normalize command")
        intermediate = scratch / f"seg_{index:03d}.mp4"
        command = build_normalize_command(
            segment, clip, target, profile, intermediate, render_node=options.render_node
        )
        commands.append(command.args)
        warnings.extend(command.warnings)
        intermediates.append(intermediate)

    list_file = scratch / "concat.txt"
    metadata_file = scratch / "chapters.ffmeta"
    commands.append(build_concat_command(list_file, output_path, metadata_file=metadata_file))
    return RenderResult(
        output_path=output_path,
        dry_run=True,
        commands=tuple(commands),
        warnings=tuple(warnings),
    )


def _normalize_segment(
    index: int,
    segment: Segment,
    *,
    target: TargetSpec,
    profile: AccelProfile,
    options: RenderOptions,
    scratch: Path,
    progress: _Progress,
) -> tuple[Path, tuple[str, ...]]:
    """Normalize one segment to an intermediate; return ``(path, warnings)``."""
    clip = options.clip_facts.get(segment.identity) if segment.identity else None
    if clip is None:
        raise RenderError(f"segment {index} ({segment.identity!r}) has no clip facts to normalize")
    intermediate = scratch / f"seg_{index:03d}.mp4"
    command = build_normalize_command(
        segment, clip, target, profile, intermediate, render_node=options.render_node
    )
    for warning in command.warnings:
        logger.warning("segment %s: %s", segment.identity, warning)
    try:
        options.runtime.run_with_progress(
            command.args, duration=command.duration, on_progress=progress.step(index)
        )
    except EngineError as exc:
        raise RenderError(
            f"normalize failed for segment {index} ({segment.identity!r}): {exc}"
        ) from exc
    return intermediate, command.warnings


def _execute(
    segments: tuple[Segment, ...],
    target: TargetSpec,
    profile: AccelProfile,
    options: RenderOptions,
    output_path: Path,
) -> RenderResult:
    """Run the full pipeline: normalize/copy, equivalence-guard, assemble, verify."""
    runtime = options.runtime
    progress = _Progress(len(segments) + 1, options.on_progress)
    Path(options.output_dir).mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="auto-reel-render-", dir=str(options.temp_dir) if options.temp_dir else None
    ) as tmp:
        scratch = Path(tmp)
        warnings: list[str] = []
        intermediates: list[Path] = []
        copied_indices: list[int] = []
        for index, segment in enumerate(segments):
            if segment.copy_eligible and segment.source_path is not None:
                intermediates.append(segment.source_path)
                copied_indices.append(index)
                progress.complete(index)
                continue
            intermediate, segment_warnings = _normalize_segment(
                index,
                segment,
                target=target,
                profile=profile,
                options=options,
                scratch=scratch,
                progress=progress,
            )
            intermediates.append(intermediate)
            warnings.extend(segment_warnings)

        # Equivalence pre-flight (probe data, never the exit code). If the set is
        # not uniform, re-normalize the stream-copied source segments to the
        # target so the join is over a truly uniform set, then re-check.
        if not is_copy_uniform(runtime, intermediates) and copied_indices:
            logger.info(
                "Segment set not copy-uniform; re-encoding %d copied segment(s)",
                len(copied_indices),
            )
            for index in copied_indices:
                intermediate, segment_warnings = _normalize_segment(
                    index,
                    segments[index],
                    target=target,
                    profile=profile,
                    options=options,
                    scratch=scratch,
                    progress=progress,
                )
                intermediates[index] = intermediate
                warnings.extend(segment_warnings)
        if not is_copy_uniform(runtime, intermediates):
            raise RenderError(
                "segments could not be made copy-uniform; refusing a silent-broken concat"
            )

        measured = [probe_media(Path(p), runtime=runtime).duration for p in intermediates]
        chapter_pairs = aggregate_chapter_durations(segments, measured)
        metadata_file = scratch / "chapters.ffmeta"
        metadata_file.write_text(build_ffmetadata(chapter_pairs), encoding="utf-8")

        list_file = scratch / "concat.txt"
        list_file.write_text(build_concat_list(intermediates), encoding="utf-8")
        concat_command = build_concat_command(list_file, output_path, metadata_file=metadata_file)
        try:
            runtime.run(concat_command)
        except EngineError as exc:
            raise RenderError(f"concat failed assembling {output_path.name}: {exc}") from exc
        progress.complete(len(segments))

        verify_output(runtime, output_path, target)

    return RenderResult(output_path=output_path, warnings=tuple(warnings))


def render_batch(jobs: Sequence[RenderJob]) -> list[BatchOutcome]:
    """Render a batch of events, isolating per-event failures.

    A failure rendering one event is caught, logged with its cause, and recorded
    as a :class:`BatchOutcome` error; the remaining events are still rendered.
    """
    outcomes: list[BatchOutcome] = []
    for job in jobs:
        try:
            result = render_movie(job.plan, job.profile, job.options)
            outcomes.append(BatchOutcome(job=job, result=result))
        except EngineError as exc:
            logger.error("Event render failed: %s", exc)
            outcomes.append(BatchOutcome(job=job, error=str(exc)))
    return outcomes


__all__ = [
    "RenderOptions",
    "RenderResult",
    "RenderJob",
    "BatchOutcome",
    "output_filename",
    "render_movie",
    "render_batch",
]
