"""The Cairo + Pango title-card renderer: one swappable seam (decision **D-B**).

``render_title_card`` writes an RGBA PNG sized to the target spec via an ARGB32
Cairo surface, laying out the card text as centered Pango layouts that wrap within
a column (real shaping/wrapping/kerning, fontconfig name-based fonts) — never
auto-reel's relative-offset hand-positioning. Every ``gi``/Cairo call is confined
to this module so the backend never leaks into the pipeline or the GUI, and so the
engine imports light unless a title decorator actually runs.

Fonts come from the bundled set under ``fonts/`` (decision **D-22**): before the first
Pango font map exists the renderer points fontconfig at ``fonts/fonts.conf``, so a host
needs no system font. Font resolution is fail-loud (decision **D-F**): the configured
family is resolved through that fontconfig and a mismatch of family or weight raises
rather than letting Pango silently substitute a different typeface.
"""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...errors import FontResolutionError, TitleCardBackendError, TitleCardError
from .config import TitleCardConfig
from .content import TitleCardContent, title_card_lines
from .fonts import BUNDLED_FONTS, DEFAULT_FONT_FAMILY, configure_fontconfig, fonts_dir

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids importing TargetSpec at runtime
    from ..target import TargetSpec

#: Horizontal margin (px) reserved on each side; the text column wraps within the rest.
_MARGIN = 96

#: The weight a card is drawn at (a weight is not yet selectable in ``look.title_card``).
_CARD_WEIGHT = 400

#: A ``video`` card's soft shadow (``title-card-date-place-shadow``): alpha, offset and blur as
#: fractions of the image height. The colour is the card's ``shadow_color``.
_SOFT_SHADOW_ALPHA = 0.6
_SOFT_SHADOW_OFFSET = 0.004
_SOFT_SHADOW_BLUR = 0.006
#: A blur spreads thin strokes into a faint halo; the blurred coverage is doubled (saturating at
#: full) so the shadow reaches its alpha next to the glyphs and still fades out over the blur.
_SOFT_SHADOW_GAIN = 2


def _load_backend() -> tuple[Any, Any, Any]:
    """Import and return ``(cairo, Pango, PangoCairo)``, or fail loud if unavailable.

    Keeping the import here (not at module import) means the heavy ``gi``/Cairo
    surface only loads when a card is actually rendered, and a host missing the
    libraries gets a typed error naming the missing backend.
    """
    # Intentional lazy imports (decision **D-B**): the heavy gi/Cairo surface only
    # loads when a card actually renders, never at engine import.
    # pylint: disable=import-outside-toplevel
    # The font map is cached by the first call below and fontconfig reads its configuration
    # once, so the bundled fonts.conf has to be in the environment before Pango is used.
    configure_fontconfig()
    try:
        import gi

        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        import cairo
        from gi.repository import Pango, PangoCairo

        return cairo, Pango, PangoCairo
    except (ImportError, ValueError) as exc:  # ValueError: gi.require_version mismatch
        raise TitleCardBackendError(
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


def _resolve_font_or_raise(family: str, weight: int, pango: Any, pangocairo: Any) -> None:
    """Resolve ``family`` at ``weight`` through fontconfig; raise if Pango would substitute it.

    Pango silently substitutes a missing family, and synthesizes a bold when a family has no
    bold file. We load the font and compare the resolved family name (case-insensitively) and
    the weight of the face that loaded with the request; a mismatch fails loud, naming the
    family, the weight and the bundled default (decision **D-F**).
    """
    fontmap = pangocairo.FontMap.get_default()
    context = fontmap.create_context()
    desc = pango.FontDescription()
    desc.set_family(family)
    desc.set_weight(pango.Weight(weight))
    font = context.load_font(desc)
    described = font.describe() if font is not None else None
    resolved = described.get_family() if described is not None else None
    if not resolved or resolved.strip().lower() != family.strip().lower():
        raise FontResolutionError(
            f"font family {family!r} did not resolve through fontconfig "
            f"(got {resolved!r}); the bundled default is {DEFAULT_FONT_FAMILY!r}; "
            f"fonts directory {str(fonts_dir())!r}, FONTCONFIG_FILE={_fontconfig_file()!r} "
            "(it must be set before the process makes its first Pango font map)"
        )
    resolved_weight = int(described.get_weight()) if described is not None else None
    if resolved_weight != weight:
        raise FontResolutionError(
            f"font family {family!r} did not resolve at weight {weight} through fontconfig "
            f"(got weight {resolved_weight}); the font file for that weight is missing from "
            f"{str(fonts_dir())!r}; the bundled default is {DEFAULT_FONT_FAMILY!r}"
        )


def _fontconfig_file() -> str:
    """The ``FONTCONFIG_FILE`` in effect, for an error message."""
    return os.environ.get("FONTCONFIG_FILE", "")


def verify_bundled_fonts() -> None:
    """Check every registered family at every declared weight resolves; raise for the first not.

    Raises :class:`FontResolutionError` naming the family and the weight. The image build and
    the per-font test call it, so a font file that went missing never reaches a render.
    """
    _, pango, pangocairo = _load_backend()
    for font in BUNDLED_FONTS:
        for weight in font.weights:
            _resolve_font_or_raise(font.family, weight, pango, pangocairo)


def _make_layout(  # pylint: disable=too-many-arguments
    ctx: Any, pango: Any, pangocairo: Any, *, family: str, weight: int, size: int, width: int
) -> Any:
    """Build a centered, word-wrapping Pango layout for one text block."""
    layout = pangocairo.create_layout(ctx)
    desc = pango.FontDescription()
    desc.set_family(family)
    desc.set_weight(pango.Weight(weight))
    desc.set_absolute_size(size * pango.SCALE)
    layout.set_font_description(desc)
    layout.set_alignment(pango.Alignment.CENTER)
    layout.set_width(width * pango.SCALE)
    layout.set_wrap(pango.WrapMode.WORD)
    return layout


def render_card_png(
    config: TitleCardConfig, content: TitleCardContent, width: int, height: int
) -> bytes:
    """Render ``content`` to RGBA PNG **bytes** at ``width`` x ``height``.

    A ``black`` card fills the configured background (with its opacity); a ``video`` card skips the
    fill and so is transparent wherever nothing is drawn. The card lays out each display line as a
    centered Pango layout that wraps within the column, and draws an offset drop-shadow and a glyph
    outline under the fill per ``config``. The configured font family is resolved fail-loud before
    any drawing. Needs no destination file, no ffmpeg and no probed target, so a preview and a
    render draw through this one function.
    """
    cairo, pango, pangocairo = _load_backend()
    family = config.resolved_family
    _resolve_font_or_raise(family, _CARD_WEIGHT, pango, pangocairo)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)

    if config.background != "video":
        # A video card is overlaid on footage: its canvas stays fully transparent.
        bg_r, bg_g, bg_b = _parse_color(config.background_color)
        ctx.set_source_rgba(bg_r, bg_g, bg_b, config.background_opacity)
        ctx.paint()

    column = max(1, width - 2 * _MARGIN)
    placed = _place_layouts(ctx, (pango, pangocairo), config, content, column, height)
    soft = config.background == "video" and config.has_shadow
    if soft:
        _draw_soft_shadow(cairo, pangocairo, ctx, config, placed, width, height, column)
    for layout, top in placed:
        _draw_layout(
            ctx, pango, pangocairo, config, layout, width, top, column, hard_shadow=not soft
        )

    buffer = io.BytesIO()
    surface.write_to_png(buffer)
    return buffer.getvalue()


def _place_layouts(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    ctx: Any,
    backend: tuple[Any, Any],
    config: TitleCardConfig,
    content: TitleCardContent,
    column: int,
    height: int,
) -> list[tuple[Any, float]]:
    """Lay out each display line (title size, then subtitle size) and stack them: ``(layout, y)``."""
    pango, pangocairo = backend
    layouts = []
    total_height = 0
    for index, text in enumerate(title_card_lines(content)):
        size = config.title_font_size if index == 0 else config.subtitle_font_size
        layout = _make_layout(
            ctx,
            pango,
            pangocairo,
            family=config.resolved_family,
            weight=_CARD_WEIGHT,
            size=size,
            width=column,
        )
        layout.set_text(text, -1)
        _, logical = layout.get_pixel_extents()
        layouts.append((layout, logical.height))
        total_height += logical.height
    y = _start_y(config.position, height, total_height)
    placed: list[tuple[Any, float]] = []
    for layout, layout_height in layouts:
        placed.append((layout, y))
        y += layout_height
    return placed


def render_title_card(
    config: TitleCardConfig,
    content: TitleCardContent,
    target: "TargetSpec",
    dest: Path,
) -> Path:
    """Render ``content`` to an RGBA PNG at the target resolution and return ``dest``.

    Writes exactly the bytes :func:`render_card_png` returns for the target's width and height.
    """
    dest.write_bytes(render_card_png(config, content, target.width, target.height))
    return dest


def _gaussian_weights(radius: int) -> list[float]:
    """Normalised Gaussian weights for offsets ``-radius..radius`` (sigma = radius / 2)."""
    sigma = max(radius, 1) / 2.0
    raw = [math.exp(-(i * i) / (2.0 * sigma * sigma)) for i in range(-radius, radius + 1)]
    total = sum(raw)
    return [w / total for w in raw]


def _blur_mask(cairo: Any, mask: Any, radius: int) -> Any:
    """Return ``mask`` (an A8 surface) blurred by a separable Gaussian, deterministically.

    Each pass adds shifted, weighted copies of the surface with Cairo's integer-exact ``ADD``
    operator, so the result has no random, locale or thread input and needs no numpy.
    """
    width, height = mask.get_width(), mask.get_height()
    weights = _gaussian_weights(radius)
    source = mask
    for horizontal in (True, False):
        target = cairo.ImageSurface(cairo.FORMAT_A8, width, height)
        tctx = cairo.Context(target)
        tctx.set_operator(cairo.OPERATOR_ADD)
        for index, weight in enumerate(weights):
            shift = index - radius
            tctx.set_source_surface(source, shift if horizontal else 0, 0 if horizontal else shift)
            tctx.paint_with_alpha(weight * (1 if horizontal else _SOFT_SHADOW_GAIN))
        source = target
    return source


def _draw_soft_shadow(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    cairo: Any,
    pangocairo: Any,
    ctx: Any,
    config: TitleCardConfig,
    placed: list[tuple[Any, float]],
    width: int,
    height: int,
    column: int,
) -> None:
    """Draw the blurred drop shadow of every placed layout under the text (``video`` cards)."""
    offset = round(_SOFT_SHADOW_OFFSET * height)
    radius = max(1, round(_SOFT_SHADOW_BLUR * height))
    # Only the band of rows the text and its blurred shadow can touch is blurred (a speed-up
    # that changes no pixel: everything outside it is transparent either way).
    reach = offset + 2 * radius + 2
    top_row = max(0, int(min(top for _, top in placed)) - reach)
    bottom_row = min(
        height,
        int(max(top + layout.get_pixel_extents()[1].height for layout, top in placed)) + reach + 1,
    )
    mask = cairo.ImageSurface(cairo.FORMAT_A8, width, max(1, bottom_row - top_row))
    mctx = cairo.Context(mask)
    mctx.set_source_rgba(0.0, 0.0, 0.0, 1.0)
    x = (width - column) / 2.0
    for layout, top in placed:
        mctx.move_to(x + offset, top + offset - top_row)
        pangocairo.layout_path(mctx, layout)
        mctx.fill()
    blurred = _blur_mask(cairo, mask, radius)
    sr, sg, sb = _parse_color(config.shadow_color)
    ctx.set_source_rgba(sr, sg, sb, _SOFT_SHADOW_ALPHA)
    ctx.mask_surface(blurred, 0, top_row)


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
    *,
    hard_shadow: bool = True,
) -> None:
    """Draw one layout (shadow, outline, fill) centered horizontally at ``y``.

    ``hard_shadow`` False skips the offset shadow (a ``video`` card draws its soft one first).
    """
    del pango  # symmetry with _make_layout's signature; not needed here
    x = (canvas_width - column) / 2.0

    if hard_shadow and config.has_shadow:
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


__all__ = ["render_card_png", "render_title_card", "verify_bundled_fonts"]
