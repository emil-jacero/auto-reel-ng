## 1. web/ — the verdict-only refresh

- [x] 1.1 In `src/events/EventDetail.tsx`, add the verdict slice and `refreshVerdict` (design, "Where the refreshed fields live" and "The verdict read"):
  - `ready` gains optional `verdict?: { staleness; latest_job }` and `verdictUnread?: { cause; detail }`; `RenderPanel` gets its verdict and latest job from `verdictOf(state)` (the refreshed slice, else the event's), and nothing else changes in what it is given
  - `refreshVerdict()` with its own flight (`verdictFlight.ts`, pure and covered by `verdictFlight.test.ts`): one read in flight, one more after it; an `ok` answer that is not aborted and arrives while `editingRef.current` is true merges only `verdict` and clears `verdictUnread`; any other answer (not an abort) sets only `verdictUnread`, from `describeProblem` / `unansweredFailure` words; neither touches `event`, `fetchedAt`, `updating` or the `failed` state
  - `reread` calls `refreshVerdict()` while Edit mode is open and `load({ quiet: true })` otherwise
  - `leaveEditMode` and the unmount cleanup abort `verdictFlight` (which also drops the request waiting)
  - the pure slice (`withVerdict`, `withVerdictUnread`, `verdictOf`, and the `LoadState` fields) lives in `src/events/loadState.ts`, with tests in `loadState.test.ts` (each transition leaves `event`, `fetchedAt` and `updating` alone; a non-`ready` state is returned unchanged; a later `withVerdict` clears the note; a new `readingState` read drops both)
  - the comments on `reread` and in the file's header doc say what the page now does in Edit mode

  Verify: `npm test`, `npx tsc --noEmit` and `npm run build` pass in the node:22 container, and `git diff --stat` shows only `web/src/events/EventDetail.tsx`, `loadState.ts` and `loadState.test.ts` (plus `detail.css` only if 1.2 needs one rule).
- [x] 1.2 Show a failed refresh in the render region (design, "A failed verdict read is said, in the region"): when `verdictUnread` is set, `RenderPanel` renders an `Alert` (`tone="warn"`, `role="note"`) under `RenderControl` titled "The render verdict may be out of date. Stop editing to read the event again." with the failure's cause and detail as its detail, and puts the same title into a persistent visually-hidden `<p role="status">` so it is announced; both are empty or gone after a successful refresh or a plain read.

  Verify: `npx tsc --noEmit` and `npm run build` pass; the note is checked in 2.1.
- [x] 1.3 Keep a re-read that Edit interrupts (design, "Edit pressed with a re-read on its way"): the Edit button notes whether `inFlight.current !== null || pending.current`, aborts and nulls `inFlight`, clears `pending`, sets `editingRef.current`, and when a read was on its way calls `refreshVerdict()`.

  Verify: `npx tsc --noEmit` and `npm run build` pass; the behaviour is checked in 2.1.

## 2. Verification in a real browser

- [x] 2.1 Build `web/` and serve `$DEV` with `auto-reel serve` on port 8245 (database `arel_web_edit_verdict_refresh`; schema via `alembic upgrade head`). Drive it with a Playwright script kept in `$SCRATCH` (never in the repo; container, locators scoped to `main:not([hidden])`, `page.wait_for_timeout`). Start `auto-reel worker $DEV --device cpu` only for the first check and stop it with SIGINT after. Route only `**/api/v1/events/**` (the event read), `**/reel`, `**/reel?*`, `**/api/v1/jobs` and `**/api/v1/jobs/**`, never a catch-all. Assert on `2024-06-27 - Grillning med grannar`:
  - **Verdict only, real render:** press Render, press Edit while the job runs, move a clip to another chapter without saving, and let the render finish. The render region changes from stale to up to date with the job rendered; the chapters, clip rows, counts line, facts, "Read" time and the unsaved move are exactly as before (compare their text before and after); the page never shows "Updating…"; the refresh makes no request to `/reel`.
  - **Baseline untouched:** with the event read routed to answer a different clip order and title after the job ends, the editor still shows the draft's order and title, and the `PUT /reel` body Save sends (intercepted, then aborted) is built from the original baseline.
  - **Failure:** route the refresh to a network failure, then to a 503: Edit mode and its changes stay, the region keeps its words and shows the "may be out of date" note (`role="status"`), no `role="alert"` appears; a later successful refresh removes the note. After Stop editing (discard) the page reads and shows the event as up to date.
  - **Late answer:** hold the refresh, press Stop editing, then release it: the held answer changes nothing, and the page shows the plain read's result.
  - **Edit during a re-read:** hold the quiet re-read the job's end starts, press Edit, release it: Edit mode shows the unchanged chapters and the region shows the new verdict.
  - **Burst:** two job ends in a row make at most one verdict read in flight and one after it (count the held requests).
  - Check at 1280×900 and 390×844, in the light and the dark theme; save and LOOK at screenshots of the note and of the region before and after, and check `scrollWidth <= clientWidth` at 390.

  Verify: every assertion above passes and the screenshots look right.

## 3. Validation

- [x] 3.1 Run the gates and verify that all pass:
  - `npm test`, `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `grep -rn 'autoFocus' web/src` prints nothing new, and `git diff --stat origin/main -- auto_reel_ng tests scripts web/openapi.json web/src/api web/src/jobs web/src/edit web/package.json web/package-lock.json` is empty
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, then `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest` (web-mount and OpenAPI drift tests green; `-m "not requires_db"` and say so if podman is unavailable)
  - `openspec validate web-edit-verdict-refresh --strict` passes
  - no Playwright script, screenshot or `.playwright` directory is in the worktree
