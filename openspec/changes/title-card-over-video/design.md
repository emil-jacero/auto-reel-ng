## Context

A card today is a synthetic segment: `title_decorator` (`render/title/decorator.py`) inserts a `Segment` with
`producer="title"` and a `TitleCardRequest`, the `title` producer renders an RGBA PNG, and
`build_synthetic_normalize_command` loops it, fades it and encodes it **overlay-free** (HLD §4.4, D-A; the
reason is experiment 003: `overlay_vaapi` is unsupported on AMD Mesa). The overlay half of the pipeline already
exists but has never been used for real: `Segment.overlays` / `OverlaySpec`, `make_attacher`, and in
`render/normalize.py` `_build_video_graph`, which switches to `-filter_complex` and bridges to the CPU around
`overlay` when the profile cannot overlay on the GPU (golden test `test_overlay_uses_cpu_bridge_filter_complex`,
which pins `hwdownload,format=nv12` and `overlay=x=10:y=20`). `copy_eligible` already refuses a segment with
overlays. See proposal.md "Why" for the motivation.

**What this change takes from the gate `title-card-model`** (not yet on origin/main when this was written; names
are the plan's, to be read off the merged code, see task 2.2): an optional per-chapter `card:` mapping with
`background: black | video`, `duration`, `title`, `subtitle` and style overrides, merged over the event-wide
`look.title_card` into one resolved card per chapter (the default chapter `''` holds the opening card); the
`TitleCardConfig` / `TitleCardRequest` payload the decorator and producer already pass around carrying the
resolved background. This change reads only the resolved background, duration, fades and style; it never reads
`reel.yaml`, and it does not touch `reel/` or `api/`.

Research evidence relied on (no v2 research document covers title cards; the evidence is repo-local):
- `experiments/003-vaapi-native-normalize/report.md` (rows A and §"Implications"): `overlay_vaapi` fails on AMD
  ("VAAPI driver doesn't support overlay"), there is no GPU text filter, and its own advice for an overlay was
  "only the title segment pays CPU cost". An over-video card gives that advice up for the anchor segment (Risks).
- `tests/test_render.py::test_overlay_uses_cpu_bridge_filter_complex` and the `clip-normalize` requirement
  "Overlay compositing with CPU bridge fallback": the bridge shape is specified and unit-tested; what has never
  run is a real overlay render, which tasks 3.1 and 3.2 add.
- HLD §4.4 names the overlay variant as the future use of the decorator seam's `attacher`; this is that use.

## Goals / Non-Goals

**Goals:**
- `background: video` cards render over the first seconds of the chapter's anchor segment, fading in and out,
  adding no time, on the CPU profile and on VAAPI (AMD, this host).
- `background: black` cards are untouched, byte for byte.
- One card renderer for both backgrounds, so the editor preview (`title-card-write-api`) shows what a render
  draws.

**Non-Goals:**
- Splitting the anchor segment so only the card seconds pay the CPU bridge (needs clip durations at decorator
  time; see Risks).
- Verifying hardware overlay filters (`overlay_cuda`, `overlay_qsv`) with an alpha still; cards use the CPU
  overlay on every profile instead.
- A scrim or dimming layer behind the text; legibility comes from the existing outline and drop shadow.
- Recording a title-card span for an over-video card in the manifest (Decisions, "Chapter times").
- The schema, fonts, preview endpoint and GUI (`title-card-model`, `title-card-fonts`, `title-card-write-api`).

## Decisions

### Attach an overlay, do not insert a segment
**Context**: the user decision is "the text sits over the START of the chapter's first clip while it plays (no
extra time added)". An inserted segment, even one built from the clip's frames, adds time.
**Explored**: (a) insert a synthetic segment that re-uses the clip's first frames as its background (adds
`duration` seconds, wrong); (b) replace the anchor segment by a synthetic "clip with card" producer (a producer
that decodes the clip: breaks the producer seam, which renders an asset and never encodes, D-C); (c) attach an
`OverlaySpec` to the anchor segment through the attacher shape the decorator seam was built for.
**Decision**: (c). `title_decorator` stays one decorator. For each chapter it picks the existing anchor
(`_anchor_indexes`: the title clip's first surviving span, else the chapter's first surviving segment, nothing
for a chapter with no surviving segment) and, by the chapter's resolved background, either inserts the segment
as now (`black`) or replaces the anchor with `replace(segment, overlays=segment.overlays + (overlay,))`
(`video`). The same anchor for both keeps the user-visible rule one sentence: the card goes where the chapter's
title clip starts.
**Rationale**: the seam already supports it; segment durations, chapter durations, `aggregate_chapter_durations`
and the concat are untouched, which is what makes "no time added" structural rather than tested-for.

### The decorator cannot render, so an overlay can carry a producer reference
**Context**: decorators are pure `(plan, target, segments) -> segments`; the card PNG is made by the `title`
producer into the render's scratch directory when the command is built (`_build_segment_command`).
**Decision**: `OverlaySpec` gains `producer: Optional[str]`, `producer_config: Optional[object]`, `fade_in`,
`fade_out` (all defaulting to "not used", `source` defaults to `""`, so every existing `OverlaySpec(...)` call
and its `to_dict` keys still hold). `_build_segment_command` resolves each producer-backed overlay before
building: it calls the registered producer with a transient synthetic `Segment` carrying the overlay's
`producer` and `producer_config`, gets a `ProducedSegment` (image path, duration, fades), and replaces the
overlay with a copy whose `source` is the image, `start=0`, `end=produced.duration` and fades from the produced
timings. The same `title_producer` and `TitleCardRequest` serve inserted and attached cards. An unregistered
producer fails loud through the existing `get_producer` error. The dry-run path goes through the same function,
so a planned command names a real PNG.
**Alternatives**: render the PNG in the decorator (impure, needs a scratch dir at decorate time, breaks
determinism of the pure transform); a second registry for overlay producers (duplicate seam, Principle VII).

### Transparent canvas = skip the fill
**Decision**: for `video`, `render_title_card` does not `paint()` the background. The Cairo ARGB32 surface starts
fully transparent, so alpha is 0 wherever there is no glyph, outline or shadow; `write_to_png` un-premultiplies.
Everything else (layout, outline, shadow, position, font resolution, fail-loud font errors) is the one code
path. The black card still paints `background_color` at `background_opacity`.
**Rationale**: a `background_opacity` of 0 would give the same canvas, but the event-wide default is `1.0`, so
a `video` card would need every style to override it; making the background kind decide it matches the user's
mental model (the choice is text on black *or* on video), and it keeps a hidden second knob out of the editor.

### Composite on the CPU on every profile, with a looped, alpha-faded still
**Context**: a card needs a window (`0..D`), fades that must be alpha fades (a faded-in black or white frame
would show), and a still that outlasts one frame.
**Decision**: for an overlay with fades, `_build_video_graph` builds the overlay input as
`-loop 1 -framerate <target fps> -t <window> -i card.png`, filters it
`format=rgba,fade=t=in:st=0:d=<in>:alpha=1,fade=t=out:st=<window-out>:d=<out>:alpha=1`, and composites with the
**CPU** `overlay` fragment whatever the profile (`CPUProfile` overlay: `overlay`, frames in system memory), so
the existing transfer logic inserts `hwdownload,format=nv12` before and `format=nv12,hwupload` after on VAAPI
and nothing on the CPU path. The `enable='between(t,0,<window>)'` expression is kept (`_overlay_enable`). An
overlay without fades keeps the exact existing graph and arguments (existing goldens unchanged).
**Why CPU on NVIDIA/Intel too**: `overlay_cuda` / `overlay_qsv` taking an RGBA still with alpha fades is
unverified on any host we have; only AMD (bridge) and CPU are exercised here. A uniform CPU composite is one
tested path; the cost is one download/upload per anchor segment, the same cost AMD pays.
**Alternatives**: `drawtext` (no Pango layout, no bundled fonts, preview/render drift; rejected by D-B);
pre-compose a card-over-frames video file (an extra encode and an intermediate); `overlay` with no fades and
`format=yuva420p` on the PNG (fades would have to be baked into several images).

### Clamp to the segment, and say so
**Context**: the anchor segment can be shorter than the card (a 3 s kept span under a 7 s card). Segment length
is known in `build_normalize_command` (`span_duration`, else the probed `clip.duration`), not in the decorator,
which never sees clip facts.
**Decision**: the clamp lives in `build_normalize_command`: `window = min(overlay.end, duration)`; the fades are
scaled down together so `fade_in + fade_out <= window` (the same proportional rule as the card config's
`_clamp_fades`, re-stated in `normalize.py` rather than imported, since the normalize layer must not import
`render/title`); and when `window < overlay.end` a warning is appended to `NormalizeCommand.warnings`:
`segment <identity>: card shown for <window> s of the <D> s asked, the segment is only <window> s long`.
Warnings already reach `RenderResult.warnings` (and the HDR warning is the precedent). The movie length is
unaffected either way.
**Rationale**: fail-loud does not fit here: a short opening clip is a legitimate edit, and refusing the render
would make the card unusable on it. The warning is the loud part; the render is never silently different.

### Chapter times
**Decision**: no change. `chapter_times` records a title-card span only for a segment with
`producer == "title"`; an over-video card inserts none, so the chapter records `null`, which is exactly what the
`movie-assembly` requirement already says for "a chapter with no title-card segment". Nothing reads the span
today (the API's `movie.chapters` carries names and starts only; the web has no card lane), and a measured span
for an overlay would be a window inside a source segment, not a segment, so it deserves its own change when the
timeline wants it. A test pins that chapter starts and ends equal the no-card control's.

### `RENDER_GRAPH_VERSION` is not bumped
**Decision**: no bump (stays at 7). **Which events turn stale**: none by this change. An event rendering with
`background: black` (or no `card:`) produces the same arguments and bytes as before; the fingerprint's engine
component is unchanged. An event whose chapter card is edited to `background: video` is stale through the
**editorial** hash (`document.to_dict()` includes the card mapping), exactly as any other card edit.
**Premise checked on the merged gate** (`title-card-model`, `RENDER_GRAPH_VERSION` 7): the gate's decorator raises a
typed `TitleCardError` for a card whose effective background is `video` ("not rendered by this engine"), before any
segment is encoded, so no event was ever rendered with a `video` card as a black one and no output exists to be
stale. No bump (stays at 7). This change removes that error, which the `title-card` delta records as a MODIFIED
requirement.

## Risks / Trade-offs

- [The whole anchor segment goes through the CPU bridge, not just the card seconds. For a long first clip on AMD
  that means decode on GPU, `hwdownload`, CPU overlay (a pass-through outside the window, but the frames still
  cross), `hwupload`, encode, for every frame] -> Bounded to one segment per over-video chapter; the rest stays
  on the GPU. Not measured yet: task 3.2 records the anchor segment's wall time against the no-card control in
  the PR so the supervisor can judge it. The fix, splitting the anchor into a card span and a remainder, needs
  clip durations at decorate time and adds an audio-priming seam at every chapter start; deferred on purpose.
- [A stream-copy-eligible anchor clip is now re-encoded] -> Intended (an overlay requires it, `copy_eligible`
  already says so); the concat's uniformity check still holds because the re-encoded segment conforms to the
  target.
- [Colour of the card over video: the RGBA still is converted to YUV by the filter graph's automatic scaler with
  its default matrix, which may differ slightly from the matrix the black-card path's encode uses for coloured
  text] -> White text with a black outline is neutral; tests assert luma only. Coloured text is not asserted
  either way.
- [Silent wrong output on the new path (the failure mode the v2 brief names for proxies: an unexercised graph
  that encodes but looks wrong)] -> The real-render tests decode frames and look for the text, and the
  control comparison fails if the window is empty, late or never ends.
- [Alpha-fade semantics differ across ffmpeg versions] -> The engine asserts ffmpeg >= 7.1 and the host has 8.x;
  the golden arguments pin the filter text, the real renders pin the behaviour.
