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
- [x] 2.2 `ChapterTools` `placement: 'bar'` in the bin (design D3):
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
- [x] 3.3 Gates in podman: `npm test`, `npm run check`, `npm run build`. Then run
  `openspec validate compact-bin-tools --strict`.

## 4. Round 2 (decisions 1a and 2b, review leftovers)

- [x] 4.1 Toolbar at most 88 px including its border (design D2): take 1 px off the bin toolbar's padding. Verify with
  Playwright: the toolbar's bounding box is 88 px or less, fine pointer, before and after a mark.
- [x] 4.2 Decision 2b (design D6):
  - `web/src/edit/wideBin.ts`: `WIDE_BIN`, `useWideBin()` and the pure `ignoredGroups` helper, with `wideBin.test.ts`
    (Tjörn gives one group `Main`; named chapters group in chapter order; a deleted chapter is skipped; none gives [])
  - one shared `namesIn(...)` for chapter names, reused by `nameNow` in `EventEditor.tsx`
  - `ClipOrderList.tsx`: export `IgnoredRow`, add `ignoredApart`, add `IgnoredBin` (h2 "Ignored clips", a caption per
    chapter that names it, `aria-labelledby` lists); update the file's header comment
  - `EventEditor.tsx`: `ignoredApart = inWorkspace && wide`; the block after `ChapterDrag` and before Add chapter
  - `workspace.css`: bin gap 8 px from 960 px only; `.ignored-chapter` weight; `.edit-ignored` inherits the flat
    chapter rules and is a container
  - a test: with `ignoredApart` no `.clip-ignored` in a chapter, and `.edit-ignored` sits after the last chapter
  Verify with Playwright (fine pointer, Tjörn, writes aborted): 1280×720 shows 3 whole played rows with at least 5 px
  to spare; 1440×900 shows 4; at 900 px `Main` lists `s1710004.mp4` after `s1710001.mp4` and there is no
  `.edit-ignored`; `Bara ignorerad` lists its clip directly below the chapter (not in the dev library, so not browser-checked); screenshots light and dark.
- [x] 4.3 Review leftovers:
  - drop the dead `.ws-bin > .edit-hint` rule in `workspace.css` (and `.edit-hint` from its `:is()`)
  - drop the redundant nested `@media (width >= 960px)` inside the coarse-pointer block of `workspace.css`
  - fix the `newClipsLine` doc comment in `clipsHelp.ts`
  - `clipsHelp.test.ts`: `deepEqual` for where `NEW_CLIP_NOTE` is placed
  - `chapterBar.ts`: type `place` (not `unknown`)
  - HelpToggle's `title` is global: stated in D2, keep it or scope it to the bin
  - `common.tsx` docstring "when narrow" made accurate
  - decision 1a: bin status is icon-only with a fine pointer, words visually hidden and as the tooltip, icons
    distinct per status; verify in Playwright that "New, not yet in reel.yaml" is the new clip's hidden text and the icon's tooltip and no word is
    visible, at 1280×720 and at 900 px (still icon-only), and that a coarse pointer shows the word
- [x] 4.4 Re-verify with a coarse pointer (`hasTouch`) that the 44 px areas and the Move-before-Rotate DOM order
  hold (design D4), and that 400-clip windowing still paints only rows near the view (the dev library has no 400-clip event: the
  CSS contract tests in `listPaint.test.ts` hold, and the compact rows' `content-visibility` is unchanged).
- [x] 4.5 Strict pass bar and docs:
  - Tjörn, fine pointer, nothing marked, light and dark: at least 3 whole played rows at 1280×720, all 4 at 1440×900;
    screenshots, Read them
  - `docs/editor-workspace.md` (around line 122): replace "(the ignored clip counts as a row)" with "(played rows;
    from 960 px the ignored clips are listed after the chapters)"; HLD D-28: one sentence to the same effect
- [x] 4.6 Gates in podman: `npm test`, `npm run check`, `npm run build`, then
  `openspec validate compact-bin-tools --strict`.
