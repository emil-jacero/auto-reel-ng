"""The ``auto-reel`` argument parser and entry point (HLD §4.11).

Exposes twelve subcommands — ``render``, ``scan``/``list``, ``analyze``, ``import``,
``enqueue``, ``worker``, ``jobs`` (``list``/``show``/``cancel``), ``serve``,
``adopt-renders``, ``thumbs``, ``proxies``, and ``prune-renamed``. The scan/render family
shares the project options (project root, ``--output``, ``--years``, ``--layout``,
``--verbose``; ``thumbs`` and ``proxies`` take no ``--output``); flags such as ``--dry-run``,
``--force``, ``--device`` and ``--jobs`` are added per subcommand. Unknown subcommands and
bad arguments exit non-zero with usage (argparse); engine errors are caught at the top and
reported on stderr with a non-zero exit.

``render`` and ``enqueue`` gate every event through the staleness gate
(change-detection, §8.14): only stale events render/enqueue unless ``--force``.
``render``'s former ``--overwrite`` flag was removed (**BREAKING**) — ``--force``
now covers both "bypass the gate" and "replace an existing output".
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence, Tuple

from ..errors import EngineError
from ..ingest import DEFAULT_LAYOUT
from ..persistence.models import JobStatus
from .analyze import cmd_analyze
from .commands import (
    cmd_adopt_renders,
    cmd_enqueue,
    cmd_import,
    cmd_jobs_cancel,
    cmd_jobs_list,
    cmd_jobs_show,
    cmd_render,
    cmd_scan,
    cmd_serve,
    cmd_worker,
)
from .proxies import cmd_proxies
from .prune import cmd_prune_renamed
from .thumbnails import cmd_thumbs


def _parse_years(value: str) -> Tuple[str, ...]:
    """Parse a comma-separated ``--years`` value into a tuple of year strings."""
    return tuple(year.strip() for year in value.split(",") if year.strip())


def _positive_int(value: str) -> int:
    """Parse a positive integer argument (``--jobs``); argparse reports the rest."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value!r}") from exc
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value!r}")
    return number


def _add_root_arg(parser: argparse.ArgumentParser) -> None:
    """Add the project-root positional + ``-v``/``--verbose`` (job-scheduler commands).

    ``worker``/``jobs`` resolve a job's own project from its stored identity
    (D-S7), so unlike ``_add_common_args`` they take no ``--years``/``--layout``/
    ``--output`` — only the root used to locate ``config.yaml`` and the database.
    """
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="project root (default: current directory)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="enable debug logging",
    )


def _add_common_args(parser: argparse.ArgumentParser, *, output: bool = True) -> None:
    """Add the shared project options every scan/render-family subcommand accepts (3.3).

    ``output=False`` leaves out ``-o``/``--output`` for a subcommand that writes no
    movie (``thumbs``, ``proxies``); it then sets ``output=None`` itself.
    """
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="project root to scan (default: current directory)",
    )
    if output:
        parser.add_argument(
            "-o",
            "--output",
            default=None,
            help=(
                "output directory "
                "(default: <parent>/<root-name>-output, or config.yaml 'output')"
            ),
        )
    parser.add_argument(
        "--years",
        type=_parse_years,
        default=None,
        help="comma-separated years to include (year-event layout)",
    )
    parser.add_argument(
        "--layout",
        default=None,
        help=f"ingest layout name (default: config.yaml or {DEFAULT_LAYOUT!r})",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="enable debug logging",
    )


def _add_prune_renamed(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Register ``prune-renamed`` (project options plus ``--yes``)."""
    prune = subparsers.add_parser(
        "prune-renamed",
        help="list (and with --yes delete) movies a rename left behind; dry run by default",
    )
    _add_common_args(prune)
    prune.add_argument(
        "--yes",
        action="store_true",
        help="delete the listed movies; without it the run only lists them",
    )
    prune.set_defaults(func=cmd_prune_renamed)


def _add_thumbs(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Register ``thumbs`` (project options without ``--output``, plus ``--jobs``)."""
    thumbs = subparsers.add_parser(
        "thumbs",
        help="generate missing clip thumbnails into the cache; never writes the library",
    )
    _add_common_args(thumbs, output=False)
    thumbs.add_argument(
        "--jobs",
        type=_positive_int,
        default=2,
        help="max concurrent extractions (default: 2; lower it for a slow drive)",
    )
    thumbs.set_defaults(output=None, func=cmd_thumbs)


def _add_proxies(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Register ``proxies`` (project options without ``--output``, plus ``--device``/``--jobs``)."""
    proxies = subparsers.add_parser(
        "proxies",
        help="make missing clip proxies and filmstrips in the cache; never writes the library",
    )
    _add_common_args(proxies, output=False)
    proxies.add_argument(
        "--device",
        default=None,
        help="acceleration override: a vendor (amd/nvidia/intel/cpu) or a device id",
    )
    proxies.add_argument(
        "--jobs",
        type=_positive_int,
        default=1,
        help="max concurrent encodes (default: 1; each uses several cores)",
    )
    proxies.set_defaults(output=None, func=cmd_proxies)


def build_parser() -> argparse.ArgumentParser:
    """Build the ``auto-reel`` argument parser with its twelve subcommands."""
    parser = argparse.ArgumentParser(
        prog="auto-reel",
        description="Merge per-event clips into one movie per event, headless.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    render = subparsers.add_parser(
        "render", help="scan, reconcile, resolve, and render selected events"
    )
    _add_common_args(render)
    render.add_argument(
        "--dry-run",
        action="store_true",
        help="print the ffmpeg commands without executing or writing anything",
    )
    render.add_argument(
        "--force",
        action="store_true",
        help="bypass the staleness gate and replace any existing output (was --overwrite)",
    )
    render.add_argument(
        "--device",
        default=None,
        help="acceleration override: a vendor (amd/nvidia/intel/cpu) or a device id",
    )
    render.set_defaults(func=cmd_render)

    scan = subparsers.add_parser(
        "scan", aliases=["list"], help="report events and clip status without rendering"
    )
    _add_common_args(scan)
    scan.set_defaults(func=cmd_scan)

    analyze = subparsers.add_parser(
        "analyze", help="detect black/white/freeze segments and cache the suggestions"
    )
    _add_common_args(analyze)
    analyze.add_argument(
        "--enqueue",
        action="store_true",
        help="queue one analysis job per event for the worker instead of analyzing here",
    )
    analyze.add_argument(
        "--force",
        action="store_true",
        help="analyze every clip again, ignoring cached results (with --enqueue: on the jobs)",
    )
    analyze.set_defaults(func=cmd_analyze)

    importer = subparsers.add_parser(
        "import", help="adopt auto-reel legacy metadata into a v2 reel.yaml"
    )
    _add_common_args(importer)
    importer.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite an existing v2 reel.yaml",
    )
    importer.set_defaults(func=cmd_import)

    enqueue = subparsers.add_parser(
        "enqueue", help="scan, gate, and insert one queued job per stale event; never renders"
    )
    _add_common_args(enqueue)
    enqueue.add_argument(
        "--device",
        default=None,
        help="device selector stored on the job (default: auto)",
    )
    enqueue.add_argument(
        "--force",
        action="store_true",
        help="bypass the staleness gate: enqueue every event, with force set on the job",
    )
    enqueue.set_defaults(func=cmd_enqueue)

    worker = subparsers.add_parser("worker", help="run the job-scheduler loop until SIGINT/SIGTERM")
    _add_root_arg(worker)
    worker.add_argument(
        "--device",
        default=None,
        help="acceleration override: a vendor (amd/nvidia/intel/cpu) or a device id",
    )
    worker.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="seconds to sleep between empty claim polls (default: config.yaml or 2.0)",
    )
    worker.add_argument(
        "--gpu-sessions-per-device",
        type=int,
        default=None,
        help="max concurrent GPU-encode sessions per render node (default: config.yaml or 1)",
    )
    worker.add_argument(
        "--cpu-slots",
        type=int,
        default=None,
        help="max concurrent CPU-encoded renders (default: config.yaml or 1)",
    )
    worker.set_defaults(func=cmd_worker)

    jobs = subparsers.add_parser("jobs", help="read the job store; request cancellation")
    jobs_sub = jobs.add_subparsers(dest="jobs_command", required=True, metavar="<jobs-command>")

    jobs_list = jobs_sub.add_parser("list", help="list jobs, oldest first")
    _add_root_arg(jobs_list)
    jobs_list.add_argument(
        "--status",
        choices=[status.value for status in JobStatus],
        default=None,
        help="filter by status (default: every status)",
    )
    jobs_list.set_defaults(func=cmd_jobs_list)

    jobs_show = jobs_sub.add_parser("show", help="show one job's full detail")
    _add_root_arg(jobs_show)
    jobs_show.add_argument("job_id", help="the job's id")
    jobs_show.set_defaults(func=cmd_jobs_show)

    jobs_cancel = jobs_sub.add_parser("cancel", help="request cancellation of a job")
    _add_root_arg(jobs_cancel)
    jobs_cancel.add_argument("job_id", help="the job's id")
    jobs_cancel.set_defaults(func=cmd_jobs_cancel)

    serve = subparsers.add_parser(
        "serve", help="run the API service (REST + WS) until SIGINT/SIGTERM"
    )
    _add_root_arg(serve)
    serve.add_argument(
        "--host",
        default=None,
        help="bind host (default: config.yaml 'api.host' or 127.0.0.1)",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=None,
        help="bind port (default: config.yaml 'api.port' or 8080)",
    )
    serve.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="WS hub poll interval in seconds (default: config.yaml 'api.poll_interval' or 1.0)",
    )
    serve.set_defaults(func=cmd_serve)

    adopt_renders = subparsers.add_parser(
        "adopt-renders",
        help="write manifests for already-rendered events; never renders (one-time deploy step)",
    )
    _add_common_args(adopt_renders)
    adopt_renders.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be adopted without writing any manifest",
    )
    adopt_renders.set_defaults(func=cmd_adopt_renders)

    _add_thumbs(subparsers)

    _add_proxies(subparsers)

    _add_prune_renamed(subparsers)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse ``argv`` and dispatch the chosen subcommand; return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        return int(args.func(args))
    except EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
