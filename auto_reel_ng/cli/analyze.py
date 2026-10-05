"""The ``auto-reel analyze`` subcommand: detect black/white/freeze spans (HLD §4.5).

Walks the project like ``scan`` (the same :func:`~.context.project_context`) and runs the
two-pass detection over every clip of each selected event, printing the suggestions and
caching them in the event's ``.auto-reel/cache/`` sidecar. It never touches ``reel.yaml``.
Kept apart from :mod:`.commands`, which holds the render/scan/job family.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

from ..analysis import Segment, analyze_event
from ..ffmpeg.runtime import FfmpegRuntime
from .context import project_context


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


__all__ = ["cmd_analyze"]
