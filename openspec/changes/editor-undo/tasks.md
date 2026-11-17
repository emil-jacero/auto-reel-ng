All tasks are in `web/` (plus the HLD). Node runs only in podman (`docker.io/library/node:22`); Playwright runs from
the scratchpad, never from the repo, with PUT/POST/DELETE intercepted except the write being tested.

## 0. Gate

- [ ] 0.1 Dependency gate — `editor-workspace-layout` MUST be finished. From the repo root all three must succeed:
  `test ! -d openspec/changes/editor-workspace-layout`,
  `git ls-tree -d --name-only main openspec/changes/archive/ | grep -q -- '-editor-workspace-layout$'`,
  `grep -q "Requirement: The workspace's top bar holds the event and the save controls" openspec/specs/web-app/spec.md`.
  If any fails, STOP: do not start this change; report which check failed.
- [ ] 0.2 Note which of `editor-selection` and `track-drag-edit` are archived; their actions get labels in 2.1 and
  their scenarios are added to 3.1. Neither is required.

## 1. Model (web/src/edit)

- [x] 1.1 Add `history.ts` (`record`, `undo`, `redo`, `cleared`, coalescing, 200-step cap; design D1). Verify
  `history.test.ts`: undo/redo, new edit clears future, coalescing by key and time, cap, cleared.

## 2. Wiring

- [x] 2.1 Wrap the editor's reducer; give every action a label and field actions a coalesce key; Save and Reload
  latest clear, Reset records (D2). Verify `npm test` and `npm run check`.
- [x] 2.2 Top-bar Undo/Redo with step names, keys at the workspace frame with the text-field and drag exceptions (D3),
  announcements. Verify with Playwright.

## 3. Verification and docs

- [ ] 3.1 Playwright: every scenario of the delta, plus trim release, approve suggestion, card field, chapter rename,
  rotate and poster each undo in one step; light/dark.
- [x] 3.2 HLD: amend the workspace D-n (history wraps the reducer; Save clears); tick slice 4 in `docs/editor-workspace.md`.
- [ ] 3.3 Gates: `npm test`, `npm run check`, `npm run build` in podman; `openspec validate editor-undo --strict`.
