All tasks are in `web/` (plus the HLD). Node runs only in podman (`docker.io/library/node:22`); Playwright runs from
the scratchpad, never from the repo, with PUT/POST/DELETE intercepted except the write being tested.

## 0. Gate

- [ ] 0.1 Dependency gate — `editor-selection` MUST be finished. From the repo root all three must succeed:
  `test ! -d openspec/changes/editor-selection`,
  `git ls-tree -d --name-only main openspec/changes/archive/ | grep -q -- '-editor-selection$'`,
  `grep -q "Requirement: One selection in the workspace" openspec/specs/event-timeline/spec.md`.
  Also confirm `track-draft-order` is archived the same way (this change needs the draft order drawn).
  If any fails, STOP: do not start this change; report which check failed.
- [ ] 0.2 Spec freshness: re-read `timeline` and `event-timeline`; confirm no requirement still says the order is
  edited only in the lists; add MODIFIED blocks here if one does.

## 1. Model (web/src/timeline)

- [ ] 1.1 Add `reorder.ts` (`dropSlot`, `applyDrop`, design D1). Verify `reorder.test.ts` with every scenario of the
  `timeline` delta plus cards between chapters and a 400-clip lay.

## 2. Drag (web/src/timeline, web/src/edit)

- [ ] 2.1 `ClipDrag` on the block body via `dragStore` (claim, 3 px slop, capture, Escape, live shift, slot line and
  words, design D2); release dispatches the lists' reducer actions (D3). Verify `dragStore.test.ts` and Playwright.
- [ ] 2.2 Bin↔track include/ignore adapter, through 2.2a's edit. Verify with Playwright (New clip in, clip out to Ignored).
- [ ] 2.2a The draft ignore/include edit: a draft field in `draft.ts`, `buildWriteBody`'s `ignore`, `isDirty`, Reset,
  the top bar and save counts, one reducer action in `EventEditor.tsx` (design D5). Verify `draft` node tests and the
  save body.
- [ ] 2.2b "Ignore clip" button in the inspector's Clip tab (`timeline/ClipTab.tsx`). Verify with Playwright.
- [ ] 2.3 Alt+Left/Right on a selected clip, announcements, inert while pending (D4). Verify `keys.test.ts` and Playwright.

## 3. Verification and docs

- [ ] 3.1 Gates: drag smoothness on an 80-clip event in Chrome 4x (as `clip-edge-trim` measured), Firefox, 400-clip
  windowing, light/dark, 1280×720.
- [ ] 3.2 HLD: amend D-20 (reorder on the track built in the repo; dnd-kit stays in the bin); tick slice 3 in
  `docs/editor-workspace.md`.
- [ ] 3.3 Gates: `npm test`, `npm run check`, `npm run build` in podman; `openspec validate track-drag-edit --strict`.
