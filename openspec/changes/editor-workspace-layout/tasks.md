All tasks are in `web/` (plus the HLD). Node runs only in podman (`docker.io/library/node:22`); Playwright runs from
the scratchpad, never from the repo, with PUT/POST/DELETE intercepted except the write being tested.

## 0. Gate

- [x] 0.1 Dependency gate — `track-draft-order` MUST be finished. From the repo root all three must succeed:
  `test ! -d openspec/changes/track-draft-order` (not active),
  `git ls-tree -d --name-only main openspec/changes/archive/ | grep -q -- '-track-draft-order$'` (archived on `main`),
  `grep -q "Requirement: The Edit-mode Timeline draws the draft" openspec/specs/event-timeline/spec.md` (spec merged).
  If any fails, STOP: do not start this change; report which check failed and that `track-draft-order` comes first.
- [x] 0.2 Spec freshness: re-read the main `web-app` and `event-timeline` specs; confirm the MODIFIED/REMOVED headers
  above still exist verbatim, and list every other `web-app` requirement that assumes the stacked page (sticky
  panels, focus scrolled into view, save bar at the bottom). Add REMOVED/MODIFIED blocks for them here before 1.1.

## 1. Timeline split (web/src/timeline)

- [x] 1.1 Extract `useTimeline` from `Timeline.tsx` and render `TimelineViewer`, `TimelineTrack`, `TimelineCutPanel`
  from it (design D2); one `<video>`. Verify `npm test`, `npm run check`, and that today's Edit page still works with
  the three parts stacked (no layout change yet).
- [x] 1.2 Add Previous / Next clip to the viewer's transport (playhead to the first kept frame of the drawn clip).
  Verify with a `keys.test.ts` / model test for the target place.

## 2. Workspace frame (web/src/edit/workspace, web/src/events)

- [x] 2.1 Add `Workspace` (grid, panes, CSS for light and dark, stacking below 960 px) and render it from
  `EventDetail` in Edit mode with the app header hidden (design D1). Verify `npm run check` and a Playwright
  screenshot at 1440×900, 1280×720 and 390 px, both themes.
- [x] 2.2 Top bar: move `SaveBar` states into it (design D4), title/date/location, back control, theme switch.
  Verify the save, 412 and failure paths with Playwright (route only the write being tested).

## 3. Panes (web/src/edit)

- [x] 3.1 Bin: compact row variant of `ClipOrderList` inside `ChapterDrag`, windowed (design D3). Verify keyboard
  reorder, cross-chapter move, marks, Add chapter, New/Ignored/Missing with Playwright.
- [ ] 3.2 Inspector with Event and Cut tabs (Details, Poster, Title cards switch, card style; `TimelineCutPanel`);
  selecting a cut or suggestion shows Cut. Verify with Playwright.

## 4. Verification and docs

- [ ] 4.1 Gates: `edit-list-paint-cost` drag in Chrome 4x, 400-clip bin windowing, no horizontal scroll 320–1440 px,
  bundle size before/after.
- [ ] 4.2 HLD: new D-n "Edit mode is a workspace" (frame, panes, no List view) and §6 item 10 note; tick slice 1 in
  `docs/editor-workspace.md`.
- [ ] 4.3 Gates: `npm test`, `npm run check`, `npm run build` in podman; `openspec validate editor-workspace-layout --strict`.
