All tasks are in `web/` for option A (plus the HLD). Node runs only in podman (`docker.io/library/node:22`);
Playwright runs from the scratchpad, never from the repo, with PUT/POST/DELETE intercepted except the write being tested.

## 0. Gates

- [ ] 0.1 Dependency gate — `track-drag-edit` MUST be finished. From the repo root all three must succeed:
  `test ! -d openspec/changes/track-drag-edit`,
  `git ls-tree -d --name-only main openspec/changes/archive/ | grep -q -- '-track-drag-edit$'`,
  `grep -q "Requirement: A clip is reordered by dragging it on the track" openspec/specs/event-timeline/spec.md`.
  If any fails, STOP: do not start this change; report which check failed.
- [ ] 0.2 Check `reel/` and the `reel-document` spec: is a zero-length trim (`a..a`) legal, and is there any place a
  split point could be stored without a schema change? Record the answer in design.md D1.
- [ ] 0.3 Decision gate — run `/opsx:explore clip-split` with the user and record option A, B or C in design.md
  "Research & Decisions". STOP here until the user has chosen. If B: rewrite this change into the first of several
  small changes (schema → write API → web) and replace the tasks below. If C: delete this change and mark §6.12
  dropped in `docs/editor-workspace.md`.

## 1. Option A only (web/src/timeline, web/src/edit)

- [ ] 1.1 Pure model: split point at the playhead, the availability rules (card, cut, three frames, pending save), the
  two drawn blocks. Verify `split.test.ts` with the delta's scenarios.
- [ ] 1.2 Draft action and the storage chosen in 0.2; Split button and `B` key, announcements. Verify `npm test`,
  `npm run check`, Playwright (split, save, reload shows the split, Undo if `editor-undo` is archived).

## 2. Verification and docs

- [ ] 2.1 HLD: D-n for the split model; tick slice 5 in `docs/editor-workspace.md`.
- [ ] 2.2 Gates: `npm test`, `npm run check`, `npm run build` in podman; `openspec validate clip-split --strict`.
