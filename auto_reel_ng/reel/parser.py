"""Fail-loud loader for ``reel.yaml`` documents.

Reads YAML in ruamel round-trip mode (so the validated :class:`ReelDocument`
keeps its source structure for a byte-stable rewrite) and routes the content:
a document with no ``version`` key is the auto-reel legacy format and goes to the
importer; any other document is validated as v0 by :func:`build_document`.
Validation itself lives in :mod:`schema`, which this module re-exports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Union

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..errors import ReelParseError
from .document import ReelDocument
from .legacy import import_legacy_data
from .schema import build_document

__all__ = ["load_document", "loads_document", "build_document"]


def _yaml() -> YAML:
    """A ruamel round-trip YAML configured to preserve quotes and comments."""
    yaml = YAML()  # round-trip mode by default
    yaml.preserve_quotes = True
    return yaml


def load_document(path: Union[str, Path]) -> ReelDocument:
    """Load and validate a ``reel.yaml`` file into a typed :class:`ReelDocument`.

    A missing ``version`` key routes the file to the auto-reel legacy importer.
    Raises :class:`ReelParseError` on any malformed or invalid content.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReelParseError(f"{path}: cannot read document: {exc}") from exc
    return loads_document(text, source=str(path))


def loads_document(text: str, *, source: str = "<string>") -> ReelDocument:
    """Parse and validate a ``reel.yaml`` document from a string."""
    try:
        data = _yaml().load(text)
    except YAMLError as exc:
        raise ReelParseError(f"{source}: malformed YAML: {exc}") from exc

    if data is None:
        raise ReelParseError(f"{source}: empty document")
    if not isinstance(data, Mapping):
        raise ReelParseError(
            f"{source}: top-level document must be a mapping, got {type(data).__name__}"
        )

    if "version" not in data:
        # No version key => auto-reel legacy format; import into a v0 document.
        return import_legacy_data(data, source=source)

    return build_document(data, source=source)
