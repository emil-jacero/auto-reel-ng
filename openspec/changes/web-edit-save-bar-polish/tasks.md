## 1. Gate

- [ ] 1.1 Confirm the base and re-read what the two gates changed (design, "Context" and "Gate interplay"). Stop and report to the supervisor on any mismatch.
  - `ls openspec/changes/archive/ | grep -E -- '-(web-toast-and-dialog-layers|api-excluded-clips-read-model)$'` lists both.
  - `web/src/edit/EventEditor.tsx`: `showBar` is `ready !== null && (dirty || ready.problem?.kind === 'gone')`; `<SaveBar>` is rendered only `{showBar && …}`; the layout effect keyed on `[showBar]` calls `keepToastsClearOf(bar)` and returns early when `!showBar || bar === null`. Write down how `web-toast-and-dialog-layers` changed that effect and whether anything now reads the bar while it is hidden (a `ResizeObserver` on it, a `--toast-rise-h` term).
  - `onReset` still calls `focusPageHeading({ preventScroll: true })`, and `focusPageHeading` is still in `web/src/shell/AppShell.tsx`.
  - `web/src/edit/ClipOrderList.tsx`: `MOVE_IN`, `NO_CLIPS`, `NO_CLIPS_PLAYED` and `words={empty ? NO_CLIPS : NO_CLIPS_PLAYED}`. Write down how `api-excluded-clips-read-model` changed `empty`, `plays` and `removed`.
  - `ChapterToolsModel.moveClips` is `null` exactly when the event lists one chapter (`EventEditor.tsx`, `moveClips: !several ? null : …`).
  - `web/src/styles/reset.css` still has `[hidden] { display: none !important }`.
  - `grep -rn "save-bar" web/src --include=*.ts --include=*.tsx` hits only `SaveBar.tsx`.
  - Re-base the two MODIFIED blocks in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md` if either requirement changed since 6a7fe16: take the landed text and carry over only this change's paragraph and scenarios.

  Verify: `openspec validate web-edit-save-bar-polish --strict` passes.

## 2. web/ — the save bar

- [ ] 2.1 Mount the save bar from the start of Edit mode and hide it while clean (design, "Mount the bar early, hide it with the attribute" and "What stays conditional on `shown`").
  - `src/edit/SaveBar.tsx`: a `shown: boolean` prop; the root `div` gets `hidden={!shown}`; the header comment says the bar is in the page from the moment Edit mode is ready and hidden while there is nothing to save.
  - `src/edit/EventEditor.tsx`: render `<SaveBar>` whenever `ready !== null` and pass `shown={showBar}`; compute `summary` only when `showBar` (`''` otherwise). Leave the `[showBar]` layout effect, `placeBar` and the registration as they are, so placement, `--toast-inset-bottom`, the `ResizeObserver`, the listeners and `keepToastsClearOf(bar)` exist only while the bar is shown. Update the comment on that effect.
  - `src/edit/edit.css`: no rule changes. If the gate left a comment that says the bar is mounted when the page becomes dirty, correct it.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the node:22 container.
  - In a real browser (Playwright from the scratch directory, light and dark, 1280 and 390), the scenarios "No save bar before the first edit", "The first edit shows the bar" and "An undone edit hides the bar again" hold. While clean: `[role=region][aria-label="Unsaved changes"]` is absent from the accessibility tree, the bar has the `hidden` attribute, Tab never stops on Reset or Save, `--toast-inset-bottom` is unset on `<html>`, and a shown error toast sits where it sits on a page with no bar. After the first edit the bar is held, Reset and Save are reachable, and `.save-bar-card` starts translucent under `prefers-reduced-motion: no-preference` (the entrance survives).
  - Looked at: screenshots of the clean page and the dirty page in both schemes, at both widths.
- [ ] 2.2 Measure the first edit against the second on a 400-clip chapter (design, "Findings, re-checked", 1).
  - Build the event in the dev library, never in the repo or `auto-reel-media/`: 400 symlinks to one fixture clip under distinct names, in one chapter.
  - In a Chromium window 1280 × 900, five runs, each in a fresh Edit mode: press Move down on the first clip, wait for the next painted frame (`requestAnimationFrame` twice), and record the time from the press; then the same for the second clip. Take the median of each.
  - Run it on the base (before 2.1) and after, and keep both outputs in the scratch directory.

  Verify: after 2.1 the median of the first press is at most 50 ms above the second's. If it is not, stop, attach both measurements and a performance profile of the first press, and report that the cost is elsewhere (design, "Risks"); do not weaken the requirement or change `ClipOrderList`.

## 3. web/ — Reset

- [ ] 3.1 Bring the focused heading into view after Reset (design, "Reset: focus now, scroll after the page settles").
  - `src/edit/EventEditor.tsx`: keep `focusPageHeading({ preventScroll: true })` in the handler. Add a `useLayoutEffect` keyed on `ready?.resets` that skips the value it first sees and, when `document.activeElement` is `main:not([hidden]) h1`, calls `keepInView(heading, null)`. It runs nothing else, and is placed beside the other bar effects with a comment saying why the scroll waits for the commit.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass.
  - In the browser, the scenarios "Reset from the bottom of a long page" (1280 × 900 and 390 × 844, keyboard Enter on Reset, on the 400-clip event), "Reset with the heading already in view" (`window.scrollY` equal before and after) and "Reset with the bar resting" (320 × 256) hold. In each, `document.activeElement` is the `h1`, its rect lies below the sticky header's bottom, and `window.scrollY` read two frames apart is the same (the scroll is instant).
  - Looked at: a screenshot after Reset at 390 × 844 in both schemes.

## 4. web/ — the empty-chapter hint

- [ ] 4.1 Build the empty-chapter words from the chapter count (design, "The words come from a function of two booleans").
  - New `src/edit/emptyChapter.ts` exporting `emptyChapterWords(alone: boolean, wholly: boolean): string` with no imports. With `alone` false it returns today's two texts character for character (`No clips. Drag clips here, or move them here with another chapter’s Move clips. A chapter without clips is left out of the movie.` and `It plays no clip. …`); with `alone` true it omits the drag-and-Move-clips sentence.
  - `src/edit/ClipOrderList.tsx`: drop `MOVE_IN`, `NO_CLIPS` and `NO_CLIPS_PLAYED`; pass `words={emptyChapterWords(tools.moveClips === null, empty)}`. Add no prop.
  - Update the comment on the old constants (Move clips is per chapter and absent on a lone one).
  - `src/edit/emptyChapter.test.ts`: the four cases (alone or not, wholly empty or not) with the exact strings. Run it with `npm test` (node:22 in podman: `node --test --experimental-strip-types "src/**/*.test.ts"`, as for `toast.test.ts`).

  Verify:
  - The unit test passes and `npx tsc --noEmit` and `npm run build` pass.
  - In the browser, with an event that has no clip (a folder holding only a `reel.yaml`) and one whose only clip is ignored, in the dev library, the scenarios "A lone empty chapter does not point at Move clips", "A lone chapter whose only clip is ignored" and "A second chapter brings the hint back" hold, in both schemes at 1280 and 390, with no sideways scroll at 320. If the library scan does not list a folder with no clip, say so in the result and keep the first scenario covered by the unit test.
  - Looked at: screenshots of the lone and the two-chapter empty states.

## 5. Gates

- [ ] 5.1 Run the validation gates for the package this change touches.
  - `npm run check` (tsc for the app and the tests) and `npm run build` in the node:22 container.
  - `npm test` (`emptyChapter.test.ts` and the existing tests).
  - `git status --short` lists only files under `web/src/edit/` and this change's own folder (no Python file changes, so black, mypy, pylint and pytest do not apply).

  Verify: all pass; `openspec validate web-edit-save-bar-polish --strict` passes.
