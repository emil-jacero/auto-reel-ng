"""The ``auto-reel`` argument parser and entry point (HLD §4.11).

Exposes the four subcommands (``render``, ``scan``/``list``, ``analyze``,
``import``) over a shared set of options (project root, output dir, ``--years``,
``--layout``, ``--device``, ``--dry-run``, ``--overwrite``). Unknown subcommands
and bad arguments exit non-zero with usage (argparse); engine errors are caught at
the top and reported on stderr with a non-zero exit.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence, Tuple

from ..errors import EngineError
from ..ingest import DEFAULT_LAYOUT
from .commands import cmd_analyze, cmd_import, cmd_render, cmd_scan


def _parse_years(value: str) -> Tuple[str, ...]:
    """Parse a comma-separated ``--years`` value into a tuple of year strings."""
    return tuple(year.strip() for year in value.split(",") if year.strip())


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add the shared project options every subcommand accepts (3.3)."""
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="project root to scan (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="output directory (default: <root>/output, or config.yaml 'output')",
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


def build_parser() -> argparse.ArgumentParser:
    """Build the ``auto-reel`` argument parser with its four subcommands."""
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
        "--overwrite",
        action="store_true",
        help="replace an existing output file",
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
