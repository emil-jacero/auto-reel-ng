All work is in `web/`, plus the HLD and `docs/editor-workspace.md`.
- **Node** runs only in podman (`docker.io/library/node:22`), with the repo root mounted and `-w /app/web`. Some web
  tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo. It intercepts PUT, POST and DELETE.

## 0. Gate

- [x] 0.1 Dependency gate: `clip-tab-and-player` MUST be archived, and both of these must succeed from the repo root:
  - `ls -d openspec/changes/archive/*-clip-tab-and-player`
  - `grep -q "Requirement: The Clip tab offers a clip's edits whether or not the track draws it" openspec/specs/web-app/spec.md`

  If either fails, STOP and report which check failed. Then confirm that `openspec validate plain-clip-bin --strict`
  reports no "Archive would refuse" note. If it reports one, re-copy that requirement from `openspec/specs/` and
  re-apply this change's edits to it.

## 1. Rules (web/src/edit)

- [x] 1.1 Add `binList.ts` (design D1). Verify with `binList.test.ts`. It must cover:
  - the order and the groups of Tjörn and of Sommarlov, before and after a removal;
  - "was N" and "from X" after a move within a chapter and after a move across chapters;
  - names of clips from another folder;
  - the `typed` flag;
  - a 400-clip event.
- [x] 1.2 Add `clipInfo.ts` (design D3). Verify with `clipInfo.test.ts`. It must cover:
  - frame rates 25/1, 30000/1001 and a variable one;
  - the ratios 1920×1080 → 16:9, 540×960 → 9:16, 1440×1080 → 4:3, and an odd one ("about …");
  - rotation 90, and the codecs AAC, `pcm_s16le` and none;
  - a null duration, and a clip without facts, neither of which gives a zero;
  - the cuts' words and the kept length with overlapping cuts.

## 2. Wiring (web/src/edit, web/src/timeline, web/src/cuts)

- [x] 2.1 `ClipBin` (design D2): the listbox, `listKey` with its unit test, pointer presses, the frame's watch, the
  row menu, and the ignored row's drag. It replaces `ChapterDrag` and `ClipOrderList` in the workspace's bin slot.
  Verify with `npm test` and `npm run check`, then in Playwright with the scenarios of "The clip bin lists every clip
  of the event as one plain list" and "The bin's list selects clips as the track does and opens their menu".
- [x] 2.2 The menu's status items, the group view's Include clips and `include-many` (design D5), with their unit tests
  in `clipMenu.test.ts` and a reducer test (one Undo step). Verify in Playwright with the scenarios of "Edit mode offers
  a clip's edits in a menu", "The Clip tab acts on several selected clips" and "Edit mode removes a missing clip from
  reel.yaml on request".
- [x] 2.3 The Cuts panel in the Clip tab, merged with the track part's cuts, and the row's "typed" (design D4). Verify in
  Playwright:
  - every scenario of "Edit mode lists, adds and removes a clip's cuts";
  - "A clip's preview sets cut times at the playhead and plays the clip as the movie will";
  - "A trim made on the timeline is an edit of the same draft as a cut made in the Cuts panel";
  - a typed cut on a clip with no ready proxy.
- [x] 2.4 `ClipInfo` and its Hide information preference (design D3). Verify in Playwright with the scenarios of "The
  bin shows what the page knows of the shown clip". Check the request log: selecting clips makes thumbnail requests
  only.
- [x] 2.5 Delete the old bin (design D6): the components and modules, the marks' actions and words, and the Clips help
  words. Remove `@dnd-kit` if nothing imports it, and update the dependency test. Verify with `npm test`, `npm run
  check` and `npm run build`, and report the bundle's change in kB. `grep -rn "Move marked\|Clear marks" web/src`
  must find nothing.
  Also sweep what the old bin left: the `.clip-item`, `.clip-order` and `.cuts-toggle` rules in `edit.css` (and the
  `listPaint.test.ts` checks of them), `cuts/times.ts`'s `toggleName`, and the comments that still cite `ChapterDrag` or
  `ClipOrderList` (`EventEditor.tsx`, `clipLength.ts`, `drag.css`, `edit.css`, `emptyChapter.ts`, `ChapterTools.tsx`,
  `layout.ts`, `workspace.css`).

## 3. Verification and record

- [x] 3.1 Run Playwright in Chromium and Firefox over every scenario of the delta (`web-app`, `clip-rotation`),
  including every MODIFIED requirement's scenarios. Also:
  - report the rows in view at 1280×720 and 1440×900, with the player and the information shown and hidden;
  - keep the windowing gates: no jump while scrolling 400 rows, and a scroll height within 5 %;
  - take screenshots of the bin in light and dark at 1440, 1100 and 390 px, and look at them for clipping and
    contrast.
  - The screen reader part is 3.1b: the Playwright run checked the accessibility tree and the live region only.
- [ ] 3.1b A person runs Orca with Firefox over the bin's list and checks that it announces a row's name, place
  and selected state, and the selection once. Not done by Playwright (Orca cannot run headless): leave this open
  until someone has done it, and name the gap in the PR description.
- [ ] 3.2 Record the change:
  - HLD D-28: amend "No List view". The bin is one plain list, and the non-pointer reorder path is the Clip tab's Move
    earlier, Move later and Move to…. Remove the marks from D-28's text, and note what the information shows and
    why there is no source resolution.
  - §6 item 10: the plain clip list is built.
  - The HLD's dependency section (the "dependency budget" paragraph): `@dnd-kit` left with `plain-clip-bin`, and the
    note that `@dnd-kit/react` will replace it is dropped.
  - `docs/editor-workspace.md`: rewrite rows 1.3 and 3.1–3.3 to the plain list and the information, and add a row for
    `plain-clip-bin`.
- [ ] 3.3 Gates: `npm test`, `npm run check` and `npm run build` in podman; `openspec validate plain-clip-bin
  --strict`.
