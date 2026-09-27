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
import os
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Hashable, Mapping, Optional, Sequence, TypeVar

from ..accel.profiles.base import AccelProfile
from ..errors import EngineError, RenderCancelledError, RenderError
from ..event.plan import RenderPlan
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe import probe_media
from ..probe.metadata import ClipMetadata
from ..reel.document import Metadata
from ..staleness.fingerprint import Fingerprint, engine_identity
from ..staleness.manifest import write_manifest
from .chapters import aggregate_chapter_durations, build_ffmetadata
from .concat import build_concat_command, build_concat_list, is_copy_uniform
from .decorators import apply_decorators, resolve_decorator_names
from .normalize import (
    NormalizeCommand,
    build_normalize_command,
    build_synthetic_normalize_command,
    decide_copy_eligibility,
)
from .producers import get_producer
from .segments import Segment, build_segments
from .target import TargetSpec, derive_target
from .verify import verify_output

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]
ShouldCancel = Callable[[], bool]


@dataclass
class RenderOptions:  # pylint: disable=too-many-instance-attributes
    """Inputs and switches for one movie render.

    ``event_dir`` roots clip identities to files; ``clip_facts`` carries the
    probed metadata keyed by identity; ``runtime`` runs the commands. ``overwrite``
    replaces an existing output, ``dry_run`` builds + reports commands without
    executing or writing, ``render_node`` targets a specific GPU, ``on_progress``
    receives an overall 0.0-1.0 fraction, and ``temp_dir`` overrides the base for
    the ephemeral per-render scratch directory. ``should_cancel``, when given, is
    polled at each segment boundary (job-scheduler, D-S6); a true result stops the
    render before the next segment starts and raises :class:`RenderCancelledError`
    rather than completing or failing the render. ``fingerprint``, when given, is
    the caller's pre-render staleness fingerprint (change-detection, D-C5); the
    render manifest is written from it immediately after the atomic finalize
    succeeds, and never on skip/dry-run/failure/absent fingerprint.
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
    should_cancel: Optional[ShouldCancel] = None
    fingerprint: Optional[Fingerprint] = None


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
    """``[<YYYY-MM-DD> - ]<title>[ - <location>].mp4``, the legacy auto-reel name.

    A dated event's name starts with its ISO date (legacy ``directory.py:220``);
    an undated event has no prefix. The location, when present, is appended.
    """
    stem = metadata.title or "Untitled"
    if metadata.date is not None:
        stem = f"{metadata.date.isoformat()} - {stem}"
    if metadata.location:
        return f"{stem} - {metadata.location}.mp4"
    return f"{stem}.mp4"


def output_relpath(metadata: Metadata) -> PurePosixPath:
    """The output path relative to the output directory (legacy auto-reel layout).

    ``<YYYY>/<output_filename>`` when ``metadata.date`` is set, else the bare
    filename at the output root. The year is never inferred from anything else.
    """
    name = output_filename(metadata)
    if metadata.date is None:
        return PurePosixPath(name)
    return PurePosixPath(f"{metadata.date.year:04d}") / name


_K = TypeVar("_K", bound=Hashable)


def _collision_key(path: PurePosixPath) -> str:
    """Case- and normalization-insensitive comparison key for an output path."""
    return unicodedata.normalize("NFC", str(path)).casefold()


def find_output_collisions(claims: Mapping[_K, PurePosixPath]) -> dict[_K, tuple[_K, ...]]:
    """Map each key whose output path is shared to the other keys claiming it.

    Paths compare case-insensitively after NFC normalization, so a clash a
    case-insensitive archive filesystem would create is caught on any host. Keys
    in no collision are absent from the result. Pure: no filesystem access.
    """
    groups: dict[str, list[_K]] = {}
    for key, path in claims.items():
        groups.setdefault(_collision_key(path), []).append(key)
    result: dict[_K, tuple[_K, ...]] = {}
    for keys in groups.values():
        if len(keys) > 1:
            for key in keys:
                result[key] = tuple(other for other in keys if other != key)
    return result


def _part_path(output_path: Path) -> Path:
    """The atomic-finalize temp path: same directory as ``output_path``, ``.part`` suffix.

    Same directory guarantees the finalizing :func:`os.replace` is a same-filesystem
    (atomic) rename rather than a cross-filesystem copy.
    """
    return output_path.with_name(output_path.name + ".part")


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


def resolve_target(
    plan: RenderPlan, profile: AccelProfile, clip_facts: Mapping[str, ClipMetadata]
) -> TargetSpec:
    """Derive the :class:`TargetSpec` for ``plan`` under ``profile`` (public seam).

    The same derivation :func:`render_movie` performs internally, exposed so a
    caller can learn the resolved encoder (job-scheduler capacity classification,
    D-S3) before committing to a render.
    """
    return derive_target(plan.look, _first_clip_facts(plan, clip_facts), profile)


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

    Honors overwrite/skip and dry-run. Finalization is atomic (movie-assembly): the
    assembled movie is written to a ``.part`` file in the output directory and moved
    into place with :func:`os.replace` only after verification passes, so a file at
    the final path always means a complete, verified render — even across a hard
    kill (SIGKILL/OOM/power loss) mid-assembly. On any failure, the ``.part`` is
    removed so a failed render is never presented as a successful one, then the
    error is re-raised; the final path itself is never touched until the rename.
    """
    target = resolve_target(plan, profile, options.clip_facts)

    segments = build_segments(plan, options.event_dir, options.clip_facts)
    names = resolve_decorator_names(plan.look)
    segments = apply_decorators(names, plan, target, segments)
    segments = decide_copy_eligibility(segments, options.clip_facts, target)
    if not segments:
        raise RenderError("render plan produced no segments to render")

    output_path = Path(options.output_dir) / output_relpath(plan.metadata)

    if options.dry_run:
        return _plan_only(segments, target, profile, options, output_path)

    if output_path.exists() and not options.overwrite:
        logger.info("Output %s exists and overwrite not requested; skipping", output_path)
        return RenderResult(output_path=output_path, skipped=True)

    try:
        return _execute(segments, target, profile, options, output_path)
    except BaseException:
        # Never present a half-written output as a finished render; the final path
        # is untouched until the atomic rename, so only the .part needs cleanup.
        part_path = _part_path(output_path)
        if part_path.exists():
            part_path.unlink()
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
    # A synthetic segment is materialized (its card image rendered) to plan its
    # command, so the scratch dir must exist for those renders.
    if any(segment.is_synthetic for segment in segments):
        scratch.mkdir(parents=True, exist_ok=True)
    commands: list[tuple[str, ...]] = []
    warnings: list[str] = []
    intermediates: list[Path] = []
    for index, segment in enumerate(segments):
        if segment.copy_eligible and segment.source_path is not None:
            intermediates.append(segment.source_path)
            continue
        command = _build_segment_command(
            index, segment, target=target, profile=profile, options=options, scratch=scratch
        )
        commands.append(command.args)
        warnings.extend(command.warnings)
        intermediates.append(command.output_path)

    list_file = scratch / "concat.txt"
    metadata_file = scratch / "chapters.ffmeta"
    commands.append(build_concat_command(list_file, output_path, metadata_file=metadata_file))
    return RenderResult(
        output_path=output_path,
        dry_run=True,
        commands=tuple(commands),
        warnings=tuple(warnings),
    )


def _segment_label(segment: Segment) -> str:
    """A human label for a segment in logs/errors (source identity or producer)."""
    if segment.is_synthetic:
        return f"<{segment.producer} producer>"
    return repr(segment.identity)


def _build_segment_command(
    index: int,
    segment: Segment,
    *,
    target: TargetSpec,
    profile: AccelProfile,
    options: RenderOptions,
    scratch: Path,
) -> NormalizeCommand:
    """Build the normalize command for one segment (synthetic or source).

    A synthetic segment is first materialized through its producer (rendering its
    card image into ``scratch`` as a side effect), then built overlay-free; a
    source segment takes the probe-driven normalize path.
    """
    intermediate = scratch / f"seg_{index:03d}.mp4"
    if segment.is_synthetic:
        assert segment.producer is not None
        producer = get_producer(segment.producer)
        produced = producer(segment, target, scratch / f"card_{index:03d}.png")
        return build_synthetic_normalize_command(
            segment, produced, target, profile, intermediate, render_node=options.render_node
        )
    clip = options.clip_facts.get(segment.identity) if segment.identity else None
    if clip is None:
        raise RenderError(
            f"segment {index} ({_segment_label(segment)}) has no clip facts to normalize"
        )
    return build_normalize_command(
        segment, clip, target, profile, intermediate, render_node=options.render_node
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
    """Normalize one segment (synthetic or source) to an intermediate; return ``(path, warnings)``."""
    command = _build_segment_command(
        index, segment, target=target, profile=profile, options=options, scratch=scratch
    )
    for warning in command.warnings:
        logger.warning("segment %s: %s", _segment_label(segment), warning)
    try:
        options.runtime.run_with_progress(
            command.args, duration=command.duration, on_progress=progress.step(index)
        )
    except EngineError as exc:
        raise RenderError(
            f"normalize failed for segment {index} ({_segment_label(segment)}): {exc}"
        ) from exc
    return command.output_path, command.warnings


def _check_cancelled(options: RenderOptions, *, before: str) -> None:
    """Raise :class:`RenderCancelledError` if a cancel was requested (D-S6).

    Polled at each segment boundary (and once more before the final assembly), so
    a cooperative cancel takes effect between segments rather than mid-ffmpeg.
    """
    if options.should_cancel is not None and options.should_cancel():
        raise RenderCancelledError(f"render canceled before {before}")


def _execute(
    segments: tuple[Segment, ...],
    target: TargetSpec,
    profile: AccelProfile,
    options: RenderOptions,
    output_path: Path,
) -> RenderResult:
    """Run the full pipeline: normalize/copy, equivalence-guard, assemble, verify, finalize."""
    runtime = options.runtime
    progress = _Progress(len(segments) + 1, options.on_progress)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = _part_path(output_path)

    with tempfile.TemporaryDirectory(
        prefix="auto-reel-render-", dir=str(options.temp_dir) if options.temp_dir else None
    ) as tmp:
        scratch = Path(tmp)
        warnings: list[str] = []
        intermediates: list[Path] = []
        copied_indices: list[int] = []
        for index, segment in enumerate(segments):
            _check_cancelled(options, before=f"segment {index}")
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

        _check_cancelled(options, before="final assembly")
        measured = [probe_media(Path(p), runtime=runtime).duration for p in intermediates]
        chapter_pairs = aggregate_chapter_durations(segments, measured)
        metadata_file = scratch / "chapters.ffmeta"
        metadata_file.write_text(build_ffmetadata(chapter_pairs), encoding="utf-8")

        list_file = scratch / "concat.txt"
        list_file.write_text(build_concat_list(intermediates), encoding="utf-8")
        concat_command = build_concat_command(list_file, part_path, metadata_file=metadata_file)
        try:
            runtime.run(concat_command)
        except EngineError as exc:
            raise RenderError(f"concat failed assembling {output_path.name}: {exc}") from exc
        progress.complete(len(segments))

        # Verify the .part file, not the final path: a file only ever appears at
        # output_path once it is known-complete (the atomic-finalize guarantee).
        verify_output(runtime, part_path, target)
        os.replace(part_path, output_path)

        # The manifest is written only once the output is known-complete, and only
        # when a fingerprint was supplied (D-C5); direct library use without one
        # leaves the event stale-by-absence rather than fabricating a manifest.
        if options.fingerprint is not None:
            write_manifest(
                options.event_dir,
                options.fingerprint,
                output=output_path.name,
                engine_identity=engine_identity(runtime.version),
            )

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
    "output_relpath",
    "find_output_collisions",
    "render_movie",
    "render_batch",
]
