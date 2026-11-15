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
- [x] 3.2 Inspector with Event and Cut tabs (Details, Poster, Title cards switch, card style; `TimelineCutPanel`);
  selecting a cut or suggestion shows Cut. Verify with Playwright.

## 4. Verification and docs

- [x] 4.1 Gates: `edit-list-paint-cost` drag in Chrome 4x, 400-clip bin windowing, no horizontal scroll 320–1440 px,
  bundle size before/after.
  Status (2026-11-15, load 1.1-2.4; production builds of this branch and `origin/main` 7538e62c served by `vite
  preview` against the same API and library; Playwright 1.49 Chromium, scripts in SCRATCH: rAF frame deltas during
  the input, % over 25 ms; a 400-clip event served by `page.route` from Grillning's four clips, as no fixture has 400):
  zoom-slider drag Fit -> 159 px/s on 400 clips at 1280x800, Chrome 4x (`Emulation.setCPUThrottlingRate`, a busy loop
  3.6-4x slower), five launches of three drags: launch medians 0 / 0.32 / 0.28 / 0 / 0.84 % -> median 0.28 % (p95
  16.8 ms), idle 0 % in all five; `origin/main` (the stacked page) 0 / 0.53 / 0 / 0.28 / 0 % -> median 0 %. The gate
  (<= 2 %) holds. Not a gate before, for the record: a pointer drag of a bin row down the 400 clips with auto-scroll at
  4x 41-44 % (`origin/main`'s page 65-73 %; during a dnd-kit drag every row carries a transform and is drawn on both).
  Windowing, 400 clips: in the 1280/1440 bin 13-14 of 400 rows drawn on opening, 14-16 after scrolling to the end in
  half-view steps (none farther than 1,500 px from the pane), every step's scroll position kept (0 px drift over
  185-211 steps), scroll height +0.2 %; at 390 (the page scrolls) 0 drawn on opening, 25 at the end, +0.3 %
  (`origin/main` +0.09 %). A wheel scroll through the bin: 0 % at 1x on both builds; at 4x 22-40 % (frames of 33 ms)
  against `origin/main`'s 26-59 % (idle 0 % on both). Sideways overflow, Edit mode on Grillning (the 400-clip event)
  and Tjörn, both inspector tabs, at 320/360/390/768/959/960/1024/1280/1440 and a sweep 320-1460 in 8 px steps: page
  and every pane 0 px, no element past its pane, after two fixes: the readout's time pairs scrolled the page 10-50 px
  under a 28rem Timeline (now a row of their own; `origin/main`'s page has 17 px at 320), and in the 340 px inspector
  the poster area's window-width two columns put Use default 91 px outside the pane (one column there). Bundle (`vite
  build`, `origin/main` -> this branch): JS 665.78 kB (gzip 215.85) -> 677.79 kB (gzip 219.04), +12.01 kB (+3.19
  gzip); CSS 95.71 kB (gzip 18.14) -> 105.07 kB (gzip 19.91), +9.36 kB (+1.77 gzip); index.html 1.48 kB unchanged.
- [ ] 4.2 HLD: new D-n "Edit mode is a workspace" (frame, panes, no List view) and §6 item 10 note; tick slice 1 in
  `docs/editor-workspace.md`.
- [ ] 4.3 Gates: `npm test`, `npm run check`, `npm run build` in podman; `openspec validate editor-workspace-layout --strict`.
