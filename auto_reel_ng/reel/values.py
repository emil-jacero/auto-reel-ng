"""Pure scans over a parsed document tree, shared by every layer that validates one.

Two questions about a tree of mappings, lists and scalars: does a string anywhere in it
hold a lone surrogate (text that cannot be encoded as UTF-8), and does a mapping anywhere in
it use a key that is not a string. Both *return* the location instead of raising, because
``reel/`` reports a :class:`~auto_reel_ng.errors.ReelParseError` and ``config/`` its own
``ConfigError``; the caller words the message.

The walks are iterative (an explicit stack), so a deeply nested structure built by an API
caller cannot raise ``RecursionError`` here, and each container is visited once, so an
aliased or self-referencing YAML structure terminates. Locations are rendered like
``look.layers[0]`` or ``chapters[1].clips[0]``; a key that is not a plain identifier, or that
is not a string, is shown as ``['a.mp4']`` (escaped with ``repr``, so a surrogate in a key
never reaches the message raw).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator, Mapping, Optional

__all__ = ["NonStrKey", "find_lone_surrogate", "find_non_str_key"]

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

# A path is a linked list of segments, rendered only when a scan finds something.
_Link = Optional[tuple[str, "_Link"]]


@dataclass(frozen=True)
class NonStrKey:
    """A mapping key that is not a string: where its mapping is, the key, and what it is."""

    path: str
    key: Any
    kind: str


def find_lone_surrogate(tree: Any, *, root: str = "") -> Optional[str]:
    """The location of the first string in ``tree`` that is not UTF-8 encodable, else ``None``.

    Visits every string, key or value, at any depth. A lone surrogate (the double-quoted YAML
    escape ``"\\ud800"`` yields one) is the only way a ``str`` fails to encode; a character
    beyond U+FFFF is one real code point and is not flagged. ``root`` prefixes every location.
    """
    for node, link in _walk(tree, _root_link(root)):
        if isinstance(node, str) and _unencodable(node):
            return _render(link)
    return None


def find_non_str_key(tree: Any, *, root: str = "") -> Optional[NonStrKey]:
    """The first mapping key in ``tree`` (any depth, lists included) that is not a ``str``.

    The result names the location of the mapping that holds the key, the key itself and its
    kind (``integer``, ``date``, ...). ``root`` prefixes every location (``"look"``).
    """
    for node, link in _walk(tree, _root_link(root), keys=False):
        if isinstance(node, Mapping):
            for key in node:
                if not isinstance(key, str):
                    return NonStrKey(path=_render(link), key=key, kind=_kind(key))
    return None


def _walk(tree: Any, link: _Link, *, keys: bool = True) -> Iterator[tuple[Any, _Link]]:
    """Every node of ``tree`` in document order with its location; string keys when ``keys``.

    A mapping or list is yielded before its children and at most once, whatever the number
    of aliases that point at it: a revisited container is neither yielded nor expanded.
    """
    seen: set[int] = set()
    stack: list[tuple[Any, _Link]] = [(tree, link)]
    while stack:
        node, here = stack.pop()
        children: list[tuple[Any, _Link]] = []
        if isinstance(node, Mapping):
            if id(node) in seen:
                continue
            seen.add(id(node))
            yield node, here
            for key, value in node.items():
                if keys and isinstance(key, str):
                    children.append((key, (_segment(key), here)))
                children.append((value, (_segment(key), here)))
        elif isinstance(node, (list, tuple)):
            if id(node) in seen:
                continue
            seen.add(id(node))
            yield node, here
            children.extend((item, (f"[{i}]", here)) for i, item in enumerate(node))
        else:
            yield node, here
        stack.extend(reversed(children))


def _unencodable(text: str) -> bool:
    if text.isascii():
        return False
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


def _root_link(root: str) -> _Link:
    return (root, None) if root else None


def _segment(key: Any) -> str:
    if isinstance(key, str) and _IDENTIFIER.match(key):
        return f".{key}"
    return f"[{key!r}]"


def _render(link: _Link) -> str:
    parts: list[str] = []
    while link is not None:
        parts.append(link[0])
        link = link[1]
    text = "".join(reversed(parts))
    return text[1:] if text.startswith(".") else text


def _kind(key: Any) -> str:
    """A short word for a key's type, for an error message (``integer``, ``date``, ...)."""
    if isinstance(key, bool):
        return "boolean"
    if isinstance(key, int):
        return "integer"
    if isinstance(key, float):
        return "number"
    if isinstance(key, datetime):
        return "timestamp"
    if isinstance(key, date):
        return "date"
    if key is None:
        return "null"
    return type(key).__name__
