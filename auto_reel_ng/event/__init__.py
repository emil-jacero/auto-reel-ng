"""event subpackage: discovery seeding, reconcile, and resolution.

Provides the pure ``reconcile(disk, document)`` diff and apply-operations, the
folder-structure discovery seeder, and resolution of a document + event dir into
a fully-explicit :class:`RenderPlan`.
"""

from __future__ import annotations

from .discovery import DiskListing, scan_event, seed_document
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
]
