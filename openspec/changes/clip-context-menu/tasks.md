All work is in `web/`, plus the HLD and `docs/editor-workspace.md`.
- **Node** runs only in podman (`docker.io/library/node:22`), with the repo root mounted and `-w /app/web`. Some web
  tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo. It intercepts PUT, POST and DELETE.
- **Fixture.** The scenarios use the dev library's `2024-08-20 - Två kapitel - Tjörn`: `s1710001.mp4` in Main, and
  `s1710002.mp4` and `s1710003.mp4` in Kvällen.

## 0. Gate

- [ ] 0.1 Dependency gate: `editor-shortcuts` MUST be archived, and all of these must succeed from the repo root:
  - `ls -d openspec/changes/archive/*-editor-shortcuts`
  - `grep -q "Requirement: The workspace lists its keyboard shortcuts" openspec/specs/web-app/spec.md`
  - `test -f web/src/edit/workspace/shortcuts.ts && test -f web/src/edit/workspace/modality.ts`

  If any of them fails, STOP and report which check failed.

## 1. Rules (pure modules)

- [x] 1.1 Add `web/src/timeline/clipMenu.ts` (design D2): `clipMenu`, `MENU_LOCKED`, `menuSelects` and `focusAfter`.
  Verify with `clipMenu.test.ts`, which must check:
  - the items' order, groups and labels;
  - Move to: one item per other chapter, in the chapters' order, and none when one chapter is drawn;
  - `cutWhy` and `posterWhy` land on their own items only;
  - while locked: the note is set and every item is unavailable under it, over the playhead's reasons;
  - `menuSelects` is false for the clip and for a cut of it, and true for nothing, another clip, a card or a
    suggestion;
  - `focusAfter` gives the next clip, the previous one at the end, and null for a lone clip.
- [ ] 1.2 Add `web/src/ui/menu.ts` (design D3): `menuKey` and `placeMenu`. Verify with `menu.test.ts`, which must
  check:
  - Up on the first item wraps to the last, Down on the last wraps to the first, and Home and End go to the ends;
  - Enter and Space choose, and Escape, Tab and Shift+Tab close;
  - Ctrl+S and Cmd+Z `pass`;
  - W, Right and Alt+Left `keep` with `preventDefault`, and F5 `keep`s without it;
  - a point 20 px from the right edge of 1280×720 flips left, and one near the bottom flips up;
  - a 320×568 view clamps to 8 px, with `maxHeight` 552;
  - a box with room only above it opens above.

## 2. The menu and its wiring (web/src/ui, web/src/timeline)

- [ ] 2.1 Build the menu and its openers. The items may do nothing until 2.2.
  - `ui/Menu.tsx` and the `.menu` styles (design D3, D7).
  - The Timeline's one `openClipMenu` (D1).
  - The track's openers (D4):
    - the delegated `onContextMenu`;
    - `data-identity` on `.tl-clip-press` and `.tl-trims`;
    - Shift+F10, the Menu key and `aria-keyshortcuts` on the block;
    - `ClipDrag`'s `contextmenu` listener.

  Verify with `npm test` and `npm run check`, then in Playwright (Chromium):
  - A right-click on the body of `s1710003.mp4`, on an edge tool and on a cut's handle opens its menu at the pointer
    and selects it (Clip tab), with the playhead unmoved and the `contextmenu` event `defaultPrevented`. On the
    "Kvällen" card block and on the empty track, the event is not `defaultPrevented`.
  - With the second cut of `s1710002.mp4` selected, a right-click on that clip keeps the cut selected.
  - The menu is still open after the right button comes up.
  - Tab to the block of `s1710002.mp4`, then Shift+F10: the menu opens under the block with Rotate left focused. Up
    wraps to Ignore clip. Escape closes the menu with focus on the block and the clip still selected.
  - A right-button press moved 20 px drags nothing.
  - A right-click during a drag puts every clip back and opens no menu.
  - A right-click during a Trim In drag opens no menu.
- [ ] 2.2 Wire the items to their edits (design D2, D5). Lift "+ Cut at playhead" out of `ClipCuts` into
  `addCutAtPlayhead`, which the Clip tab and the menu share.

  Verify with `npm test` and `npm run check`, then in Playwright run every scenario of these `web-app` requirements:
  - "Edit mode offers a clip's edits in a menu"
  - "An unavailable item in the clip menu says why"
  - "The clip menu gives focus back and closes when it is done"

  Also check that:
  - Undo says "Undo rotation of s1710002.mp4", "Undo move of s1710003.mp4", "Undo cut added", "Undo poster" and
    "Undo ignore of s1710002.mp4" after the matching item;
  - the Clip tab's "+ Cut at playhead" still makes the same cut and gives the same refusal;
  - during a save (with the PUT held), Enter on Rotate right announces `MENU_LOCKED` and turns nothing;
  - after Ignore clip chosen by keyboard, focus is on the block of `s1710003.mp4`;
  - after Move to Main, focus is on the block of `s1710003.mp4`, now in Main.
- [ ] 2.3 Add the two `SHORTCUTS` rows (design D6). Add a paragraph to `web/README.md` beside the `editor-shortcuts`
  one. Verify that `shortcuts.test.ts` still passes, then in Playwright check that:
  - the Keyboard shortcuts list shows both rows;
  - with the playhead in `s1710002.mp4` and its menu opened by a right-click, pressing W, Right, then Space on Rotate
    left trims nothing, leaves the playhead where it was, does not play, and turns the clip left once;
  - with the menu of an included `s1710004.mp4` open, Ctrl+Z undoes the include and closes the menu.

## 3. Verification and record

- [ ] 3.1 Run Playwright in Chromium and Firefox over every scenario of both deltas (`web-app`, `event-timeline`).
  Also check that:
  - on this Linux host, a real right-click (press, then release) leaves the menu open in both browsers (design,
    "Popover: manual, auto, or a dialog");
  - in screenshots of the menu in light and dark at 1440, 1100 and 390 px (390 px with a coarse pointer), one of them
    with unavailable items, nothing is clipped, and the reason text measures at least 4.5:1;
  - at 390×844 with a coarse pointer, every item's box is at least 44 px tall and the page does not scroll sideways;
  - in Chromium with touch emulation, a held touch on `s1710002.mp4` (CDP `Input.dispatchTouchEvent`) opens its menu
    and starts no drag. If the emulation sends no `contextmenu`, write that down here rather than fake the event.
- [ ] 3.2 Record the change:
  - HLD: add a D-28 "Clip menu" bullet: one menu owned by the Timeline, a manual popover and why, the items as
    existing edits, Cut and poster at the playhead, the track only until `plain-clip-bin`, and the touch rule. Add
    "Slice 7 is built" to §6 item 10.
  - `docs/editor-workspace.md`: add row 7, `clip-context-menu`, and note that it reverses the context-menu half of
    `compact-bin-tools`' non-goal.
- [ ] 3.3 Gates:
  - `npm test`, `npm run check` and `npm run build` in podman;
  - `openspec validate clip-context-menu --strict`.

  The Python gates (black/isort, mypy, pylint, pytest) have nothing to check: `git status --short` lists no file
  under `auto_reel_ng/` or `tests/`.
