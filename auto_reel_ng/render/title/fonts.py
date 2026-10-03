"""The bundled title-card fonts: one registry, and the fontconfig the renderer owns.

Decision **D-22**: a title card is drawn from a curated set of fonts that lives in the
repository (``fonts/``), so the same families, with the same weights, render on every
host and in the image. This module is the single source of that list: the config check,
the schema, the preview API and the GUI read the families from here and keep no list of
their own.

The registry half imports neither ``gi`` nor ``cairo`` (it must stay cheap to import,
decision **D-B**). :func:`configure_fontconfig` is the one place that decides which
fontconfig Pango will use; it must run before the first Pango font map of the process
exists, which is why ``render._load_backend`` calls it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ...errors import FontResolutionError, TitleCardError

#: The default family. It is bundled too, so no family is "whatever the host has".
DEFAULT_FONT_FAMILY = "DejaVu Sans"

#: Env var that moves the fonts directory (a copy of ``fonts/``, ``fonts.conf`` included).
FONTS_DIR_ENV = "AUTO_REEL_FONTS_DIR"

#: The fontconfig configuration inside the fonts directory: that directory, nothing else.
FONTS_CONF_NAME = "fonts.conf"

# Role names (one family per role).
ROLE_DEFAULT = "default"
ROLE_CLEAN_SANS = "clean sans"
ROLE_GEOMETRIC_SANS = "geometric sans"
ROLE_HUMANIST_SANS = "humanist sans"
ROLE_SERIF = "serif"
ROLE_DISPLAY_SERIF = "display serif"
ROLE_CONDENSED = "condensed"
ROLE_SCRIPT = "handwritten script"
ROLE_MONOSPACE = "monospace"

#: Every role a title-card font fills, in registry order.
ROLES = (
    ROLE_DEFAULT,
    ROLE_CLEAN_SANS,
    ROLE_GEOMETRIC_SANS,
    ROLE_HUMANIST_SANS,
    ROLE_SERIF,
    ROLE_DISPLAY_SERIF,
    ROLE_CONDENSED,
    ROLE_SCRIPT,
    ROLE_MONOSPACE,
)

OFL = "SIL Open Font License 1.1"


@dataclass(frozen=True)
class FontFile:
    """One static font file: the weight it is, its path under ``fonts/``, its SHA-256."""

    weight: int
    path: str
    sha256: str


@dataclass(frozen=True)
class FontFamily:
    """One bundled family, as every consumer sees it."""

    #: The family name as fontconfig knows it (what Pango is asked for).
    family: str
    #: The name a picker shows.
    display_name: str
    #: Which of :data:`ROLES` the family fills.
    role: str
    #: One entry per declared weight, lightest first.
    files: tuple[FontFile, ...]
    #: Path of the license text under ``fonts/``.
    license_file: str
    #: The license, by name.
    license: str

    @property
    def weights(self) -> tuple[int, ...]:
        """The weights this family declares (a later weight control must offer only these)."""
        return tuple(font.weight for font in self.files)


#: The bundled families, default first. Changing a font file means changing its hash here and
#: bumping ``RENDER_GRAPH_VERSION`` (a font is a render input the fingerprint cannot see).
BUNDLED_FONTS: tuple[FontFamily, ...] = (
    FontFamily(
        family="DejaVu Sans",
        display_name="DejaVu Sans",
        role=ROLE_DEFAULT,
        files=(
            FontFile(
                400,
                "dejavu-sans/DejaVuSans.ttf",
                "7da195a74c55bef988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954",
            ),
            FontFile(
                700,
                "dejavu-sans/DejaVuSans-Bold.ttf",
                "e6476c1b80502924294eed40894c5b18e06c181444ca953e5334262df9c27724",
            ),
        ),
        license_file="dejavu-sans/LICENSE.txt",
        license="Bitstream Vera / DejaVu license",
    ),
    FontFamily(
        family="Inter",
        display_name="Inter",
        role=ROLE_CLEAN_SANS,
        files=(
            FontFile(
                400,
                "inter/Inter-Regular.ttf",
                "40d692fce188e4471e2b3cba937be967878f631ad3ebbbdcd587687c7ebe0c82",
            ),
            FontFile(
                700,
                "inter/Inter-Bold.ttf",
                "288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f",
            ),
        ),
        license_file="inter/OFL.txt",
        license=OFL,
    ),
    FontFamily(
        family="Poppins",
        display_name="Poppins",
        role=ROLE_GEOMETRIC_SANS,
        files=(
            FontFile(
                400,
                "poppins/Poppins-Regular.ttf",
                "7e65201e9b79159e2300267cc885e16c8dcef2424cdfa09a29bfb0980a94a7ba",
            ),
            FontFile(
                700,
                "poppins/Poppins-Bold.ttf",
                "983676516167748b74de6f4771fb384c664fd913acb8b471122ecacf5da5ea6c",
            ),
        ),
        license_file="poppins/OFL.txt",
        license=OFL,
    ),
    FontFamily(
        family="Source Sans 3",
        display_name="Source Sans",
        role=ROLE_HUMANIST_SANS,
        files=(
            FontFile(
                400,
                "source-sans-3/SourceSans3-Regular.ttf",
                "4644c81b86ec9caaa76b634889968ed3c4f4f52f054855933acc7c2b21e53b0f",
            ),
            FontFile(
                700,
                "source-sans-3/SourceSans3-Bold.ttf",
                "9214b9d95e4231c609802815c2646c98174e2102d0d37f88978a7f8e71006e6a",
            ),
        ),
        license_file="source-sans-3/OFL.txt",
        license=OFL,
    ),
    FontFamily(
        family="Source Serif 4",
        display_name="Source Serif",
        role=ROLE_SERIF,
        files=(
            FontFile(
                400,
                "source-serif-4/SourceSerif4-Regular.ttf",
                "e5a4ee6a3d87bb9024796be390c6771e2a0eb1883dae25effaf57ca01668e24b",
            ),
            FontFile(
                700,
                "source-serif-4/SourceSerif4-Bold.ttf",
                "7cf4f4e1ad74f45058d5bc61716b82560442fbdcd9d3654d2dea96bf6c683d86",
            ),
        ),
        license_file="source-serif-4/OFL.txt",
        license=OFL,
    ),
    # Playfair Display (the design's first pick) ships only as a variable font; re-instancing
    # it would ship a modified font, so the display-serif role is DM Serif Display, which has
    # one static weight like Pacifico.
    FontFamily(
        family="DM Serif Display",
        display_name="DM Serif Display",
        role=ROLE_DISPLAY_SERIF,
        files=(
            FontFile(
                400,
                "dm-serif-display/DMSerifDisplay-Regular.ttf",
                "8cc3643535edf039aa5d95440a8542735e9197e4f4b8d9303e980fefbf5ab616",
            ),
        ),
        license_file="dm-serif-display/OFL.txt",
        license=OFL,
    ),
    FontFamily(
        family="Barlow Condensed",
        display_name="Barlow Condensed",
        role=ROLE_CONDENSED,
        files=(
            FontFile(
                400,
                "barlow-condensed/BarlowCondensed-Regular.ttf",
                "583cec5da3b84bc4dc7c9c72e2a565c94d34e431518b19d7e250b7830ad5f996",
            ),
            FontFile(
                700,
                "barlow-condensed/BarlowCondensed-Bold.ttf",
                "e476562ec9c1e16cf16475895b511f08c804f438cc9a9f80a44ea50a0eeb5b65",
            ),
        ),
        license_file="barlow-condensed/OFL.txt",
        license=OFL,
    ),
    FontFamily(
        family="Pacifico",
        display_name="Pacifico",
        role=ROLE_SCRIPT,
        files=(
            FontFile(
                400,
                "pacifico/Pacifico-Regular.ttf",
                "5b6c0d5334a7bf77dea52b975c5a0c408878c0f7115ed5b6fb151f634b7bf701",
            ),
        ),
        license_file="pacifico/OFL.txt",
        license=OFL,
    ),
    FontFamily(
        family="IBM Plex Mono",
        display_name="IBM Plex Mono",
        role=ROLE_MONOSPACE,
        files=(
            FontFile(
                400,
                "ibm-plex-mono/IBMPlexMono-Regular.ttf",
                "6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46",
            ),
            FontFile(
                700,
                "ibm-plex-mono/IBMPlexMono-Bold.ttf",
                "ac27abd6450a64dd94467580a02fe6235156d5b92f2926ebbc8e7489df64e0be",
            ),
        ),
        license_file="ibm-plex-mono/OFL.txt",
        license=OFL,
    ),
)


def registered_families() -> tuple[str, ...]:
    """The registered family names, default first."""
    return tuple(font.family for font in BUNDLED_FONTS)


def font_for(name: str) -> FontFamily:
    """Return the registry entry for ``name`` (ignoring case), or raise naming the choices."""
    wanted = name.strip().lower()
    for font in BUNDLED_FONTS:
        if font.family.lower() == wanted:
            return font
    raise FontResolutionError(
        f"font family {name!r} is not one of the bundled families: "
        f"{', '.join(registered_families())}"
    )


def fonts_dir() -> Path:
    """The directory holding the bundled fonts and their ``fonts.conf``.

    ``AUTO_REEL_FONTS_DIR`` if set, else the checkout's ``fonts/`` (the same editable-install
    layout assumption as ``web/dist``; the wheel ships neither).
    """
    override = os.environ.get(FONTS_DIR_ENV)
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "fonts"


def configure_fontconfig() -> Path:
    """Point fontconfig at the bundled ``fonts.conf`` and return its path.

    Sets ``FONTCONFIG_FILE``, replacing any value already in the environment: the renderer's
    contract is the bundled set, not the host's. It must run before Pango makes its first
    font map (the map is cached for the process and fontconfig reads the variable once).
    Idempotent. Raises :class:`TitleCardError` naming the path when the directory or its
    ``fonts.conf`` is missing.
    """
    directory = fonts_dir()
    conf = directory / FONTS_CONF_NAME
    if not directory.is_dir():
        raise TitleCardError(
            f"the bundled fonts directory {str(directory)!r} does not exist "
            f"(set {FONTS_DIR_ENV} to a copy of the repository's fonts/)"
        )
    if not conf.is_file():
        raise TitleCardError(
            f"the bundled fonts directory has no {FONTS_CONF_NAME}: {str(conf)!r} does not exist"
        )
    os.environ["FONTCONFIG_FILE"] = str(conf)
    return conf


__all__ = [
    "BUNDLED_FONTS",
    "DEFAULT_FONT_FAMILY",
    "FONTS_CONF_NAME",
    "FONTS_DIR_ENV",
    "FontFamily",
    "FontFile",
    "ROLES",
    "configure_fontconfig",
    "font_for",
    "fonts_dir",
    "registered_families",
]
