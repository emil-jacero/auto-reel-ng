All tasks are in `web/` (plus the HLD). Node runs only in podman (`docker.io/library/node:22`); Playwright runs from
the scratchpad, never from the repo, with PUT/POST/DELETE intercepted except the write being tested.

## 0. Gate

- [x] 0.1 Dependency gate — `editor-workspace-layout` MUST be finished. From the repo root all three must succeed:
  `test ! -d openspec/changes/editor-workspace-layout`,
  `git ls-tree -d --name-only main openspec/changes/archive/ | grep -q -- '-editor-workspace-layout$'`,
  `grep -q "Requirement: Edit mode is a full-window workspace" openspec/specs/web-app/spec.md`.
  If any fails, STOP: do not start this change; report which check failed.
- [x] 0.2 Spec freshness: confirm both REMOVED headers still exist verbatim in the main specs; sweep `web-app` and
  `event-timeline` for card requirements that mention the dialog (focus return, Escape closes the dialog, full-screen
  sheet) and add REMOVED/MODIFIED blocks for them here before 1.1.

## 1. Model (web/src/edit/workspace)

- [x] 1.1 Add `selection.ts` (`Selection`, `keptSelection`, `inspectorTab`, design D1). Verify `selection.test.ts`:
  each kind's tab, one ends the other, gone target → none, cut → clip tab.

## 2. Wiring

- [x] 2.1 Hold the selection in `EventDetail`; replace `Track`'s cut selection, `useSuggestions`' `selectedId` and the
  card selection with it. Verify `npm test`, `npm run check`, and the existing cut/suggestion/card Playwright checks.
- [x] 2.2 Clip press on the block body and on the bin row (design D2, D4); outline, highlight, scroll into view.
  Verify with Playwright (press, Escape, empty track, bin→track scroll, focus stays).

## 3. Inspector (web/src/edit)

- [x] 3.1 `Inspector.tsx` with Clip · Title card · Suggestion · Event tabs following the selection. Verify Playwright, and that each kind's selection (clip, cut,
  title card, suggestion) is announced once through the polite status (today only the card's is).
- [x] 3.2 Clip tab: typed Trim In/Out through the edge-edit action, rotate, cuts list, "+ Cut at playhead", poster
  (Ignore clip moved to track-drag-edit). Verify `edgeEdit.test.ts` case for typed trims and Playwright.
- [x] 3.3 Dock the card editor (design D3): remove the `Dialog` wrapper, preview above fields. Verify Playwright: no
  dialog opens, edits counted in the top bar, both tabs work.

## 4. Verification and docs

- [x] 4.1 Gates: paint-cost drag (Chrome 4x), Tab order per clip, light/dark, 1280×720 and 390 px.
- [ ] 4.2 HLD: amend the workspace D-n (one selection, docked card editor); tick slice 2 in `docs/editor-workspace.md`.
- [ ] 4.3 Gates: `npm test`, `npm run check`, `npm run build` in podman; `openspec validate editor-selection --strict`.
