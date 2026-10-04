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
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Callable, Hashable, Mapping, Optional, Sequence, TypeVar

from ..accel.profiles.base import AccelProfile
from ..errors import (
    EngineError,
    FfmpegCancelledError,
    FfmpegStalledError,
    RenderCancelledError,
    RenderError,
)
from ..event.plan import RenderPlan
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe import probe_media
from ..probe.metadata import ClipMetadata
from ..reel.document import Metadata
from ..staleness.fingerprint import Fingerprint, engine_identity
from ..staleness.manifest import write_manifest
from ..thumbs.settings import DEFAULT_POSITION
from .chapters import aggregate_chapter_durations, build_ffmetadata, chapter_times
from .concat import build_concat_command, build_concat_list, is_copy_uniform
from .decorators import apply_decorators, resolve_decorator_names
from .normalize import (
    NormalizeCommand,
    build_normalize_command,
    build_synthetic_normalize_command,
    decide_copy_eligibility,
)
from .poster import (
    PosterChoice,
    PosterResolution,
    cover_part_path,
    embed_cover,
    extract_poster,
    poster_args,
    poster_part_path,
    poster_path,
    resolve_poster,
)
from .producers import get_producer, materialize_overlay
from .segments import Segment, build_segments
from .target import TargetSpec, derive_target
from .verify import verify_output

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]
ShouldCancel = Callable[[], bool]

#: How long a segment encode may go without ffmpeg's reported output time advancing before it
#: is killed and the render fails (render-stall-watchdog, D-19). A policy constant, not a
#: config key: ffmpeg reports about twice a second while it works, so ten minutes is far past
#: any healthy gap, yet bounds a hung driver or a dead mount. Not a measurement of a real hang.
SEGMENT_STALL_TIMEOUT_S = 600.0


@dataclass
class RenderOptions:  # pylint: disable=too-many-instance-attributes
    """Inputs and switches for one movie render.

    ``event_dir`` roots clip identities to files; ``clip_facts`` carries the
    probed metadata keyed by identity; ``runtime`` runs the commands. ``overwrite``
    replaces an existing output, ``dry_run`` builds + reports commands without
    executing or writing, ``render_node`` targets a specific GPU, ``on_progress``
    receives an overall 0.0-1.0 fraction, and ``temp_dir`` overrides the base for
    the ephemeral per-render scratch directory. ``should_cancel``, when given, is
    polled at each segment boundary (job-scheduler, D-S6) and about once a second while
    a segment is encoded; a true result stops the render (before the next segment, or by
    killing the running ffmpeg) and raises :class:`RenderCancelledError` rather than
    completing or failing the render. ``fingerprint``, when given, is
    the caller's pre-render staleness fingerprint (change-detection, D-C5); the
    render manifest is written from it immediately after the atomic finalize
    succeeds, and never on skip/dry-run/failure/absent fingerprint. ``poster_position`` is the
    configured ``thumbnails.position``: where the default poster frame is taken.
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
    poster_position: float = DEFAULT_POSITION


@dataclass(frozen=True)
class RenderResult:
    """The outcome of a single movie render."""

    output_path: Path
    skipped: bool = False
    dry_run: bool = False
    commands: tuple[tuple[str, ...], ...] = ()
    warnings: tuple[str, ...] = ()
    #: The poster sidecar this render wrote (or would write, on a dry run); ``None`` when the
    #: event has no played clip or the render was skipped.
    poster_path: Optional[Path] = None


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


def _name_part(text: str) -> str:
    """``text`` made safe as part of ONE path component: separators and controls become ``-``.

    ``/`` and ``\\`` (a separator on the SMB side of the archive) and every control
    character (code point < 0x20, 0x7f; NUL included) are replaced by ``-`` one for
    one, so a title can never add a folder or form a ``..`` component. Only the file
    name is affected; the authored text is never altered.
    """
    return "".join(
        "-" if char in "/\\" or ord(char) < 0x20 or ord(char) == 0x7F else char for char in text
    )


def output_filename(metadata: Metadata) -> str:
    """``[<YYYY-MM-DD> - ]<title>[ - <location>].mp4``, the legacy auto-reel name.

    A dated event's name starts with its ISO date (legacy ``directory.py:220``);
    an undated event has no prefix. The location, when present, is appended. The
    title and location are sanitised (:func:`_name_part`) so the result is always a
    single path component.
    """
    stem = _name_part(metadata.title) if metadata.title else "Untitled"
    if metadata.date is not None:
        stem = f"{metadata.date.isoformat()} - {stem}"
    if metadata.location:
        return f"{stem} - {_name_part(metadata.location)}.mp4"
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


def _plan_clip_facts(
    plan: RenderPlan, clip_facts: Mapping[str, ClipMetadata]
) -> list[ClipMetadata]:
    """Return the probed facts of every clip in the plan, or fail loud."""
    facts: list[ClipMetadata] = []
    for chapter in plan.chapters:
        for clip in chapter.clips:
            clip_meta = clip_facts.get(clip.identity)
            if clip_meta is None:
                raise RenderError(
                    f"clip {clip.identity!r} has no probed metadata; cannot derive target"
                )
            facts.append(clip_meta)
    if not facts:
        raise RenderError("render plan has no clips to render")
    return facts


def resolve_target(
    plan: RenderPlan, profile: AccelProfile, clip_facts: Mapping[str, ClipMetadata]
) -> TargetSpec:
    """Derive the :class:`TargetSpec` for ``plan`` under ``profile`` (public seam).

    The same derivation :func:`render_movie` performs internally, exposed so a
    caller can learn the resolved encoder (job-scheduler capacity classification,
    D-S3) before committing to a render.
    """
    return derive_target(plan.look, _plan_clip_facts(plan, clip_facts), profile)


# The overall progress span: the normalize pass fills [0, normalize_end], a possible re-encode
# pass has its own reserved stretch above it (only when a segment is copy-eligible), and the
# concat owns the top _CONCAT_SHARE. Weights are an estimate of work, not of wall-clock time.
_CONCAT_SHARE = 0.05
_REENCODE_SHARE = 0.15


def _segment_weight(segment: Segment, clip_facts: Mapping[str, ClipMetadata]) -> float:
    """The expected work to normalize ``segment``: its intended duration, else ``0.0``.

    A kept span or a synthetic segment weighs its duration; a whole clip weighs its probed
    duration. An unknown duration weighs nothing (the weight only paces progress; a source
    segment without facts fails loudly when its command is built).
    """
    duration = segment.span_duration
    if duration is None and segment.identity is not None:
        facts = clip_facts.get(segment.identity)
        duration = facts.duration if facts is not None else None
    return max(0.0, duration) if duration is not None else 0.0


class _Progress:
    """Maps per-step fractions into one overall, non-decreasing 0.0-1.0 callback.

    Every value goes through :meth:`_emit`, which drops anything not above the highest
    value delivered so far, so a re-run step (the re-encode pass, a software-decode retry)
    can only hold or raise the reported progress (movie-assembly: render progress).
    """

    def __init__(
        self,
        callback: Optional[ProgressCallback],
        weights: Mapping[int, float],
        *,
        normalize_end: float,
    ) -> None:
        self._callback = callback
        self._high = 0.0
        self._set_pass(weights, start=0.0, end=normalize_end)

    def _set_pass(self, weights: Mapping[int, float], *, start: float, end: float) -> None:
        """Map the segments in ``weights`` onto ``[start, end]`` in proportion to their weight."""
        self._start = start
        self._end = max(start, end)
        self._before: dict[int, float] = {}
        total = 0.0
        for index in sorted(weights):
            self._before[index] = total
            total += weights[index]
        self._weights = dict(weights)
        self._total = total

    def _emit(self, value: float) -> None:
        value = min(1.0, value)
        if value <= self._high:
            return
        self._high = value
        if self._callback is not None:
            self._callback(value)

    def step(self, index: int) -> Optional[ProgressCallback]:
        """Return a callback scaling a step's local fraction into the global one.

        ``None`` when nobody listens or the step carries no weight (nothing to report).
        """
        weight = self._weights.get(index, 0.0)
        if self._callback is None or weight <= 0.0 or self._total <= 0.0:
            return None
        before = self._before[index]
        span = self._end - self._start

        def scaled(local: float) -> None:
            done = before + weight * min(1.0, max(0.0, local))
            self._emit(self._start + span * done / self._total)

        return scaled

    def begin_reencode(self, weights: Mapping[int, float], *, end: float) -> None:
        """Start the re-encode pass: it moves forward from the highest value so far to ``end``."""
        self._set_pass(weights, start=self._high, end=end)

    def advance_to_concat(self) -> None:
        """Report the start of the concat share (the pre-flight has passed)."""
        self._emit(1.0 - _CONCAT_SHARE)

    def finish(self) -> None:
        """Report the render's work finished (the concat has completed)."""
        self._emit(1.0)


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
    # Before any segment is built or encoded: a poster time past its clip's end fails the event.
    poster = resolve_poster(plan, options.clip_facts, position=options.poster_position)

    segments = build_segments(plan, options.event_dir, options.clip_facts)
    names = resolve_decorator_names(plan.look)
    segments = apply_decorators(names, plan, target, segments)
    segments = decide_copy_eligibility(segments, options.clip_facts, target)
    if not segments:
        raise RenderError("render plan produced no segments to render")

    output_path = Path(options.output_dir) / output_relpath(plan.metadata)
    _require_inside(output_path, Path(options.output_dir))

    if options.dry_run:
        return _plan_only(segments, target, profile, options, output_path, poster=poster)

    if output_path.exists() and not output_path.is_file():
        # A folder (or other non-file) where the movie belongs is not a render to skip or to
        # replace: the engine never removes what it did not write (change-detection).
        raise RenderError(
            f"{output_path} exists and is not a regular file; refusing to render over it"
        )

    if output_path.exists() and not options.overwrite:
        logger.info("Output %s exists and overwrite not requested; skipping", output_path)
        return RenderResult(output_path=output_path, skipped=True)

    try:
        return _execute(segments, target, profile, options, output_path, poster=poster)
    except BaseException:
        # Never present a half-written output as a finished render; the final paths
        # are untouched until the atomic renames, so only the .part files need cleanup.
        for leftover in (
            _part_path(output_path),
            cover_part_path(output_path),
            poster_part_path(output_path),
        ):
            if leftover.exists():
                leftover.unlink()
        raise


def _require_inside(output_path: Path, output_dir: Path) -> None:
    """Refuse an output path that lies outside ``output_dir`` (lexical; no filesystem access).

    Backstop for :func:`output_filename`: ``..`` or absolute components must never
    reach a directory creation or a write. Lexical on purpose — a symlinked year
    folder is a legitimate archive layout that ``resolve()`` would wrongly refuse.
    """
    root = os.path.abspath(output_dir)
    candidate = os.path.abspath(output_path)
    if candidate != root and not candidate.startswith(root.rstrip(os.sep) + os.sep):
        raise RenderError(f"output path {output_path} is outside the output directory {output_dir}")


def _plan_only(
    segments: tuple[Segment, ...],
    target: TargetSpec,
    profile: AccelProfile,
    options: RenderOptions,
    output_path: Path,
    *,
    poster: PosterResolution = PosterResolution(None),
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
    if poster.choice is not None:
        commands.append(
            tuple(
                poster_args(
                    options.clip_facts[poster.choice.identity],
                    poster.choice,
                    target=target,
                    output=poster_part_path(output_path),
                )
            )
        )
    return RenderResult(
        output_path=output_path,
        dry_run=True,
        commands=tuple(commands),
        warnings=(*poster.warnings, *warnings),
        poster_path=None if poster.choice is None else poster_path(output_path),
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
    force_software_decode: bool = False,
) -> NormalizeCommand:
    """Build the normalize command for one segment (synthetic or source).

    A synthetic segment is first materialized through its producer (rendering its
    card image into ``scratch`` as a side effect), then built overlay-free; a
    source segment takes the probe-driven normalize path, with ``force_software_decode``
    set only for the retry of a failed hardware-decode initialisation. A source segment's
    producer-backed overlays (an attached title card) are materialized first, so a planned
    command names a real image as a run one does.
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
    if any(overlay.producer is not None for overlay in segment.overlays):
        segment = replace(
            segment,
            overlays=tuple(
                materialize_overlay(overlay, target, scratch / f"card_{index:03d}_{n}.png")
                for n, overlay in enumerate(segment.overlays)
            ),
        )
    return build_normalize_command(
        segment,
        clip,
        target,
        profile,
        intermediate,
        render_node=options.render_node,
        force_software_decode=force_software_decode,
    )


#: ffmpeg phrases for a hardware decoder that could not be set up for a stream. Only these
#: are retried in software; any other failure (a corrupt input, say) is raised as it is.
_HW_DECODE_INIT_FAILURES = ("hwaccel initialisation returned error", "Failed setup for format")


def _hw_decode_init_failure(exc: EngineError) -> Optional[str]:
    """The first ffmpeg line naming a hardware-decode initialisation failure, else ``None``.

    A stalled run never counts, whatever stderr it had printed before it hung: retrying it
    would only double the wait.
    """
    if isinstance(exc, FfmpegStalledError):
        return None
    for line in str(exc).splitlines():
        if any(phrase in line for phrase in _HW_DECODE_INIT_FAILURES):
            return line.strip()
    return None


def _run_segment(
    index: int,
    segment: Segment,
    command: NormalizeCommand,
    *,
    options: RenderOptions,
    progress: _Progress,
) -> None:
    """Run one segment's normalize command under the stall limit and the cancel check.

    Raises:
        RenderCancelledError: the cancel check reported true while ffmpeg was encoding;
            ffmpeg was killed (a cancel is never retried or reported as a failure).
        EngineError: any other failure, including a stall (:class:`FfmpegStalledError`).
    """
    try:
        options.runtime.run_with_progress(
            command.args,
            duration=command.duration,
            on_progress=progress.step(index),
            stall_timeout=SEGMENT_STALL_TIMEOUT_S,
            should_cancel=options.should_cancel,
        )
    except FfmpegCancelledError as exc:
        raise RenderCancelledError(
            f"render canceled during segment {index} ({_segment_label(segment)})"
        ) from exc


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
    """Normalize one segment (synthetic or source) to an intermediate; return ``(path, warnings)``.

    A source segment whose hardware decode fails to initialise is run once more with
    software decode (``_retry_in_software``); every other failure is raised as it is.
    """
    try:
        command = _build_segment_command(
            index, segment, target=target, profile=profile, options=options, scratch=scratch
        )
    except RenderError as exc:
        raise RenderError(
            f"normalize failed for segment {index} ({_segment_label(segment)}): {exc}"
        ) from exc
    for warning in command.warnings:
        logger.warning("segment %s: %s", _segment_label(segment), warning)
    try:
        _run_segment(index, segment, command, options=options, progress=progress)
    except RenderCancelledError:
        raise  # a cancel is not a failure to wrap, nor a hardware-decode failure to retry
    except EngineError as exc:
        failure = _hw_decode_init_failure(exc) if command.hardware_decode else None
        if failure is None:
            raise RenderError(
                f"normalize failed for segment {index} ({_segment_label(segment)}): {exc}"
            ) from exc
        return _retry_in_software(
            index,
            segment,
            first=exc,
            target=target,
            profile=profile,
            options=options,
            scratch=scratch,
            progress=progress,
        )
    return command.output_path, command.warnings


def _retry_in_software(
    index: int,
    segment: Segment,
    *,
    first: EngineError,
    target: TargetSpec,
    profile: AccelProfile,
    options: RenderOptions,
    scratch: Path,
    progress: _Progress,
) -> tuple[Path, tuple[str, ...]]:
    """Run one segment again with software decode after its hardware decode failed to start.

    The retry writes the same intermediate (``-y`` replaces the failed attempt's partial
    file) and happens at most once. The recovered first failure is logged and returned as
    a warning so it reaches the render result; a failed retry is raised with both
    attempts' detail, never dropped.
    """
    label = _segment_label(segment)
    failure = _hw_decode_init_failure(first) or str(first)
    warning = f"segment {label}: hardware decode failed, retrying with software decode: {failure}"
    logger.warning(warning)
    try:
        command = _build_segment_command(
            index,
            segment,
            target=target,
            profile=profile,
            options=options,
            scratch=scratch,
            force_software_decode=True,
        )
    except RenderError as rebuild_error:
        # The profile cannot express the software path (e.g. no verified upload device).
        raise RenderError(
            f"normalize failed for segment {index} ({label}): hardware decode failed "
            f"({failure}) and the software retry cannot be built: {rebuild_error}"
        ) from first
    try:
        _run_segment(index, segment, command, options=options, progress=progress)
    except RenderCancelledError:
        raise  # a cancel is not a failure to wrap, nor a hardware-decode failure to retry
    except EngineError as exc:
        raise RenderError(
            f"normalize failed for segment {index} ({label}) in software decode, after its "
            f"hardware decode failed first ({failure}): {exc}"
        ) from exc
    return command.output_path, (*command.warnings, warning)


def _check_cancelled(options: RenderOptions, *, before: str) -> None:
    """Raise :class:`RenderCancelledError` if a cancel was requested (D-S6).

    Polled at each segment boundary (and once more before the final assembly); a cancel
    during a segment's encode is caught by the runtime's own poll (:func:`_run_segment`).
    """
    if options.should_cancel is not None and options.should_cancel():
        raise RenderCancelledError(f"render canceled before {before}")


def _plan_progress(segments: tuple[Segment, ...], options: RenderOptions) -> _Progress:
    """Build the progress mapper: weights by expected work, copy-eligible segments weigh nothing."""
    copyable = [bool(s.copy_eligible and s.source_path is not None) for s in segments]
    weights = {
        index: 0.0 if copyable[index] else _segment_weight(segment, options.clip_facts)
        for index, segment in enumerate(segments)
    }
    normalize_end = 1.0 - _CONCAT_SHARE - (_REENCODE_SHARE if any(copyable) else 0.0)
    return _Progress(options.on_progress, weights, normalize_end=normalize_end)


def _execute(
    segments: tuple[Segment, ...],
    target: TargetSpec,
    profile: AccelProfile,
    options: RenderOptions,
    output_path: Path,
    *,
    poster: PosterResolution = PosterResolution(None),
) -> RenderResult:
    """Run the full pipeline: normalize/copy, equivalence-guard, assemble, verify, finalize.

    The poster frame is extracted first (a ``.part`` beside the movie) so a frame that cannot be
    read fails the event before the encode; it is embedded into the verified movie, and the
    poster is renamed into place just before the movie, which is renamed last.
    """
    runtime = options.runtime
    progress = _plan_progress(segments, options)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = _part_path(output_path)
    if poster.choice is not None:
        _extract_poster(poster.choice, target, options, output_path)

    with tempfile.TemporaryDirectory(
        prefix="auto-reel-render-", dir=str(options.temp_dir) if options.temp_dir else None
    ) as tmp:
        scratch = Path(tmp)
        warnings: list[str] = list(poster.warnings)
        intermediates: list[Path] = []
        copied_indices: list[int] = []
        for index, segment in enumerate(segments):
            _check_cancelled(options, before=f"segment {index}")
            if segment.copy_eligible and segment.source_path is not None:
                intermediates.append(segment.source_path)
                copied_indices.append(index)
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
            progress.begin_reencode(
                {i: _segment_weight(segments[i], options.clip_facts) for i in copied_indices},
                end=1.0 - _CONCAT_SHARE,
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
        progress.advance_to_concat()

        _check_cancelled(options, before="final assembly")
        measured = [probe_media(Path(p), runtime=runtime).duration for p in intermediates]
        chapter_pairs = aggregate_chapter_durations(segments, measured)
        # The recorded chapter times come from the same measured durations and boundary rule as
        # the muxed markers; computed before the concat (after the segments are normalized), so a
        # malformed plan fails before the final assembly.
        chapters = chapter_times(segments, measured)
        metadata_file = scratch / "chapters.ffmeta"
        metadata_file.write_text(build_ffmetadata(chapter_pairs), encoding="utf-8")

        list_file = scratch / "concat.txt"
        list_file.write_text(build_concat_list(intermediates), encoding="utf-8")
        concat_command = build_concat_command(list_file, part_path, metadata_file=metadata_file)
        try:
            runtime.run(concat_command)
        except EngineError as exc:
            raise RenderError(f"concat failed assembling {output_path.name}: {exc}") from exc
        progress.finish()

        # Verify the .part file, not the final path: a file only ever appears at
        # output_path once it is known-complete (the atomic-finalize guarantee).
        verify_output(runtime, part_path, target)
        if poster.choice is not None:
            _embed_poster(runtime, part_path, output_path, target)
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
                chapters=chapters,
                poster=None if poster.choice is None else poster_path(output_path).name,
            )

    return RenderResult(
        output_path=output_path,
        warnings=tuple(warnings),
        poster_path=None if poster.choice is None else poster_path(output_path),
    )


def _extract_poster(
    choice: PosterChoice, target: TargetSpec, options: RenderOptions, output_path: Path
) -> None:
    """Write the poster frame to its ``.part`` beside the movie, verified."""
    extract_poster(
        options.runtime,
        options.clip_facts[choice.identity],
        choice,
        target=target,
        output=poster_part_path(output_path),
    )


def _embed_poster(
    runtime: FfmpegRuntime, part_path: Path, output_path: Path, target: TargetSpec
) -> None:
    """Embed the extracted poster into the verified ``part_path`` and move the poster into place.

    The cover goes into ``<movie>.cover.part``, which is verified again (exactly one ``mjpeg``
    cover beside the one video stream) and replaces the movie ``.part``; the poster is then renamed
    to its final name, just before the caller renames the movie, which is always last.
    """
    cover_part = cover_part_path(output_path)
    embed_cover(runtime, part_path, poster_part_path(output_path), cover_part)
    verify_output(runtime, cover_part, target, cover=True)
    os.replace(cover_part, part_path)
    os.replace(poster_part_path(output_path), poster_path(output_path))


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
