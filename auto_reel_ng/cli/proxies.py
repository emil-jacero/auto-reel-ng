"""The ``auto-reel proxies`` subcommand: fill the clip-proxy cache (D-21).

Walks the project like ``scan`` and ``thumbs`` (the same :func:`~.context.project_context`) and
makes a proxy for every clip discovery lists on disk, IGNORED ones included, skipping clips
whose entry is complete. It never reads ``reel.yaml``, so a MISSING clip is never requested,
and it writes only into the proxy cache, never under the project root. Clips that resolve to
one entry (symlinks to one clip) are encoded once per event: the first in listing order counts
as generated, the others as cached. The acceleration profile is selected once, as ``render``
does. Kept apart from :mod:`.commands`, which holds the render/scan/job family.

After a clip's proxy is ready (made now or already cached) the same pool slot makes its filmstrip
sprite (``clip-filmstrips``) unless one is recorded; a clip whose proxy failed gets no sprite
attempt. A failed sprite is reported and counted apart from the proxy, which stays valid.

Each failed clip (proxy or sprite) gets exactly one ``ERROR  <event>/<clip>: <cause>`` line,
the cause cut to one line by :func:`~auto_reel_ng.thumbs.one_line_cause` (the failing command
and its stderr are logged at debug level, ``-v``). An interrupt sets one shared cancel flag
every encode and every sprite polls, so running ffmpeg processes are killed and their build
directories removed before the process exits.
"""

from __future__ import annotations

import argparse
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..accel import AccelProfile, detect_capabilities, select_profile
from ..accel.profiles.hardware import HardwareProfile
from ..errors import FfmpegCancelledError, FilmstripError, ProxyError
from ..event import scan_event
from ..ffmpeg.runtime import FfmpegRuntime
from ..ingest import EventRef
from ..proxies import (
    Filmstrip,
    ProxyEntry,
    ProxySettings,
    ensure_filmstrip,
    ensure_proxy,
    lookup_filmstrip,
    lookup_proxy,
    proxy_key,
    resolve_proxy_settings,
)
from ..thumbs import one_line_cause
from .context import project_context
from .printing import emit as _emit
from .printing import os_reason as _os_reason
from .printing import plural as _plural
from .printing import printable as _printable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _EventProxies:
    """One event's proxy counts; ``listed`` is False when its folder could not be read."""

    clips: int = 0
    generated: int = 0
    cached: int = 0
    failed: int = 0
    written: int = 0
    listed: bool = True
    #: The filmstrip counts: of the clips whose proxy is ready, how many sprites were made now,
    #: were already recorded, or failed (the proxy stays valid), and the bytes of those made.
    film_generated: int = 0
    film_cached: int = 0
    film_failed: int = 0
    film_written: int = 0


@dataclass(frozen=True)
class _Made:
    """What one pool slot made for one entry: its proxy and, unless that failed, its sprite."""

    entry: ProxyEntry
    #: The recorded or built filmstrip, or ``None`` when its attempt failed (``film_error``).
    film: Optional[Filmstrip]
    #: The failed sprite's reason, or ``None``.
    film_error: Optional[str] = None
    #: The size on disk of the proxy this slot made, taken before the sprite is recorded in the
    #: facts (0 for a proxy that was already cached).
    proxy_bytes: int = 0


@dataclass(frozen=True)
class _Run:
    """What every event of one invocation shares."""

    pool: ThreadPoolExecutor
    settings: ProxySettings
    runtime: FfmpegRuntime
    profile: AccelProfile
    render_node: Optional[str]
    cancel: threading.Event


def cmd_proxies(args: argparse.Namespace) -> int:
    """``proxies``: make the missing proxy of every clip on disk (D-21).

    Settings are validated before anything runs, then one runtime asserts the ffmpeg version
    and the acceleration profile is selected once (an override that cannot be satisfied stops
    the run with one error, before any encode). Up to ``--jobs`` encodes run at once in one
    shared pool; each event is a barrier, so its line prints when all its clips are done. A
    failed clip or an unreadable event is reported and the run continues; a cache error or an
    interrupt cancels every queued and running encode and propagates.
    """
    ctx = project_context(args)
    settings = resolve_proxy_settings(ctx.config, ctx.project_root)
    if not ctx.events:
        _emit(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    runtime = FfmpegRuntime()
    profile = select_profile(detect_capabilities(runtime), override=args.device)
    render_node = _selected_render_node(profile)
    logger.info("Selected %s profile (render_node=%s)", profile.vendor.value, render_node)

    results: List[_EventProxies] = []
    pool = ThreadPoolExecutor(max_workers=args.jobs)
    run = _Run(pool, settings, runtime, profile, render_node, threading.Event())
    try:
        for ref in ctx.events:
            results.append(_proxies_event(ref, run))
    except BaseException:
        # Leaving a ``with`` block would still run a large event's queued clips; the flag
        # makes the encodes already running kill their ffmpeg and remove their build directory.
        run.cancel.set()
        pool.shutdown(cancel_futures=True)
        raise
    pool.shutdown()

    clips = sum(r.clips for r in results)
    generated = sum(r.generated for r in results)
    cached = sum(r.cached for r in results)
    failed = sum(r.failed for r in results)
    written = sum(r.written for r in results)
    film_generated = sum(r.film_generated for r in results)
    film_cached = sum(r.film_cached for r in results)
    film_failed = sum(r.film_failed for r in results)
    film_written = sum(r.film_written for r in results)
    unlisted = sum(1 for r in results if not r.listed)
    events_note = f", {_plural(unlisted, 'event')} unreadable" if unlisted else ""
    _emit(
        f"proxies: {_plural(clips, 'clip')} in {_plural(len(results), 'event')}: "
        f"{generated} generated ({_size(written)}), {cached} cached, {failed} failed; "
        f"filmstrips: {film_generated} generated ({_size(film_written)}), "
        f"{film_cached} cached, {film_failed} failed"
        f"{events_note} (cache: {settings.cache_dir})"
    )
    return 1 if failed or film_failed or unlisted else 0


def _selected_render_node(profile: AccelProfile) -> Optional[str]:
    """The DRM render node of the selected hardware device, or None for CPU (D-CLI4)."""
    if isinstance(profile, HardwareProfile) and profile.capabilities.device is not None:
        return profile.capabilities.device.render_node
    return None


def _make_entry(clip: Path, known: Optional[ProxyEntry], run: _Run) -> _Made:
    """One pool slot: the clip's proxy (unless ``known``), then its filmstrip.

    A :class:`ProxyError` propagates (no sprite is attempted for a failed proxy); a failed
    sprite is returned, because the proxy it leaves is valid and counted.

    Raises:
        FfmpegCancelledError: the run was interrupted before the sprite started.
    """
    entry = known
    proxy_bytes = 0
    if entry is None:
        entry = ensure_proxy(
            clip,
            settings=run.settings,
            runtime=run.runtime,
            profile=run.profile,
            render_node=run.render_node,
            should_cancel=run.cancel.is_set,
        )
        proxy_bytes = _entry_bytes(entry)
    if run.cancel.is_set():
        raise FfmpegCancelledError("proxies: interrupted before the filmstrip was made")
    try:
        film = ensure_filmstrip(clip, entry, runtime=run.runtime, should_cancel=run.cancel.is_set)
    except FilmstripError as exc:
        return _Made(entry, None, exc.reason, proxy_bytes)
    return _Made(entry, film, None, proxy_bytes)


def _counts(generated: int, cached: int, failed: int) -> List[str]:
    """``"3 generated"``-style parts for the non-zero counts."""
    return [
        f"{count} {label}"
        for label, count in (("generated", generated), ("cached", cached), ("failed", failed))
        if count
    ]


@dataclass
class _Tally:
    """One event's counts and failures while its slots finish."""

    generated: int = 0
    cached: int = 0
    written: int = 0
    film_generated: int = 0
    film_cached: int = 0
    film_written: int = 0
    #: identity -> reason, for the clips whose proxy failed and those whose sprite failed.
    errors: Dict[str, str] = field(default_factory=dict)
    film_errors: Dict[str, str] = field(default_factory=dict)

    def add(self, made: _Made, members: List[str], *, known: bool) -> None:
        """Count one finished slot, whose entry is shared by ``members`` (the first made it)."""
        if not known:
            if made.entry.generated:
                self.generated += 1  # the first member made the entry; the rest share it
                self.written += made.proxy_bytes
                self.cached += len(members) - 1
            else:
                self.cached += len(members)  # another process finished first
        if made.film is None:
            for member in members:
                self.film_errors[member] = made.film_error or "the filmstrip could not be made"
        elif made.film.generated:
            self.film_generated += 1
            self.film_written += made.film.bytes
            self.film_cached += len(members) - 1
        else:
            self.film_cached += len(members)  # recorded by another process meanwhile


def _proxies_event(ref: EventRef, run: _Run) -> _EventProxies:
    """Fill one event's proxies and filmstrips through the pool; print its ERROR lines, its line."""
    name = ref.event_dir.name
    try:
        listing = scan_event(ref.event_dir)
    except OSError as exc:
        _emit(f"ERROR  {name}: cannot list event folder: {_os_reason(exc)}")
        return _EventProxies(listed=False)

    identities = listing.identities
    tally = _Tally()
    groups: Dict[str, List[str]] = {}  # entry key -> the identities that share it
    for identity in identities:
        try:
            key = proxy_key(ref.event_dir / identity)
        except OSError as exc:  # the clip vanished between the listing and the stat
            tally.errors[identity] = f"cannot stat the clip: {_os_reason(exc)}"
            continue
        groups.setdefault(key, []).append(identity)

    # One slot per distinct entry, for its first identity: the others resolve to the same
    # entry, so the one attempt serves them all. A cached proxy with a recorded sprite needs
    # no slot at all; a cached proxy without one needs only the sprite.
    known_keys: set[str] = set()  # entries that were complete before this run touched them
    futures: Dict[str, Future[_Made]] = {}
    for key, members in groups.items():
        clip = ref.event_dir / members[0]
        known = lookup_proxy(clip, settings=run.settings)
        if known is not None:
            known_keys.add(key)
            tally.cached += len(members)
            if lookup_filmstrip(known) is not None:
                tally.film_cached += len(members)
                continue
        futures[key] = run.pool.submit(_make_entry, clip, known, run)

    for key, future in futures.items():
        try:
            made = future.result()
        except ProxyError as exc:
            for member in groups[key]:  # each ERROR line names the clip itself
                tally.errors[member] = exc.reason
            continue  # a failed proxy gets no sprite attempt and no sprite count
        tally.add(made, groups[key], known=key in known_keys)

    # Collected per event and printed in identity order, so the output is deterministic.
    for identity in sorted({**tally.errors, **tally.film_errors}):
        reason = tally.errors.get(identity) or tally.film_errors[identity]
        logger.debug("%s", _printable(f"{name}/{identity}: {reason}"))
        source = (ref.event_dir / identity).resolve()
        _emit(f"ERROR  {name}/{identity}: {one_line_cause(reason, source)}")
    counts = _counts(tally.generated, tally.cached, len(tally.errors))
    film_counts = _counts(tally.film_generated, tally.film_cached, len(tally.film_errors))
    line = ", ".join([f"{name}: {_plural(len(identities), 'clip')}", *counts])
    _emit(f"{line}; filmstrips: {', '.join(film_counts)}" if film_counts else line)
    return _EventProxies(
        clips=len(identities),
        generated=tally.generated,
        cached=tally.cached,
        failed=len(tally.errors),
        written=tally.written,
        film_generated=tally.film_generated,
        film_cached=tally.film_cached,
        film_failed=len(tally.film_errors),
        film_written=tally.film_written,
    )


def _entry_bytes(entry: ProxyEntry) -> int:
    """The size on disk of a published entry's files, 0 for one that cannot be statted."""
    total = 0
    for path in (entry.proxy_path, entry.facts_path):
        try:
            total += Path(path).stat().st_size
        except OSError:
            logger.debug("Cannot size %s", path)
    return total


def _size(count: int) -> str:
    """``count`` bytes as a short decimal size: ``812 B``, ``3.4 MB``, ``1.2 GB``."""
    value = float(count)
    for unit in ("B", "kB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{count} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1000
    raise AssertionError("unreachable")  # pragma: no cover
