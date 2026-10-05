## Why

`timeline-zoom-slider` (PR #140, archived as `openspec/changes/archive/2026-10-05-timeline-zoom-slider/`) landed with
one gate open: its tasks 3.1 and 5.2 required a Zoom-slider drag on the 400-clip fixture, Chrome at a 4x CPU throttle,
to keep at most 2 % of frames over 25 ms. Chrome measured **30–34 %** (p95 55–66 ms); Firefox 0 %. The slider thumb
alone (zoom switched off in a scratch build) costs 1.4–2.1 %, the idle page 0–0.6 %. The lander's profile showed that
most of a zoom frame is the **Edit page's paint and layerize of the 400-row clip list under the Timeline**, not the
Timeline: with `content-visibility: auto` injected on the rows the same drag measured **7.4–7.9 %** (p95 ≈ 30 ms)
(archived `design.md` Risks, `tasks.md` 3.1 status; scripts `scratchpad/verify/v2/timeline-zoom-slider/perf_slider.py`,
`prof.py`). The archived design named this "a separate change: it touches the clip list, its focus rings and dnd-kit's
measuring" — this is that change.

It serves D-20 (the Timeline is ours, in `web/src/timeline/`, and must stay smooth on large events) within D-8's
frontend budget (no new dependency). HLD §6 phase 9 (GUI v2), a follow-up to `timeline-zoom-slider`. No §8 research item
is involved: the evidence is the measurement above, which this change re-runs.

## What Changes

- **Edit mode's clip rows skip rendering while off screen**: `content-visibility: auto` with
  `contain-intrinsic-size: auto <estimate>` on each clip row (`li.clip-item` in `ClipOrderList.tsx`), the estimate a
  measured per-layout row height held in a CSS custom property, so the page's scroll height and scroll position do not
  jump as rows come into view. Focus rings, the drop indicator and the drag overlay that today draw outside a row are
  kept visible under the row's paint containment (drawn inset, or by an element outside the contained box).
- **Other repaint sources the profiler names are removed or contained**: the measured candidates are the sticky save
  bar (`.save-bar`, `box-shadow: var(--shadow-lg)` over a scrolling page), the marks line, large composited layers,
  and thumbnail decoding (`ClipThumb.tsx` already has `loading="lazy" decoding="async"`; any other row image gets them).
  Only sources the profile shows to cost a zoom frame are changed.
- **Zoom, scrub and play render no clip row**: Timeline state stays inside `web/src/timeline/`; any prop or context
  that today changes identity on a Timeline state change and reaches `ClipOrderList` is made stable. Proven by a render
  count in a scratch-only build (never committed).
- **The #140 gate is re-run** (same fixture, same 180-move drag, Chrome 4x and Firefox), with the scrub and frame-step
  gates. Target ≤ 2 % in Chrome. If 2 % is not reachable, the best achieved, with the breakdown, is reported and the
  change stops there for the supervisor's decision (the new requirement's figure then follows that decision).
- **The edge tools step aside while a zoom is in progress** (supervisor decision 2026-10-05, after this change's first
  run stopped blocked): once `clip-edge-trim` (#141) merged, the slider drag on 400 clips rose from a 0.36 % median to
  9.34 %, because every zoom re-renders and re-positions the in-view Trim In / Trim Out tools (each tool's `x` changes,
  so `memo` cannot hold; a scratch build without them measured 0.32-3.05 %). The 2 % requirement is not relaxed.
  Instead the Track leaves the edge tools out from a zoom's first input until it settles (slider release, or ~150 ms
  after the last Ctrl/Cmd+wheel, pinch, button or `=`/`-` input), exactly as it already leaves them out behind a
  rippling drag (`d5f1e2f`), keeps the one tool that holds focus, and renders them once on settle; the hover cursor
  returns without a pointer move.
- If the gate is met, `timeline-zoom-slider`'s open tasks 3.1 and 5.2 are ticked in the archive with a status line
  naming this change; the "track zooms" requirement in `event-timeline` needs no wording change (it has no numeric
  frame gate — the gate is this change's ADDED requirement).

## Non-goals

- Virtualising the clip list (unmounting off-screen rows): it would break dnd-kit's sortable measuring, keyboard
  reorder's focus and find-in-page; `content-visibility` keeps every row in the DOM and in the accessibility tree.
- Any other change to the Timeline's own rendering (windowing, `LIVE_OVERSCAN`, the zoom math) — `timeline-zoom-slider`
  owns those and its numbers show the Timeline is not the bulk of the cost. The one Timeline change is the edge tools'
  zoom-settle omission above.
- Raising `MAX_PPS`, a drag preview, or changing any gate other than the slider-drag one.
- The read view's clip list (no Timeline on that page since `timeline-zoom-slider`).
- Engine, API, CLI, scheduler: untouched.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `event-timeline`: ADDED requirement — zooming, scrubbing and playing re-render no clip row of the Edit page, and a
  Zoom-slider drag on a 400-clip event meets a frame gate in Chrome (4x throttle) and Firefox.
- `web-app`: ADDED requirement — Edit mode's clip list skips drawing rows out of view without moving the page, and
  every row stays focusable, readable by assistive technology, draggable and reorderable by keyboard.
- `event-timeline`: MODIFIED requirement "In Edit mode a clip block's edges are Trim In and Trim Out tools" — the edge
  tools do not exist while a zoom is in progress (except the focused one) and return once it settles.

## Impact

- Package: `web/` only (`src/edit/` CSS and `ClipOrderList.tsx`, `src/edit/EventEditor.tsx` prop stability, possibly
  `src/timeline/TimelineSection.tsx`), `src/timeline/Track.tsx` / `Timeline.tsx` and a pure zoom-settle helper in
  `src/timeline/` (edge tools out while zooming), plus `docs/high-level-design.md`. Neither the CLI nor the API is touched
  (Principle V: nothing to reach).
- Rendered output for identical inputs: unchanged — no `RENDER_GRAPH_VERSION` bump. Staleness fingerprint inputs:
  unchanged.
- `reel.yaml` / project `config.yaml` schema: unchanged. No Alembic migration, no rescan.
- No new dependency (D-8). `content-visibility` and `contain-intrinsic-size: auto` are supported by both browser
  targets (Chrome 154, Firefox ≥ 155).
