"""Per-event document resolution and the NEW-clip adoption policy (D-CLI3).

:func:`~auto_reel_ng.event.reconcile.reconcile` classifies but never mutates, so
the policy lives here:

- No ``reel.yaml`` -> seed a document from disk structure (the seeding case, D-F).
- A ``reel.yaml`` plus ``NEW`` clips on disk -> adopt each ``NEW`` clip into the
  default chapter (configurable) so an added file is never silently dropped.
- ``MISSING`` clips (referenced, absent from disk) are reported by the caller and
  never removed from the document.

Only ``render`` adopts and persists; ``scan`` resolves with ``adopt=False`` and
writes nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ..event import ReconcileResult, add_clip, reconcile, scan_event, seed_document
from ..reel import ReelDocument, build_document, load_document, write_document
from ..reel.document import DEFAULT_CHAPTER_NAME
from ..reel.writer import document_to_data

logger = logging.getLogger(__name__)

#: The editorial document file name within an event directory.
REEL_FILENAME = "reel.yaml"


@dataclass(frozen=True)
class PreparedEvent:
    """An event resolved to a document plus its disk reconcile (D-CLI3)."""

    event_dir: Path
    document: ReelDocument
    reconcile: ReconcileResult
    seeded: bool
    adopted: Tuple[str, ...]

    @property
    def changed(self) -> bool:
        """Whether the document differs from disk and is worth persisting."""
        return self.seeded or bool(self.adopted)


def load_or_seed(event_dir: Path) -> Tuple[ReelDocument, bool]:
    """Load ``<event>/reel.yaml`` if present, else seed a document from disk structure."""
    reel_path = Path(event_dir) / REEL_FILENAME
    if reel_path.exists():
        return load_document(reel_path), False
    return seed_document(event_dir), True


def prepare_event(
    event_dir: Path,
    *,
    adopt: bool = True,
    adopt_chapter: str = DEFAULT_CHAPTER_NAME,
) -> PreparedEvent:
    """Resolve ``event_dir`` to a document and reconcile it against disk.

    When ``adopt`` is set, every ``NEW`` clip is adopted into ``adopt_chapter``
    (created if absent) so an added file is included rather than dropped. ``MISSING``
    clips are left in the document for the caller to report loudly (D-CLI3).
    """
    event_dir = Path(event_dir)
    document, seeded = load_or_seed(event_dir)
    listing = scan_event(event_dir)
    result = reconcile(listing.identities, document)

    adopted: Tuple[str, ...] = ()
    if adopt and result.new:
        document = _ensure_chapter(document, adopt_chapter)
        for identity in result.new:
            document = add_clip(document, identity, adopt_chapter)
        adopted = result.new

    return PreparedEvent(
        event_dir=event_dir,
        document=document,
        reconcile=result,
        seeded=seeded,
        adopted=adopted,
    )


def persist(event: PreparedEvent) -> Optional[Path]:
    """Write the event's document back to ``reel.yaml`` when it changed; return the path."""
    if not event.changed:
        return None
    reel_path = event.event_dir / REEL_FILENAME
    write_document(event.document, reel_path)
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
