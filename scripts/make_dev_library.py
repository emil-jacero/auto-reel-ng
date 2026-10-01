"""Build a small, real-footage project library for GUI development.

The shared fixture (``auto-reel-media``) holds a single event, which cannot show
what the event screens must render: fresh and stale events, each staleness
reason, NEW and MISSING clips, a named chapter, an IGNORED clip, an event dated by its reel.yaml rather than its folder
name, an output collision, every
latest-job state, and an event the list cannot read (its "Needs attention" row). This script cuts short stream-copied clips from the fixture
(never modifying it) and lays out a ``year-event`` project under ``DEST``:

    DEST/clips/            the cut clips (outside the walked root)
    DEST/library/          the project root to point ``serve`` at
    DEST/library-output/   rendered movies (the default output directory)

It renders part of the library through the real queue (``enqueue`` + ``worker``,
so the events carry job history), then edits disk so the rest goes stale. Needs
the dev database (``DATABASE_URL`` or the dev default) migrated to head, and a
working ffmpeg. Re-running rebuilds ``DEST`` from scratch and drops the jobs
recorded for its project root.

Usage (from the repository root)::

    .venv/bin/python scripts/make_dev_library.py ../auto-reel-dev
"""

from __future__ import annotations

import argparse
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from ruamel.yaml import YAML
from sqlalchemy import delete, select

from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.persistence.config import resolve_database_url
from auto_reel_ng.persistence.engine import make_engine, make_session_factory, session_scope
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobStatus

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES = (
    REPO_ROOT.parent / "auto-reel-media" / "input" / "2024" / "2024-06-27 - grillning med grannar"
)
MARKER = ".auto-reel-dev-library"
CLIP_SECONDS = 6
WORKER_TIMEOUT_S = 300.0

#: Events rendered through the queue before disk is edited (phase 1).
RENDERED = {
    "2023/2023-06-23 - Midsommar - Dalarna": ["s1710001.mp4", "s1710002.mp4"],
    "2024/2024-06-21 - Midsommar - Dalarna": ["s1710003.mp4"],
    "2024/2024-06-27 - Grillning med grannar": [
        "s1710001.mp4",
        "s1710002.mp4",
        "s1710003.mp4",
        "s1710004.mp4",
    ],
    "2024/2024-07-14 - Kalas": ["s1710002.mp4"],
    "2024/2024-08-02 - Badutflykt - Varberg": ["s1710001.mp4", "s1710003.mp4"],
    "2024/2024-10-05 - Trasig": ["trasig.mp4"],  # an empty clip: its job fails
    # Root clips plus a named chapter: the worker seeds chapters "" and "Kvällen".
    "2024/2024-08-20 - Två kapitel - Tjörn": [
        "s1710001.mp4",
        "Kvällen/s1710002.mp4",
        "Kvällen/s1710003.mp4",
    ],
}


def _auto_reel(*args: str, check: bool = True) -> None:
    """Run the venv's ``auto-reel`` entry point."""
    subprocess.run([str(Path(sys.executable).with_name("auto-reel")), *args], check=check)


def _link(event_dir: Path, clips_dir: Path, names: list[str]) -> None:
    """Link each clip into ``event_dir``; a name may carry a chapter folder (``Kvällen/x.mp4``)."""
    for name in names:
        link = event_dir / name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(clips_dir / Path(name).name)


def _prepare_dest(dest: Path) -> None:
    """Create ``dest``, or clear a previous build of it; refuse anything else."""
    if dest.exists() and any(dest.iterdir()) and not (dest / MARKER).exists():
        sys.exit(f"refusing to build into non-empty {dest}: it is not a dev library ({MARKER})")
    for sub in ("clips", "library", "library-output"):
        shutil.rmtree(dest / sub, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / MARKER).write_text("built by scripts/make_dev_library.py\n", encoding="utf-8")


def _cut_clips(samples: Path, clips_dir: Path) -> None:
    """Stream-copy the first seconds of each fixture clip; the fixture is only read."""
    runtime = FfmpegRuntime()
    clips_dir.mkdir()
    for source in sorted(samples.glob("*.mp4")):
        runtime.run(
            [
                "-y",
                "-i",
                str(source),
                "-t",
                str(CLIP_SECONDS),
                "-map",
                "0",
                "-c",
                "copy",
                str(clips_dir / source.name),
            ]
        )
    (clips_dir / "trasig.mp4").write_bytes(b"")  # zero bytes: probing it fails loud


def _render_through_queue(library: Path, store: JobStore) -> None:
    """Enqueue every stale event and run a worker until this project's queue drains."""
    _auto_reel("enqueue", str(library))
    worker = subprocess.Popen([str(Path(sys.executable).with_name("auto-reel")), "worker"])
    try:
        deadline = time.monotonic() + WORKER_TIMEOUT_S
        while time.monotonic() < deadline:
            active = [
                job
                for status in (JobStatus.QUEUED, JobStatus.RUNNING)
                for job in store.list_by_status(status)
                if job.project_root == str(library)
            ]
            if not active:
                break
            time.sleep(1.0)
        else:
            sys.exit(f"worker did not drain the queue within {WORKER_TIMEOUT_S:.0f}s")
    finally:
        worker.send_signal(signal.SIGINT)
        worker.wait(timeout=60)


def _edit_title(reel: Path, title: str) -> None:
    """Round-trip ``reel.yaml`` (comments and key order kept) with a new title."""
    yaml = YAML()
    document = yaml.load(reel.read_text(encoding="utf-8"))
    document["metadata"]["title"] = title
    with reel.open("w", encoding="utf-8") as handle:
        yaml.dump(document, handle)


def _ignore(reel: Path, identity: str) -> None:
    """Round-trip ``reel.yaml`` (comments and key order kept), dismissing ``identity``."""
    yaml = YAML()
    document = yaml.load(reel.read_text(encoding="utf-8"))
    document["ignore"] = [identity]
    with reel.open("w", encoding="utf-8") as handle:
        yaml.dump(document, handle)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dest", type=Path, help="directory to build into (e.g. ../auto-reel-dev)")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES, help="fixture clip dir")
    args = parser.parse_args()

    dest = args.dest.resolve()
    clips, library = dest / "clips", dest / "library"
    _prepare_dest(dest)

    engine = make_engine(resolve_database_url())
    store = JobStore(make_session_factory(engine))
    with session_scope(make_session_factory(engine)) as session:
        session.execute(delete(Job).where(Job.project_root == str(library)))

    _cut_clips(args.samples, clips)

    # Phase 1: render through the queue, so events carry done/failed job history.
    for event, names in RENDERED.items():
        _link(library / event, clips, names)
    _render_through_queue(library, store)

    # Phase 2: edit disk so the list shows each kind of staleness.
    _edit_title(
        library / "2024/2024-06-27 - Grillning med grannar/reel.yaml", "Grillkväll med grannarna"
    )  # stale: editorial, output_renamed (its old movie stays)
    _link(library / "2024/2024-08-02 - Badutflykt - Varberg", clips, ["s1710004.mp4"])  # NEW
    sommarlov = library / "2024/2024-09-01 - Sommarlov"
    _link(sommarlov, clips, ["s1710002.mp4", "s1710004.mp4"])
    (sommarlov / "reel.yaml").write_text(
        "version: 0\n"
        "metadata:\n  title: Sommarlov\n  date: 2024-09-01\n"
        "chapters:\n  - name: ''\n    clips:\n"
        "      - s1710002.mp4\n      - s1710004.mp4\n      - borttagen.mp4  # MISSING\n",
        encoding="utf-8",
    )
    # IGNORED at the root, and NEW inside a named chapter: stale for clip_set.
    tva_kapitel = library / "2024/2024-08-20 - Två kapitel - Tjörn"
    _link(tva_kapitel, clips, ["s1710004.mp4", "Kvällen/s1710004.mp4"])
    _ignore(tva_kapitel / "reel.yaml", "s1710004.mp4")
    # A folder name without a date: reel.yaml supplies it (reel.yaml over folder name). Never
    # rendered; its clip is NEW because the document names no chapters.
    blandat = library / "2024/Blandat"
    _link(blandat, clips, ["s1710003.mp4"])
    (blandat / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Blandat\n  date: 2024-11-02\n", encoding="utf-8"
    )
    # Same date, differing only in case: collides with 2024-07-14 - Kalas.
    _link(library / "2024/2024-07-14 - kalas", clips, ["s1710004.mp4"])

    # An impossible folder date: the list shows it as an unusable-metadata error row. Added
    # only now, because ``enqueue`` in phase 1 would report it as an ERROR and exit 1.
    _link(library / "2024/2024-02-30 - Omöjligt datum", clips, ["s1710001.mp4"])

    # A queued job that no worker is running: the list's "waiting" state.
    store.enqueue(str(library), "2024/Blandat")

    with session_scope(make_session_factory(engine)) as session:
        jobs = session.execute(select(Job).where(Job.project_root == str(library))).scalars()
        states = sorted(f"{job.status.value:8} {job.event_dir}" for job in jobs)
    print(f"\nlibrary: {library}\njobs:\n  " + "\n  ".join(states))
    _auto_reel("scan", str(library), check=False)


if __name__ == "__main__":
    main()
