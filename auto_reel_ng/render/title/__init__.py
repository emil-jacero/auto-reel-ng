"""Title-card capability: typed config, the Cairo+Pango renderer, and the seams.

Importing this package registers the ``title`` decorator and the ``title``
producer (see :mod:`auto_reel_ng.render.title.decorator`). The renderer
(:func:`render_title_card`) is the single swappable seam shared by the pipeline
and the future GUI preview; every ``gi``/Cairo call lives behind it.
"""

from __future__ import annotations

from .config import DEFAULT_FONT_FAMILY, TitleCardConfig, parse_title_card_config
from .content import TitleCardContent, compose_content, title_card_lines
from .decorator import (
    TITLE_PRODUCER,
    TitleCardRequest,
    title_decorator,
    title_producer,
)
from .render import render_title_card

__all__ = [
    "TitleCardConfig",
    "parse_title_card_config",
    "DEFAULT_FONT_FAMILY",
    "TitleCardContent",
    "title_card_lines",
    "compose_content",
    "render_title_card",
    "TitleCardRequest",
    "title_producer",
    "title_decorator",
    "TITLE_PRODUCER",
]
