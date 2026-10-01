## Why

GUI v1 (HLD **§6 phase 8**, §4.10, stack **D-8**, visual system **D-10**) is feature-complete on main
`bca64f2`. The final end-to-end pass and its four critics found that the event list, the first screen
the operator sees, does not yet read as the calm, data-dense list D-10 promised. Each finding below was
reproduced on the live read-only server (design, "Reproduction"):

- At 1280 px the rows are ragged, at 43 to 103 px. The job cell is 11rem wide, so a row's pill, time and
  compact Render stack on three lines. The cell's `vertical-align: middle` then puts "Failed" 27 px
  above its row's title, and Render sits under the time in one row and at the top of the cell in the
  next.
- At the 768 px card width, wrapped reasons push a row's date and clip count 46 px away from its title.
  A wrapped "1 missing" badge is indented under the clip count.
- The two collision fixtures, `2024-07-14 - Kalas` and `2024-07-14 - kalas`, render as identical rows.
  They are the one conflict v1 asks the operator to resolve by hand.
- Rows highlight on hover, but only the title opens the event.
- The empty library shows "0 of 0 events need rendering" over a bare "No events found.". The filtered
  empty list offers no way back. Finished reads and filter changes are not announced.
- Three time formats are in use: "12:54:52 AM" (read times), "10/1/2026, 12:23:00 AM" (clip times) and
  "Oct 1, 12:35 AM" (job times).
- The failure copy is rough:
  - the pill is lowercase
  - the row's fix repeats its folder name ("2024-02-30 - Omöjligt datum: no date: …")
  - the not-found page says the same thing twice
  - an unreachable list shows "TypeError: Failed to fetch"
- **A 500 from the service is reported as "The service is not reachable."** on the list, the event page
  and the save bar. The detail line underneath says "…answered 500 Internal Server Error". That names a
  cause the answer does not carry. It sends the operator to check the wrong thing exactly when the
  service has a bug. This is the fail-loud rule (HLD §2, problem 5) applied to the client. The render
  region already tells these apart (`api/jobs.ts`, kind `unpublished`), but the three reads and the save
  do not.

## What Changes

- **Calm, aligned list rows.**
  - Every cell's first line shares the title's line.
  - At table widths the job cell holds the job (status, then its time) and, at the cell's end on that
    first line, the row's action: Render, or why the row is blocked. The action has the same place in
    every row.
  - The job column takes the width the event column never used. At the 50rem card breakpoint the event
    column keeps 11rem.
  - In the card layout, date and clip count sit right under the title, the job is the card's last line,
    and the action ends that line.
  - A row's clip count and badges wrap as one group, with no indent.
- **Look-alike rows are told apart.** When two or more rows show the same date, title (or folder name in
  its place) and location, compared without regard to letter case, each also shows its folder's path
  under the project root, muted, under the title (`2024/2024-07-14 - Kalas`). That path is unique, so it
  separates the dev library's output collision and also two same-named folders in different years. The
  folder's name alone would not.
- **The whole event row opens its event.** A click anywhere on a year-group row that is not on a control
  opens its page, as the title does.
  - Text selection still works.
  - The keyboard path is unchanged: the title link stays the row's one tab stop.
  - Only rows that open something highlight on hover. The clip table and the "Needs attention" table
    lose their hover fill.
- **Empty and filtered states say what to do.**
  - An empty library shows no summary. It says "No events yet" and how to proceed.
  - A filter that hides every event says so and offers **Show all events**, which hands focus to the
    All choice.
  - A status message announces each finished read the operator started, and each filter change: how
    many events are shown and how many need rendering.
- **One time format.** A new `web/src/format.ts` writes every instant one way: short month and day, then
  hour and minute, the year only when it is not the current one, and no seconds, locale-aware. It covers
  read times, clip modification times and job times. Event dates stay `YYYY-MM-DD`, as the folders write
  them.
- **Failure copy.**
  - Failure-kind words are in sentence case ("Missing or invalid date or title").
  - A detail that starts with the row's own folder name drops that repetition, on the list and on the
    page alike.
  - The not-found page says it once.
  - "Not reachable" on the list and the page tells the operator to check that `auto-reel serve` runs,
    then Refresh, instead of printing the browser's error text.
- **No answer vs an unexpected answer.**
  - `api/events.ts`, `api/event.ts` and `api/reel.ts` split today's `unreachable` result kind in two:
    `unreachable` (the fetch was rejected) and `unpublished` (an answer whose status or body the route
    does not publish).
  - The list, the event page, Edit mode's document read and the save bar say "The service sent an
    unexpected answer." with the request and status for the second kind. A save still keeps the edits
    and offers Retry.
- **Docs:** `web/README.md` (the list paragraph, the time format under "Design system", and the file
  tree).

## Non-goals

- **No API, engine or schema change.** The service's error-row detail keeps its folder prefix, which the
  CLI prints usefully. The list and page trim it for display only.
- **The event page's own layout** (header stack, status column, thumbnails, loading state, the h1 for a
  look-alike event) belongs to `event-page-polish`. This change touches `EventDetail.tsx` only at call
  sites (design, "Files and parallel changes").
- **The job cell's inner words** (the "·" separator, 100%, toasts naming titles) belong to
  `jobs-live-polish`. **Toasts and dialogs** belong to `ui-a11y-polish`. **Edit-mode layout** belongs to
  `edit-mode-polish`.
- **No new list column.** Render stays inside the job cell (`render-progress-screen`'s decision). The
  cell's grid gives it a fixed place instead.
- **No larger touch targets** (critic minor, unassigned this round), no search or sort, and no
  list-level collision flag from the API.
- **The browser-drawn date field** in Edit mode keeps the browser's own format.
- Out of this round by the supervisor's brief: NEW-clip adoption into the default chapter on render, and
  the movie orphaned by a retitle.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: two ADDED and five MODIFIED requirements. Each MODIFIED block is re-based on the current
  `openspec/specs/web-app/spec.md` at the gate and again before archiving (task 1.1).
  - added `Requirement: Times are written one way on every screen`
  - added `Requirement: A request that gets no usable answer says which`
  - modified `Requirement: The event list shows every event with its render state`: look-alike rows show
    their folders' paths
  - modified `Requirement: The event list answers what needs rendering, from disk`: the empty and
    filtered-empty states, Show all events, and the announced result
  - modified `Requirement: The event list reports failures by cause`: an unpublished answer, and a fix
    detail without the repeated folder name
  - modified `Requirement: Each event opens on its own page`: the whole row opens the event
  - modified `Requirement: The event page reports failures by cause`: not found said once, the trimmed
    detail, and an unpublished answer

## Impact

- **Packages:** `web/` only, plus `web/README.md`.
  - Owned:
    - `src/events/EventList.tsx`, `list.css`, `labels.ts` and `grouping.ts` (list-only)
    - the new `src/format.ts`
    - `src/api/http.ts`, `events.ts`, `event.ts` and `reel.ts`
  - Call sites in other changes' files, each a few lines, listed exactly in design, "Files and parallel
    changes":
    - `src/events/EventDetail.tsx` and `common.tsx` (`event-page-polish`)
    - `src/edit/ClipOrderList.tsx`, `EventEditor.tsx` and `SaveBar.tsx` (`edit-mode-polish`)
    - `src/jobs/JobProgress.tsx` (`jobs-live-polish`)
    - the `.data-table` hover rules in `src/styles/components.css` (unowned; `ui-a11y-polish` owns only
      the toast rules there)
- **CLI vs API (Principle V):** neither is touched. This is presentation and client-side classification
  of answers the API already gives.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump**, and the fingerprint inputs are
  unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, **no Alembic migration**, and no rescan.
  `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gates:** none. The change builds on main `bca64f2`.
  - **Parallel changes:** `edit-mode-polish`, `jobs-live-polish`, `event-page-polish` and
    `ui-a11y-polish` edit some of the same files. Whichever lands second rebases (design, "Files and
    parallel changes").
  - **New runtime dependencies:** none (D-8's budget is unchanged).
- **Size (Principle VIII):** one package, one capability delta and 10 tasks.
