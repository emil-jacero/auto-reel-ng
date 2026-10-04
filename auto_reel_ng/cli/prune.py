"""The ``auto-reel prune-renamed`` subcommand: remove the movies that renames left behind.

A renamed event keeps its previous movie by design (D-9): the engine never deletes a movie. The
render manifest records the names an event's renders superseded
(:attr:`~auto_reel_ng.staleness.manifest.RenderManifest.superseded`); this command lists the ones
that are still on disk and, only with ``--yes``, deletes them. It is the one place a movie is
deleted, and only on the operator's request: no render, worker, scan or API path calls it.

A superseded movie is listed only when its event has rendered successfully under another name (the
manifest records a current movie that exists as a regular file) and nothing else claims the file:
not another event's manifest (:func:`~auto_reel_ng.render.claims.claimed_movie`, the rule the
render guard uses), and not the expected output path of another event, rendered or not. Every
event the layout walks claims, whatever ``--years`` selected. Nothing is ever deleted unless it
is a regular file (not a link or a folder) inside the output directory. It never renders, probes,
enqueues or writes a manifest or ``reel.yaml``.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from ..ingest import EventRef, LayoutError, get_layout
from ..render import output_relpath
from ..render.claims import claimed_movie
from ..render.poster import poster_path
from ..staleness.manifest import read_manifest, recorded_output_in, records_poster
from .commands import _checked_documents
from .context import ProjectContext, project_context

_NOT_A_FILE_NAME = ("", ".", "..")


@dataclass(frozen=True)
class PruneCandidate:
    """A superseded movie, the event that superseded it and the movie that replaced it."""

    event_dir: Path
    path: Path
    replaced_by: Path
    #: The movie's ``-poster.jpg`` sidecar when one lies beside it and nothing claims it; it is
    #: listed and deleted with the movie. Never a candidate of its own.
    poster: Optional[Path] = None


def _key(path: Path | PurePosixPath) -> str:
    """The output-collision comparison key: NFC-normalised and case-insensitive."""
    return unicodedata.normalize("NFC", str(path)).casefold()


def _is_bare_file_name(name: str) -> bool:
    return name not in _NOT_A_FILE_NAME and Path(name).name == name and "\0" not in name


def _is_regular_file(path: Path) -> bool:
    """True when ``path`` itself (not what a link points at) is a regular file."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _is_plain_file_inside(path: Path, output_dir: Path) -> bool:
    """True when ``path`` is a regular file (not a link) whose folder lies inside ``output_dir``."""
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            return False
        return path.parent.resolve().is_relative_to(output_dir.resolve())
    except (OSError, ValueError, RuntimeError):
        return False


def _same_file(first: Path, second: Path) -> bool:
    try:
        return os.path.samefile(first, second)
    except (OSError, ValueError):
        return False


def plan_prune(
    events: Iterable[Path],
    all_events: Sequence[Path],
    output_dir: Path,
    expected: Callable[[], Mapping[Path, PurePosixPath]],
) -> List[PruneCandidate]:
    """The superseded movies of ``events`` that may be deleted, sorted by path. Read-only.

    ``all_events`` is every event the layout walks (they all claim); ``expected`` returns each
    event that loads with its expected output path relative to ``output_dir``. It loads every
    ``reel.yaml``, so it is called once, and only when a file is still a candidate.
    """
    candidates: Dict[str, PruneCandidate] = {}
    claims: Dict[Path, PurePosixPath] = {}
    loaded = False
    for event_dir in events:
        manifest = read_manifest(event_dir)
        if manifest is None or not manifest.superseded or not _is_bare_file_name(manifest.output):
            continue
        current = recorded_output_in(manifest.output, output_dir)
        if not _is_regular_file(current):
            continue  # not rendered under its new name (here): the old movie is still its movie
        for name in manifest.superseded:
            if not _is_bare_file_name(name):
                continue
            path = recorded_output_in(name, output_dir)
            if _key(path) == _key(current) or not _is_plain_file_inside(path, output_dir):
                continue
            if _same_file(path, current):
                continue
            if claimed_movie(event_dir, path, events=all_events, poster=False) is not None:
                continue  # another event's manifest records it as its movie
            if not loaded:
                claims, loaded = dict(expected()), True
            relative = PurePosixPath(*path.relative_to(output_dir).parts)
            if any(
                other != event_dir and _key(relative) == _key(claim)
                for other, claim in claims.items()
            ):
                continue  # another event's current expected output path: a pending takeover
            sidecar = poster_path(path)
            if not _is_plain_file_inside(sidecar, output_dir) or any(
                records_poster(other, sidecar) for other in all_events
            ):
                sidecar_or_none: Optional[Path] = None  # none, or another event's recorded poster
            else:
                sidecar_or_none = sidecar
            candidates.setdefault(
                _key(path), PruneCandidate(event_dir, path, current, poster=sidecar_or_none)
            )
    return sorted(candidates.values(), key=lambda candidate: str(candidate.path))


def _print_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)


def _line(marker: str, candidate: PruneCandidate, output_dir: Path) -> str:
    with_poster = "" if candidate.poster is None else " + poster"
    return (
        f"{marker}  {candidate.path.relative_to(output_dir)}{with_poster}  "
        f"(event {candidate.event_dir.name}; now {candidate.replaced_by.relative_to(output_dir)})"
    )


def _walk(ctx: ProjectContext) -> List[EventRef]:
    """Every event of the layout, never narrowed by ``--years``: all of them claim."""
    return list(get_layout(ctx.layout_name)(ctx.walk_root, None))


def _expected_paths(refs: Sequence[EventRef], ctx: ProjectContext) -> Dict[Path, PurePosixPath]:
    """Each loadable event's expected output path; an event that fails to load claims nothing."""
    documents, _failures = _checked_documents(list(refs), date.today(), ctx.config.sort)
    return {event_dir: output_relpath(doc.metadata) for event_dir, doc in documents.items()}


def cmd_prune_renamed(args: argparse.Namespace) -> int:
    """``prune-renamed``: list, and with ``--yes`` delete, the movies renames left behind.

    The listing is the same in both modes, so the dry run is a faithful preview. A file that
    cannot be deleted is reported with the operating system's reason and the run continues;
    the exit code is 1 then, and when the layout cannot be walked (before anything is deleted).
    """
    try:
        ctx = project_context(args)
        if not ctx.events:
            print(f"No events found under {ctx.walk_root} (layout: {ctx.layout_name})")
            return 0
        all_refs = _walk(ctx)
        candidates = plan_prune(
            [ref.event_dir for ref in ctx.events],
            [ref.event_dir for ref in all_refs],
            ctx.output_dir,
            lambda: _expected_paths(all_refs, ctx),
        )
    except (LayoutError, OSError) as exc:
        _print_error(f"cannot walk the project: {getattr(exc, 'strerror', None) or exc}")
        return 1

    if not candidates:
        print("No superseded movies found.")
        return 0

    if not args.yes:
        for candidate in candidates:
            print(_line("-", candidate, ctx.output_dir))
        print(
            f"{len(candidates)} superseded movie(s) "
            "(dry run: nothing deleted; pass --yes to delete them)"
        )
        return 0

    deleted = failed = 0
    for candidate in candidates:
        try:
            if not _is_plain_file_inside(candidate.path, ctx.output_dir):
                continue  # gone or changed since the plan: not an error, nothing to delete
            candidate.path.unlink()
            if candidate.poster is not None and _is_plain_file_inside(
                candidate.poster, ctx.output_dir
            ):
                candidate.poster.unlink()
        except OSError as exc:
            failed += 1
            print(f"ERROR  {candidate.path.relative_to(ctx.output_dir)}: {exc.strerror or exc}")
            continue
        deleted += 1
        print(_line("x", candidate, ctx.output_dir))
    print(f"{deleted} deleted, {failed} failed")
    return 1 if failed else 0


__all__ = ["PruneCandidate", "cmd_prune_renamed", "plan_prune"]
