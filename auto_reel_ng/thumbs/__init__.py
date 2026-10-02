"""Clip thumbnails (D-11): one cached JPEG frame per clip, outside the library."""

from __future__ import annotations

from .settings import ThumbnailSettings, resolve_thumbnail_settings
from .thumbnail import (
    FAILURE_TTL_SECONDS,
    STALE_TEMPORARY_AGE,
    THUMBNAIL_BOX,
    THUMBNAIL_VERSION,
    is_cached,
    one_line_cause,
    recorded_duration,
    recorded_failure,
    sweep_stale_temporaries,
    thumbnail_args,
    thumbnail_for,
    thumbnail_key,
    thumbnail_path,
)

__all__ = [
    "FAILURE_TTL_SECONDS",
    "STALE_TEMPORARY_AGE",
    "THUMBNAIL_BOX",
    "THUMBNAIL_VERSION",
    "ThumbnailSettings",
    "is_cached",
    "one_line_cause",
    "recorded_duration",
    "recorded_failure",
    "resolve_thumbnail_settings",
    "sweep_stale_temporaries",
    "thumbnail_args",
    "thumbnail_for",
    "thumbnail_key",
    "thumbnail_path",
]
