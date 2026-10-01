"""Per-event document resolution and the NEW-clip adoption policy (D-12, amends D-CLI3).

:func:`~auto_reel_ng.event.reconcile.reconcile` classifies but never mutates, so
the policy lives here:

- No ``reel.yaml`` -> seed a document from disk structure (the seeding case, D-F).
- A ``reel.yaml`` plus ``NEW`` clips on disk -> adopt each ``NEW`` clip into the
  chapter named after its folder (the event folder's clips into the default
  chapter), or into the default chapter when the document names no such chapter,
  so an added file is never silently dropped. A document that names no chapters
  at all is adopted into as a new event is seeded: each folder becomes its own
  chapter. Entering clips are appended after the chapter's existing clips, in the
  sort rule's order among themselves (the document's own ``sort`` when set, else
  the project's); an existing order is never re-sorted.
  :func:`place_disk_clips` is that placement, which the events read model shares
  so the page shows each clip where a render adopts it.
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
from typing import Dict, Iterable, List, Optional, Tuple

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ..errors import ReconcileError
from ..event import (
    ClipOrder,
    DiskListing,
    ReconcileResult,
    add_clip,
    order_clips,
    reconcile,
    scan_event,
)
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
    """An event resolved to a document plus its disk reconcile (D-12).

    ``document`` has resolved metadata and is what every consumer reads;
    ``authored`` is the same document as authored, and is what :func:`persist` writes.
    ``adopted`` lists the ``NEW`` clips adoption placed, chapter by chapter in the
    order :func:`place_disk_clips` returns them.
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


def place_disk_clips(
    document: ReelDocument,
    listing: DiskListing,
    identities: Iterable[str],
    *,
    event_dir: Path,
    order: ClipOrder,
) -> Tuple[Tuple[str, Tuple[str, ...]], ...]:
    """The chapter each disk clip the document does not list enters, and its order there (D-12).

    ``identities`` are clips ``listing`` holds that ``document`` does not list (NEW, or for the
    read model also IGNORED). Each enters the chapter named after its ``listing`` folder group
    (the event root is the default chapter) when ``document`` names that chapter, else the
    default chapter. Returns ``((chapter, clips), ...)`` with no empty groups: the document's
    chapters in its order, then the default chapter when the document does not name it. Each
    group's clips are in ``order_clips(..., document.sort or order)`` order.

    A document that names no chapters is placed as a new event is seeded: every clip enters
    its folder's chapter, in ``listing.by_chapter`` order (the default chapter first, then
    subfolders by name).

    Raises:
        ReconcileError: an identity ``listing`` does not hold (a caller bug; fail loud).
    """
    folder_of = {identity: name for name, clips in listing.by_chapter for identity in clips}
    seed_like = not document.chapters
    buckets: Dict[str, List[str]] = {}
    for identity in identities:
        folder = folder_of.get(identity)
        if folder is None:
            raise ReconcileError(f"place: clip {identity!r} is not in the event's disk listing")
        named = seed_like or document.chapter(folder) is not None
        buckets.setdefault(folder if named else DEFAULT_CHAPTER_NAME, []).append(identity)

    if seed_like:
        names = [name for name, _ in listing.by_chapter]
    else:
        names = [chapter.name for chapter in document.chapters]
        if document.chapter(DEFAULT_CHAPTER_NAME) is None:
            names.append(DEFAULT_CHAPTER_NAME)
    rule = document.sort or order
    return tuple(
        (name, order_clips(buckets[name], event_dir, rule)) for name in names if name in buckets
    )


def prepare_event(event_dir: Path, *, order: ClipOrder, adopt: bool = True) -> PreparedEvent:
    """Resolve ``event_dir`` to a document and reconcile it against disk.

    When ``adopt`` is set, every ``NEW`` clip is adopted by :func:`place_disk_clips`
    (D-12): into its folder's chapter, or the default chapter (created if absent)
    when the document names no such chapter, or into the seed's chapters when the
    document names none. Entering clips follow the document's own ``sort`` among
    themselves, or ``order`` (the project's rule) when it sets none, so an added
    file is included rather than dropped. ``MISSING`` clips are left in the
    document for the caller to report loudly.
    """
    event_dir = Path(event_dir)
    authored, seeded = load_authored_document(event_dir, order=order)
    listing = scan_event(event_dir)
    result = reconcile(listing.identities, authored)

    adopted: Tuple[str, ...] = ()
    if adopt and result.new:
        placed = place_disk_clips(authored, listing, result.new, event_dir=event_dir, order=order)
        for chapter, clips in placed:
            # The default chapter, appended last; or, in a document that names no
            # chapters, each seed chapter in turn.
            authored = _ensure_chapter(authored, chapter)
            for identity in clips:
                authored = add_clip(authored, identity, chapter)
            adopted += clips

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
    or subdir-only document may lack the default chapter, and a document that names
    no chapters lacks every seed chapter, so create it rather than let
    :func:`add_clip` fail.
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
