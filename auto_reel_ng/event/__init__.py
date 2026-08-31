"""event subpackage: discovery seeding, reconcile, resolution, and editorial writes.

Provides the pure ``reconcile(disk, document)`` diff and apply-operations, the
folder-structure discovery seeder, resolution of a document + event dir into a
fully-explicit :class:`RenderPlan`, and the editorial write operation that
applies a desired editorial state onto an event's document and persists it.
"""

from __future__ import annotations

from .discovery import DiskListing, scan_event, seed_document
from .editorial import apply_editorial_write
from .plan import RenderPlan, ResolvedChapter, ResolvedClip
from .reconcile import ClipStatus, ReconcileResult, add_clip, ignore_clip, reconcile
from .resolution import resolve

__all__ = [
    # plan model
    "RenderPlan",
    "ResolvedChapter",
    "ResolvedClip",
    # resolution
    "resolve",
    # discovery / seeding
    "DiskListing",
    "scan_event",
    "seed_document",
    # reconcile
    "ClipStatus",
    "ReconcileResult",
    "reconcile",
    "add_clip",
    "ignore_clip",
    # editorial write
    "apply_editorial_write",
]
