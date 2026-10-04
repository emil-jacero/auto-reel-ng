"""reel-document subpackage: the ``reel.yaml`` v0 schema, model, and I/O.

Provides the typed document model, a fail-loud v0 parser/validator, a
round-trip-preserving writer, and an auto-reel legacy importer.
"""

from __future__ import annotations

from .card import ChapterCard
from .document import (
    DEFAULT_CHAPTER_NAME,
    SCHEMA_VERSION,
    Chapter,
    ClipProperties,
    ClipRef,
    Metadata,
    Poster,
    ReelDocument,
    Trim,
    is_excluded,
)
from .legacy import ImportResult, import_legacy, import_legacy_data
from .parser import load_document, loads_document
from .schema import build_document
from .writer import document_to_data, dumps_document, write_document

__all__ = [
    # model
    "SCHEMA_VERSION",
    "DEFAULT_CHAPTER_NAME",
    "ReelDocument",
    "Metadata",
    "Chapter",
    "ChapterCard",
    "ClipRef",
    "ClipProperties",
    "Trim",
    "Poster",
    "is_excluded",
    # load / validate
    "load_document",
    "loads_document",
    "build_document",
    # write
    "write_document",
    "dumps_document",
    "document_to_data",
    # legacy import
    "import_legacy",
    "import_legacy_data",
    "ImportResult",
]
