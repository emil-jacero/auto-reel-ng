"""Analysis pass: detect black/white/freeze spans and cache the suggestions (HLD §4.5).

A separate, explicit pass over a clip or event that runs ffmpeg detection filters and
returns overlap-resolved :class:`Segment`s with experiment-005-calibrated default
thresholds. It is suggestion-only: it never writes ``reel.yaml`` and never applies
trims — mapping a ``Segment`` to an approved ``Trim`` belongs to a future consumer.

Layering (decision D-AN1) keeps the impure ffmpeg runner separate from a pure log
parser and a pure overlap resolver, so most of the suite runs without ffmpeg:

- :mod:`.filters` — build the two passes' args (pure)
- :mod:`.parser` — ffmpeg log text -> :class:`Segment`s (pure)
- :mod:`.overlap` — ``black``/``white`` > ``freeze`` precedence (pure)
- :mod:`.runner` — :func:`analyze_clip`, the two-pass ffmpeg invocation (impure)
- :mod:`.cache` — :func:`analyze_event` and the ``.auto-reel/cache/`` sidecar
"""

from __future__ import annotations

from ..errors import AnalysisError
from .cache import analyze_event, cache_dir
from .models import AnalysisConfig, Segment, SegmentKind
from .runner import analyze_clip

__all__ = [
    "Segment",
    "SegmentKind",
    "AnalysisConfig",
    "AnalysisError",
    "analyze_clip",
    "analyze_event",
    "cache_dir",
]
