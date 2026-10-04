## 1. Help state

- [x] 1.1 Add `web/src/ui/help/helpState.ts` (`readHelp`, `writeHelp`, section keys, injected storage, all access guarded) and `useHelp`. Test (`helpState.test.ts`, `node:test`): defaults closed; round trip per section; a storage whose `getItem`/`setItem` throw reads closed and does not throw; an absent storage; unrelated keys untouched.

## 2. Toggle and panel

- [x] 2.1 Add `HelpToggle` and `HelpPanel` (`web/src/ui/help/`) with CSS: information icon, "Help", `aria-expanded`, `aria-controls`, 44 px target, visible focus, a muted panel kept in the DOM with `hidden`. Test: Playwright in Chrome and Firefox opens and closes a toggle by mouse and keyboard, measures it at 390 px (at least 44 x 44), reloads and finds the state kept; a pure test pins the toggle's ids and `aria-` attributes from `helpModel` (`helpModel.test.ts`).

## 3. Timeline

- [x] 3.1 Replace `movieWords` with `movieStat` (movie · footage · cuts − · cards +, the terms for zero cuts and zero cards left out, one clock scale) and render it in `tl-controls` instead of the `tl-summary` paragraph; keep "Reading the cuts…" and the unknown-cards sentence. Test: `labels.test.ts` for the strings, the width identity (1:00:00 scale, 9.99 s to 10.00 s), movie = footage − cuts + cards; Playwright: the stat is one line in the control row at 1280 and 390 px.
- [x] 3.2 Timeline help: move `CARDS_FADES`, `DISMISSAL_NOTE`, the analyze command and the cut fields' hint into it; "Not analyzed" becomes a badge; `CutFields` draws nothing without a selected cut (fields keep `aria-describedby` to the help text). Test: `suggestions` text tests updated; Playwright: no "No cut selected" in the document, the group appears on selecting a cut, the badge is visible and the command is in the help, in the read view and Edit mode.

- [x] 3.3 Remove the selected-card read-out: `CardInspector` renders only the visually hidden polite status region (no `tl-inspector` section) in the read view and Edit mode; drop the unused CSS. Test: `cards.test.ts` keeps `inspectorWords`; Playwright in Chrome and Firefox, both modes: selecting a card block leaves no visible "Title card for …" text outside the block, and the status region holds the sentence once (no second announcement on a re-press).

## 4. Edit mode sections

- [x] 4.1 Details, Poster and the Title cards tab: a Help toggle each, holding the Details lead, "Pick the frame on the Timeline…" and the tab's lead; their state lines and fields unchanged. Test: Playwright in both modes: each toggle opens, closes and persists, the fields' names and the dialog's fields are unchanged.
- [x] 4.2 Clips help: the `edit-hint` instructions, `MARK_HINT` and `OWN_CHAPTER_NOTE` go into one Clips panel opened from a toggle in the marks line; "Saving adds N new clips" stays as its own line only while a new clip exists; the empty-chapter and ignored captions stay. Test: `marks.test.ts` and `chapterNames` tests keep their words; Playwright: the same event shows the instructions only after Help is pressed, and the count, Clear marks, missing-clip status and "Saving adds…" stay visible.
- [x] 4.3 Move's reason: `title` and `aria-describedby` always, a visible reason line only after Move is pressed while unavailable, cleared when the reason changes; drop the reserved empty line. Test: Playwright: no reason line on load, pressing Move with no mark shows "Mark a clip to move it.", marking a clip changes it to "Choose a chapter.", no clip row moves on marking; `marks.test.ts` for `moveReason` unchanged.

## 5. Verification and documents

- [x] 5.1 Verify in real browsers: Playwright in Chrome (`localhost/playback-research:chrome`) and Firefox (`localhost/pcm-audio-research:pw163`) on `2024-08-20 - Två kapitel - Tjörn`, read view and Edit mode, light and dark, 1280 and 390 px: count the visible paragraphs of explanatory text before and after (report the numbers), every toggle opens, closes and persists across reload, a missing clip, Needs render and unsaved changes stay visible, no horizontal overflow; look at before/after full-page screenshots. `npm test`, `tsc --noEmit` and `npm run build` pass.
- [x] 5.2 Update `docs/high-level-design.md`: a §4.10 bullet "v2 help text declutter" (`help-text-declutter`, D-20: the movie stat, the help toggles, the Not analyzed badge), the §6 roadmap line, and the D-20 note that the Timeline's explanations live in its help. Test: extend `web/src/timeline/docs.test.ts` to assert the HLD names `help-text-declutter` in §4.10 and no longer describes a permanent "Movie … of … of footage" line.
