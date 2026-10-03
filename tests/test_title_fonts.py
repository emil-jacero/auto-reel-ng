"""The bundled title-card fonts: the registry, the files, the engine's fontconfig, a render per font.

The registry and file checks need neither Cairo nor any font installed. Everything that draws is
marked ``has_fonts`` and runs against the repository's own ``fonts/`` (the engine's fontconfig), so
it runs on a host with no system font. Anything that depends on the process's first Pango font map
runs in a fresh subprocess, because that map is cached for the life of the process.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.errors import FontResolutionError, TitleCardError
from auto_reel_ng.render.title.fonts import (
    BUNDLED_FONTS,
    DEFAULT_FONT_FAMILY,
    FONTS_CONF_NAME,
    FONTS_DIR_ENV,
    ROLES,
    configure_fontconfig,
    font_for,
    fonts_dir,
    registered_families,
)

FONTS = Path(__file__).resolve().parents[1] / "fonts"
SWEDISH = "Åsa, Örjan och Märta åt smörgås på café"
#: The Latin Extended-A letters of the Polish, Czech, Slovak, Hungarian, Croatian, Slovenian, Romanian,
#: Turkish, Latvian, Lithuanian and Estonian alphabets, and French Œ and Ÿ (not the whole block:
#: Esperanto, Maltese and the ligature Ĳ are missing from most families).
CENTRAL_EUROPEAN = "ĄąĆćĘęŁłŃńŚśŹźŻżČčĎďĚěŇňŘřŠšŤťŮůŽžĹĺĽľŔŕŐőŰűĐđĞğİıŞşĂăĀāĒēĢģĪīĶķĻļŅņŪūĖėĮįŲųŒœŸ"
_MAX_FONTS_BYTES = 8 * 1024 * 1024
#: Pango's own virtual families, which resolve to a bundled font here.
_PANGO_GENERIC_FAMILIES = {"Sans", "Serif", "Monospace", "System-ui"}
_FONT_SUFFIXES = {".ttf", ".otf", ".ttc", ".woff", ".woff2", ".pfb"}


_TARGET_FIELDS = (
    'video_codec="h264", video_encoder="libx264", pix_fmt="yuv420p", sample_aspect_ratio="1:1", '
    'fill_color="black", audio_codec="aac", audio_sample_rate=48000, audio_channels=2'
)


def _target(width: int, height: int):  # type: ignore[no-untyped-def]
    from auto_reel_ng.render.target import TargetSpec

    return TargetSpec(
        width=width,
        height=height,
        fps=30.0,
        video_codec="h264",
        video_encoder="libx264",
        pix_fmt="yuv420p",
        sample_aspect_ratio="1:1",
        fill_color="black",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
    )


def _run(script: str, *, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    """Run ``script`` in a fresh interpreter (its own Pango font map)."""
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        check=False,
        env=env if env is not None else os.environ.copy(),
        timeout=120,
    )


def _fresh_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    """An environment with no FONTCONFIG_FILE and an empty HOME / cache."""
    env = os.environ.copy()
    env.pop("FONTCONFIG_FILE", None)
    env.pop(FONTS_DIR_ENV, None)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["XDG_CACHE_HOME"] = str(home / "cache")
    env.update(extra)
    return env


# --------------------------------------------------------------------------- #
# 1. The registry and the files (no fonts, no Cairo needed)                    #
# --------------------------------------------------------------------------- #


def test_nine_families_with_dejavu_sans_first_and_default() -> None:
    assert len(BUNDLED_FONTS) == 9
    assert BUNDLED_FONTS[0].family == "DejaVu Sans"
    assert DEFAULT_FONT_FAMILY == "DejaVu Sans"
    assert registered_families()[0] == DEFAULT_FONT_FAMILY
    assert len(set(registered_families())) == 9


def test_every_role_is_filled_exactly_once() -> None:
    assert [font.role for font in BUNDLED_FONTS] == list(ROLES)
    assert len(ROLES) == 9


def test_every_declared_weight_has_a_file_whose_hash_matches() -> None:
    for font in BUNDLED_FONTS:
        assert font.weights == tuple(sorted(set(font.weights))), font.family
        for file in font.files:
            path = FONTS / file.path
            assert path.is_file(), f"{font.family} {file.weight}: {file.path} is missing"
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == file.sha256, (
                f"{file.path} changed ({digest}); a bundled font is a render input the "
                "fingerprint cannot see: record the new hash in the registry AND bump "
                "RENDER_GRAPH_VERSION in staleness/fingerprint.py"
            )


def test_weights_follow_the_files_that_exist() -> None:
    by_family = {font.family: font.weights for font in BUNDLED_FONTS}
    assert by_family["Pacifico"] == (400,)
    assert by_family["DM Serif Display"] == (400,)
    assert by_family["Inter"] == (400, 700)


def test_no_font_file_in_the_directory_is_unregistered() -> None:
    registered = {file.path for font in BUNDLED_FONTS for file in font.files}
    on_disk = {
        path.relative_to(FONTS).as_posix()
        for path in FONTS.rglob("*")
        if path.is_file() and path.suffix.lower() in _FONT_SUFFIXES
    }
    assert on_disk == registered


def test_every_family_ships_a_txt_license_and_ofl_ones_say_so() -> None:
    for font in BUNDLED_FONTS:
        assert font.license_file.endswith(".txt"), font.family
        text = (FONTS / font.license_file).read_text(encoding="utf-8")
        if font.family == "DejaVu Sans":
            assert "Bitstream Vera" in text
            assert "DejaVu" in font.license
        else:
            assert "SIL OPEN FONT LICENSE" in text.upper(), font.family
            assert "SIL Open Font License" in font.license


def test_the_fonts_directory_stays_within_its_budget() -> None:
    total = sum(path.stat().st_size for path in FONTS.rglob("*") if path.is_file())
    assert total <= _MAX_FONTS_BYTES, f"fonts/ is {total} bytes, over the 8 MB budget"


def test_fonts_conf_lists_only_its_own_directory() -> None:
    root = ET.parse(FONTS / FONTS_CONF_NAME).getroot()
    dirs = root.findall("dir")
    assert [(d.text, d.get("prefix")) for d in dirs] == [(".", "relative")]
    assert root.findall("include") == [] and root.findall("includedir") == []
    assert [(c.text, c.get("prefix")) for c in root.findall("cachedir")] == [
        ("auto-reel/fontconfig", "xdg")
    ]


def test_lookup_ignores_case_and_returns_the_canonical_entry() -> None:
    assert font_for("dejavu sans") is BUNDLED_FONTS[0]
    assert font_for("  BARLOW CONDENSED ").family == "Barlow Condensed"


def test_an_unknown_family_names_itself_and_the_choices() -> None:
    with pytest.raises(FontResolutionError) as excinfo:
        font_for("Comic Sans")
    message = str(excinfo.value)
    assert "Comic Sans" in message
    for family in registered_families():
        assert family in message


def test_the_registry_imports_with_the_drawing_backend_blocked() -> None:
    result = _run("""
        import sys
        sys.modules["gi"] = None
        sys.modules["cairo"] = None
        from auto_reel_ng.render.title.fonts import registered_families
        print(len(registered_families()))
        """)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "9"


# --------------------------------------------------------------------------- #
# 2. The engine's own fontconfig                                               #
# --------------------------------------------------------------------------- #


def test_fonts_dir_defaults_to_the_checkout_and_honors_the_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(FONTS_DIR_ENV, raising=False)
    assert fonts_dir() == FONTS
    monkeypatch.setenv(FONTS_DIR_ENV, str(tmp_path))
    assert fonts_dir() == tmp_path


def test_a_directory_without_fonts_conf_raises_naming_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(FONTS_DIR_ENV, str(tmp_path))
    with pytest.raises(TitleCardError, match="fonts.conf") as excinfo:
        configure_fontconfig()
    assert str(tmp_path / FONTS_CONF_NAME) in str(excinfo.value)


def test_a_missing_directory_raises_naming_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "nowhere"
    monkeypatch.setenv(FONTS_DIR_ENV, str(missing))
    with pytest.raises(TitleCardError) as excinfo:
        configure_fontconfig()
    assert str(missing) in str(excinfo.value)


def test_an_inherited_fontconfig_file_is_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FONTS_DIR_ENV, raising=False)
    monkeypatch.setenv("FONTCONFIG_FILE", "/etc/fonts/fonts.conf")
    assert configure_fontconfig() == FONTS / FONTS_CONF_NAME
    assert os.environ["FONTCONFIG_FILE"] == str(FONTS / FONTS_CONF_NAME)


def test_a_second_call_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FONTS_DIR_ENV, raising=False)
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    first = configure_fontconfig()
    environment = dict(os.environ)
    assert configure_fontconfig() == first
    assert dict(os.environ) == environment


# --------------------------------------------------------------------------- #
# 3. Resolution and rendering (need Cairo/Pango; fonts come from fonts/)       #
# --------------------------------------------------------------------------- #


@pytest.mark.has_fonts
def test_every_registered_family_resolves_at_every_declared_weight(has_fonts: None) -> None:
    from auto_reel_ng.render.title import verify_bundled_fonts

    verify_bundled_fonts()


@pytest.mark.has_fonts
def test_an_unregistered_name_raises_rather_than_rendering_in_a_substitute(
    has_fonts: None,
) -> None:
    from auto_reel_ng.render.title import render as render_module

    cairo, pango, pangocairo = render_module._load_backend()  # pylint: disable=protected-access
    del cairo
    with pytest.raises(FontResolutionError, match="Papyrus"):
        render_module._resolve_font_or_raise(  # pylint: disable=protected-access
            "Papyrus", 400, pango, pangocairo
        )


@pytest.mark.has_fonts
def test_a_missing_bold_file_is_named_not_synthesized(has_fonts: None, tmp_path: Path) -> None:
    copy = tmp_path / "fonts"
    shutil.copytree(FONTS, copy)
    (copy / "inter" / "Inter-Bold.ttf").unlink()
    script = """
        from auto_reel_ng.errors import FontResolutionError
        from auto_reel_ng.render.title import render as r, verify_bundled_fonts

        _, pango, pangocairo = r._load_backend()
        r._resolve_font_or_raise("Inter", 400, pango, pangocairo)  # the Regular file is there
        for label, call in (
            ("verify", verify_bundled_fonts),
            ("card", lambda: r._resolve_font_or_raise("Inter", 700, pango, pangocairo)),
        ):
            try:
                call()
            except FontResolutionError as exc:
                print(label, exc)
            else:
                print(label, "NO ERROR")
    """
    result = _run(script, env=_fresh_env(tmp_path, **{FONTS_DIR_ENV: str(copy)}))
    assert result.returncode == 0, result.stderr
    lines = dict(line.split(" ", 1) for line in result.stdout.strip().splitlines())
    for label in ("verify", "card"):
        assert "NO ERROR" not in lines[label], lines
        assert "Inter" in lines[label] and "700" in lines[label], lines[label]


def _layout_unknown_glyphs(family: str, weight: int, text: str) -> int:
    from auto_reel_ng.render.title import render as render_module

    cairo, pango, pangocairo = render_module._load_backend()  # pylint: disable=protected-access
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 200)
    layout = render_module._make_layout(  # pylint: disable=protected-access
        cairo.Context(surface),
        pango,
        pangocairo,
        family=family,
        weight=weight,
        size=48,
        width=1700,
    )
    layout.set_text(text, -1)
    return int(layout.get_unknown_glyphs_count())


def _uncovered_by_family(family: str, weight: int, text: str) -> list[str]:
    """Characters of ``text`` the requested face itself cannot draw.

    Pango falls back to another bundled family for a missing glyph, which the unknown-glyph count
    does not see; the face's own coverage does.
    """
    from auto_reel_ng.render.title import render as render_module

    _, pango, pangocairo = render_module._load_backend()  # pylint: disable=protected-access
    desc = pango.FontDescription()
    desc.set_family(family)
    desc.set_weight(pango.Weight(weight))
    font = pangocairo.FontMap.get_default().create_context().load_font(desc)
    coverage = font.get_coverage(pango.Language.from_string("en"))
    return [
        char
        for char in text
        if not char.isspace() and coverage.get(ord(char)) != pango.CoverageLevel.EXACT
    ]


@pytest.mark.has_fonts
@pytest.mark.parametrize(
    ("family", "weight"),
    [(font.family, weight) for font in BUNDLED_FONTS for weight in font.weights],
)
def test_swedish_and_central_european_text_has_every_glyph(
    has_fonts: None, family: str, weight: int
) -> None:
    text = SWEDISH + " ÉüñÅ " + CENTRAL_EUROPEAN
    assert _layout_unknown_glyphs(family, weight, text) == 0
    assert _uncovered_by_family(family, weight, text) == []


@pytest.mark.has_fonts
def test_the_glyph_check_notices_a_missing_glyph(has_fonts: None) -> None:
    # Pacifico has no Ĳ (U+0132) and Pango draws it from another bundled family, so only the
    # face's own coverage notices: the coverage check is not vacuous.
    assert _uncovered_by_family("Pacifico", 400, "ĲaÅ") == ["Ĳ"]


@pytest.mark.has_fonts
def test_every_family_renders_a_distinct_nonblank_card(has_fonts: None, tmp_path: Path) -> None:
    import cairo

    from auto_reel_ng.render.title import (
        TitleCardConfig,
        TitleCardContent,
        render_title_card,
    )

    target = _target(1920, 1080)
    digests: dict[str, str] = {}
    for font in BUNDLED_FONTS:
        dest = tmp_path / f"{font.family}.png"
        render_title_card(
            TitleCardConfig(font_family=font.family, background_opacity=0.5),
            TitleCardContent(heading=SWEDISH),
            target,
            dest,
        )
        surface = cairo.ImageSurface.create_from_png(str(dest))
        assert (surface.get_width(), surface.get_height()) == (1920, 1080), font.family
        assert surface.get_format() == cairo.FORMAT_ARGB32
        data = bytes(surface.get_data())
        # translucent black background (an opaque PNG collapses to RGB), white fill: a blank
        # card has no colour channel above zero
        assert any(data[i] for i in range(0, len(data), 4)), f"{font.family} drew nothing"
        digests[font.family] = hashlib.sha256(data).hexdigest()
    assert len(set(digests.values())) == len(BUNDLED_FONTS), digests


@pytest.mark.has_fonts
def test_a_fresh_host_run_needs_no_system_font(has_fonts: None, tmp_path: Path) -> None:
    dest = tmp_path / "card.png"
    script = f"""
        from pathlib import Path
        from auto_reel_ng.render.target import TargetSpec
        from auto_reel_ng.render.title import (
            TitleCardContent, parse_title_card_config, render_title_card,
        )
        from auto_reel_ng.render.title import render as r

        config = parse_title_card_config({{"font_family": "dm serif display"}})
        render_title_card(
            config, TitleCardContent(heading="Hej"), TargetSpec(width=320, height=240, fps=30.0, {_TARGET_FIELDS}),
            Path({str(dest)!r}),
        )
        _, pango, pangocairo = r._load_backend()
        families = sorted(f.get_name() for f in pangocairo.FontMap.get_default().list_families())
        print("|".join(families))
    """
    result = _run(script, env=_fresh_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert dest.is_file()
    seen = set(result.stdout.strip().split("|")) - _PANGO_GENERIC_FAMILIES
    # Pango lists the families of the engine's fontconfig: the bundled ones and no host font
    # (neither a shadow of a registered name nor a fallback for a missing glyph).
    assert seen == set(registered_families()), seen


@pytest.mark.has_fonts
@pytest.mark.skipif(shutil.which("fc-list") is None, reason="fc-list not installed")
def test_fc_list_under_the_engines_conf_lists_only_bundled_families(tmp_path: Path) -> None:
    env = _fresh_env(tmp_path, FONTCONFIG_FILE=str(FONTS / FONTS_CONF_NAME))
    result = subprocess.run(
        ["fc-list", "-f", "%{family[0]}\\n"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    assert set(result.stdout.split("\n")) - {""} == set(registered_families())


# --------------------------------------------------------------------------- #
# 4. The has_fonts gate uses the bundled directory                             #
# --------------------------------------------------------------------------- #

_GATE = """
    import sys
    sys.path.insert(0, {tests!r})
    from conftest import fonts_available
    print(fonts_available())
"""


def test_the_gate_is_true_in_a_fresh_process_with_no_fontconfig_file(tmp_path: Path) -> None:
    result = _run(_GATE.format(tests=str(Path(__file__).parent)), env=_fresh_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_the_gate_is_false_when_the_fonts_directory_has_no_conf(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _run(
        _GATE.format(tests=str(Path(__file__).parent)),
        env=_fresh_env(tmp_path, **{FONTS_DIR_ENV: str(empty)}),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
