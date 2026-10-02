"""Fail-loud loader for ``reel.yaml`` documents.

Reads YAML in ruamel round-trip mode (so the validated :class:`ReelDocument`
keeps its source structure for a byte-stable rewrite) and routes the content:
a document with no ``version`` key is the auto-reel legacy format and goes to the
importer; any other document is validated as v0 by :func:`build_document`.
Validation itself lives in :mod:`schema`, which this module re-exports.

Every way the text can fail to load is a :class:`ReelParseError`, never a builtin
error: bytes that are not UTF-8, malformed YAML, and a well-formed value its tag
cannot hold — an unquoted ``2024-02-30`` is a date that does not exist — which is
reported with the value as written and its line. Every message names the real source
(not ruamel's ``<unicode string>``); a failure with no position of its own says how far
the scanner got, and one after scanning (a document nested past the recursion limit)
reports no line, which is a known limitation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Union

from ruamel.yaml import YAML
from ruamel.yaml.constructor import ConstructorError, RoundTripConstructor
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import ScalarNode

from ..errors import ReelParseError
from .document import ReelDocument
from .legacy import import_legacy_data
from .schema import build_document, lone_surrogate_message
from .values import find_lone_surrogate

__all__ = ["load_document", "loads_document", "build_document"]

_TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"


class _Constructor(RoundTripConstructor):
    """ruamel's round-trip constructor, reporting a node its tag cannot hold with its line.

    ruamel builds an unquoted ``2024-02-30`` with ``datetime.date(2024, 2, 30)`` and an
    ``!!bool maybe`` by a dict lookup, so such values escape as a bare ``ValueError``,
    ``KeyError``, ``IndexError``, ... Here they become ruamel's own ``ConstructorError``.
    An integer too long to print is refused the same way, however it is written.
    """

    def construct_non_recursive_object(self, node: Any, tag: Optional[str] = None) -> Any:
        try:
            data = super().construct_non_recursive_object(node, tag)
            if isinstance(data, int):
                # ruamel's int() refuses a decimal literal past Python's int-to-str digit limit,
                # but not the same number in hex, octal or binary; printing it would fail later,
                # in a message, a fingerprint or a JSON body, so refuse it here alike.
                str(data)
            return data
        except (YAMLError, RecursionError):
            # ruamel's own error, or a child node's converted below, already names the innermost
            # failing node; a document too deep to construct is no one node's fault.
            raise
        except Exception as exc:  # pylint: disable=broad-exception-caught
            mark = node.start_mark
            # A ValueError describes the value (no day 30 in February, not a number); the
            # other builtin errors ruamel leaks (KeyError, IndexError, ...) describe its code.
            reason = f" ({exc})" if isinstance(exc, ValueError) else ""
            raise ConstructorError(
                None,
                None,
                f"{_shown(node)} on line {mark.line + 1}, column {mark.column + 1} "
                f"is not a {_kind(node)}{reason}",
            ) from exc


def _shown(node: Any) -> str:
    """The node as written: ``'2024-02-30'`` for a scalar, ``the mapping`` otherwise."""
    return repr(node.value) if isinstance(node, ScalarNode) else f"the {node.id}"


def _kind(node: Any) -> str:
    """What the node's tag says it is: ``real date``, ``valid int``, ``valid bool``, ..."""
    if node.tag == _TIMESTAMP_TAG:
        return "real date and time" if ":" in node.value else "real date"
    return "valid " + str(node.tag).rsplit(":", 1)[-1]


def _yaml() -> YAML:
    """A ruamel round-trip YAML configured to preserve quotes and comments."""
    yaml = YAML()  # round-trip mode by default
    yaml.preserve_quotes = True
    yaml.Constructor = _Constructor
    return yaml


def _named(exc: YAMLError, source: str) -> str:
    """ruamel's error text with ``source`` where it names the stream it was reading.

    A loader handed a string calls it ``<unicode string>`` in every ``in "...", line N``
    excerpt. The marks belong to the exception, so renaming them touches nothing else, and
    the document's own text is never rewritten (a string replace would).
    """
    for mark in (getattr(exc, "context_mark", None), getattr(exc, "problem_mark", None)):
        if mark is not None:
            mark.name = source
    return str(exc)


def _reached_line(text: str) -> Optional[int]:
    """The line the scanner got as far as before it failed, or ``None`` if it did not fail.

    A lower bound, not the failing line: ruamel holds a simple-key token back until the next
    token is fetched. Re-scanning is paid only by a document that is already failing; a scan
    that completes (the failure came later) or breaks at once has nothing to report.
    """
    last = None
    try:
        for token in _yaml().scan(text):
            last = token
    except Exception:  # pylint: disable=broad-exception-caught
        return None if last is None else int(last.end_mark.line) + 1
    return None


def load_document(path: Union[str, Path]) -> ReelDocument:
    """Load and validate a ``reel.yaml`` file into a typed :class:`ReelDocument`.

    A missing ``version`` key routes the file to the auto-reel legacy importer.
    Raises :class:`ReelParseError` on any malformed or invalid content, including
    bytes that are not UTF-8 and a value that cannot be constructed
    (``date: 2024-02-30``), and when the file cannot be read.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:  # the content's fault, not the disk's; no encoding guessed
        raise ReelParseError(f"{path}: not UTF-8 text ({exc.reason} at byte {exc.start})") from exc
    except OSError as exc:
        raise ReelParseError(f"{path}: cannot read document: {exc}") from exc
    return loads_document(text, source=str(path))


def loads_document(text: str, *, source: str = "<string>") -> ReelDocument:
    """Parse and validate a ``reel.yaml`` document from a string.

    Raises :class:`ReelParseError`, never a builtin error, for text that cannot be
    loaded: an invalid value (well-formed YAML its tag cannot hold) names the value
    and its line, malformed YAML carries ruamel's reason and position when it has one.
    """
    try:
        data = _yaml().load(text)
    except ConstructorError as exc:  # well-formed YAML, but a node its tag cannot build
        raise ReelParseError(f"{source}: invalid value: {_named(exc, source)}") from exc
    except YAMLError as exc:
        raise ReelParseError(f"{source}: malformed YAML: {_named(exc, source)}") from exc
    except RecursionError as exc:
        # Hit after the whole text scanned fine (composing or constructing), so no line exists.
        raise ReelParseError(f"{source}: nested too deeply to load ({exc})") from exc
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # ruamel failing with no node to blame: a scanner chr() error, the root collection's
        # constructor after its first yield (a bare assert in the omap constructor has no
        # text: its type is the reason left to name)
        reason = str(exc) or type(exc).__name__
        reached = _reached_line(text)
        where = f" (reading got as far as line {reached})" if reached else ""
        raise ReelParseError(f"{source}: malformed YAML: {reason}{where}") from exc

    if data is None:
        raise ReelParseError(f"{source}: empty document")
    if not isinstance(data, Mapping):
        raise ReelParseError(
            f"{source}: top-level document must be a mapping, got {type(data).__name__}"
        )

    if "version" not in data:
        # No version key => auto-reel legacy format; import into a v0 document. The importer
        # copies only the fields it maps, so scan the raw mapping for what it would drop.
        surrogate = find_lone_surrogate(data)
        if surrogate is not None:
            raise ReelParseError(lone_surrogate_message(source, surrogate))
        return import_legacy_data(data, source=source)

    return build_document(data, source=source)
