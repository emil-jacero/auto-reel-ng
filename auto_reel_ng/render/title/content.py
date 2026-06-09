"""Title-card text content: what the card says, composed from plan data (D-E).

The movie's first/default card composes its text from the event ``metadata``
(title, date, location, description); a non-default chapter's card uses the
chapter name as its heading. Location carries auto-reel's Swedish ``Plats:`` form.
The composed lines are exposed as a pure function so layout can be asserted
structurally without rendering an image.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from ...event.plan import RenderPlan, ResolvedChapter
from ...reel.document import DEFAULT_CHAPTER_NAME

#: Swedish label prefixed to the event location on the card.
LOCATION_LABEL = "Plats"


@dataclass(frozen=True)
class TitleCardContent:
    """The text a card displays: a heading plus optional date/location/description."""

    heading: str
    date: Optional[date] = None
    location: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug/golden logging."""
        return {
            "heading": self.heading,
            "date": self.date.isoformat() if self.date else None,
            "location": self.location,
            "description": self.description,
        }


def format_date(value: date) -> str:
    """Format a card date deterministically (ISO ``YYYY-MM-DD``)."""
    return value.isoformat()


def format_location(value: str) -> str:
    """Format the location the Swedish ``Plats: <location>`` way auto-reel used."""
    return f"{LOCATION_LABEL}: {value}"


def title_card_lines(content: TitleCardContent) -> list[str]:
    """Return the ordered, non-empty display lines for ``content``.

    Heading first (the event title or the chapter name), then the formatted date,
    the ``Plats:``-prefixed location, and the description — each included only when
    present. Pango wraps each line within the card column; no manual positioning.
    """
    lines: list[str] = []
    if content.heading:
        lines.append(content.heading)
    if content.date is not None:
        lines.append(format_date(content.date))
    if content.location:
        lines.append(format_location(content.location))
    if content.description:
        lines.append(content.description)
    return lines


def compose_content(plan: RenderPlan, chapter: ResolvedChapter) -> TitleCardContent:
    """Compose the card content for ``chapter`` from the plan (decision **D-E**).

    The default chapter draws title/date/location/description from the event
    metadata; any other chapter uses its own name as the heading and carries no
    event sub-text (the opening card already showed it).
    """
    if chapter.name == DEFAULT_CHAPTER_NAME:
        meta = plan.metadata
        return TitleCardContent(
            heading=meta.title or "",
            date=meta.date,
            location=meta.location,
            description=meta.description,
        )
    return TitleCardContent(heading=chapter.name)


__all__ = [
    "TitleCardContent",
    "title_card_lines",
    "compose_content",
    "format_date",
    "format_location",
    "LOCATION_LABEL",
]
