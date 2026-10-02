## Context

See `proposal.md` for the motivation. The current shape of `web/src/events/EventDetail.tsx` (re-checked
against `origin/main` after `web-save-shortcut` merged, `1d1ba9d`):

- `state` is `loading | ready { event, fetchedAt, updating? } | failed` (the `LoadState` of
  `events/loadState.ts`, whose pure `readingState` is tested by `npm test`). `load()` reads the event; a
  **quiet** `load` keeps the content and marks it updating, a plain one shows placeholders. The page keeps
  one `inFlight` controller and a `pending` flag (one more quiet read after the one in flight).
- `reread` is what `RenderPanel`'s `onFinished` calls. It is `if (!editingRef.current) load({ quiet: true })`:
  a no-op in Edit mode. `leaveEditMode` (the only way out: Stop editing, a save answer, Reload) sets
  `editingRef.current = false`, `setEditing(false)` and calls a plain `load()`, which is the deferred read.
- The **Edit** button aborts a quiet re-read in flight (`inFlight.current?.abort()`) before it sets
  `editingRef.current = true`. Nothing replaces that read, and `inFlight.current` keeps pointing at the
  aborted controller.
- `RenderPanel` shows `StalenessCell(event.staleness)` and `RenderControl(staleness, latestJob =
  event.latest_job, blockedReason = editing ? 'Save or leave Edit mode to render' : missing-clips reason)`.
  `RenderControl` follows the live job store (`useEventJob`), so the job's own status text moves in Edit
  mode already; it calls `onFinished` once when the job it shows goes from active to finished, and once per
  job id when its read still shows an active job the store knows ended (`readIsBehind`). The verdict
  (`StalenessCell`) and the `latestJob` prop come only from the page's last read: those are what stay stale.
- `EventEditor` copies `event` once (`useState(event)`) and reads `reel.yaml` itself, so it never
  re-initialises from a newer detail; the page's `state.event` is its baseline in name, and the spec says a
  later re-read "never changes the order shown or the draft".

`GET /api/v1/events/{id}` returns the chapters, clips and `missing` along with `staleness` and
`latest_job`; there is no verdict-only route, and adding one would put a second reader of the same scan in
`api/` for a GUI polish item (Principle V, VII).

## Goals / Non-Goals

**Goals:**

- A render that ends while Edit mode is open updates the verdict and the latest job in the render region
  without touching anything the editor depends on.
- The failure to do so is said, never silent.
- A re-read dropped by pressing Edit is not lost.

**Non-Goals:**

- A verdict-only API route, polling, or noticing renders the page never showed (see the proposal).
- Changing `RenderControl`, the job store, `EventEditor`, or the editor's conflict handling.
- Refreshing `missing` or the clip rows: Edit mode's own reason replaces the missing-clips reason, and its
  rows come from the draft.

## Research & Decisions

### Where the refreshed fields live
**Context**: `state.event` is passed to `EventEditor` and read by `Counts`, the facts line and the chapter
views; replacing it would be the "re-read the editor must not see".
**Explored**: (a) replace `state.event` with a merge of the old event and the new `staleness` and
`latest_job`; (b) a separate piece of page state used only by `RenderPanel`; (c) `RenderPanel` keeps its own
state and reads itself.
**Decision**: (b). The `ready` state gains an optional `verdict?: { staleness; latest_job }` and an
optional `verdictUnread?: { cause; detail }` (a failed verdict read's words). `RenderPanel` is given
`verdictOf(state)` (`state.verdict ?? state.event`) for those two fields. The slice's transitions are pure
functions in `loadState.ts` (`withVerdict`, `withVerdictUnread`, `verdictOf`), so `loadState.test.ts` holds
that they change neither `event`, `fetchedAt` nor `updating`, and that only a `ready` state takes them. `state.event`, `fetchedAt` and `updating` are never
written by a verdict read.
**Rationale**: (a) changes the object identity the page and the editor props are built from, so the
"never touches the baseline" guarantee would rest on `EventEditor` copying it once instead of on the page;
(c) moves a read next to the render control that the page must also control (abort on leaving Edit mode).
(b) keeps the guarantee in the page: the only writer of `state.event` stays `load()`. A plain `load()`
(leaving Edit mode, Refresh) builds a new `ready` state without `verdict`, so the override never outlives
the read that replaces it.

### The verdict read: a second, quieter read path
**Context**: the existing quiet `load` marks the page as updating, can set the whole state to `failed`, and
shares `inFlight` and `pending` with Refresh; none of that is acceptable under an editor.
**Decision**: a `refreshVerdict()` beside `load`, with its own `verdictFlight` controller and
`verdictPending` flag:
- calls `fetchEvent(eventId, signal)` (the same read as `load`);
- while one is in flight, a further request sets `verdictPending` and one more read runs after it (the
  same "one more, not an endless restart" rule as the quiet re-read);
- on `ok` **and** `editingRef.current` still true **and** not aborted: `setState` merges `verdict:
  { staleness, latest_job }` and clears `verdictUnread`, only when the state is `ready`; the answer's
  chapters, clips, `missing`, title and date are discarded;
- on any other answer (`problem`, `unreachable`, `unpublished`, a thrown error that is not an abort): the
  state is `ready` and only `verdictUnread` is set to the failure's text. It never sets `failed`, never
  touches `updating`.
`reread` becomes `editingRef.current ? refreshVerdict() : load({ quiet: true })`. `leaveEditMode` aborts
`verdictFlight`, clears `verdictPending` and then calls its plain `load()` as today; the unmount cleanup
aborts it too.
**Rationale**: the same read, a different, narrower consumer. An answer that arrives after Edit mode ended is
dropped, because the read leaving Edit mode is newer and replaces everything.
**Alternatives**: waiting for `inFlight` to be free and reusing `load` with a flag. Rejected: it would
couple Refresh's abort rules to a read that must survive them (Refresh in Edit mode is `leaveEditMode`
anyway) and put "do not write `event`" behind a flag inside `load`.

### Edit pressed with a re-read on its way
**Context**: render ends, `reread` starts a quiet read, the operator presses Edit within the read's
latency. Today the button aborts it and the page shows the old verdict in Edit mode; with this change that
would be the same bug in a narrower window, because `onFinished` has already fired and will not fire again.
**Decision**: the Edit button records `inFlight.current !== null || pending.current` before it aborts,
sets `inFlight.current = null` and `pending.current = false` for the aborted read, and, when a read was on
its way, calls `refreshVerdict()` after `editingRef.current` is set. (Clearing `inFlight` also removes a
latent stale controller that would make the next quiet `load` park itself as `pending`.)
**Rationale**: the aborted read was the page's only record that a finished job needed a read; the narrower
read honours it.

### A failed verdict read is said, in the region
**Context**: Principle I. Keeping the old verdict silently is the bug again; replacing the page would
destroy the draft.
**Decision**: `RenderPanel` shows an `Alert` (`tone="warn"`, `role="status"`) under the render control:
"The render verdict may be out of date" with the failure's detail and "Stop editing to read the event
again." It uses the page's existing failure words where one exists (`describeProblem`, `unansweredFailure`)
for the detail. A later successful verdict read removes it; leaving Edit mode does (new `ready` state).
It is a status, not an alert: the operator is typing, and the render status already announces the job's end.
**Rationale**: smallest honest signal; no retry button (Stop editing is the retry, and the unsaved-changes
dialog already guards it).

### Where "Read <time>" stays
`fetchedAt` is the clips' read time and stays so; the verdict may be newer than it. Showing two times in the
header is more than this fix needs; the render region's own job text carries its own dates (existing
"A shown job is dated by the time that matches its state").

### Failure, idempotency, and what is not written
- Nothing is written to disk or the service: the only request is the existing `GET`.
- Repeated triggers: `RenderControl` calls `onFinished` once per ended job (and once per job id when behind),
  and `refreshVerdict` allows one read in flight plus one pending; a re-run, a forced render or a worker
  restart simply produce another job end, hence another idempotent read.
- If the verdict read itself still shows an active job the store knows ended (`readIsBehind`),
  `RenderControl` calls `onFinished` again once for that job id, which reads again; `behindFor` bounds it.
- A vanished event (404) or a failing scan (502/503) during a verdict read is "could not read again": the
  note, not the page's failure screen; the editor's own save and conflict handling say what happened to the
  event.

## Risks / Trade-offs

- **The page shows two read times' worth of data** (clips at `fetchedAt`, verdict newer) → the verdict is
  the only part the operator cannot see change otherwise, and the editor already tells the operator when
  `reel.yaml` changed on disk; acceptable and stated in the spec scenario.
- **`StalenessCell` reasons can name clips or fields the editor's draft has changed** → they describe the
  saved event on disk, which is what a render uses; the region already says Render needs a save first.
- **A second consumer of `EventDetail` in the page** → one extra `ready` field pair, no new endpoint; the
  generated types stay untouched.
- **The page's wiring is not unit-testable** (no component runner) → the pure slice is tested with
  `npm test` (task 1.1); the wiring is checked in a real browser (task 2.1), with the request routes
  controlled where no real render is needed.

## Open Questions

None that change the specs or the tasks.
