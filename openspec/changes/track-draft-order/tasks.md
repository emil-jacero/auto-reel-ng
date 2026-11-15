All tasks are in `web/` (plus the HLD). Node runs only in podman (`docker.io/library/node:22`); Playwright runs from
the scratchpad, never from the repo, with PUT/POST/DELETE intercepted except the write being tested.

## 0. Gate

- [ ] 0.1 Dependency gate: this change has **no** dependency change. Confirm the ground is clear before starting:
  `openspec list --json` lists no other active change that touches `web/src/timeline/` or the `event-timeline` spec
  (if one does, STOP and ask which goes first), and `git status` on `main` is clean.
- [ ] 0.2 Spec freshness: compare the REMOVED + ADDED pair in `specs/event-timeline/spec.md` with the current
  `openspec/specs/event-timeline/spec.md` requirement "The Timeline is shown only in Edit mode, open from the start"; carry over any text changed since 2026-11-15.

## 1. Pure model (web/src/timeline)

- [x] 1.1 Add `draftClips(live, chapters, orders)` to `timeline/layout.ts` (design D1). Verify with
  `layout.test.ts` cases: reorder, cross-chapter move, deleted chapter, added chapter, identity without facts counted
  as missing, ignored skipped, names follow the draft.
- [x] 1.2 Add the card mapping to `timeline/cards.ts`: resolved card by `readName`, `synthCard` for added chapters,
  placeholder when nothing resolved (design D2). Verify with `cards.test.ts` (rename keeps duration/background, black
  added card shifts later clips, title cards off draws none, no resolved card → placeholder words).

## 2. Wiring (web/src/edit, web/src/timeline)

- [ ] 2.1 Pass the draft's `chapters` and `orders` from `edit/EventEditor.tsx` through `TimelineSection` to `Timeline`;
  use `draftClips` in Edit mode; memoise on the three inputs. Verify with `npm test` and `npm run check`.
- [ ] 2.2 Remove `ORDER_SAVED` and its `Alert` (`timeline/labels.ts`, `Timeline.tsx`) and the `orderChanged` note path.
  Verify `grep -rn ORDER_SAVED web/src` is empty and `npm run check` passes.

## 3. Browser verification (scratchpad only)

- [ ] 3.1 Playwright in Chrome and Firefox against a dev service with its own DB, port and library copy: every
  scenario of the delta (reorder drawn, Reset, deleted chapter, added chapter's black card shifts clips, rename keeps
  card, Play order), light and dark at 1280 and 390; screenshots looked at.
- [ ] 3.2 Gates: the 80-clip drag measurement of `edit-list-paint-cost` (Chrome 4x) still passes; 400-clip windowing
  unchanged; bundle size before/after recorded.

## 4. Docs and validation

- [ ] 4.1 Amend D-20 in `docs/high-level-design.md` (the Edit-mode Timeline draws the draft order; added chapters'
  cards built in the browser) and the §6 item 10 note; tick `docs/editor-workspace.md` slice 0.
- [ ] 4.2 Gates: `npm test`, `npm run check`, `npm run build` in podman; `openspec validate track-draft-order --strict`.
