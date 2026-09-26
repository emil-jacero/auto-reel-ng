## 0. Prerequisite

- [x] 0.1 Confirm `events-list-job-status-contract` is applied. Verify `web/src/api/schema.d.ts` types `JobSummaryOut.status` as the `JobStatus` union and contains `ProblemOut`. If not, apply that change first.

## 1. web/ — data and vocabulary

- [x] 1.1 Add `src/api/events.ts`: the response type aliases derived from `components['schemas']`, plus `fetchEvents(signal)` returning the `EventsResult` union. Parse 502/503 as `ProblemOut`; treat fetch rejection or an undeclared status as `unreachable`; rethrow `AbortError` (design "How a failed read becomes a cause"). Verify `npx tsc --noEmit` passes.
- [x] 1.2 Add `src/events/labels.ts` with `REASON_LABEL` and `JOB_STATUS_LABEL`, typed `Record<union, string>` (design "Label maps"). Verify exhaustiveness in both directions: temporarily delete one key and `tsc --noEmit` fails; temporarily add a bogus key and it fails again; restore, and it passes.
- [x] 1.3 Add `src/events/grouping.ts` with `groupByYear` and `needsRender` (design "Grouping and ordering"). Verify `tsc --noEmit` passes. Ordering is checked on screen in 3.1.

## 2. web/ — the screen

- [x] 2.1 Add `src/events/EventList.tsx`: the loading, ready and failed states; the summary; the needs-render filter; refresh with abort; one table per year group; the row columns per design "Rendering the rows". Verify `tsc --noEmit` passes.
- [x] 2.2 Replace `src/App.tsx` with `<EventList />`, and add `src/app.css` (theme tokens with a dark-mode override, per design "Theme"). Verify:
  - `tsc --noEmit` passes
  - `npm run build` in the node:22 container produces `web/dist`
  - `package.json` dependencies are unchanged

## 3. Verification against the dev library

- [x] 3.1 With `auto-reel serve ../auto-reel-dev/library` and the Vite dev server running, open <http://127.0.0.1:5173/> and check every item below.
  - **Summary:** it reads "6 of 9 events need rendering".
  - **Groups:** 2024, then 2023, then "No date" (containing `2024/Blandat`), each ordered newest date first.
  - **Grillning** (title "Grillkväll med grannarna"): needs render, "edited since last render, movie file missing", last job Rendered.
  - **Badutflykt:** needs render, "clips changed", 1 new, last job Rendered.
  - **Sommarlov:** 1 missing, "never rendered", no job.
  - **Trasig:** last job Failed.
  - **Blandat:** last job Queued.
  - **Fresh events:** both Midsommar events and Kalas 07-14 show "Up to date".
  - **Filter:** on, it leaves exactly the 6 stale events.
  - **Refresh:** add a symlinked clip to `2024-07-14 - Kalas`, refresh, and it shows as needing a render with "clips changed" and 1 new.
- [x] 3.2 Check the failure states:
  - `podman stop auto-reel-ng-dev-db` then refresh: the database message shows and no events are listed.
  - Restart the database. Put an unparseable `reel.yaml` in one event and refresh: the scan-failure message names that event. Restore it.
  - Stop `auto-reel serve` and refresh: the "service is not reachable" message shows.
  - Finish by rebuilding the dev library with `scripts/make_dev_library.py ../auto-reel-dev`.
- [x] 3.3 Update `web/README.md`: it no longer says there is no screen, and it names `src/events/` and `src/api/events.ts`. Verify by rereading it against the files.

## 4. Validation

- [x] 4.1 Run `npx tsc --noEmit` and `npm run build` in the node:22 container, and the full `.venv/bin/python -m pytest` (the web-mount and OpenAPI drift tests must stay green). Verify all pass.
