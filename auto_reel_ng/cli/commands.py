"""The ``auto-reel`` subcommand implementations: render / scan / analyze / import.

This module is almost entirely *wiring*: it consumes existing engine APIs unchanged
and applies the three CLI decisions — layout selection + config layering, the
adoption policy (delegated to :mod:`.adoption`), and per-event isolation with an
exit code that reflects per-event outcomes (D-CLI5).

The ``render`` flow is structured ``enumerate -> [staleness seam] -> build jobs ->
render_batch`` so a future ``is_stale(event)`` gate (deferred, §8.14) is a localized
insertion (:func:`_staleness_filter`).
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from ruamel.yaml import YAML

from ..accel import AccelProfile, detect_capabilities, select_profile
from ..accel.profiles.hardware import HardwareProfile
from ..analysis import Segment, analyze_event
from ..config import ProjectConfig, load_project_config, resolve_look_defaults
from ..errors import EngineError
from ..event import ReconcileResult, reconcile, scan_event
from ..ffmpeg.runtime import FfmpegRuntime
from ..ingest import DEFAULT_LAYOUT, EventRef, get_layout
from ..persistence.config import resolve_database_url
from ..persistence.engine import make_engine, make_session_factory
from ..persistence.job_store import JobStore
from ..persistence.models import JobStatus
from ..reel import ReelDocument, import_legacy, load_document, write_document
from ..reel.legacy import ImportResult
from ..render import RenderJob, render_batch
from ..scheduler import (
    CapacityPools,
    Worker,
    default_build_job,
    resolve_worker_config,
    worker_identity,
)
from .adoption import REEL_FILENAME
from .build import build_render_job

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Shared project context
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProjectContext:
    """The resolved settings for one CLI invocation (layout, paths, events)."""

    project_root: Path
    walk_root: Path
    output_dir: Path
    layout_name: str
    config: ProjectConfig
    events: List[EventRef]


def _project_context(args: argparse.Namespace) -> ProjectContext:
    """Resolve the project root, config, layout, paths, and enumerate events.

    Precedence (D-CLI2): a CLI flag wins over ``config.yaml``, which wins over the
    built-in default. ``config.yaml`` is read from the project root the layout walks.
    """
    project_root = Path(args.root).resolve() if args.root else Path.cwd()
    if not project_root.is_dir():
        raise FileNotFoundError(
            f"project root does not exist or is not a directory: {project_root}"
        )

    config = load_project_config(project_root)
    walk_root = (project_root / config.input_dir) if config.input_dir else project_root

    if args.output:
        output_dir = Path(args.output)
    elif config.output_dir:
        output_dir = project_root / config.output_dir
    else:
        output_dir = project_root / "output"

    layout_name = args.layout or config.layout or DEFAULT_LAYOUT
    layout = get_layout(layout_name)
    years = args.years  # a tuple parsed by the CLI, or None
    events = list(layout(walk_root, years))

    return ProjectContext(
        project_root=project_root,
        walk_root=walk_root,
        output_dir=output_dir,
        layout_name=layout_name,
        config=config,
        events=events,
    )


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #


def cmd_render(args: argparse.Namespace) -> int:
    """``render``: scan -> reconcile -> probe -> resolve -> select -> render_batch."""
    ctx = _project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    runtime = FfmpegRuntime()
    look_defaults = resolve_look_defaults(ctx.config)

    # Select the acceleration profile once (D-CLI4); --device is the explicit override.
    inventory = detect_capabilities(runtime)
    profile = select_profile(inventory, override=args.device)
    render_node = _selected_render_node(profile)
    logger.info("Selected %s profile (render_node=%s)", profile.vendor.value, render_node)

    # enumerate -> [staleness seam, no-op in this slice] -> build jobs -> render_batch
    candidates = _staleness_filter(ctx.events)

    jobs: List[RenderJob] = []
    build_failures: List[Tuple[Path, str]] = []
    for ref in candidates:
        try:
            jobs.append(
                _build_job(
                    ref,
                    ctx,
                    runtime=runtime,
                    profile=profile,
                    render_node=render_node,
                    look_defaults=look_defaults,
                    dry_run=args.dry_run,
                    overwrite=args.overwrite,
                )
            )
        except EngineError as exc:
            # Isolate per-event build failures the same way render_batch isolates
            # render failures (D-CLI5): one bad event never aborts the rest.
            logger.error("Skipping %s: %s", ref.event_dir.name, exc)
            build_failures.append((ref.event_dir, str(exc)))

    outcomes = render_batch(jobs)
    return _report_render(outcomes, build_failures, dry_run=args.dry_run)


def _build_job(
    ref: EventRef,
    ctx: ProjectContext,
    *,
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    render_node: Optional[str],
    look_defaults: Mapping[str, object],
    dry_run: bool,
    overwrite: bool,
) -> RenderJob:
    """Resolve one event into a :class:`RenderJob`, reporting adopt/missing to stdout."""
    job, event = build_render_job(
        ref.event_dir,
        output_dir=ctx.output_dir,
        runtime=runtime,
        profile=profile,
        render_node=render_node,
        look_defaults=look_defaults,
        dry_run=dry_run,
        overwrite=overwrite,
    )

    if event.adopted:
        print(f"+  {ref.event_dir.name}: adopted {len(event.adopted)} new clip(s)")
    if event.reconcile.missing:
        # MISSING is reported loudly and never removed from the document (D-CLI3).
        print(
            f"!  {ref.event_dir.name}: {len(event.reconcile.missing)} MISSING clip(s) "
            f"referenced but absent: {', '.join(event.reconcile.missing)}"
        )

    return job


def _selected_render_node(profile: AccelProfile) -> Optional[str]:
    """The DRM render node of the selected hardware device, or None for CPU (D-CLI4)."""
    if isinstance(profile, HardwareProfile) and profile.capabilities.device is not None:
        return profile.capabilities.device.render_node
    return None


def _staleness_filter(events: List[EventRef]) -> List[EventRef]:
    """Seam where a future ``is_stale(event)`` gate slots in (deferred, §8.14).

    For now it is the identity filter — every enumerated event is a render candidate.
    Keeping it a distinct step makes inserting the change-detection gate later a
    localized edit (enumerate -> [here] -> build jobs -> render_batch).
    """
    return list(events)


def _report_render(outcomes: list, build_failures: List[Tuple[Path, str]], *, dry_run: bool) -> int:
    """Print per-event results and return the process exit code (D-CLI5)."""
    errors = 0
    for path, message in build_failures:
        print(f"ERROR  {path.name}: {message}")
        errors += 1

    for outcome in outcomes:
        name = outcome.job.options.event_dir.name
        if outcome.error is not None:
            print(f"ERROR  {name}: {outcome.error}")
            errors += 1
            continue
        result = outcome.result
        if dry_run:
            print(f"DRY-RUN {name}: {len(result.commands)} command(s) -> {result.output_path}")
            for command in result.commands:
                print("    " + " ".join(command))
        elif result.skipped:
            print(f"SKIP   {name}: {result.output_path} exists (use --overwrite)")
        else:
            print(f"OK     {name}: {result.output_path}")
        for warning in result.warnings:
            print(f"  warn: {warning}")

    total = len(outcomes) + len(build_failures)
    print(f"\n{total - errors}/{total} event(s) succeeded")
    return 1 if errors else 0


# --------------------------------------------------------------------------- #
# scan / list
# --------------------------------------------------------------------------- #


def cmd_scan(args: argparse.Namespace) -> int:
    """``scan``/``list``: report events and clip reconcile status; render nothing."""
    ctx = _project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    for ref in ctx.events:
        # Reconcile disk against the persisted reel.yaml (None -> every clip NEW);
        # scan never seeds, adopts, or writes anything.
        reel_path = ref.event_dir / REEL_FILENAME
        document = load_document(reel_path) if reel_path.exists() else None
        listing = scan_event(ref.event_dir)
        result = reconcile(listing.identities, document)
        _print_inventory(ref, document, result)
    return 0


def _print_inventory(
    ref: EventRef, document: Optional[ReelDocument], result: ReconcileResult
) -> None:
    """Print one event with each clip classified NEW/ACTIVE/IGNORED/MISSING."""
    title = _event_title(ref, document)
    print(f"\n{title}  [{ref.event_dir}]")
    classification = result.classification
    if not classification:
        print("  (no clips)")
        return
    for identity in sorted(classification):
        print(f"  {classification[identity].value.upper():8} {identity}")
    if result.missing:
        print(f"  ! {len(result.missing)} MISSING clip(s) referenced but absent from disk")


def _event_title(ref: EventRef, document: Optional[ReelDocument]) -> str:
    """A display title: the document's, else the folder-name hint, else the dir name."""
    if document is not None and document.metadata.title:
        return document.metadata.title
    if ref.metadata_hint is not None:
        return ref.metadata_hint.title
    return ref.event_dir.name


# --------------------------------------------------------------------------- #
# analyze
# --------------------------------------------------------------------------- #


def cmd_analyze(args: argparse.Namespace) -> int:
    """``analyze``: run detection over selected events; print + cache; never touch reel.yaml."""
    ctx = _project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    runtime = FfmpegRuntime()
    for ref in ctx.events:
        results = analyze_event(ref.event_dir, runtime=runtime)
        _print_analysis(ref.event_dir, results)
    return 0


def _print_analysis(event_dir: Path, results: Dict[str, List[Segment]]) -> None:
    """Print detected segments per clip (suggestion-only; reel.yaml is untouched)."""
    print(f"\n{event_dir.name}  [{event_dir}]")
    if not results:
        print("  (no clips)")
        return
    for identity in sorted(results):
        segments = results[identity]
        if not segments:
            print(f"  {identity}: no segments")
            continue
        print(f"  {identity}: {len(segments)} segment(s)")
        for seg in segments:
            print(
                f"    {seg.kind.value:6} {seg.start:.3f}-{seg.end:.3f}s "
                f"(confidence {seg.confidence:.2f})"
            )


# --------------------------------------------------------------------------- #
# import
# --------------------------------------------------------------------------- #


def cmd_import(args: argparse.Namespace) -> int:
    """``import``: adopt auto-reel legacy metadata into a v2 ``reel.yaml``."""
    ctx = _project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    imported = 0
    for ref in ctx.events:
        result = _import_event(ref.event_dir, overwrite=args.overwrite)
        if result is not None:
            imported += 1
            _report_import(ref.event_dir, result)
    print(f"\nimported {imported} event(s)")
    return 0


def _import_event(event_dir: Path, *, overwrite: bool) -> Optional[ImportResult]:
    """Import one event's legacy metadata into a v2 ``reel.yaml`` (or skip)."""
    legacy_path = _legacy_source(event_dir)
    if legacy_path is None:
        logger.debug("No legacy metadata in %s", event_dir)
        return None

    reel_path = event_dir / REEL_FILENAME
    # Refuse to clobber an existing *v2* reel.yaml unless asked; a legacy reel.yaml
    # (no version key) is the migration source and is rewritten in place.
    if reel_path.exists() and _has_version(reel_path) and not overwrite:
        print(f"SKIP   {event_dir.name}: a v2 reel.yaml already exists (use --overwrite)")
        return None

    data = _read_yaml(legacy_path)
    result = import_legacy(data, source=str(legacy_path))
    write_document(result.document, reel_path)
    return result


def _legacy_source(event_dir: Path) -> Optional[Path]:
    """The legacy file to import: ``metadata.yaml``, else a versionless ``reel.yaml``."""
    metadata = event_dir / "metadata.yaml"
    if metadata.exists():
        return metadata
    reel = event_dir / REEL_FILENAME
    if reel.exists() and not _has_version(reel):
        return reel
    return None


def _report_import(event_dir: Path, result: ImportResult) -> None:
    """Print what an import carried over and what it could not map."""
    metadata = result.document.metadata
    present = [
        name
        for name, value in (
            ("title", metadata.title),
            ("date", metadata.date),
            ("location", metadata.location),
            ("description", metadata.description),
        )
        if value is not None
    ]
    print(f"OK     {event_dir.name}: imported {', '.join(present) or 'no metadata fields'}")
    if result.document.look:
        print(f"  look: {sorted(result.document.look)}")
    for field_name in result.unmapped:
        print(f"  unmapped: {field_name}")


def _read_yaml(path: Path) -> Mapping[str, object]:
    """Read a YAML mapping from ``path`` for the legacy importer."""
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"{path}: legacy metadata must be a mapping, got {type(data).__name__}")
    return data


def _has_version(path: Path) -> bool:
    """True when a YAML file declares a top-level ``version`` key (i.e. is v2, not legacy)."""
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    return isinstance(data, Mapping) and "version" in data


# --------------------------------------------------------------------------- #
# job-scheduler: shared helpers
# --------------------------------------------------------------------------- #


def _resolve_project_root(args: argparse.Namespace) -> Path:
    """Resolve the project root positional arg (shared by worker/jobs, D-CLI2)."""
    project_root = Path(args.root).resolve() if args.root else Path.cwd()
    if not project_root.is_dir():
        raise FileNotFoundError(
            f"project root does not exist or is not a directory: {project_root}"
        )
    return project_root


def _job_store(project_root: Path) -> JobStore:
    """Build a :class:`JobStore` bound to the ``DATABASE_URL`` resolved for ``project_root``."""
    database_url = resolve_database_url(project_root)
    engine = make_engine(database_url)
    return JobStore(make_session_factory(engine))


def _parse_job_id(value: str) -> Optional[uuid.UUID]:
    """Parse a job id, returning ``None`` (rather than raising) on a malformed string."""
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# enqueue
# --------------------------------------------------------------------------- #


def cmd_enqueue(args: argparse.Namespace) -> int:
    """``enqueue``: scan via ingest layout, insert one queued job per event.

    Never probes or renders (D-S8) — it only records intent, reusing the same
    layout selection + config layering as ``render``/``scan``.
    """
    ctx = _project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    store = _job_store(ctx.project_root)
    device = args.device or "auto"
    project_root_str = str(ctx.project_root)

    created = 0
    for ref in ctx.events:
        event_dir = str(ref.event_dir.relative_to(ctx.project_root))
        # Best-effort classification for the report only (a concurrent enqueue for
        # the same identity could race this check); the DB-level idempotency
        # guarantee itself comes from enqueue()'s own unique-index fallback.
        was_active = store.active_job(project_root_str, event_dir) is not None
        job_id = store.enqueue(project_root_str, event_dir, device=device)
        if was_active:
            print(f"=  {ref.event_dir.name}: already queued/running ({job_id})")
        else:
            created += 1
            print(f"+  {ref.event_dir.name}: queued ({job_id})")

    print(f"\n{created}/{len(ctx.events)} event(s) newly queued")
    return 0


# --------------------------------------------------------------------------- #
# worker
# --------------------------------------------------------------------------- #


def cmd_worker(args: argparse.Namespace) -> int:
    """``worker``: run the job-scheduler loop until SIGINT/SIGTERM triggers a clean exit."""
    project_root = _resolve_project_root(args)
    config = load_project_config(project_root)
    worker_config = resolve_worker_config(
        config,
        poll_interval=args.poll_interval,
        gpu_sessions_per_device=args.gpu_sessions_per_device,
        cpu_slots=args.cpu_slots,
    )

    runtime = FfmpegRuntime()
    inventory = detect_capabilities(runtime)
    profile = select_profile(inventory, override=args.device)
    render_node = _selected_render_node(profile)
    pools = CapacityPools.from_inventory(
        inventory,
        gpu_cap=worker_config.gpu_sessions_per_device,
        cpu_cap=worker_config.cpu_slots,
    )

    store = _job_store(project_root)
    identity = worker_identity()
    logger.info(
        "Starting worker %s (profile=%s render_node=%s poll_interval=%.1fs)",
        identity,
        profile.vendor.value,
        render_node,
        worker_config.poll_interval,
    )

    worker = Worker(
        store,
        worker_id=identity,
        pools=pools,
        poll_interval=worker_config.poll_interval,
        build_job=lambda job: default_build_job(
            job, runtime=runtime, profile=profile, render_node=render_node
        ),
        device_filter=render_node,
    )

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %s; stopping worker", signum)
        worker.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    worker.run()
    logger.info("Worker %s stopped cleanly", identity)
    return 0


# --------------------------------------------------------------------------- #
# jobs: list / show / cancel
# --------------------------------------------------------------------------- #


def cmd_jobs_list(args: argparse.Namespace) -> int:
    """``jobs list``: print jobs (optionally filtered by ``--status``), oldest first."""
    project_root = _resolve_project_root(args)
    store = _job_store(project_root)
    if args.status:
        jobs = store.list_by_status(JobStatus(args.status))
    else:
        jobs = sorted(
            (job for status in JobStatus for job in store.list_by_status(status)),
            key=lambda job: job.created_at,
        )
    if not jobs:
        print("No jobs found")
        return 0
    for job in jobs:
        print(f"{job.id}  {job.status.value:9} {job.event_dir}  created={job.created_at}")
    return 0


def cmd_jobs_show(args: argparse.Namespace) -> int:
    """``jobs show <id>``: print one job's full detail."""
    project_root = _resolve_project_root(args)
    job_id = _parse_job_id(args.job_id)
    if job_id is None:
        print(f"error: {args.job_id!r} is not a valid job id", file=sys.stderr)
        return 1

    store = _job_store(project_root)
    job = store.get(job_id)
    if job is None:
        print(f"error: no job with id {job_id}", file=sys.stderr)
        return 1

    print(f"id:               {job.id}")
    print(f"status:           {job.status.value}")
    print(f"event_dir:        {job.event_dir}")
    print(f"project_root:     {job.project_root}")
    print(f"device:           {job.device}")
    print(f"progress:         {job.progress:.0%}")
    print(f"worker_id:        {job.worker_id}")
    print(f"cancel_requested: {job.cancel_requested}")
    print(f"requeue_count:    {job.requeue_count}")
    print(f"created_at:       {job.created_at}")
    print(f"started_at:       {job.started_at}")
    print(f"finished_at:      {job.finished_at}")
    if job.error:
        print(f"error:            {job.error}")
    return 0


def cmd_jobs_cancel(args: argparse.Namespace) -> int:
    """``jobs cancel <id>``: request cancellation (D-S6).

    A ``running`` job only has its ``cancel_requested`` flag set — the worker
    performs the terminal transition itself once it next checks between
    segments. A ``queued`` job is canceled immediately.
    """
    project_root = _resolve_project_root(args)
    job_id = _parse_job_id(args.job_id)
    if job_id is None:
        print(f"error: {args.job_id!r} is not a valid job id", file=sys.stderr)
        return 1

    store = _job_store(project_root)
    result = store.request_cancel(job_id)
    if result is None:
        print(f"job {job_id}: already in a terminal state (or does not exist); no change")
        return 0
    if result.status == JobStatus.RUNNING:
        print(f"job {job_id}: cancel requested; the worker will stop between segments")
    else:
        print(f"job {job_id}: {result.status.value}")
    return 0
