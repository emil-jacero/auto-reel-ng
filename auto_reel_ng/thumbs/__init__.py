"""Clip thumbnails (D-11): one cached JPEG frame per clip, outside the library."""

from __future__ import annotations

from .settings import ThumbnailSettings, resolve_thumbnail_settings
from .thumbnail import (
    THUMBNAIL_BOX,
    THUMBNAIL_VERSION,
    is_cached,
    thumbnail_args,
    thumbnail_for,
    thumbnail_key,
    thumbnail_path,
)

__all__ = [
    "THUMBNAIL_BOX",
    "THUMBNAIL_VERSION",
    "ThumbnailSettings",
    "is_cached",
    "resolve_thumbnail_settings",
    "thumbnail_args",
    "thumbnail_for",
    "thumbnail_key",
    "thumbnail_path",
]
