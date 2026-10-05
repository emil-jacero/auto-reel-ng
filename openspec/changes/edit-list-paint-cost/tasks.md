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
- [ ] 2.2 Rows skip drawing off screen (D1): `content-visibility: auto; contain-intrinsic-size: auto var(--clip-row-h)`
  on each clip row (`li.clip-item` of `ClipOrderList.tsx`, incl. ignored and removed rows), `--clip-row-h` the measured
  median collapsed-row height per container-query layout, static CSS only; no `overflow-anchor: none` on the page.
  Test: Playwright on the 400-clip event at 1280 and 390 — scrolling top→bottom in half-view steps keeps the top row
  within 1 px of where each step put it, scroll height at the end within 5 % of on opening; Tab walks rows in order;
  find-in-page of the 390th clip's name scrolls it into view (web-app scenarios).
- [ ] 2.3 Nothing clipped, drag still lands (D2, D3): fix every ring/indicator/overlay that paint containment cuts
  (inset ring, or drawn outside the contained `li`); make `ChapterDrag`'s `DndContext` measure while dragging if it
  does not already. Test: screenshots of a focused row, a drop indicator and a dragged row, light/dark, 1280/390,
  compared with `main`'s (whole, same look); Playwright drags the first clip of the 400-clip chapter to the last slot of
  the last chapter (auto-scroll over never-drawn rows) and asserts the draft order; keyboard-moves a clip 30 places down
  and asserts focus, ring in view and the announcement; the existing drag, marks/move-marked, keyboard reorder, rotate,
  card dialog and save-bar Playwright suites pass in Chrome and Firefox.
- [ ] 2.4 Other repaint sources (D5), only those 1.1's breakdown shows: the sticky save bar (`contain: paint` or its own
  layer only if the trace shows a raster win), large layers, any row `<img>` without `loading="lazy" decoding="async"`.
  Test: a re-traced drag shows the named source gone from the per-frame paint list; the save-bar Playwright suite and
  the toast placement checks pass.

## 3. The gate

- [ ] 3.1 Re-run 1.1's measurement on this branch (event-timeline requirement): Chrome 4x `slider` ×5 with `idle` ×5 in
  the same session, Firefox ×3, scrub and frame-step gates in both browsers. Test: Chrome median ≤ 2 % frames over
  25 ms, Firefox median ≤ 2 %, scrub ≥ 30 fps median, frame-step p90 ≤ 60 ms. If Chrome stays above 2 %: record the
  best achieved with the breakdown in the PR body, leave this task open and stop for the supervisor's decision (the
  ADDED requirement's figure is then set to the agreed value, with the evidence, in this change's spec delta).
- [ ] 3.2 Close #140's gate: if 3.1 meets 2 %, tick `timeline-zoom-slider`'s tasks 3.1 and 5.2 in
  `openspec/changes/archive/2026-10-05-timeline-zoom-slider/tasks.md`, each with a one-line status naming
  `edit-list-paint-cost` and the figures (the `event-timeline` zoom requirement has no frame figure, so its text is not
  changed). Test: `openspec validate edit-list-paint-cost --strict` passes; `grep -c '\- \[ \]'` on that archived file
  is 0.

## 4. Docs and gates

- [ ] 4.1 HLD (`docs/high-level-design.md`): a D-20 note (Edit page paint cost: per-row `content-visibility` with a
  remembered intrinsic size, zero clip-row renders on zoom/scrub/play, the before/after figures and the idle floor), a
  §4.10 bullet and a §6 phase-9 note naming `edit-list-paint-cost`. Test: a `docs.test.ts` case asserting
  `edit-list-paint-cost` is named in D-20, §4.10 and §6.
- [ ] 4.2 Gates: `npm test`, `npx tsc --noEmit` and `npm run build` in podman; the full Playwright run of 2.2–2.4 and
  3.1 in Chrome 154 and Firefox ≥ 155, light and dark, 1280 and 390 px, screenshots looked at; no request other than
  reads during any zoom, scrub, play or scroll.
