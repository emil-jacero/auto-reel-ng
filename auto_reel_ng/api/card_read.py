"""The event detail's title-card facts: each chapter's resolved card and the event's style.

Read-only and probe-free. Every value comes from the engine's own functions
(:func:`~auto_reel_ng.render.title.resolve_card` over the resolved plan); nothing here decides
what a card looks like.
"""

from __future__ import annotations

from typing import List, Mapping, Optional

from ..errors import TitleCardError
from ..event.plan import ResolvedChapter
from ..event.resolution import resolve
from ..reel import ReelDocument
from ..render.title import TitleCardConfig, resolve_card, resolve_card_config
from .schemas import ChapterOut, ResolvedCardOut, TitleStyleOut


def style_out(config: TitleCardConfig) -> TitleStyleOut:
    return TitleStyleOut(
        duration=config.duration,
        background=config.background,
        font_family=config.resolved_family,
        title_font_size=config.title_font_size,
        subtitle_font_size=config.subtitle_font_size,
        text_color=config.text_color,
        position=config.position,
    )


def with_cards(
    resolved: ReelDocument,
    look_defaults: Mapping[str, object],
    chapters: List[ChapterOut],
) -> tuple[List[ChapterOut], Optional[TitleStyleOut], Optional[str]]:
    """Each chapter's resolved card and the event's card style, from the engine's own functions.

    Read-only and probe-free: the document resolves to a plan, :func:`resolve_card` yields what
    a render draws for each chapter, and the event-wide layer is the same resolution with no
    chapter overrides. An event-wide style the engine refuses leaves every card ``null`` with the
    error; a chapter whose own card cannot be resolved has ``card: null`` and a ``card_error``.
    Nothing is defaulted in place of a card that cannot be resolved.
    """
    plan = resolve(resolved, look_defaults=look_defaults)
    try:
        style = resolve_card_config(plan.look.get("title_card"), None)
    except TitleCardError as exc:
        return chapters, None, str(exc)
    by_name = {chapter.name: chapter for chapter in plan.chapters}
    described: List[ChapterOut] = []
    for chapter in chapters:
        try:
            request = resolve_card(plan, by_name.get(chapter.name) or ResolvedChapter(chapter.name))
        except TitleCardError as exc:
            described.append(chapter.model_copy(update={"card_error": str(exc)}))
            continue
        card = style_out(request.config).model_dump()
        described.append(
            chapter.model_copy(
                update={
                    "card": ResolvedCardOut(
                        **card,
                        title=request.content.heading,
                        subtitle=request.content.subtitle,
                    )
                }
            )
        )
    return described, style_out(style), None


__all__ = ["style_out", "with_cards"]
