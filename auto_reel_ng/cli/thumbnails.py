"""The ``auto-reel thumbs`` subcommand: fill the clip-thumbnail cache (D-11).

Walks the project like ``scan`` (the same :func:`~.commands._project_context`) and
makes a thumbnail for every clip discovery lists on disk, IGNORED ones included,
skipping cached ones. It never reads ``reel.yaml``, so a MISSING clip is never
requested, and it writes only into the thumbnail cache, never under the project
root. Kept apart from :mod:`.commands`, which holds the render/scan/job family.

Each failed clip gets exactly one ``ERROR  <event>/<clip>: <cause>`` line; the full
reason, with the failing command and its stderr, is logged at debug level (``-v``).
Every printed line is made printable first, so a file name that is not valid UTF-8
shows its raw bytes as ``\\xNN`` instead of ending the run.
"""

from __future__ import annotations

import argparse
import logging
import re
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from ..errors import ThumbnailError
from ..event import scan_event
from ..ffmpeg.runtime import FfmpegRuntime
from ..ingest import EventRef
from ..thumbs import (
    ThumbnailSettings,
    is_cached,
    resolve_thumbnail_settings,
    thumbnail_for,
    thumbnail_path,
)
from .commands import _project_context

logger = logging.getLogger(__name__)

#: How :class:`FfmpegRuntime` reports a failed command inside a reason.
_FAILED_COMMAND = re.compile(r": Command exited -?\d+: ")

#: ffmpeg's ``[component @ 0x…]`` prefixes on a stderr line.
_LOG_TAGS = re.compile(r"^(?:\[[^\]]*\]\s*)+")


@dataclass(frozen=True)
class _EventThumbs:
    """One event's thumbnail counts; ``listed`` is False when its folder could not be read."""

    clips: int = 0
    generated: int = 0
    cached: int = 0
    failed: int = 0
    listed: bool = True


def cmd_thumbs(args: argparse.Namespace) -> int:
    """``thumbs``: generate the missing thumbnail of every clip on disk (D-11).

    Settings are validated before anything runs, then one runtime asserts the
    ffmpeg version. Up to ``--jobs`` extractions run at once in one shared pool;
    each event is a barrier, so its line prints when all its clips are done and a
    clip shared with a later event is already cached by then. A failed clip or an
    unreadable event is reported and the run continues; a cache error or an
    interrupt cancels every queued clip and propagates.
    """
    ctx = _project_context(args)
    settings = resolve_thumbnail_settings(ctx.config, ctx.project_root)
    if not ctx.events:
        _emit(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
        return 0

    runtime = FfmpegRuntime()
    results: List[_EventThumbs] = []
    pool = ThreadPoolExecutor(max_workers=args.jobs)
    try:
        for ref in ctx.events:
            results.append(_thumbs_event(ref, pool, settings, runtime))
    except BaseException:
        # Leaving a ``with`` block would still run a large event's queued clips.
        pool.shutdown(cancel_futures=True)
        raise
    pool.shutdown()

    clips = sum(r.clips for r in results)
    generated = sum(r.generated for r in results)
    cached = sum(r.cached for r in results)
    failed = sum(r.failed for r in results)
    unlisted = sum(1 for r in results if not r.listed)
    events_note = f", {_plural(unlisted, 'event')} unreadable" if unlisted else ""
    _emit(
        f"thumbnails: {_plural(clips, 'clip')} in {_plural(len(results), 'event')}: "
        f"{generated} generated, {cached} cached, {failed} failed{events_note} "
        f"(cache: {settings.cache_dir})"
    )
    return 1 if failed or unlisted else 0


def _thumbs_event(
    ref: EventRef,
    pool: ThreadPoolExecutor,
    settings: ThumbnailSettings,
    runtime: FfmpegRuntime,
) -> _EventThumbs:
    """Fill one event's thumbnails through ``pool``; print its ERROR lines, then its line."""
    name = ref.event_dir.name
    try:
        listing = scan_event(ref.event_dir)
    except OSError as exc:
        _emit(f"ERROR  {name}: cannot list event folder: {_os_reason(exc)}")
        return _EventThumbs(listed=False)

    identities = listing.identities
    errors: Dict[str, str] = {}
    futures: Dict[str, Future[Path]] = {}
    cached = 0
    for identity in identities:
        clip = ref.event_dir / identity
        try:
            target = thumbnail_path(clip, position=settings.position, cache_dir=settings.cache_dir)
        except OSError as exc:  # the clip vanished between the listing and the stat
            errors[identity] = f"cannot stat the clip: {_os_reason(exc)}"
            continue
        if is_cached(target):
            cached += 1
            continue
        futures[identity] = pool.submit(
            thumbnail_for,
            clip,
            position=settings.position,
            cache_dir=settings.cache_dir,
            runtime=runtime,
        )

    generated = 0
    for identity, future in futures.items():
        try:
            future.result()
        except ThumbnailError as exc:
            errors[identity] = exc.reason  # the line names the clip itself
        else:
            generated += 1

    # Collected per event and printed in identity order, so the output is deterministic.
    for identity in sorted(errors):
        reason = errors[identity]
        logger.debug("%s", _printable(f"{name}/{identity}: {reason}"))
        source = (ref.event_dir / identity).resolve()
        _emit(f"ERROR  {name}/{identity}: {_cause(reason, source)}")
    counts = [
        f"{count} {label}"
        for label, count in (("generated", generated), ("cached", cached), ("failed", len(errors)))
        if count
    ]
    _emit(", ".join([f"{name}: {_plural(len(identities), 'clip')}", *counts]))
    return _EventThumbs(
        clips=len(identities), generated=generated, cached=cached, failed=len(errors)
    )


def _cause(reason: str, source: Path) -> str:
    """The one-line cause an ERROR line shows for a clip's ``reason``.

    A reason that quotes a failed command (``…: Command exited N: <cmd>`` then
    ``stderr:`` and ffmpeg's output) is cut before the command, and ffmpeg's last
    stderr line, without its ``[component @ 0x…]`` tags and the clip's path, is
    kept as the gist: ``ffprobe could not read: Invalid data found when processing
    input``. Any other reason keeps its first line. The debug log has the rest.
    """
    head, _, stderr = reason.partition("\nstderr:\n")
    lines = head.splitlines()
    head = lines[0] if lines else head
    failed = _FAILED_COMMAND.search(head)
    if failed is None:
        return head
    cause = head[: failed.start()]
    last = next((line.strip() for line in reversed(stderr.splitlines()) if line.strip()), "")
    gist = _LOG_TAGS.sub("", last).replace(f"{source}: ", "").replace(str(source), source.name)
    return f"{cause}: {gist}" if gist else cause


def _emit(line: str) -> None:
    """Print ``line`` made printable (see :func:`_printable`)."""
    print(_printable(line))


def _printable(text: str) -> str:
    """``text`` with any byte of a non-UTF-8 file name shown as ``\\xNN``.

    Such names reach Python as surrogate escapes, which a UTF-8 stdout refuses.
    """
    try:
        return text.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")
    except UnicodeEncodeError:  # a surrogate that no file name produced
        return text.encode("utf-8", "backslashreplace").decode("utf-8")


def _os_reason(exc: OSError) -> str:
    """An ``OSError``'s cause without the path it repeats; the ERROR line names it."""
    return exc.strerror or str(exc)


def _plural(count: int, noun: str) -> str:
    """``1 clip`` / ``2 clips``."""
    return f"{count} {noun}{'' if count == 1 else 's'}"
