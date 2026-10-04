"""The event's effective poster as the detail reports it (change ``event-poster-gui``).

Probe-free and read-only. The rule is the engine's (:func:`~auto_reel_ng.render.poster.resolve_poster`):
the document's ``poster`` when its clip is played, else the first played clip's default frame,
with a note naming why a chosen clip is not used. This module differs from the render only in
what it cannot know without a probe (the default frame's time), and in reading "played" from the
detail's own chapters, which already place the disk clips a render would adopt.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..event.reconcile import ClipStatus
from ..reel.document import ReelDocument
from .schemas import ChapterOut, PosterOut, PosterSource


def played_clips(chapters: List[ChapterOut]) -> List[str]:
    """The identities a render plays, in order: not missing, ignored or excluded."""
    return [
        clip.identity
        for chapter in chapters
        for clip in chapter.clips
        if clip.status in (ClipStatus.ACTIVE, ClipStatus.NEW) and not clip.excluded
    ]


def poster_for(
    document: Optional[ReelDocument], chapters: List[ChapterOut]
) -> Tuple[Optional[PosterOut], Optional[str]]:
    """``(poster, poster_note)``: the effective poster and why a chosen one is not used."""
    played = played_clips(chapters)
    if not played:
        return None, None
    chosen = document.poster if document is not None else None
    if chosen is not None and chosen.clip in played:
        return PosterOut(clip=chosen.clip, at=chosen.at, source=PosterSource.EVENT), None
    note: Optional[str] = None
    if chosen is not None:
        statuses = {c.identity: c for chapter in chapters for c in chapter.clips}
        listed = statuses.get(chosen.clip)
        if document is not None and chosen.clip in document.ignore:
            reason = "ignored"
        elif listed is not None and listed.excluded:
            reason = "excluded"
        else:
            reason = "missing"
        note = f"poster clip {chosen.clip!r} is {reason}; using the first played clip's frame"
    return PosterOut(clip=played[0], at=None, source=PosterSource.DEFAULT), note


__all__ = ["played_clips", "poster_for"]
