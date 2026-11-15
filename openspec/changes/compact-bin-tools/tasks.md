All tasks are in `web/`. Node runs only in podman (`docker.io/library/node:22`). Playwright runs from the scratchpad,
never from the repo, with PUT/POST/DELETE intercepted. The layout targets are fine-pointer sizes. Check touch
(`hasTouch`, coarse pointer) for overlap and 44 px areas only.

## 1. Bin width and rows (web/src/edit, web/src/edit/workspace)

- [x] 1.1 Bin width `clamp(240px, 22vw, 320px)` on `html[data-workspace]` (design D1). Verify with Playwright:
  - the bin is 282 px at 1280×720 and 317 px at 1440×900
  - the picture is no smaller than before at either size
  - no horizontal scroll from 960 to 1440 px
- [x] 1.2 Two-line compact rows from the bin's width, with tighter padding, and `--clip-row-h` re-measured
  (design D4). Coarse-pointer rows keep the 44 px rules. Verify with Playwright:
  - row height is at most 70 px with a fine pointer
  - no control overlaps another at 240 and 320 px wide
  - with a coarse pointer, no touch areas overlap
  - 400-clip windowing still holds: only rows near the view paint

## 2. Toolbar and chapter header (web/src/edit)

- [x] 2.1 Marks line in the bin (design D2):
  - two fixed rows, sticky at the bin's top
  - Rotate buttons icon-only, with their names in hidden text and `title` tooltips
  - the "Move marked to…" label visually hidden, the picker filling the row
  - the bin's scroll padding includes the toolbar height
  Verify with Playwright: the toolbar is at most 88 px tall; no row moves on the first mark; the toolbar stays sticky
  while the bin scrolls; a row reached by keyboard reorder is not hidden under the toolbar.
- [ ] 2.2 `ChapterTools` `placement: 'bar'` in the bin (design D3):
  - Move up, Move down and Delete go into the header bar after the count, as icon buttons with names and tooltips
  - Edit Titlecard becomes icon-only in the bin
  - notes and Delete's refusal stay as lines under the bar
  Verify with Playwright: the header is at most 36 px tall; the buttons are named "Move chapter Kvällen up" and so
  on; after Move up, focus stays on the button; Delete's refusal shows; the stacked page is unchanged.
- [x] 2.3 Drop the bin's new-clip line in the workspace, and add the "joins `reel.yaml` once…" sentence to the
  Clips help while a new clip waits (design D5). Update `clipsHelp.test.ts`. Verify on `Badutflykt - Varberg` with
  Playwright: the top bar summary says "adds 1 new clip", and the line is gone.

## 3. Verification and docs

- [x] 3.1 Pass bar with Playwright on `Två kapitel - Tjörn`, fine pointer, nothing marked, both themes:
  - at least 3 whole clip rows visible at 1280×720, all 4 at 1440×900
  - screenshots at 1280×720, 1440×900 and 390 px
- [x] 3.2 Docs:
  - `docs/editor-workspace.md`: note the bin's width and the compact tools under slice 1, and update 1.4's "bin
    240 px"
  - HLD D-28: one line on the bin's width
- [ ] 3.3 Gates in podman: `npm test`, `npm run check`, `npm run build`. Then run
  `openspec validate compact-bin-tools --strict`.
