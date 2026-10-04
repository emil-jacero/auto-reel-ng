"""Title-card text content: what the card says, composed from the plan and the chapter's card.

A card has a heading and an optional subtitle. The heading is the chapter's own
``card.title`` when it sets one, else the chapter name, else (the default chapter's opening
card) the event title. The subtitle is free text from ``card.subtitle`` and is empty by
default on every card: a card never shows the event's date, location or description by
itself. The composed lines are exposed as a pure function so layout can be asserted
structurally without rendering an image.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...errors import TitleCardError
from ...event.plan import RenderPlan, ResolvedChapter
from ...reel.document import DEFAULT_CHAPTER_NAME

#: The label of the location line, as the legacy auto-reel drew it.
LOCATION_LABEL = "Plats"


def default_subtitle(plan: RenderPlan, chapter: ResolvedChapter) -> str:
    """The subtitle a card shows when its ``subtitle`` key is absent.

    For the default chapter: the resolved date as ISO ``YYYY-MM-DD`` then ``Plats: <location>``,
    each line only when the metadata has it, joined by a newline (``""`` with neither). Any other
    chapter has no default (``""``). The description is never part of it.
    """
    if chapter.name != DEFAULT_CHAPTER_NAME:
        return ""
    lines: list[str] = []
    if plan.metadata.date is not None:
        lines.append(plan.metadata.date.isoformat())
    if plan.metadata.location and plan.metadata.location.strip():
        lines.append(f"{LOCATION_LABEL}: {plan.metadata.location.strip()}")
    return "\n".join(lines)


@dataclass(frozen=True)
class TitleCardContent:
    """The text a card displays: a heading plus an optional free-text subtitle."""

    heading: str
    subtitle: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug/golden logging."""
        return {"heading": self.heading, "subtitle": self.subtitle}


def title_card_lines(content: TitleCardContent) -> list[str]:
    """Return the ordered, non-empty display lines for ``content``.

    The heading first, then the subtitle when it is not empty. The renderer draws line 0 at
    the title size and later lines at the subtitle size; Pango wraps each line within the
    card column, with no manual positioning.
    """
    lines: list[str] = []
    if content.heading:
        lines.append(content.heading)
    if content.subtitle:
        lines.append(content.subtitle)
    return lines


def compose_content(plan: RenderPlan, chapter: ResolvedChapter) -> TitleCardContent:
    """Compose the card content for ``chapter`` from the plan and the chapter's ``card``.

    Heading: ``card.title``, else the chapter name, else (default chapter) the event title.
    Subtitle: ``card.subtitle`` as written (``""`` is none); when the key is absent, the
    :func:`default_subtitle` (the opening card's date and place, nothing for a chapter card).

    Raises:
        TitleCardError: the heading would be empty (a default chapter with no ``card.title``
            and no event title), naming the chapter, rather than drawing an empty card.
    """
    card = chapter.card
    if card is not None and card.title:
        heading = card.title
    elif chapter.name != DEFAULT_CHAPTER_NAME:
        heading = chapter.name
    else:
        heading = plan.metadata.title or ""
    if not heading.strip():
        shown = (
            "the default chapter" if chapter.name == DEFAULT_CHAPTER_NAME else repr(chapter.name)
        )
        raise TitleCardError(
            f"title card of {shown} has no heading: set card.title"
            + (" or metadata.title" if chapter.name == DEFAULT_CHAPTER_NAME else "")
        )
    if card is not None and card.subtitle is not None:
        subtitle = card.subtitle
    else:
        subtitle = default_subtitle(plan, chapter)
    return TitleCardContent(heading=heading, subtitle=subtitle)


__all__ = [
    "LOCATION_LABEL",
    "default_subtitle",
    "TitleCardContent",
    "title_card_lines",
    "compose_content",
]
