"""The Cairo + Pango title-card renderer: one swappable seam (decision **D-B**).

``render_title_card`` writes an RGBA PNG sized to the target spec via an ARGB32
Cairo surface, laying out the card text as centered Pango layouts that wrap within
a column (real shaping/wrapping/kerning, fontconfig name-based fonts) — never
auto-reel's relative-offset hand-positioning. Every ``gi``/Cairo call is confined
to this module so the backend never leaks into the pipeline or the GUI, and so the
engine imports light unless a title decorator actually runs.

Font resolution is fail-loud (decision **D-F**): the configured family is resolved
through fontconfig and a mismatch raises rather than letting Pango silently
substitute a different typeface.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...errors import FontResolutionError, TitleCardError
from .config import DEFAULT_FONT_FAMILY, TitleCardConfig
from .content import TitleCardContent, title_card_lines

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids importing TargetSpec at runtime
    from ..target import TargetSpec

#: Horizontal margin (px) reserved on each side; the text column wraps within the rest.
_MARGIN = 96


def _load_backend() -> tuple[Any, Any, Any]:
    """Import and return ``(cairo, Pango, PangoCairo)``, or fail loud if unavailable.

    Keeping the import here (not at module import) means the heavy ``gi``/Cairo
    surface only loads when a card is actually rendered, and a host missing the
    libraries gets a typed error naming the missing backend.
    """
    # Intentional lazy imports (decision **D-B**): the heavy gi/Cairo surface only
    # loads when a card actually renders, never at engine import.
    # pylint: disable=import-outside-toplevel
    try:
        import gi

        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        import cairo
        from gi.repository import Pango, PangoCairo

        return cairo, Pango, PangoCairo
    except (ImportError, ValueError) as exc:  # ValueError: gi.require_version mismatch
        raise TitleCardError(
            "title-card rendering requires Cairo + Pango (pycairo + PyGObject) and the "
            "Pango GObject-introspection typelib; none usable on this host"
        ) from exc


def _parse_color(value: str) -> tuple[float, float, float]:
    """Parse ``#RRGGBB`` or a small set of named colors into RGB floats in [0, 1]."""
    named = {
        "black": (0.0, 0.0, 0.0),
        "white": (1.0, 1.0, 1.0),
        "red": (1.0, 0.0, 0.0),
        "green": (0.0, 1.0, 0.0),
        "blue": (0.0, 0.0, 1.0),
    }
    key = value.strip().lower()
    if key in named:
        return named[key]
    hexstr = key.lstrip("#")
    if len(hexstr) == 6:
        try:
            r, g, b = (int(hexstr[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
            return r, g, b
        except ValueError:
            pass
    raise TitleCardError(f"unrecognized color {value!r}; use #RRGGBB or a named color")


def _resolve_font_or_raise(family: str, pango: Any, pangocairo: Any) -> None:
    """Resolve ``family`` through fontconfig; raise if Pango would substitute it.

    Pango silently substitutes a missing family. We load the font and compare the
    resolved family name to the requested one (case-insensitively); a mismatch
    fails loud, naming the family and the bundled default (decision **D-F**).
    """
    fontmap = pangocairo.FontMap.get_default()
    context = fontmap.create_context()
    desc = pango.FontDescription()
    desc.set_family(family)
    font = context.load_font(desc)
    resolved = font.describe().get_family() if font is not None else None
    if not resolved or resolved.strip().lower() != family.strip().lower():
        raise FontResolutionError(
            f"font family {family!r} did not resolve through fontconfig "
            f"(got {resolved!r}); the bundled default is {DEFAULT_FONT_FAMILY!r}"
        )


def _make_layout(
    ctx: Any, pango: Any, pangocairo: Any, *, family: str, size: int, width: int
) -> Any:
    """Build a centered, word-wrapping Pango layout for one text block."""
    layout = pangocairo.create_layout(ctx)
    desc = pango.FontDescription()
    desc.set_family(family)
    desc.set_absolute_size(size * pango.SCALE)
    layout.set_font_description(desc)
    layout.set_alignment(pango.Alignment.CENTER)
    layout.set_width(width * pango.SCALE)
    layout.set_wrap(pango.WrapMode.WORD)
    return layout


def render_title_card(
    config: TitleCardConfig,
    content: TitleCardContent,
    target: "TargetSpec",
    dest: Path,
) -> Path:
    """Render ``content`` to an RGBA PNG at the target resolution and return ``dest``.

    The card fills the configured background, lays out each display line as a
    centered Pango layout that wraps within the column, and draws an offset
    drop-shadow and a glyph outline under the fill per ``config``. The configured
    font family is resolved fail-loud before any drawing.
    """
    cairo, pango, pangocairo = _load_backend()
    family = config.resolved_family
    _resolve_font_or_raise(family, pango, pangocairo)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, target.width, target.height)
    ctx = cairo.Context(surface)

    bg_r, bg_g, bg_b = _parse_color(config.background_color)
    ctx.set_source_rgba(bg_r, bg_g, bg_b, config.background_opacity)
    ctx.paint()

    column = max(1, target.width - 2 * _MARGIN)
    lines = title_card_lines(content)
    layouts = []
    total_height = 0
    for index, text in enumerate(lines):
        size = config.title_font_size if index == 0 else config.subtitle_font_size
        layout = _make_layout(ctx, pango, pangocairo, family=family, size=size, width=column)
        layout.set_text(text, -1)
        _, logical = layout.get_pixel_extents()
        layouts.append((layout, logical.height))
        total_height += logical.height

    y = _start_y(config.position, target.height, total_height)
    for layout, height in layouts:
        _draw_layout(ctx, pango, pangocairo, config, layout, target.width, y, column)
        y += height

    surface.write_to_png(str(dest))
    return dest


def _start_y(position: str, canvas_height: int, block_height: int) -> float:
    """Vertical start offset of the text block for the configured position."""
    if position == "top":
        return float(_MARGIN)
    if position == "bottom":
        return float(canvas_height - block_height - _MARGIN)
    return max(0.0, (canvas_height - block_height) / 2.0)


def _draw_layout(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    ctx: Any,
    pango: Any,
    pangocairo: Any,
    config: TitleCardConfig,
    layout: Any,
    canvas_width: int,
    y: float,
    column: int,
) -> None:
    """Draw one layout (shadow, outline, fill) centered horizontally at ``y``."""
    del pango  # symmetry with _make_layout's signature; not needed here
    x = (canvas_width - column) / 2.0

    if config.has_shadow:
        sr, sg, sb = _parse_color(config.shadow_color)
        ctx.set_source_rgba(sr, sg, sb, config.shadow_opacity)
        ctx.move_to(x + config.shadow_offset, y + config.shadow_offset)
        pangocairo.layout_path(ctx, layout)
        ctx.fill()

    if config.has_outline:
        orr, og, ob = _parse_color(config.outline_color)
        ctx.set_source_rgb(orr, og, ob)
        ctx.set_line_width(config.outline_width)
        ctx.move_to(x, y)
        pangocairo.layout_path(ctx, layout)
        ctx.stroke()

    tr, tg, tb = _parse_color(config.text_color)
    ctx.set_source_rgb(tr, tg, tb)
    ctx.move_to(x, y)
    pangocairo.show_layout(ctx, layout)


__all__ = ["render_title_card"]
