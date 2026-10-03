"""Render pipeline: turn a :class:`RenderPlan` into one verified movie per event.

This is HLD slice #4. It consumes the three foundations — ``event-resolution``
(the :class:`~auto_reel_ng.event.plan.RenderPlan`), ``media-probe`` (typed clip
facts), and ``acceleration-profile`` (per-op ffmpeg fragments + frame-location
tracking) — and produces a polished movie with real chapters.

The strategy is normalize-on-GPU + guarded stream-copy concat: flatten the plan
into a deterministic :class:`Segment` list, apply the pluggable decorator seam,
derive a :class:`TargetSpec`, normalize each non-conforming segment (with
guaranteed CPU fallbacks) or pass a probe-verified copy-eligible one through,
then equivalence-guard the join, write real ``ffmetadata`` chapters, and
re-probe the output before reporting success.
"""

from __future__ import annotations

from ..errors import RenderCancelledError, RenderError, RenderVerificationError

# Importing the title package registers the ``title`` decorator and producer; the
# render API must expose them, so trigger registration on package import.
from . import title  # noqa: E402,F401  (side-effect import after the symbols above)
from .chapters import aggregate_chapter_durations, build_ffmetadata
from .concat import build_concat_command, build_concat_list, is_copy_uniform, probe_copy_fields
from .decorators import (
    Decorator,
    apply_decorators,
    get_decorator,
    make_attacher,
    make_inserter,
    none_decorator,
    register_decorator,
    resolve_decorator_names,
)
from .normalize import (
    HDR_SLOWNESS_WARNING,
    NormalizeCommand,
    build_normalize_command,
    build_synthetic_normalize_command,
    copy_eligible,
    decide_copy_eligibility,
)
from .orchestrator import (
    BatchOutcome,
    RenderJob,
    RenderOptions,
    RenderResult,
    find_output_collisions,
    output_filename,
    output_relpath,
    render_batch,
    render_movie,
    resolve_target,
)
from .producers import ProducedSegment, Producer, get_producer, register_producer
from .segments import OverlaySpec, Segment, build_segments, kept_spans
from .target import TargetSpec, derive_target
from .title import (  # noqa: E402
    TitleCardConfig,
    TitleCardContent,
    TitleCardRequest,
    parse_title_card_config,
    render_title_card,
    resolve_card,
    resolve_card_config,
)
from .verify import verify_output

__all__ = [
    # public render API
    "render_movie",
    "render_batch",
    "RenderOptions",
    "RenderResult",
    "RenderJob",
    "BatchOutcome",
    "output_filename",
    "output_relpath",
    "find_output_collisions",
    # models
    "Segment",
    "OverlaySpec",
    "TargetSpec",
    "NormalizeCommand",
    # segment + target builders
    "build_segments",
    "kept_spans",
    "derive_target",
    "resolve_target",
    # decorators
    "Decorator",
    "register_decorator",
    "get_decorator",
    "none_decorator",
    "make_inserter",
    "make_attacher",
    "resolve_decorator_names",
    "apply_decorators",
    # normalize + copy eligibility
    "build_normalize_command",
    "build_synthetic_normalize_command",
    "copy_eligible",
    "decide_copy_eligibility",
    "HDR_SLOWNESS_WARNING",
    # synthetic-segment producers
    "ProducedSegment",
    "Producer",
    "register_producer",
    "get_producer",
    # title card
    "TitleCardConfig",
    "TitleCardContent",
    "TitleCardRequest",
    "parse_title_card_config",
    "resolve_card_config",
    "resolve_card",
    "render_title_card",
    # assembly
    "is_copy_uniform",
    "probe_copy_fields",
    "build_concat_list",
    "build_concat_command",
    "aggregate_chapter_durations",
    "build_ffmetadata",
    "verify_output",
    # errors
    "RenderError",
    "RenderVerificationError",
    "RenderCancelledError",
]
