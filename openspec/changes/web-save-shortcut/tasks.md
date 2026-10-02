## 1. Gate

- [x] 1.1 Re-check the names this change builds on, on main after `web-edit-save-bar-polish` and `web-playback-and-notices` have merged (design, "Gates"). Stop and report to the supervisor on any mismatch, and re-base the delta if a landed requirement now says something about a shortcut.
  - `git log origin/main --oneline | grep -E "web-edit-save-bar-polish|web-playback-and-notices"` finds both.
  - `grep -rnE "ctrlKey|metaKey|aria-keyshortcuts" web/src` still finds only `EventList.tsx`'s link guard, so no other change added a Save shortcut.
  - `web/src/edit/SaveBar.tsx` computes `saveBlocked` (or its replacement) from `edited`, `unfinished` and `problem`; `web/src/edit/EventEditor.tsx` has `submit`, `announce`, `latest` and the `<p role="status">` region. Write down where each sits now, and how `SaveBar` is mounted (always, hidden while clean, or `showBar`).
  - The hidden `MoviePanel` in Edit mode does not stop `keydown` propagation (`grep -rn "stopPropagation" web/src/movie web/src/preview`).

  Verify: `openspec validate web-save-shortcut --strict` passes on the re-based delta.

## 2. web/ — the shortcut

- [ ] 2.1 In `src/edit/SaveBar.tsx`, export `SaveHold` and `saveHold(edited, unfinished, problem)` (design, Decision 2) and make the button's `saveBlocked` read it; add `aria-keyshortcuts="Control+S Meta+S"` and `title="Save (Ctrl+S, or ⌘S on a Mac)"` to the Save button. Update the file's doc comment with one sentence on the shortcut.
  - The button's behaviour is unchanged: with each of `nothing`, `unfinished`, `conflict`, `gone` and `null` the same states are `aria-disabled` as before.

  Verify: `npx tsc --noEmit` and `npm run build` pass in the node:22 container; `git diff web/src/edit/SaveBar.tsx` changes no class name and no rendered text.
- [ ] 2.2 In `src/edit/EventEditor.tsx`, add the `document` `keydown` effect keyed on `ready !== null` (design, Decisions 1, 3 and 4): the key test, `preventDefault`, the ordered table of states (open `dialog[open]`, repeat, in flight or Move clips pending, `saveHold`), `announce(...)` for each message and `submit('save', 'save')` otherwise. Read the draft through `latest.current`; the effect re-registers only when `ready` goes between null and non-null. Add a short comment above it saying why it is a document listener and why it never clicks the button.

  Verify: `npx tsc --noEmit` and `npm run build` pass; `grep -c "addEventListener('keydown'" web/src/edit/EventEditor.tsx` prints 1 and its cleanup is `removeEventListener`; `submit`'s own body is unchanged in `git diff`.

## 3. Playwright in a real browser (scratchpad only, never in the repo)

- [ ] 3.1 Happy paths against the dev library on `PORT`, with writes intercepted by a route on `**/reel` and `**/reel?*` only (record the request, fulfil with the real answer for the saves that should land, abort for the unreachable case), and a `keydown` probe on `document` that records `defaultPrevented`:
  - Ctrl+S in the location field of `2024-06-27 - Grillning med grannar`: one write with the changed location, "Saving…" in the live region, `defaultPrevented` true, "Saved" toast, event page shown.
  - Meta+S after a keyboard drop (focus still on the clip handle): one write with the new order.
  - Ctrl+S with the request aborted on `2024-08-02 - Badutflykt - Varberg`: the unreachable alert with Retry, `document.activeElement` is still the title field, the edit is kept.
  - Ctrl+Shift+S and Alt+Ctrl+S: no request, `defaultPrevented` false.
  - The Save button's `aria-keyshortcuts` and `title`.

  Verify: the script exits 0; each assertion above is in its output.
- [ ] 3.2 Held-back paths, same setup:
  - clean editor: Ctrl+S sends nothing, the region says "Nothing to save.", `defaultPrevented` true
  - a date with its year cleared: nothing sent, the region names the incomplete date
  - a conflict (change `reel.yaml` in the scratch copy of the library between the edit and the save): after the conflict shows, Ctrl+S sends nothing, the region says Reload latest or Overwrite with mine first, and the Overwrite dialog is not open. This is the regression test for `saveHold` being shared.
  - a slow answer (route held for 500 ms): three presses, including `repeat: true`, send one write
  - the "Discard unsaved changes?" dialog open: Ctrl+S sends nothing, says nothing, the dialog stays open
  - before the document is read (hold the first `GET .../reel`): `defaultPrevented` false

  Verify: the script exits 0; each assertion above is in its output.
- [ ] 3.3 Look at the result in light and dark at 1280 and 390 wide: after an edit with the focus in a field, Ctrl+S in each, and the Save button focused (tooltip and bar unchanged). Screenshots to `$SCRATCH`, each opened and looked at; the bar's height at 390 × 844 is the same as before this change (measure with `getBoundingClientRect` on `.save-bar`, with and without the change on the same state).

  Verify: four screenshots opened and described in the result; the two bar heights are equal.

## 4. Docs and gates

- [ ] 4.1 In `web/README.md`, in the Edit-mode paragraph that describes the save bar, add one sentence: Ctrl+S (Cmd+S on a Mac) saves from anywhere on the page, says why when Save is held back, and is left to the browser outside Edit mode. Add `saveHold` to the `SaveBar.tsx` line of the file tree.

  Verify: `git diff --stat web/README.md` shows only those lines.
- [ ] 4.2 Final gates: in the node:22 container `npm ci`, `npx tsc --noEmit` and `npm run build` pass; `git diff --stat -- auto_reel_ng tests web/openapi.json web/src/api` is empty (no Python, no API, no schema change, so black, isort, mypy, pylint and pytest are unaffected, and `RENDER_GRAPH_VERSION` stays); `openspec validate web-save-shortcut --strict` passes.

  Verify: the three commands exit 0 and the diff stat prints nothing.
