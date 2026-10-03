## Why

A title card is drawn with Pango, which resolves the font by family name through whatever fontconfig the host has.
Today the only guaranteed family is DejaVu Sans, installed as a Debian package in the image; on a dev host it is
whatever happens to be installed (the five title-card tests skip when it is missing). That makes two things
impossible that the title-card work of GUI v2 needs:

- **A choice of typeface.** The user wants to "edit the font" of a title card in the editor. A picker needs a fixed,
  known list: the same families, with the same weights, on every host, so the preview and the render match.
- **The same render everywhere.** `render_title_card` is the single seam the GUI preview and the render share
  (HLD §4.4). If the families come from the host, a card that looks right on the dev machine renders in another
  face in the image, or fails.

This change is the foundation under the later title-card changes (the card style and per-card fields, the preview
API, the editor): a curated set of bundled fonts, one registry that names them, and an engine that finds them with
no system install. It adds no card field and no endpoint; the schema, the preview API and the GUI read the registry
when their changes land.

User decisions (2026-10-03, relayed by the supervisor): "a curated bundled set of ~8 OFL fonts (same render
everywhere)"; DejaVu Sans stays the default. Evidence relied on: the renderer today (`render/title/render.py`: D-B
lazy backend, D-F fail-loud resolution), the Containerfile header (fonts resolved by family name through fontconfig,
DejaVu Sans from `fonts-dejavu`), `tests/conftest.py` (`fonts_available` is why host tests skip), and a probe made
for this change on the dev host (fontconfig 2.17.0, PyGObject 3.56.3): a `fonts.conf` of one relative `<dir>` set as
`FONTCONFIG_FILE` from Python before the first `PangoCairo.FontMap.get_default()` made Pango see exactly that
directory, and a family it did not hold was **silently substituted** (asked for DejaVu Sans, got Liberation Sans),
which is why the existing fail-loud check has to stay. The GUI v2 research (`research/v2/`) did not study fonts.

## What Changes

- **A bundled font set** in a repo `fonts/` directory: DejaVu Sans (the default) and eight OFL families, one per
  role (a clean sans, a geometric sans, a humanist sans, a serif, a display serif, a condensed, a handwritten
  script, a monospace), each with its license text and a `fonts.conf` that makes the directory the whole font world
  of the renderer.
- **A font registry module** (`auto_reel_ng/render/title/fonts.py`): per family its name, display name, role, weights,
  files with checksums and license; the single source that the config check, the later schema, the preview API and
  the GUI read. `DEFAULT_FONT_FAMILY` stays "DejaVu Sans".
- **The engine finds the fonts itself.** Before the first Pango font map exists, the renderer points fontconfig at
  `fonts/fonts.conf` (`FONTCONFIG_FILE`), so a host run needs no system font install. `AUTO_REEL_FONTS_DIR` moves the
  directory. The renderer's host-substitution check stays and now also checks the weight.
- **`look.title_card.font_family` must be a registered family**, checked when the config is parsed, with the list in
  the error. Matching ignores case.
- **The image installs the fonts** from `fonts/` instead of the Debian `fonts-dejavu` package, and the build fails
  if any registered family does not resolve.
- **`RENDER_GRAPH_VERSION` 4 → 5**: the font files are now a render input the fingerprint cannot see, and the
  default card is drawn from a different DejaVu Sans file under a different fontconfig. Every rendered event
  becomes stale once.

No **BREAKING** API change: nothing reads the registry over HTTP yet.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `title-card`: adds the bundled font set, the registry, the engine-owned fontconfig and the registered-family
  check; modifies "Fail-loud font resolution" (the family resolves from the bundled set, not from the host).
- `container-stack`: the image carries the bundled font set, resolvable through fontconfig, in place of the Debian
  DejaVu package, and a build that cannot resolve a registered family fails.

## Impact

- New: `fonts/` (about 16 font files, license texts, `fonts.conf`), `auto_reel_ng/render/title/fonts.py`.
- Changed: `render/title/render.py` (configure before the font map; weight in the check), `render/title/config.py`
  (the family check; `DEFAULT_FONT_FAMILY` imported from the registry), `render/title/__init__.py` (exports),
  `staleness/fingerprint.py` (version), `Containerfile`, `.dockerignore` (keeps `fonts/`; licenses are `.txt` because
  `**/*.md` is ignored), `tests/conftest.py` (`fonts_available` uses the bundled directory), `docs/high-level-design.md`,
  `README.md`.
- No new Python dependency. Image grows by the font files (budget: 8 MB for `fonts/`). No schema, API or web change,
  so no regenerated web types.
- Not done here: the card style, per-card fields, background-on-video, durations, the preview endpoint, any GUI.
  A font weight is not yet selectable in `look.title_card`; the registry records which weights exist for the change
  that adds it.
