## 1. web/ — routing and shared pieces

- [x] 1.1 Add `src/route.ts` (`Route`, `parseRoute`, `eventHref`, `useRoute`) per design "Routing without a router". Move `readJson` and `isProblem` into `src/api/http.ts`. Move `JobCell`, `folderName` and `plural` into `src/events/common.tsx`, and add `formatBytes` there. Verify:
  - `npx tsc --noEmit` passes in the node:22 container
  - the list renders exactly as before (checked in 4.1)
- [x] 1.2 Add `src/api/event.ts` (the detail aliases and `fetchEvent`, where 404/502/503 are problems), and `CLIP_STATUS_LABEL` in `src/events/labels.ts` (design "Reading one event", "Labels"). Verify `tsc --noEmit` passes. Temporarily deleting one `CLIP_STATUS_LABEL` key makes it fail; restore it.

## 2. web/ — the page and the navigation

- [x] 2.1 Add `src/events/EventDetail.tsx`: the load, refresh and abort states; the header, status line and counts; the missing warning; per-chapter tables; the failure descriptions (design "The page"). Verify `tsc --noEmit` passes.
- [x] 2.2 Wire `App.tsx` as follows (design "Keeping the list alive"). Verify that `tsc --noEmit` and `npm run build` pass, and that `package.json` dependencies are unchanged.
  - `useRoute` picks the page
  - the list mounts lazily and stays mounted, hidden while an event page is shown
  - scroll is saved and restored, with `history.scrollRestoration = 'manual'`
  - `document.title` is set per page
  - `EventList` event titles link to `eventHref(event_id)`; "Needs attention" rows stay unlinked

## 3. Dev library

- [x] 3.1 Add `2024/2024-08-20 - Två kapitel - Tjörn` to `scripts/make_dev_library.py`: phase 1 renders a root clip plus a `Kvällen/` chapter; phase 2 adds an ignored root clip and a NEW `Kvällen/` clip (design "The dev library event"). Update `web/README.md`'s dev-library text: 11 events (10 listed, 1 needs attention), plus a bullet for the chapter, IGNORED and NEW-in-chapter states. Verify:
  - `.venv/bin/python scripts/make_dev_library.py ../auto-reel-dev` exits 0
  - `GET /api/v1/events/2024/2024-08-20%20-%20Tv%C3%A5%20kapitel%20-%20Tj%C3%B6rn` returns chapters `""` and `Kvällen`, with statuses `active`, `ignored`, `active`, `active` and `new`

## 4. Verification against the dev library

- [x] 4.1 Start the dev database (`podman start auto-reel-ng-dev-db`), `auto-reel serve ../auto-reel-dev/library`, and the Vite dev server, then open <http://127.0.0.1:5173/>. Check each item:
  - **List:** unchanged. "7 of 10 events need rendering · 1 needs attention"; event titles are links; the attention row is not.
  - **Två kapitel:** its page shows a `Main` table (included and ignored clips) and a `Kvällen` table (two included clips and a new one), with statuses in words, sizes and times, and counts "5 clips · … · 1 new · 1 ignored".
  - **Sommarlov:** its page warns that `borttagen.mp4` is missing, and that row shows `—` for size and time.
  - **Grillning:** its page shows "Needs render" with "edited since last render, movie file missing".
  - **Back:** with the filter on, scroll down, open an event, press Back. The filter is still on, the scroll position is restored, and neither the browser's network panel nor the `serve` access log shows a new `GET /api/v1/events` (list) request.
  - **Reload:** reloading an event page (for example Två kapitel, whose name has `å`) shows the same event.
  - **Unknown and malformed addresses:** typing `#/event/2024/nope` shows "not found" with a link back; `#/nonsense` and `#/event/%E0%A4%A` show the list.
  - **Unreadable event:** typing the hash of `2024-02-30 - Omöjligt datum` shows the same failure words and detail as its attention row.
  - **Database down:** `podman stop auto-reel-ng-dev-db`, then Refresh on an event page, shows the database message. Restart the database afterwards.

## 5. Validation

- [x] 5.1 Run `npx tsc --noEmit` and `npm run build` in the node:22 container. Also run `.venv/bin/python -m black scripts && .venv/bin/python -m isort scripts` and the full `.venv/bin/python -m pytest` (the web-mount and OpenAPI drift tests must stay green). Verify all pass.
