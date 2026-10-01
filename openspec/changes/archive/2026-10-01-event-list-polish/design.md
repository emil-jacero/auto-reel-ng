## Context

See proposal.md, "Why", for the motivation. The shape of the code on main `bca64f2`:

- **The list** (`web/src/events/EventList.tsx`, 433 lines) renders each year as a
  `<table className="data-table event-table">`. It has five `<col>`s, all sized in `list.css`:

  | Column | Width |
  |---|---|
  | date | 6.5rem |
  | clips | 8.5rem |
  | render | 24% |
  | job | 11rem |

  Below a 50rem panel, rows become grid cards. The job `<td>` is `jobs/LiveJobCell.tsx`, which belongs
  to `jobs-live-polish`. It holds `<span class="live-job">` with the job (`.job-progress` from
  `JobProgress.tsx`) and then either the compact Render (`.btn`) or `.row-blocked`. `jobs.css` sets
  `.live-job` to `inline-flex; flex-wrap: wrap; vertical-align: middle`, in `@layer components`.
  `list.css` is in `@layer screens`, so its rules win whatever their specificity.
- **Cells** align on their first line's baseline (`components.css`, `.data-table td`, the design
  system's decision). The middle-aligned `.live-job` breaks that for the job cell.
- **Hover:** `components.css` gives every `.data-table` row a hover fill, in both the table and the card
  layout. That covers the list, "Needs attention" and the event page's clip table. Only the title link
  in a list row navigates.
- **Times:**
  - `EventList.tsx:308` and `EventDetail.tsx:266` use `toLocaleTimeString()`
  - `EventDetail.tsx:504` and `edit/ClipOrderList.tsx:108` use `toLocaleString()`
  - `jobs/JobProgress.tsx:30-47` has its own `Intl.DateTimeFormat` pair: short month, and the year only
    when it is not the current one
- **Answers:**
  - `api/events.ts`, `api/event.ts` and `api/reel.ts` return `{ kind: 'unreachable' }` both for a rejected
    fetch and for any status or body the route does not publish
  - `api/jobs.ts` already separates the two, as `unreachable` and `unpublished`
  - the consumers of the three modules are `EventList.tsx`, `EventDetail.tsx`, `edit/EventEditor.tsx`
    (`readFailure`, and `send` twice) and `edit/SaveBar.tsx` (`SaveProblem`)
- **Failure words:**
  - `events/labels.ts` `FAILURE_LABEL` is lowercase
  - `events/common.tsx` holds `UNREACHABLE_CAUSE`, which the jobs and edit slices import too
  - `EventDetail.tsx` `describeProblem` shows the service's 404 detail under a title that already says
    the same thing

## Goals / Non-Goals

**Goals:**

- Every list row's cells share the title's line, and the row's action has one place at every width.
- One time format in the whole client, from one module.
- Tell "no answer" apart from "an answer the route does not publish" wherever an events or reel request
  is made, and give each its own words.
- Keep the edits in other changes' files to call sites, listed exactly below.

**Non-Goals:**

- Anything listed under the proposal's "Non-goals".
- New tokens, a new breakpoint, or a new column. The layout uses the existing 50rem and 30rem container
  breakpoints and the five `<col>`s.

## Reproduction

Every finding was reproduced read-only against `http://127.0.0.1:8114/`, which serves `wt-final-e2e` at
`bca64f2`. Its `web/src` is identical to main (`diff -r`). Every non-GET request was aborted, and none was
attempted. The jobs WebSocket and some reads were mocked in the browser to produce the running, queued,
cancelling, missing-clip, other-year, empty and 500 states. Scripts, logs and shots are in
`<scratchpad>/polish-spec/event-list-polish/`.

| Finding (brief P3) | Result |
|---|---|
| List at 1280: ragged rows, wandering Render, status off the title's line | **Reproduced.** The columns measure date 104, event 458, clips 136, render 276 and job 176 px, and titles are 35-166 px wide. Rows are 43, 58, 59, 93 and 103 px, and 77-103 px with live jobs. The job pill sits at top 8 while the title sits at 35. Render is at top 58, or at top 8 in the job-less `kalas` row. 1024 and 1440 behave the same. |
| 768 cards: date and clips pushed away; wrapped "1 missing" indented | **Reproduced.** Grillkväll's date is at 59, against 39 in the other cards, and its Render sits inline beside the time. Sommarlov's wrapped badge is at x 643 against the count at 639, which is the badge's `margin-inline-start`. |
| Five date and time formats | **Partly.** There are three formats the app controls: `h:mm:ss AM` (Scanned and Read), `10/1/2026, 12:23:00 AM` (clip times) and `Oct 1, 12:35 AM` (job times). In sv-SE they read `01:49:39`, `2026-10-01 00:23:00` and `1 okt. 0:35`. The ISO event date is the folders' own date, and the Edit form's date field is drawn by the browser. Neither is a defect, so neither is changed. |
| Look-alike Kalas rows | **Reproduced.** Both rows read "2024-07-14 Kalas 1 clip". |
| Rows highlight but are not clickable | **Reproduced** in code (`components.css` hover on every `.data-table` row) and on screen. |
| Bare empty and filtered-empty states; nothing announced | **Reproduced.** An empty read shows "0 of 0 events need rendering" and "No events found.", with no heading. The filtered-empty state has no control. A MutationObserver on every live region logged nothing on a filter change, and on Refresh logged only "Scanning events…" and then "". |
| Failure copy | **Reproduced.** The pill reads "missing or invalid date or title". The row's fix reads "2024-02-30 - Omöjligt datum: no date: …". The not-found page adds "no event '2024/Finns inte' under the configured project root" under its title. An unreachable list shows "TypeError: Failed to fetch". |
| A 500 reads as "not reachable" | **Reproduced** on the list and the event page with a mocked bare 500: "The service is not reachable." over "…answered 500 Internal Server Error". The save bar has the same path (`reel.ts` `unexpected()` feeds the `unreachable` kind into `SaveBar`'s `UNREACHABLE_CAUSE`). That was confirmed in code, and the completeness critic's shot `c2-save-500-1280.png` shows it. |

Nothing was dropped. Parts of the critics' proposed fixes were not adopted:

- **"Updated" as one verb for both screens:** rejected. "Scanned" and "Read" pair with "Scanning events…"
  and "Reading event…" (web-design-system design).
- **A new `col-action` column:** rejected. See "The list's row layout".
- **An 8.5rem clip-time column:** not this change's file. The critic's width is also wrong for times
  from past years (see "One time format").
- **A stretched-link overlay:** rejected after measurement. See "The whole row opens its event".
- **An empty-state line naming the expected layout** (`<root>/<year>/<YYYY-MM-DD - Title>/`): rejected.
  See "Empty states and announcements".

An adversarial review re-checked this design against main, the other five polish changes and the live
server (scripts, logs and shots in `<scratchpad>/polish-spec/event-list-polish/review/`). It changed:

- the look-alike line, from the folder's name to its path, because look-alikes can share a name
- `useId` in `EventRow`, which must be called unconditionally
- the separator rule, now a stop-gap that exists only until `jobs-live-polish` lands
- the blocked note's alignment check, from its center to its top
- the dev-proxy risk: Vite answers 500, not 502
- the scope of the "not reachable" hint, which is limited to the list's and the page's reads

## Research & Decisions

### The list's row layout

**Context**: The job column is 11rem. It cannot hold a status, a time and an 81 px Render side by side,
so they stack, and `vertical-align: middle` centers that stack against the other cells. The event
column's 458 px mostly holds 35-166 px titles.

**Explored**: The following were prototyped by injecting CSS into the live page and measured at 1440,
1280, 1024, 900, 768, 600, 390 and 320 px, with mocked queued, running, cancelling, blocked,
other-year and no-job rows and a 38-clip long-title row (`p2_proto.py`, `p6_proto2.py`):

- **Alignment only** (`vertical-align: baseline` on `.live-job`). First lines align, but rows stay three
  lines and Render still moves between the top and the bottom of the cell.
- **A separate trailing action column** (the critic's fix). It needs `RowRender` moved out of
  `LiveJobCell.tsx`. That file belongs to `jobs-live-polish`, which is changing its props this round.
  It would also reverse `render-progress-screen`'s decision that the table gains no column.
- **A two-track grid inside the job cell** (chosen). In Chromium, Firefox and WebKit, the date, the
  verdict pill and the job pill start within 3 px of the title, and the taller Render's center is within
  2 px of the title's. Render sits at the same place in every row. A finished job reads as its status
  over its time, two lines. An active job adds its bar.

**Decision** (`list.css` only, `@layer screens`):

- **Widths:**

  | Column | Width |
  |---|---|
  | date | 6.5rem |
  | clips | 7.5rem |
  | render | 21% |
  | job | 29% |

  That is 14rem fixed plus 50%, so at the 50rem breakpoint the event column keeps 11rem, as the
  components.css comment asks. At the 72rem maximum the columns measure date 104, event about 350, clips
  120, render 241 and job 333 px. At a 1024 px window the job column is 278 px, enough for "finished
  Oct 1, 12:35 AM" beside an 81 px Render.
- **At table widths** (`@container (width >= 50rem)`):
  - `.event-table .live-job` becomes `display: grid; grid-template-columns: minmax(0, 1fr) auto;
    align-items: baseline; column-gap: var(--s-3)`
  - `.live-job > .job-progress` goes in `1 / 1`
  - `.live-job > :is(.btn, .row-blocked)` goes in `1 / 2` with `justify-self: end`
  - `.row-blocked` gets `max-inline-size: 7.5rem`, so it wraps to two lines
  - `.live-job .job-when` gets `flex-basis: 100%`, so the time is the job's second line, for finished
    jobs too
  - **The separator is `jobs-live-polish`'s.** Its design ("The separator") replaces today's
    `.job-words:has(+ .job-when)::after` dot and already gives an active list row's time its own line with
    no dot (`.job-progress .job-words + .job-when { flex-basis: 100% }`, `::before { content: none }`).
    This change MUST NOT add a second rule for it, except as a stop-gap: only while today's `::after` rule
    is still in `jobs.css` when this change is applied (task 1.1 greps it), `list.css` adds
    `.live-job .job-words::after { content: none }` inside this block, with a comment naming
    `jobs-live-polish`, because the stacked time would otherwise leave the dot dangling at the end of the
    words' line. Whichever change lands second deletes that stop-gap rule: `jobs-live-polish` removes it
    from `list.css` as a one-line call site, or this change does not add it.

  A block-level grid gives the cell its first baseline in all three engines (measured). The review
  re-measured this exact block at 1440, 1280, 1024, 900, 768, 600, 390 and 320 px (`review/spike.py`).
  It ran with `jobs-live-polish`'s separator rules injected in Chromium, Firefox and WebKit, and
  without them in WebKit. The results:

  - no page scrolls sideways
  - the date, verdict and job pills start within 3 px of the title
  - every Render's center is within 3 px of the title's
  - every action ends at one right edge per table and per card

  A two-line "Blocked by missing clips" note is top-aligned (its top within 2 px of the title's), so its
  center sits 7-8 px lower. That is the intended look, and task 6.1 checks its top, not its center.
- **At card widths** (`< 50rem`):
  - the areas become `'event event render' 'date clips render' 'job job job'`, so the date and clip count
    follow the title, and the job is the card's last line
  - the rows become `grid-template-rows: auto 1fr auto`. With plain `auto` rows, a verdict whose reasons
    run to three lines (the 38-clip row at 768 px, Grillkväll at 600 px) spreads its extra height over
    both rows it spans. That pushed the date 14 px below the title instead of 6 px (`p8_lasse.py`). A
    flexible second row takes all of it, below the date line.
  - `.live-job > :is(.btn, .row-blocked)` gets `margin-inline-start: auto`, so the action ends the job
    line (jobs.css makes `.live-job` `display: contents` there)
  - below 30rem the areas stay as they are today, with `grid-template-rows: none`

  No page scrolls sideways at any measured width.
- **Clip counts:** the count and its badges go in a new `<span className="clip-counts">`, with
  `display: inline-flex; flex-wrap: wrap; align-items: baseline; gap: var(--s-1) var(--s-2)`. The
  `.cell-clips .badge` margin is removed, so a wrapped badge starts at the cell's edge.

**Rationale**: This fixes both the alignment and the action's place without touching `LiveJobCell.tsx`
or adding a column. The selectors depend only on five class names `jobs-live-polish` publishes
(`.live-job`, `.job-progress`, `.job-words`, `.job-when`, `.row-blocked`) plus `.btn`. The gate task checks they
still exist.

### The whole row opens its event

**Context**: Rows take a hover fill, but only the title navigates.

**Explored**:

- **A stretched link** (`tr { position: relative }` plus `a::after { position: absolute; inset: 0 }`).
  It works in Chromium and Firefox, and in the card layout everywhere. In WebKit's table layout a table
  row does not become the containing block: a click on Trasig's date opened **the last row's event**,
  2023 Midsommar (`p3_click.py`). A fallback that mis-navigates is worse than none. The overlay would
  also block text selection.
- **A row click handler** (chosen). It opened the right event in Chromium, Firefox and WebKit at 1280 and
  390. A drag-selection over the date did not navigate (`p4_rowclick.py`).
- **Dropping the hover.** Adopted for the rows that open nothing.

**Decision**:

- `EventRow`'s `<tr>` gets `onClick={openRow}`:

  ```ts
  /** A plain click on a row, not on a control and not ending a text selection, opens its title's link. */
  function openRow(event: MouseEvent<HTMLTableRowElement>): void {
    if (event.button !== 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
      return
    }
    if (event.target instanceof Element && event.target.closest('a, button, input, label, select, textarea')) {
      return
    }
    if (window.getSelection()?.isCollapsed === false) {
      return
    }
    event.currentTarget.querySelector<HTMLAnchorElement>('.cell-event a[href]')?.click()
  }
  ```

  - `.click()` follows the hash exactly as a click on the title does, so routing, scroll restore and the
    focus move to the page's h1 are unchanged.
  - The synthetic click bubbles back to the `<tr>`. Its target is the `<a>`, so the `closest(…)` test
    returns at once. That test MUST stay ahead of the `.click()`, or the handler would recurse.
  - The handler MUST NOT navigate on a click on a control, on a modified or non-primary click, or on one
    that ends a text selection.
  - The row gets no role, tabindex or key handler. The title link stays its only tab stop, so the
    keyboard path and the accessibility tree are unchanged.
  - **Every control in the row stays above the row target.** Nothing is laid over the row. A control's
    own box, and any hit area its own pseudo-element adds, is the control. That includes
    `ui-a11y-polish`'s coarse-pointer `.btn::after`, which grows the compact Render to 44 px tall. So the
    click's target is inside the control, `openRow` returns, and only the control's own handler runs.
    The list rows' controls are the title link and Render. Cancel lives on the event page, not in a row.
- `list.css` adds:
  - `.event-table tbody tr { cursor: pointer }`
  - at table widths, `.event-table tbody tr:hover > td { background: var(--surface-hover) }`
  - at card widths, `.event-table tbody tr:hover { background: var(--surface-hover) }`
- `components.css` loses the two generic hover blocks:
  - `.data-table … tbody tr:hover > td` (lines 252-254)
  - the card-layout `tbody tr:hover` / `tr:hover > td` pair (lines 301-307)

  So "Needs attention" rows and the event page's clip rows no longer highlight.
- "Needs attention" rows get no row click. Their fix text is instructions the operator may want to
  select and copy, and a row target would navigate on the first click of a double-click. Their folder
  link stays.

**Rationale**: One mechanism that behaves the same in every engine and keeps native link behaviour on
the title (middle-click, context menu). The hover now appears exactly where a click does something.

### Look-alike rows show their folder's path

**Context**: Two rows read the same when they show the same date, the same title (or, without one, the
same folder name in its place) and the same location. The dev library's output collision, the Kalas pair,
is such a case: the engine compares output paths case-insensitively after NFC normalization
(`render/orchestrator.py`, `_collision_key`), and the output name is built from the same date, title and
location (`output_filename`). The two sets are close but not equal: two untitled events collide on
`Untitled.mp4` while their rows read differently (each shows its own folder name), and rows can read alike
without colliding (one titled "Blandat", the other an untitled folder named `Blandat`). The rule therefore
follows what the rows show, not the engine's key.

**Explored**:

- Showing the folder on every row where the title differs from the folder name was rejected. That is
  nearly every row (the folder is `<date> - <title>[ - <location>]`, and titles are edited), so it would
  double the list's text to disambiguate one pair.
- Showing the folder's **name** (the id's last segment) on look-alikes, as first written, was rejected in
  review. Look-alikes can share that name: two undated, untitled folders `2023/Blandat` and `2024/Blandat`
  both read "Blandat" in the "No date" group, and a "Blandat" line under each would tell nothing apart.
- **Showing the event id** (the folder's path under the project root, which no two events share) on
  look-alikes only (chosen). It changes only the rows that need it, and it is unique by construction. In a
  year group its year prefix repeats the group's heading, which is acceptable on a row that exists to say
  exactly where its folder is: the operator resolves a look-alike by renaming one of the folders on disk.

**Decision**:

- `grouping.ts` gains a pure `lookAlikes(events: readonly EventSummary[]): ReadonlySet<string>`. It
  returns the ids of every event whose key is shared with another event. The key is `date ?? ''`,
  `(title ?? <folder name>).normalize('NFC').toLowerCase()` and
  `(location ?? '').normalize('NFC').toLowerCase()`, joined by `\u0000`. NFC makes two spellings of "å"
  that read the same compare the same. The folder name is the id's last segment, computed inline, so
  `grouping.ts` keeps type-only imports and runs under the node check (task 4.2).
- `ReadyView` computes it over **all** readable events, not the filtered ones, so a row's path line does
  not appear and disappear with the filter. It passes `lookAlike` to each `EventRow`.
- `EventRow` calls `const pathId = useId()` **unconditionally**, at its top. React's rules of hooks
  forbid `useId()` inside `{lookAlike && …}`: a refresh that changes the look-alike set would change the
  hook order and throw. Only the markup is conditional: a look-alike row adds
  `<span id={pathId} className="event-folder">{event.event_id}</span>` after the location, and the title
  link gets `aria-describedby={lookAlike ? pathId : undefined}`, so two "Kalas" links are told apart by
  assistive technology too. The span is `display: block`, muted and `--text-xs`, and the cell's existing
  `overflow-wrap: anywhere` breaks a long path.

**Rationale**: This targets the one conflict v1 asks the operator to resolve by hand, and the line it adds
is the one fact that always tells two rows apart. The event page's h1 for such an event belongs to
`event-page-polish`.

### One time format

**Context**: There are three formats (see "Reproduction"). The job one has already been chosen and
specified (`job-summary-times`: "No new time format").

**Decision**: a new `web/src/format.ts` with no imports, so it can be checked under
`node --experimental-strip-types`:

```ts
const THIS_YEAR = new Intl.DateTimeFormat(undefined, {
  month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
})
const OTHER_YEAR = new Intl.DateTimeFormat(undefined, {
  year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
})

/**
 * An instant, written the one way the client writes times: short month and day,
 * hour and minute, the year only when it is not the current one, never seconds,
 * locale-aware. A value that does not parse is returned as given, never as a
 * made-up time. Callers keep the exact instant in `<time dateTime>`.
 */
export function formatInstant(value: string | Date): string
```

- **Call sites:**
  - the list's "Scanned" and the page's "Read" become `<time dateTime={fetchedAt.toISOString()}>`
    around `formatInstant(fetchedAt)`
  - clip times on the page and in Edit mode become `formatInstant(clip.mtime)`
  - `JobProgress.tsx` drops its own pair and calls `formatInstant(time.iso)`
- Job times keep today's exact output. Read and clip times lose their seconds and gain the month and
  day.
- Every instant the client shows MUST go through `formatInstant`; no other module may build an
  `Intl.DateTimeFormat` or call `toLocale*String` (task 2.1 greps for both).
- Checked in review in `docker.io/library/node:22` with `TZ=Europe/Stockholm`: under `LANG=en_US.UTF-8`
  and `C.UTF-8` it writes "Oct 1, 12:23 AM", "Jun 22, 2025, 8:03 PM" and returns "nonsense" as given;
  under `sv_SE.UTF-8` it writes "1 okt. 0:23" and "22 juni 2025 20:03", without seconds.
- **Event dates stay `YYYY-MM-DD`.** They are calendar dates the folders and `reel.yaml` write that way,
  and the spec's scenarios quote them.
- **Supersedes** web-design-system's "Scanned 14:02:11". Seconds were kept to show that a same-minute
  Refresh re-read. That is now signalled by the placeholder rows and by the new result announcement
  ("Empty states and announcements"). A read time without a date would be ambiguous in a tab left open
  overnight.
- Measured widths: "Oct 1, 12:23 AM" is about 100 px against 155 px today, and a past year's "Jun 27,
  2024, 3:14 PM" is about 142 px. So `detail.css`'s 11.5rem `.col-mtime` and `edit.css`'s time track
  (other changes' files, left as they are) have room to spare. Their owners may narrow them.

**Rationale**: One function, one module, and the format the spec already accepted for jobs. The format
is a convention of D-10's visual system. D-10 points later slices to `web/README.md`, "Design system",
so it is recorded there, and the HLD gains no D-n entry.

### No answer vs an unpublished answer

**Context**: `jobs.ts` models this already. The three other modules fold both into `unreachable`.

**Decision**:

- **`api/http.ts`** gains the shared type and a helper:

  ```ts
  /** A request with no usable answer: none at all, or one its route does not publish. */
  export type Unanswered =
    // no answer at all: fetch rejected (the message is the error)
    | { kind: 'unreachable'; message: string }
    // an answer whose status or body the route does not publish (the message names it)
    | { kind: 'unpublished'; message: string }

  /** "GET /api/v1/events answered 500 Internal Server Error": what came back instead. */
  export function unpublishedAnswer(
    method: 'GET' | 'PUT', url: string, response: Response,
  ): Extract<Unanswered, { kind: 'unpublished' }>
  ```

- **`events.ts`, `event.ts` and `reel.ts`** make their unions `ok | problem | Unanswered`. Every
  fall-through return, and `reel.ts`'s "200 without an ETag", becomes `unpublished`. A rejected fetch
  stays `unreachable`, and an `AbortError` is still rethrown. `jobs.ts` is untouched: its members are
  structurally the same.
- **`events/labels.ts`** gains the wording. It stays a type-only importer:

  ```ts
  export const UNANSWERED_CAUSE: Record<Unanswered['kind'], string> = {
    unreachable: 'The service is not reachable.',
    unpublished: 'The service sent an unexpected answer.',
  }
  export const NOT_REACHABLE_HINT = 'Check that auto-reel serve is running, then press Refresh.'
  /** A read's failure for the list and the page: the cause, and what to show under it. */
  export function unansweredFailure(result: Unanswered): { cause: string; detail: string }
  //   unreachable → { cause, detail: NOT_REACHABLE_HINT }   (never the browser's error text)
  //   unpublished → { cause, detail: result.message }       ("GET … answered 500 …")
  ```

  - `common.tsx`'s `UNREACHABLE_CAUSE` becomes `= UNANSWERED_CAUSE.unreachable`. There is one source
    for the sentence, and the jobs slice keeps its import.
  - `labels.ts` does not import `common.tsx`. That import would be a cycle, since `common.tsx` imports
    `labels.ts`.
- **Consumers:**
  - The list and the page handle `case 'unreachable': case 'unpublished':` with
    `...unansweredFailure(result)`.
  - Edit mode's `readFailure` uses `UNANSWERED_CAUSE[result.kind]` and keeps `result.message` as the
    detail. Its own "Try again" is the recovery.
  - The save path carries the kind through. `SaveProblem`'s last member becomes
    `{ kind: 'unreachable' | 'unpublished'; detail: string; retry: Operation }`. `SaveBar` renders it
    in the `disk` group with the title `UNANSWERED_CAUSE[problem.kind]`, the detail and Retry.
  - Only the list's and the page's reads swap the browser's error text for `NOT_REACHABLE_HINT`, whose
    "press Refresh" names their own control (the spec scopes the hint to those two reads). Edit mode's read
    and the save bar keep the message as their detail, under their own "Try again" and Retry. Their
    wording is `edit-mode-polish`'s, and this change edits only the lines listed below.
  - `EventEditor`'s `.catch` around `send()` (a thrown client error, not an answer) keeps
    `kind: 'unreachable'`. It is left as it is: changing it is not a call site.
- The list's and the page's `switch` statements have no `default`. A missing `case` would leave them
  loading silently, so task 3.1 names every consumer, and task 6.2 checks each kind on each screen.

**Rationale**: The same vocabulary as `jobs.ts`, so every request in the client tells the two apart.
The operator is told to check the service only when it did not answer.

### Failure copy

**Decision**:

- **`FAILURE_LABEL`** becomes "reel.yaml can't be read" (unchanged, since a file name starts it),
  "Missing or invalid date or title" and "Files can't be read". That is sentence case, like every
  other status label. The list, the page and the save bar all read this map.
- **`labels.ts`** gains `failureDetail(eventId, detail)`. When `detail` starts with
  `<folder name>: `, it returns the rest with its first letter capitalized. Otherwise it returns
  `detail` unchanged. The folder name is the id's last segment, computed inline, because `labels.ts`
  does not import `common.tsx`.
  - Omöjligt datum's detail then reads "No date: folder name date 2024-02-30 is not a real date; set
    metadata.date in reel.yaml or correct the folder name".
  - A parse error's `/path/reel.yaml: …` is left alone.
  - The list's "How to fix" cell and the page's 502 failure both use it, so "reads the same as in the
    list" holds.
- **Not found:** the page's and Edit mode's 404 branches set `detail: null`. The title already names the
  event and the project root. The action "Back to the event list" stays.
- **Unreachable** on the list and the page: see `unansweredFailure`. The browser still logs the failed
  request in its console.

**Rationale**: The engine's detail is right for the CLI, which prints it without a row beside it. The
GUI trims only what its own row already shows, and MUST NOT rewrite the fix itself.

### Empty states and announcements

**Decision** (all in `EventList.tsx`):

- **Summary:**
  - `Summary` renders only when the read holds any row
  - its "N of M events need rendering" chip only when `events.length > 0`
  - its attention chip only when `errors.length > 0`, as today
- **The list's empty states become a `<div className="empty-state">`.** Today's element is a `<p>`, which
  cannot hold a title paragraph or a button. `.empty-state` (`shell/shell.css`) is already a centered
  column, so only `.event-list .empty-title` (`list.css`: `--fg`, weight 600) is new.
- **No rows at all:** the film icon, `<p className="empty-title">No events yet</p>` and "The service found
  no event folders in its project. Add a folder of clips for an event, then press Refresh." It names no
  path or layout: the client does not know the root, and layouts are pluggable (D-6).
- **The filter hides every event:**
  - the check icon, "Nothing needs rendering", and "All N events are up to date." (or "The one event is
    up to date.")
  - a `btn btn-secondary` **Show all events**, whose handler calls `setOnlyStale(false)` and then focuses
    the All radio through a ref `FilterControl` takes. The radio exists before the button unmounts, so
    focus never falls to `<body>`, and `input:focus-visible + label` shows the ring.
- **Only error rows:** "No other events." as today.
- **Result announcement:** a second status region in `.page-meta`, beside `LoadStatus`:
  `<p role="status" className="visually-hidden">{…}</p>`.
  - It MUST be mounted in every state, empty unless ready. A live region inserted together with its
    text is not reliably announced, so the element never mounts with the result.
  - It holds text only while `state.status === 'ready'`, so an operator's read (which passes through
    `loading`) empties it and then fills it. That is announced every time, even with unchanged counts.
  - A quiet re-read keeps `ready`, so the text changes, and is announced, only when the counts change.
  - A filter change changes it at once.
  - Examples of the text:
    - "Showing 11 events; 5 need rendering."
    - "Showing the 5 of 11 events that need rendering."
    - "None of the 11 events needs rendering."
    - with error rows, a following " 1 needs attention."
    - with no rows, "No events found."
  - It is visually hidden because the stat chips already show the same counts.

**Rationale**: `LoadStatus` belongs to `ui/` (`ui-a11y-polish`) and keeps its contract: the read's
message, then empty. The list's result is list business.

## Files and parallel changes

Owned by this change: `src/format.ts` (new), `src/api/http.ts`, `events.ts`, `event.ts`, `reel.ts`,
`src/events/EventList.tsx`, `list.css`, `labels.ts`, `grouping.ts` (list-only; unassigned in the brief)
and `web/README.md` (the list paragraph, "Design system" and the file tree).

Call-site edits in other changes' files, exactly these and nothing else. Whichever change lands second
re-applies the other side's lines.

- **`src/events/EventDetail.tsx`** (`event-page-polish`):
  - imports: `formatInstant`; `failureDetail` and `unansweredFailure`; drop `UNREACHABLE_CAUSE`
  - `describeProblem` 404: `detail: null`
  - `describeProblem` 502: `detail: failureDetail(eventId, problem.detail)`
  - `load()`: `case 'unreachable': case 'unpublished': setState({ status: 'failed', ...unansweredFailure(result) })`
  - the "Read" span: `<time dateTime=…>{formatInstant(state.fetchedAt)}</time>`
  - the clip time: `formatInstant(clip.mtime)`

  If `event-page-polish` moves the "Read" time, the formatter call moves with it.
- **`src/events/common.tsx`** (`event-page-polish`): `UNREACHABLE_CAUSE = UNANSWERED_CAUSE.unreachable`,
  and the import line.
- **`src/edit/EventEditor.tsx`** (`edit-mode-polish`):
  - `readFailure`: the `unreachable` test covers `unpublished`, with `UNANSWERED_CAUSE[result.kind]`
  - `readFailure`'s 404 `detail: null`
  - `send()`'s overwrite re-read passes `kind: latest.kind`
  - `send()`'s save `switch` adds `case 'unpublished':` with `kind: result.kind`
  - the import line
- **`src/edit/SaveBar.tsx`** (`edit-mode-polish`):
  - the `SaveProblem` member's `kind`
  - `case 'unpublished':`
  - the title expression `problem.kind !== 'disk' ? UNANSWERED_CAUSE[problem.kind] : …`
  - the import line

  `edit-mode-polish` restyles this file's alert and buttons. These lines are in its failure `switch` and
  type, not in its layout.
- **`src/edit/ClipOrderList.tsx`** (`edit-mode-polish`): the clip time becomes `formatInstant(clip.mtime)`,
  plus the import.
- **`src/jobs/JobProgress.tsx`** (`jobs-live-polish`): `THIS_YEAR`, `OTHER_YEAR` and `formatTime` (lines
  28-47) are deleted, `formatInstant` is imported, and line 105 calls it. `jobs-live-polish` edits the
  floor at line 121 and the separator's words, which are other hunks.
- **`src/styles/components.css`** (unowned lines; `ui-a11y-polish` owns only the toast rules, lines
  737-826): the two `.data-table` hover blocks are deleted. The design critic's own fix dropped the clip
  table's hover too ("whose rows have no action"), so `event-page-polish`'s clip rows lose a fill that
  promised nothing. `event-page-polish` edits no `styles/` file.

Other changes' lines in **this** change's files, which this change MUST keep when it lands second:

- **`src/events/EventList.tsx`:** `jobs-live-polish` adds `title={event.title}` on `<LiveJobCell>` (its
  design, "File ownership and coordination").
- **`src/events/list.css`:** if this change lands first with the separator stop-gap ("The list's row
  layout"), `jobs-live-polish` deletes that one rule when its own separator rule lands.

**Coordination notes for the supervisor:**

- `jobs-live-polish` owns the "·" separator, and its rules already cover list rows. This change adds a
  stop-gap only while today's `::after` dot exists (task 1.1), and the second change to land removes it.
- `jobs-live-polish` names events in toasts by title. Its spec already names the output-collision toast's
  events by folder name, which covers the Kalas pair: the service refuses to queue either event of an
  output collision (`api/events_read.py` `output_collision` is symmetric), so no "queued" toast names one
  of the pair by its shared title.
- `event-page-polish` owns the event page's h1 for a look-alike event.

## Failure behavior and idempotency

- Presentation only. No request is added, removed or reordered, no write path changes, and nothing on
  disk or in the database is touched. Opening, filtering and refreshing stay reads (spec, "Reading a
  screen never changes state").
- A row click performs exactly the title link's navigation. Pressing Render in a row is a click on a
  `button`, so the row ignores it and the enqueue runs as today.
- **An unpublished answer to a save:** the service may or may not have written. Retry resends the same
  body under the same `If-Match`, so a write that did land answers 412. That leads to the existing
  conflict alert, never a silent overwrite.
- `formatInstant` never throws on a bad value and never invents one: it returns the value as given.
  `failureDetail` returns the service's detail unchanged unless it starts with the row's own folder
  name.
- Re-runs: a second Refresh re-announces its counts, because the region is emptied while loading. A
  `--force` render and a worker restart do not concern this client change.
- **Rendered output and fingerprint:** unchanged.

## Risks / Trade-offs

- **Near the card breakpoint (about 50-56rem panels), a row with an action can take three lines.** At 900
  px the job column is 242 px, so "finished" and "Oct 1, 12:39 AM" split around the Render. → Accepted.
  Widening the job column there would squeeze the event column below 11rem, and from a 1024 px window up
  every row fits.
- **The list's layout reads five class names `jobs-live-polish` owns.** → Gate task 1.1 greps them, and the
  selectors are direct-child and descendant only. A renamed class leaves today's layout (cells still
  readable), not a broken page.
- **Double-clicking a row's text navigates on the first click.** → Drag-selection works. The event page
  shows the same facts, and "Needs attention" rows, whose text is meant for copying, are not row targets.
- **Under `npm run dev` with the service down, the list now reads "unexpected answer" rather than "not
  reachable".** Vite 6's proxy answers a failed upstream connection itself, with a bare **500**
  (`res.writeHead(500, { 'Content-Type': 'text/plain' })` in its proxy error handler). → Accepted, and
  truthful: something did answer, and the detail names the request and its 500. `api/jobs.ts` already
  behaves this way. The built client served by `auto-reel serve`, the only shipped setup, gets a rejected
  fetch when the service is down and says "not reachable" with the hint.
- **Read times lose their seconds.** → A same-minute Refresh is still visible (placeholders) and audible
  (the announcement).
- **Under a coarse pointer at table widths, a Render's 44 px hit area (`ui-a11y-polish`) reaches 1 px into
  the row above.** That pixel is the row above's 1 px bottom border, the divider line. The cell's 8 px top
  padding is one short of the area's 9 px growth, so a tap on exactly that line presses the lower row's
  Render. → Accepted: it is a divider line, not the upper row's content, and it hands the tap to the
  nearest control. Card widths leave 13 px or more. Measured with `ui-a11y-polish`'s rules injected (it had
  not landed).
- **Parallel edits in `EventDetail.tsx`, `EventEditor.tsx`, `SaveBar.tsx`, `ClipOrderList.tsx` and
  `JobProgress.tsx`.** → Each edit is listed above, and each is a few lines away from what the owning
  change rewrites.

## Migration Plan

None. The change is client-only and needs no data migration. Rollback is a revert.

## Supervisor decisions

Recorded at the start of implementation (2026-10-01), binding on this change:

- **Polish round context:** the supervisor's polish brief, including its file ownership. Six sibling
  changes run in parallel: `edit-mode-polish` (P1), `jobs-live-polish` (P2), this change (P3),
  `event-page-polish` (P4), `ui-a11y-polish` (P5) and `serve-clean-exit` (P6). This change stays in its
  owned files plus the call sites listed in "Files and parallel changes". For `web/README.md` hunks,
  whichever change lands second rebases and keeps every side.
- **Look-alike rows show the full path** (for example `2024/2024-07-14 - Kalas`): accepted.
- **Deleting the generic `.data-table` row hover:** accepted. `event-page-polish` is told.
- **The separator stop-gap in `list.css`** is allowed only if `jobs-live-polish` has NOT landed when the
  pr/ branch is built. `jobs-live-polish` removes it when it lands second.
- **The Vite dev proxy answering 500 when the service is down** ("Risks / Trade-offs"): accepted.
  `web/README.md`'s development section gains one sentence saying so.

Recorded after implementation (Phase 2), binding on this change:

- **The Firefox 0.1 px pill miss is accepted.** At 900-1440 px, Firefox draws both the verdict pill and the
  job pill 3.1 px above the title's top. Task 6.1 allows 3 px, and Chromium and WebKit are within it. The
  job pill's top equals the verdict pill's in all three engines, and both pills' text baselines sit 3 px
  above the title's in every engine. The offset comes from the shared `ui/Pill` (`ui-a11y-polish`'s file),
  not from this change's grid, so no baseline fix is made here.
- **Implementation deviations accepted:**
  1. `failureDetail` also returns the detail unchanged when only blank text follows the folder-name
     prefix, so "a bare prefix comes back unchanged" holds.
  2. `formatInstant` given an invalid `Date` returns its string form (`"Invalid Date"`), the value as
     given, never a made-up time.
  3. The "only error rows" empty state is a `div.empty-state` holding a `<p>`, like the other two, with
     the same words and look as before.
  4. The result announcement's wording for one event: "The one event does not need rendering." and
     "Showing the N of M events that need(s) rendering."
  5. `web/README.md` also extends the list paragraph's failure sentence ("not reachable" vs "an unexpected
     answer"), and the file tree's lines for `http.ts` and `labels.ts`.
- **The separator stop-gap stays.** `jobs-live-polish` had not landed on `origin/main` when the pr/ branch
  was built: `.job-words:has(+ .job-when)::after` is still in `jobs.css`. `jobs-live-polish` deletes the
  `list.css` rule when it lands.
- **The row target leaves every control in the row clickable above it** ("The whole row opens its event").
  This was checked by hit-testing every control of every list row at 1280, 768 and 390 px:
  - with a fine pointer in Chromium, Firefox and WebKit
  - with a coarse pointer in Chromium (touch emulation), with `ui-a11y-polish`'s hit-area rules injected

## Open Questions

None that change the specs or the tasks. The coordination notes above are for the supervisor.
