"""Hand-built analysis sidecars for the analysis API tests (``analysis-enqueue-api``).

Entries and failure markers are written with the cache's own writers, for the clip's current
signal, so a test states what the disk holds without running ffmpeg.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from auto_reel_ng.analysis.cache import clip_signal, write_entry, write_failure
from auto_reel_ng.analysis.models import Segment, SegmentKind

SEGMENTS = [Segment(start=0.0, end=2.5, kind=SegmentKind.BLACK, confidence=0.9)]


def analyze(event_dir: Path, *identities: str) -> None:
    """Write a result for each named clip as it is now."""
    for identity in identities:
        write_entry(event_dir, identity, clip_signal(event_dir / identity), SEGMENTS)


def fail(event_dir: Path, identity: str, cause: str = "moov atom not found") -> None:
    """Record a failure for the clip as it is now."""
    write_failure(event_dir, identity, clip_signal(event_dir / identity), cause)


def replace(clip: Path) -> None:
    """Replace the clip by another file (another size and mtime): its signal changes."""
    clip.write_bytes(clip.read_bytes() + b" re-exported")
    stat = clip.stat()
    os.utime(clip, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))


def snapshot(root: Path) -> List[Tuple[str, int]]:
    """Every path under ``root`` with its mtime: equal before and after means nothing written."""
    return sorted((str(p.relative_to(root)), p.stat().st_mtime_ns) for p in root.rglob("*"))
