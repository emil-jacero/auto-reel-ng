All work is in `web/`, plus the HLD and `docs/editor-workspace.md`.
- **Node** runs only in podman (`docker.io/library/node:22`), with the repo root mounted and `-w /app/web`. Some web
  tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo. It intercepts PUT, POST and DELETE.

## 0. Gate

- [x] 0.1 Dependency gate: `clip-context-menu` MUST be archived, and both of these must succeed from the repo root:
  - `ls -d openspec/changes/archive/*-clip-context-menu`
  - `grep -q "Requirement: Edit mode offers a clip's edits in a menu" openspec/specs/web-app/spec.md`

  If either fails, STOP and report which check failed.
- [x] 0.2 Re-base the deltas on what was archived. Copy the archived texts of:
  - "Edit mode offers a clip's edits in a menu" and "An unavailable item in the clip menu says why" (`web-app`);
  - "A clip block opens the clip's menu" and "A clip is selected on the track or in the bin" (`event-timeline`).

  Re-apply this change's additions to them, and verify that `openspec validate clip-multi-select --strict` reports no
  "Archive would refuse" note.

## 1. Rules (web/src/edit/workspace, web/src/edit)

- [x] 1.1 Widen the selection (design D1): the `clips` kind, `pressClip`, `selectedClips`, `lastClip`,
  `selectionWords`, and `keptSelection` / `inspectorTab` for a set.
  Verify with `selection.test.ts`. It must check:
  - each press (`alone`, `toggle`, `range`) from each kind;
  - the normalisation to `clip` and `none`;
  - a range across a chapter's edge, and a range whose anchor left the order;
  - the words of design D6.
- [x] 1.2 Add `selection-move`, `selection-drop` and `ignore-many`, with their `describeEdit` labels (design D2).
  Verify with `groupMove.test.ts` and a reducer test, which must check that:
  - a missing or ignored identity in the set is not moved;
  - one `ignore-many` is one Undo step;
  - the marks are untouched apart from `afterMove`.

## 2. Wiring (web/src/timeline, web/src/edit)

- [x] 2.1 Presses (design D3): modifier presses and Enter keys on track blocks, and modifier clicks on today's bin rows.
  `aria-pressed` follows the set, and Alt+arrows with a set say why (design D6).
  Verify with `npm test` and `npm run check`, then in Playwright:
  - the scenarios of "A clip is selected on the track or in the bin";
  - Alt+Right with two clips selected moves nothing;
  - Escape clears a set.
- [x] 2.2 The group drag (design D4): `groupSlot` with its unit test in `clipDrag.test.ts`, held blocks, the line and
  tip, release on the track or the bin. Verify in Playwright with the scenarios of "Dragging one of several selected
  clips moves them all", including the unselected-clip drag.
- [x] 2.3 The Clip tab (design D5): `ClipGroupTab` and the shared Move to… for one and for several clips. Verify in
  Playwright with the scenarios of "The Clip tab acts on several selected clips" and "The Clip tab edits the selected
  clip". Take screenshots of the group tab in light and dark at 1440 and 390 px, and look at them for clipping.
- [x] 2.4 The menu (design D7): `targets` in `clipMenu.ts` with its unit tests, `menuSelects` for a set, the
  focus-after rule for a group ignore, and the three `SHORTCUTS` rows. Verify in Playwright with the scenarios of "Edit
  mode offers a clip's edits in a menu" and "A clip block opens the clip's menu".

## 3. Verification and record

- [ ] 3.1 Run Playwright in Chromium and Firefox over every scenario of both deltas (`event-timeline`, `web-app`). Also
  check that:
  - the Undo and Redo labels of a group edit read "ignore of 2 clips" and "move of 2 clips" (the reducer's wiring is
    not importable under Node), and the dispatchers pass `onDisk` so a missing clip in a set is neither moved nor
    ignored;
  - a mark and a selection coexist: Move marked to… moves only the marked clips, and the Clip tab's Move moves only the
    selected ones;
  - while either Move is pending, the trim handles and the clip menu say they wait;
  - the gates hold, in Chromium: Shift+click over 400 clips paints within 100 ms (median of five), and a 50-clip group
    drop is within 150 ms of a one-clip drop.
- [ ] 3.2 Record the change:
  - HLD D-28 "One selection": a selection may hold several clips (Ctrl/Cmd, Shift, Enter keys), group edits ship their
    clips, the group drag shows a line, and the marks stay until `plain-clip-bin`.
  - §6 item 10: this change is built.
  - `docs/editor-workspace.md`: add a row for `clip-multi-select`.
- [ ] 3.3 Gates: `npm test`, `npm run check` and `npm run build` in podman; `openspec validate clip-multi-select
  --strict`.
