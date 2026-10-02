"""The ``auto-reel`` subcommand implementations: render / scan / analyze / import.

This module is almost entirely *wiring*: it consumes existing engine APIs unchanged
and applies the three CLI decisions — layout selection + config layering, the
adoption policy (delegated to :mod:`.adoption`), and per-event isolation with an
exit code that reflects per-event outcomes (D-CLI5).

The ``render`` flow is structured ``enumerate -> [staleness gate] -> build jobs ->
render_batch``: :func:`_staleness_filter` prepares/persists and gates every event
(change-detection, §8.14) before a plan is ever built, so a fresh event is reported
and never probed. ``enqueue`` and ``scan`` apply the same gate read-only/without
adoption; ``adopt-renders`` is the one-time tool for landing the gate on an
already-rendered archive.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import signal
import socket
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, NoReturn, Optional, Tuple, override

import uvicorn
from ruamel.yaml import YAML

from ..accel import AccelProfile, detect_capabilities, select_profile
from ..accel.profiles.hardware import HardwareProfile
from ..analysis import Segment, analyze_event
from ..api.app import create_app
from ..api.settings import resolve_api_settings
from ..config import load_project_config, resolve_look_defaults
from ..errors import EngineError, ReelError, ReelParseError
from ..event import ClipOrder, ReconcileResult, reconcile, scan_event
from ..event.claims import checked_claim
from ..event.metadata import reel_exists
from ..ffmpeg.runtime import FfmpegRuntime
from ..ingest import EventRef
from ..persistence.config import resolve_database_url
from ..persistence.engine import make_engine, make_session_factory
from ..persistence.job_store import JobStore
from ..persistence.models import JobStatus
from ..reel import Metadata, ReelDocument, import_legacy, write_document
from ..reel.legacy import ImportResult
from ..render import RenderJob, find_output_collisions, output_relpath, render_batch
from ..scheduler import (
    CapacityPools,
    Worker,
    default_build_job,
    resolve_worker_config,
    worker_identity,
)
from ..staleness.fingerprint import Fingerprint, compute_fingerprint, engine_identity
from ..staleness.gate import Verdict, evaluate
from ..staleness.manifest import write_manifest
from .adoption import REEL_FILENAME, PreparedEvent
from .build import build_render_job_from_event, prepare_and_persist
from .context import project_context, resolve_project_root

logger = logging.getLogger(__name__)


def _checked_document(
    ref: EventRef, today: date, order: ClipOrder
) -> Tuple[Optional[ReelDocument], Optional[str]]:
    """(document, None) for a processable event, or (None, reason) — never raises ReelError/OSError.

    The per-event isolation point for document errors (headless-cli): an event whose
    ``reel.yaml`` cannot be parsed, whose folder or file cannot be read, or whose resolved
    metadata lacks a real date or a title, is reported by the caller and skipped; the batch
    continues. The claim rule is the engine's (:func:`checked_claim`), shared with the API.
    """
    document, reason = checked_claim(ref.event_dir, order=order, today=today)
    if document is None:
        return None, reason
    try:
        # Every command lists the folder again (fingerprint, reconcile, adoption). A folder
        # that holds a readable reel.yaml but cannot be listed passes the claim rule; fail
        # here, for this event, instead of in a step none of the four commands guards.
        scan_event(ref.event_dir)
    except OSError as exc:
        return None, f"cannot read {ref.event_dir}: {exc.strerror or exc}"
    return document, None


def _checked_documents(
    events: List[EventRef], today: date, order: ClipOrder
) -> Tuple[Dict[Path, ReelDocument], Dict[Path, str]]:
    """Split ``events`` into processable documents and per-event failure reasons."""
    documents: Dict[Path, ReelDocument] = {}
    failures: Dict[Path, str] = {}
    for ref in events:
        document, reason = _checked_document(ref, today, order)
        if document is None:
            failures[ref.event_dir] = str(reason)
        else:
            documents[ref.event_dir] = document
    return documents, failures


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #


def cmd_render(args: argparse.Namespace) -> int:
    """``render``: scan -> reconcile -> [staleness gate] -> probe -> resolve -> render_batch."""
    ctx = project_context(args)
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

    # enumerate -> [staleness gate] -> build jobs -> render_batch
    candidates, fresh, invalid = _staleness_filter(
        ctx.events,
        order=ctx.config.sort,
        output_dir=ctx.output_dir,
        look_defaults=look_defaults,
        ffmpeg_version=runtime.version,
        force=args.force,
        dry_run=args.dry_run,
        today=date.today(),
    )

    # Output-identity check over every selected event, fresh ones included: a fresh
    # event owns its output, and a new same-named sibling must not overwrite it.
    refused = _output_collisions(
        {c.ref.event_dir: c.event.document.metadata for c in (*candidates, *fresh)}
    )
    candidates = [c for c in candidates if c.ref.event_dir not in refused]
    fresh = [c for c in fresh if c.ref.event_dir not in refused]

    jobs: List[RenderJob] = []
    build_failures: List[Tuple[Path, str]] = [*invalid, *refused.items()]
    for candidate in candidates:
        try:
            jobs.append(
                _build_job(
                    candidate,
                    output_dir=ctx.output_dir,
                    runtime=runtime,
                    profile=profile,
                    render_node=render_node,
                    look_defaults=look_defaults,
                    dry_run=args.dry_run,
                )
            )
        except EngineError as exc:
            # Isolate per-event build failures the same way render_batch isolates
            # render failures (D-CLI5): one bad event never aborts the rest.
            logger.error("Skipping %s: %s", candidate.ref.event_dir.name, exc)
            build_failures.append((candidate.ref.event_dir, str(exc)))

    outcomes = render_batch(jobs)
    return _report_render(outcomes, build_failures, fresh, dry_run=args.dry_run)


def _output_collisions(metadata_by_event: Mapping[Path, Metadata]) -> dict[Path, str]:
    """Map each event whose output path collides to its ``ERROR`` message.

    Every event sharing an output path is refused (headless-cli: batch commands
    refuse colliding output paths); the message names the shared path and the
    other claimants so the operator knows which ``reel.yaml`` to edit.
    """
    claims = {event_dir: output_relpath(md) for event_dir, md in metadata_by_event.items()}
    return {
        event_dir: (
            f"output path {claims[event_dir]} is also claimed by "
            f"{', '.join(other.name for other in others)}; "
            "set a distinct title or location in reel.yaml"
        )
        for event_dir, others in find_output_collisions(claims).items()
    }


@dataclass(frozen=True)
class _Candidate:
    """One event, already prepared/persisted, its fingerprint, and its verdict."""

    ref: EventRef
    event: PreparedEvent
    fingerprint: Fingerprint
    verdict: Verdict


def _staleness_filter(
    events: List[EventRef],
    *,
    order: ClipOrder,
    output_dir: Path,
    look_defaults: Mapping[str, object],
    ffmpeg_version: Tuple[int, int],
    force: bool,
    dry_run: bool,
    today: date,
) -> Tuple[List[_Candidate], List[_Candidate], List[Tuple[Path, str]]]:
    """Prepare/persist + gate every event; split into (render candidates, fresh, failed).

    An event whose document cannot be loaded or whose metadata is not processable
    is returned as ``(event_dir, reason)`` in the third list before anything is
    prepared or persisted for it (no seed is written, nothing is rendered).

    The change-detection gate (§8.14) call site for ``render``: each event is
    prepared/adopted and persisted (unless dry-run, D-C5) *before* its fingerprint
    is computed, so the fingerprint reflects post-adoption disk state. A fresh
    event is never probed/resolved — the caller reports it and moves on; ``--force``
    treats every event as a candidate regardless of its verdict.
    """
    stale: List[_Candidate] = []
    fresh: List[_Candidate] = []
    failed: List[Tuple[Path, str]] = []
    for ref in events:
        _document, reason = _checked_document(ref, today, order)
        if reason is not None:
            failed.append((ref.event_dir, reason))
            continue
        event = prepare_and_persist(ref.event_dir, order=order, dry_run=dry_run)
        if event.adopted:
            print(f"+  {ref.event_dir.name}: adopted {len(event.adopted)} new clip(s)")
        if event.reconcile.missing:
            # MISSING is reported loudly and never removed from the document (D-CLI3);
            # it also makes the clip-set component differ, so the gate reports the
            # event stale rather than silently blocking the render.
            print(
                f"!  {ref.event_dir.name}: {len(event.reconcile.missing)} MISSING clip(s) "
                f"referenced but absent: {', '.join(event.reconcile.missing)}"
            )

        fingerprint = compute_fingerprint(
            event.document,
            event_dir=ref.event_dir,
            look_defaults=look_defaults,
            ffmpeg_version=ffmpeg_version,
        )
        candidate_output = output_dir / output_relpath(event.document.metadata)
        verdict = evaluate(ref.event_dir, candidate_output, fingerprint)
        candidate = _Candidate(ref=ref, event=event, fingerprint=fingerprint, verdict=verdict)
        if force or verdict.stale:
            stale.append(candidate)
        else:
            fresh.append(candidate)
    return stale, fresh, failed


def _build_job(
    candidate: _Candidate,
    *,
    output_dir: Path,
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    render_node: Optional[str],
    look_defaults: Mapping[str, object],
    dry_run: bool,
) -> RenderJob:
    """Resolve an already-gated candidate into a :class:`RenderJob`.

    Every candidate reaching here is stale or forced, so the gate verdict drives
    overwrite (D-C4): the existing output, if any, is by definition outdated.
    """
    return build_render_job_from_event(
        candidate.event,
        output_dir=output_dir,
        runtime=runtime,
        profile=profile,
        render_node=render_node,
        look_defaults=look_defaults,
        dry_run=dry_run,
        overwrite=True,
        fingerprint=candidate.fingerprint,
    )


def _selected_render_node(profile: AccelProfile) -> Optional[str]:
    """The DRM render node of the selected hardware device, or None for CPU (D-CLI4)."""
    if isinstance(profile, HardwareProfile) and profile.capabilities.device is not None:
        return profile.capabilities.device.render_node
    return None


def _report_render(
    outcomes: list,
    build_failures: List[Tuple[Path, str]],
    fresh: List[_Candidate],
    *,
    dry_run: bool,
) -> int:
    """Print per-event results and return the process exit code (D-CLI5)."""
    errors = 0
    for candidate in fresh:
        print(f"FRESH  {candidate.ref.event_dir.name}: up to date, not rendered")

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
            print(f"SKIP   {name}: {result.output_path} exists (use --force)")
        else:
            print(f"OK     {name}: {result.output_path}")
        for warning in result.warnings:
            print(f"  warn: {warning}")

    total = len(outcomes) + len(build_failures) + len(fresh)
    print(f"\n{total - errors}/{total} event(s) succeeded")
    return 1 if errors else 0


# --------------------------------------------------------------------------- #
# scan / list
# --------------------------------------------------------------------------- #


def cmd_scan(args: argparse.Namespace) -> int:
    """``scan``/``list``: report events, clip reconcile status, and staleness; render nothing."""
    ctx = project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    runtime = FfmpegRuntime()
    look_defaults = resolve_look_defaults(ctx.config)
    today = date.today()

    errors = 0
    for ref in ctx.events:
        # The resolved (loaded or folder-seeded) document; scan never adopts or writes.
        fp_document, reason = _checked_document(ref, today, ctx.config.sort)
        if fp_document is None:
            print(f"\nERROR  {ref.event_dir.name}: {reason}")
            errors += 1
            continue

        # Reconcile disk against the persisted reel.yaml (none -> every clip NEW).
        persisted = reel_exists(ref.event_dir / REEL_FILENAME)
        listing = scan_event(ref.event_dir)
        result = reconcile(listing.identities, fp_document if persisted else None)

        # The staleness gate (§8.14, read-only site): never adopted or persisted.
        fingerprint = compute_fingerprint(
            fp_document,
            event_dir=ref.event_dir,
            look_defaults=look_defaults,
            ffmpeg_version=runtime.version,
        )
        output_path = ctx.output_dir / output_relpath(fp_document.metadata)
        verdict = evaluate(ref.event_dir, output_path, fingerprint)

        _print_inventory(ref, str(fp_document.metadata.title), result, verdict)
    return 1 if errors else 0


def _print_inventory(ref: EventRef, title: str, result: ReconcileResult, verdict: Verdict) -> None:
    """Print one event with each clip classified NEW/ACTIVE/IGNORED/MISSING, plus staleness."""
    print(f"\n{title}  [{ref.event_dir}]")
    classification = result.classification
    if not classification:
        print("  (no clips)")
    else:
        for identity in sorted(classification):
            print(f"  {classification[identity].value.upper():8} {identity}")
        if result.missing:
            print(f"  ! {len(result.missing)} MISSING clip(s) referenced but absent from disk")
    if verdict.stale:
        print(f"  stale: {', '.join(verdict.reasons)}")
    else:
        print("  fresh")


# --------------------------------------------------------------------------- #
# analyze
# --------------------------------------------------------------------------- #


def cmd_analyze(args: argparse.Namespace) -> int:
    """``analyze``: run detection over selected events; print + cache; never touch reel.yaml."""
    ctx = project_context(args)
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
    ctx = project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    imported = 0
    failed = 0
    for ref in ctx.events:
        # Per-event isolation (Principle I): the reader maps every content problem to a
        # ReelError and the disk's refusals are OSError; anything else is a bug and propagates.
        try:
            result = _import_event(ref.event_dir, overwrite=args.overwrite)
        except (OSError, ReelError) as exc:
            print(f"ERROR  {ref.event_dir.name}: {exc}")
            failed += 1
            continue
        if result is not None:
            imported += 1
            _report_import(ref.event_dir, result)
    print(f"\nimported {imported} event(s)" + (f", {failed} failed" if failed else ""))
    return 1 if failed else 0


def _import_event(event_dir: Path, *, overwrite: bool) -> Optional[ImportResult]:
    """Import one event's legacy metadata into a v2 ``reel.yaml`` (or skip)."""
    legacy_path = _legacy_source(event_dir)
    if legacy_path is None:
        logger.debug("No legacy metadata in %s", event_dir)
        return None

    reel_path = event_dir / REEL_FILENAME
    # Refuse to clobber an existing *v2* reel.yaml unless asked; a legacy reel.yaml
    # (no version key) is the migration source and is rewritten in place.
    if not overwrite and reel_exists(reel_path) and _has_version(reel_path):
        print(f"SKIP   {event_dir.name}: a v2 reel.yaml already exists (use --overwrite)")
        return None

    data = _read_legacy_mapping(legacy_path)
    result = import_legacy(data, source=str(legacy_path))
    write_document(result.document, reel_path)
    return result


def _legacy_source(event_dir: Path) -> Optional[Path]:
    """The legacy file to import: ``metadata.yaml``, else a versionless ``reel.yaml``."""
    metadata = event_dir / "metadata.yaml"
    if reel_exists(metadata):
        return metadata
    reel = event_dir / REEL_FILENAME
    if reel_exists(reel) and not _has_version(reel):
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


def _read_yaml(path: Path) -> object:
    """Read and parse ``path``; raise :class:`ReelParseError` if it cannot be read or parsed.

    One reader for ``import`` and for the ``version`` probe, so a file that cannot be read,
    is not UTF-8 or is not valid YAML is always that event's ``ERROR``. The reason names the
    file, not its folder (the event name is already printed) and is a single line.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ReelParseError(f"{path.name}: not valid UTF-8 text: {exc.reason}") from exc
    except OSError as exc:
        raise ReelParseError(f"{path.name}: cannot read: {exc.strerror or exc}") from exc
    try:
        return YAML(typ="safe").load(text)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # ruamel's YAMLError, and the odd non-YAMLError it raises with no node to blame
        # (as reel/parser.loads_document): either way the file is malformed.
        raise ReelParseError(f"{path.name}: malformed YAML: {_first_line(exc)}") from exc


def _first_line(exc: Exception) -> str:
    """The first non-blank line of ``exc`` (ruamel's message carries a source excerpt)."""
    for line in str(exc).splitlines():
        if line.strip():
            return line.strip()
    return type(exc).__name__


def _read_legacy_mapping(path: Path) -> Mapping[str, object]:
    """Read ``path`` as a YAML mapping; raise :class:`ReelParseError` if it is not one."""
    data = _read_yaml(path)
    if not isinstance(data, Mapping):
        shape = "empty" if data is None else type(data).__name__
        raise ReelParseError(f"{path.name}: legacy metadata must be a mapping, got {shape}")
    return data


def _has_version(path: Path) -> bool:
    """True when a YAML file declares a top-level ``version`` key (i.e. is v2, not legacy).

    An empty or non-mapping root declares nothing, so it is not v2; an unreadable, non-UTF-8
    or malformed file still raises.
    """
    data = _read_yaml(path)
    return isinstance(data, Mapping) and "version" in data


# --------------------------------------------------------------------------- #
# job-scheduler: shared helpers
# --------------------------------------------------------------------------- #


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
    """``enqueue``: scan via ingest layout, gate, insert one queued job per stale event.

    Never probes or renders (D-S8) — the fingerprint uses fstat clip signals, not
    ffprobe, and no plan is built. Reuses the same layout selection + config
    layering as ``render``/``scan``. Fresh events are reported and not enqueued
    unless ``--force``, which enqueues every event with its ``force`` flag set.
    """
    ctx = project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    runtime = FfmpegRuntime()
    look_defaults = resolve_look_defaults(ctx.config)
    store = _job_store(ctx.project_root)
    device = args.device or "auto"
    project_root_str = str(ctx.project_root)
    force = args.force

    # A failing event is excluded before the collision check: it can never claim a path.
    documents, failures = _checked_documents(ctx.events, date.today(), ctx.config.sort)
    refused = _output_collisions({d: doc.metadata for d, doc in documents.items()})
    for event_dir_path, message in (*failures.items(), *refused.items()):
        print(f"ERROR  {event_dir_path.name}: {message}")

    created = 0
    fresh_count = 0
    for ref in ctx.events:
        if ref.event_dir in refused or ref.event_dir in failures:
            continue
        event_dir = str(ref.event_dir.relative_to(ctx.project_root))
        document = documents[ref.event_dir]
        fingerprint = compute_fingerprint(
            document,
            event_dir=ref.event_dir,
            look_defaults=look_defaults,
            ffmpeg_version=runtime.version,
        )
        output_path = ctx.output_dir / output_relpath(document.metadata)
        verdict = evaluate(ref.event_dir, output_path, fingerprint)

        if not force and not verdict.stale:
            fresh_count += 1
            print(f".  {ref.event_dir.name}: fresh, not enqueued")
            continue

        # The report is the insertion's own verdict (the unique index decides), never an
        # earlier read: of two concurrent enqueues exactly one says created.
        submission = store.submit(
            project_root_str,
            event_dir,
            device=device,
            force=force,
            fingerprint=fingerprint.combined,
        )
        if submission.created:
            created += 1
            print(f"+  {ref.event_dir.name}: queued ({submission.job_id})")
        else:
            print(f"=  {ref.event_dir.name}: already queued/running ({submission.job_id})")

    print(
        f"\n{created}/{len(ctx.events)} event(s) newly queued "
        f"({fresh_count} fresh, not enqueued)"
    )
    return 1 if refused or failures else 0


# --------------------------------------------------------------------------- #
# worker
# --------------------------------------------------------------------------- #


def cmd_worker(args: argparse.Namespace) -> int:
    """``worker``: run the job-scheduler loop until SIGINT/SIGTERM triggers a clean exit."""
    project_root = resolve_project_root(args)
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
    project_root = resolve_project_root(args)
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
    project_root = resolve_project_root(args)
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
    project_root = resolve_project_root(args)
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


# --------------------------------------------------------------------------- #
# serve
# --------------------------------------------------------------------------- #


class ServiceServer(uvicorn.Server):
    """uvicorn's server for ``serve``: a stop signal it has obeyed is not raised again.

    After its orderly shutdown ``uvicorn.Server`` raises each signal it caught once more,
    for the handler installed before it: asyncio's SIGINT handler turns that into a
    ``KeyboardInterrupt`` traceback, and SIGTERM's default handler kills the process.
    ``serve`` has nothing left for the signal to do. It returns, and its exit status
    reports the stop (headless-cli, "`serve` runs the API service"), which :meth:`run`
    makes final.
    """

    @override
    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        with super().capture_signals():
            yield
            # The shutdown the captured signals asked for has completed.
            self._captured_signals.clear()

    @override
    def run(self, sockets: Optional[List[socket.socket]] = None) -> None:
        """Serve until stopped; on the main thread, then make the stop final.

        Once uvicorn returns, the outcome is decided (:func:`cmd_serve`). A further SIGINT
        or SIGTERM is ignored from here on: the interpreter resets Python-level handlers
        while it finalizes, so only ``SIG_IGN`` keeps a late signal from killing the
        exiting process or ending it in a ``KeyboardInterrupt``. A forced stop ends the
        process here: a request handler still running in a worker thread (a sync route
        blocked on a stalled database or a slow drive) would otherwise hold the exit, as
        uvicorn's force stops waiting for its task but the interpreter joins the thread.
        Off the main thread (in-process tests) uvicorn handled no signal: this returns.
        """
        super().run(sockets)
        if threading.current_thread() is not threading.main_thread():
            return
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, signal.SIG_IGN)
        if self.force_exit:
            _end_forced_stop()


def _end_forced_stop() -> NoReturn:
    """End the process at once with status 130, without joining any worker thread.

    The log and the standard streams are flushed first. The app's lifespan cleanup
    has already run, when ``asyncio.run`` cancelled the lifespan task.
    """
    logging.shutdown()
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            with contextlib.suppress(OSError, ValueError):
                stream.flush()
    os._exit(130)


def cmd_serve(args: argparse.Namespace) -> int:
    """``serve``: run the FastAPI service under uvicorn until SIGINT/SIGTERM (D-A7).

    Resolves :class:`~auto_reel_ng.api.settings.ApiSettings` through the same D-2
    layering as ``worker``, then runs uvicorn programmatically; uvicorn handles
    SIGINT/SIGTERM with a graceful shutdown (the WS hub's poller is cancelled via the
    app's lifespan), after which ``serve`` exits 0, or 130 when a second SIGINT forced
    the exit (on the main thread :meth:`ServiceServer.run` ends the process itself
    then, without waiting for request handlers still running in worker threads). A
    bind failure is reported loudly, naming the attempted host:port, and the command
    exits non-zero.
    """
    project_root = resolve_project_root(args)
    settings = resolve_api_settings(
        project_root, host=args.host, port=args.port, poll_interval=args.poll_interval
    )
    app = create_app(settings)

    logger.info(
        "Starting API service on %s:%s (project_root=%s)",
        settings.host,
        settings.port,
        project_root,
    )
    uvicorn_config = uvicorn.Config(app, host=settings.host, port=settings.port)
    server = ServiceServer(uvicorn_config)
    try:
        server.run()
    except SystemExit:
        print(f"error: could not bind {settings.host}:{settings.port}", file=sys.stderr)
        return 1
    # A SIGINT during the shutdown made uvicorn skip the rest of it (its force-quit):
    # 130 = 128 + SIGINT, a shell's status for an interrupted command. On the main
    # thread ServiceServer.run() has already ended the process with it.
    return 130 if server.force_exit else 0


# --------------------------------------------------------------------------- #
# adopt-renders
# --------------------------------------------------------------------------- #


def cmd_adopt_renders(args: argparse.Namespace) -> int:
    """``adopt-renders``: the one-time manifest-adoption tool (change-detection, §8.14, D-C7).

    For each selected event whose output file exists, writes a manifest at the
    current fingerprint — the operator's assertion that today's output reflects
    today's inputs. Explicit, never automatic, renders nothing, and never touches
    an event with no output (it is genuinely unrendered, not adoptable).

    ``--dry-run`` runs the same evaluation (collision check, fingerprint, gate) and
    reports what a real run would adopt, with the same totals and exit code, but
    writes nothing, so it is safe on a read-only archive.
    """
    dry_run: bool = args.dry_run
    ctx = project_context(args)
    if not ctx.events:
        print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    runtime = FfmpegRuntime()
    look_defaults = resolve_look_defaults(ctx.config)

    # A failing event is excluded before the collision check: it can never claim a path.
    documents, failures = _checked_documents(ctx.events, date.today(), ctx.config.sort)
    # One file cannot be adopted as two movies: refuse every claimant of a shared path.
    refused = _output_collisions({d: doc.metadata for d, doc in documents.items()})
    for event_dir, message in (*failures.items(), *refused.items()):
        print(f"ERROR  {event_dir.name}: {message}")

    adopted = unrendered = already_fresh = 0
    for ref in ctx.events:
        if ref.event_dir in refused or ref.event_dir in failures:
            continue
        document = documents[ref.event_dir]
        output_path = ctx.output_dir / output_relpath(document.metadata)
        if not output_path.exists():
            unrendered += 1
            print(f".  {ref.event_dir.name}: unrendered, nothing to adopt")
            continue

        fingerprint = compute_fingerprint(
            document,
            event_dir=ref.event_dir,
            look_defaults=look_defaults,
            ffmpeg_version=runtime.version,
        )
        verdict = evaluate(ref.event_dir, output_path, fingerprint)
        if not verdict.stale:
            already_fresh += 1
            print(f"=  {ref.event_dir.name}: already fresh")
            continue

        adopted += 1
        if dry_run:
            print(f"+  {ref.event_dir.name}: would adopt at current fingerprint")
            continue
        write_manifest(
            ref.event_dir,
            fingerprint,
            output=output_path.name,
            engine_identity=engine_identity(runtime.version),
        )
        print(f"+  {ref.event_dir.name}: adopted at current fingerprint")

    if dry_run:
        print(
            f"\n{adopted} would adopt, {already_fresh} already fresh, {unrendered} unrendered"
            " (dry run: nothing written)"
        )
    else:
        print(f"\n{adopted} adopted, {already_fresh} already fresh, {unrendered} unrendered")
    return 1 if refused or failures else 0
