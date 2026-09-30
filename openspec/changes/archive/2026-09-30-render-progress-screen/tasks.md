## 1. Gate

- [x] 1.1 Confirm the three gates are archived on `main`: `ls openspec/changes/archive/ | grep -E -- '-(web-design-system|jobs-client-contract|jobs-project-guards)$'` must print three directories. Stop and report to the supervisor if any is missing. Then confirm what this change builds on:
  - `web/src/api/schema.d.ts` defines `CancelOutcome`, `WsMessage`, `WsMessageType`, `FreshResult` and `EnqueueConflict`
  - `ProblemOut` has `job_id`, `conflict` and `claimed_by`, and `POST /api/v1/jobs` publishes 201, 200, 404, 409 and 502 in `web/openapi.json`
  - `auto_reel_ng/api/ws.py` `_tick` emits a delta when only `cancel_requested` changed, and emits once a job that became terminal since the previous tick although no earlier frame carried it (C2; C3 scopes it to the project), with a hub test for each
  - C1's `src/ui/Icon.tsx` (with `play`, `square` and `loader` in `IconName`), `src/ui/Dialog.tsx` (with `initialFocus?: RefObject<HTMLElement | null>`), `src/ui/Alert.tsx` (with an `action` slot), `src/ui/Pill.tsx`, `src/ui/Skeleton.tsx` (`LoadStatus`), `src/ui/toast.ts`, `src/events/tones.ts` (`JOB_STATUS_LOOK`), `src/events/changes.ts` (`markEventsChanged`, `currentEventsVersion`, `useEventsVersion`) and `src/shell/AppShell.tsx` (with `shell-status`) exist
  - C1's `EventDetail` header has the latest-job pill and a `LoadStatus` region, C1's `EventList` holds the version-triggered effect, and `EventDetail` has none (design "The render region on the event page", `onFinished`)
  - the seam with `event-edit-screen` is not decided here: task 7.1 is evaluated only at the pre-archive rebase. If `event-edit-screen` is already archived on `main`, confirm its `load()` never touches `editing` and every Edit-mode exit sets `editing` to false and then calls `load()` (design Context)
  - `openspec/specs/web-app/spec.md` holds C1's "A read in progress is shown as a placeholder and announced". Re-base this change's MODIFIED block on its current text, then re-run `openspec validate render-progress-screen --strict`: the "archive would refuse" note must be gone
  - record whether the jobs routes publish a 503 (a named follow-up; design, Open Questions)

  Verify: each `grep -n` for the names above hits. If a piece is missing, stop and report. If only a name differs (for example an icon called `stop` rather than `square`), use the landed name and list the difference in the final report; do not add or rename anything in C1's, C2's or C3's files.

## 2. web/ — the jobs API client and labels

- [x] 2.1 Add `src/api/jobs.ts`, per design "The jobs API client":
  - the schema aliases
  - `enqueueJob`, `fetchJob`, `cancelJob` and `jobsSocketUrl`
  - per-route problem statuses (enqueue 404/409/502, job read and cancel 404); everything else is `unreachable` with the status in the message
  - the exhaustive `switch` over `problem.conflict`, with a missing `job_id` or `claimed_by` treated as `unreachable`

  Add `src/jobs/labels.ts` with `CANCEL_OUTCOME_LABEL` and `CONNECTION_LABEL`, per design "Cancel". Verify:
  - `npx tsc --noEmit` passes in the node:22 container
  - temporarily deleting one `CANCEL_OUTCOME_LABEL` key makes `tsc` fail, and so does removing one `case` of the conflict switch; restore both

## 3. web/ — the live store and the header indicator

- [x] 3.1 Add `src/jobs/store.ts`'s connection lifecycle, per design "One shared WebSocket store":
  - `subscribe`, `getState`, and refcounted retain with a deferred release that does not reconnect
  - full-jitter backoff that resets only after a valid frame
  - the stale-socket guard, and reconnect on `online` only when no socket is open or connecting
  - frame validation and the `WsMessageType` switch
  - snapshot replace and delta merge (unchanged jobs keep their identity), and `merge`

  Add `src/jobs/JobsIndicator.tsx` in `AppShell`'s `shell-status` slot, and `src/jobs/jobs.css` (the `loader` spin declared only inside `@media (prefers-reduced-motion: no-preference)`, `1.2s linear infinite`). Verify, against the agent's own dev service (set up once, as 6.1's setup describes, and reused there; port 8105):
  - `tsc --noEmit` and `npm run build` pass
  - `web-design-system`'s motion grep gate passes over `web/src/jobs` (its three commands, listed in 6.1's "Motion and layout")
  - the header shows "Live · 1 queued" (`2024/Blandat`)
  - a Playwright `page.on("websocket")` count stays at 1 across list → event page → Back
  - killing `serve` shows "Reconnecting…" with no counts, and restarting it returns to "Live" with no reload (allow up to 35 s: the backoff is capped at 30 s)
- [x] 3.2 Add the rest of the store, per design "One shared WebSocket store", "Which job an event shows" and "Progress and ETA":
  - `load` with `force` and `knownActive`, and the set of requested ids (no repeat GET without `force`)
  - snapshot reconciliation: keep known terminal jobs, and force-load known-active jobs that are missing
  - `track` and `markAnnounced`
  - `src/jobs/eta.ts` sampling in the message handler
  - the terminal effects: toasts for tracked, unannounced jobs on live transitions only, and `markEventsChanged()` on every `done`, live, reconciled, or first seen already terminal (design "Transitions")

  Add `src/jobs/useJob.ts` (`useEventJob`, `useConnection`), with "terminal beats active for the same id". Verify:
  - `tsc --noEmit` passes
  - `eta.ts` and the reconciliation are pure functions over their inputs: no `Date.now()` or `fetch` inside, time passed in (code review)
  - the behavior is checked in 6.1 (reconnect gap, one toast per ending)

## 4. web/ — the event page

- [x] 4.1 Add `src/jobs/JobProgress.tsx` and `src/jobs/RenderControl.tsx`, per design "Progress and ETA" and "The render region on the event page":
  - `JobProgress` with C1's `Pill` and `JOB_STATUS_LOOK`, the labelled time, and the indeterminate bar: static stripes by default, its sweep only inside `prefers-reduced-motion: no-preference` with a literal `1.2s` loop
  - Render, and Render anyway with its confirmation `Dialog` (its Cancel passed as `initialFocus`, no `autoFocus`)
  - `blockedReason?: string`: when set, Render and Render anyway give way to the reason text; progress, Cancel and notices stay
  - the busy state: the pressed button gets `aria-disabled="true"` + `aria-busy="true"`, never `disabled`, behind the ref-based double-submit guard
  - every `EnqueueResult` branch, including the collision Alert with links and the 502
  - focus moving to the status element when the focused control is removed
  - `load()` of a failed read-source job's error text

  In `EventDetail.tsx`, mount it in the `ready` view only, in place of C1's latest-job pill, and add `load({ quiet })` (content kept, "Updating…" in C1's `LoadStatus` region), `reread()` wired to `onFinished` and to the fresh and 404 answers (exactly one self-started re-read path, per 1.1). `load({ quiet })` never touches an Edit-mode state. Verify that `tsc --noEmit` and `npm run build` pass, and, in the dev service:
  - `2024-06-27 - Grillning med grannar` → Render shows "Waiting for a worker"
  - `2024-07-14 - kalas` → Render shows the collision alert linking `2024-07-14 - Kalas`
  - `2024-10-05 - Trasig` shows its job's error text
  - `2024-02-30 - Omöjligt datum` shows its failure and no Render
  - with `POST **/api/v1/jobs` held by `page.route`, Enter on Render on `2024-08-20 - Två kapitel - Tjörn` leaves `document.activeElement` on that button, with `aria-busy="true"` and no `disabled` attribute, until the route is aborted; a second Enter meanwhile sends no request, and after the abort the page says the render was not queued (nothing was enqueued, so the steps below still find Två kapitel stale)
  - `web-design-system`'s motion grep gate still passes over `web/src/jobs` (6.1's "Motion and layout")
- [x] 4.2 Add Cancel to `RenderControl`, per design "Cancel":
  - queued jobs cancel at once
  - running jobs ask in a `Dialog` ("the partial render is discarded"), with "Keep rendering" passed as `initialFocus` (no `autoFocus`)
  - the pressed Cancel or Cancel render is `aria-disabled` + `aria-busy` while in flight, never `disabled`
  - no Cancel while `cancel_requested` is set
  - `toast.info(CANCEL_OUTCOME_LABEL[outcome])`, `markAnnounced` for `canceled-queued` and `no-op-terminal`
  - `track` plus a forced `load` after the answer
  - a 404 shows "This job no longer exists."

  Verify that `tsc --noEmit` passes, and that Cancel on `2024/Blandat`, with `POST **/api/v1/jobs/*/cancel` held by `page.route` and pressed with Enter, keeps `document.activeElement` on Cancel until the route is released, asks nothing, shows exactly one toast ("Canceled before it started."), and then the Canceled state.

## 5. web/ — the event list

- [x] 5.1 Add `src/jobs/LiveJobCell.tsx`, which renders the job `<td>` itself (C1's role and column class passed through, `data-label="Last job"` exactly when a job is shown, live or read), and swap it for the job `<td>` in `EventRow` (design "The list: live job cell, compact Render, in-place re-read"). Add the row Render, named `Render <folder>` by `aria-label`, busy as on the page (`aria-disabled` + `aria-busy`, never `disabled`), and its toasts, with no force, nothing on error rows, focus moved to the row's event link, and no error-text fetch. Verify that `tsc --noEmit` and `npm run build` pass, and in the dev service:
  - the `2024-08-20 - Två kapitel - Tjörn` row's Render shows the job queued in that row, and that cell now has `data-label="Last job"` although the read had no job for it
  - the `2024-06-27 - Grillning med grannar` row's Render has the accessible name "Render 2024-06-27 - Grillning med grannar" (`get_by_role("button", name=…)`), and a job-less row's cell has no `data-label`
  - with `POST **/api/v1/jobs` held, Enter on the Grillning row's Render keeps `document.activeElement` on it, with `aria-busy="true"` and no `disabled` attribute, until the route is aborted (nothing is enqueued)
  - `2023-06-23 - Midsommar - Dalarna` and the `2024-02-30 - Omöjligt datum` error row have no Render
  - opening the list sends no `GET /api/v1/jobs/…` for `2024-10-05 - Trasig` (`page.on("request")`)
- [x] 5.2 In `EventList.tsx`, add `load({ quiet })`, the `updating` state ("Updating…" in C1's `LoadStatus` region, `aria-busy` on the content), quiet-read coalescing (a `pending` flag, cleared by Refresh), and make C1's version-triggered re-read quiet, both while the list is shown and when it is shown again (a failed list still reads with placeholders). Verify that `tsc --noEmit` and `npm run build` pass, and:
  - with `**/api/v1/events` delayed 2 s by `page.route`, a `curl`-queued forced job for `2023/2023-06-23 - Midsommar - Dalarna` that completes (start the worker for this check, stop it after) keeps the rows on screen with "Updating…" during the re-read
  - `git diff main --stat -- web/src/events/labels.ts web/src/events/tones.ts web/src/events/common.tsx web/src/App.tsx` is empty

## 6. Verification against the dev library

- [x] 6.1 Set up per the dev-env runbook §9, with `SLUG=render-progress-screen` and `N=5`:
  - worktree venv, database `arel_render_progress_screen`, and library `dev-render-progress-screen`
  - with no worker of your own running, rebuild the library (`scripts/make_dev_library.py <dest>` again), because tasks 3–5 queued, cancelled and rendered jobs in it; the steps below assume its documented state (`2024/Blandat` queued, Grillning, Badutflykt, Två kapitel, Blandat, kalas and Trasig stale)
  - `auto-reel serve` on `127.0.0.1:8105` over a fresh `npm run build`
  - no worker until a step starts one
  - add a synthetic long event to that library copy only: `2024/2024-12-01 - Lång`, holding 40 symlinks (`a01.mp4`…`a40.mp4`) that cycle through `clips/s1710001.mp4`…`clips/s1710004.mp4` (never the zero-byte `clips/trasig.mp4`)

  Run an ad hoc Playwright script from `<scratchpad>/verify/render-progress-screen/` in `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `--network host`. The script is never committed. Scope locators to `main:not([hidden])`. Record every toast's text as it appears (a `MutationObserver` on the toast region installed with `page.evaluate`), since successes dismiss themselves after 5 s. Start `auto-reel worker <library> --device cpu` only where a step says so, and stop it (SIGINT) only where a step says so. Check each item, in order:
  - **Header and queued:** the list's header shows "Live" and "1 queued". The `2024/Blandat` row shows "Waiting for a worker" with an indeterminate bar. The `websocket` count is 1 after list → Blandat page → Back. With the list shown for 30 s, `page.on("request")` records no request.
  - **Busy controls:** with the matching POST held by `page.route`, press Enter on Render on Grillning's page, on the Grillning row's Render, and on Cancel on Blandat's page: each time `document.activeElement` stays on the pressed button, which has `aria-busy="true"` and no `disabled` attribute, and a second Enter sends no request, until the route is aborted (so nothing is enqueued or cancelled).
  - **Queued cancel:** Cancel on Blandat's page asks nothing. Exactly one toast appears ("Canceled before it started."), the page shows Canceled, and the header shows no queued count.
  - **Collision:** Render on `2024-07-14 - kalas` shows the alert naming and linking `2024-07-14 - Kalas`, with "distinct title or location". `auto-reel jobs list` shows no job for it. The list-row Render on kalas shows an error toast.
  - **Forced render:** `2024-06-21 - Midsommar - Dalarna` shows Up to date and Render anyway. The dialog opens with focus on its Cancel. Dismissing it sends no POST (`page.on("request")`). Confirming shows "Waiting for a worker".
  - **Double click:** a `dblclick` on Render on `2024-08-20 - Två kapitel - Tjörn` sends exactly one `POST /api/v1/jobs`.
  - **Attach on 409:** open a second page in the same context, call `page2.route_web_socket("**/api/v1/ws/jobs", lambda ws: None)` before its `goto` (the socket is never connected), and open `2024-08-02 - Badutflykt - Varberg` there. `curl -X POST` a job for it from the host, then press Render in page 2. Page 2 shows that job queued, with no error. Close page 2.
  - **Live progress and done:**
    - start the worker, then press Render on `2024-06-27 - Grillning med grannar`
    - the bar goes indeterminate → percentage → Rendered (the worker first runs the jobs queued earlier)
    - exactly one "Rendered" toast names Grillning; the forced Midsommar and the Två kapitel jobs, started in this page, each raise one toast; the Badutflykt job, attached in the closed page 2, raises none here
    - the page re-reads without "Reading event…" appearing, and then shows Up to date
    - Back to the list, with `**/api/v1/events` delayed 2 s by `page.route` (the events were marked changed while the list was hidden): during the re-read the rows stay (no placeholder rows, "Updating…" shown) and `window.scrollY` equals its value before the event was opened; then the row shows Up to date, with the filter as left
  - **Fresh answer:** in a new page 2 with the socket held as above, open `2024/Blandat` (Render shown). `curl -X POST` a job for it and wait until `auto-reel jobs list` shows it done. Press Render: the page says there is nothing to render, offers Render anyway, and re-reads to Up to date, and `auto-reel jobs list` shows no new job. Close page 2.
  - **List live, in place:**
    - in a viewport short enough that the list scrolls, with the All filter, scroll until the 2023 group is in view and record `window.scrollY`; delay `**/api/v1/events` by 2 s with `page.route`
    - `curl` a forced job for `2023/2023-06-23 - Midsommar - Dalarna`
    - its row shows it queued, then Rendered, with no toast (not tracked)
    - during the re-read the rows stay rendered (the row count never drops to 0) and "Updating…" appears; afterwards the filter is still All and `window.scrollY` is unchanged
  - **ETA and running cancel:**
    - on `2024-12-01 - Lång`, press Render
    - once past 5%, a "… left" estimate appears. Sampled every second, its minutes never increase.
    - Cancel → the dialog opens with focus on "Keep rendering"; dismiss: still rendering
    - Cancel → confirm: "Cancelling…" and then Canceled; the toasts are the outcome ("Cancelling — the worker stops at the next segment.") and then one "canceled" toast
    - `find <library>-output -name '*.part'` is empty
  - **Failure text:** `2024-10-05 - Trasig` shows Failed with the recorded error text. With the worker running, press Render: the job fails at probe, and without any Refresh the page moves from "Waiting for a worker" to Failed with the new job's error text (the hub emits a job that ended between two polls, C2), and the error toast stays until dismissed.
  - **Reconnect gap:**
    - stop the worker, press Render on `Lång` (queued, tracked), then kill `serve`: the header shows "Reconnecting…" with no counts
    - start the worker, and wait until `auto-reel jobs list` shows the job done; then stop the worker and restart `serve`
    - within 35 s the header shows "Live", the page shows Rendered, and no toast appeared
  - **Failed in-place re-read:** route `**/api/v1/events` to `abort()` with the list shown, start the worker, then `curl` a forced job for `2024/2024-06-21 - Midsommar - Dalarna`. When it finishes, the list is replaced by "The service is not reachable." Stop the worker.
  - **Motion and layout:**
    - `web-design-system`'s motion grep gate (its design, "The motion grep gate"), its three commands verbatim over this change's directory:
      - `grep -rnE 'transition[^;]*[0-9.]+m?s\b' web/src/jobs` prints nothing (no literal transition duration)
      - `grep -rn 'animation[^;]*--dur-' web/src/jobs` prints nothing (no token-timed loop)
      - every hit of `grep -rnE '(^|[^-])animation(-name)?:|@keyframes' web/src/jobs` lies inside a `prefers-reduced-motion: no-preference` block (read the hits)
    - with `reduced_motion="reduce"`, the indeterminate bar's computed `animation-name` is `none`; with `no-preference` it is not
    - at 390px, `document.documentElement.scrollWidth <= 390` on the list (with the worker stopped, `curl` a forced job for `2024/2024-06-21 - Midsommar - Dalarna` after the list was read: the header shows "1 queued", that row shows the queued job with `data-label="Last job"` on its cell, and the `2024-07-14 - kalas` row shows Render named "Render 2024-07-14 - kalas"; cancel the Midsommar job afterwards) and on an event page showing progress and the collision alert
  - **Contrast:** measure, with the method C1's verification used (axe-core injected ad hoc, or computed ratios), the header indicator's text, the progress words and "last known", in both themes: every ratio is at least 4.5:1.
  - **Screenshots:** light and dark (C1's theme control), at 1280px and 390px, saved to `/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/verify/render-progress-screen/`:
    - the list with a running row and the header indicator
    - an event page mid-render with its ETA
    - the running-cancel dialog
    - the kalas collision alert

  Look at every screenshot.

## 7. web/ — the Edit-mode seam with `event-edit-screen` (at the pre-archive rebase)

- [x] 7.1 Evaluate this task only at the pre-archive rebase, never during implementation: the supervisor says which case applies after merging the first of `event-edit-screen` and `render-progress-screen`. During implementation, leave the box unchecked, go on to 8.1, and have the final report say "seam pending until the pre-archive rebase". At the pre-archive rebase, confirm the case on the rebased branch with `ls openspec/changes/archive/ | grep -- '-event-edit-screen$'`:
  - **It prints nothing:** write "not applicable: `event-edit-screen` wires the seam when it archives second" on this task and check the box.
  - **It prints the directory:** wire the seam in `EventDetail.tsx` (design "The render region on the event page", Edit mode), then run the combined check below:
    - deferred self-started re-reads while editing: while `editing`, every re-read EventDetail would start by itself (`reread()`: the render-finished re-read, and the "fresh" / 404 enqueue answers) only sets a pending ref; the `load()` in `leaveEditMode()` is that deferred re-read and clears the ref; entering Edit mode aborts a quiet re-read already in flight and sets the same pending ref (verify: start a quiet re-read held by `page.route`, press Edit, release it with an abort — the editor and its draft stay)
    - `blockedReason` on `RenderControl` while editing: `blockedReason={editing ? 'Save or leave Edit mode to render' : undefined}`
    - the draft is not reset on a quiet re-read: confirm that `load({ quiet })` never touches `editing` and that the editor keeps its draft when a quiet re-read hands it a new `event` object; report a difference, and do not rewrite `event-edit-screen`'s editor
    - re-base the text of any MODIFIED block on the current `openspec/specs` (this change's one block modifies `web-design-system`'s placeholder requirement, which `event-edit-screen` does not modify; confirm)

  Verify, in the second case only:
  - `tsc --noEmit` and `npm run build` pass after `npm ci` on the rebased branch, and the `EventDetail.tsx` diff for the seam is 15 lines or fewer
  - the combined Playwright check, with 6.1's setup and conventions (its library already holds `2024/2024-12-01 - Lång`), `serve` restarted on the rebased branch, and no worker running. Then:
    - `2024-06-27 - Grillning med grannar`, with no active job (6.1 rendered it, so it offers Render anyway): entering Edit mode removes Render anyway and shows "Save or leave Edit mode to render"; leaving Edit mode brings Render anyway back
    - `2024-12-01 - Lång`: start a render (Render anyway, confirmed, if 6.1 left it up to date; the job waits), enter Edit mode, move one clip and change the title
    - install `page.route('**/api/v1/events/**', r => r.abort())` and record the time; only then start `auto-reel worker <library> --device cpu` (it may run jobs queued earlier first)
    - while Lång's job is queued or running, at 1280px and 390px, light and dark: `document.documentElement.scrollWidth <= document.documentElement.clientWidth`; Save and Reset are visible, with bounding boxes inside the viewport; Render and Render anyway are absent and "Save or leave Edit mode to render" shows; the progress and Cancel stay
    - once the render finishes: the WebSocket delta carrying Lång's job as terminal (`page.on("websocket")`, `framereceived`) arrived after the recorded route time; `page.on("request")` recorded no events request while Edit mode was open; the editor stays, with the moved clip, the changed title and the save bar, and no failure view replaces the page
    - remove the route, then **Stop editing** → Discard: exactly one `GET /api/v1/events/…` is sent, and the page shows Up to date with the job Rendered; stop the worker (SIGINT)
    - screenshots to `<scratchpad>/verify/render-progress-screen/combined-*`

## 8. Docs and validation

- [x] 8.1 Update the docs:
  - `web/README.md`: rendering, live progress and cancel on both screens, and that a running `auto-reel worker` is needed for jobs to progress; "never poll" now reads "no timer polling; job state arrives over the jobs WebSocket"; the file tree gains `src/api/jobs.ts` and `src/jobs/*`
  - `docs/high-level-design.md` §4.10: row E of the slice table appends that it landed in `render-progress-screen` (the table has no status column; `event-edit-screen` edits row D the same way). The sentence ending "so no further `api/` prerequisite is known for v1" is corrected: slice E then needed two `api/` prerequisites, found while designing it, `jobs-client-contract` (the published jobs answers, cancel outcomes and WebSocket frames) and `jobs-project-guards` (output-collision refusal and project-scoped jobs). D-8's "Live progress needs no library" bullet gains one sentence: jobs missing from a reconnect snapshot are read once with `GET /jobs/{id}`.

  Then run the gates:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - the full `.venv/bin/python -m pytest`: the web-mount and OpenAPI drift tests stay green
  - `openspec validate render-progress-screen --strict`

  Verify:
  - `grep -n "render-progress-screen" docs/high-level-design.md`, `grep -n "jobs-project-guards" docs/high-level-design.md` and `grep -n "src/jobs" web/README.md` all hit, and `grep -n 'prerequisite is known for v1' docs/high-level-design.md` prints nothing (the sentence spans two lines)
  - `grep -rn 'autoFocus' web/src/jobs` prints nothing
  - all gates pass
  - `git diff main --stat -- web/package.json web/package-lock.json web/openapi.json web/src/api/schema.d.ts` is empty (no dependency and no schema change)
  - no Playwright script, screenshot or `.playwright` directory is in the worktree (`git status --short` lists only this change's files)
