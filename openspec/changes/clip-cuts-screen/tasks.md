## 1. Gate

- [ ] 1.1 Confirm that `openspec/changes/archive/*-chapter-management-screen` exists on main and that `openspec/changes/chapter-management-screen` does not. Stop and report to the supervisor if not. Then re-check the names this change builds on (design, "Context", "The draft model"), and stop and report on any mismatch:
  - `web/src/edit/draft.ts` exports `Draft` (with `chapters`, `orders`, `removed`, `metadata`), `Baseline` (with `read`, `chapters`, `original`), `isDirty(baseline, draft)`, `buildWriteBody(baseline, draft)`, `adoptedNewCount` and `keptOriginal`. Its one helper `writtenFromView(baseline, draft)` serves all three, and the file imports only with `import type`.
  - `web/src/edit/EventEditor.tsx` has `reduce`, `afterEdit`, `submit` (guarded by `dateIncomplete`), `summarize` (with the chapter parts), `announce`, `resets` and `dateIncomplete`, and G1's Move clips still moves a row into another chapter's `ClipOrderList` (the reason for the panel store)
  - `web/src/edit/ClipOrderList.tsx` has `ClipRow`, `RowBody` and `nameOf`, and is keyed by `chapterKey`
  - `web/src/edit/SaveBar.tsx` takes `dateIncomplete`
  - `web/src/ui/Icon.tsx`'s `IconName` has `plus` and has neither `scissors` nor `chevron-down`
  - `web/src/events/EventDetail.tsx` has `ReadyView` and `ChapterPanel`
  - `ls openspec/changes/` shows no other change touching `web/src/edit/` or `web/src/events/EventDetail.tsx`

  Re-base the MODIFIED block in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`: take the landed text of "Saving an edit writes only what the operator changed" and carry this change's edits onto it. Those edits are the cut line in the visible list, the two undone cut edits, the two cut bullets ("A clip whose cuts changed", "A chapter that plays a NEW clip whose cuts changed"), "or any cut" in the no-chapters bullet, and the five cut scenarios.

  Verify: `openspec validate clip-cuts-screen --strict` passes, and a `diff` of the requirement's main text against the change's text shows only the edits listed above.

## 2. web/ — the model (pure)

- [ ] 2.1 Add `src/cuts/times.ts` (design, "Times: forms, parsing, writing", "What a cut must satisfy", "The reason of a cut made here", "Copy"): `Trim`, `parseTime`, `formatTime`, `formatLength`, `spokenLength`, `cutOutSeconds`, `checkCut`, `checkRestore`, `KNOWN_REASONS`, `CUT_REASON_LABEL` (not `REASON_LABEL`, which `events/labels.ts` already exports), `reasonWords`, and the refusal and announcement copy as exported functions or constants. Type-only imports.

  Verify: a scratch script in `<scratchpad>/verify/clip-cuts-screen/`, never committed, runs under `node --experimental-strip-types` in `docker.io/library/node:22`, imports `times.ts`, and asserts:
  - `parseTime`:
    - accepted: `0` → 0; ` 75.5 ` → 75500; `1,5` → 1500; `1:15.5` → 75500; `0:00:01.25` → 1250; `1:01:15.5` → 3675500; `90:00` → 5400000; `0:58.1` → 58100
    - `unreadable`: `1:5`, `1:60`, `-1`, `+1`, `1.2.3`, `1:2:3`, `abc`, `1:00:60`
    - `too-precise`: `0.1234`
    - `empty`: `''` and `'   '`
  - `58100 / 1000 === 58.1`
  - `formatTime`: 0 → `0:00`, 1.5 → `0:01.5`, 62.35 → `1:02.35`, 3675.5 → `1:01:15.5`, 3.2033333 → `0:03.203`, 59.9996 → `1:00`
  - `formatLength`: 1.5 → `1.5 s`, 3.25 → `3.25 s`, 60 → `1:00`, 62.5 → `1:02.5`
  - `spokenLength`: 1 → `1 second`, 1.5 → `1.5 seconds`
  - `cutOutSeconds`:
    - `[0,3]` and `[2,4]` → 4
    - `[0,2]` and `[2,4]` → 4
    - `[4,5]` and `[0,1]` → 2
    - `[0,1.5]` → 1.5
    - `[]` → 0
  - `checkCut` against `[{in: 0, out: 1.5}]`:
    - `1`/`2` → `overlap` at the start field, clash 1
    - `1.5`/`2` → ok
    - `3`/`2` → `order` at the end field
    - `''`/`2` → `empty` at the start field
    - `1`/`''` → `empty` at the end field
    - `1:5`/`2` → `unreadable` at the start field
    - a removed listed cut does not clash
  - `checkRestore`: with `r0 = [0, 1.2]` removed and `a1 = [1, 2]` listed, restoring `r0` → `overlap`, clash 2; with `a1 = [1.2, 2]` instead → ok (touching)
  - `reasonWords`: `black` → `Black frames`, `manual` → `Cut by hand`, `sunset noise` → `“sunset noise”`, `null` → `—`
- [ ] 2.2 In `src/edit/draft.ts`, add the cut model (design, "The draft model"): `CutKey`, `DraftCut`, `Cuts`, `Draft.cuts`, `Baseline.cuts`, `readCuts`, `cutsOf`, `addCut`, `removeCut`, `restoreCut`, `changedCuts` and `cutChanges`. Add `changedCuts` to `isDirty`, the NEW-clip predicate and the no-chapters trigger to `writtenFromView`, and the `clips` merge to `buildWriteBody`. Keep the file free of runtime imports.

  Verify:
  - `npx tsc --noEmit` passes in the node:22 container once 3.2 has adapted the callers. Until then, only `EventEditor.tsx` and `ClipOrderList.tsx` may report errors.
  - the scratch script of 2.1 also imports `draft.ts`. It asserts over detail and `GET …/reel` JSON, hand-copied from the agent's library (task 4.1's setup, fixtures included):
    - **untouched**: `buildWriteBody` deep-equals the read document, and `isDirty` is false, on Grillning, Badutflykt, Sommarlov and Blandat
    - **add**: Grillning, `addCut(s1710001.mp4, {in: 0, out: 1.5})`. The body's `clips` is the read one plus `s1710001.mp4: {trims: [{in: 0, out: 1.5, reason: 'manual'}], exclude: false}`, and `chapters` deep-equals the read one. `cutChanges` is `{added: 1, removed: 0}` and `adoptedNewCount` is 0.
    - **add then remove**: removing that cut gives `isDirty` false, and `draft.cuts` has no entry for the clip
    - **order of insertion**: adding `[4, 6]`, then `[1.25, 2.5]`, then `[1.25, 1.3]` lists them as `[1.25, 2.5]`, `[1.25, 1.3]`, `[4, 6]`
    - **remove a read cut, then Undo**: Grillning with the fixture `s1710003.mp4: [{in: 0, out: 1.2, reason: black}]`
      - `removeCut(r0)` keeps the cut listed with `removed: true`. The body has no `s1710003.mp4` key (its entry held trims only), and `cutChanges` is `{added: 0, removed: 1}`.
      - `restoreCut(r0)` gives `isDirty` false
    - **other properties kept**: with `title: true, rotate: 90` added to that fixture entry, removing its cut gives `{trims: [], title: true, rotate: 90, exclude: false}` in the body
    - **NEW clip**: Badutflykt, `addCut(s1710004.mp4, {in: 4, out: 6})`. The body's root chapter is `[s1710001.mp4, s1710003.mp4, s1710004.mp4]`, `clips` has `s1710004.mp4`, and `adoptedNewCount` is 1.
    - **no chapters**: Blandat (read `chapters: []`), `addCut(s1710003.mp4, {in: 1, out: 2})` gives `chapters: [{name: '', clips: ['s1710003.mp4']}]` and the cut
    - **removed clip wins**: Sommarlov with the fixture cut on `borttagen.mp4`, removing that clip (G1's `removeClip`) gives no `borttagen.mp4` key
    - **moved clip keeps its cut**: Två kapitel, `addCut(Kvällen/s1710002.mp4, …)` then G1's `moveClips` to `r0`. The body lists it in `''` with the cut.
    - **exact numbers**: a read cut `{in: 3.2033333, out: 4}` goes back unchanged when another cut is added to the same clip
    - every body above passes a hand-written check of the engine's rules: no identity twice, every `clips` key listed by a chapter, no ignored identity listed, `out > in >= 0` in every span

## 3. web/ — the screens

- [ ] 3.1 Add `src/cuts/CutsPanel.tsx` (`CutsToggle`, `CutsPanel`, `CutList`, `CutSpan`) and `src/cuts/cuts.css`, and `scissors` and `chevron-down` to `src/ui/Icon.tsx` (design, "The Edit-mode toggle and panel", "Copy", "Keyboard model and focus", "CSS"). Field markup reuses `.field`, `.field-label`, `.field-input`, `.field-error` and `.field-hint`. The panel seeds its fields from the editor's panel store and writes them back on each change (design, "A disclosure under the row"), keeps them as local state for rendering, and reports `cut-typed {identity, typed}` (no name) when "has text" flips. It refuses an overlapping Undo through `checkRestore`, shown in the cut's row. It handles focus after add, remove and Undo with a layout effect, then the passive scroll.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the node:22 container
  - `cuts.css` declares only `@layer screens`, and `grep -n "animation\|transition" web/src/cuts/cuts.css` prints nothing
  - `grep -rn ' disabled=\|autoFocus\|role="alert"' web/src/cuts` prints nothing
- [ ] 3.2 Wire the panel into Edit mode (design, "Where the Cuts control sits", "A cut typed but not added", "Copy", "Performance"):
  - `ClipOrderList.tsx`: `ClipRow` renders `CutsToggle` after `MoveButtons` and the panel right after it, for an `active` or `new` clip. Its `open` state is seeded from and written to the panel store, and the panel is mounted while `open` or while the store has an entry. `aria-controls` is set only while the panel is mounted. The list takes `draft.cuts` and `baseline.cuts` as props (never `draft`) and resolves `cutsOf` per row (design, "Performance"). `ClipRow` shows a missing clip's cut badge through a `RowBody` prop; `RemovedRow` passes none.
  - `EventEditor.tsx`:
    - actions `cut-add`, `cut-remove`, `cut-restore` and `cut-typed` go through `afterEdit` and are refused while a save is in flight
    - `typed` (a set of identities, no names) and `nextCut` live in `Ready`, and `reset` clears them. `summarize` resolves the typed clip's name from the draft at that moment, with `nameOf`'s `clipNames` inputs (design, "A cut typed but not added"). The panel store is a `useRef` map that Reset clears before it bumps `resets`.
    - `afterEdit`'s and the editor's `dirty`, and `submit`'s guard, add `typed.size > 0` beside `dateIncomplete`
    - `summarize` gains the cut parts, in the order of design, "Copy"
    - the hint sentence changes as designed
    - every announcement of the design's tables goes through `announce`
  - `SaveBar.tsx`: `dateIncomplete` becomes `unfinished`
  - `edit.css`: the toggle's placement

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff web/src/edit/SaveBar.tsx` changes only the prop's name, its type line and its three uses
  - `git diff web/src/edit/edit.css` adds only the toggle rules and the selector change, with no `grid-template-columns` or `grid-template-areas` line changed
  - `grep -rn ' disabled=' web/src/edit web/src/cuts` prints nothing
- [ ] 3.3 Add `src/cuts/ReadCuts.tsx` (`useReadCuts`, `ReadCuts`), and use it in `src/events/EventDetail.tsx`: `ReadyView` calls the hook and shows the failure note, and `ChapterPanel` renders `ReadCuts` in the file cell (design, "The read view").

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - the `EventDetail.tsx` diff is 20 lines or fewer and touches only `ReadyView`, `ChapterPanel` and the imports. `git diff web/src/events/EventDetail.tsx | grep -n "load\|fetchEvent"` prints nothing.
  - `grep -n 'role=' web/src/cuts/ReadCuts.tsx` shows `note` only

## 4. Verification against the dev library

- [ ] 4.1 Set up the agent's own environment per the dev-env runbook §9 with `SLUG=clip-cuts-screen`, `N=27`: database `arel_clip_cuts_screen`, library `../dev-clip-cuts-screen`, `auto-reel serve <library> --port 8127` over a fresh `npm run build`, no worker. Never use port 8080 or 5173, `../auto-reel-dev`, `auto-reel-media/`, the default database, or another agent's database, library or port. In that library copy only, add the fixtures of design, "Verification fixtures" (the 400-clip `Stor dag` by the recipe the design's "Verification fixtures" copies from `archive/*-chapter-management-screen/design.md` and `archive/2026-09-30-event-edit-screen/design.md`), and copy every `reel.yaml` before touching it. Apply each `reel.yaml` fixture only for the scenarios that state it, and restore the copy before the next scenario. `make_dev_library.py` dumps `reel.yaml` with ruamel's default indentation, and the engine's writer (`reel/writer.py` 28-35) re-indents every list in the file on its first real write. So first normalise each `reel.yaml` the checks `diff`: load it and dump it again with `indent(mapping=2, sequence=4, offset=2)`. Then take its copy. A `diff` after a save then shows only the scenario's lines.

  Drive `http://127.0.0.1:8127/` with a Playwright script in `<scratchpad>/verify/clip-cuts-screen/` (container `mcr.microsoft.com/playwright/python:v1.49.0-noble`, `--network host`). Scope locators to `main:not([hidden])`, capture every `PUT …/reel` body, and check files host-side with `cat` and `diff`. Use the **keyboard only** (Tab, Shift+Tab, Enter, Space, Escape, typing; no clicks) for every item below except where it says pointer. After each step, assert `document.activeElement` and the editor's `role="status"` text.
  - Every scenario of the two ADDED requirements, on the named events, in order. Each save's body matches design, "The draft model", and each `reel.yaml` `diff` shows only the lines the scenario names.
  - The five cut scenarios of the MODIFIED requirement. Specifically:
    - **Grillning**: against the normalised copy, the `diff` adds exactly `clips:` / `s1710001.mp4:` / `trims:` / `- in: 0.0` / `out: 1.5` / `reason: manual`, and changes nothing else
    - **Badutflykt**: the root chapter's `clips` gains `- s1710004.mp4`, and the page then shows it "Included"
    - **Grillning with the fixture**: removing the read cut and saving leaves no `s1710003.mp4:` line
    - **Blandat**: `chapters` and the cut are written
  - The MODIFIED requirement's other scenarios still pass. "A moved clip keeps its cut" runs twice: as written, with G1's hand fixture `Kvällen/s1710002.mp4: {trims: [{in: 0, out: 1.5}]}` on the normalised Två kapitel, and then, the copy restored, with a cut added through the panel before the move.
  - **Focus in view**: at 1280 × 900 and 390 × 844, after the first cut is added on the last clip of `Grillning`, the start field and its whole form are inside the window and not under the save bar (bounding boxes against the bar's)
  - **Locked**: with a cut pending and the `PUT` held by `page.route`, press Enter on Save. The panel's fields, Add cut and Remove are `aria-disabled` with no `disabled` attribute, typing and Enter change nothing, the toggle still collapses and expands, and focus stays on Save. Abort the route: the cut is kept.
  - **Typed, not added**:
    - type `2` in the start field of `s1710001.mp4`. The save bar reads "Cut typed on s1710001.mp4, not added", Save is `aria-disabled`, and Back asks "Discard unsaved changes?". Keep editing, clear the field: the bar leaves. With a field change too, the bar reads "Title changed · cut typed on s1710001.mp4, not added" (design, "Copy": the order of the parts)
    - on Två kapitel, type `2` on `s1710002.mp4` of `Kvällen` (the bar names `s1710002.mp4`), move it to `Main` with Move clips: the bar names `Kvällen/s1710002.mp4`. Without pressing the toggle, its row in `Main` has the toggle `aria-expanded="true"` and the start field holds `2`; hide and show the panel once, and it still holds `2`. Reset: the field is empty and the bar leaves
    - on Två kapitel, type `2` on `s1710002.mp4` of `Kvällen`, then rename `Kvällen` to `Kväll`: the bar names `Kvällen/s1710002.mp4`, as the row now does
  - **Conflict**: on Grillning add a cut, change the title in its `reel.yaml` host-side, then Save. The conflict alert shows. Type `5` in a start field: Overwrite with mine is `aria-disabled` and pressing it sends nothing. Clear the field, then Overwrite with mine, confirmed: the captured body carries the cut.
  - **Read view**:
    - after each save, the indicator reads as the scenario says, and Enter on its summary opens the list (`details[open]`)
    - with `**/reel` aborted by `page.route` on open, the note "Cuts could not be read" shows with the not-reachable words, inside no `role="alert"`, and the clip rows are present
    - every request of "Reading cuts changes nothing" is a GET
  - **Scale**: on `2024-09-15 - Stor dag`, open the Cuts of the 400th clip, type 10 characters in its start field (under 50 ms per keystroke), and add a cut (under 200 ms from Enter to the announcement). Then type 10 characters in Title: under 50 ms per keystroke, as G1 measured (no list re-renders: design, "Performance"). Then press Move up on the 200th clip: under 200 ms to its announcement, as before.
  - Restore every touched `reel.yaml` from its copy afterwards and `diff` to confirm.
- [ ] 4.2 Layout, touch and accessibility on `2024-08-20 - Två kapitel - Tjörn` and `2024-06-27 - Grillning med grannar`. Check Edit mode with every panel closed, with one panel open holding two cuts (one of them removed, with Undo) and a refusal shown, and the read view with a cut list open:
  - **Sizes**: 320×700, 390×844, 768×1024 and 1280×900, in the light and the dark theme (the theme control). Save screenshots of each state to `<scratchpad>/verify/clip-cuts-screen/` and look at every one.
    - at every size, `document.documentElement.scrollWidth <= clientWidth`
    - with panels closed, each row's height at 320 and 390 equals a run of main's build taken first (±1 px)
    - at 1280 the rows' thumbnail, name, status, size and time `left` positions equal the read view's table's (±1 px)
    - the toggle at 320 and 390 lies within the handle's and position's columns
    - with the Sommarlov fixture, the row of `borttagen.mp4` (with its cut badge) at 390 is at most 8 px taller than the row of `s1710002.mp4`; after its Remove, its removed row shows no cut badge
    - with the layout-only fixture (`s1710002.mp4` cut from `1:02:03.125` to `1:02:05.5`), its panel open in Edit mode and its list open in the read view at 320: no horizontal scroll, and no `.cut-at` box extends past its cell or panel
  - **Tab order**: from a row's handle, Tab reaches Move up, Move down, Cuts, and then (panel shown) the panel's first control, in that order
  - **Coarse pointer**: a context with `has_touch` and `is_mobile` at 320×700 and 390×844. For the Cuts toggle, the start and end fields, Add cut, a Remove, an Undo and the read view's summary, run `ui-a11y-polish`'s touch probe: `elementFromPoint` at a 7 × 7 grid across the designed 44 × 44 area returns that control or a descendant, with each control scrolled to the window's centre first. The handle's probe still returns the handle. Each cut row is at least 44 px tall, and no row's height changes against a fine-pointer run by more than the 14 px margin allows (design, "CSS").
  - **Fine pointer**: at 1280 and 390 with a mouse, the existing controls (Edit, Save, the handle and the moves, G1's chapter tools) keep their bounding boxes against a run on main's build taken first, except the vertical offsets the design accepts for rows at 58-64rem
  - **Contrast**: the toggle's words with no cut (`--fg-muted`) and with cuts (`--info-fg`) on `--surface` and `--surface-hover`, the summary's on `--surface` and `--surface-hover`, the cut's muted texts on `--surface-2`, the refusal, and the "Removed when you save" badge each measure at least 4.5:1 in both themes
  - **axe-core**, injected ad hoc: no serious or critical violation in Edit mode with a panel open and closed, and in the read view with a list open, in both themes
  - **Busy focus**: as in 4.1's locked check, `document.activeElement` stays on Save through the held request
  - no Playwright script, screenshot or `.playwright` directory is in the worktree

## 5. Docs and validation

- [ ] 5.1 Update `web/README.md` and `docs/high-level-design.md`:
  - `web/README.md`: the Edit-mode paragraph (the Cuts control, times, refusals, Undo, typed-but-not-added) and the event page paragraph (the indicator and its list), and the file tree with `cuts/` and its four files
  - `docs/high-level-design.md`: D-14 as in design, "HLD"; §4.10's v1 bullet gains "typed cuts (**D-14**)", re-read after G1's D-13 edit landed; and §4.10's slice row D

  Then run the gates:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `web-design-system`'s motion grep gate, its three commands verbatim, over `web/src/edit` and `web/src/cuts` (this change adds no animation)
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full `.venv/bin/python -m pytest` (the web-mount and OpenAPI drift tests green)
  - `git diff --stat main -- auto_reel_ng tests scripts web/openapi.json web/src/api web/package.json web/package-lock.json` is empty
  - `openspec validate clip-cuts-screen --strict` passes

  Verify: all of the above pass. `grep -n "D-14" docs/high-level-design.md` hits §7 and §4.10, and `grep -n "Cuts" web/README.md` hits.
