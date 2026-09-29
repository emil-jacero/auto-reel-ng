"""The pure disk-against-document reconcile diff and apply-operations (decision **D-F**).

:func:`reconcile` classifies every clip as NEW / MISSING / ACTIVE / IGNORED from a
disk listing and a document, mutating neither. MISSING is reported, never dropped
(the probe ethos). The apply-operations :func:`add_clip` and :func:`ignore_clip`
return a *mutated document* — the engine never edits structure on its own and
never touches source files; the operator (CLI/GUI) decides. Dismissals are
recorded in the document's ``ignore`` list (D-E) so they survive a rebuild of any
derived index.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping, Optional

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ..errors import ReconcileError
from ..reel.document import ReelDocument
from ..reel.schema import build_document
from ..reel.writer import document_to_data


class ClipStatus(StrEnum):
    """How a clip relates the disk to the document.

    A :class:`~enum.StrEnum`, like the other engine vocabularies: a member *is* its
    string value, so the API publishes this set as-is and the wire value is the
    same ``new``/``missing``/``active``/``ignored`` string.
    """

    NEW = "new"  # on disk, not referenced, not ignored
    MISSING = "missing"  # referenced in the document, absent from disk
    ACTIVE = "active"  # referenced in the document and present on disk
    IGNORED = "ignored"  # on disk and listed in the document's ignore


@dataclass(frozen=True)
class ReconcileResult:
    """The classification of every clip seen on disk or referenced in the document."""

    classification: Mapping[str, ClipStatus]

    def _of(self, status: ClipStatus) -> tuple[str, ...]:
        """Identities with ``status``, in deterministic (sorted) order."""
        return tuple(sorted(i for i, s in self.classification.items() if s is status))

    @property
    def new(self) -> tuple[str, ...]:
        """Clips on disk that are neither referenced nor ignored."""
        return self._of(ClipStatus.NEW)

    @property
    def missing(self) -> tuple[str, ...]:
        """Clips the document references whose files are absent from disk."""
        return self._of(ClipStatus.MISSING)

    @property
    def active(self) -> tuple[str, ...]:
        """Clips both referenced in the document and present on disk."""
        return self._of(ClipStatus.ACTIVE)

    @property
    def ignored(self) -> tuple[str, ...]:
        """Clips present on disk and listed in the document's ignore."""
        return self._of(ClipStatus.IGNORED)


def reconcile(
    disk_identities: Iterable[str],
    document: Optional[ReelDocument] = None,
) -> ReconcileResult:
    """Classify ``disk_identities`` against ``document`` without mutating either.

    A ``None`` (or empty) document is the seeding case (D-F): every disk clip is
    NEW. A clip referenced by the document but absent from disk is MISSING and is
    reported here, never removed from the document.
    """
    disk = set(disk_identities)
    referenced = set(document.referenced_identities()) if document is not None else set()
    ignored = set(document.ignore) if document is not None else set()

    classification: dict[str, ClipStatus] = {}
    for identity in disk:
        if identity in referenced:
            classification[identity] = ClipStatus.ACTIVE
        elif identity in ignored:
            classification[identity] = ClipStatus.IGNORED
        else:
            classification[identity] = ClipStatus.NEW
    for identity in referenced:
        if identity not in disk:
            classification[identity] = ClipStatus.MISSING

    return ReconcileResult(classification=classification)


def add_clip(document: ReelDocument, identity: str, chapter: str) -> ReelDocument:
    """Return a document with ``identity`` referenced in the named ``chapter``.

    The chapter must already exist and the clip must be genuinely NEW (neither
    already referenced nor ignored). Source files are never moved or renamed.
    """
    if identity in document.referenced_identities():
        raise ReconcileError(f"add: clip {identity!r} is already referenced in the document")
    if identity in document.ignore:
        raise ReconcileError(f"add: clip {identity!r} is in 'ignore'; un-ignore it before adding")

    data = document_to_data(document)
    chapter_entry = _find_chapter(data, chapter)
    if chapter_entry is None:
        raise ReconcileError(f"add: chapter {chapter!r} does not exist in the document")

    clips = chapter_entry.get("clips")
    if not isinstance(clips, CommentedSeq):
        clips = CommentedSeq() if clips is None else CommentedSeq(clips)
        chapter_entry["clips"] = clips
    clips.append(identity)

    return build_document(data, source="<reconcile add>")


def ignore_clip(document: ReelDocument, identity: str) -> ReelDocument:
    """Return a document that records ``identity`` in its ``ignore`` list.

    A subsequent reconcile classifies the clip IGNORED rather than NEW. A clip
    referenced in a chapter cannot be ignored (that contradiction is rejected).
    Source files are never touched.
    """
    if identity in document.referenced_identities():
        raise ReconcileError(
            f"ignore: clip {identity!r} is referenced in a chapter; remove it from structure first"
        )
    if identity in document.ignore:
        return document  # already ignored; idempotent

    data = document_to_data(document)
    ignore = data.get("ignore")
    if not isinstance(ignore, CommentedSeq):
        ignore = CommentedSeq() if ignore is None else CommentedSeq(ignore)
        data["ignore"] = ignore
    ignore.append(identity)

    return build_document(data, source="<reconcile ignore>")


def _find_chapter(data: CommentedMap, name: str) -> Optional[CommentedMap]:
    """Locate the chapter mapping named ``name`` in a round-trip document map."""
    chapters = data.get("chapters")
    if not isinstance(chapters, (list, tuple)):
        return None
    for entry in chapters:
        if isinstance(entry, Mapping) and entry.get("name") == name:
            return entry  # type: ignore[return-value]
    return None
