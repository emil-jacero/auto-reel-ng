## Why

The user wants title cards that can sit "on a piece of video" instead of text on black (2026-10-03: "should it be
text on black or text on a piece of video"). The chosen reading is that the text appears over the start of the
chapter's first clip while it plays, with no time added. Today a card is only ever its own black segment
(HLD §4.4, D-A: "card-as-segment, overlay-free"), and the title-over-footage variant is recorded as a non-goal.
This change builds that variant; the `card:` schema that selects it (`background: black | video`) is the gate
change `title-card-model`.

## What Changes

- A chapter whose resolved card has `background: video` gets **no inserted title segment**. The `title` decorator
  instead attaches the card as an `OverlaySpec` to the chapter's anchor segment (the segment a black card would
  precede: the title clip's first surviving span, else the chapter's first surviving segment), over its first
  `duration` seconds, fading in and out. The chapter, and so the movie, is exactly as long as without the card.
- The card renders on a **transparent** canvas for `video` (the same Cairo/Pango seam, so text, font, size,
  outline, shadow and position are laid out as for a black card; only the fill is skipped).
- `OverlaySpec` grows what a card needs: fade in/out and a producer reference that is materialized (the card PNG
  rendered) when the segment's normalize command is built, because decorators are pure and cannot render.
- The normalize step composites a timed, faded overlay with the CPU `overlay` filter on every profile (the AMD
  path already bridges; NVIDIA/Intel get the same CPU composite, unverified hardware overlays are not used for
  cards), loops the card still for its window, and **clamps the window to the segment's length**, reporting a
  render warning when it does.
- Cards with `background: black` are unchanged: same inserted segment, same ffmpeg arguments, same bytes.
- `RENDER_GRAPH_VERSION` is **not** bumped (see design: output is unchanged for every input that rendered
  before; a card edited to `video` changes the editorial hash and so turns that event stale by itself).
- HLD §4.4 (the "overlay is a non-goal" wording), the §4.10 / §6 v2 notes and the title-card decision are updated.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `title-card`: adds the over-video card (attached overlay instead of an inserted segment, transparent canvas,
  black cards unchanged, chapter times unchanged).
- `clip-normalize`: the overlay requirement gains timed, looped, alpha-faded overlays composited on the CPU,
  materialized from a producer, clamped to the segment with a reported warning.

## Impact

- Code (package `render`): `render/segments.py` (`OverlaySpec`), `render/producers.py` (overlay
  materialization), `render/normalize.py` (timed card overlay graph, clamp, warning), `render/orchestrator.py`
  (materialize before building), `render/title/decorator.py` (attach vs insert), `render/title/render.py`
  (transparent canvas). No change in `reel/`, `api/`, `persistence/`, `staleness/` code or `web/`.
- Tests: golden ffmpeg arguments (AMD and CPU profiles), decorator segment lists, clamp warning, chapter times,
  real renders on the CPU and, marked `gpu`, on VAAPI.
- Cost: the anchor segment of each over-video chapter is re-encoded through the CPU overlay bridge for its
  whole length (see design "Risks"); the other segments are unaffected.
- Depends on `title-card-model` (the `card:` schema and per-chapter resolved card). Docs: HLD §4.4, §4.10, §6.
