## 1. State and logic

- [ ] 1.1 Add the pure open/dismiss transitions beside `cardSelection` in `web/src/timeline/cards.ts` and the `editing`/`open`/`dismiss` members to `useCardSelection`/`CardsBinding`: opening selects and opens (also when already selected), dismissing keeps the selection, `retain` ends both. Test: `cards.test.ts` (node:test) covers open, reopen, dismiss-keeps-selection, retain, and a cut selection ending it.

## 2. The dialog

- [ ] 2.1 Render `CardInspectorPanel` as the content of `ui/Dialog` (title from `inspectorName`, Close button, Done button, native Escape), drop its own Escape handler, and mount it from the page for `editing` in Edit mode only. Test: `npx tsc --noEmit` clean and `npm test` for any extracted pure helper; behaviour covered by 5.1.
- [ ] 2.2 Remove the inline `CardInspectorPanel` slot and the DOM-query refocus from `TimelineSection`, keeping the read view's words-only `CardInspector` and the status region. Test: Playwright asserts no `.ci` element sits in the page below the track in Edit mode (5.1).
- [ ] 2.3 Layout in `components.css`/`card.css`: preview above fields and a full-screen sheet at <= 600 px, two columns above it, fields scroll inside the dialog, no background scroll, reduced motion, 44 px targets on coarse pointers. Test: Playwright measures scrollWidth == clientWidth at 320/390/1280 and that `window.scrollY` is unchanged while open (5.1).

## 3. Entry points

- [ ] 3.1 Chapter-list card row (`CardRow.tsx`): press, Enter and Space call `open`; the highlight stays after close. Test: Playwright opens a row far down the page without the page scrolling; Escape returns focus to the row.
- [ ] 3.2 Timeline card block: pressing its body calls `open`; its duration handle still only selects. Test: Playwright opens from a block, and a handle drag still resizes and opens no dialog.

## 4. Draft behaviour

- [ ] 4.1 Confirm edits flow into the page draft with no dialog-local state: typing a title updates the preview, Done closes, the save bar shows "1 title card changed", Save writes `reel.yaml`. Test: Playwright routes only `**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel`, `**/reel?*` and asserts the written body.

## 5. Browser verification and docs

- [ ] 5.1 Playwright in Chrome (`localhost/playback-research:chrome`) and Firefox (`localhost/pcm-audio-research:pw163`), light and dark at 1280 and 390, covering the scenarios of both delta specs; screenshots are looked at. Test: the script itself, run from the scratch directory only, plus `npm test`, `npx tsc --noEmit` and `npm run build` green.
- [ ] 5.2 Update `docs/high-level-design.md` (§4.10: the Edit-mode card editor is a modal dialog opened from the row or block; §6 note). Test: a grep that §4.10 no longer says the inspector opens below the track.
