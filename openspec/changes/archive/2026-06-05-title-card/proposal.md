## Why

The render pipeline (#4) shipped the decorator seam and a `none` default but deliberately renders **no
title content**: `build_normalize_command` raises for any synthetic segment ("synthetic rendering arrives
with the title change (#5)"). This change closes that gap — it gives auto-reel its title cards back while
fixing auto-reel problem #4: moviepy spawned its own hardcoded-codec `libx264`/`aac` ffmpeg, ignored the
chosen codec, and hardcoded font paths. The card now renders to an image and is encoded to the **target
spec** like any other segment, with the chosen codec.

The HLD's §4.4 left two questions open; this change resolves both. (1) §4.4 originally said "overlay the card
in the normalize pass," but the AMD spike (exp 003) found `overlay_vaapi` unsupported on Mesa — so we ship the
card as **its own segment** (overlay-free, fully GPU on every vendor, trivially cross-vendor), siding with the
spike over the original §4.4 wording. This also makes the future GUI's title-card preview byte-identical to
the render (the same renderer produces both). (2) §8.5 (Pillow vs Cairo) is resolved to **Cairo + Pango**
(real typography: shaping, wrapping, kerning, fontconfig name-based fonts), kept behind a swappable renderer
seam so the library never leaks into the pipeline.

## What Changes

- **Title card image renderer (Cairo + Pango):** render an event's title card to an RGBA PNG at the target
  resolution — title/date/location/description text laid out by Pango (centering, wrapping, kerning), optional
  background, and an outline/shadow. Fonts are resolved **by family name via fontconfig** with a bundled
  default; an unresolved family **fails loud** (never silently substituted), honoring the project's
  fail-loud-never-fabricate rule. The renderer is a single seam — `render_title_card(config, target) -> PNG` —
  so the Cairo/Pango backend is swappable without touching the pipeline or the GUI.
- **Generic synthetic-segment producer seam:** a name-keyed **producer registry** (parallel to the decorator
  registry) materializes a synthetic `Segment`'s content by its `producer` reference. This is the general
  mechanism future synthetic segments (intros, outros, transition bumpers) reuse; the title card is its first
  registration.
- **Title decorator (inserter):** a registered `title` decorator that inserts a synthetic title segment before
  each chapter's title clip, carrying the producer reference, the resolved duration, and the look-derived card
  config. Card text is composed from the event `metadata` (and the chapter name for non-default chapters).
  Selected via the existing `look.decorators` list; absent ⇒ the `none` default, so behavior is unchanged
  unless titles are requested.
- **Typed title-card config from `look`:** parse a typed config from the opaque `look.title_card` sub-map
  (font family/size/color, outline/shadow, background, fade in/out durations, total duration, position). No
  change to `reel-document` — `look` is still carried opaquely there and interpreted at render time, matching
  how `look.decorators`/`target_resolution` are already consumed.
- **Synthetic segment encoding (replaces the `raise`):** `clip-normalize` materializes a synthetic segment via
  its producer and builds a target-conforming normalize command from the rendered image — `-loop 1` the PNG to
  the segment duration, apply `fade=in`/`fade=out` for the card fades, synthesize a silent audio track, and
  encode to the target codec/pix_fmt/fps. Overlay-free: no `overlay_vaapi`, no CPU bridge.

## Capabilities

### New Capabilities
- `title-card`: the title-card config (parsed from `look.title_card`), the Cairo+Pango image renderer
  (RGBA PNG at target resolution, fail-loud fontconfig font resolution, outline/shadow/background/fades), and
  the `title` decorator that inserts a synthetic title segment before each chapter's title clip with text
  composed from event metadata and chapter name.
- `segment-producer`: a generic, name-keyed registry that materializes a synthetic segment's content by its
  `producer` reference (returning the rendered image/inputs + duration + fade timing), so synthetic segments
  can be encoded to the target spec without the pipeline core knowing about titles. The title card registers
  the first producer; future look features (intro/outro/transition) reuse the seam.

### Modified Capabilities
- `clip-normalize`: synthetic segments are no longer rejected. The normalize builder materializes a synthetic
  segment via the `segment-producer` seam and composes a target-conforming command from the rendered image
  (image-loop input, `fade` in/out, synthesized silent audio, encode), replacing the current behavior that
  raises a typed error for any synthetic segment.

## Impact

- **New code:** `auto_reel_ng/render/title/` (Cairo+Pango renderer + typed card config), a producer registry
  (alongside `render/decorators.py`), and the `title` decorator registration. Modifications to
  `render/normalize.py` (synthetic path) and the decorator wiring.
- **New runtime dependencies:** `pycairo` + `PyGObject` (Pango/PangoCairo). System libs in the container
  image (D-1, Debian-based jellyfin-ffmpeg): `libcairo2`, `libpango-1.0-0`, `libpangocairo-1.0-0`,
  `gir1.2-pango-1.0`, a default font package (`fonts-dejavu`), plus an `fc-cache` step. `gi.*` added to the
  mypy `ignore_missing_imports` list (same exemption already granted moviepy/exifread).
- **Consumes:** `render-segments` (the decorator seam, `Segment.producer`/`duration`, `OverlaySpec`),
  `event-resolution` (`RenderPlan.metadata`/`look`, `ResolvedClip.is_title`, `ResolvedChapter.title_clip`),
  the derived `TargetSpec`, and `acceleration-profile` encode fragments.
- **Consumed by:** the GUI (#8/#9 use `render_title_card` for the look-editor preview), and any future
  synthetic-segment look feature (via the `segment-producer` seam).
- **Docs:** resolve §8.5 (Cairo+Pango) and update §4.4 (card-as-segment, not overlay-in-pass) in the HLD.

## Non-goals

- **Title-over-footage overlay:** the alternative "text fading over the opening clip" look is **not** built
  here. The decorator seam's `attacher` shape supports it as a pure future addition reusing the same renderer;
  v1 ships only the card-as-segment `inserter`. No `OverlaySpec` fade-alpha extension in this change.
- **GUI / look editor (#8/#9):** this change exposes `render_title_card` as a reusable seam but builds no API
  endpoint, preview UI, or live editing. Wiring it into the FastAPI service and the browser is later work.
- **Per-frame / animated titles, motion, transitions between segments:** the card is a static image faded
  in/out over a fixed duration; animated text and inter-segment transitions are out of scope.
- **Renderer-backend abstraction beyond one seam:** only Cairo+Pango is implemented. The `render_title_card`
  signature is swappable, but no second backend (Pillow, Pillow+raqm) is written.
- **HDR/rotation handling for synthetic segments:** the card is authored at the target spec (SDR, upright),
  so it needs no tonemap or rotation path.
