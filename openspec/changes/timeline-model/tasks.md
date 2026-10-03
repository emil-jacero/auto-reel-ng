## 1. web/ — units, facts, frames, layout

- [ ] 1.1 Create `web/src/timeline/model.ts` with `Ms`, `ClipFacts`, `ModelError`, `clipFacts`, `frameMs`, `nearestFrame`, `minCutMs`, `layout`, `clipAt`, `timeToPx`, `pxToTime` (design, Decisions "whole milliseconds", "Facts are arguments", "Layout and lookup"), with `model.test.ts` (`npm test`). Cases: 1,015 ms at 29.97 fps gives 1,001 and at 50 fps 1,020; every fps in 23.976, 24, 25, 29.97, 30, 50, 59.94 returns whole milliseconds for 0..10,000 ms; `clipFacts` throws `ModelError` for 0, negative, `NaN`, `Infinity` duration and for a rate of 0 or negative; layout of 24.96 / 6.08 / 0.48 s (starts 0, 24,960, 31,040; total 31,520); `clipAt` at -5, 0, 24,959, 24,960, the total and past it; an empty list; 137 px at 40 px/s is 3,425 ms.

  Verify: `npm test` (node:22 container) passes; `npx tsc --noEmit` and `npx tsc --noEmit -p tsconfig.test.json` are clean.

## 2. web/ — zoom and windowing

- [ ] 2.1 Add `MIN_PPS`, `MAX_PPS`, `DEFAULT_PPS`, `View`, `clampPps`, `zoomAt`, `fitPps`, `tickStepMs` (design, "Zoom"). Tests: the spec's zoom scenarios (anchor x = 300 keeps 17.5 s and gives scroll 1,100; clamps at 240 and 4; scroll never negative nor past the end; 60 s fits 1,200 px at 20, 3 s at 240; zero length gives 40); property loop over 200 random views and factors that the time under the anchor moves by less than one pixel's worth unless a clamp applied; `tickStepMs` is 1,000 ms at 80 px/s and 600,000 ms at 4 px/s; `ModelError` for a non-positive `pps` or width.

  Verify: `npm test` passes, `tsc` clean.
- [ ] 2.2 Add `visibleClips` and `visibleTicks` (design, "Windowing"): binary search over the layout's starts, strict overlap (a clip that only meets the margin's edge is out). Tests: the spec's 5,000-clip scenario returns clips 599 to 600 at 40 px/s, scroll 600,000, width 800, margin 200; one 600 s clip at 240 px/s with the view inside it; a view past the end returns null; the first and last clip at scroll 0 and at the far end; a counting wrapper around the layout's `startsMs` array (a `Proxy` that counts reads) shows at most 40 reads for 5,000 clips and no more than 4 more reads for 50,000; ticks at 40 px/s cover only the view and margin.

  Verify: `npm test` passes, `tsc` clean.

## 3. web/ — cut spans, rectangles, ordinals

- [ ] 3.1 In `web/src/preview/playback.ts`, give its two `../cuts/times` imports the `.ts` extension (no other edit), then add `cutSpans` (= `skipSpans`), `movieLengthMs`, `cutRects`, `cutOrdinals` to the model (design, "Reuse how the render joins cuts", "Cut spans, rectangles, names"). Tests: a smoke test that imports `../preview/playback.ts` under Node and calls `skipSpans` and `toMs` (it fails if the extension is lost); overlapping cuts 1 to 3 s and 2 to 4 s give one span, 7 s of a 10 s clip, two rectangles; a cut 5 to 7 s on a 6.08 s clip is drawn to 6,080 ms; a cut wholly past the end and an empty cut have no rectangle; removed cuts have no rectangle and no ordinal; `movieLengthMs` over three clips with cuts; **prototype defect 2**: cuts listed 14 to 17.2 s then 0 to 2.4 s get ordinals 2 and 1, and three cuts with equal starts get 1, 2, 3 by end then position (no two share an ordinal).

  Verify: `npm test`, `tsc` and `npm run build` pass; `git diff web/src/preview/playback.ts` is two changed lines.

## 4. web/ — trim limits, snapping, trimEdge

- [ ] 4.1 Add `trimLimits` (design, "Trim limits"). Tests: **prototype defect 1**: at 25 fps the cut 0 to 2.4 s has end limit 120 ms (not 100) and at 29.97 fps 100 ms, each equal to `frameMs(3, fps)`; a property loop over fps in 23.976, 24, 25, 29.97, 30, 50, 59.94 and 100 random on-grid edges that the min-length limit is on the grid (`nearestFrame(limit) === limit`) and the span is at least `minCutMs`; neighbour limits for cuts 0 to 2.4 s and 14 to 17.2 s on a 24.96 s clip (start 2,400..17,080, end 14,120..24,960); overlapping cuts 1 to 3 s and 2 to 4 s (second cut is not a neighbour; ranges contain 1, 3, 2 and 4 s and none is inverted); a 5.000 to 5.050 s cut keeps 5,050 in its end range; a 0.08 s clip gives `[80, 80]` and `[0, 0]`; removed cuts are not neighbours; touching cuts (end 3 s, start 3 s) limit each other exactly at 3,000.

  Verify: `npm test` passes, `tsc` clean.
- [ ] 4.2 Add `snapTo`, `snapCandidates`, `trimEdge` (design, "Snapping and `trimEdge`"). Tests: the spec's four snap scenarios (7,900 to 8,000 at 40 px/s; held by a 7,800 limit at 10 px/s with `snappedTo` null; 5,317 gives 5,320 at 25 fps with no snap; tie at 8,000 and 8,100 in either order gives 8,000); `snapCandidates` sorted, de-duplicated, includes the playhead only inside the clip; a snap at exactly 8 px is taken and at 8.01 px is not; a limit reached is returned exactly and not moved to the grid (neighbour edge 3,007 ms at 25 fps); `trimEdge` is a fixed point (`trimEdge(.., r.ms ..).ms === r.ms`) over 200 random drags; an out-of-range index throws.

  Verify: `npm test` passes, `tsc` clean.

## 5. Bundle and dependencies

- [ ] 5.1 Record the bundle delta. In the node:22 container run `npm ci && npm run build` on `origin/main` (a clean worktree or `git stash`) and on this change; `gzip -9 -c` each `dist/assets/*.js` and `*.css` and write both totals in the notes for task 6.1 (D-20). An unwired model is expected to add 0 bytes; any other result is investigated before D-20 is written. Add a test in `model.test.ts` that reads `web/package.json` and asserts `dependencies` is exactly `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`, `react`, `react-dom`, and that `model.ts` has no import except `../cuts/times.ts` and `../preview/playback.ts` (a regex over the source's `import` lines).

  Verify: `npm test` passes; the two totals are written down.
## 6. Docs and gates

- [ ] 6.1 In `docs/high-level-design.md` add **D-20** after D-19 (the timeline is built in the repo, no library, `web/src/timeline/`, `@dnd-kit` for reorder only, windowed, the model in whole milliseconds with facts as arguments; test runner = the existing `node:test`, no vitest; first slice = trim and analysis overlays on one timeline, one `<video>` with a `src` swap at clip boundaries, reorder stays list-based, no waveform lane; opens only for an event whose proxies are prepared; the bundle delta task 5.1 measured; the research numbers: +5.6 KB gz prototype versus +68.5 KB for the nearest library, 60 fps drag to 400 clips at 4x), noting that the research calls it D-18 and that D-21 (the proxy contract) is recorded by the proxy changes. Update the §4.10 "v2" bullet (model landed, UI pending) and the §6 phase 9 line, and correct the §4.10 sentence "no test runner" (about line 459) to say `npm test` runs Node's built-in runner for pure modules. Update the `web/README.md` timeline/test section by one paragraph naming `web/src/timeline/model.ts` and its units (whole milliseconds).

  Verify: `grep -n "D-20" docs/high-level-design.md` finds the entry and its references; `grep -n "D-18\\|D-19" docs/high-level-design.md` still finds the two existing entries unchanged; `openspec validate timeline-model --strict` passes.

- [ ] 6.2 Run the frontend gates in the node:22 container: `npm ci`, `npx tsc --noEmit`, `npx tsc --noEmit -p tsconfig.test.json`, `npm test`, `npm run build`. Then a regression smoke in real browsers from the scratchpad only (never in the repo): serve the built `web/dist` with a dev library on `PORT`, and in Chrome 154 and Firefox 155 load the event list, an event page and Edit mode's Cuts panel with its preview open, in light and dark at 1280 and 390 wide; look at each screenshot; no console error and the preview's cut bar unchanged (this change wires nothing, so any difference is a regression from the `playback.ts` import edit). Also run `.venv/bin/python -m pytest -m "not requires_db"` once to confirm nothing outside `web/` moved (expected: untouched).

  Verify: all commands exit 0; the Playwright script's output lists each page, browser and scheme; `git status` shows only `web/src/timeline/`, `web/src/preview/playback.ts`, `web/README.md`, `docs/high-level-design.md` and `openspec/changes/timeline-model/`.
