## Context

The render pipeline (#4) is in place: a `RenderPlan` is flattened into a `Segment` list, decorators may add
synthetic segments or attach overlays, each segment is normalized to a derived `TargetSpec`, and the uniform
set is stream-copy concatenated with real chapter markers. Two seams were built but left unfilled for #5:

- `render/decorators.py` — a name-keyed decorator registry with `make_inserter` / `make_attacher`; only `none`
  is registered. Decorators are pure `(plan, target, segments) -> segments` and selected from `look.decorators`.
- `segments.py` — `Segment.producer` / `Segment.duration` (synthetic fields) and `Segment.overlays` /
  `OverlaySpec` (already wired into the normalize graph builder, including a CPU overlay bridge).

The gap: `build_normalize_command` (`render/normalize.py`) raises `RenderError` for any synthetic segment —
*"synthetic rendering arrives with the title change (#5)"*. So nothing materializes a synthetic segment's
content. This change fills both seams with the title card and the generic producer mechanism behind it.

Inputs available to a decorator: `RenderPlan.metadata` (title/date/location/description), `RenderPlan.look`
(opaque map), `ResolvedClip.is_title`, and `ResolvedChapter.title_clip`. The old auto-reel marked the first
clip of each chapter as the title clip; `is_title` already carries that resolution forward.

Constraints carried in: fail loud / never fabricate; strict mypy; ffmpeg ≥ 7.1 invoked as subprocess; the
chosen codec must be honored (the moviepy bug being fixed); AMD `overlay_vaapi` is unsupported (exp 003);
D-1 Debian-based jellyfin-ffmpeg image.

## Goals / Non-Goals

**Goals:**
- Render an event title card to an image and encode it as a normal segment at the target spec, with the chosen
  codec — never a separate hardcoded-codec encode (fixes auto-reel #4).
- Card-as-segment: overlay-free, fully on-GPU on every vendor, sidestepping the AMD `overlay_vaapi` gap.
- One swappable renderer seam (`render_title_card`) shared by the pipeline and the future GUI preview, so
  preview is byte-identical to the render.
- A generic synthetic-segment **producer** seam that future look features (intro/outro/transition) reuse.
- Fail loud on an unresolved font family; honor a bundled default.

**Non-Goals:**
- Title-over-footage overlay (the `attacher` shape stays unused this change).
- GUI endpoints/preview UI; animated/motion titles; a second renderer backend; HDR/rotation for cards.

## Decisions

### D-A — Card as its own segment (inserter), not an overlay
The card is a synthetic `Segment` inserted before a chapter's title clip, then encoded and concatenated like
any clip. **Why:** AMD has no `overlay_vaapi` (exp 003); a segment keeps the whole pipeline overlay-free and
100% GPU on every vendor, makes fades trivial (a `fade` filter on the card clip rather than time-varying
overlay alpha), and makes the GUI preview equal to the render (just display the PNG). **Alternative
considered:** the `attacher`/overlay path from §4.4's original wording — rejected for v1 because it forces a
CPU bridge on AMD for the title seconds and an `OverlaySpec` fade-alpha extension, for a look (text over live
footage) that is a *different* product we can add later via the same renderer with zero rework.

### D-B — Cairo + Pango renderer behind a swappable seam
`render_title_card(config: TitleCardConfig, target: TargetSpec) -> Path` writes an RGBA PNG. Backend is
pycairo + PangoCairo: an `ARGB32` surface at `target.width × target.height`, a `Pango.Layout` per text block
(alignment, wrap width, kerning/interline), outline via `pango_cairo_layout_path` + stroke, shadow via an
offset translucent draw, optional background fill. **Why Cairo+Pango over Pillow:** real shaping/wrapping/
kerning, fontconfig name-based fonts (matches §4.4 "configurable fonts, no hardcoded path"), and headroom for
non-Latin/RTL — chosen by the operator over Pillow's lighter footprint. The single-function seam means the
backend never leaks into the pipeline or GUI and stays reversible. **Alternative:** Pillow (lighter image,
better typing) — recorded in the proposal/HLD §8.5 as the runner-up.

### D-C — Generic, name-keyed producer registry (parallel to decorators)
`segment-producer` is a registry `name -> producer`. A producer materializes a synthetic segment into a
`ProducedSegment` (a rendered image/input path, a duration, and fade-in/out timings). `Segment.producer` holds
the registry key. **Why generic:** mirrors the decorator seam's "pluggable, not hardcoded" design so
intro/outro/transition bumpers slot in later without touching the core; the title is just the first
registration. **Alternative:** a title-specific branch in the orchestrator — rejected as the same hardcoding
the decorator seam was built to avoid.

### D-D — Synthetic normalize: loop the image, fade, synthesize silence
`clip-normalize` gains a synthetic path: instead of raising, it asks the producer to materialize the segment,
then builds `-loop 1 -t <duration> -i card.png`, applies `fade=t=in` / `fade=t=out` over the configured fade
durations, synthesizes a silent audio track (`anullsrc` at the target's audio params — reusing the existing
video-only-clip silence logic), scales/conforms to the target if the PNG is authored off-size (it is authored
on-size, so this is a guard), and encodes to the target codec/pix_fmt/fps. **Why reuse normalize:** the card
must hit the *exact* target spec or the equivalence pre-flight will force a re-encode anyway; building it
through the same target-conforming path guarantees a copy-uniform set. Synthetic segments remain never
copy-eligible (existing requirement).

### D-E — Title placement and text from plan data
The `title` decorator inserts one synthetic segment immediately before each chapter's title clip
(`is_title`/`title_clip`). The movie's first/default card composes text from `RenderPlan.metadata` (title,
date, location, description, with the Swedish "Plats:"-style location handling carried over); a non-default
chapter's card uses the chapter name as its heading. The synthetic segment records that chapter so chapter
durations (measured post-encode) stay correct. **Why driven by `is_title`:** reuses the resolution the reel
loader already produces (per-clip `title: true`), so no new editorial concept is introduced.

### D-F — Fail-loud font resolution
Pango silently substitutes a missing family. Before rendering, resolve the configured family through
fontconfig and **raise a typed error** if it does not resolve, naming the family and the bundled default.
**Why:** Pango's silent substitution violates the project's fail-loud ethos; an operator must never get a card
in the wrong typeface without being told.

### D-G — Config parsed at render time, `reel-document` unchanged
The typed `TitleCardConfig` is parsed from the opaque `look.title_card` sub-map at render time, exactly as
`look.decorators` / `look.target_resolution` are already consumed. `reel-document` keeps carrying `look`
opaquely. **Why:** avoids widening the reel loader's contract (and its round-trip/comment-preservation
burden) for a schema only the renderer interprets; keeps this change to the render layer.

## Risks / Trade-offs

- **Pixel-exact golden tests are fragile** (Cairo/Pango/freetype anti-aliasing drifts across versions) →
  test layout *decisions* structurally (computed text boxes, wrap points, resolved family, emitted ffmpeg
  args) and gate a small tolerance-based image snapshot behind a "has-fonts" marker; do not assert exact PNGs.
- **Heavier container image** (cairo/pango/fontconfig + PyGObject + `fc-cache`) → confined to the D-1 image;
  the engine stays import-light elsewhere and the renderer is only imported when a title decorator runs.
- **PyGObject is untyped under strict mypy** → add `gi.*` to `ignore_missing_imports` (same exemption already
  granted moviepy/exifread); wrap the gi surface in our own typed `render_title_card` so untyped calls don't
  spread.
- **Soft drop-shadow** has no native Cairo blur → ship a crisp offset shadow / vector outline in v1; a blurred
  shadow (manual surface blur) is a follow-up, not a blocker.
- **Card duration vs a very short first clip** (old code split the clip behind the title) → not a problem
  here: the card is a *separate* segment, so the footage is never consumed by the title; the only risk is a
  fade longer than the card duration → clamp fades to the duration and validate at config parse.

## Migration Plan

Additive. With no `look.decorators` (or `none`), behavior is unchanged — no card is produced and the synthetic
path is never hit. Titles are opt-in via `look.decorators: [title]`. Container changes (apt libs + fonts +
`fc-cache`, `pycairo`/`PyGObject` deps) ship with the image; a dev host needs the same system libs to render
or run the renderer's tests (otherwise those tests skip behind the marker). No data migration; no rollback
beyond removing the decorator from `look`.

## Resolved Questions (2026-06-04)

- **Per-chapter cards: yes.** v1 inserts a title segment before every `is_title` clip — the movie's opening
  card *and* a card before each subsequent chapter's title clip. (As already specced in `specs/title-card`
  "Per-chapter title segments" and task 5.1.)
- **Defaults: carry auto-reel's.** When `look.title_card` is silent, default to **7s total duration / 2s
  fades** with title centered and description/location below. Bundled default font family = **DejaVu Sans**
  (resolved by fontconfig name, installed via `fonts-dejavu` in the D-1 image, not a hardcoded path).
- **Layout: Pango column-wrapping**, not auto-reel's relative-offset hand-positioning. Text blocks (title,
  then date/location/description) are laid out as centered Pango layouts that wrap within a max-width column —
  this is a reason we chose Cairo+Pango. Validate spacing against the sample media during implementation, but
  do not re-port the old manual offset math.
