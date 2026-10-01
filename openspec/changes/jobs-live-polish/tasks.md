## 1. Gate

- [ ] 1.1 Confirm the base, re-base the spec, and set up.
  - **The base:** `main` contains `bca64f2`. Run `git diff --stat bca64f2 main -- web/src/jobs
    web/src/api/jobs.ts web/src/events/EventList.tsx web/src/events/EventDetail.tsx web/src/ui/Dialog.tsx`.
    - If a parallel polish change landed first, read its diff and keep its edits. Expected ones:
      `event-list-polish`'s formatter call in `JobProgress.tsx`, `.live-job` or card-layout rules in
      `jobs.css`, and the row markup in `EventList.tsx`; `event-page-polish`'s header regrouping around
      `<RenderControl>`; `ui-a11y-polish`'s `Dialog` props.
    - Stop and report if one of them restructured `choose()`, `JobMeter`, RenderControl's dialog state
      (`asking`) or hand-off, `tellRowAnswer`, or `track`. `ui-a11y-polish` moving each dialog's `<p>`
      into `description` is expected, not a restructure.
  - **The code facts:** re-check the facts in design, "Context", against the landed code. Line numbers may
    move; the shapes must hold.
  - **The spec:** re-base each of the four MODIFIED blocks in `specs/web-app/spec.md` on the current
    `openspec/specs/web-app/spec.md` text of the same requirement. Keep every edit another change made, and
    re-apply only this change's sentences and scenarios.
  - **Set up** per the dev-env runbook §9 with `SLUG=jobs-live-polish` and `N=16`:
    - database `arel_jobs_live_polish`, library `../dev-jobs-live-polish`, port 8116
    - a worker only for task 6.1
    - never port 8080 or 5173, `../auto-reel-dev`, `auto-reel-media/` or the default database
  - **Verify:**
    - in `docker.io/library/node:22`, after `npm ci` (a checkout's `node_modules` can be stale: `main`'s
      lacks `@dnd-kit`, and tsc then fails in `ClipOrderList.tsx`), `npx tsc --noEmit` and `npm run build`
      pass on the untouched tree
    - `curl -s http://127.0.0.1:8116/healthz` answers ok
    - `openspec validate jobs-live-polish --strict` passes after the re-base

## 2. web/ — the job a screen shows

- [ ] 2.1 In `src/jobs/useJob.ts`, add the `'refreshed'` `ShownJob` variant, `standing()`/`isFurther()`, and
  `choose(live, latest, connectionLive)` per design, "The job a screen shows while the connection is down".
  `useEventJob` passes `connection === 'live'`, and its `useMemo` gets `[live, latest, connection]` as its
  dependencies. Then update the readers of `source`:
  - `JobProgress.tsx`: `isCancelling` and `JobMeter`'s `lastKnown` read `source !== 'read'`
  - `RenderControl.tsx`: `cancellable` reads `source !== 'read' && job.cancel_requested`, and `eta` goes
    to `JobMeter` only for `source === 'live'`

  Verify:
  - `tsc --noEmit` passes
  - `grep -rn "source === 'live'\|source !== 'read'" web/src/jobs` lists only the readers named in the
    design
  - with an ad hoc Playwright script against 8116 (`<scratch>/verify/jobs-live-polish/check_outage.py`,
    started from `…/scratchpad/polish-spec/jobs-live-polish/probe.py` `probe_a`): the jobs WebSocket is
    mocked with `route_web_socket`, `POST /jobs` is mocked 201 queued, and the event read is patched to
    that job running at 0.6. On Grillning: Render, then close the socket with 1012 and refuse reconnects,
    then Refresh.
    - The card reads "Rendering", "60%" and "last known", with no "Queued" and no time-left estimate.
    - On the list, a Refresh shows the same on Grillning's row.
    - With the socket live, a patched read of 0.6 does not beat a live delta of 0.4: the card reads 40%.
    - A read that is behind (queued) while the store has running 0.4 and the socket is down shows 40%.
- [ ] 2.2 In `JobMeter`, cap a running job at `RUNNING_MAX = 0.99` for both the `<progress>` value and the
  percentage (design, "A running job reads at most 99%"), and fix the comment.

  Verify:
  - `tsc --noEmit` passes
  - with a mocked snapshot of Grillning:
    - running at 1.0: `.job-percent` reads "99%", the `<progress>` value is 0.99, and the progressbar
      node in the accessibility tree (CDP `Accessibility.getFullAXTree`) has a value of 0.99 of 1, not 1
    - running at 0.994: 99%; at 0.5: 50%
    - a `done` delta then shows "Rendered" and no meter

## 3. web/ — the render region's dialogs (`src/jobs/RenderControl.tsx`)

- [ ] 3.1 Cancel asks while the connection is not live. Per design, "Cancel asks whenever the job might be
  running":
  - `asking` becomes `{ kind: 'force' } | { kind: 'cancel'; jobId; mayHaveStarted }`
  - subscribe to `connection === 'live'`
  - the cancel dialog's text starts with "The connection is down, so this render may have started." when
    `mayHaveStarted`. It is its one `<p>`, or its `description` once `ui-a11y-polish` has landed.
  - the confirm button cancels `asking.jobId`

  Verify, in `<scratch>/verify/jobs-live-polish/check_dialogs.py`, with the socket and `POST
  /jobs/{id}/cancel` mocked:
  - Blandat's queued job while live: Cancel sends one POST and opens no dialog
  - the same job with the socket closed and reconnects refused: Cancel opens the dialog with the lead
    sentence and focus on "Keep rendering", and sends nothing. Escape sends nothing, and "Cancel render"
    sends exactly one POST, to the question's job id.
  - a running job while live: the dialog opens without the lead sentence
- [ ] 3.2 Dialogs close when their question is gone, and focus never falls to `<body>`. Per design,
  "Dialogs close when their question is gone" and "Focus after a dialog whose opener is gone": add the
  `questionGone` effect and `focusIsLost()`, and use `focusIsLost()` in the hand-off effect.

  Verify, in the same script:
  - **Keyboard Render anyway:** on `2024-06-21 - Midsommar - Dalarna`, focus Render anyway, press Enter,
    Tab to the dialog's Render anyway, and press Enter. `POST /jobs` is mocked 201, once answered at once
    and once after 600 ms. Each time, `document.activeElement` is `p.render-status`, one POST was sent,
    and the next Tab focuses Cancel.
  - **The job ends under the question:** on Grillning, running at 30%, Cancel opens the dialog. A `done`
    delta then closes it (`dialog[open]` count 0), sends no cancel POST, shows "Rendered", and puts focus
    on `p.render-status`.
  - **A job appears under the question:** with the Render anyway dialog open on Midsommar, a foreign
    queued delta for that event closes it, sends no POST, and the card shows "Waiting for a worker".
  - **In flight:** with the confirm's request held (`page.route`), a `done` delta leaves the dialog open
    and the pressed button busy and focused until the answer. The answer then closes it, and focus is on
    `p.render-status`.
  - **Controls:** Escape on each dialog returns focus to its opener. A confirmed running-job cancel ends
    with focus on the status once "Cancelling…" shows, as before.

## 4. web/ — naming and row answers

- [ ] 4.1 Name events by title (design, "Toasts name the event by its title"):
  - `eventName()` in `src/jobs/labels.ts`
  - `tracked` becomes a `Map` with `track(jobId, name)` in `store.ts`, and `onEnded` uses the tracked name
  - a required `title: string | null | undefined` prop on `RenderControl` and `LiveJobCell`, passed to every
    `track` call
  - the one-line call-site edits `title={event.title}` in `src/events/EventDetail.tsx` and
    `src/events/EventList.tsx` (other changes' files; one line each)

  Verify:
  - `tsc --noEmit` passes, and fails when either call-site line is removed (restore it)
  - `grep -n folderName web/src/jobs/store.ts` prints nothing
  - Playwright, on Grillning's page: Render (mock 201), then running and `done` deltas raise one toast,
    'Rendered “Grillkväll med grannarna”'. The same with a `failed` delta raises 'Render of “Grillkväll med
    grannarna” failed'. With a confirmed cancel, the canceled end raises no second toast.
- [ ] 4.2 Announce a row's `enqueued` and `active` answers with `toast.info` (design, "Row answers are
  announced"). Name every non-collision row answer by title, and keep folder names in the collision toast.

  Verify, in `<scratch>/verify/jobs-live-polish/check_rows.py`, which logs every `[role=status]`,
  `[role=alert]` and `[aria-live]` text change with a `MutationObserver` in an init script:
  - **Queued:** Enter on "Render 2024-08-02 - Badutflykt - Varberg" (mock 201) makes the polite region say
    'Render of “Badutflykt” queued', puts focus on the row's "Badutflykt" link, and sends one POST
  - **Already active:** a mocked 409 `active_job` says 'A render of “Badutflykt” is already queued or
    running'
  - **Fresh:** a mocked 200 fresh says '“Badutflykt” is already up to date'
  - **Collision:** Render on the `2024-07-14 - kalas` row, answered 409 by the service itself (a real
    answer: nothing is enqueued), raises an error toast naming '2024-07-14 - kalas' and '2024-07-14 -
    Kalas'
  - **Quiet rows:** a later `running` delta for Badutflykt adds no live-region text

## 5. web/ — the separator (`src/jobs/jobs.css`)

- [ ] 5.1 Replace the `.job-words:has(+ .job-when)::after` rule with the hanging dot and the clipped
  `.job-state`, and give an active time its own line in `.job-progress` (design, "The separator"). Do not
  touch `.live-job` or the `@container (width < 50rem)` block.

  Verify, in `<scratch>/verify/jobs-live-polish/check_separator.py`:
  - **States:** mocked snapshots of Grillning running at 0 ("Starting…") and cancelling, Lång kväll running
    and cancelling, and Trasig queued with an other-year `created_at`. The Trasig job must also be patched
    into the events read as its `latest_job`: from the snapshot alone it loses to the read's newer failed
    job, and the row would show "Failed".
  - **Widths and schemes:** 1280, 768, 390 and 320px, light and dark
  - **Page:**
    - where `.job-words` and `.job-when` share a line, `when.left − words.right` is 12 ± 1 px and
      `getComputedStyle(when, '::before').content` is `"·" / ""`
    - where the time wraps, `when.left` equals the `.job-state`'s left, so the dot lies outside the clip
    - the status row's (`.render-row`) height at 1280 is the same with "Starting…" and with progress 0.4.
      The card itself grows by the meter's figures line on `main` too (design, "Adjacent findings not
      taken"), so compare the row, not the card.
  - **List:** in every row whose job shows words ("Waiting for a worker", "Starting…", "Cancelling…"),
    the time is on its own line, and its `::before` content is `none`
  - **Everywhere:** `document.documentElement.scrollWidth <= innerWidth`, with a screenshot per state,
    width and scheme, and every screenshot looked at
  - **Gates:**
    - the three motion grep commands in `web/README.md` pass over `web/src/jobs`
    - `grep -nE '#[0-9a-fA-F]{3}|oklch\(|rgb' web/src/jobs/jobs.css` prints nothing new
    - the class names the sibling changes select on are still rendered (design, "File ownership and
      coordination"): for each of `live-job`, `job-progress`, `job-words`, `job-when`, `row-blocked`,
      `render-card`, `render-none` and `render-blocked`, `grep -rn 'className="<name>"' web/src/jobs` hits
      once, and the `render-card` line still sets `data-active`

## 6. Verification against the dev library

- [ ] 6.1 Run an end-to-end pass against 8116 with a real `auto-reel worker` on this library copy (`--device
  cpu` if VAAPI is contended):
  - script: `<scratch>/verify/jobs-live-polish/check_e2e.py`, in
    `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `--network host`, the Noto fonts and
    `FONTCONFIG_FILE` per `web/README.md`, and locators scoped to `main:not([hidden])`
  - never committed

  Check:
  - **A real render:** from Grillning's page, a sampler reads `.job-state` and `.job-percent` every 100 ms.
    No sample shows "100%" while the pill reads "Rendering". One toast names "Grillkväll med grannarna".
  - **A real row Render:** on Badutflykt, the queued toast is announced, focus is on the row link, and
    the row follows the job to "Rendered".
  - **Screenshots:** the page (queued, running, cancelling, rendered, and the cancel dialog) and the list
    (queued and running rows), in light and dark, at 1280 and 390px. Look at each.
  - **axe-core** (wcag2a, wcag2aa; the copy in `scratchpad/verify/final/axe/`): zero violations on
    Grillning's page with the cancel dialog open, and on the list with a queued row, in both schemes.
  - **Phone width:** no horizontal scroll at 390 or 320px in any of these states.

  Verify: every check passes, the PNGs and the logs are in the verify directory, and `git status` shows no
  Playwright or screenshot file in the repository.

## 7. Docs and validation

- [ ] 7.1 Update `web/README.md`'s "Rendering" paragraph, then run the gates.
  - **README**, two sentences only:
    - Cancel "asks first for a running one, and for any job while the connection is down"
    - "Toasts, naming each event by its title, confirm a row's Render and tell how renders started in
      the tab ended"
  - **Gates:**
    - `npx tsc --noEmit` and `npm run build` in the node:22 container
    - the full `.venv/bin/python -m pytest`, which keeps the web-mount and OpenAPI drift tests green
    - no Python file changed, so these run only to confirm that nothing changed:
      - `.venv/bin/python -m black --check auto_reel_ng tests`
      - `.venv/bin/python -m isort --check auto_reel_ng tests`
      - `.venv/bin/python -m mypy auto_reel_ng`
      - `.venv/bin/python -m pylint auto_reel_ng`

  Verify:
  - `git diff web/README.md` touches only the "Rendering" paragraph
  - all of the gates pass
  - the motion grep gate passes over `web/src`
  - `git diff main --stat` lists only `web/src/jobs/*`, `web/README.md`, the two one-line call sites in
    `web/src/events/EventList.tsx` and `EventDetail.tsx`, and this change's directory
  - `git diff main -- web/package.json web/package-lock.json web/openapi.json web/src/api web/src/ui
    web/src/styles` is empty
  - `openspec validate jobs-live-polish --strict` passes
