"""Typed, immutable model of a ``reel.yaml`` v0 editorial document.

The model is the engine's *view* of a document; the authoritative on-disk
representation is a ruamel round-trip structure carried alongside it (``_data``)
so the writer can re-emit comments and key order byte-stable (decision **D-G**).
Engine logic reads the typed fields; only the writer touches ``_data``.

Two design rules from the change (D-B, D-C):

- **Structure and properties are normalized apart.** ``chapters`` owns order and
  membership (clip references only); ``clips`` is a flat map of per-clip
  properties keyed by identity. A clip's trims survive a reorder because position
  and attributes never live in the same record.
- **Identity is the event-relative path** (``Reception/00400.mp4``), unique by
  construction. The GUI displays the basename.

``look`` is carried opaquely in v0 (D-I): parsed, preserved, round-tripped, but
never interpreted on its inner keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping, Optional

# The only document version this engine defines.
SCHEMA_VERSION = 0

# The default chapter (root-level clips, not in a named subdirectory) carries the
# empty name; named chapters come from subdirectories or the GUI.
DEFAULT_CHAPTER_NAME = ""


@dataclass(frozen=True)
class Trim:
    """One cut span to REMOVE from a clip (decision **D-D**).

    ``start``/``end`` are seconds and map to the YAML keys ``in``/``out`` (``in``
    is a Python keyword, so the field is renamed). ``reason`` is an open string
    (D-K): known values (``black``/``white``/``freeze``/``manual``) are documented
    for the GUI/analysis but not enforced, so a later analysis change can add new
    kinds without a schema change.
    """

    start: float
    end: float
    reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize using the YAML vocabulary (``in``/``out``)."""
        return {"in": self.start, "out": self.end, "reason": self.reason}


@dataclass(frozen=True)
class ClipRef:
    """A reference to a clip by its event-relative-path identity (D-C)."""

    identity: str

    @property
    def basename(self) -> str:
        """The trailing path component the GUI displays."""
        return PurePosixPath(self.identity).name


@dataclass(frozen=True)
class ClipProperties:
    """Per-clip editorial attributes, keyed in ``clips`` by identity (D-B).

    ``title`` is a three-state override: ``None`` defers to the baseline (first
    included clip of the chapter), ``True`` forces this clip as the title,
    ``False`` prevents the baseline from selecting it. ``exclude`` drops the clip
    from the render plan while leaving it in the document.
    """

    trims: tuple[Trim, ...] = ()
    title: Optional[bool] = None
    rotate: Optional[int] = None
    exclude: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging."""
        return {
            "trims": [t.to_dict() for t in self.trims],
            "title": self.title,
            "rotate": self.rotate,
            "exclude": self.exclude,
        }


def is_excluded(clips: Mapping[str, ClipProperties], identity: str) -> bool:
    """Whether ``clips`` marks ``identity`` ``exclude: true`` (a clip with no entry is not).

    The one definition of the rule: the engine's missing-clip check and plan, and the
    API's read model, all ask this, so they cannot drift apart.
    """
    props = clips.get(identity)
    return props is not None and props.exclude


@dataclass(frozen=True)
class Chapter:
    """An ordered chapter: a name and an ordered list of clip references (D-B)."""

    name: str
    clips: tuple[ClipRef, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging."""
        return {"name": self.name, "clips": [c.identity for c in self.clips]}


@dataclass(frozen=True)
class Metadata:
    """Event metadata: title, date, location, description (all optional)."""

    title: Optional[str] = None
    date: Optional[date] = None
    location: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict for debug logging."""
        return {
            "title": self.title,
            "date": self.date.isoformat() if self.date else None,
            "location": self.location,
            "description": self.description,
        }


class SortMethod(StrEnum):
    """How clips entering a document are ordered (auto-reel's ``sort.method``)."""

    DATETIME = "datetime"  # file mtime, oldest first; ties by the filename order
    FILENAME = "filename"  # natural, case-insensitive file name order
    CUSTOM = "custom"  # ``custom_order`` positions first, then the rest by filename; per event


@dataclass(frozen=True)
class ClipOrder:
    """The sort rule for clips entering a document (seeding and NEW-clip adoption).

    ``custom_order`` maps a clip's file name (basename) to its position and is only
    meaningful with :attr:`SortMethod.CUSTOM`.
    """

    method: SortMethod = SortMethod.DATETIME
    reverse: bool = False
    custom_order: Mapping[str, int] = field(default=MappingProxyType({}), hash=False)


#: auto-reel's own default: ``datetime``, not reversed.
DEFAULT_CLIP_ORDER = ClipOrder()


@dataclass(frozen=True)
class ReelDocument:  # pylint: disable=too-many-instance-attributes
    """A loaded, validated v0 editorial document.

    The typed fields are the engine's read model. ``_data`` is the ruamel
    round-trip structure the writer re-emits to preserve comments and key order;
    it is excluded from equality and repr so two documents compare on content.
    """

    version: int = SCHEMA_VERSION
    metadata: Metadata = field(default_factory=Metadata)
    look: Mapping[str, Any] = field(default_factory=dict)
    chapters: tuple[Chapter, ...] = ()
    clips: Mapping[str, ClipProperties] = field(default_factory=dict)
    ignore: tuple[str, ...] = ()
    #: The event's own sort rule, overriding the project's for clips entering this document.
    sort: Optional[ClipOrder] = None
    _data: Optional[Any] = field(default=None, compare=False, repr=False)

    @property
    def raw(self) -> Optional[Any]:
        """The ruamel round-trip structure this document was loaded from, if any.

        Present for loaded documents (so the writer can re-emit them byte-stable);
        ``None`` for documents built in memory (seeded/imported), which serialize
        from the typed fields instead.
        """
        return self._data

    def chapter(self, name: str) -> Optional[Chapter]:
        """Return the chapter named ``name``, or ``None`` if absent.

        The exact name wins; otherwise the chapter whose name equals ``name`` under
        ``str.casefold()``. Chapter names are unique under that fold, so at most one chapter
        can match. Whitespace is never trimmed: a padded name matches nothing.
        """
        for chapter in self.chapters:
            if chapter.name == name:
                return chapter
        folded = name.casefold()
        for chapter in self.chapters:
            if chapter.name.casefold() == folded:
                return chapter
        return None

    def referenced_identities(self) -> tuple[str, ...]:
        """Every clip identity referenced across all chapters, in document order."""
        return tuple(ref.identity for chapter in self.chapters for ref in chapter.clips)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging (excludes the raw round-trip data).

        This is also the staleness fingerprint's editorial input. ``sort`` is left
        out: it only orders clips entering ``chapters``, which is hashed already.
        """
        return {
            "version": self.version,
            "metadata": self.metadata.to_dict(),
            "look": dict(self.look),
            "chapters": [c.to_dict() for c in self.chapters],
            "clips": {identity: props.to_dict() for identity, props in self.clips.items()},
            "ignore": list(self.ignore),
        }
