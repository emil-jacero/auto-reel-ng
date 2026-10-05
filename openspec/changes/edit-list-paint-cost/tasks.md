All tasks are in `web/` (plus the HLD and the archived `timeline-zoom-slider` tasks). Node runs only in podman
(`docker.io/library/node:22`); Playwright runs from SCRATCH only, Chrome 154 (`localhost/playback-research:chrome`) and
Firefox ≥ 155 (`localhost/pcm-audio-research:pw163`), light and dark, 1280 and 390 px, locators scoped to
`main:not([hidden])`, write routes intercepted, every screenshot looked at. Perf runs on a quiet host, load average
recorded per run.

## 1. Measure first

- [x] 1.1 Baseline and breakdown (design E1): on this worktree's `origin/main` build (port 8460, DB
  `arel_edit_list_paint_cost`, the 400-clip `2024-07-06 - Fyrahundra` event), run #140's `perf_slider.py` (copied into
  SCRATCH): Chrome 4x `idle` and `slider` ×5 each, Firefox `slider` ×3, the scrub and frame-step scripts; capture a CDP
  trace of one drag with and without the injected `content-visibility: auto` row style and attribute the frame cost
  (script / style+layout / paint / layerize+commit / raster) to page subtrees. Test: the numbers and the breakdown are
  in SCRATCH and the PR body, and reproduce #140's 30–34 % / 7.4–7.9 % within the run-to-run spread (if not, say so
  before changing anything).
  Status: on `origin/main` 12007da the Chrome 4x drag measured 33.8-64.0 % (median of five launches 44.1 %; 33.8-48.3 %
  at load 2.5-2.9, so above #140's 30-34 % on this busier host), idle 0-3.7 %, Firefox 0 %; with the row style injected
  6.8-9.4 % (#140: 7.4-7.9 %). Trace of one drag at 4x: layerize (`PaintArtifactCompositor::Update`) 9.8 s, paint 5.6 s,
  layout 3.2 s; with the injection 1.5 / 0.9 / 0.8 s; with the clip list removed 0.23 s of layerize. The rest under the
  injection is the list's drawn rows (about 60 ms of layerize each per drag; every inline `<svg>` icon is its own paint
  chunk) and the skipped rows (about 0.5 s together). Making the list's `<ol>` its own composited layer took layerize to
  0.41 s and the drag to 0-2.95 % (median 0.6 %); thumbnails, the sticky chapter header, the app header's backdrop
  filter, the panels above and an isolation group changed nothing measurable.
- [x] 1.2 Render count (design D4): a scratch-only patch (`React.Profiler` around the chapter list, `window.__rowCommits`)
  built in podman from a scratch copy of `web/`; Playwright drags the slider Fit→240, scrubs across 20 clips, plays 5 s.
  Test: the count is recorded; any non-zero count names the changed props (`changedProps`).
  Status: 0 renders of `ClipRow`, `RowBody`, `ClipOrderList`, `ChapterDrag`, `EventEditor`, `PosterPanel`, `SaveBar`,
  `MetadataForm` and `TimelineSection` for the zoom, the scrub (the video moved to another clip) and 5 s of play, in
  Chrome 154 and Firefox 155 (the counter build counted 400 `ClipRow` renders on opening, so it counts).

## 2. web/ — The clip list stops repainting

- [x] 2.1 Zero row renders (D4): make stable whatever 1.2 found reaching `ClipOrderList` / `ClipRow` on Timeline state
  changes (`useMemo`/`useCallback` in `EventEditor.tsx`, or the state kept in `web/src/timeline/`); skip if 1.2 found 0.
  Test: the 1.2 run shows 0 clip-row commits in Chrome and Firefox; `npm test` and `npx tsc --noEmit` pass.
  Status: skipped as the task allows: 1.2 found 0 renders on `main`, so nothing needed making stable.
- [x] 2.2 Rows skip drawing off screen (D1): `content-visibility: auto; contain-intrinsic-size: auto var(--clip-row-h)`
  on each clip row (`li.clip-item` of `ClipOrderList.tsx`, incl. ignored and removed rows), `--clip-row-h` the measured
  median collapsed-row height per container-query layout, static CSS only; no `overflow-anchor: none` on the page.
  Test: Playwright on the 400-clip event at 1280 and 390 — scrolling top→bottom in half-view steps keeps the top row
  within 1 px of where each step put it, scroll height at the end within 5 % of on opening; Tab walks rows in order;
  find-in-page of the 390th clip's name scrolls it into view (web-app scenarios).
  Status: the estimates are content-box heights (row less its 17 px of padding and border; a first try with the whole
  row's 89 px grew the page 15 % and failed the 5 % check). Chrome 154 and Firefox 155, 1280 and 390: 396-400 of 400
  rows skipped on opening, worst displacement 0.00 px over 78/87 half-view steps, scroll height +0.00 % / +0.10 %; Tab
  walks rows 1-33 in order; `window.find` of the 390th clip's name scrolls that row into view, drawn. `main` fails
  the skipped-rows check (0 of 400). `listPaint.test.ts` pins the rule, the four estimates, no script writing
  `--clip-row-h` and no `overflow-anchor: none`.
- [x] 2.3 Nothing clipped, drag still lands (D2, D3): fix every ring/indicator/overlay that paint containment cuts
  (inset ring, or drawn outside the contained `li`); make `ChapterDrag`'s `DndContext` measure while dragging if it
  does not already. Test: screenshots of a focused row, a drop indicator and a dragged row, light/dark, 1280/390,
  compared with `main`'s (whole, same look); Playwright drags the first clip of the 400-clip chapter to the last slot of
  the last chapter (auto-scroll over never-drawn rows) and asserts the draft order; keyboard-moves a clip 30 places down
  and asserts focus, ring in view and the announcement; the existing drag, marks/move-marked, keyboard reorder, rotate,
  card dialog and save-bar Playwright suites pass in Chrome and Firefox.
  Status: a focused row, the drop target and the lifted row are left out of the rule (`:not(:focus-within,
  [data-drop-before], [data-dragging])`); screenshots of the three, light/dark, 1280/390, equal `main`'s pixel for
  pixel in Chrome and Firefox, and a scratch build without the exclusion cuts the ring's left edge and the line's upper
  half (diffs of 94-2,496 px). Under a 20.25rem panel a row's tools already overflow the row (and the page below
  340 px, on `main` too), so the rule applies only from 20.25rem; there the rows equal `main`'s. Where rows have
  fractional heights (390: 99.09 px) a contained row snaps its content to whole pixels: glyph antialiasing differs,
  nothing moves by a pixel. `ChapterDrag` already measures while dragging (dnd-kit's default `WhileDragging`): no
  change. Drags in Chrome and Firefox: the first of 400 clips to the last slot of its chapter, the page wheeled over
  378-388 never-drawn rows (it showed and got position 400), and into a new last chapter; a keyboard lift 30 places
  down (position 35, handle focused with its ring in view, "moved to position 35 of 400"); Move down x30 keeps focus.
  The earlier suites (group drag, marks, move marked, keyboard scenarios, rotate rows, save bar) give the same results
  on this build as on `main` in both browsers (their stale parts fail the same way on both); a fresh record of marks,
  rotate marked, a far rotate, Move down, the card dialog, Reset and Move marked to… is identical on both builds.
- [x] 2.4 Other repaint sources (D5), only those 1.1's breakdown shows: the sticky save bar (`contain: paint` or its own
  layer only if the trace shows a raster win), large layers, any row `<img>` without `loading="lazy" decoding="async"`.
  Test: a re-traced drag shows the named source gone from the per-frame paint list; the save-bar Playwright suite and
  the toast placement checks pass.
  Status: 1.1's breakdown named one source left after 2.2: the layerize of the rows in view (every icon `<svg>` is a
  paint chunk). The played list `<ol>` is now its own composited layer (`will-change: transform`; tiled, 1150 x 35,599
  px on the 400-clip event, only tiles near the view rastered): a traced drag's layerize went 1.5 s -> 0.48-0.50 s
  and BeginMainFrame p95 34 -> 18.5-19.3 ms; during a zoom the list layer's paint count stays 1 (the root layer took
  every frame before). Not in the trace, so unchanged: the sticky save bar (hidden during a zoom; its suite gives the
  same results as on `main`), the app header's backdrop filter, the sticky chapter header, thumbnails (every row
  `<img>` already has `loading="lazy" decoding="async"`). The layer snaps the list to whole pixels: screenshots differ
  from `main`'s only in sub-pixel glyph and thumbnail antialiasing (zoomed, nothing moves). A loading thumbnail's
  shimmer (6 x 1.6 s) repaints its row until it ends, on `main` too.

## 3. The gate

- [x] 3.1 Re-run 1.1's measurement on this branch (event-timeline requirement): Chrome 4x `slider` ×5 with `idle` ×5 in
  the same session, Firefox ×3, scrub and frame-step gates in both browsers. Test: Chrome median ≤ 2 % frames over
  25 ms, Firefox median ≤ 2 %, scrub ≥ 30 fps median, frame-step p90 ≤ 60 ms. If Chrome stays above 2 %: record the
  best achieved with the breakdown in the PR body, leave this task open and stop for the supervisor's decision (the
  ADDED requirement's figure is then set to the agreed value, with the evidence, in this change's spec delta).
  Status (quiet host, load 0.8-2.0, one session; `out/gate-after.txt`, `out/gate-main-quiet.txt`): Chrome 154 at 4x,
  five launches of three drags: 0-1.17 % of frames over 25 ms, launch medians 0 / 0.37 / 0.36 / 0.37 / 0 % -> median
  0.36 % (p95 19.0-22.1 ms); idle 0.00 % in all 15; `main` in the same session 48.2-59.3 %, median 50.0 % (p95 74-93
  ms). Firefox 155, three launches: 0 % in all nine drags. Scrub / frame-step on the 400-clip event: Chrome 56.5 fps,
  p90 27.4 ms; Firefox 49.1 fps, p90 25.0 ms; on Grillning 56.6 / 50.5 fps, p90 27.9 / 23.5 ms. The gate is met; the
  requirement's 2 % stands unchanged.
- [x] 3.2 Close #140's gate: if 3.1 meets 2 %, tick `timeline-zoom-slider`'s tasks 3.1 and 5.2 in
  `openspec/changes/archive/2026-10-05-timeline-zoom-slider/tasks.md`, each with a one-line status naming
  `edit-list-paint-cost` and the figures (the `event-timeline` zoom requirement has no frame figure, so its text is not
  changed). Test: `openspec validate edit-list-paint-cost --strict` passes; `grep -c '\- \[ \]'` on that archived file
  is 0.

## 4. Docs and gates

- [x] 4.1 HLD (`docs/high-level-design.md`): a D-20 note (Edit page paint cost: per-row `content-visibility` with a
  remembered intrinsic size, zero clip-row renders on zoom/scrub/play, the before/after figures and the idle floor), a
  §4.10 bullet and a §6 phase-9 note naming `edit-list-paint-cost`. Test: a `docs.test.ts` case asserting
  `edit-list-paint-cost` is named in D-20, §4.10 and §6.
- [ ] 4.2 Gates: `npm test`, `npx tsc --noEmit` and `npm run build` in podman; the full Playwright run of 2.2–2.4 and
  3.1 in Chrome 154 and Firefox ≥ 155, light and dark, 1280 and 390 px, screenshots looked at; no request other than
  reads during any zoom, scrub, play or scroll.
