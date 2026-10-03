## Context

State of `origin/main` (143f0fc, `timeline-view` and the proxy changes merged):

- `render/title/render.py` loads Cairo and Pango lazily in `_load_backend` (D-B), builds layouts by family name, and
  `_resolve_font_or_raise` loads the family and compares Pango's answer with the request, because Pango substitutes
  a missing family without a word (D-F). The probe for this change confirmed that on a one-font fontconfig.
- `render/title/config.py` owns `DEFAULT_FONT_FAMILY = "DejaVu Sans"` and parses `look.title_card.font_family` as any
  string; a family nobody installed fails only at render time.
- The image installs `fonts-dejavu` with apt and runs `fc-cache -f`; its header says fonts are resolved by name through
  fontconfig, "never a hardcoded path". `.dockerignore` drops `**/*.md`, `docs/`, `tests/`, `experiments/`, and keeps
  everything else, so a top-level `fonts/` reaches the build.
- `tests/conftest.py::fonts_available` loads "DejaVu Sans" through the default font map and the five title-card tests
  skip when it is not the answer. Host tests therefore skip on a machine without DejaVu.
- `RENDER_GRAPH_VERSION = 4`; the fingerprint is probe-free (editorial, defaults, clip set, engine id) and cannot see
  a font file.

## Goals / Non-Goals

**Goals**

- One list of families, with weights, that every consumer reads; the same glyphs on a dev host and in the image.
- No system font install on a host: `fonts/` is the font world of the renderer.
- A wrong or missing font is an error naming the family, at parse time when the config is wrong and at render time
  when the install is wrong; never a different typeface.

**Non-Goals**

- Card style, per-card fields, subtitle, background-on-video, durations, preview API, GUI: later changes read this one.
- Selecting a weight in `look.title_card`, italic faces, user-supplied fonts, web fonts in the GUI (D-10: system
  fonts, no web font). The GUI will preview a card with the engine's PNG, not by loading these files in the browser.
- A CLI command to list fonts: nothing an operator does changes; the registry is a library surface for the schema and
  API changes (Principle V is met when they land with their own surface).

## Decisions

**1. The set: DejaVu Sans plus eight OFL families, one per role.** DejaVu Sans stays the default and is bundled too, so
no family is "whatever the host has". Candidates (the implementer may swap a family within its role if upstream has
no static files or the license text cannot be shipped; the tests, not this list, are the contract):

| Role | Family | Weights |
|---|---|---|
| default | DejaVu Sans (Bitstream Vera / DejaVu license, not OFL) | 400, 700 |
| clean sans | Inter | 400, 700 |
| geometric sans | Poppins | 400, 700 |
| humanist sans | Source Sans 3 | 400, 700 |
| serif | Source Serif 4 | 400, 700 |
| display serif | DM Serif Display (Playfair Display ships only as a variable font) | 400 only |
| condensed | Barlow Condensed | 400, 700 |
| handwritten script | Pacifico | 400 only |
| monospace | IBM Plex Mono | 400, 700 |

Static files, not variable fonts, one file per declared weight. Where upstream ships only a variable font, take another
family for that role: re-instancing a font ships a modified font, and several of these have a Reserved Font Name.
Playfair Display, the first pick for the display serif, ships only as a variable font upstream, so the role is
DM Serif Display. Pacifico and DM Serif Display have one weight, which is why the registry records weights per family: a later weight control must not offer
a bold that Pango would synthesize. Every family must cover Basic Latin, Latin-1 and the Latin Extended-A letters of the Nordic, Western and Central
European alphabets and Turkish (the archive is Swedish: å ä ö, plus names with é ü ñ ł č ő); the render test checks
that set. It is not all of Latin Extended-A: measured on the files, no family but DejaVu Sans, Source Sans 3 and
IBM Plex Mono has every precomposed character of the block (Esperanto circumflexes, Maltese dots and the ligature Ĳ are the
usual gaps; a family with a combining mark still draws a base letter plus the mark), and those letters are in no
name of the archive. The test checks the requested face's own coverage as well as Pango's unknown-glyph count,
because Pango fills a gap from another bundled family without counting it. Alternatives: Noto/Liberation (broader coverage but
visually plain), a larger set (a picker of 30 is a worse picker, and 40 MB of image).

**2. The registry is Python in `render/title/fonts.py`, with no `gi` import.** A frozen dataclass `FontFamily` (family
name as fontconfig knows it, display name, role, weights, files as relative path plus sha256, license file) and an
ordered tuple `BUNDLED_FONTS`, with `font_for(name)` (case-insensitive, returns the canonical entry or raises
`FontResolutionError` listing the registered names), `registered_families()` and `DEFAULT_FONT_FAMILY`. It stays free of
`gi` so the config parser, the schema and the API import it cheaply and the engine still imports light (D-B). Why not a
JSON/YAML file in `fonts/`: Python gives typed access and mypy, and the sha256 test ties the file list to the
directory. Alternative, reading the families from fontconfig at runtime (`fc-list`): shells out (Principle VI) and
yields no roles or display names.

**3. `fonts/fonts.conf` makes the bundled directory the entire font world.** It holds `<dir prefix="relative">.</dir>`
and a `<cachedir prefix="xdg">auto-reel/fontconfig</cachedir>`, and **no** include of `/etc/fonts/fonts.conf`. A
standalone configuration is what "the same render everywhere" means: no host font can be picked as a fallback and no
host rule (hinting, antialiasing, an alias that maps "serif" elsewhere) changes the glyphs. The cost is that a
character outside the bundled coverage renders as a missing-glyph box instead of a host fallback; that is visible,
not a silent other face, and the coverage rule in decision 1 keeps it to unusual input. The probe showed the relative
dir and the xdg cachedir work on fontconfig 2.17. Alternative, including the system config: smaller conf, but then
the render depends on the host and host fonts could shadow a bundled family of the same name.

**4. The engine sets `FONTCONFIG_FILE` itself, once, before the first Pango font map.** `configure_fontconfig()` in
`fonts.py` (idempotent) sets `os.environ["FONTCONFIG_FILE"]` to `<fonts dir>/fonts.conf`, where the directory is
`$AUTO_REEL_FONTS_DIR` or the checkout's `fonts/` (the same layout assumption as `web/dist`: an editable install; the
wheel does not ship `fonts/`, as it does not ship `web/dist`). It overrides a `FONTCONFIG_FILE` already in the
environment, because the renderer's contract is the bundled set; a missing directory or `fonts.conf` raises
`TitleCardError` naming the path. `_load_backend` calls it before importing `PangoCairo`. The default font map is
created and cached by the first call, after which fontconfig ignores the variable, so the order matters: the
fail-loud check stays, and when a family does not resolve the error names the fonts directory and the
`FONTCONFIG_FILE` in effect, and says the variable must be set before the process makes its first font map. The variable also reaches ffmpeg children; they do not use
fontconfig for this pipeline. Alternatives: calling `FcConfigAppFontAddDir` through ctypes (the font map may already
hold its own config; no better ordering story, and a native-library dependency in Python), or a generated conf file
under the cache (needs a writable directory and invalidation; a static file does not).

**5. The renderer's check also checks the weight.** `_resolve_font_or_raise` already compares families. It takes the
weight the card is drawn at (400 today) and also compares the weight of the face Pango loaded with the weight
asked for, so a missing Bold file is caught for a family that declares it, instead of Pango synthesizing a fake
bold. `verify_bundled_fonts()` (in `render.py` with the other `gi` calls) loads every registered family at every
declared weight and raises `FontResolutionError` for the first that does not resolve; the per-font test and the
image build both call it.

**6. `font_family` is checked against the registry at parse time.** `parse_title_card_config` canonicalises the
family through `font_for` (so "dejavu sans" becomes "DejaVu Sans") and raises `TitleCardError` naming the field
and the registered families. This is an ADDED requirement beside the unchanged "Title-card config parsed from `look`",
which several sibling title-card changes will also edit; keeping it separate keeps their MODIFIED blocks from
colliding. An absent family still means the default. Existing events that named an unregistered family could not
render in the image before either (only DejaVu was installed there), so no data migration; a host that had other
fonts installed and used them via `look.title_card.font_family` now gets the parse error and must pick a registered one.

**7. The image installs `fonts/`; it drops `fonts-dejavu`.** The Containerfile adds `fontconfig` (for `fc-cache`,
which `fonts-dejavu` brought in; Debian's `fontconfig-config` may still pull `fonts-dejavu-core`, which the standalone
`fonts.conf` of decision 3 never reads), copies `fonts/` to `/app/fonts` in a layer after the dependency layer and before `COPY . /app` (a font edit
does not re-download the wheels; `COPY . /app` carries the directory too, so the named copy is for the reader), and after `COPY . /app` runs `verify_bundled_fonts()` with the engine's configuration, so a build
whose fonts do not resolve fails. The engine reads `/app/fonts`, the same path logic as the host (`/app` is the
checkout in the image). No second copy under `/usr/share/fonts`: one source, so the image and the host cannot
diverge. License texts are `.txt` because `.dockerignore` drops `**/*.md`.

**8. `RENDER_GRAPH_VERSION` goes 4 → 5.** The fingerprint cannot see font files, and this change swaps the file DejaVu
Sans is drawn from and removes the host fontconfig's rules, so the default card's pixels may change for identical
inputs (Principle IV: bump in the same change). Over-bumping costs one re-render per event (D-C8). To keep the next
font edit from slipping by, the registry records a sha256 per file and a test fails on a mismatch with a message that
says to bump the version; changing a bundled font is then a deliberate edit of three things (file, hash, version).

## Risks / Trade-offs

- [`FONTCONFIG_FILE` set too late: another component in the process created a Pango font map first] -> the order is
  fixed at the one backend seam, the fail-loud check catches a miss, and a fresh-subprocess test runs a render with the
  variable unset.
- [Standalone fontconfig drops system fallback, so an unusual character draws a box] -> coverage rule (decision 1) and a
  glyph test per family; acceptable and visible, the opposite of a silent other face.
- [Licenses] -> every family ships its license text beside the files; OFL fonts are not sold alone and keep their
  names (no modification), and DejaVu's license is named as such. The image stays local-only (Containerfile header),
  so no redistribution question arises from this change.
- [Repo size: about 16 files, typically 100 to 700 KB each] -> budget of 8 MB for `fonts/`, enforced by a test.
- [A family's static files are not at the expected upstream place] -> swap within the role (decision 1); the registry
  and tests do not name the family.
- [Everything re-renders once] -> accepted, decision 8; `--force` is not needed, the gate sees the version.

## Migration Plan

Merge, rebuild the image (`podman compose build`), and re-render events as the gate marks them stale. Rollback is
reverting the change; the version bump makes the revert re-render once more. The Postgres schema is untouched.
