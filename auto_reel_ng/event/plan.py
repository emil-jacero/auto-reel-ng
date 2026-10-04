"""The resolved render plan: a fully-explicit view of a document for rendering.

Where a :class:`~auto_reel_ng.reel.document.ReelDocument` says *what the file
records* (structure and properties kept apart), a :class:`RenderPlan` says *what
to render*: chapters and clips materialized in order, per-clip properties applied,
the title clip of each chapter chosen, excluded clips dropped, and ``look``
filled from the server defaults (decision **D-H**). Render and GUI consume the
plan; only the document is written back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Mapping, Optional

from ..reel.card import ChapterCard
from ..reel.document import Metadata, Poster, Trim


@dataclass(frozen=True)
class ResolvedClip:
    """One clip in the plan with its editorial properties already applied."""

    identity: str
    cut_spans: tuple[Trim, ...] = ()
    rotate: Optional[int] = None
    is_title: bool = False

    @property
    def basename(self) -> str:
        """The trailing path component the GUI displays."""
        return PurePosixPath(self.identity).name

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging."""
        return {
            "identity": self.identity,
            "cut_spans": [t.to_dict() for t in self.cut_spans],
            "rotate": self.rotate,
            "is_title": self.is_title,
        }


@dataclass(frozen=True)
class ResolvedChapter:
    """A chapter materialized into an explicit, ordered list of included clips."""

    name: str
    clips: tuple[ResolvedClip, ...] = ()
    #: The chapter's title-card overrides from the document; kept even when every clip of the
    #: chapter is excluded (the card then draws nothing).
    card: Optional[ChapterCard] = None

    @property
    def title_clip(self) -> Optional[ResolvedClip]:
        """The clip marked as this chapter's title, if any."""
        for clip in self.clips:
            if clip.is_title:
                return clip
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging."""
        data: dict[str, Any] = {"name": self.name, "clips": [c.to_dict() for c in self.clips]}
        if self.card is not None:
            data["card"] = self.card.to_dict()
        return data


@dataclass(frozen=True)
class RenderPlan:
    """A fully-explicit, deterministic plan derived from a document + event dir."""

    metadata: Metadata = field(default_factory=Metadata)
    look: Mapping[str, Any] = field(default_factory=dict)
    chapters: tuple[ResolvedChapter, ...] = ()
    #: The document's chosen poster frame; ``None`` when it sets none (the default frame).
    poster: Optional[Poster] = None
    #: Why ``poster``'s clip is not played by the movie (``missing``, ``ignored``, ``excluded``),
    #: or ``None`` when it is played or there is no poster. The render falls back with a warning.
    poster_unplayed: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging."""
        data: dict[str, Any] = {
            "metadata": self.metadata.to_dict(),
            "look": dict(self.look),
            "chapters": [c.to_dict() for c in self.chapters],
        }
        if self.poster is not None:
            data["poster"] = self.poster.to_dict()
        return data
