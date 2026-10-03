"""A chapter's title card as the document records it (``chapters[i].card``).

The card is the content and look of the title card the movie shows at the start of a
chapter; the default chapter ``""`` holds the opening card. Every field is optional: an
unset field defers to the chapter name / event title (text) or to the event-wide
``look.title_card`` and the engine defaults (style). The allowed keys, their sets and the
numeric bounds live here, below the renderer, so the loader and the renderer share one
definition and ``reel/`` never imports ``render/`` (Principle VI).

Whether ``font_family`` names a font the renderer can use is decided when the card is
rendered; the loader only checks it is a non-blank string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

#: Every key a ``card`` mapping may hold, in the order the writer emits them.
CARD_KEYS: tuple[str, ...] = (
    "title",
    "subtitle",
    "duration",
    "background",
    "font_family",
    "title_font_size",
    "subtitle_font_size",
    "text_color",
    "position",
)

#: Whether the card is text on black or text over the chapter's first clip.
CARD_BACKGROUNDS: tuple[str, ...] = ("black", "video")

#: Where the text sits on the card.
CARD_POSITIONS: tuple[str, ...] = ("center", "top", "bottom")

#: The shortest and longest card, in seconds (below 0.5 s the default fades clamp to almost
#: nothing; above 60 s is most likely milliseconds typed as seconds).
CARD_MIN_DURATION = 0.5
CARD_MAX_DURATION = 60.0

#: Font sizes in pixels at a 1080p canvas, inclusive.
CARD_MIN_FONT_SIZE = 8
CARD_MAX_FONT_SIZE = 400


@dataclass(frozen=True)
class ChapterCard:  # pylint: disable=too-many-instance-attributes
    """A chapter's card overrides; ``None`` means "not set here"."""

    title: Optional[str] = None
    subtitle: Optional[str] = None
    duration: Optional[float] = None
    background: Optional[str] = None
    font_family: Optional[str] = None
    title_font_size: Optional[int] = None
    subtitle_font_size: Optional[int] = None
    text_color: Optional[str] = None
    position: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Only the fields that are set, in :data:`CARD_KEYS` order."""
        return {key: getattr(self, key) for key in CARD_KEYS if getattr(self, key) is not None}


__all__ = [
    "CARD_KEYS",
    "CARD_BACKGROUNDS",
    "CARD_POSITIONS",
    "CARD_MIN_DURATION",
    "CARD_MAX_DURATION",
    "CARD_MIN_FONT_SIZE",
    "CARD_MAX_FONT_SIZE",
    "ChapterCard",
]
