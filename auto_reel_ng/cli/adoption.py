"""Per-event document resolution and the NEW-clip adoption policy (D-CLI3).

:func:`~auto_reel_ng.event.reconcile.reconcile` classifies but never mutates, so
the policy lives here:

- No ``reel.yaml`` -> seed a document from disk structure (the seeding case, D-F).
- A ``reel.yaml`` plus ``NEW`` clips on disk -> adopt each ``NEW`` clip into the
  default chapter (configurable) so an added file is never silently dropped. They
  are appended after the chapter's existing clips, in the sort rule's order among
  themselves (the document's own ``sort`` when set, else the project's); an
  existing order is never re-sorted.
- ``MISSING`` clips (referenced, absent from disk) are reported by the caller and
  never removed from the document.

Only ``render`` adopts and persists; ``scan`` resolves with ``adopt=False`` and
writes nothing. The prepared ``document`` carries resolved metadata (reel.yaml over
folder name, D-2); ``persist`` writes the ``authored`` one, so resolution never
reaches disk.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ..event import ClipOrder, ReconcileResult, add_clip, order_clips, reconcile, scan_event
from ..event.metadata import (
    REEL_FILENAME,
    load_authored_document,
    load_event_document,
    with_resolved_metadata,
)
from ..reel import ReelDocument, build_document, write_document
from ..reel.document import DEFAULT_CHAPTER_NAME
from ..reel.writer import document_to_data

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedEvent:
    """An event resolved to a document plus its disk reconcile (D-CLI3).

    ``document`` has resolved metadata and is what every consumer reads;
    ``authored`` is the same document as authored, and is what :func:`persist` writes.
    """

    event_dir: Path
    document: ReelDocument
    reconcile: ReconcileResult
    seeded: bool
    adopted: Tuple[str, ...]
    authored: ReelDocument

    @property
    def changed(self) -> bool:
        """Whether the document differs from disk and is worth persisting."""
        return self.seeded or bool(self.adopted)


def load_or_seed(event_dir: Path, *, order: ClipOrder) -> Tuple[ReelDocument, bool]:
    """Load or seed ``event_dir``'s document with resolved metadata (see :mod:`..event.metadata`)."""
    return load_event_document(event_dir, order=order)


def prepare_event(
    event_dir: Path,
    *,
    order: ClipOrder,
    adopt: bool = True,
    adopt_chapter: str = DEFAULT_CHAPTER_NAME,
) -> PreparedEvent:
    """Resolve ``event_dir`` to a document and reconcile it against disk.

    When ``adopt`` is set, every ``NEW`` clip is appended to ``adopt_chapter``
    (created if absent), in the document's own ``sort`` among themselves, or
    ``order`` (the project's rule) when it sets none, so an added file is included
    rather than dropped. ``MISSING`` clips are left in the document for the caller
    to report loudly (D-CLI3).
    """
    event_dir = Path(event_dir)
    authored, seeded = load_authored_document(event_dir, order=order)
    listing = scan_event(event_dir)
    result = reconcile(listing.identities, authored)

    adopted: Tuple[str, ...] = ()
    if adopt and result.new:
        authored = _ensure_chapter(authored, adopt_chapter)
        adopted = order_clips(result.new, event_dir, authored.sort or order)
        for identity in adopted:
            authored = add_clip(authored, identity, adopt_chapter)

    return PreparedEvent(
        event_dir=event_dir,
        document=with_resolved_metadata(authored, event_dir),
        reconcile=result,
        seeded=seeded,
        adopted=adopted,
        authored=authored,
    )


def persist(event: PreparedEvent) -> Optional[Path]:
    """Write the event's document back to ``reel.yaml`` when it changed; return the path."""
    if not event.changed:
        return None
    reel_path = event.event_dir / REEL_FILENAME
    write_document(event.authored, reel_path)
    return reel_path


def _ensure_chapter(document: ReelDocument, name: str) -> ReelDocument:
    """Return a document that has a chapter named ``name`` (appending an empty one).

    Adopting a ``NEW`` clip needs its target chapter to exist; a freshly authored
    or subdir-only document may lack the default chapter, so create it rather than
    let :func:`add_clip` fail.
    """
    if document.chapter(name) is not None:
        return document
    data = document_to_data(document)
    chapters = data.get("chapters")
    if not isinstance(chapters, CommentedSeq):
        chapters = CommentedSeq() if chapters is None else CommentedSeq(chapters)
        data["chapters"] = chapters
    entry = CommentedMap()
    entry["name"] = name
    entry["clips"] = CommentedSeq()
    chapters.append(entry)
    return build_document(data, source="<cli ensure-chapter>")
