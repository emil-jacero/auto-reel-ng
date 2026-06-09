"""Ingest layouts: map a project root to events via a named, pluggable layout (D-6).

Public surface: the :class:`EventRef`/:class:`FolderHint` data, the :class:`Layout`
protocol, a name-keyed registry (:func:`register_layout`/:func:`get_layout`/
:func:`layout_names`), and the two built-ins (``year-event``/``flat``), registered
on import.
"""

from __future__ import annotations

from .layouts import (
    DEFAULT_LAYOUT,
    EventRef,
    FolderHint,
    Layout,
    LayoutError,
    flat_layout,
    get_layout,
    layout_names,
    register_layout,
    year_event_layout,
)

__all__ = [
    "DEFAULT_LAYOUT",
    "EventRef",
    "FolderHint",
    "Layout",
    "LayoutError",
    "get_layout",
    "layout_names",
    "register_layout",
    "year_event_layout",
    "flat_layout",
]
