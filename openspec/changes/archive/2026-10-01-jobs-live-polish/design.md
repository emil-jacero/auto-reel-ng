## Context

See proposal.md, "Why". Line numbers refer to `main` at `bca64f2`. The code facts behind the approach:

- **`useJob.ts` `choose(live, latest)`** (43-63) picks the job a screen shows. `live` is the store's
  newest job for the event, and `latest` is the screen's last read (`latest_job`, a `JobSummaryOut`). For
  one and the same id, an ended copy beats an active one. Otherwise the store's copy always wins: "being at
  least as recent as the read". `useEventJob` (72-99) already subscribes to the connection state, but
  `choose` never sees it. `ShownJob` is `{ source: 'live'; job: JobOut } | { source: 'read'; job:
  JobSummary }`. `JobSummaryOut` has only `id`, `status`, `progress`, `created_at`, `started_at` and
  `finished_at`. It lacks `cancel_requested` and `error`.
- **Readers of `source`:**
  - `JobProgress.tsx` `isCancelling` (49-51) and `JobMeter`'s `lastKnown` (122) read `'live'`.
  - `RenderControl.tsx` `cancellable` (331), `failedReadId` (224-225) and the failure alert (412-417) read
    `'live'` or `'read'`.
  - `useEventJob`'s `readWins` (82) reads `'read'`.
- **The estimate** is the store's per-job sample (`store.ts` `commit`, 282-308), which RenderControl reads
  by job id (147-149) and hands to `JobMeter`.
- **`JobMeter`** (116-143): `determinate = running && progress > 0`, `percent = Math.floor(progress *
  100)`, and `<progress value={progress}>`. The worker writes `set_progress(1.0)` and the done transition
  as two writes (`scheduler/worker.py:288-291`), and the hub can publish the state between them.
- **RenderControl's dialogs:**
  - `asking: 'force' | 'cancel' | null` (151).
  - Cancel asks only when `job.status === 'running'` (390-400).
  - The cancel confirmation cancels whatever `job` is shown when it is pressed (472-476).
  - Nothing closes a dialog when its job changes (420-482).
- **The focus hand-off** (164-188): `closeDialog` and `watchRemoval` set `handOff`. After every commit,
  an effect focuses `.render-status` only when `document.activeElement` is `null` or `<body>`.
- **`Dialog.tsx`** (`ui-a11y-polish`'s file): its effect cleanup (58-66) calls `dialog.close()`, then
  focuses the opener only when the opener is still connected.
- **`store.ts`:**
  - `tracked` is a `Set` of job ids (84).
  - `onEnded` (397-425) names the event `folderName(job.event_dir)` (405).
  - `track(jobId)` (451-453) is called from RenderControl (enqueued, active, cancel) and LiveJobCell
    (enqueued, active).
- **`LiveJobCell.tsx` `tellRowAnswer`** (18-56): the `enqueued` and `active` cases only `track` and
  `merge`/`load`. The other cases toast, each naming the event `“${folderName(eventId)}”`. The row's
  Render hands focus to the row's link when it is removed (117-142).
- **The call sites:**
  - `EventList.tsx:83-90` `<LiveJobCell …/>` (`event-list-polish`'s file). The row has `event.title`.
  - `EventDetail.tsx:356-364` `<RenderControl …/>` (`event-page-polish`'s file). The page has
    `event.title`.
  - Both screens name the event `event.title ?? folderName(event_id)` (`EventList.tsx:61`,
    `EventDetail.tsx:195-196`).
- **`jobs.css` 142-152:** `.job-words:has(+ .job-when)::after { content: '·' / '' }`. The dot ends the
  words' box, so it stays at the end of the line when the time wraps. In the list's card layout (below a
  50rem panel, 389-406), `.job-state` is `display: contents`.

### Findings reproduced

Every finding was reproduced again for this change, read-only, against the shared `serve` on :8114 (final
`main`). Every non-GET request was mocked in the browser context or aborted, and the jobs WebSocket was
mocked with `route_web_socket`. The script is `probe.py`, with results in `logs/probe.log` (A–G),
`probe.json` (H only: the last run overwrote it) and `shots/`, all under
`/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/polish-spec/jobs-live-polish/`.

| Finding | Reproduction | Result |
|---|---|---|
| Stale store copy wins | Grillning: Render (mock 201), socket closed 1012 with reconnects refused, read patched to running 0.6, Refresh | card "Queued · Waiting for a worker · … · Cancel · last known"; Cancel sent `POST …/cancel` with no dialog |
| Row Render silent | list: Enter on "Render 2024-06-27 - Grillning med grannar" (mock 201), then running deltas | focus on the "Grillkväll med grannarna" link; the live-region log is `[]` after the enqueue and after both deltas |
| Render anyway focus | 2023 Midsommar: keyboard Render anyway, Tab, Enter (mock 201) | `activeElement` BODY; the next Tab lands on "Skip to content" |
| Dialog outlives its job | Grillning running 30%: Cancel opens the dialog, then a `done` delta | the card reads "Rendered", and `dialog[open]` still asks "Cancel this render?". "Render anyway?" also stays open after a foreign queued delta |
| 100% while running | snapshot running, progress 1.0 | "Rendering … 100%" |
| Dangling "·" | list, queued and cancelling rows at 1280, 768 and 390; page cancelling at 390 and 320 | in every list case the time wraps below "Waiting for a worker ·" / "Cancelling… ·"; the page wraps at 390 and 320 and not at 1280 |
| Toast names the folder | Badutflykt page: Render, running, done | 'Rendered “2024-08-02 - Badutflykt - Varberg”', wrapped to "- Varberg”" at 390, while the h1 reads "Badutflykt" |

**The fixes, spiked.** The review applied this design's code, as written below, to a scratch copy of
`web/` at `bca64f2`. `tsc --noEmit` and `vite build` passed. The build was served over the read-only :8114
by route interception, with the same mocks (`review/spike.py`, `review/logs/`, `review/shots/` in the
scratch directory above). Every finding is fixed:

| Finding | Result with the fix |
|---|---|
| Stale store copy wins | After Refresh in the outage, the card reads "Rendering · started … · Cancel · 60% · last known", with no estimate, and the list row matches. Cancel opens the dialog. Live, a read of 0.6 does not beat a delta of 0.4, and in an outage an older queued read does not either: both show 40%. |
| Cancel while not live | A queued job opens the dialog with the lead sentence and focus on "Keep rendering". Escape sends nothing and returns focus to Cancel, and the confirm sends one POST to the question's id. |
| Row Render silent | The toast stack announces 'Render of “Badutflykt” queued'. Focus is on the "Badutflykt" link, and a later running delta adds no live text. |
| Render anyway focus | With the answer at once and after 600 ms, focus is on `p.render-status` and the next Tab reaches Cancel. |
| Dialog outlives its job | A `done` delta closes "Cancel this render?" with no POST and focus on the status. A foreign queued delta closes "Render anyway?" the same way. With the confirm held in flight, the dialog stays open and busy until the answer, which closes it with focus on the status. |
| 100% while running | "99%", and `progress.value` is 0.99. |
| Dangling "·" | On the page the gap is 12 px on one line at 1280, 768 and 390 ("Starting…"), and a wrapped time starts at the job state's left edge at 320 ("Starting…") and at 390 and 320 ("Cancelling…"). In list rows the time after the words has its own line and its `::before` is `none`. There is no horizontal scroll at any width, in either scheme. |
| Toast names the folder | 'Rendered “Badutflykt”'. |

**Nothing is dropped.** Two parts of the findings' wider text are not handled here:

- The bare **"Saved"** toast (`web/src/edit/EventEditor.tsx:617`) is `edit-mode-polish`'s file.
- A **row's running state** stays unannounced, by the recorded decision (see "Row answers" below).

## Goals / Non-Goals

**Goals:**

- Each of the seven findings is fixed inside `web/src/jobs/`, and nothing in the service changes.
- The fixes keep every existing slice-E behavior that the spec pins: one socket, no polling, toasts only
  for live ends of tracked jobs, busy controls that keep focus, and a quiet list.

**Non-Goals:**

- The proposal's non-goals. Beyond them, this change does not restructure the render card's markup or the
  list's job cell. `event-page-polish` and `event-list-polish` own those layouts (see "File ownership and
  coordination").

## Research & Decisions

### Supervisor decisions (implementation round)

Recorded before implementation. They are binding, and they settle this design's two open questions and
one adjacent finding. The sections below are updated to match.

- **Polish-round context.** The brief is `plan/brief-polish.md`, with its file ownership. Six sibling
  changes run in parallel: `edit-mode-polish` (P1), this change (P2), `event-list-polish` (P3),
  `event-page-polish` (P4), `ui-a11y-polish` (P5) and `serve-clean-exit` (P6). This change stays in its
  owned files. For `web/README.md` hunks, whichever change lands second rebases and keeps every side.
- **Toasts name an event by its title plus its date**, for example 'Rendered “Midsommar” · 2024-06-21',
  because titles repeat. This settles the first open question. Use the shared formatter from
  `event-list-polish` if it has landed, otherwise a local one-liner. (`event-list-polish`'s `format.ts`
  formats instants only, and its design keeps event dates as `YYYY-MM-DD`. So the local one-liner writes
  the date as the screens write it, and stays correct after that change lands. See "Toasts name the event
  by its title and date".)
- **No visible focus ring on script-focused non-controls.** The codebase convention stays. This settles
  the second open question.
- **The requeue-while-the-socket-is-down limitation is accepted** and documented (Risks).
- **Also fix: the render card grows by about 11.5 px when the first progress arrives.** Reserve the line,
  so nothing shifts. This moves the finding out of "Adjacent findings not taken" (see "The render card
  keeps its height").
- **Separator stop-gap.** `event-list-polish` may add `.live-job .job-words::after { content: none }` to
  `list.css` as a stop-gap. If it is on `main` when this change's PR branch is built, this change deletes
  it, because its own rule replaces it. That is a one-line edit in another change's file.

### Supervisor decisions (review round)

Recorded after the implementation report. They are binding, and the sections below are updated to match.

- **The card's residual reflow is accepted** (option (a) of "The render card keeps its height"). Between
  320 and 480 px the card can still shrink by a line, and never grow, when "Starting…" gives way to the
  first percentage. It is documented under Risks.
- **List rows keep their height too.** A row shrank by 4–8 px when its first percentage arrived, because its
  compact meter was not reserved. Reserve its line, so the row does not shrink (see "A list row keeps its
  height").
- **The toast wording is accepted** as built: each event-named toast ends with the name, for example
  'Render failed: “Grillkväll med grannarna” · 2024-06-27' (see "Toasts name the event by its title and
  date").
- **Separator stop-gap, re-checked.** `event-list-polish` had not landed when this change's PR branch was
  built, so `list.css` has no stop-gap to delete.

### The job a screen shows while the connection is down

**Context**: `choose()` keeps the store's copy of an active job over the screen's read of the same job,
unconditionally. While the socket is up, that is right: the hub pushes every change within about a
second. While it is down, the store holds only the last known copy, and a Refresh cannot correct it. The
spec's own rule ("the live state when the connection carries one, and otherwise the latest job the last
read returned") is broken, and Cancel judges a running job to be queued.

**Explored**:

1. **The read always wins while not live.** This regresses whenever the read is older than the store's
   last copy. For example, the list read "queued" before the store heard "running 40%" and the socket
   then dropped. A row re-mounted by the list's filter would also show its old read.
2. **Screens push their reads into the store** (`absorbRead` from `useEventJob`, keyed on the read
   object). One fix then serves every screen. But the client does not know when a read was answered. The
   list's filter re-mounts rows with the same, older read object, and an effect keyed on that object
   cannot tell it from a fresh one. Stamping reads with their arrival time needs `api/events.ts` and
   `api/event.ts` (`event-list-polish`'s files) or new props from both screens.
3. **Order the two copies by the job's own fields,** and only while the connection is not live. Within
   one job, the lifecycle is ordered: queued, then running, then more progress. A requeue ends a run, and
   the next claim sets a later `started_at`. Content-based ordering has no identity problem: an older read
   is simply not further along.
4. **Read the job itself** (`load(id, { force: true })`) whenever a screen's read shows an active job the
   store holds while the connection is not live. The store would then hold a full, current `JobOut`, cancel
   flag included. But the trigger is the same read object as in option 2, so every filter re-mount and
   every row of a Refresh sends one more request per active job during an outage. For what the screens
   show, its answer adds only the cancel flag to the read that caused it. Option 3 needs no request.

**Decision**: Option 3, pure, in `useJob.ts`:

```ts
export type ShownJob =
  | { source: 'live'; job: JobOut } // the store's copy
  | { source: 'refreshed'; job: JobOut } // the store's copy, brought forward by a newer read (connection down)
  | { source: 'read'; job: JobSummary } // the screen's last read

// How far along an active version is: running beyond queued, then a later run (a claim after a
// requeue) beyond an earlier one, then more progress.
function standing(job: JobSummary | JobOut): [number, number, number] {
  return [
    job.status === 'running' ? 1 : 0,
    job.started_at == null ? 0 : Date.parse(job.started_at),
    job.progress,
  ]
}
function isFurther(a: JobSummary | JobOut, b: JobSummary | JobOut): boolean // lexicographic a > b

function choose(live, latest, connectionLive: boolean): ShownJob | null
//  same id: store ended → live; read ended → read (unchanged)
//           both active, !connectionLive, isFurther(latest, live) →
//             { source: 'refreshed', job: { ...live, status, progress, started_at, finished_at from latest } }
//           otherwise → live
//  different ids: unchanged (newer created_at wins)
```

- `useEventJob` passes `connection === 'live'`, and `useMemo` gets `[live, latest, connection]` as its
  dependencies.
- `'refreshed'` keeps every field only the socket carries: `cancel_requested`, so "Cancelling…" and a
  pending cancel survive, and `error` and the worker fields.
- It is a `JobOut`, so the readers of `source` change as follows:
  - `isCancelling` and `lastKnown` read `source !== 'read'`. A refreshed copy is still "last known": the
    socket is down.
  - RenderControl's `cancellable` reads `source !== 'read' && job.cancel_requested`.
  - RenderControl hands `eta` to `JobMeter` only for `source === 'live'`. The estimate is the store's
    sample for the store's progress. Beside a refreshed 80%, a "4 min left" computed at 40% would be a
    number for a state not shown, so the spec gains that sentence.
  - `failedReadId`, the failure alert and `readWins` are unchanged (`'refreshed'` is never ended).
- Nothing is written to the store, so the store's invariants, its toasts and its reconcile-on-snapshot
  are untouched. Once the connection is live again, its snapshot is current and the store's copy wins
  again.

**Rationale**:

- This is the brief's "prefer the more advanced / fresher copy", with the ordering taken from the job's
  own recorded fields (no clock of the client's, no invented state). It stays inside the jobs slice.
- A page opened during an outage, the page's Refresh and the list's Refresh are each fixed on the screen
  that read. Each screen shows the newest copy it knows, which is what the requirement says.
- The one misorder is a requeue during the outage: store "running (run 1)" against a read "queued (after
  requeue)". The store's copy then stays shown until the socket is back, labelled "last known" (Risks).

### Cancel asks whenever the job might be running

**Context**: The spec says "a running job is cancelled only after the operator confirms". While the
socket is down, a job shown as queued (last known, with no Refresh) may have started, and its Cancel skips
the dialog today.

**Decision**: Cancel asks when `job.status === 'running' || connection !== 'live'`. `asking` becomes:

```ts
type Asking = { kind: 'force' } | { kind: 'cancel'; jobId: string; mayHaveStarted: boolean }
```

- `mayHaveStarted` is set when the shown status is not `running`. The dialog's one paragraph then begins
  "The connection is down, so this render may have started." before the existing sentence. (Changed in
  review: it is read at each render, from the connection and the shown status, and `Asking` no longer
  carries it. See "Changed during review", item 6.)
- The confirm button cancels `asking.jobId`, the job the question named, and never a job shown later.
- A queued job while live still cancels at once, as the spec's scenario requires.

**Rationale**: One condition closes the spec gap without depending on a Refresh. The copy stays true: it
is read from the state as it is now, so a reconnect does not leave it saying the connection is down.

### Dialogs close when their question is gone

**Context**: A modal that asks about a finished job, or asks to force a render while a render is already
queued, asks about something that no longer exists. Its confirm then yields only "already finished", or a
409 that attaches.

**Explored**:

- Rewrite the dialog's body ("This render already finished"). That leaves a question open with no
  decision in it.
- Close it. The page's job status already says what happened, and that is where focus goes.

**Decision**: Close it, from RenderControl:

```ts
// Not while its own request is in flight: that answer closes it (enqueue/cancel .then).
const questionGone =
  asking !== null &&
  pressed === null &&
  (asking.kind === 'force'
    ? !(canRender && upToDate) // a queued/running job appeared, Edit/missing-clip block, or no longer up to date
    : !(cancellable && jobId === asking.jobId)) // ended, cancel requested elsewhere, or another job shown
useEffect(() => {
  if (questionGone) closeDialog() // sets handOff; sends nothing
}, [questionGone, closeDialog])
```

**Rationale**: The dialog's own opener is gone in almost every one of these cases: Cancel is not rendered
once the job is not cancellable, and Render anyway is not rendered once a job is active or the event needs
a render. The exception is another job shown in the asked job's place, whose own Cancel can take the
opener's node. (Changed in review: a dialog that closes by itself now always hands focus to the status,
and Cancel is keyed by its job. See "Changed during review", item 4.) Focus lands on the status that
states the new fact. The status is a `role="status"` region whose words just changed, and it is focused, so the new state
is read.

### Focus after a dialog whose opener is gone

**Context**: The earlier refutation instrumented the confirmed "Render anyway?" path
(`r2.py`–`r4.py` in
`/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/verify/final/refute-ra-focus/`). React 19 commits `setAsking(null)` and the store
merge together. In the passive phase, `Dialog`'s cleanup calls `close()`. The opener, the page's Render
anyway, is detached, so no focus is restored. RenderControl's hand-off effect then runs with `handOff`
true, but `document.activeElement` is still the button inside the now-closed `<dialog>`. Chromium moves
focus to `<body>` only at the next frame. The check `focused === null || focused === document.body`
therefore fails, and nobody focuses anything.

**Explored**:

- Close the dialog in the same update as the merge: already the case (the refuter's r4), so this is no
  fix.
- Teach `Dialog.tsx` a fallback target. That is `ui-a11y-polish`'s file, and `Dialog` does not know the
  right target.
- Widen RenderControl's notion of lost focus.

**Decision**:

```ts
/** Focus is gone: nowhere, on <body>, on a removed node, or inside a closed <dialog> (Chromium
 *  moves it to <body> only at the next frame). */
function focusIsLost(): boolean {
  const focused = document.activeElement
  return (
    focused === null ||
    focused === document.body ||
    !focused.isConnected ||
    focused.closest('dialog:not([open])') !== null
  )
}
```

The hand-off effect calls `focusIsLost()` in place of its two comparisons.

The paths that work today stay the same:

- Escape on either dialog returns focus to its connected opener, which is then not lost.
- The cancel confirmation returns focus to the page's Cancel. The Cancel is then removed while focused, and
  `watchRemoval` hands focus to the status.

**Rationale**: The fix is local, it covers the closed-by-itself case with the same code, and it is correct
under a browser that moves focus to `<body>` at once. (Changed in review: `focusIsLost()` alone missed a
self-closed question whose opener node survived. See "Changed during review", item 4.)

### A running job reads at most 99%

**Context**: `Math.floor(1.0 * 100)` is 100. The comment in `JobProgress.tsx:120` promised that a running
job never reads 100%, but floor alone cannot keep that promise. The gap between the worker's two writes
(progress 1.0, then done) is real: verify, rename and the manifest run between them.

**Explored**:

- Cap the words only. Then `<progress value={1}>` still exposes 100% to assistive technology and draws a
  full bar.
- Merge the worker's two writes (`scheduler/`). That is another package, and the moment between them
  still exists.

**Decision**: In `JobMeter`: `const RUNNING_MAX = 0.99`, `const fraction = Math.min(job.progress,
RUNNING_MAX)`. Both `value={fraction}` and `percent = Math.floor(fraction * 100)` use it. Only the done
state says the render finished. The spec states the cap, so it is a rule, not an invented number.

**Rationale**: The bar and the words agree, for eyes and for assistive technology, and the finalize step
really is not done.

### The separator

**Context**: The dot is the words' `::after`, so it always ends the words' line. In the list's narrow cell
the time wraps at every width. On the page it wraps at 390 and 320px, and not at 1280.

**Explored**: Candidates were injected into the live page and list (`sep.py`, shots `sepA-*`, `sepA3-*` and
`sepB-*` in the scratch directory above), at 1280, 768, 390 and 320px, in both schemes:

- **Put the dot at the start of the time.** A wrapped line then starts with it. The original comment
  already rejects that.
- **Always give the time its own line.** The page's status row would change height when "Starting…" gives
  way to the first progress, a second shift on every render. (The card also grew by 11.5 px at that
  moment on `main`, because the meter's figures line appears. That shift is now fixed too: "The render
  card keeps its height".)
- **B: no glyph, a 12px gap.** This works, but on one line "Starting…  started 11:44 PM" loses the clause
  break the dot gives. Terminal states have no words, so they never needed one.
- **A3: the dot hangs in the gap, and the job state clips its inline start.** On one line the words and
  the time are 12px apart with the dot centred. A wrapped time starts at the job state's left edge, so its
  dot lies outside the box and is not drawn. `scrollWidth` equals `innerWidth` everywhere.

**Decision**: Use A3 for the page. In list rows, the time after an active job's words always takes its own
line, with no dot. A running row with progress has no words, so it keeps its pill and time together where
they fit, as today; the list's row layout is `event-list-polish`'s. (Changed in review: every active job's
time in a row now takes its own line, words or not. See "A list row keeps its height".) The rules replace
`jobs.css` 142-152 (changed in review: the clip applies to `.render-status` only, see "Changed during
review", item 2):

```css
.job-state:has(> .job-words + .job-when) {
  column-gap: var(--s-3);
  overflow-x: clip; /* nothing in a job state is focusable: no focus ring is cut */
}

.job-words + .job-when {
  position: relative;

  &::before {
    content: '·';
    content: '·' / '';
    position: absolute;
    inset-inline-end: 100%;
    inline-size: var(--s-3);
    color: var(--fg-subtle);
    text-align: center;
  }
}
```

Inside the existing `.job-progress` block (408-431):

```css
& .job-words + .job-when {
  flex-basis: 100%;

  &::before {
    content: none;
  }
}
```

In the list's card layout, `.job-state` is `display: contents`, so the time is a flex item of
`.cell-job`. `flex-basis: 100%` still gives it its own line there, as the probe at 390 and 768 shows.

The first rule sets the whole job state's column gap, so while an active job shows words, the pill and the
words are also 12 px apart, against 8 px today. A job state without words keeps 8 px. The review's
screenshots (`review/shots/F-*`, `F2-*`) show no crowding at any width.

**Rationale**: The dot never starts or ends a line, by construction rather than by a width guess. This
covers other-year dates, Edit mode's blocked reason in the same status and every locale. The page keeps
its one-line active state at desktop width, so the status row does not shift. A list row with words gets
one predictable shape: pill and words, then time, then bar. `overflow-x: clip` leaves `overflow-y`
visible, and it is within the support floor (Safari 16+).

### The render card keeps its height

**Context**: The supervisor's added fix. On `main`, at 1280 px the card goes from 78 to 89.5 px (at 390 px,
from 106 to 117.7) when "Starting…" gives way to "40%" (`review/spike.py` `spike_h`). The meter is a flex
line of the bar and `.job-figures`. A waiting or starting job has an indeterminate bar and no figures, so
the line is the bar's 8 px. The first percentage adds the figures, whose line is `--text-sm` × `--lh-normal`
(13 px × 1.5 = 19.5 px), and the line grows by 11.5 px.

**Explored**:

- Always render an empty `.job-figures`. An empty flex item has no height, so it reserves nothing.
- Hide the figures with `visibility: hidden` text such as "0%". That is a figure the service did not
  report, kept in the DOM.
- Give the card's meter a minimum block size of the figures' line.

**Decision**: In `jobs.css`, `.render-card .job-meter { min-block-size: calc(var(--text-sm) *
var(--lh-normal)); }`. It uses tokens only, and the bar is centred in the line as before. The list rows'
compact meter was left as it was at first, because the supervisor had named only the card. Task 6.1
measured the rows, and the review then asked for them too (see "A list row keeps its height").

**Rationale**: The line is reserved from the first active state, so queued, starting, running, cancelling
and last-known all have one meter height. The card no longer grows when the first percentage arrives, at
any width. A meter whose figures wrap below the bar can still grow. That happens only when the
percentage, an estimate and "last known" all show at the narrowest widths. (Changed in review: at 320–390
px the percentage and the estimate alone wrapped below the bar, so the card grew a line at the end of
every render longer than a minute. A narrow card now always puts its figures on their own reserved line.
See "Changed during review", item 8.)

**Measured, and accepted by the supervisor as option (a)** (`verify/jobs-live-polish/spike_narrow.py`,
this-year dates):
the status line's own text still reflows when "Starting…" gives way to the percentage, at some widths. The
words go, so the time, or the Cancel button, can move up a line. The card then shrinks; it never grows.

| viewport | card content box | `main`, card px, Starting… → 40% | this change |
|---|---|---|---|
| 1280, 768, 600 | 1118, 673, 518 px | 78 → 89.5 | 89.5 → 89.5 |
| 480 | 408 px | 106.2 → 89.5 | 117.7 → 89.5 |
| 430 | 362 px | 106.2 → 89.5 | 117.7 → 89.5 |
| 390 | 324 px | 106.2 → 117.7 | 117.7 → 117.7 |
| 360, 320 | 294, 254 px | 129.7 → 117.7 | 141.2 → 117.7 |

The `main` column is derived, not measured: on `main` the Starting… meter is 11.5 px shorter, and the 40%
state is the same. It agrees with the review's measurements at 1280 (78 → 89.5) and 390 (106 → 117.7).

Two ways to remove that too were offered, and the supervisor took neither:

- **A narrow-card rule:** below a card width, an active job's time takes its own line (a container query on
  `.render-card`). With 21rem it holds 390, 360 and 320 steady, but not 430 or 480, because there the
  Cancel button wraps instead. Any threshold is a width guess, and dates of another year move it.
- **"Starting…" in the meter's figures slot**, where the percentage then appears, instead of in the status
  words. The status line then reads the same in both states at every width, by construction. But it
  changes `JobState`'s state table for the list rows too, and the status region would no longer announce
  "Starting…" (only "Rendering").

### A list row keeps its height

**Context**: A review decision. Before this fix, measured on this branch with `spike_rows.py` in the
verify directory (Grillkväll, this-year dates), a row shrank by 8 px when the first percentage arrived, at
every width from 1280 to 360 px. At 1280 the row went from 89.2 to 81.2 px, and at 390 from 151.3 to
143.3 px. Two things change at that moment:

- the compact meter gains its figures' line: the 4 px bar becomes an 18 px line (+14 px)
- the words "Starting…" go (−22 px): either their own line, or the line of the time they pushed down

So reserving the meter's line alone makes the shift −22 px, not 0. "Starting…" also takes a line of its
own under the pill wherever the cell is narrow. That happens in the 148 px job column at table widths on
`main`, and in the 206 px column of the card layout at 600 px.

**Explored** (rules injected into the list, at 1280, 1024, 900, 768, 600, 480, 390, 360 and 320 px):

- **Reserve the meter's line only** (`min-block-size`, as on the card). The row shrinks by 22 px at every
  width.
- **Also give every active row's time its own line.** This holds where "Starting…" fits beside the pill
  (768, 480, 390, 360 and 320 px). It still shrinks by 22 px where the words wrap under the pill (1280,
  1024, 900 and 600 px).
- **Also show "Starting…" as the row meter's figure**, where the percentage then appears. The row's status
  words are then the same before and after the first progress: there are none. So its lines are the same
  at every width, by construction. This is option (c) above, which the card did not take because the card's
  status region announces its words. A row has no live region, so a row loses nothing by it.

**Decision**: All three, in the jobs slice only:

- `JobProgress` (the row) passes `startingInMeter` to `JobState` and to `JobMeter`. The state's words then
  omit "Starting…", and the meter shows it as `.job-starting` in its figures, where the percentage then
  appears. `RenderControl` passes nothing, so the card is unchanged, and its status region still announces
  "Starting…".
- In `.job-progress`, the meter reserves its figures' line: `min-block-size: calc(var(--text-xs) *
  var(--lh-normal))`.
- In `.job-progress`, an active job's time always takes its own line:
  `.job-state:is([data-status='queued'], [data-status='running']) > .job-when { flex-basis: 100% }`. This
  replaces the rule for the time after words, and that time's dot stays `none`. A finished job keeps its
  pill and time together where they fit.

**Measured after the fix** (row height in px; queued / Starting… / 40% / cancelling; Grillkväll, this-year
dates):

| viewport | before | after |
|---|---|---|
| 1280, 1024, 900 | 89.2 / 89.2 / 81.2 / 103.2 | 103.2 / 81.2 / 81.2 / 103.2 |
| 768 | 101.3 / 101.3 / 93.3 / 115.3 | 115.3 / 115.3 / 115.3 / 115.3 |
| 600 | 123.3 / 123.3 / 115.3 / 137.3 | 137.3 / 115.3 / 115.3 / 137.3 |
| 480, 390, 360 | 151.3 / 151.3 / 143.3 / 165.3 | 165.3 / 165.3 / 165.3 / 165.3 |
| 320 | 173.3 / 151.3 / 165.3 / 165.3 | 187.3 / 165.3 / 165.3 / 165.3 |

Starting… → 40% keeps the row's height in all 36 cases measured: Grillkväll and Lång Kväll, with this-year
and other-year dates, at the nine widths. `check_separator.py` checks it at eight widths in light, and at
1280 and 390 in dark.

**Rationale**: The first percentage no longer moves a row, at any width. At card widths from 360 to 768 px
a row keeps one height through every active state. That holds wherever an active job's words fit beside
its pill. (Changed in review: the row's bar changed length at each state, because the figures beside it
changed width. The figures now sit in a slot as wide as "Starting…". See "Changed during review",
item 7.)

**Trade-offs**:

- Where "Waiting for a worker" or "Cancelling…" does not fit beside the pill, the row changes by one line
  when the job starts and when a cancel is requested. That is the 148 px table column on `main`, 600 px,
  and the queued words at 320 px. Both are state changes, where the pill changes too, not a progress tick.
  Before this fix, those columns kept their height when the job started and shrank by 8 px at the first
  percentage.
- `event-list-polish` widens the table's job column (29%, about 278 px at 1024 px), where the words fit
  beside the pill. Once it lands, the table widths should hold too. That is expected, not measured, because
  that change is not on `main`.
- An active row is taller than before: by 14 px while it waits or starts (the reserved line), and by up to
  22 px while it runs (the time's own line).

### Row answers are announced

**Context**: The row's `enqueued` and `active` answers raise nothing, while its `fresh`, `collision` and
failure answers raise toasts ("A row's enqueue answer, told by toast", `LiveJobCell.tsx:17`). Focus moves
to the row's link, and no live region changes. The slice-E design gave rows no live region, so that a busy
list stays quiet (`render-progress-screen/design.md:366`).

**Explored**:

- A visually hidden status element per row, filled only after that row's Render. That is N live regions
  on the list, and it contradicts the recorded quiet-list decision.
- One list-level status region. That lives in `EventList.tsx`, `event-list-polish`'s file.
- A polite toast from the answer handler that already toasts every other answer.

**Decision**: Use the toast. (Changed in review: the toast covered the next rows' Render controls, so
`enqueued` and `active` are now said through a visually hidden status region of the jobs slice, with no
toast. See "Changed during review", item 1.)

- `enqueued` raises `toast.info('Render queued: <name>', Open)`.
- `active` raises `toast.info('Render already queued or running: <name>', Open)`.
- `<name>` is the event's name as the next section defines it, for example '“Badutflykt” · 2024-08-02'.
- Later states of the row (running, cancelling) stay unannounced. The terminal toast of a tracked job
  announces the end.

**Rationale**: It is the channel the row already uses for its answers, and it confirms the operator's own
action (WCAG 4.1.3) without making the list chatty. Sighted operators also get the event's link, which is
useful when the row is far down a long list. The wording matches the terminal toasts ("Render failed: …",
"Render canceled: …").

### Toasts name the event by its title and date

**Context**: The store knows only `event_dir`. Titles and dates live in the screens' reads. Titles repeat:
the dev library has two "Midsommar" events (2023 and 2024), and the Kalas pair.

**Decision** (the supervisor's, "Supervisor decisions"):

- `jobs/labels.ts` gains `eventName(eventId, title, date)`. With a title it is the title in quotes, then
  " · " and the date when there is one: '“Midsommar” · 2024-06-21'. With no title it is the folder name in
  quotes, as the screens show it. A folder name already starts with its date in the year-event layout, so
  no date is added to it.
- The date is the event's `YYYY-MM-DD`, as the list and the page write it. `event-list-polish`'s shared
  `format.ts` formats instants only and keeps event dates as they are, so the local rule stays right once
  that change lands.
- A toast's text is a plain string, so the name keeps its own line breaks out of the "” · date" tail. No-break
  spaces sit on both sides of the "·", and a word joiner (U+2060) follows each hyphen of the date. Found in
  the 390 px pass: 'Rendered “Grillkväll med grannarna” ·' ended a line with the dot, and '· 2024-' /
  '09-20' split the date. Chromium breaks after a hyphen even between digits. A word joiner is a
  default-ignorable format character: it is neither drawn nor spoken.
- Every toast that names the event puts the name last, or before a colon, so its "·" never sits inside a
  sentence:
  - the store's live endings: 'Rendered <name>', 'Render failed: <name>' and 'Render canceled: <name>'
  - a row's answers: 'Render queued: <name>', 'Render already queued or running: <name>', 'Already up to
    date: <name>' and 'No longer exists: <name>' (changed in review: the first two are announced, not
    toasted, with the same words)
  - the page's cancel answers (added in review): 'Render canceled before it started: <name>', 'Render
    stopping at the next segment: <name>' and 'Render had already finished: <name>'
  - a row's failures keep their shape '<name>: <sentence> <detail>'
- `store.ts`'s `tracked` becomes a `Map<jobId, name>`, and `track(jobId, name)` records it. Every `track`
  call site has the name. `onEnded` announces `tracked.get(job.id)`, and a job with no entry raises
  nothing, as before. `store.ts` no longer imports `folderName`.
- `RenderControl` and `LiveJobCell` gain two **required** props, `title` and `date` (each `string | null |
  undefined`), so tsc fails until both call sites pass them. Each call site passes `title={event.title}`
  and `date={event.date}`: two lines each in `EventDetail.tsx` and `EventList.tsx`.
- `tellRowAnswer` names the pressed event this way in `enqueued`, `active`, `fresh`, the 404, the scan
  failure and the not-queued answers.
- The **output-collision** toast keeps folder names for the pressed event and for the claimants. A
  collision exists only when date, title and location match, so the titles are identical and only the
  folders tell the events apart. The page's collision alert links the folder names too.
- The row's Render keeps its accessible name "Render <folder>", as the spec requires.

**Rationale**: Every toast now says what the screens say, and the date tells apart events that share a
title. The folder's " - " no longer wraps to the start of a toast line in the common case. The one place
where folder names are the only distinction keeps them.

### MODIFIED, not ADDED

Each fix changes the observable behavior of an existing slice-E requirement. A new requirement cannot
change the rule of an existing one, so each of the four blocks is MODIFIED:

- which copy of a job is shown
- the running percentage and the estimate
- whether Cancel asks, and when a dialog closes
- how a row's answers are told, and how events are named

Each block is copied whole from `openspec/specs/web-app/spec.md` at `bca64f2`, and every earlier sentence
and scenario is kept (`build_delta.py` in the scratch directory above asserts that each edit matches exactly once). The separator
is purely visual, and no requirement describes it.

### File ownership and coordination

This change edits:

- `web/src/jobs/useJob.ts`, `JobProgress.tsx`, `RenderControl.tsx`, `LiveJobCell.tsx`, `store.ts`,
  `labels.ts` and `jobs.css`; in review also `JobsIndicator.tsx` and a new `announce.ts`
- two sentences of `web/README.md`; in review also the jobs slice's line for `announce.ts` in its source
  tree
- two lines each in other changes' files: `web/src/events/EventList.tsx` (`event-list-polish`,
  `title={event.title}` and `date={event.date}` on `<LiveJobCell>`) and `web/src/events/EventDetail.tsx`
  (`event-page-polish`, the same two props on `<RenderControl>`)
- only if `event-list-polish` has landed its stop-gap `.live-job .job-words::after { content: none }` in
  `web/src/events/list.css` when this change's PR branch is built: that one rule is deleted

`web/src/api/jobs.ts` needs no change.

It leaves alone:

- `.live-job` (`jobs.css` 359-367) and the `@container (width < 50rem) .event-table .cell-job` block
  (389-406). `event-list-polish` may need them for its row alignment.
- The render card's markup. `event-page-polish` may regroup the page header around it.
- `JobProgress.tsx`'s time formatting. `event-list-polish` deletes `THIS_YEAR`, `OTHER_YEAR` and
  `formatTime` (28-47), imports its shared formatter and changes the call at 105. This change edits other
  hunks of that file: the state table's comment (10-26), 49-63, `JobState`'s props, 116-143 and
  `JobProgress`.
- Every class name another change selects on. `event-list-polish`'s `list.css` reads `.live-job`,
  `.job-progress`, `.job-when`, `.job-words` and `.row-blocked`. `event-page-polish`'s `detail.css` reads
  `.render-card` with `[data-active]`, `.render-none` and `.render-blocked`. All of them stay, on the same
  elements. A row whose job is starting now shows no `.job-words`, because its "Starting…" is the meter's
  `.job-starting` ("A list row keeps its height"). Its queued and cancelling words keep the class.

Coordination with the other changes:

- `ui-a11y-polish` gives `Dialog` a required `description: ReactNode` and moves each dialog's `<p>` into
  it (its design, "Files and parallel changes"). The cancel dialog's text stays one piece of content: the
  conditional lead sentence and the existing sentence. It is a `<p>` if this change lands first, and the
  `description` if `ui-a11y-polish` does. Whichever lands second keeps both sides.
- Toast rendering and focus are `ui-a11y-polish`'s. This change only calls `toast.info` and `toast.error`.
- `event-list-polish` puts every list time on its own line at table widths (`.live-job .job-when {
  flex-basis: 100% }`), which agrees with this change's list rule. Its `.live-job .job-words::after {
  content: none }` targets the separator this change removes, so once both land that rule matches nothing.
  If it is on `main` when this change's PR branch is built, this change deletes it (supervisor decision).
- Where another change lands first, the gate task keeps its edits and re-applies this change's edits
  around them.

### Adjacent findings not taken

- **The render card grows when the first progress arrives.** Taken after all, by supervisor decision: see
  "The render card keeps its height".
- **A focus ring on `.render-status`** (a11y minor). The status matches `:focus-visible` after a keyboard
  action and shows no outline. That was confirmed in `shots/H-status-focused-1280.png`. The design system
  deliberately draws no ring on script-focused non-controls (the h1 in `base.css:78-85`, the status in
  `jobs.css:322-325`). The supervisor kept that convention ("Supervisor decisions"), so no ring is added,
  although this change hands focus there in two more cases.
- **A toast raised while a modal is open is not perceived** (integration minor). This is not in this
  round's brief. It is mitigated here for the cancel dialog: the dialog now closes when its job ends, and
  focus goes to the status, whose words say the job ended.

### Changed during review

The supervisor's review found two major and six minor defects. It used two review lenses, and a skeptic
re-checked each finding. All eight were fixed in new commits on `pr/jobs-live-polish`. The archived spec
delta and the synced `openspec/specs/web-app/spec.md` were changed to match, as listed at the end. The
checks are scratch Playwright scripts against this branch's serve on :8116 (`verify/jobs-live-polish/`):
`check_rows.py`, `check_dialogs.py`, `check_names.py`, `check_review.py`, and the real-worker
`check_e2e.py`.

1. **A row's own Render raised a toast over the next rows' Render controls (major).** The toast region
   sits over the table's "Last job" column at desktop width and spans the full width on a phone. A Render
   pressed low in the viewport therefore put a toast over the next row's Render. A tap there then hit the
   toast's Open link. Now `enqueued` and `active` say 'Render queued: <name>' and 'Render already queued
   or running: <name>' through a visually hidden, polite status region, `jobs/announce.ts`. The region:
   - is rendered once, by `JobsIndicator`, which the shell always mounts, so it exists before its first
     message
   - puts each message in a new node, so a repeat is said again
   - is cleared after 5 s, so the text does not stay in the header

   The row shows the job at once, so a sighted operator loses only the Open link. The row's other answers
   keep their toasts. **Measured** at 1280×900 (pointer) and 390×844 (touch), with Badutflykt's Render in
   the viewport's bottom band, after pressing Två Kapitel's Render:
   - no toast shows
   - `elementFromPoint` at the centre of Badutflykt's Render returns that button
   - a real click or tap there renders Badutflykt and does not navigate
2. **A row's time was cut under user text spacing (major, WCAG 1.4.12).** `overflow-x: clip` applied to
   every job state with words, list rows included. A row draws no dot to clip. The clip now applies to
   `.render-status` only. **Measured** with the 1.4.12 overrides and other-year dates:
   - in the 1280 and 1024 table, the queued and cancelling rows' times end 14.8 px past their job state,
     unclipped, and hit-test as the time
   - the page keeps its clip, with its time whole, at 1280, 390, 360 and 320 px
3. **A routine row toast could evict an unread error (minor).** Fixed by item 1: the row's own Render
   raises no toast, so three held "Render failed" toasts survive a fourth row's Render. A row's "Already up
   to date" info toast, which `main` already raised, can still evict an error when three errors are held.
   That eviction rule belongs to `ui/toast.ts` (`ui-a11y-polish`), so it is a follow-up.
4. **A cancel question that closed by itself could leave focus on another job's Cancel (minor).** Job J
   was asked about while the connection was down, and the reconnect showed job K for the same event. K's
   Cancel reused J's unkeyed node, so `Dialog` restored focus to it, and `focusIsLost()` was false. The
   next Enter then cancelled K without asking. Two fixes:
   - a question that closes by itself always hands focus to the job status (a `selfClosed` ref that the
     hand-off effect honours)
   - Cancel is keyed by its job, so a focused Cancel whose job gave way is removed and also hands focus
     to the status (the same swap while live, in one delta)

   Render and Render anyway stay unkeyed on purpose: the "fresh" answer turns the pressed Render into
   Render anyway in place. A Render anyway question that closes by itself is covered by the first fix.
5. **The cancel answer's toast did not name the event (minor).** It was the only notification of a
   canceled-queued ending, because it suppresses the store's named ending toast. `CANCEL_OUTCOME_LABEL`
   now holds prefixes, and the toast ends with the name, as the other toasts do:
   - 'Render canceled before it started: “Blandat” · 2024-11-02'
   - 'Render stopping at the next segment: <name>'
   - 'Render had already finished: <name>'
6. **The cancel dialog kept saying "The connection is down…" after a reconnect (minor).** The sentence was
   captured when the question opened. It is now read at each render: `!connectionLive && job.status !==
   'running'`. `Asking` no longer carries `mayHaveStarted`. The dialog stays open, so a confirmation the
   operator is reading does not vanish, and confirming still cancels the job it asked about. Checked
   with the job still queued after the reconnect, and with it now running.
7. **A row's progress bar changed length at every state change (minor).** The bar shares a flex line
   with figures of varying width. A row's figures now sit in `.job-slot`, an inline grid. Its hidden
   `::before` (`content: attr(data-reserve)`, which holds `STARTING`) is stacked under the figures, so the
   slot is at least as wide as "Starting…" from the first active state, and the figures end where
   "Starting…" ends. **Measured:**
   - Grillkväll's bar keeps one length from queued through Starting…, 9%, 40% and cancelling.
   - Every active row's bar has that length too: 84.3 px at 1280 and 1024, 220.1 at 768, 142.8 at 600,
     260.3 at 390 and 190.3 at 320, in light and dark.
   - Row heights are unchanged: `check_separator.py` passes 206/206.

   A queued row's bar is shorter than on `main`: 84 against 148 px at 1280. "last known" can still widen
   the slot during an outage.
8. **At 320–390 px the card grew a line when the estimate appeared (minor).** On one line, the meter
   needs the bar's 8rem flex basis, the 0.75rem gap and the figures. "99% · less than a minute left" is
   181.2 px in Noto Sans (172.8 in Liberation Sans, 160.4 in DejaVu Sans), so the meter needs 20.1rem of
   card content. The card is now a named inline-size container (`render-card`). Below 20.5rem of content,
   the figures always take their own line under the bar. That line is reserved from the first active
   state: `min-block-size` is the bar, the row gap and the figures' line, with `align-content:
   flex-start`, so the bar does not move.

   **Measured**, card height in px for Starting… → 4% (no estimate) → with the estimate:

   | viewport | card content | card px |
   |---|---|---|
   | 320, 340, 360 | 254, 274, 294 px | 153.2 → 129.7 → 129.7 |
   | 390 | 324 px | 129.7 → 129.7 → 129.7 |
   | 430, 480 | 362, 408 px | 117.7 → 89.5 → 89.5 |
   | 768, 1280 | 673, 1118 px | 89.5 → 89.5 → 89.5 |

   The shrink at Starting… → 4% is the accepted option (a). The narrow card is 12 px taller than before in
   every active state.

**Spec**, changed in the archived delta and the synced spec alike:
- The progress requirement keeps the indicator's height when the estimate appears too, with a new
  320 px scenario.
- The cancel requirement:
  - the "may have started" sentence holds only while the connection is down and the job is not shown
    running
  - the dialog also closes when another job shows in its place, and focus goes to the status even when
    a Cancel for another job is shown
  - the queued-cancel scenario's notification names the event
  - two scenarios are added: another job takes the question's place, and the sentence goes after a
    reconnect
- The list requirement:
  - a row's created and already-active answers are told to assistive technology, with no visible
    notification
  - what a row tells assistive technology names the event as its notifications do
  - the confirmed-in-words scenario says no notification is shown over the list

### Rebuilt on main

`event-page-polish` (#15), `serve-clean-exit` (#16), `ui-a11y-polish` (#20) and `event-list-polish` (#21)
merged first. The change was cherry-picked onto that main as `pr/jobs-live-polish-2`, with every commit kept
and none rewritten.

- **One conflict: `EventDetail.tsx`.** #15 moved `RenderControl` into its new `RenderPanel` (the render
  region). Its version of the component is kept, and this change's two props, `title={event.title}` and
  `date={event.date}`, are added to `RenderControl` there. `EventList.tsx`'s two props merged cleanly onto
  #21's row.
- **The separator stop-gap is deleted** (this design, "Supervisor decisions"). #21 landed
  `.event-table .live-job .job-words::after { content: none }` in `list.css`. This change removes the
  `::after` dot it guarded against: the separator is `.job-words + .job-when::before`, which `.live-job`
  turns off in every row. So the stop-gap matched nothing, and a new commit deletes it. `check_separator.py`
  now also asserts that no `.job-words` draws an `::after`, on the page and in every row. It passed
  246/246 at 1280, 768, 390 and 320 px, light and dark.
- **The four MODIFIED requirements** are ones no merged change touched. The synced spec's blocks equal this
  change's, and every other requirement equals main's.
- **The dev library's fixture.** The earlier `check_e2e.py` pass rendered Grillning and Badutflykt for real,
  which left them up to date. The mock-based scripts need them stale, as `make_dev_library` left them:
  Grillning "editorial, output" and Badutflykt "clip_set". Their render manifests were set back to those
  reasons before the scripts ran, and again after this pass's own end-to-end run.

## Failure behavior & idempotency

- **No new request.** A dialog that closes by itself sends nothing. Cancel's extra confirmation adds no
  request, and a confirmed Cancel sends exactly one, as before.
- **The double-press guard is unchanged.** `inFlight` still guards every control, the busy states stay
  `aria-disabled` plus `aria-busy`, and a dialog never closes by itself while its own request is in flight.
- **A refreshed copy is display-only.** Nothing is stored, and nothing raises a toast or marks events
  changed. A read showing the job ended still goes through the existing path: the read wins, and the job
  is read once and absorbed as a reconciled end, with no toast.
- **The 99% cap is display-only.** Stored progress, estimates and the done transition are untouched.
- **Service-side repeats are unchanged.** Rendered output is not affected, and neither are the enqueue
  and cancel semantics. A re-run, a `--force` run (Render anyway) and a worker restart mid-render behave
  as before, apart from the last-known requeue case under Risks.

## Risks / Trade-offs

- **[A requeue during an outage]** The store holds "running (run 1)" and the read says "queued (requeued)",
  so the store's copy stays shown until the socket is back → it is labelled "last known", Cancel still
  asks (not live), and the snapshot on reconnect corrects it. The client cannot tell a requeued-queued job
  from a never-started one without `requeue_count`, which `JobSummaryOut` lacks. The supervisor accepted
  this limitation.
- **[A silently dead socket]** A half-open socket stays `live`, so the store keeps winning → this is
  unchanged from today and out of scope (proposal, Non-goals).
- **[A second job for the event]** The dialog-closing rule compares the shown job's id with the question's
  → a cancel question about job J closes when job K is shown instead, rather than cancelling K, and focus
  goes to the status, never to K's Cancel (changed in review).
- **[Toast noise on the list]** Each row's Render now adds a 5 s info toast → at most three toasts are held
  and successes dismiss themselves. The toast carries the event's link, which is useful far down the list.
  (Changed in review: that toast covered the next rows' Render and could evict an unread error, so a row's
  own Render is now announced without a toast.)
- **[Two events with one title]** A title alone can fit two events (both Midsommar events, the Kalas pair),
  where the folder name it replaces could not. → The toast adds the event's date, so the Midsommar pair
  reads '“Midsommar” · 2023-06-23' and '“Midsommar” · 2024-06-21'. The Kalas pair shares title and date,
  but they claim one movie file, so the service refuses either one's enqueue, forced or not
  (`api/routes/jobs.py`), and the collision toast keeps folder names. The terminal toasts and the row's
  queued, already-active, up-to-date and collision toasts also carry an "Open" link to their own event's
  page.
- **[The card's residual reflow]** Between 320 and 480 px, the card can still shrink by a line when
  "Starting…" gives way to the first percentage. It never grows. → The supervisor accepted this (option (a)).
  The measurements are in "The render card keeps its height".
- **[A row at a job's start or cancel, in a narrow column]** Where an active job's words do not fit beside
  its pill, a row changes by one line when the job starts and when a cancel is requested → these are state
  changes, where the pill changes too. `event-list-polish`'s wider job column should remove them at table
  widths ("A list row keeps its height").
- **[A meter whose figures wrap]** At the narrowest widths, a meter showing a percentage, an estimate and
  "last known" together can wrap its figures below the bar, and the card then grows by a line → this is
  rare, because the estimate shows only for the store's copy, and "last known" only while the connection is
  down. (Changed in review: the percentage and the estimate alone wrapped at 320–390 px; a narrow card now
  reserves that line. Only all three together, offline, can still wrap: 266.5 px in Noto Sans, against a
  254 px card at 320 px.)
- **[Merge conflicts with parallel polish changes]** → The ownership split above keeps every hunk in
  separate blocks. The gate task checks `git diff bca64f2 main -- web/src/jobs` before starting.
- **[`overflow-x: clip` on `.job-state`]** This could clip a future focusable child → a job state holds
  none today. The comment on the rule says why the clip is safe, so a later change that adds a control
  there sees the constraint. (Changed in review: it also cut a row's other-year time under user text
  spacing, so it now applies to the event page's status only.)
- **[A narrow card's reserved line]** Below 20.5rem of card content the meter reserves a second line, so a
  waiting or starting card at 320–390 px is 12 px taller than before → it keeps one height while it runs.
  The threshold is measured for Noto Sans, the widest of the fonts checked. The card is now an inline-size
  container: a later layout must give it a definite width (a grid or flex item that stretches), as
  `event-page-polish`'s `.render-panel` does.
- **[The row's reserved slot]** A queued row's bar is shorter than on `main` (84 against 148 px at 1280),
  so that it keeps one length once the job starts → bars in a list of active rows line up.

## Migration Plan

Client only: build and serve as before. There is no data or schema step, and a rollback is a revert of the
web change.

## Open Questions

None. Both earlier questions were settled by the supervisor ("Supervisor decisions"):

- Two events that share a title are told apart in toasts by adding the date.
- Script-focused non-controls (the page h1 and the job status) keep the convention of no visible ring.
