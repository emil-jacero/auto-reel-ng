## Context

See proposal.md, Why. This design assumes the three gates are archived on `main`. Task 1.1 checks that.
What `web/` looks like then, and what this change reads from the service:

- **Shell and primitives (C1):**
  - `src/shell/AppShell.tsx` renders a header containing `<div className="shell-status">`, an empty slot for
    this change's indicator. `src/ui/` has `Icon`, `Dialog`, `toast` with `ToastRegion`, and the `btn` and
    `pill` classes (`data-tone`).
  - `src/events/changes.ts` exports `markEventsChanged()`, `currentEventsVersion()` and `useEventsVersion()`.
    The list re-reads, with placeholders, when it is shown with a newer version than its last read, both
    while shown and when shown again. The event page does not listen to the version.
  - `web-app` gains C1's "A read in progress is shown as a placeholder and announced". This change
    MODIFIES it: it scopes it to a screen's read of its own content and adds the in-place exception.
  - `Dialog` takes `initialFocus?: RefObject<HTMLElement | null>`, focused right after `showModal()`; without it
    the first focusable child gets focus. React's `autoFocus` is not used.
  - Busy controls: the control just pressed gets `aria-disabled="true"` + `aria-busy="true"` and ignores
    clicks while its request is in flight; it never gets `disabled`, which drops focus to `<body>`. `.btn`
    styles both attributes.
  - Motion: every `animation` is declared inside `@media (prefers-reduced-motion: no-preference)`. Loop
    durations are literal (for example `1.2s`); the `--dur-*` tokens are for transitions only.
  - CSS layers are declared once in `src/styles/index.css`.
- **Screens after C1** (line numbers from `main` at 541c44c; C1 restyles them, but the structure stays):
  - `EventList.tsx` holds a `LoadState` of `loading | ready | failed`. `load()` aborts the previous read
    and sets `loading`, which replaces the list (`:129-162`). Each row's job cell is a `<td>` holding
    `<JobCell job={latest_job}>` (`:60-62`); C1 gives that `<td>` `data-label="Last job"` only when the event
    has a job.
  - `EventDetail.tsx` follows the same pattern (`:66-95`). C1's rebuilt header holds the verdict and
    latest-job pills, the counts, the `LoadStatus` region (`<p role="status">`, rendered in every state,
    empty when no read runs) and Refresh.
  - `JobCell` shows text only: the status label, `N%` while running, and the created time
    (`common.tsx:35-47`).
- **`event-edit-screen` (C4), built in parallel:** it adds an in-page Edit mode to `EventDetail`. Its
  `load()` never touches `editing`: every Edit-mode exit (save, Stop editing, Reload latest, Read again,
  Refresh) sets `editing` to false and then calls `load()`. The editor's draft is not reset when the `event`
  prop changes identity.
- **Jobs API** (`auto_reel_ng/api/routes/jobs.py`; published by C2 and C3):
  - **`POST /api/v1/jobs`** takes `EnqueueRequest{event_id, device='auto', force=false}` (`schemas.py`
    `EnqueueRequest`) and answers:
    - 201 `JobOut`
    - 200 `FreshResult{event_id, status:'fresh', fingerprint, manifest}` (`:65-77`)
    - 404 `ProblemOut` with `event_id`
    - 409 `ProblemOut` with `conflict: EnqueueConflict`; `active_job` carries `job_id`, and
      `output_collision` carries `claimed_by: string[]`. C3 runs the collision check first, so a colliding
      event is refused even when it is fresh or has an active job, and `force` does not override it.
    - 502 `ProblemOut`: the project walk behind the collision check failed (C3), the same scan-failure
      body the events list uses
    - no 503: the jobs routes publish none (C2 non-goal). A database outage there is an unhandled
      exception, which Starlette answers as a bare `500 Internal Server Error` with no problem body.
    - 422 (FastAPI validation) is not a problem shape; the client never sends a malformed body.
  - **`GET /api/v1/jobs/{id}`** answers `JobOut` or 404 (`job_id`).
  - **`POST /api/v1/jobs/{id}/cancel`** answers `CancelResult{id, status, outcome: CancelOutcome}` or 404.
- **Cancel semantics** (`persistence/job_store.py:219-243`, `scheduler/worker.py:245`, `:273-283`,
  `render/orchestrator.py:256-264`):
  - A queued job is canceled at once.
  - A running job only gets `cancel_requested`. The worker checks between segments, deletes the `.part`,
    and moves the job to `canceled`. The final movie path is never touched.
- **`JobOut`** (`schemas.py`, `class JobOut`) carries, among others, `id`, `status`, `event_dir` (the event
  id; C2 documents this), `progress` (a fraction clamped to `[0,1]`, `job_store.py:163-173`),
  `cancel_requested`, `error`, `created_at`, `started_at` and `finished_at`. The worker requeues a running
  job when it restarts (orphan reconcile, D-S5, `worker.py:133-144`) or is stopped gracefully (D-S8,
  `worker.py:211-218`): `progress` goes back to 0, the status back to `queued`, and `cancel_requested` is
  kept (`job_store.py:245-265`).
- **The read side carries `latest_job: JobSummaryOut{id, status, progress, created_at}`** (`schemas.py:57-68`,
  `:98`, `:146`). It has no `error`, no `cancel_requested`, no `started_at` and no `finished_at`.
- **WebSocket** (`auto_reel_ng/api/ws.py`):
  - the first frame is always a `snapshot` of the queued and running jobs (`:66-81`, `:175-183`)
  - deltas are for new jobs and for changes of `status`, `progress` or `cancel_requested` (`:141-149`,
    plus C2's `cancel_requested` trigger)
  - a job leaving the active set is emitted once as its terminal row (`:151-157`). After C2, a job that
    became terminal since the previous tick although no earlier frame carried it (its whole active life
    fell between two polls, such as `2024-10-05 - Trasig` failing at probe) is also emitted once, as its
    terminal row. C3 keeps that project-scoped.
  - a slow consumer is closed normally (`:163-173`)
  - the endpoint never reads from the client (`:194-217`)
  - the hub polls at `poll_interval`, 1 s by default (`settings.py`), only while a subscriber is connected
    (`:66-92`)
  - after C3, it carries only the served project's jobs
- **`vite.config.ts`** already proxies `/api` with `ws: true`.

## Goals / Non-Goals

**Goals:**

- One WebSocket per tab. Its state is readable from any component, and it survives StrictMode double-mounts.
- Every published answer of the three jobs routes maps to a distinct, worded outcome. There are no silent
  branches.
- Nothing shown as current that is not: no stale counts while disconnected, no guessed terminal state, and
  no invented ETA.
- A small footprint in shared files, so C4, built in parallel, merges cleanly.

**Non-Goals:**

- A jobs page, batch render, a device picker, server-side ETA, and a list-level collision flag (see
  proposal.md, Non-goals).
- Closing the socket on tab visibility. It is an optional optimization, and nothing needs it (see Risks).

## Research & Decisions

### The jobs API client

**Context**: The client has only GET readers (`api/events.ts`, `api/event.ts`). They return discriminated
results in which expected failures are values. The jobs routes add POSTs and more answer kinds.

**Explored**:
- the existing reader pattern
- react-patterns.md §2 and §5 (scratchpad research)
- the answers published by C2 and C3

**Decision**: A new `src/api/jobs.ts` holds aliases into the generated schema, never re-declared shapes:
`JobOut`, `JobStatus`, `FreshResult`, `CancelResult`, `CancelOutcome`, `EnqueueConflict`, `WsMessage` and
`WsMessageType`.

```ts
export type EnqueueResult =
  | { kind: 'enqueued'; job: JobOut }                       // 201
  | { kind: 'fresh'; fresh: FreshResult }                   // 200
  | { kind: 'active'; jobId: string; problem: Problem }     // 409 conflict=active_job
  | { kind: 'collision'; claimedBy: string[]; problem: Problem } // 409 conflict=output_collision
  | { kind: 'problem'; problem: Problem }                   // 404 or 502, in the ProblemOut shape
  | { kind: 'unreachable'; message: string }                // no answer, or an unpublished status/shape
export function enqueueJob(eventId: string, force: boolean): Promise<EnqueueResult>

export type JobResult =
  | { kind: 'ok'; job: JobOut } | { kind: 'problem'; problem: Problem } | { kind: 'unreachable'; message: string }
export function fetchJob(jobId: string, signal?: AbortSignal): Promise<JobResult>

export type CancelAnswer =
  | { kind: 'ok'; result: CancelResult } | { kind: 'problem'; problem: Problem } | { kind: 'unreachable'; message: string }
export function cancelJob(jobId: string): Promise<CancelAnswer>

/** ws:// or wss:// + location.host + '/api/v1/ws/jobs' — by path on the serving origin. */
export function jobsSocketUrl(): string
```

- The 409 branch uses a `switch` over `problem.conflict` with an exhaustive `never` default. A new
  `EnqueueConflict` member is then a `tsc` error.
- A 409 without `conflict`, `active_job` without `job_id`, or `output_collision` without `claimed_by` is
  `unreachable`, with a message naming the status. It is never guessed as "active".
- Problem statuses are per route, as in `api/event.ts`: enqueue `{404, 409, 502}`, job read and cancel
  `{404}`. Anything else, including the bare 500 of a database outage, is `unreachable` with the message
  `POST /api/v1/jobs answered 500 Internal Server Error`. No `check === 'database'` branch is written: the
  jobs routes publish no 503 (Principle VII: no code path for an answer the contract does not have).
- `readJson` and `isProblem` are reused from `api/http.ts`. POST bodies are sent as JSON.
- Enqueue and cancel are not aborted on unmount. They are writes, and their answer still updates the store.

**Rationale**:
- It keeps the house pattern: one module knows the URLs and statuses, and callers handle every kind.
- Collisions and "already active" are separate kinds because the UI treats them in opposite ways: attach
  versus refuse (spec: "An event's page schedules its render").

### One shared WebSocket store

**Context**: The list stays mounted while an event page is open (`App.tsx:53-54`), and rows, the page and
the header all show job state. One socket per component would open several connections. `useEffect`-owned
sockets would also be torn down mid-handshake by StrictMode (`main.tsx:11-15`).

**Explored**:
- react-patterns.md §1: a module store with `useSyncExternalStore` and refcounting
- D-8 ("one WebSocket hook holding a `Map<job_id, JobOut>` with reconnect backoff")
- a React context provider, rejected: its lifetime is tied to a tree, it re-renders every consumer, and
  it gains nothing over a module store

**Decision**: `src/jobs/store.ts` is a module-level store read through `useSyncExternalStore`.

```ts
export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting'
export type JobsState = {
  readonly connection: ConnectionStatus
  readonly jobs: ReadonlyMap<string, JobOut>   // by job id
  readonly eta: ReadonlyMap<string, number>    // job id -> ms left, only when shown (see "Progress and ETA")
}
export function subscribe(listener: () => void): () => void   // retain on first listener
export function getState(): JobsState                         // same object until something changes
export function merge(job: JobOut): void                      // POST 201, GET results
export function track(jobId: string): void                    // started or attached in this tab
export function markAnnounced(jobId: string): void            // its end was already told (cancel answer)
export type LoadOptions = {
  force?: boolean        // GET even if this id was requested before
  knownActive?: boolean  // a screen showed it queued/running: a terminal answer is a reconciled end
}
export function load(jobId: string, options?: LoadOptions): void
```

- **`load`** sends `GET /jobs/{id}` and `merge`s the answer. The store keeps the set of ids it has
  requested. Without `force`, `load` of a requested id does nothing, so a component effect can never loop
  on a job that keeps answering 404 or keeps failing. A 404 removes the job from the map and leaves the id
  in the set. An `unreachable` answer leaves the last known copy in place; it is retried only by a later
  forced `load` (the next snapshot's reconciliation, or an operator action). Nothing retries on a timer.

- **Lifecycle:**
  - The first subscriber opens the socket. `retain` cancels any pending close.
  - When the last subscriber leaves, the close is deferred with `setTimeout(…, 0)`. The StrictMode
    mount, cleanup, mount sequence then reuses one socket.
  - `JobsIndicator` lives in the shell, so in practice the socket is open while the app is.
- **Reconnect:**
  - The socket reconnects on every `close` the store did not start itself, including a normal close (the
    hub closes a slow consumer normally), and `error` closes it. The store's own deferred close clears
    `current` first, so the guard below drops its `close` event and nothing reconnects.
  - The delay is full jitter: `random(0, min(30_000, 500 · 2^attempt))`.
  - `attempt` resets only when a **valid** frame arrives on the new socket. A server that accepts and then
    closes at once, or sends garbage, therefore backs off instead of spinning.
  - `window` `online` cancels a pending retry and connects at once, but only when no socket is open or
    connecting, so a tab never holds two.
  - Every handler starts with `if (socket !== current) return`, a stale-socket guard.
- **Frames:**
  - Each frame is parsed and checked for a `type` in `WsMessageType` and a `jobs` array.
  - A malformed frame is a protocol error. It is logged with `console.error` and closes the socket, so the
    reconnect path runs. It is never half-applied.
  - The type is handled with an exhaustive `switch` on `WsMessageType`.
- **`snapshot`:** `connection` becomes `live`, and the store builds a new map:
  1. every job in the snapshot
  2. every job the store knew as **terminal** (terminal states are final, so keeping them loses nothing)
  3. every job the store knew as **active** that the snapshot lacks: it ended during the gap, so it is kept
     as last known, and `load(id, { force: true, knownActive: true })` replaces it with its real terminal
     row. A 404 drops it.
- **`delta`:** each job is merged by id. An unchanged job keeps its object identity, so row selectors see
  no change.
- **Transitions.** A merged job whose previous version was active and whose new version is terminal ends
  in one of two ways:
  - a *live terminal transition*: the new version came in a `delta`, or from a GET the operator's own action
    caused (the cancel answer's forced `load`)
    - `done` calls `markEventsChanged()`
    - if the job is tracked and not announced, a toast: `toast.success('Rendered “<folder>”')`, or
      `toast.error('Render of “<folder>” failed')`, or `toast.info('Render of “<folder>” canceled')`, each
      with an `Open` action to `eventHref(event_dir)`
  - a *reconciled end*: the new version came from a `load` with `knownActive` (snapshot reconciliation, or
    a screen whose read showed the job active). `done` calls `markEventsChanged()`, and **no** toast is
    raised (spec). A `knownActive` load counts even when the store had no earlier copy of the job, so a
    list read that showed a job running which then ended before the socket saw it still marks events
    changed.

  When a merged row (from a `delta`, or from the GET made for a job just attached) is terminal and its id
  was not in the map, there was no active version to end: a `done` row calls `markEventsChanged()` and
  raises no toast. C2's hub sends such a row once for a job whose whole active life fell between two polls
  (for example another client's job found fresh at claim), and an attached job can end before its GET.
- **Announced jobs.** A cancel answered `canceled-queued` or `no-op-terminal` already told the operator how
  the job ended (see "Cancel"), so `RenderControl` calls `markAnnounced(id)` and the job's terminal
  transition raises no second toast. A `flagged-running` answer does not announce: the later "canceled"
  toast says the worker actually stopped.
- **The state object** is replaced only when something changes, so `getSnapshot` is stable (a
  `useSyncExternalStore` requirement).

**Rationale**:
- The snapshot holds only active jobs (`ws.py:175-183`), so "absent" means "no longer active", not
  "unchanged". A job that finished during a disconnect would otherwise show as running forever, or vanish
  and let the row fall back to the older read (Principle I).
- Keeping known terminal jobs means the page keeps showing a failure's `error` text after a reconnect,
  and no row falls back to an older read, without re-reading.
- Side effects (toasts, marks) run in the store's frame and GET handlers, outside React. They fire once per
  change, never twice under StrictMode, and even when no page for that event is mounted.

### Which job an event shows

**Context**: A job reaches the UI from three sources:
- the read's `latest_job` (a `JobSummaryOut`)
- the store's live `JobOut`s
- a `GET /jobs/{id}`

They disagree for a while after every transition.

**Decision**: `src/jobs/useJob.ts`:

```ts
export type ShownJob =
  | { source: 'live'; job: JobOut }                  // from the store
  | { source: 'read'; job: JobSummary }              // latest_job from the last read
export function useEventJob(eventId: string, latest: JobSummary | null | undefined): ShownJob | null
export function useConnection(): { status: ConnectionStatus; rendering: number; queued: number }
```

- The candidates are the store's jobs with `event_dir === eventId`, plus `latest`. The newest by
  `created_at` wins.
- When ids are equal, the more advanced state wins: a terminal status beats an active one, because
  terminal states are final. Otherwise the store's version wins (it is at least as recent as the read).
  This covers the window of up to one hub poll in which a read has already seen a job's end and its delta
  has not arrived yet, and it lets a Refresh correct a store copy that missed an end on a connection that
  died silently (see Risks, the half-open connection).
- The store's per-event lookup comes from a memoized index keyed on the `jobs` map's identity. A row
  re-renders only when its own shown job changes (a selector that returns the same object).
- An effect in `useEventJob` asks the store to `load(latest.id, { knownActive: true })` in two cases, so a
  screen never keeps showing the read's active job as current after it has ended:
  - `latest` wins, is `queued` or `running`, and the connection is `live` but the store lacks it
  - the same id is active in the store but terminal in `latest`: the load is also `force`d, so the store
    replaces its stale copy
- The failure text is fetched by the event page only: `RenderControl` calls `load(latest.id)` when the shown
  job is a `failed` read-source job (`JobSummaryOut` has no `error`). List rows never fetch it, so opening
  the list costs no request per failed row.
- `useConnection` counts `running` and `queued` over the store's map.

**Rationale**:
- `JobOut.event_dir` is the event id (`jobs.py:79-81`; C2 makes it contractual), and after C3 the socket
  carries only this project's jobs, so an equality match is exact.
- `JobSummaryOut` lacks `error`, and the spec requires the failure text on the event's page, so one GET
  there is the honest way to get it. A list of a real archive can hold many failed rows; one GET each on
  every list open would be a burst of requests for text a row has no room to show.

### Progress and ETA

**Context**: The service reports only `progress` (0..1), and only when it changes, about once a second. The
estimate has to be computed in the client. The research sketch computed it in `useMemo` with a mutated ref,
which is impure and breaks under StrictMode's double render (react-patterns.md §5).

**Decision**: `src/jobs/eta.ts` is a pure sampler that the store calls from its message handler, never from
render:

```ts
type Sample = { t: number; p: number; rate: number | null; n: number; shown: number | null }
export function nextSample(prev: Sample | undefined, job: JobOut, now: number): Sample | undefined
export function etaMs(s: Sample, job: JobOut): number | null
```

- **Sampling:**
  - A sample is taken only while `status === 'running'`.
  - Any other status, or a `progress` lower than the last one (a requeue), discards the sample.
  - The rate is an EWMA of Δp/Δt with α = 0.3, updated only when `progress` increased.
- **When shown:** only when `progress > 0.05` and `n ≥ 3` samples.
- **Monotonic:** `shown = min(previous shown, (1 - p) / rate)`. It is never increasing (spec). It holds
  while progress stalls.
- **Format:** "less than a minute left", "about N min left", or "about H h M min left". Always "about", and
  never seconds.

`src/jobs/JobProgress.tsx` renders one job (`ShownJob`), `compact` in list rows:

| State | Bar | Words (status element) |
|---|---|---|
| queued | `<progress>` without `value` (indeterminate) | "Waiting for a worker" |
| running, progress 0 | indeterminate | "Starting…" |
| running | `<progress value={p} max={1}>` + `NN%` | "Rendering", plus the ETA on the page only |
| queued or running + `cancel_requested` | bar kept, muted | "Cancelling…" (a requeue keeps the flag, so a queued job can carry it) |
| done / failed / canceled | none | `JOB_STATUS_LABEL` + a time. Failed adds, on the page only, the `error` text in an Alert once the store holds the `JobOut`; a row shows "Failed" alone. |

- The status word is a C1 `Pill` with `JOB_STATUS_LOOK[status]` (`src/events/tones.ts`), so a status has
  the same tone and icon as everywhere else. `JOB_STATUS_LABEL` and `JOB_STATUS_LOOK` are imported, not
  edited.
- **The time** is what the service reported, labelled for what it is: "finished <time>" from `finished_at`
  when the shown job is a `JobOut` that has one, otherwise "queued <time>" from `created_at` (a
  `JobSummaryOut` has no finish time). It is never presented as a finish time it is not.
- The words sit in one `role="status"` element per page region. The percentage and the ETA are outside it,
  so updates are not announced (spec).
- Rows get no live region, so a busy list stays quiet.
- When the connection is not `live`, a `live`-source job shows "last known" beside its percentage.
- **Motion** (C1's rule). `jobs.css` gives `progress` `appearance: none` with token colors
  (`::-webkit-progress-bar`, `::-webkit-progress-value`, `::-moz-progress-bar`). Outside any media query,
  `progress:indeterminate` is a static striped bar. Its moving-gradient `animation`, and the header
  indicator's `loader` spin, are declared only inside `@media (prefers-reduced-motion: no-preference)`,
  with literal loop durations (`1.2s linear infinite`), never a `--dur-*` token: those are at most a few
  hundred milliseconds and become 0 under reduce, which suits a transition, not a loop. Under reduce
  nothing moves, and no `reduce` override is needed. The bar's state is always also in words.

**Rationale**:
- Native `<progress>` has the right semantics with no ARIA work.
- Sampling in the handler keeps render pure. Non-increasing plus hidden-until-trustworthy is the spec's
  rule, and it avoids the classic "2 min, 5 min, 1 min" jitter.

### The render region on the event page

**Context**: The page must offer Render or Render anyway, follow a job, and handle every enqueue answer.

**Decision**: `src/jobs/RenderControl.tsx`, props
`{ eventId, staleness, latestJob, onFinished: () => void, blockedReason?: string }`. `EventDetail` mounts it
in the header, in place of C1's latest-job pill (the verdict pill stays beside it), and **only in the
`ready` view**: a page whose read failed (404, 502 such as `unusable_metadata`, database, unreachable) has
no verdict to act on, so it offers no Render. States come from `useEventJob` plus local UI state
(`idle | submitting | confirmForce | confirmCancel | notice`):

- **Active job shown** (queued or running): `JobProgress`, plus a **Cancel** button (see "Cancel"), except
  while `cancel_requested` is set: the cancel is already requested, so the button is gone.
- **No active job:**
  - stale: **Render** (`btn btn-primary`, icon `play`)
  - fresh: **Render anyway** (`btn btn-secondary`), which opens a `Dialog`: "Render anyway? The event is
    up to date. The existing movie is replaced when the new render finishes." The actions are Cancel and
    Render anyway. Cancel is the safe action, passed as the Dialog's `initialFocus`.
- **`blockedReason`:** when set, Render and Render anyway are not rendered; the reason is shown in their
  place as muted text in the region's status element. `JobProgress`, Cancel and any notice Alert stay.
  `EventDetail` passes `editing ? 'Save or leave Edit mode to render' : undefined` once C4's Edit mode is
  on `main` (task 7.1): a render reads the saved `reel.yaml`, not the draft, and a render that adopts NEW
  clips rewrites `reel.yaml` under the open editor, which would force a 412 on its next save. List-row
  Render is unaffected: the list has no Edit mode.
- **While a request is in flight** (C1's busy-control rule): the pressed button gets
  `aria-disabled="true"` and `aria-busy="true"` and stays focused; it never gets `disabled`, which would
  drop focus to `<body>`. A ref set synchronously in the click handler is the actual guard, so a second
  click or Enter, in the same frame or later, starts nothing until the answer arrives.
- **Answers:**

| Answer | Page |
|---|---|
| `enqueued` | `merge(job)`, `track(job.id)`; the region now shows the job |
| `fresh` | inline info Alert "Nothing to render — the movie is up to date." + **Render anyway**; `markEventsChanged()` and `onFinished()` (the read was out of date) |
| `active` | `track(jobId)`, `load(jobId)`; no alert: the region shows that job |
| `collision` | error Alert "Another event renders to the same movie file", its `action` node holding one link per `claimedBy` id (`eventHref`, `folderName`) and "Give one of them a distinct title or location in its reel.yaml.", its `detail` the problem `detail` |
| `problem` 404 | error Alert "This event no longer exists." + link to the list; `markEventsChanged()` and `onFinished()` (the page's re-read then shows the not-found failure) |
| `problem` 502 | error Alert "The project could not be scanned, so the render was not queued." + detail (the words the list uses for the same body) |
| `unreachable` | error Alert "The render was not queued." + the message (the status received, or the fetch error). Never `DATABASE_CAUSE`: a bare 500 does not say why. |

- **Focus:** a busy control keeps focus (above). When the focused control is removed after its answer,
  focus moves to the region's status element (`tabIndex={-1}`), so a keyboard user keeps their place. That
  covers Render replaced by the job's progress, Cancel removed once the cancel is requested or the job
  ends, and a Dialog confirmed whose opener no longer exists (C1's `Dialog` returns focus to the opener
  only if it is still connected).
- **`onFinished`:** an effect watches the shown job. When its status goes from active to
  terminal while mounted, it calls `onFinished()` once. A ref holds the previous status, so a StrictMode
  re-run sees no transition. `EventDetail` wires `onFinished` to its `reread()`, which runs
  `load({ quiet: true })`. C1's event page does not listen to `useEventsVersion()` (only the list does, per
  C1's design), so this is the page's only self-started re-read path. A terminal state other than done
  also re-reads, because `latest_job` changed.
- **Edit mode (`event-edit-screen`, built in parallel; the seam).** C4's `load()` never touches `editing`,
  and every Edit-mode exit sets `editing` to false and then calls `load()`. This change keeps that:
  `load({ quiet })` never touches `editing` either. While `editing` is true, `reread()` does not read at
  all: it defers every self-started re-read (a finished render, and the fresh and 404 enqueue answers)
  until Edit mode ends, and the exit's own `load()` is that deferred re-read. Entering Edit mode also aborts
  a quiet re-read already in flight and marks it pending, so it too becomes the exit's `load()`. A quiet
  re-read therefore never runs under an open editor, so its failure path, which replaces the page, can never unmount a dirty
  draft (C4: "Unsaved edits are never discarded silently"). The wiring (`reread()`'s `editing` check and
  `blockedReason`) needs C4's `editing` state, so it is done by the change that archives second: task 7.1
  here, mirrored by C4's own final task, both evaluated only at the pre-archive rebase.

**Rationale**:
- The spec's outcome list maps one-to-one onto `EnqueueResult`.
- Attaching on `active_job` is the rule of the plan: someone already started it, so show it.
- The collision fix text is the CLI's own advice (`cli/commands.py:224-239`, "set a distinct title or
  location in reel.yaml"), so both surfaces say the same thing.

### Cancel

**Context**: Cancel has three outcomes. A running cancel is cooperative and takes until the next segment
boundary (`worker.py:245`, `:273-283`). The hub pushes the `cancel_requested` change as a delta within
about one poll (C2's trigger), so every open screen shows "Cancelling…" without a read.

**Decision**:
- **Cancel button** (`btn btn-danger`, icon `square`), shown while the shown job is queued or running:
  - queued: it sends at once
  - running: a `Dialog` titled "Cancel this render?" says "The partial render is discarded. The existing
    movie, if any, stays as it was." The actions are "Keep rendering" (the safe action: passed as C1's
    `Dialog` `initialFocus`, and what Escape does) and "Cancel render" (danger). No React `autoFocus`: it
    would run while the `<dialog>` is still closed.
- **While the request is in flight**, the pressed Cancel or Cancel render gets `aria-disabled="true"` +
  `aria-busy="true"` and keeps focus, never `disabled`, with the same ref guard as Render. Cancel render
  sits in the Dialog, which stays open until the answer arrives, so focus stays inside it.
- **On `ok`:**
  - `toast.info(CANCEL_OUTCOME_LABEL[result.outcome])`
  - `track(id)`; for `canceled-queued` and `no-op-terminal` also `markAnnounced(id)`, so the job's terminal
    transition does not raise a second toast for the same ending
  - then `load(id, { force: true })`: a GET that merges the fresh `JobOut`, so "Cancelling…" or "Canceled"
    shows at once, without waiting for the next poll, and whether or not the socket is live
- **On 404:** error Alert "This job no longer exists." Other failures are handled as for enqueue: the cancel
  was not confirmed, and the job is shown as the store last knew it.
- **Labels** go in `src/jobs/labels.ts`, owned by this change, so `events/labels.ts` stays untouched for C4:

```ts
export const CANCEL_OUTCOME_LABEL: Record<CancelOutcome, string> = {
  'flagged-running': 'Cancelling — the worker stops at the next segment.',
  'canceled-queued': 'Canceled before it started.',
  'no-op-terminal': 'The job had already finished.',
}
export const CONNECTION_LABEL: Record<ConnectionStatus, string> = {
  live: 'Live', connecting: 'Connecting…', reconnecting: 'Reconnecting…',
}
```

**Rationale**:
- A `Record` over the generated union is the house mechanism for "never render a slug".
- The forced GET is more honest than faking `cancel_requested: true` locally, and it does not depend on the
  socket being live. With C2 the delta would follow within a second anyway; the GET only removes that
  wait.

### The list: live job cell, compact Render, in-place re-read

**Context**: Rows render `JobCell` from the read, inside a `<td>` that C1 labels "Last job" only when the
read had a job. After a render finishes, the list's verdicts are out of date. C1 re-reads the list when it
is shown with a newer events version, but its `load()` replaces the rows with the loading state: that
flashes when the list is on screen, and on Back it drops the rows that App's scroll restore relies on, so
the list loses its place whenever any worker finished a render meanwhile.

**Decision**:
- `src/jobs/LiveJobCell.tsx` renders the whole job **`<td>`**, and replaces the job `<td>` in `EventRow` (one
  element swapped; it keeps C1's `role="cell"` and column class, passed through as props). Rendering the
  `<td>` itself lets the cell's narrow-width label follow the job actually shown: `data-label="Last job"`
  when `useEventJob` returns a job, live or read, and no `data-label` otherwise. A job the connection
  reported after the read is therefore labelled, and a job-less row stays unlabelled (C1's "no job status
  at all"). In the cell, so the table gains no column:
  - `JobProgress compact` over `useEventJob(event.event_id, event.latest_job)`
  - when `staleness.stale` and no active job, a compact `btn btn-secondary` **Render** whose accessible
    name names the event: visible "Render", `aria-label={`Render ${folderName(event.event_id)}`}` (the
    visible word comes first, so label-in-name holds). It has the same busy treatment as the page's
    (`aria-disabled` + `aria-busy`, focus kept, never `disabled`) and the same ref-based guard.
  The row Render handles the enqueue answers as follows:
  - enqueued or active: as on the page. Focus moves from the removed button to the row's event link.
  - fresh: `toast.info('“<folder>” is already up to date', { action: { label: 'Open', href } })` plus
    `markEventsChanged()`
  - collision: `toast.error('“<folder>” shares its movie file with <names>', { action: { label: 'Open', href } })`
  - 404: `toast.error(…)` plus `markEventsChanged()`
  - 502 and `unreachable`: `toast.error` with the same words as the page
  The list never forces a render, and error rows get nothing. A row never fetches a failed job's error text.
- **In-place re-read.** `load` gains `{ quiet?: boolean }`, in `EventList` and in `EventDetail`:
  - quiet, with `ready` content: the content is kept, and the state becomes
    `{ status: 'ready', …, updating: true }`. The content region gets `aria-busy="true"`, and C1's
    `LoadStatus` region in the page header (already rendered in every state) shows "Updating…", so the
    change is announced through a region that already exists.
  - an `ok` answer replaces the content; a failure replaces it with the failure, exactly as today
  - a quiet read while any read is in flight (quiet or not) sets a `pending` flag. One more quiet read runs
    after the current one. Reads are not restarted.
  - a quiet read requested while the screen shows a failure is an ordinary read (placeholders): there is no
    content to keep
  - Refresh and the first read keep today's behavior: they abort any read, clear `pending`, and the loading
    state replaces the content.
  - every read, quiet or not, records `currentEventsVersion()` at its start (C1's `readVersion` ref)
  - C1's version-triggered effect (`if (!hidden && version !== readVersion.current) load()`) calls
    `load({ quiet: true })` instead, both when the version changes while the list is shown and when a
    hidden list is shown again with a newer version. The component and its DOM stay mounted while hidden
    (`App.tsx`), so on Back the rows are still there: App's scroll restore lands on the same rows, and the
    filter is untouched. No `hidden`-transition ref is needed.
  - These are the two changes to C1's "A read in progress is shown as a placeholder and announced", which
    this change MODIFIES: the requirement covers a screen's read of its own content only (a job read, or
    C4's re-read of a document for its `ETag`, shows no placeholders and is outside it), and a re-read
    because events changed, while shown or on return, is in place.

**Rationale**:
- Swapping in place on success, and replacing on failure, keeps the existing rule "a failed read replaces
  the list" intact. It removes only the flash.
- Coalescing instead of abort-and-restart prevents a batch of finishing CLI jobs from restarting a
  whole-library scan forever.

### The header indicator

**Decision**: `src/jobs/JobsIndicator.tsx` is rendered in C1's `.shell-status` slot (one line in
`AppShell.tsx`). It shows a `.pill` with a tone and a text label:
- `live`: `ok` tone, with a static dot drawn in CSS
- `connecting` and `reconnecting`: `idle` and `warn` tones, with the `loader` icon. Its spin is declared
  in `jobs.css` only inside `@media (prefers-reduced-motion: no-preference)`, `1.2s linear infinite` (see
  "Progress and ETA", Motion), so under reduce the icon stands still.

While `live`, it adds `N rendering · M queued`, omitting zero parts, or nothing when both are zero. It is
not a live region; the page regions announce state. It is plain text, not a link: there is no jobs page in
v1. Below 30rem the counts wrap onto their own line inside the slot rather than widening the header, so
the header never scrolls horizontally at 390px.

**Rationale**: Status is never by color alone (C1). Hiding the counts while not live is the spec's "not
current" rule.

### File ownership and shared-file edits

**Decision**: Everything under `src/jobs/**`, plus `src/api/jobs.ts`, is new and owned here. Edits to shared
files are limited to these:
- `AppShell.tsx`: 1 import, and 1 element in the slot
- `EventDetail.tsx`: an import, `RenderControl` in place of C1's latest-job pill, `load({quiet})` with the
  `updating` state in C1's `LoadStatus`, and `reread()`. At the seam (task 7.1, only when C4 is already on
  `main`): the `editing` check in `reread()` and `blockedReason={editing ? … : undefined}`.
- `EventList.tsx`: an import, the job `<td>` swapped for `<LiveJobCell>`, and the `load({quiet})` plus
  `updating` handling

No edit touches `labels.ts`, `tones.ts`, `common.tsx`, `App.tsx`, `route.ts`, `src/ui/**`, `src/styles/**`,
`package.json`, `src/edit/**` or `src/api/reel.ts`; the first two are imported, not edited.
`JobCell` stays in `common.tsx`: C4 or later code may still use it, and removing it is not this change's
business. Styles live in `src/jobs/jobs.css` (`@layer components`), imported once by `JobsIndicator.tsx`, which
the shell always mounts.

**Rationale**: C4 edits the same two screen files, for the Edit toggle and the error-row link. Keeping this
change's footprint to a few named lines keeps the rebase mechanical. The seam in `EventDetail` (deferred
re-read, Render blocked in Edit mode) needs both changes' code, so it is wired once, by whichever change
archives second: that change's final integration task wires it and runs one combined Playwright check
(C5 task 7.1, mirrored in C4).

## Failure behavior and idempotency

- **Writes are explicit.** The client writes only when the operator presses Render, Render anyway (after
  confirming), Cancel, or confirms a cancel. Opening, returning to, or refreshing a screen sends no POST
  (C1: "Reading a screen never changes state").
- **Enqueue is idempotent server-side.** A second enqueue while one is active is a 409 `active_job`, which
  the client treats as "attach". The client also blocks a double click. Render anyway is the GUI's `--force`
  (Principle IV: the one documented bypass), and it is always confirmed.
- **Cancel is idempotent.** Cancelling a finished job is `no-op-terminal`, shown in words.
- **Worker restart mid-render.** The worker requeues the job: a restarted worker requeues its orphans
  (D-S5), and a gracefully stopped one requeues its in-flight job (D-S8). A delta moves it from running back
  to queued with `progress` 0. The client shows "Waiting for a worker" (or "Cancelling…" if the flag was
  set, since a requeue keeps it) and discards the ETA sample. It is not a terminal transition, so there is
  no toast and no re-read.
- **Service restart or network loss.** The socket closes, the indicator shows Reconnecting…, and the counts
  are hidden. On reconnect the snapshot replaces the active set, and jobs that ended in the gap are read.
- **A killed render** leaves no file that looks rendered (`orchestrator.py:256-264`). The GUI never claims
  a render succeeded unless the service reported `done`.
- **Malformed frames** close the socket and reconnect. They are logged and never half-applied.
- **Nothing here changes rendered bytes.** No `RENDER_GRAPH_VERSION` bump, and no schema or migration.

## Risks / Trade-offs

- **[The hub polls the database about once a second while any GUI tab is open]** The indicator keeps a
  subscriber whenever the app is open. → This is D-A4's design, and the poll is two indexed queries. A
  visibility-based close is a possible later optimization (Non-Goals).
- **[A batch of CLI renders triggers many list re-reads]** → Quiet reads coalesce: at most one in flight and
  one pending.
- **[The ETA is rough on short renders]** Dev-library renders take seconds. → It is hidden until past 5%
  with at least 3 samples. It is verified on a synthetic long event (task 6.1).
- **[Toasts only for jobs this tab started or attached]** A render started from another tab or the CLI
  updates rows and pages live but raises no toast here. → This is deliberate: a CLI batch would otherwise
  flood the region. It is stated in the spec.
- **[The jobs routes answer a bare 500 when the database is down]** C2 and C3 publish no 503 on the jobs
  routes; the supervisor named it a follow-up (verify at gate). → The client says the render was not queued
  and shows "answered 500 Internal Server Error". It does not guess "database".
- **[A job whose whole active life fell between two hub polls]** The worker claims on a 2 s poll, and a job
  that fails at probe (`2024-10-05 - Trasig`) or completes as fresh at claim time can start and end between
  two 1 s hub polls. → C2's hub emits such a job once, as its terminal row, and C3 keeps it project-scoped.
  Task 1.1 confirms it; the page that enqueued the job then shows its ending live, and task 6.1 checks it
  on Trasig without any Refresh.
- **[A half-open connection still reads "Live"]** The hub sends nothing while no job changes, and the
  endpoint never reads from the client (`ws.py:194-217`), so a connection that died silently (a suspended
  laptop, a dropped route without an `offline` event) is only noticed when the browser's TCP stack gives up.
  Until then the header says Live. → `online` reconnects cover the common case. A server heartbeat frame
  would close the gap, but it is an API change and out of scope; noted as a follow-up.
- **[An early underestimate sticks]** `min(previous, new)` never lets the estimate grow, so a fast first
  stretch (short clips first) can hold "about 1 min left" while a slow stretch runs. → Accepted: the spec
  forbids a growing estimate, the wording is always "about", and the percentage beside it stays exact.
- **[Terminal jobs stay in memory for the tab's life]** → The store is bounded by the jobs seen in one
  session, which is negligible.
- **[C1's "A read in progress is shown as a placeholder and announced" says every read shows placeholders]**
  Taken literally it is broken by this change's own job reads and by C4's `ETag`-only re-read. → This change
  MODIFIES it (C1's design hands it this spec change): it scopes it to a screen's read of its own content
  (the list, the event, the editor's first document read) and adds the in-place exception for re-reads
  because events changed, while shown or on return. The delta was written against C1's proposed text.
  `openspec validate` reports that archive would refuse it until C1 is archived, which the gate
  guarantees. At archive, the block is re-based on the then-current spec text.
- **[Edit mode and a render on the same page]** A render that finishes while the operator edits would
  re-read the page, and a failed re-read replaces the page, unmounting a dirty editor; and Render next to
  an open editor would render the saved `reel.yaml`, not the draft. → While editing, `EventDetail` defers
  its self-started re-reads until Edit mode ends and passes `blockedReason` to `RenderControl` (design "The
  render region on the event page"). Both need C4's `editing`, so the change that archives second wires
  them (task 7.1 here, mirrored in C4) and runs the combined check.
- **[No automated frontend test]** `tsc` is the gate (web-app spec). → The reducer-like parts (`eta.ts` and
  snapshot reconciliation) are pure functions with exhaustive types. The Playwright pass exercises them
  against a real service and worker.

## Migration Plan

Rebuild `web/dist` with the `web/README.md` container command. `serve` mounts it as before, and nothing
server-side changes. A worker must be running for renders to progress; the GUI shows "Waiting for a worker"
otherwise. Rollback means reverting the `web/` files; no data is touched.

## Open Questions

None blocking. Follow-ups, named and out of scope for this round:
- a published 503 `check: database` on the jobs routes, as the events routes have. Adding it to the route's
  problem statuses and a `DATABASE_CAUSE` branch is then a one-line client change.
- a server heartbeat frame on the jobs WebSocket, so a half-open connection stops reading "Live" (Risks).
