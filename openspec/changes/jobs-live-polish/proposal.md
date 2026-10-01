## Why

GUI v1 (HLD **§6 phase 8**, §4.10, stack **D-8**) closes legacy problem 8 (HLD §2: no GUI, so a render
could be started and followed only from a terminal). Slice E (`render-progress-screen`) made rendering
live: one jobs WebSocket per tab, Render / Render anyway / Cancel on the event page, a compact Render on
list rows, and toasts when a render the tab started ends. The final end-to-end pass on `main` (`bca64f2`)
and four critics found seven defects in that slice. Each was reproduced again, read-only, for this change
(design, "Findings reproduced"):

- **A stale job wins over a newer read.** While the jobs socket is down, a Refresh cannot replace the
  store's copy of the same job (`useJob.ts` `choose()`: the store's copy always wins). A job the service
  reports as running at 60% still shows as "Queued · last known". Cancel then skips the confirmation that
  the spec requires for a running job, and the running render is flagged at once. The screen shows an
  older state as current, which is the fabrication Principle I forbids.
- **A row's Render is silent to assistive technology.** Pressing Render on a list row moves focus to the
  row's link, and nothing announces that the render was queued. The first thing spoken is the terminal
  toast.
- **Confirming "Render anyway?" drops keyboard focus to `<body>`.** The next Tab lands on "Skip to
  content".
- **"Cancel this render?" outlives its job.** The dialog stays open after the job it asks about has
  finished. "Render anyway?" also stays open after another client's job has appeared for the event.
- **A running job reads 100%.** `Math.floor(1.0 * 100)` is 100. The worker writes progress 1.0 and the
  done state as two writes, and the WebSocket publishes the moment between them, so for about a second
  the page shows "Rendering" with a full bar and "100%".
- **The "·" separator dangles.** At a line end in active job states ("Waiting for a worker ·"), on every
  queued or cancelling list row at every width, and on the event page at phone width.
- **Toasts name events by folder, not by title.** For example, 'Rendered “2024-08-02 - Badutflykt -
  Varberg”' where the screens say "Badutflykt". The folder's " - " can wrap to the start of a line, where
  it reads like a list bullet.

The supervisor added an eighth fix for this round: **the render card grows by about 11.5 px** when the first
progress arrives, because the meter's figures line appears.

## What Changes

- **The newest copy of a job wins while the socket is down.** While the connection is live, the store's
  copy of an active job stays authoritative, because the socket carries every change within about a
  second. While the connection is not live, the store's copy is only last known. A read that shows the
  same job further along replaces it: running beats queued, a later run beats an earlier one, and more
  progress beats less. The fields only the socket carries, such as the cancel flag, are kept. A Refresh
  during an outage, on the page or the list, therefore shows the job as the service reports it. The
  time-left estimate is shown only beside the progress it was computed from.
- **Cancel asks whenever the job might be running.** It asks for a running job, as before. It also asks
  for a job shown as queued while the connection is not live, because that job may have started. The
  dialog then says so.
- **Dialogs close when their question is gone.** "Cancel this render?" closes by itself, sending nothing,
  when its job ends or its cancel is requested elsewhere. "Render anyway?" closes when a queued or running
  job appears for the event, or when the event no longer reads as up to date. Focus moves to the page's
  job status, which says what happened.
- **Focus never drops to `<body>` after a dialog.** When a dialog closes after its opener is gone, focus
  moves to the job status. This covers a confirmed Render anyway and a dialog that closed by itself.
- **A running job reads at most 99%, bar included.** Only "Rendered" says a render is done.
- **The render card keeps its height.** The meter's line is reserved from the first active state, so
  nothing shifts when the first percentage arrives.
- **The separator never dangles.** On the event page the "·" sits in the gap between an active job's words
  and its time, and it is clipped away when the time wraps to a new line. In list rows the time after an
  active job's words always takes its own line, with no separator.
- **Row answers are announced, and toasts name events by title and date.**
  - A row's Render that creates a job raises a polite notification: 'Render queued: “<title>” · <date>'.
  - A row's Render that finds a job already queued or running also raises one.
  - Every job toast and row-answer toast names the event by its title, as the screens do, followed by its
    date, since titles repeat: 'Rendered “Midsommar” · 2024-06-21'. An event with no title is named by its
    folder name.
  - The output-collision toast keeps folder names. The events it names share their title by definition,
    so only the folder tells them apart.
- **Docs.** `web/README.md` gets two sentences: Cancel asks while the connection is down, and toasts name
  events by title and date and confirm a row's Render.

## Non-goals

- **The "Saved" toast after an edit** (`web/src/edit/EventEditor.tsx`). It is owned by
  `edit-mode-polish`, so this change does not name the event there.
- **Announcing a row's later states** (running, cancelling). The slice-E decision stands: list rows have
  no live region, so a busy list stays quiet. The operator's own action is confirmed, and the ending is
  announced by the terminal toast.
- **The list's job-cell layout and alignment** (`event-list-polish`), the event page's header grouping
  (`event-page-polish`), the shared date/time formatter (`event-list-polish`), and toast focus, live-region
  atomicity, dialog descriptions and the toast inset (`ui-a11y-polish`).
- **A visible ring on the script-focused job status.** The design system gives the page's h1 and the
  status element no ring when script focuses them (`base.css`, `jobs.css`). The supervisor kept that
  convention.
- **The list rows' compact meter height.** Only the event page's render card reserves the meter's line. The
  rows' layout is `event-list-polish`'s.
- **Refresh re-opening the socket.** Reconnects keep their backoff, and Refresh reads only the screen's
  own content.
- **Detecting a silently dead socket** (a keepalive on the client), and **toasts raised while a modal
  dialog makes the page inert.** Neither is in this round's brief.
- **Any change to the worker's two writes** (progress 1.0, then done) or to any service answer. This is a
  client-side change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`, MODIFIED. The changes are to slice E's own requirements, re-based on the current
  `openspec/specs/web-app/spec.md` text:
  - `Requirement: An event's page schedules its render`: Render anyway's dialog closes when its question
    is gone, and focus goes to the job status, never to `<body>`.
  - `Requirement: A render's progress is shown live`: while the connection is not live, the copy that is
    further along wins; a running job reads at most 99%; the page's progress indicator keeps one height;
    the estimate is shown only beside the progress it was computed from; and notifications name the event
    by its title and date.
  - `Requirement: A queued or running render can be cancelled`: Cancel asks while the connection is not
    live, and the dialog closes by itself when its job ends.
  - `Requirement: The event list shows live job state and offers a render`: a row's enqueue answers
    "created" and "already active" raise a notification, and row notifications name the event by title and
    date, except the output-collision one.

## Impact

- **Dependencies (gates):** none. The change builds on `main` at `bca64f2`, where slice E and every v1
  slice are archived. It runs in parallel with `edit-mode-polish`, `event-list-polish`,
  `event-page-polish`, `ui-a11y-polish` and `serve-clean-exit`. None of them is a gate. Before archiving,
  each MODIFIED block is re-based on the then-current spec text (task 1.1).
- **Packages:** `web/` only.
  - Owned files: `src/jobs/useJob.ts`, `store.ts`, `RenderControl.tsx`, `LiveJobCell.tsx`,
    `JobProgress.tsx`, `labels.ts` and `jobs.css`, plus two sentences in `web/README.md`.
  - `src/api/jobs.ts` needs no change.
  - Call-site edits in other changes' files, two lines each:
    - `src/events/EventList.tsx` (`event-list-polish`): `title={event.title}` and `date={event.date}` on
      `<LiveJobCell>`.
    - `src/events/EventDetail.tsx` (`event-page-polish`): the same two props on `<RenderControl>`.
    - Only if `event-list-polish`'s separator stop-gap is on `main` when this change's PR branch is built:
      that one rule is deleted from `src/events/list.css`.
- **CLI vs API (Principle V):** neither is touched.
- **Rendered output:** unchanged, and **no `RENDER_GRAPH_VERSION` bump**. The fingerprint inputs are
  unchanged.
- **Schemas:** no change to `reel.yaml`, `config.yaml`, the API, `web/openapi.json` or `schema.d.ts`. **No
  Alembic migration**, and no rescan.
- **Dependencies (Principle VII):** none added.
- **Size (Principle VIII):** one package, one capability delta (four MODIFIED requirements of slice E),
  and 10 tasks. Every fix is local to the jobs slice.
