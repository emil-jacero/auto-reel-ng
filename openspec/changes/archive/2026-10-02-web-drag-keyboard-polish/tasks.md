## 1. web/ — the pure part and its test

- [x] 1.1 In `src/edit/dragSlots.ts`, add `stepChapter(model, identity, staysHome, from, delta)` next to `stepSlot` (design, "`stepChapter` in `dragSlots.ts`"): the first slot of the next / previous reachable chapter, `null` at either end, for a missing clip and while one chapter is listed. Add `src/edit/dragSlots.test.ts` on Node's `node:test` / `node:assert/strict`, importing `./dragSlots.ts`. First read `web/package.json` and `web/tsconfig.json` on main: `web-toast-and-dialog-layers` adds the runner (`"test": "node --test --experimental-strip-types src/**/*.test.ts"` and `"exclude": ["src/**/*.test.ts"]`). If they are there, change neither file; if not, add exactly those two lines, character for character (no dependency, `package-lock.json` unchanged) (design, "A test for the pure part").

  Verify: `npm test` in the `node:22` container passes with these cases, on `2024-08-20 - Två kapitel - Tjörn`'s orders (`r0` = `[s1710001.mp4]`, `r1` = `[Kvällen/s1710002.mp4, Kvällen/s1710003.mp4, Kvällen/s1710004.mp4]`, listed `[r0, r1]`):
  - `s1710001.mp4` from `r0:0`, delta 1, gives `r1:0`; from `r1:2`, delta -1, gives `r0:0`; from `r0:0`, delta -1, and from `r1:0`, delta 1, give `null`
  - `Kvällen/s1710002.mp4` (own `r1`) from `r1:1`, delta -1, gives `r0:0` (the gap before `s1710001.mp4`); from `r0:1` (past it), delta 1, gives `r1:0`
  - `staysHome` true gives `null` both ways; one listed chapter gives `null`; an unknown identity and a `from` in an unlisted chapter give `null`
  - a listed empty chapter `r2` (`orders` maps it to `[]`): `s1710001.mp4` from `r1:0`, delta 1, gives `r2:0`, and a deleted chapter left out of `listed` is passed over
  - `npx tsc --noEmit` and `npm run build` still pass, and `git diff -- web/package-lock.json` is empty
  - `npm test` also runs any other `*.test.ts` already on main, and they pass

## 2. web/ — the keyboard drag

- [x] 2.1 In `src/edit/ChapterDrag.tsx`, extend `coordinateGetter` (design, "The getter" and "Getting the target into view"): `PageDown` → `stepChapter(…, 1)` and `PageUp` → `stepChapter(…, -1)`, both calling `event.preventDefault()` before the lookup; the shared `y` computation, `slot.current` and every other key stay as they are. When the computed `y` lies outside the window, scroll the page by `y − currentY` with the sensor options' `behavior` and return `undefined`; if that does not land the copy on the target, use the named fallback. Update the comment above the getter, and append the Page sentence to `ACROSS`.

  Verify, from the scratchpad, with Playwright (`mcr.microsoft.com/playwright/python:v1.49.0-noble`, `--network host`, locators scoped to `main:not([hidden])`, writes intercepted as the brief says), on the agent's own service over a fresh `npm run build`:
  - the scenarios "Page Down jumps to the next chapter from the keyboard", "Page Up jumps to the chapter before from the keyboard" and "Page keys with one chapter or a missing clip move nothing", with the live-region texts read through a `MutationObserver` installed before the lift, and `window.scrollY` read before and after each key
  - "Page Down and Page Up cross a long chapter in one press" on a `2024/2024-09-15 - Stor dag` of 400 symlinked `c0001.mp4`…`c0400.mp4` plus `Kväll/k001.mp4`…`k003.mp4` (library copy only): after each key the bounding boxes of `.clip-item[data-drop-before]` (or the area) and `.clip-drag-overlay` lie inside the window, below the header, at 1280 × 900 and 390 × 844, light and dark, with and without `reduced_motion='reduce'`; look at the screenshots
  - the instructions text (`#DndDescribedBy-…` in `<body>`) contains the Page sentence on `Två kapitel` and not on `Grillning`
  - Home, End and the arrows behave as on main; a drop after a Page jump saves the same body as after the equivalent arrows (`PUT …/reel` intercepted and aborted)

## 3. web/ — the pointer's auto-scroll

- [x] 3.1 In `src/edit/ChapterDrag.tsx`, set `AUTO_SCROLL` to `{ acceleration: 34, interval: 20, threshold: { x: 0.2, y: 0.2 } }` and rewrite the comment above it with the reason (the unclamped ratio, the timer, why 10 and 25 failed) (design, "Auto-scroll"). The object stays a single constant.

  Verify, from the scratchpad, with Playwright in the real browser (`localhost/playback-research:chrome`, production build) on the `Stor dag` fixture of 2.1, 1280 × 900:
  - lift `Kväll/k001.mp4` with the mouse (10 px past the activation distance, 10 steps), move to `y = 0` and hold 2 s sampling `scrollY` every 100 ms: the 2 s total is between 1,200 and 4,000 px (600-2,000 px/s)
  - hold at `y = 90` (a tenth of the window) for 2 s: between a quarter and three quarters of the edge distance
  - move out of the zone (`y = 450`): `scrollY` stops changing within 100 ms
  - the bottom edge (`y = 899`) and a pointer at `y = -40` (dragged out of the window) are sampled and recorded; the second is not bounded by the spec
  - the old constant on main's build, sampled the same way, is recorded for contrast
  - from `y = 20` the time the page takes to reach `c0001.mp4` is recorded, with the old constant's for contrast (the earlier change's 30 s was not reproducible in the headless browser)
  - the page does not scroll horizontally, and a release over `c0001.mp4`'s upper half gives position 1 of 401 with the second chapter playing 2 clips ("Reaching a chapter out of view")
  - if a bound fails, change `acceleration` or `interval` and measure again; the spec's bounds are the contract, not the numbers

## 4. Docs and validation

- [x] 4.1 In `web/README.md`: in the Edit-mode paragraph, add the Page keys beside "past a chapter's first or last clip the arrows cross into the chapter before or after". Read "Checks" on main: if it still says there is deliberately "**no test runner and no browser automation**", replace it with the new position (the type check is `tsc --noEmit`; `npm test` runs the pure functions under Node's built-in runner, with no dependency; browser automation is still not committed), and list `npm test` with its podman form among the toolchain commands; if `web-toast-and-dialog-layers` already did, leave it.

  Verify: `grep -n "Page Down" web/README.md` hits the Edit-mode paragraph, and `grep -n "no test runner" web/README.md` prints nothing.
- [x] 4.2 Run the gates: in the `node:22` container `npx tsc --noEmit`, `npm run build` and `npm test`; `.venv/bin/python -m pytest -m "not requires_db" tests/test_api_web_mount.py`; and `git status --short` lists only `web/` paths (`web/src/edit/dragSlots.ts`, `web/src/edit/dragSlots.test.ts`, `web/src/edit/ChapterDrag.tsx`, `web/README.md`, and `web/package.json` and `web/tsconfig.json` only if task 1.1 added the runner) and the change's own directory; no Playwright script, screenshot or `.playwright` directory is in the worktree. `openspec validate web-drag-keyboard-polish --strict` passes.
