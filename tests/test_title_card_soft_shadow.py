"""The video card's soft shadow (``title-card-date-place-shadow``): look, determinism, contrast.

Drawn through the one renderer seam, so a preview and a render show the same bytes. Needs the
bundled fonts and Cairo/Pango (``has_fonts``).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from pathlib import Path

import cairo
import pytest

from auto_reel_ng.render.target import TargetSpec
from auto_reel_ng.render.title import (
    TitleCardContent,
    parse_title_card_config,
    render_card_png,
    render_title_card,
)

pytestmark = pytest.mark.has_fonts

CONTENT = TitleCardContent("Midsommar", "2024-08-20\nPlats: Tjörn")

#: sha256 of the black card below as the release before this change rendered it (the old path).
BLACK_BEFORE = "369cb8b8a9ef00423553011adfcbab63f10c3c43df4c564a8792e128ddc27b6a"

W, H = 1920, 1080


def _config(**look: object):
    return parse_title_card_config({"background": "video", **look})


def _pixels(png: bytes) -> tuple[bytes, int]:
    import io

    surface = cairo.ImageSurface.create_from_png(io.BytesIO(png))
    return bytes(surface.get_data()), surface.get_stride()


def _alpha(png: bytes) -> list[list[int]]:
    data, stride = _pixels(png)
    return [[data[y * stride + x * 4 + 3] for x in range(W)] for y in range(H)]


def _without_shadow(**look: object) -> bytes:
    return render_card_png(_config(shadow_opacity=0.0, **look), CONTENT, W, H)


def test_a_black_card_is_byte_identical_to_the_release_before() -> None:
    config = parse_title_card_config({"background": "black"})
    png = render_card_png(config, CONTENT, W, H)
    assert hashlib.sha256(png).hexdigest() == BLACK_BEFORE


def test_a_video_card_differs_from_the_same_card_without_a_shadow() -> None:
    assert render_card_png(_config(), CONTENT, W, H) != _without_shadow()


def test_two_renders_in_separate_processes_are_byte_identical() -> None:
    code = (
        "import hashlib\n"
        "from auto_reel_ng.render.title import *\n"
        "c=parse_title_card_config({'background':'video'})\n"
        "t=TitleCardContent('Midsommar','2024-08-20\\nPlats: Tjörn')\n"
        "print(hashlib.sha256(render_card_png(c,t,1920,1080)).hexdigest())\n"
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        ).stdout.strip()
        for _ in range(2)
    }
    assert len(runs) == 1
    assert runs == {hashlib.sha256(render_card_png(_config(), CONTENT, W, H)).hexdigest()}


def test_the_file_entry_point_writes_the_same_bytes(tmp_path: Path) -> None:
    target = TargetSpec(
        width=W, height=H, fps=30.0, video_codec="h264", video_encoder="libx264",
        pix_fmt="yuv420p", sample_aspect_ratio="1:1", fill_color="black",
        audio_codec="aac", audio_sample_rate=48000, audio_channels=2,
    )  # fmt: skip
    dest = render_title_card(_config(), CONTENT, target, tmp_path / "card.png")
    assert dest.read_bytes() == render_card_png(_config(), CONTENT, W, H)


def test_the_corners_stay_fully_transparent() -> None:
    alpha = _alpha(render_card_png(_config(), CONTENT, W, H))
    assert (alpha[0][0], alpha[0][W - 1], alpha[H - 1][0], alpha[H - 1][W - 1]) == (0, 0, 0, 0)


def test_no_shadow_opacity_draws_no_shadow_pixels() -> None:
    off = _alpha(_without_shadow())
    glyph = {(y, x) for y in range(H) for x in range(W) if off[y][x]}
    assert glyph  # the text itself is there
    assert max(max(row) for row in off) == 255
    # every non-zero pixel of the shadowless card is text or its outline: none reaches 4 px
    # beyond a fully opaque pixel, where the soft shadow would still be drawing
    shadowed = _alpha(render_card_png(_config(), CONTENT, W, H))
    extra = sum(1 for y in range(H) for x in range(W) if shadowed[y][x] and not off[y][x])
    assert extra > 1000
    assert all(not off[y][x] for y, x in ((10, 10), (H - 10, W - 10)))


def test_the_shadow_falls_off_softly_over_several_pixels() -> None:
    off = _alpha(_without_shadow())
    on = _alpha(render_card_png(_config(), CONTENT, W, H))
    # a horizontal run through the heading, right of its last glyph: the shadow alpha
    # profile away from text (where the shadowless card is 0) climbs/falls in small steps
    rows = [y for y in range(H) if max(off[y]) == 255]
    y = rows[len(rows) // 4]
    right = max(x for x in range(W) if off[y][x])
    profile = [on[y][x] for x in range(right + 1, min(W, right + 24)) if not off[y][x]]
    nonzero = [v for v in profile if v]
    assert len(nonzero) >= 5, "the shadow extends several pixels past the glyph"
    assert max(nonzero) <= round(255 * 0.6) + 1  # never harder than 60 % alpha
    steps = [abs(a - b) for a, b in zip(profile, profile[1:])]
    assert max(steps) < 0.6 * 255 * 0.5  # no hard edge: no single step takes half the range


def test_the_shadow_stays_within_the_blur_reach_of_the_offset_glyphs() -> None:
    off = _alpha(_without_shadow())
    on = _alpha(render_card_png(_config(), CONTENT, W, H))
    reach = round(0.004 * H) + 2 * round(0.006 * H) + 2
    ys = [y for y in range(H) if any(off[y])]
    xs = [x for x in range(W) if any(off[y][x] for y in range(H))]
    shadow_ys = [y for y in range(H) if any(on[y])]
    shadow_xs = [x for x in range(W) if any(on[y][x] for y in range(H))]
    assert min(ys) - reach <= min(shadow_ys) <= min(ys)
    assert max(ys) <= max(shadow_ys) <= max(ys) + reach
    assert min(xs) - reach <= min(shadow_xs) and max(shadow_xs) <= max(xs) + reach


def test_a_1080p_soft_shadow_card_renders_quickly() -> None:
    render_card_png(_config(), CONTENT, W, H)  # warm the font map
    started = time.perf_counter()
    render_card_png(_config(), CONTENT, W, H)
    took = time.perf_counter() - started
    print(f"soft-shadow 1080p render: {took * 1000:.0f} ms")
    assert took < 0.5


def _composite_over(png: bytes, frame_luma: int) -> list[list[float]]:
    """Luminance (0..255) of the card composited over a flat grey frame."""
    data, stride = _pixels(png)
    out = []
    for y in range(H):
        row = []
        for x in range(W):
            b, g, r, a = data[y * stride + x * 4 : y * stride + x * 4 + 4]  # premultiplied BGRA
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            row.append(luma + frame_luma * (255 - a) / 255)
        out.append(row)
    return out


def _wcag(l1: float, l2: float) -> float:
    def rel(v: float) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    hi, lo = sorted((rel(l1), rel(l2)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_white_text_is_readable_over_a_bright_frame_with_the_shadow() -> None:
    frame = 235  # a bright, light-grey frame
    off_png = _without_shadow()
    off = _alpha(off_png)
    on_luma = _composite_over(render_card_png(_config(), CONTENT, W, H), frame)
    off_luma = _composite_over(off_png, frame)
    # the band 1 to 3 px outside the glyphs: no text pixel there; the shadowless card shows the
    # bare frame. (At 4 to 10 px a 60 % blurred shadow has mostly faded: see the printed profile.)
    band = [
        (y, x)
        for y in range(3, H - 3)
        for x in range(3, W - 3, 2)
        if off[y][x] == 0
        and any(off[y + dy][x + dx] == 255 for dy in (-3, 0, 3) for dx in (-3, 0, 3))
    ]
    mean_on = sum(on_luma[y][x] for y, x in band) / len(band)
    mean_off = sum(off_luma[y][x] for y, x in band) / len(band)
    print(f"band luminance without shadow {mean_off:.1f}, with {mean_on:.1f}")
    assert mean_off == pytest.approx(frame, abs=1)
    assert _wcag(255, mean_off) < 1.5
    assert _wcag(255, mean_on) >= 2.0 and mean_on < mean_off - 50
    # far from the text nothing changes
    far = (5, 5)
    assert on_luma[far[0]][far[1]] == off_luma[far[0]][far[1]] == frame


def test_shadow_opacity_scales_the_soft_shadow() -> None:
    def peak_extra(opacity: float) -> int:
        off = _alpha(_without_shadow())
        on = _alpha(render_card_png(_config(shadow_opacity=opacity), CONTENT, W, H))
        return max(on[y][x] for y in range(H) for x in range(W) if not off[y][x])

    assert peak_extra(0.25) < peak_extra(0.5)
