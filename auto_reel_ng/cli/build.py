"""Shared plan-build helper (D-S1): prepare/adopt -> persist -> probe -> resolve.

The one build path from an event directory to a :class:`RenderJob`, used by both
``cmd_render`` (:mod:`.commands`) and the job-scheduler worker
(:mod:`auto_reel_ng.scheduler`). Kept in its own module, rather than
``cli/commands.py``, so the worker does not have to import the CLI's argparse
wiring to reuse it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

from ..accel.profiles.base import AccelProfile
from ..errors import MissingClipsError
from ..event import ClipOrder, resolve
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe import probe_media
from ..probe.metadata import ClipMetadata
from ..reel import ReelDocument, is_excluded
from ..render import RenderJob, RenderOptions
from ..render.orchestrator import ProgressCallback, ShouldCancel
from ..staleness.fingerprint import Fingerprint
from ..thumbs.settings import DEFAULT_POSITION
from .adoption import PreparedEvent, persist, prepare_event

logger = logging.getLogger(__name__)


def missing_clips_message(identities: Sequence[str]) -> str:
    """The one wording of the missing-clip refusal: every identity, and the fix."""
    names = ", ".join(f"'{identity}'" for identity in identities)
    fix = "(Edit mode, or reel.yaml)"
    if len(identities) == 1:
        return (
            f"clip {names} is listed in reel.yaml but is missing from the event folder; "
            f"restore the file, or remove the clip from the event {fix}"
        )
    return (
        f"{len(identities)} clips are listed in reel.yaml but missing from the event folder: "
        f"{names}; restore the files, or remove the clips from the event {fix}"
    )


def _probe_clips(
    document: ReelDocument, event_dir: Path, runtime: FfmpegRuntime
) -> Dict[str, ClipMetadata]:
    """Probe every included clip into facts keyed by identity (fail loud on a bad clip).

    Clips the document references but the folder lacks are refused first, all at once and
    by identity, so no ffprobe runs for an event that cannot render (``MissingClipsError``).
    ``exists`` follows symlinks, so a dangling one is missing; a directory or special file
    named like a clip is left to ``probe_media``, which reports it as not a regular file.
    """
    included = [
        identity
        for identity in document.referenced_identities()
        if not is_excluded(document.clips, identity)
    ]  # excluded clips never reach the plan, so do not check or probe them
    missing = [identity for identity in included if not (Path(event_dir) / identity).exists()]
    if missing:
        raise MissingClipsError(missing_clips_message(missing))
    return {
        identity: probe_media(Path(event_dir) / identity, runtime=runtime) for identity in included
    }


def prepare_and_persist(
    event_dir: Path, *, order: ClipOrder, dry_run: bool = False
) -> PreparedEvent:
    """Prepare/adopt ``event_dir`` and persist the result (never in dry-run).

    The first half of the D-S1 build path, split out so a caller (the
    change-detection gate, D-C5) can compute the render fingerprint from
    post-adoption disk state before deciding whether the second half (probe ->
    resolve, potentially expensive) is worth doing at all.
    """
    event = prepare_event(event_dir, order=order, adopt=True)
    if not dry_run:
        path = persist(event)
        if path is not None:
            logger.info("Wrote %s", path)
    return event


def build_render_job_from_event(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    event: PreparedEvent,
    *,
    output_dir: Path,
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    render_node: Optional[str],
    look_defaults: Mapping[str, object],
    dry_run: bool = False,
    overwrite: bool = False,
    on_progress: Optional[ProgressCallback] = None,
    should_cancel: Optional[ShouldCancel] = None,
    temp_dir: Optional[Path] = None,
    fingerprint: Optional[Fingerprint] = None,
    poster_position: float = DEFAULT_POSITION,
) -> RenderJob:
    """Probe ``event``'s clips, resolve its plan, and build a :class:`RenderJob`.

    The second half of the D-S1 build path: takes an already-prepared/persisted
    event (:func:`prepare_and_persist`) rather than an event directory, so a
    caller that already paid the prepare/persist cost (to compute a fingerprint
    or gate on staleness) does not pay it twice.
    """
    clip_facts = _probe_clips(event.document, event.event_dir, runtime)
    plan = resolve(event.document, look_defaults=look_defaults, clip_facts=clip_facts)
    options = RenderOptions(
        event_dir=event.event_dir,
        output_dir=output_dir,
        clip_facts=clip_facts,
        runtime=runtime,
        overwrite=overwrite,
        dry_run=dry_run,
        render_node=render_node,
        on_progress=on_progress,
        should_cancel=should_cancel,
        temp_dir=temp_dir,
        fingerprint=fingerprint,
        poster_position=poster_position,
    )
    return RenderJob(plan=plan, profile=profile, options=options)


def build_render_job(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    event_dir: Path,
    *,
    order: ClipOrder,
    output_dir: Path,
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    render_node: Optional[str],
    look_defaults: Mapping[str, object],
    dry_run: bool = False,
    overwrite: bool = False,
    on_progress: Optional[ProgressCallback] = None,
    should_cancel: Optional[ShouldCancel] = None,
    temp_dir: Optional[Path] = None,
    fingerprint: Optional[Fingerprint] = None,
    poster_position: float = DEFAULT_POSITION,
) -> Tuple[RenderJob, PreparedEvent]:
    """Prepare/adopt ``event_dir``, probe its clips, resolve the plan, build a job.

    The one build path (D-S1) shared by ``cmd_render`` and the job-scheduler
    worker: a claimed job is an event reference, never a frozen plan, so both
    callers rebuild from current disk state through this exact sequence
    (prepare/adopt -> persist -> probe -> resolve) rather than duplicating it.
    """
    event = prepare_and_persist(event_dir, order=order, dry_run=dry_run)
    job = build_render_job_from_event(
        event,
        output_dir=output_dir,
        runtime=runtime,
        profile=profile,
        render_node=render_node,
        look_defaults=look_defaults,
        dry_run=dry_run,
        overwrite=overwrite,
        on_progress=on_progress,
        should_cancel=should_cancel,
        temp_dir=temp_dir,
        fingerprint=fingerprint,
        poster_position=poster_position,
    )
    return job, event


__all__ = ["prepare_and_persist", "build_render_job_from_event", "build_render_job"]
