"""Seed the compose stack's writable scratch library from the read-only auto-reel-media fixture.

The GUI writes ``reel.yaml`` and a render writes ``<event>/.auto-reel/cache/``, so the stack
cannot serve the fixture itself (a shared test fixture that is never mutated). This script lays
out a ``year-event`` library of symlinks over it instead; ``compose.yaml``'s one-shot ``seed``
service runs it from the image before ``server`` and ``worker`` start:

    MEDIA   (ro)  /media/auto-reel-media/
                    input/<year>/<event>/      reel.yaml, clips, chapter folders, .auto-reel/
                    samples/                   loose clips; legacy-* is an old MPEG-4 Part 2 render
    LIBRARY (rw)  /data/library/
                    <year>/<event>/            reel.yaml copied; every other file an absolute
                                               symlink into MEDIA; folders mirrored; no .auto-reel/
                    2025/2025-01-15 - Provklipp/         samples/* except legacy-*
                    2025/2025-01-16 - Gammal rendering/  samples/legacy-*
    OUTPUT  (rw)  /data/library-output/        the server's default output directory
    TMP     (rw)  /data/tmp/                   TMPDIR: a render's temporary segments

Every service mounts the fixture at the same path, so the links resolve in each of them.

Idempotent: a re-run creates only missing folders and links and copies a ``reel.yaml`` only into
an event that has none. It never replaces, re-links or deletes an existing entry, so GUI edits,
the engine's generated ``reel.yaml`` and its ``.auto-reel/`` cache survive. ``--reset`` empties
the library, the output and the render scratch first (never following a link into the fixture),
then seeds. A render empties its own scratch when it finishes or is cancelled cleanly; one that was
killed leaves its ``auto-reel-render-*`` directory behind until a reset.

Stdlib only: it runs on the image's system Python. Usage::

    podman compose run --rm seed [--reset]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MEDIA = Path("/media/auto-reel-media")
LIBRARY = Path("/data/library")
OUTPUT = Path("/data/library-output")
TMP = Path("/data/tmp")

REEL = "reel.yaml"
CACHE_DIR = ".auto-reel"
SAMPLES_EVENT = Path("2025") / "2025-01-15 - Provklipp"
# The legacy render (MPEG-4 Part 2 + MP3) gets an event of its own: radeonsi has no MPEG-4 VAAPI
# decode, so on the GPU profile it fails its event, and the sample event stays renderable.
LEGACY_EVENT = Path("2025") / "2025-01-16 - Gammal rendering"
LEGACY_PREFIX = "legacy-"


@dataclass
class SeedCounts:
    """What one seed run did; printed as the run's single line."""

    events: int = 0
    reel_copied: int = 0
    reel_kept: int = 0
    link_new: int = 0
    link_kept: int = 0


def _clear(directory: Path) -> None:
    """Empty ``directory``; a symlink is unlinked, never followed."""
    for child in directory.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _link(source: Path, dest: Path, counts: SeedCounts) -> None:
    if dest.is_symlink() or dest.exists():
        counts.link_kept += 1
        return
    dest.symlink_to(source)  # absolute: the fixture's mount path is the same in every service
    counts.link_new += 1


def _mirror(source: Path, target: Path, counts: SeedCounts, *, event_root: bool) -> None:
    """Mirror one fixture folder: folders as folders, files as links, the root reel.yaml copied."""
    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(source.iterdir()):
        dest = target / entry.name
        if entry.name == CACHE_DIR:
            continue  # the fixture's render cache never comes along
        if entry.is_dir() and not entry.is_symlink():
            _mirror(entry, dest, counts, event_root=False)
        elif event_root and entry.name == REEL:
            if dest.is_symlink() or dest.exists():
                counts.reel_kept += 1
            else:
                shutil.copyfile(entry, dest)  # a real copy: GUI saves write here
                counts.reel_copied += 1
        else:
            _link(entry, dest, counts)


def _seed_samples(
    samples: Path, target: Path, counts: SeedCounts, keep: Callable[[str], bool]
) -> None:
    clips = [e for e in sorted(samples.iterdir()) if e.is_file() and keep(e.name)]
    if not clips:
        return
    target.mkdir(parents=True, exist_ok=True)
    for clip in clips:
        _link(clip, target / clip.name, counts)
    counts.events += 1


def seed(
    media: Path, library: Path, output: Path, *, reset: bool = False, tmp: Path | None = None
) -> SeedCounts:
    """Seed ``library`` and ``output`` from ``media``; see the module docstring for the layout.

    ``reset`` also empties ``tmp`` (the stack's TMPDIR) when given and present.

    ``media/input`` must exist (``main`` checks it first); any ``OSError`` propagates.
    """
    media = media.absolute()
    library.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    if reset:
        _clear(library)
        _clear(output)
        if tmp is not None and tmp.is_dir():
            _clear(tmp)
    counts = SeedCounts()
    for year in sorted((media / "input").iterdir()):
        if not year.is_dir() or year.name.startswith("."):
            continue
        for event in sorted(year.iterdir()):
            if event.is_dir() and not event.name.startswith("."):
                _mirror(event, library / year.name / event.name, counts, event_root=True)
                counts.events += 1
    samples = media / "samples"
    if samples.is_dir():
        _seed_samples(
            samples, library / SAMPLES_EVENT, counts, lambda n: not n.startswith(LEGACY_PREFIX)
        )
        _seed_samples(
            samples, library / LEGACY_EVENT, counts, lambda n: n.startswith(LEGACY_PREFIX)
        )
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--reset", action="store_true", help="empty library, output and tmp first")
    parser.add_argument("--media", type=Path, default=MEDIA, help=f"fixture (default {MEDIA})")
    parser.add_argument("--library", type=Path, default=LIBRARY, help=f"(default {LIBRARY})")
    parser.add_argument("--output", type=Path, default=OUTPUT, help=f"(default {OUTPUT})")
    parser.add_argument("--tmp", type=Path, default=TMP, help=f"render scratch (default {TMP})")
    args = parser.parse_args(argv)
    media: Path = args.media
    if not (media / "input").is_dir():
        print(f"seed: {media}/input not found — is auto-reel-media mounted?", file=sys.stderr)
        return 1
    counts = seed(media, args.library, args.output, reset=args.reset, tmp=args.tmp)
    if args.reset:
        print(f"seed: reset {args.library}, {args.output} and {args.tmp}")
    print(
        f"seed: {counts.events} events under {args.library}: reel_copied={counts.reel_copied}"
        f" reel_kept={counts.reel_kept} link_new={counts.link_new} link_kept={counts.link_kept}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
