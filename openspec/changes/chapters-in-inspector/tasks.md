All work is in `web/`, plus the HLD and `docs/editor-workspace.md`.
- **Node** runs only in podman (`docker.io/library/node:22`), with the repo root mounted and `-w /app/web`. Some web
  tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo. It intercepts PUT, POST and DELETE.

## 0. Gate

- [x] 0.1 Dependency gate: `clip-multi-select` MUST be archived, and both of these must succeed from the repo root:
  - `ls -d openspec/changes/archive/*-clip-multi-select`
  - `grep -q "Requirement: Dragging one of several selected clips moves them all" openspec/specs/event-timeline/spec.md`

  If either fails, STOP and report which check failed.

## 1. The Chapters list (web/src/edit)

- [ ] 1.1 Reword the empty chapter's hint in `emptyChapter.ts` so that it points at Move to… and no longer at dragging or
  Move marked to…. Verify with `emptyChapter.test.ts`: the alone and not-alone words, and that neither mentions "Move
  marked".
- [ ] 1.2 Add `ChapterList.tsx` (design D1) and render it in the Event tab after Details. It reuses `ChapterTools`,
  `DeletedChapter`, `AddChapter` and `EditTitlecard`, with the one-line row and the coarse-pointer wrap. Verify with
  `npm test` and `npm run check`, then in Playwright:
  - "A chapter's header in the bin is one row";
  - "Chapters while proxies are being prepared", with the proxies' read stubbed to not prepared;
  - "An empty chapter is listed".

## 2. The bin and focus (web/src/edit, web/src/edit/workspace)

- [ ] 2.1 Take `EditTitlecard`, `ChapterTools`, `DeletedChapter` and `AddChapter` out of the bin (design D2), and
  update the Clips help's sentence about Add chapter. Verify in Playwright:
  - "The bin holds no chapter tool";
  - "The hint says how to reach other chapters";
  - dragging a clip between the bin's chapters still works.
- [ ] 2.2 Focus back from the card editor to the row's Edit Titlecard button, with the fallback (design D3). Verify in
  Playwright with "Renaming with the keyboard only", "Escape drops what was typed" and "A refused rename keeps the field
  open", in Chromium and Firefox.

## 3. Verification and record

- [ ] 3.1 Run Playwright in Chromium and Firefox over every scenario of the delta (`web-app`). Also check that:
  - every chapter edit is one Undo step, with the labels it had;
  - the inspector at 390 px with a coarse pointer has no horizontal scroll, and its 44 × 44 targets do not overlap;
  - screenshots of the Event tab in light and dark at 1440, 1100 and 390 px show no clipping.
- [ ] 3.2 Record the change:
  - HLD D-28: the Event tab holds the Chapters list, and the bin holds no chapter tool, because the track may be
    absent and an empty chapter has no band. §6 item 10: this change is built.
  - `docs/editor-workspace.md`: add a row for `chapters-in-inspector`.
- [ ] 3.3 Gates: `npm test`, `npm run check` and `npm run build` in podman; `openspec validate chapters-in-inspector
  --strict`.
