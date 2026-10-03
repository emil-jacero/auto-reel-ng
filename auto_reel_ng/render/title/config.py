"""Typed title-card config parsed from the opaque ``look.title_card`` sub-map.

Decision **D-G**: ``reel-document`` keeps carrying ``look`` opaquely; the typed
:class:`TitleCardConfig` is parsed here at render time, exactly as
``look.decorators`` / ``look.target_resolution`` are already consumed. Absent
fields take documented defaults (auto-reel's 7s duration / 2s fades); a malformed
value fails loud with a typed error naming the field rather than rendering with a
guessed value (decision: fail loud / never fabricate).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ...errors import TitleCardError
from ...reel.card import CARD_BACKGROUNDS, CARD_POSITIONS, ChapterCard
from .fonts import DEFAULT_FONT_FAMILY, font_for, registered_families

#: Documented defaults carried over from auto-reel when ``look.title_card`` is silent.
DEFAULT_DURATION = 7.0
DEFAULT_FADE_IN = 2.0
DEFAULT_FADE_OUT = 2.0
DEFAULT_TITLE_FONT_SIZE = 96
DEFAULT_SUBTITLE_FONT_SIZE = 48
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_OUTLINE_COLOR = "#000000"
DEFAULT_OUTLINE_WIDTH = 2.0
DEFAULT_SHADOW_COLOR = "#000000"
DEFAULT_SHADOW_OFFSET = 3
DEFAULT_SHADOW_OPACITY = 0.5
DEFAULT_BACKGROUND_COLOR = "#000000"
DEFAULT_BACKGROUND_OPACITY = 1.0
DEFAULT_POSITION = "center"
DEFAULT_BACKGROUND = "black"

#: Text positions the renderer understands (the set the document's ``card.position`` takes).
_POSITIONS = frozenset(CARD_POSITIONS)

#: The card style keys a chapter's ``card`` overrides; the rest of the card is text.
_CARD_STYLE_KEYS = (
    "duration",
    "background",
    "font_family",
    "title_font_size",
    "subtitle_font_size",
    "text_color",
    "position",
)


@dataclass(frozen=True)
class TitleCardConfig:  # pylint: disable=too-many-instance-attributes
    """Fully-explicit title-card styling, the renderer's only styling input.

    Every field has a documented default so a card renders with an empty
    ``look.title_card``. Combined fades are clamped to ``duration`` at parse time
    so a card never fades for longer than it is shown.
    """

    font_family: Optional[str] = None
    title_font_size: int = DEFAULT_TITLE_FONT_SIZE
    subtitle_font_size: int = DEFAULT_SUBTITLE_FONT_SIZE
    text_color: str = DEFAULT_TEXT_COLOR
    outline_color: str = DEFAULT_OUTLINE_COLOR
    outline_width: float = DEFAULT_OUTLINE_WIDTH
    shadow_color: str = DEFAULT_SHADOW_COLOR
    shadow_offset: int = DEFAULT_SHADOW_OFFSET
    shadow_opacity: float = DEFAULT_SHADOW_OPACITY
    background_color: str = DEFAULT_BACKGROUND_COLOR
    background_opacity: float = DEFAULT_BACKGROUND_OPACITY
    fade_in: float = DEFAULT_FADE_IN
    fade_out: float = DEFAULT_FADE_OUT
    duration: float = DEFAULT_DURATION
    position: str = DEFAULT_POSITION
    #: ``black`` (text on a colour fill) or ``video`` (text over the chapter's first clip).
    background: str = DEFAULT_BACKGROUND

    @property
    def resolved_family(self) -> str:
        """The configured family, falling back to the bundled default."""
        return self.font_family if self.font_family else DEFAULT_FONT_FAMILY

    @property
    def has_shadow(self) -> bool:
        """True when a drop-shadow should be drawn."""
        return self.shadow_offset != 0 and self.shadow_opacity > 0.0

    @property
    def has_outline(self) -> bool:
        """True when a glyph outline should be stroked."""
        return self.outline_width > 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug/golden logging."""
        return {
            "font_family": self.font_family,
            "title_font_size": self.title_font_size,
            "subtitle_font_size": self.subtitle_font_size,
            "text_color": self.text_color,
            "outline_color": self.outline_color,
            "outline_width": self.outline_width,
            "shadow_color": self.shadow_color,
            "shadow_offset": self.shadow_offset,
            "shadow_opacity": self.shadow_opacity,
            "background_color": self.background_color,
            "background_opacity": self.background_opacity,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "duration": self.duration,
            "position": self.position,
            "background": self.background,
        }


def _require(mapping: Mapping[str, Any], key: str, kind: type, *, default: Any) -> Any:
    """Return ``mapping[key]`` coerced to ``kind``, or ``default`` when absent.

    A present value of the wrong type (or one that cannot coerce) fails loud with a
    typed error naming the field, rather than being silently ignored.
    """
    if key not in mapping or mapping[key] is None:
        return default
    raw = mapping[key]
    if kind is float and isinstance(raw, bool):
        raise TitleCardError(f"look.title_card.{key} must be a number, got {raw!r}")
    if kind is int and isinstance(raw, bool):
        raise TitleCardError(f"look.title_card.{key} must be an integer, got {raw!r}")
    try:
        if kind is float:
            return float(raw)
        if kind is int:
            return int(raw)
        if kind is str:
            if not isinstance(raw, str):
                raise TypeError
            return raw
    except (TypeError, ValueError) as exc:
        raise TitleCardError(
            f"look.title_card.{key} must be a {kind.__name__}, got {raw!r}"
        ) from exc
    return raw  # pragma: no cover - kind is always one of the three above


def _parse_font_family(raw: Mapping[str, Any]) -> Optional[str]:
    """The configured family in the registry's spelling, or ``None`` (the default)."""
    value = _require(raw, "font_family", str, default=None)
    if value is None:
        return None
    try:
        return font_for(value).family
    except TitleCardError as exc:
        raise TitleCardError(
            f"look.title_card.font_family {value!r} is not a bundled font family; "
            f"use one of: {', '.join(registered_families())}"
        ) from exc


def parse_title_card_config(raw: Optional[Mapping[str, Any]]) -> TitleCardConfig:
    """Parse a :class:`TitleCardConfig` from the opaque ``look.title_card`` sub-map.

    Absent fields take their documented defaults; a malformed value fails loud.
    The combined fade durations are clamped so their sum never exceeds the card
    duration (a card never fades for longer than it is shown).
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise TitleCardError(f"look.title_card must be a mapping, got {raw!r}")

    position = _require(raw, "position", str, default=DEFAULT_POSITION)
    if position not in _POSITIONS:
        raise TitleCardError(
            f"look.title_card.position must be one of {sorted(_POSITIONS)}, got {position!r}"
        )

    background = _require(raw, "background", str, default=DEFAULT_BACKGROUND)
    if background not in CARD_BACKGROUNDS:
        raise TitleCardError(
            f"look.title_card.background must be one of {list(CARD_BACKGROUNDS)}, "
            f"got {background!r}"
        )

    duration = _require(raw, "duration", float, default=DEFAULT_DURATION)
    fade_in = _require(raw, "fade_in", float, default=DEFAULT_FADE_IN)
    fade_out = _require(raw, "fade_out", float, default=DEFAULT_FADE_OUT)
    fade_in, fade_out = _clamp_fades(fade_in, fade_out, duration)

    return TitleCardConfig(
        font_family=_parse_font_family(raw),
        title_font_size=_require(raw, "title_font_size", int, default=DEFAULT_TITLE_FONT_SIZE),
        subtitle_font_size=_require(
            raw, "subtitle_font_size", int, default=DEFAULT_SUBTITLE_FONT_SIZE
        ),
        text_color=_require(raw, "text_color", str, default=DEFAULT_TEXT_COLOR),
        outline_color=_require(raw, "outline_color", str, default=DEFAULT_OUTLINE_COLOR),
        outline_width=_require(raw, "outline_width", float, default=DEFAULT_OUTLINE_WIDTH),
        shadow_color=_require(raw, "shadow_color", str, default=DEFAULT_SHADOW_COLOR),
        shadow_offset=_require(raw, "shadow_offset", int, default=DEFAULT_SHADOW_OFFSET),
        shadow_opacity=_require(raw, "shadow_opacity", float, default=DEFAULT_SHADOW_OPACITY),
        background_color=_require(raw, "background_color", str, default=DEFAULT_BACKGROUND_COLOR),
        background_opacity=_require(
            raw, "background_opacity", float, default=DEFAULT_BACKGROUND_OPACITY
        ),
        fade_in=fade_in,
        fade_out=fade_out,
        duration=duration,
        position=position,
        background=background,
    )


def resolve_card_config(
    look_title_card: Optional[Mapping[str, Any]], card: Optional[ChapterCard]
) -> TitleCardConfig:
    """A card's effective config: defaults, then ``look.title_card``, then the card's overrides.

    The layers are overlaid as raw mappings and parsed once, so every rule of
    :func:`parse_title_card_config` applies to the result and the fades are clamped against
    the final duration (not against an earlier layer's).
    """
    if look_title_card is not None and not isinstance(look_title_card, Mapping):
        raise TitleCardError(f"look.title_card must be a mapping, got {look_title_card!r}")
    layered: dict[str, Any] = dict(look_title_card) if look_title_card is not None else {}
    if card is not None:
        for key in _CARD_STYLE_KEYS:
            value = getattr(card, key)
            if value is not None:
                layered[key] = value
    return parse_title_card_config(layered)


def _clamp_fades(fade_in: float, fade_out: float, duration: float) -> tuple[float, float]:
    """Scale the fades so their sum does not exceed ``duration`` (decision: clamp)."""
    total = fade_in + fade_out
    if total <= duration or total <= 0.0:
        return fade_in, fade_out
    scale = duration / total
    return fade_in * scale, fade_out * scale


__all__ = [
    "DEFAULT_FONT_FAMILY",
    "DEFAULT_DURATION",
    "DEFAULT_FADE_IN",
    "DEFAULT_FADE_OUT",
    "DEFAULT_BACKGROUND",
    "TitleCardConfig",
    "parse_title_card_config",
    "resolve_card_config",
]
