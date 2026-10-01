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
  "The connection is down, so this render may have started." before the existing sentence.
- The confirm button cancels `asking.jobId`, the job the question named, and never a job shown later.
- A queued job while live still cancels at once, as the spec's scenario requires.

**Rationale**: One condition closes the spec gap without depending on a Refresh. The copy stays true: it
is captured when the question opens.

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

**Rationale**: The dialog's own opener is gone in every one of these cases: Cancel is not rendered once the
job is not cancellable, and Render anyway is not rendered once a job is active or the event needs a
render. The focus rule below therefore always applies, and focus lands on the status that states the new
fact. The status is a `role="status"` region whose words just changed, and it is focused, so the new state
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
under a browser that moves focus to `<body>` at once.

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
  way to the first progress, a second shift on every render. (The card already grows by 11.5 px at that
  moment, on `main` as with this change, because the meter's figures line appears: "Adjacent findings not
  taken".)
- **B: no glyph, a 12px gap.** This works, but on one line "Starting…  started 11:44 PM" loses the clause
  break the dot gives. Terminal states have no words, so they never needed one.
- **A3: the dot hangs in the gap, and the job state clips its inline start.** On one line the words and
  the time are 12px apart with the dot centred. A wrapped time starts at the job state's left edge, so its
  dot lies outside the box and is not drawn. `scrollWidth` equals `innerWidth` everywhere.

**Decision**: Use A3 for the page. In list rows, the time after an active job's words always takes its own
line, with no dot. A running row with progress has no words, so it keeps its pill and time together where
they fit, as today; the list's row layout is `event-list-polish`'s. The rules replace `jobs.css` 142-152:

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

**Decision**: Use the toast.

- `enqueued` raises `toast.info('Render of “<name>” queued', Open)`.
- `active` raises `toast.info('A render of “<name>” is already queued or running', Open)`.
- Later states of the row (running, cancelling) stay unannounced. The terminal toast of a tracked job
  announces the end.

**Rationale**: It is the channel the row already uses for its answers, and it confirms the operator's own
action (WCAG 4.1.3) without making the list chatty. Sighted operators also get the event's link, which is
useful when the row is far down a long list. The wording matches the terminal toasts ("Render of “…”
failed / canceled").

### Toasts name the event by its title

**Context**: The store knows only `event_dir`. Titles live in the screens' reads.

**Decision**:

- `jobs/labels.ts` gains `eventName(eventId, title) = title ?? folderName(eventId)`, the screens' own
  rule.
- `store.ts`'s `tracked` becomes a `Map<jobId, name>`, and `track(jobId, name)` records it. Every `track`
  call site has the name. `onEnded` announces `tracked.get(job.id)`, and a job with no entry raises
  nothing, as before. `store.ts` no longer imports `folderName`.
- `RenderControl` and `LiveJobCell` gain a **required** prop `title: string | null | undefined`, so tsc
  fails until both call sites pass it. Each call site passes `title={event.title}`: one line each in
  `EventDetail.tsx` and `EventList.tsx`.
- `tellRowAnswer` names the pressed event by title in `enqueued`, `active`, `fresh`, the 404, the scan
  failure and the not-queued answers.
- The **output-collision** toast keeps folder names for the pressed event and for the claimants. A
  collision exists only when date, title and location match, so the titles are identical and only the
  folders tell the events apart. The page's collision alert links the folder names too.
- The row's Render keeps its accessible name "Render <folder>", as the spec requires.

**Rationale**: Every toast now says what the screens say. The folder's " - " no longer wraps to the start
of a toast line in the common case. The one place where folder names are the only distinction keeps them.

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
  `labels.ts` and `jobs.css`
- two sentences of `web/README.md`
- one line each in other changes' files: `web/src/events/EventList.tsx` (`event-list-polish`,
  `title={event.title}` on `<LiveJobCell>`) and `web/src/events/EventDetail.tsx` (`event-page-polish`,
  `title={event.title}` on `<RenderControl>`)

`web/src/api/jobs.ts` needs no change.

It leaves alone:

- `.live-job` (`jobs.css` 359-367) and the `@container (width < 50rem) .event-table .cell-job` block
  (389-406). `event-list-polish` may need them for its row alignment.
- The render card's markup. `event-page-polish` may regroup the page header around it.
- `JobProgress.tsx`'s time formatting. `event-list-polish` deletes `THIS_YEAR`, `OTHER_YEAR` and
  `formatTime` (28-47), imports its shared formatter and changes the call at 105. This change edits other
  hunks of that file (49-51 and 116-143).
- Every class name another change selects on. `event-list-polish`'s `list.css` reads `.live-job`,
  `.job-progress`, `.job-when`, `.job-words` and `.row-blocked`. `event-page-polish`'s `detail.css` reads
  `.render-card` with `[data-active]`, `.render-none` and `.render-blocked`. All of them stay, on the same
  elements.

Coordination with the other changes:

- `ui-a11y-polish` gives `Dialog` a required `description: ReactNode` and moves each dialog's `<p>` into
  it (its design, "Files and parallel changes"). The cancel dialog's text stays one piece of content: the
  conditional lead sentence and the existing sentence. It is a `<p>` if this change lands first, and the
  `description` if `ui-a11y-polish` does. Whichever lands second keeps both sides.
- Toast rendering and focus are `ui-a11y-polish`'s. This change only calls `toast.info` and `toast.error`.
- `event-list-polish` puts every list time on its own line at table widths (`.live-job .job-when {
  flex-basis: 100% }`), which agrees with this change's list rule. Its `.live-job .job-words::after {
  content: none }` targets the separator this change removes, so once both land that rule matches nothing.
  Whichever lands second may drop it; leaving it is harmless.
- Where another change lands first, the gate task keeps its edits and re-applies this change's edits
  around them.

### Adjacent findings not taken

- **The render card grows when the first progress arrives.** At 1280 px the card goes from 78 to 89.5 px
  (at 390 px, from 106 to 117.7) when "Starting…" gives way to "40%", because `.job-figures` appears beside the
  bar and is taller than it. This was measured on `main` and with this change alike (`review/spike.py`
  `spike_h`). It is not in this round's brief, and this change neither adds to it nor fixes it.
- **A focus ring on `.render-status`** (a11y minor). The status matches `:focus-visible` after a keyboard
  action and shows no outline. That was confirmed in `shots/H-status-focused-1280.png`. The design system
  deliberately draws no ring on script-focused non-controls (the h1 in `base.css:78-85`, the status in
  `jobs.css:322-325`). Changing that belongs to the design system, not this change. This change hands
  focus there in two more cases, so the question is recorded under Open Questions.
- **A toast raised while a modal is open is not perceived** (integration minor). This is not in this
  round's brief. It is mitigated here for the cancel dialog: the dialog now closes when its job ends, and
  focus goes to the status, whose words say the job ended.

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
  from a never-started one without `requeue_count`, which `JobSummaryOut` lacks.
- **[A silently dead socket]** A half-open socket stays `live`, so the store keeps winning → this is
  unchanged from today and out of scope (proposal, Non-goals).
- **[A second job for the event]** The dialog-closing rule compares the shown job's id with the question's
  → a cancel question about job J closes when job K is shown instead, rather than cancelling K.
- **[Toast noise on the list]** Each row's Render now adds a 5 s info toast → at most three toasts are held
  and successes dismiss themselves. The toast carries the event's link, which is useful far down the list.
- **[Two events with one title]** A title-named toast can fit two events (both Midsommar events, the
  Kalas pair), where the folder name it replaces could not. → The terminal toasts and the row's queued,
  already-active, up-to-date and collision toasts carry an "Open" link to their own event's page. The Kalas
  pair claim one movie file, so the service refuses either one's enqueue, forced or not
  (`api/routes/jobs.py`), and the collision toast keeps folder names. The Midsommar pair stays ambiguous
  in the toast's words; this is recorded under Open Questions.
- **[Merge conflicts with parallel polish changes]** → The ownership split above keeps every hunk in
  separate blocks. The gate task checks `git diff bca64f2 main -- web/src/jobs` before starting.
- **[`overflow-x: clip` on `.job-state`]** This could clip a future focusable child → a job state holds
  none today. The comment on the rule says why the clip is safe, so a later change that adds a control
  there sees the constraint.

## Migration Plan

Client only: build and serve as before. There is no data or schema step, and a rollback is a revert of the
web change.

## Open Questions

- Should a toast tell apart two events that share a title? This change names events by title, as the
  screens do. In the dev library `2023-06-23 - Midsommar - Dalarna` and `2024-06-21 - Midsommar - Dalarna`
  are both "Midsommar", and `2024-07-14 - Kalas` and `2024-07-14 - kalas` are both "Kalas". A toast such as
  'Rendered “Midsommar”' does not say which, while the folder name it replaces did ("Risks"). Adding the
  date, or the folder only where `event-list-polish`'s look-alike rule applies, would change the toast
  wording and the spec scenarios here.
- Should the design system give script-focused non-controls (the page h1 and the job status) a visible
  ring after a keyboard action? This change leaves both as they are ("Adjacent findings not taken"). The
  answer changes no spec text or task here.
