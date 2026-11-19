All work is in `web/`, plus the HLD and `docs/editor-workspace.md`.
- **Node** runs only in podman (`docker.io/library/node:22`), with the repo root mounted and `-w /app/web`. Some web
  tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo. It intercepts PUT, POST and DELETE.

## 0. Gate

- [ ] 0.1 Dependency gate: `editor-undo` MUST be archived, and both of these must succeed from the repo root:
  - `ls -d openspec/changes/archive/*-editor-undo`
  - `grep -q "Requirement: Edit mode undoes and redoes draft edits" openspec/specs/web-app/spec.md`

  If either fails, STOP and report which check failed.

## 1. Rules (web/src/edit/workspace)

- [x] 1.1 Add `shortcuts.ts` (design D1). It holds:
  - the `SHORTCUTS` table (groups Playback, Zoom, Editing, Mouse, in words);
  - `workspaceCommand`, which reuses `playheadKey`, `trackZoomKey`, `clipMoveKey` and `isTextTarget`;
  - `focusFacts` over element-like objects.

  Verify with `shortcuts.test.ts`. It must cover every rule of D1 in its order, including:
  - a held Space gives `hold`;
  - Space on a button gives `null` when reached by keyboard and toggle after a pointer press;
  - arrows on a range or `role=slider` give `null`;
  - AltGr characters;
  - every `workspace` row maps to a command, and every command has a row.
- [x] 1.2 Add `modality.ts` (design D2): `nextModality`, `lastInput()`, `pointerHeld()`, and the install hook used by
  `Workspace.tsx`. Verify with `modality.test.ts`, which must check that:
  - Tab gives `keyboard` and a pointer press gives `pointer`;
  - an arrow keeps the last input;
  - the start value is `keyboard`;
  - pointer-held clears on `pointerup`, `pointercancel`, `contextmenu` and `blur`.

## 2. Wiring (web/src/timeline, web/src/edit/workspace)

- [x] 2.1 Add the document listener in `useTimeline`, active only in the workspace (design D3).
  - Lift the Alt+arrow code out of `Track.tsx` into `moveSelected(way)`, shared by the track and the listener.
  - The clip block gives up Space after a pointer press.

  Verify with `npm test` and `npm run check`, then in Playwright:
  - Space after a click on a clip, on the picture, and on Rotate plays (and Rotate turns the clip once);
  - Space on Rotate reached by Tab turns the clip;
  - typing a space in Title only types.
- [ ] 2.2 Move the Ctrl+wheel listener to `.tl-track-part` through a callback ref, with the pointer or playhead anchor
  (design D6). Verify in Playwright:
  - over the track, the moment under the pointer stays;
  - over the tool row, the playhead keeps its place;
  - over the viewer, the wheel event is not `defaultPrevented` and the zoom is unchanged.
- [ ] 2.3 Add the top bar's "Keyboard shortcuts" button and the `#ws-keys` popover drawn from `SHORTCUTS`, plus `?`
  and the single-key switch with its storage (design D4, D5). `useSelection`'s Escape yields while the list is open.

  Add a paragraph to `web/README.md` beside the editor-undo one. Verify in Playwright:
  - `?` opens the list;
  - Escape closes only the list and the selection is kept;
  - Space works with the list open;
  - with the switch off, Space after a click on the picture does nothing, Space on the ruler plays, and the switch is
    still off after leaving Edit mode and entering it again;
  - screenshots of the list in light and dark at 1440, 1100 and 390 px, looked at for clipping and contrast.

## 3. Verification and record

- [ ] 3.1 Run Playwright in Chromium and Firefox over every scenario of both deltas (`web-app`, `event-timeline`).
  Also check that:
  - Space after clicking a mark checkbox in the bin plays and does not toggle the mark;
  - Space during a trim drag changes nothing;
  - a held Space does not flap between Play and Pause;
  - the frame-step gate still holds with the key coming through the workspace layer: p90 ≤ 60 ms over 40 Right
    presses, in Chromium.
- [ ] 3.2 Record the change:
  - HLD: a D-28 "Shortcuts" bullet (the workspace layer, the last-input rule for Space, the 2.1.4 switch), and "Slice 6
    is built" in §6 item 10.
  - `docs/editor-workspace.md`: add row 6 `editor-shortcuts`, and mark row 5 `clip-split` dropped (its change was
    removed on `main` on 2026-11-18).
- [ ] 3.3 Gates: `npm test`, `npm run check` and `npm run build` in podman; `openspec validate editor-shortcuts
  --strict`.
