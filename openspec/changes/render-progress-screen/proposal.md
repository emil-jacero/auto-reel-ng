## Why

GUI v1 (HLD **§6 phase 8**, §4.10, stack **D-8**) promises "schedule a render and watch live progress". This
is slice **E**, the last v1 slice. Legacy auto-reel had no persistence and no GUI (HLD §2, problem 8): a
render could be started and followed only from a terminal. Today the GUI shows only the latest job "as of the last read"
(`JobCell`, `web/src/events/common.tsx:35-47`), and it has no way to start or stop a render. Both screens are
still read-only, and there is no button anywhere except Refresh.

The service side is complete once the three gates land:

- **`web-design-system` (C1)** adds the app shell with its header status slot, `Icon`, `Dialog`, toasts,
  button and pill classes, the `markEventsChanged()` / `useEventsVersion()` signal, and the requirement
  "Reading a screen never changes state". That requirement drops the old "read-only / MUST NOT enqueue /
  SHALL NOT poll" sentences, and it states that a push channel is not polling.
- **`jobs-client-contract` (C2)** publishes every `POST /api/v1/jobs` answer: 201 `JobOut`, 200
  `FreshResult`, 404, and 409 with a typed `job_id`. It also publishes `CancelOutcome` and `WsMessage` with
  `WsMessageType`, documents `JobOut.event_dir` as the event id, and makes the hub push a change of
  `cancel_requested` as a delta. The hub also emits, once, a job that became terminal between two polls
  although no earlier frame carried it, so a render that fails at once (`2024-10-05 - Trasig`) still
  reaches the page that started it.
- **`jobs-project-guards` (C3)** adds the typed 409 `conflict` (`active_job` | `output_collision`) with
  `claimed_by`, and a published 502 when the project walk behind the collision check fails. It also scopes
  the WebSocket, the job list and the job reads to the served project.

The API already does the work. `POST /jobs` gates on staleness (`auto_reel_ng/api/routes/jobs.py:65-77`).
`WS /api/v1/ws/jobs` sends a snapshot of active jobs on connect, then deltas about once a second
(`auto_reel_ng/api/ws.py:66-81`, `:137-161`). A running job is cancelled cooperatively
(`auto_reel_ng/persistence/job_store.py:219-243`). D-8 already says the client is "one WebSocket hook
holding a `Map<job_id, JobOut>` with reconnect backoff", with no library. This change is therefore a pure
`web/` change, like every screen slice before it (Principle VIII precedent,
`event-detail-screen/proposal.md`).

## What Changes

- **One live connection per browser tab.** A module-level store over `WS /api/v1/ws/jobs`:
  - it opens while any part of the app uses it, with a deferred close that is safe under StrictMode
  - it reconnects after any close, with a growing, randomized delay capped near 30 s, and at once when the
    browser comes back online
  - a snapshot replaces the store's active set, and a delta merges into it
  - a job the store knew as active that is missing from a new snapshot ended while the socket was down, so
    the store reads it once with `GET /api/v1/jobs/{id}`
  - the header's status slot shows **Live**, **Connecting…** or **Reconnecting…**, plus "2 rendering ·
    1 queued" only while live
- **The event page schedules a render.** A render region in the page header, in place of C1's latest-job
  pill, offers:
  - **Render** when the event needs a render
  - **Up to date** plus a secondary **Render anyway** when it does not; the forced render is confirmed in
    a dialog that opens on its safe action
  - neither while the page is in Edit mode (slice D, `event-edit-screen`): it says "Save or leave Edit mode
    to render" instead, because a render reads the saved `reel.yaml`, not the draft. Progress and Cancel
    stay.
  A pressed control stays focused and is marked busy (`aria-disabled` + `aria-busy`, never `disabled`)
  until its answer arrives, and a second press sends nothing.
  Every answer to `POST /jobs` is handled:
  - 201: the page follows the new job
  - 200 fresh: the page says there is nothing to render and offers Render anyway
  - 409 `active_job`: the page attaches to that job
  - 409 `output_collision`: an alert names the other events, linked, and says how to fix it (a distinct
    title or location in `reel.yaml`)
  - 404: the event is gone
  - 502: the project could not be scanned, so nothing was queued
  - any unpublished answer (a bare 500 when the database is down) or no answer: the render was not queued,
    with the status received; the cause is never guessed
- **Live progress:**
  - queued: an indeterminate bar, "Waiting for a worker"
  - running: a determinate bar from `progress` (0..1), with a percentage and a client-side time-left
    estimate that is hidden until it is trustworthy and never shown increasing
  - the indeterminate bar and the header's spinner move only when the operating system allows motion
  - cancel requested: "Cancelling…"
  - done: the page and the list re-read in place
  - failed: the job's own `error` text on the event's page (list rows say "Failed" only, so opening the
    list never fetches one job per failed row)
  - canceled: a neutral state
  Toasts come only from live terminal transitions of jobs this tab started or attached to, never from a
  snapshot.
- **Cancel.** A Cancel button while a job is queued or running. A running job asks first in a dialog ("the
  partial render is discarded"). The answer's `CancelOutcome` is put into words through an exhaustive label
  map.
- **The event list goes live:**
  - each row's job cell shows the live status and progress from the same store
  - the job cell's "Last job" label at phone width follows the job actually shown
  - a row that needs a render gets a compact **Render** action, named for its event ("Render <folder>")
  - after a render finishes, a list or page on screen re-reads in place, keeping its content until the
    new read answers, instead of flashing to placeholders. A hidden list's re-read on return is in place
    too, so Back keeps the list's rows and scroll position. An event page in Edit mode defers its re-read
    until Edit mode ends, so an unsaved draft is never replaced.
- **Docs.** `web/README.md` gets the screens, the live connection and the file tree. HLD §4.10 marks slice E
  landed, and its sentence "no further `api/` prerequisite is known for v1" is corrected: slice E needed
  `jobs-client-contract` and `jobs-project-guards`. D-8's live-progress bullet gains the reconnect rule:
  read each job that went missing from a snapshot.
- **The Edit-mode seam.** `event-edit-screen` (C4) is built in parallel and edits the same event page. The
  change that archives second wires the seam in `EventDetail` (deferred re-read, Render blocked in Edit
  mode) and runs one combined browser check; this change's final integration task does it when C4 is
  already on `main` at the pre-archive rebase.

## Non-goals

- **No batch "render all that need rendering"**, no jobs/queue page, and no job history view. These are
  follow-ups.
- **No list-level output-collision flag.** A collision is reported when the operator presses Render, from
  C3's 409. Flagging it in the list before that is a follow-up.
- **No server-side ETA, fps or stage.** The estimate is computed in the client from `progress` samples.
  `JobOut` gains no field.
- **No device picker.** Renders are enqueued with the default `device: "auto"`.
- **No change to editing** (slice D, `event-edit-screen`) and none to the visual system (C1). This change
  uses C1's primitives and adds its own CSS file.
- **No backend change.** Any contract gap found while implementing goes back to C2 or C3. It is not patched
  here.
- **No new dependency.** WebSocket, `useSyncExternalStore` and `<progress>` are platform and React
  built-ins.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: ADDED requirements, per the cross-change ownership rule (C1 already removed the read-only and
  no-poll sentences):
  - `Requirement: The client follows render jobs live over one connection`
  - `Requirement: An event's page schedules its render`
  - `Requirement: A render's progress is shown live`
  - `Requirement: A queued or running render can be cancelled`
  - `Requirement: The event list shows live job state and offers a render`
  - `Requirement: A shown screen re-reads in place when events change`
- `web-app`, MODIFIED: `Requirement: A read in progress is shown as a placeholder and announced`. This
  requirement is added by C1, whose design hands this one spec change to this change
  (`web-design-system/design.md`, "The events-changed signal"); `event-edit-screen` only ADDs requirements,
  so no parallel change modifies it. Two edits: it covers a screen's read of its own content (the list,
  the event, the editor's first document read), so job reads and C4's `ETag`-only re-read are outside it;
  and a re-read because events changed, while the screen is shown or when a hidden list is shown again,
  keeps the content, marked as updating.

## Impact

- **Dependencies (gates):** `web-design-system` (C1), `jobs-client-contract` (C2) and `jobs-project-guards`
  (C3) MUST be archived on `main` before this change is implemented. It uses their shell slot, their
  primitives, their events-changed signal and their generated types. `event-edit-screen` (C4) is not a
  gate: it is built in parallel, and whichever of the two archives second wires their seam (task 7.1).
- **Packages:** `web/` only (code and `web/README.md`), plus `docs/high-level-design.md` §4.10 text (row E
  and the "no further `api/` prerequisite" sentence).
  - New files, all owned by this change:
    - `src/api/jobs.ts`
    - `src/jobs/store.ts`, `src/jobs/eta.ts`, `src/jobs/useJob.ts`, `src/jobs/labels.ts`
    - `src/jobs/RenderControl.tsx`, `src/jobs/JobProgress.tsx`, `src/jobs/LiveJobCell.tsx`,
      `src/jobs/JobsIndicator.tsx`
    - `src/jobs/jobs.css`
  - Small, localized edits to shared files:
    - `src/shell/AppShell.tsx`: the indicator in the `shell-status` slot
    - `src/events/EventDetail.tsx`: the render region in place of C1's latest-job pill, and a quiet
      re-read; at the seam (only if C4 is on `main` first), the Edit-mode deferral and `blockedReason`
    - `src/events/EventList.tsx`: the live job `<td>`, and quiet re-reads after a render and on return
- **File ownership (C4 runs in parallel):** this change owns `web/src/jobs/**`, `web/src/api/jobs.ts`, the
  header status slot's content, the render region of the detail header and the list's job cell. It does not
  touch `web/src/edit/**`, `web/src/api/reel.ts`, `package.json` or `package-lock.json`.
- **CLI vs API (Principle V):** neither is touched. The GUI calls routes that mirror `auto-reel enqueue`,
  `jobs show` and `jobs cancel`.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs are unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, **no Alembic migration**, no rescan.
  `web/openapi.json` and `schema.d.ts` are read, not regenerated.
- **Dependencies (Principle VII):** none added.
- **Size (Principle VIII):** one package, one capability delta, 11 tasks (the docs update is folded into
  the validation task to make room for the conditional seam task). It is the largest screen slice so far.
  If implementation runs long, the split point is after task 4.2: the list integration (5.1 and 5.2)
  becomes its own change, taking the list requirement and the list half of the in-place re-read with it.
