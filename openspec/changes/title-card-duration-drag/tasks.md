## 1. Gate and model

- [x] 1.1 Re-read the merged `title-card-blocks` (the card block, the shared selection, the chapter list's card row, the draft's card shape) and `title-card-write-api`'s `PUT .../reel` card body; map every role in design.md to its real name and record any difference in design.md; verify with a short list in the task's commit message body and `openspec validate title-card-duration-drag --strict`
- [ ] 1.2 Add the title-card duration rules to the timeline model (limits with the kept-span bound and the range that holds the current value, tenth steps, whole-second snap within 8 px, key steps, the layout shift through `withDurations`, the released-words) and the mirrored 0.5/60 constants; verify with `node:test` cases for every scenario in the `timeline` delta, including the test that reads `auto_reel_ng/reel/card.py` and fails on a mismatch, run by `npm test` and type-checked by `tsc -p tsconfig.test.json`

## 2. Draft and drag state

- [ ] 2.1 Add the draft's card-duration edit (`setCardDuration`: one decimal, equal-to-resolved is no edit, Reset restores) and its unsaved/dirty counting and Save body, using the existing `PUT .../reel` shape; verify with `node:test` cases (edit, no-op, reset, the body carrying only `duration` for the card) and a Save against the dev service showing `card.duration` in `reel.yaml`
- [ ] 2.2 Extend the drag store with a card drag (chapter, tenths, snapped flag, words) under the existing one-drag-at-a-time claim, and add the one-decimal case to `clock.ts` for "Card 4.0 s"; verify with `node:test` cases (claim refused while a trim drag holds the store, listener runs only on change, fixed character count from 0.5 to 60.0)

## 3. The handle

- [ ] 3.1 Build the card handle on each card block (slider role, name, value and value text, pointer and touch drag with the delta rule, snap line and words, Escape, locked while a save or Move is pending, press hand-over with trim handles, selecting the card on press, disabled with a reason); verify with a Playwright run in Chrome and Firefox >= 155 dragging a black and a video card, cancelling with Escape, and a locked pending save, asserting the draft through the Save request body (route only the allowed endpoints)
- [ ] 3.2 Add the keyboard (arrows, Shift, Home/End, limits, no live-region duplicate, scroll into view, not inside a field) and the release announcement; verify with a Playwright key sequence asserting `aria-valuenow`, `aria-valuetext` and the live region text in both browsers
- [ ] 3.3 Make a black card's drag shift the later blocks, ruler, length and chapter bands live while the playhead keeps its content, and bound a video card by its first clip after the draft's cuts (including a just-edited trim, a card longer than its clip, and a chapter with no clip); verify with a Playwright run on a dev library asserting block positions during the drag and the limit, plus the `--shift` fallback only if 4.1 fails its number

## 4. Gates and docs

- [ ] 4.1 Measure the drag: the scripted black-card drag in an 80-clip dev library, Chrome (4x CPU throttle) and Firefox (unthrottled), at most 2 % of frames over 25 ms; also check 1280 and 390 px, light and dark, reduced motion, a coarse pointer, and look at the screenshots; verify by recording the figures and screenshots paths in the PR body (SCRATCH, never the repo), and by `npm test`, `tsc --noEmit` (both configs) and `npm run build` passing with the gzip sizes recorded
- [ ] 4.2 Update `docs/high-level-design.md`: D-20 (the card handle reuses the trim handle's drag store, slider and snap rules; the mirrored bounds and their test), D-21 untouched, §4.10 (title-card length by drag in the v2 scope), §6 (this change ticked, `title-card-inspector` noted as the typed alternative); verify by `rg "title-card-duration-drag" docs/high-level-design.md` showing each place and `openspec validate title-card-duration-drag --strict` passing
