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
from typing import Dict, Mapping, Optional, Tuple

from ..accel.profiles.base import AccelProfile
from ..event import resolve
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe import probe_media
from ..probe.metadata import ClipMetadata
from ..reel import ReelDocument
from ..render import RenderJob, RenderOptions
from ..render.orchestrator import ProgressCallback, ShouldCancel
from .adoption import PreparedEvent, persist, prepare_event

logger = logging.getLogger(__name__)


def _probe_clips(
    document: ReelDocument, event_dir: Path, runtime: FfmpegRuntime
) -> Dict[str, ClipMetadata]:
    """Probe every included clip into facts keyed by identity (fail loud on a bad clip)."""
    facts: Dict[str, ClipMetadata] = {}
    for identity in document.referenced_identities():
        props = document.clips.get(identity)
        if props is not None and props.exclude:
            continue  # excluded clips never reach the plan, so do not probe them
        facts[identity] = probe_media(Path(event_dir) / identity, runtime=runtime)
    return facts


def build_render_job(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    event_dir: Path,
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
) -> Tuple[RenderJob, PreparedEvent]:
    """Prepare/adopt ``event_dir``, probe its clips, resolve the plan, build a job.

    The one build path (D-S1) shared by ``cmd_render`` and the job-scheduler
    worker: a claimed job is an event reference, never a frozen plan, so both
    callers rebuild from current disk state through this exact sequence
    (prepare/adopt -> persist -> probe -> resolve) rather than duplicating it.
    """
    event = prepare_event(event_dir, adopt=True)

    # Persist the seeded/adopted document so it is stable next run — never in dry-run.
    if not dry_run:
        path = persist(event)
        if path is not None:
            logger.info("Wrote %s", path)

    clip_facts = _probe_clips(event.document, event_dir, runtime)
    plan = resolve(event.document, look_defaults=look_defaults, clip_facts=clip_facts)
    options = RenderOptions(
        event_dir=event_dir,
        output_dir=output_dir,
        clip_facts=clip_facts,
        runtime=runtime,
        overwrite=overwrite,
        dry_run=dry_run,
        render_node=render_node,
        on_progress=on_progress,
        should_cancel=should_cancel,
        temp_dir=temp_dir,
    )
    return RenderJob(plan=plan, profile=profile, options=options), event


__all__ = ["build_render_job"]
