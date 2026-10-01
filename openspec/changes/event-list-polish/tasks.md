## 1. Gate

- [ ] 1.1 Confirm the base, and re-check the names this change builds on. Stop and report to the supervisor on any mismatch.

  - `git merge-base --is-ancestor bca64f2 HEAD` succeeds.
  - Find which parallel changes have landed with `ls openspec/changes/archive/ | grep -E -- '-(edit-mode|jobs-live|event-page|ui-a11y)-polish$'`. For each one that has, re-read every file named in design, "Files and parallel changes", and plan this change's lines onto that file's current text.
  - `grep -n 'className="live-job"\|className="row-blocked"' web/src/jobs/LiveJobCell.tsx` hits both names.
  - `grep -n 'className="job-progress"\|className="job-when"\|className="job-words"' web/src/jobs/JobProgress.tsx` hits all three.
  - `grep -n "kind: 'unreachable'" web/src/edit/SaveBar.tsx` hits the `SaveProblem` member.
  - `grep -n "UNREACHABLE_CAUSE =" web/src/events/common.tsx` hits.
  - `grep -n "tr:hover" web/src/styles/components.css` shows exactly the two `.data-table` blocks the design deletes.
  - `grep -n 'job-words:has(+ .job-when)::after' web/src/jobs/jobs.css`: write down whether it hits. A hit means `jobs-live-polish`'s separator has not landed, so task 4.1 adds the stop-gap rule. No hit means task 4.1 adds none (design, "The list's row layout").
  - `grep -n 'title={event.title}' web/src/events/EventList.tsx`: if it hits, `jobs-live-polish` has landed its line on `<LiveJobCell>`, and every edit below keeps it.

  Re-base the five MODIFIED blocks in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`. For each requirement, take the landed text and carry this change's edits onto it, so that no other change's wording is lost. Do this again before archiving.

  Verify: `openspec validate event-list-polish --strict` passes.

## 2. web/ — one time format

- [ ] 2.1 Add `web/src/format.ts` with `formatInstant`, with no imports (design, "One time format"). Switch the five call sites:
  - `EventList.tsx` "Scanned"
  - `EventDetail.tsx` "Read"
  - `EventDetail.tsx` clip time
  - `edit/ClipOrderList.tsx` clip time
  - `jobs/JobProgress.tsx`, which deletes its `THIS_YEAR`, `OTHER_YEAR` and `formatTime`

  "Scanned" and "Read" wrap the value in `<time dateTime={fetchedAt.toISOString()}>`.

  Verify:
  - `npx tsc --noEmit` passes in the node:22 container.
  - A scratch script in the session scratchpad (never committed) imports `format.ts`. It runs as `node --experimental-strip-types` in `docker.io/library/node:22` with `-e TZ=Europe/Stockholm`.
    - With `-e LANG=en_US.UTF-8` it asserts:
      - `` `${currentYear}-09-30T22:23:00Z` `` gives "Oct 1, 12:23 AM"
      - `2025-06-22T18:03:00Z` gives "Jun 22, 2025, 8:03 PM"
      - `'nonsense'` gives "nonsense"
    - With `-e LANG=sv_SE.UTF-8`, no output matches `/\d:\d\d:\d\d/`.
  - `grep -rnE 'toLocale(Time|Date)?String|Intl\.DateTimeFormat' web/src` hits only `web/src/format.ts`.
  - The `EventDetail.tsx`, `ClipOrderList.tsx` and `JobProgress.tsx` diffs touch only the lines design, "Files and parallel changes", names for them.

## 3. web/ — answers and failure copy

- [ ] 3.1 Split the result kinds and give each its words (design, "No answer vs an unpublished answer" and "Failure copy"):
  - `api/http.ts`: `Unanswered` and `unpublishedAnswer`
  - `api/events.ts`, `api/event.ts`, `api/reel.ts`: unions `ok | problem | Unanswered`. Every off-contract answer, including "200 without an ETag", becomes `unpublished`. A rejected fetch stays `unreachable`, and an `AbortError` is rethrown as today.
  - `events/labels.ts`:
    - sentence-case `FAILURE_LABEL`
    - `UNANSWERED_CAUSE`, `NOT_REACHABLE_HINT`, `unansweredFailure` and `failureDetail`
    - type-only imports, still
  - `events/common.tsx`: `UNREACHABLE_CAUSE = UNANSWERED_CAUSE.unreachable`
  - every consumer, exactly as design lists:
    - `EventList.tsx`: the load `switch`, and the attention row's fix through `failureDetail`
    - `EventDetail.tsx`: the load `switch`, and `describeProblem`'s 404 and 502 branches
    - `edit/EventEditor.tsx`: `readFailure` (both kinds, and the 404's `detail: null`), and `send()`'s two `unreachable` sites
    - `edit/SaveBar.tsx`: the `SaveProblem` member, the `case`, and the title

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass.
  - `grep -n "kind: 'unreachable'" web/src/api/events.ts web/src/api/event.ts web/src/api/reel.ts` hits only the `catch` of a rejected fetch.
  - `grep -rn "case 'unreachable'" web/src/events web/src/edit` shows each hit followed by `case 'unpublished'`, or sharing a test that covers both.
  - A scratch node script (as in 2.1) imports `labels.ts` and asserts:
    - `failureDetail('2024/2024-02-30 - Omöjligt datum', '<the dev library's error-row detail>')` starts with "No date: folder name date 2024-02-30"
    - a detail starting `/abs/path/reel.yaml: malformed YAML` comes back unchanged
    - a detail equal to the bare prefix comes back unchanged
    - `unansweredFailure({ kind: 'unreachable', message: 'TypeError: Failed to fetch' }).detail` is `NOT_REACHABLE_HINT`
    - `unansweredFailure({ kind: 'unpublished', message: 'GET /api/v1/events answered 500 Internal Server Error' })` keeps that message
  - The diffs of `EventDetail.tsx`, `common.tsx`, `EventEditor.tsx` and `SaveBar.tsx` touch only the lines named in design.

## 4. web/ — the list

- [ ] 4.1 Lay out the rows (design, "The list's row layout").
  - `list.css`:
    - the new column widths, with the comment's budget
    - the table-width job-cell grid and the stacked `.job-when`
    - only if task 1.1's `::after` grep hit: the separator stop-gap `.live-job .job-words::after { content: none }` inside the table-width block, with its comment naming `jobs-live-polish`
    - the card areas `'event event render' 'date clips render' 'job job job'` over the rows `auto 1fr auto` (`none` below 30rem), and the action's `margin-inline-start: auto`
    - `.clip-counts`, without the old badge margin
    - `.event-folder` (block, muted, `--text-xs`) and `.event-list .empty-title`
    - the row cursor and hover, at table and at card widths
  - `EventList.tsx`: the clip count and badges move inside `<span className="clip-counts">`.
  - `styles/components.css`: delete the two `.data-table` hover blocks, and nothing else.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass.
  - `git diff web/src/styles/components.css` shows only deleted lines, all inside the two hover blocks.
  - Every new rule in `list.css` is inside `@layer screens` and uses tokens only, with no literal colors.
  - `grep -nE '@container' web/src/events/list.css` shows only `50rem` and `30rem` breakpoints.
  - `grep -c 'job-words' web/src/events/list.css` is 1 if task 1.1's `::after` grep hit, else 0.
- [ ] 4.2 Tell look-alike rows apart, and make the row a target (design, "Look-alike rows show their folder's path" and "The whole row opens its event"):
  - `grouping.ts` `lookAlikes`, with the NFC, case-folded key
  - `ReadyView` computes it over all readable events
  - `EventRow` takes `lookAlike` and calls `useId()` unconditionally at its top. A look-alike row renders `.event-folder` holding `event.event_id` under that id, and sets the link's `aria-describedby` to it.
  - `EventRow`'s `<tr onClick={openRow}>`, with `openRow` at module level
  - no role, `tabIndex` or key handler on the row

  Verify:
  - `npx tsc --noEmit` passes.
  - A scratch node script imports `grouping.ts`. It feeds it a saved copy of the dev library's `GET /api/v1/events` answer (from any server of the dev library, such as task 6.1's) and asserts exactly `{'2024/2024-07-14 - Kalas', '2024/2024-07-14 - kalas'}`. It also asserts these hand-made cases:
    - same date and title with different locations gives none
    - titles differing only in case give both
    - titles differing only in Unicode normalization (`'Två'` NFC and NFD) give both
    - two untitled events whose folder names differ only in case give both
    - two undated, untitled events `2023/Blandat` and `2024/Blandat` give both
    - a titled event and an untitled one whose folder name equals that title give both
    - three alike events give all three
  - `grep -n 'useId' web/src/events/EventList.tsx` shows no `useId(` inside a JSX expression or a condition.
  - `grep -n 'tabIndex\|onKeyDown' web/src/events/EventList.tsx` shows no new hit on a `<tr>`.
- [ ] 4.3 Add the empty states and the announcement (design, "Empty states and announcements"):
  - `Summary` only when the read holds rows, and its rendering chip only when `events.length > 0`
  - "No events yet", with its line
  - the filtered-empty "Nothing needs rendering" with **Show all events**: `setOnlyStale(false)`, then focus the All radio through a ref `FilterControl` takes
  - the list's empty states as a `<div className="empty-state">` (a `<p>` cannot hold the title and the button)
  - the visually hidden `role="status"` result region in `.page-meta`, mounted in every state and filled only while `state.status === 'ready'`

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass.
  - `grep -n ' disabled=' web/src/events/EventList.tsx` prints nothing.
  - `grep -n 'autoFocus' web/src/events` prints nothing.

## 5. Docs

- [ ] 5.1 Update `web/README.md`:
  - **The list paragraph:** the whole event row opens its page (the title stays the keyboard stop), look-alike rows show their folder's path, and the empty and filtered-empty states with Show all events.
  - **"Design system":** one sentence saying that every time is written by `src/format.ts` (short month and day, hour and minute, the year only when not current, no seconds) and that event dates stay `YYYY-MM-DD`. One more saying that only rows that open something take a hover fill.
  - **The file tree:** `format.ts`, and `grouping.ts`'s new `lookAlikes`.

  Verify:
  - `grep -n "format.ts" web/README.md` hits the tree and "Design system".
  - `git diff --stat` shows no change to `docs/high-level-design.md` (no decision here outlives the change beyond D-10's visual system).

## 6. Verification against the dev library

- [ ] 6.1 Set up the agent's own environment per the dev-env runbook §9, with `SLUG=event-list-polish` and `N=17`:
  - database `arel_event_list_polish`, library `../dev-event-list-polish`, serve on port 8117 over a fresh `npm run build`
  - no worker
  - never port 8080 or 5173, the `auto_reel_ng` database, `auto-reel-media/`, `:8114`, or another agent's database, library or port

  Drive `http://127.0.0.1:8117/` with Playwright scripts kept in `<scratchpad>/verify/event-list-polish/`, never committed:
  - container `mcr.microsoft.com/playwright/python:v1.49.0-noble`, with `--network host`
  - locators scoped to `main:not([hidden])`
  - timezone `Europe/Stockholm`, locale `en-US`
  - every non-GET request aborted or answered by an in-browser mock
  - running, queued, cancelling, blocked, other-year and no-job rows produced as in design, "Reproduction": a `route_web_socket` snapshot on `**/api/v1/ws/jobs`, plus a patched `GET /api/v1/events` that marks Sommarlov with one missing clip, gives Midsommar 2024 a job that finished in 2025, and appends a 38-clip `2024-04-20 - Lasse 80 år, M-A och Lasse kärleksförklaring - Kungälv` row

  Check the **layout** at 1440, 1280, 1024, 900, 768, 600, 390 and 320 px. Do it in the light scheme, and at 1280 and 390 in the dark scheme too (the theme control). Save screenshots to `<scratchpad>/verify/event-list-polish/` and look at every one.
  - **Every width:** `document.documentElement.scrollWidth <= clientWidth`.
  - **Table widths (1024 and up, and 900):**
    - in every row, the date's, verdict pill's and job pill's tops are within 3 px of the title link's top
    - every Render's vertical center is within 3 px of the title's, and every "Blocked by missing clips" note's top is within 3 px of the title's top (the note wraps to two lines and is top-aligned, so its center sits lower)
    - every Render and every "Blocked by missing clips" note shares one right edge (±1 px) per table
    - at 1024 and up, each finished job's time starts on the line below its pill, and no row's job cell holds more than two text lines apart from an active job's bar
  - **768 and 600:**
    - each card's date starts at most 8 px below the last line of its event cell's text (title, location or path), including the 38-clip row whose verdict runs to three lines
    - every Render and "Blocked by missing clips" note ends at the card's right content edge (±1 px)
    - each action's vertical center lies within its card's job line
  - **Clip counts:** a wrapped badge's left edge equals its clip count's left edge (±1 px).
  - **Look-alike rows:**
    - exactly two rows show `.event-folder`, reading `2024/2024-07-14 - Kalas` and `2024/2024-07-14 - kalas`
    - each Kalas link's `aria-describedby` resolves to its own path text
    - toggling Needs render keeps both path lines on the rows still shown
    - a Refresh whose patched read renames one Kalas row's title (so the pair is no longer alike) shows no path line and no React error in the console, and the next Refresh with the real read shows both lines again
- [ ] 6.2 Check the behaviour on the same server and harness:
  - **Row target**, in Chromium, Firefox **and WebKit**, at 1280 and 390:
    - a click on Två kapitel's clip count opens its page
    - a drag across a row's date selects it and stays on the list
    - pressing a row's Render (its POST answered by an in-browser mocked 201) stays on the list
    - a click on the "Needs attention" row's fix text stays on the list
  - **Hover:**
    - hovering an event row changes its cells' computed background
    - hovering a "Needs attention" row or an event page's clip row changes nothing
  - **Empty states:**
    - a mocked `[]` read shows no `.stats` and the "No events yet" text
    - a patched all-fresh read with Needs render chosen shows "Nothing needs rendering" and "Show all events"; Tab to it and Enter shows every row, with `document.activeElement` the All radio, never `<body>`
  - **Announcements:** a MutationObserver on every `[role=status]` and `[role=alert]` records:
    - Refresh gives "Scanning events…", then the result sentence, even with unchanged counts
    - a filter change gives the new result sentence
    - a quiet re-read with unchanged counts (a mocked snapshot running job, then a `delta` with it `done`) changes no result text
  - **Answers:**
    - mocked bare 500s on `GET /api/v1/events`, on Grillning's `GET` detail, on its Edit-mode `GET …/reel`, and on its `PUT …/reel` after a title edit each show "The service sent an unexpected answer." with the request and "500", and never "not reachable"
    - the save keeps the edit and offers Retry
    - an aborted list read and an aborted page read show "The service is not reachable." and the hint, with no "TypeError"
  - **Failure copy:**
    - the Omöjligt datum row's pill reads "Missing or invalid date or title", and its fix starts "No date: folder name date 2024-02-30"
    - the Omöjligt datum page shows the same words and detail
    - `#/event/2024/Finns%20inte` shows its title and "Back to the event list", and no detail paragraph
  - **Times:**
    - "Scanned", "Read", every clip time on Grillning (read view and Edit mode) and every job time match `formatInstant`'s output, and none matches `/\d:\d\d:\d\d/`
    - the 2025 job reads "Jun 22, 2025, 8:03 PM"
    - at 320 and 360 px, Grillning's page and its Edit mode do not scroll sideways
    - with locale `sv-SE`, there are still no seconds
  - **Contrast and axe:**
    - `.event-folder` text measures at least 4.5:1 in both schemes, on the panel and on the row's hover fill
    - axe-core is injected ad hoc from the scratchpad. Runs on the list (look-alike rows, the filtered-empty state and the empty state), at 1280 and 390 in both schemes, report no serious or critical violation.

## 7. Validation

- [ ] 7.1 Run the gates. Verify all pass:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `web-design-system`'s motion grep gate (its design, "Tokens and the support floor"): its three commands verbatim, over `web/src/events` and `web/src/format.ts`. This change adds no animation or transition.
  - `grep -rn 'autoFocus' web/src/events` prints nothing
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, then `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, with the web-mount and OpenAPI drift tests green
  - `git diff --stat main -- auto_reel_ng tests scripts docs web/openapi.json web/src/api/schema.d.ts web/package.json web/package-lock.json` is empty
  - `openspec validate event-list-polish --strict` passes
  - no Playwright script, screenshot or `.playwright` directory is in the worktree
