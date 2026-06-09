"""auto-reel-ng engine: ffmpeg runtime + fail-loud media probe.

This package is the foundation every later auto-reel-ng change builds on. It provides
two things and nothing more (capability interpretation, render, and analysis are later
changes):

- :class:`FfmpegRuntime` — a binary-agnostic ffmpeg/ffprobe runtime that resolves the
  executables once (explicit config -> env -> bundled jellyfin-ffmpeg -> PATH; decision
  **D-1**), asserts **ffmpeg >= 7.1** at construction, runs commands with structured
  errors, reports progress, and exposes raw capability text.
- :func:`probe_media` — a single-pass, **fail-loud** probe returning an immutable
  :class:`ClipMetadata`. It never fabricates metadata: an unprobeable file raises
  :class:`ProbeError` instead of substituting assumed values such as 1920x1080/25fps.
"""

from __future__ import annotations

from .analysis import (
    AnalysisConfig,
    AnalysisError,
    Segment,
    SegmentKind,
    analyze_clip,
    analyze_event,
)
from .cli import main as cli_main
from .config import (
    ConfigError,
    ProjectConfig,
    load_project_config,
    resolve_look_defaults,
)
from .errors import (
    AccelError,
    EngineError,
    FfmpegError,
    FfmpegVersionError,
    ProbeError,
    ReconcileError,
    ReelError,
    ReelImportError,
    ReelParseError,
)
from .event import (
    ClipStatus,
    ReconcileResult,
    RenderPlan,
    add_clip,
    ignore_clip,
    reconcile,
    resolve,
    scan_event,
    seed_document,
)
from .ffmpeg.runtime import REQUIRED_FFMPEG_VERSION, FfmpegRuntime, parse_ffmpeg_version
from .ingest import (
    DEFAULT_LAYOUT,
    EventRef,
    FolderHint,
    Layout,
    LayoutError,
    get_layout,
    layout_names,
    register_layout,
)
from .probe.media import get_default_runtime, probe_many, probe_media
from .probe.metadata import AudioStream, ClipMetadata
from .reel import (
    ReelDocument,
    import_legacy,
    load_document,
    loads_document,
    write_document,
)

__all__ = [
    # runtime
    "FfmpegRuntime",
    "REQUIRED_FFMPEG_VERSION",
    "parse_ffmpeg_version",
    # probe
    "probe_media",
    "probe_many",
    "get_default_runtime",
    "ClipMetadata",
    "AudioStream",
    # reel-document
    "ReelDocument",
    "load_document",
    "loads_document",
    "write_document",
    "import_legacy",
    # event resolution / reconcile
    "resolve",
    "RenderPlan",
    "seed_document",
    "scan_event",
    "reconcile",
    "ReconcileResult",
    "ClipStatus",
    "add_clip",
    "ignore_clip",
    # analysis
    "Segment",
    "SegmentKind",
    "AnalysisConfig",
    "analyze_clip",
    "analyze_event",
    # ingest layouts
    "EventRef",
    "FolderHint",
    "Layout",
    "LayoutError",
    "DEFAULT_LAYOUT",
    "get_layout",
    "layout_names",
    "register_layout",
    # project config
    "ProjectConfig",
    "ConfigError",
    "load_project_config",
    "resolve_look_defaults",
    # cli entry
    "cli_main",
    # errors
    "EngineError",
    "FfmpegError",
    "FfmpegVersionError",
    "ProbeError",
    "AccelError",
    "AnalysisError",
    "ReelError",
    "ReelParseError",
    "ReelImportError",
    "ReconcileError",
]
