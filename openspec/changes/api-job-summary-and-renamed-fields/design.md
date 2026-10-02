## Context

See proposal.md, "Why". Code facts, from `main` at `6a7fe16`, re-checked at `ad08dbf` (both gates merged):

- **The summary is built in one place.** `api/events_read.py` `_job_summary(job)` passes six fields to
  `JobSummaryOut`; `list_events` (through `_event_summary`) and `get_event` both call it, so the list and the detail
  cannot disagree. `JobStore.latest_by_project` loads whole rows (`expire_on_commit=False`), so
  `cancel_requested` and `requeue_count` are already on the row. `api/serialize.py` `job_to_out` fills the same two
  fields of `JobOut` from the same row type.
- **The schema test pins the summary's shape.** `tests/test_api_openapi.py`
  `test_the_latest_job_publishes_its_fields_as_the_job_detail_does` asserts the property list and
  `required == ["id", "status", "progress", "created_at"]`; this change updates it. Its core check (each summary
  property equals `JobOut`'s) stays and covers the new fields for free.
- **The requeue.** `JobStore.requeue` sets `status=queued`, `worker_id=None`, `started_at=None`, `progress=0` and
  `requeue_count += 1`, and leaves `cancel_requested` in place. The orphan reconcile and a graceful stop go through it.
- **The choice rule moves to a pure module.** `choose`, `standing` and `isFurther` leave `useJob.ts` for
  `jobs/shownJob.ts` (type-only imports, no `react`, no store), so the rule that this change extends runs under
  `npm test` (`shownJob.test.ts`); `useJob.ts` keeps the hooks and imports `choose`.
- **The client's choice.** `useJob.ts` `choose(live, latest, connectionLive)` returns, for the same job id: the
  read when the held copy is active and the read ended; a `refreshed` copy (`{...live, status, progress, started_at,
  finished_at}`) when the connection is not live, both are active and `isFurther(latest, live)`; otherwise the held
  copy. `standing()` ranks running above queued, then a later `started_at`, then progress, so a requeued read
  (queued, no start, progress 0) never beats a running copy. `JobProgress.isCancelling` and
  `RenderControl`'s `cancelRequested` both exclude `source === 'read'`, because a `JobSummary` had no flag.
- **The verdict is built in one place for every API response.** `events_read.staleness_for` ends with
  `StalenessOut(stale=verdict.stale, reasons=list(verdict.reasons))`, and is used by the list, the detail and the
  editorial write's echo. It already holds `output_path` (`settings.output_dir / output_relpath(...)`), whose
  `.name` is the file the next render writes. `routes/jobs.py` also calls `evaluate`, but only for `.stale`.
- **The gate.** `staleness/gate.py` `_renamed_output(manifest, expected)` finds the old movie (a bare recorded name
  that differs from `expected.name`, is a file on disk) and `evaluate` cites `output_renamed` from it, then discards the
  path. `output-renamed-names-files` has landed: `Verdict` carries `renamed_from` and `output_name`, bare file names, both set
  exactly when `output_renamed` is cited and `None` otherwise; `scan` prints them.
- **The client's note.** `events/labels.ts` `REASON_NOTE: Record<StalenessReason, string | null>`;
  `events/common.tsx` `StalenessCell` renders `REASON_NOTE[reason]` as a `.reason-note` span when `explain` is set
  (the event page only; the list never explains). `events/detail.css` styles `.render-panel .reason-note`.
- **Gate overlap.** `api-excluded-clips-read-model` edits `ClipOut`, `EventDetailOut`, `clip_count` and
  `EventDetail.tsx`. This change edits `JobSummaryOut`, `StalenessOut`, `_job_summary`, `staleness_for` and does not
  need `EventDetail.tsx` at all (it passes `event.staleness` to `StalenessCell` whole). The triage listed
  `EventDetail.tsx` and `useJob.ts` for the whole group; only `useJob.ts` is needed. Any merge conflict is textual
  and adjacent, never semantic.

## Goals / Non-Goals

**Goals:**
- A screen that knows a job only from a read can tell a requeue and a cancel request, and the client prefers the read
  where the held copy is provably older.
- Every API verdict names the old and the new movie file when it cites `output_renamed`; the event page says them.

**Non-Goals:**
- No new summary fields beyond the two (`error`, `worker_id`, `device`, `event_dir` stay on `JobOut`).
- No change to the gate's decision, `evaluate`'s reasons or the `output_renamed` rule (that is the gates' area).
- No file names on the list, the render region or the Movie section's own source (the movie route still answers it).
- No requeue label, heartbeat or reaper (supervisor decision: requeued job label stays as is).
- No deletion or pruning of the superseded movie (held for the user).

## Decisions

### D1. Both summary fields are required, without defaults
`cancel_requested: bool` and `requeue_count: int` are declared exactly as in `JobOut`. The earlier
`started_at`/`finished_at` fields were optional because the store may not have stamped them; these two are columns
that are never null (`requeue_count` defaults 0, `cancel_requested` defaults false). Required means a generated client
types them `boolean`/`number`, not `boolean | undefined`, and a future second construction site of `JobSummaryOut`
fails type-check rather than defaulting. *Alternative:* optional with defaults, to keep old clients' fixtures valid.
Rejected: the only client is `web/`, rebuilt with the service, and a default would let a path forget the fields and
report "not requeued".

### D2. The choice rule: a higher `requeue_count` is a newer fact
In the active-active, not-live branch, `choose` advances the held copy when any of these hold:
`latest.requeue_count > live.requeue_count`; `isFurther(latest, live)` (as today); or `latest.cancel_requested &&
!live.cancel_requested`. `requeue_count` only grows, so a higher value is always the newer fact and a lower one an older read that never advances the copy (it could otherwise win on progress against a run that was requeued again), and no client clock
is involved (the same reasoning as `standing()`). The advanced copy is `{...live, status, progress, started_at,
finished_at, cancel_requested, requeue_count}`; the fields a summary lacks (`worker_id`, `error`, `device`...) stay
from the held copy. `worker_id` is left as held although a requeue cleared it: the client shows no worker today
(grep: no use outside the type), and copying `null` would be a guess about a field the read does not carry
(Principle I). The cancel flag is monotone (a requeue leaves it set), so "newly true" is a safe advance and "newly
false" never occurs for the same job. *Alternative:* compare `started_at` instead. Rejected: a requeued job has no
`started_at`, which is what we need to tell. The `live` connection branch is untouched: the connection carries
every change, so a requeue arrives as a delta.

### D3. A read's cancel request is shown
With the flag in the read, the `source !== 'read'` guards in `JobProgress.isCancelling` and
`RenderControl.cancelRequested` are removed (both then read `shown.job.cancel_requested`, which type-checks on the
union). A page opened in a new tab on a job whose cancel is pending then says "Cancelling…" from the first read
instead of offering Cancel until the connection's snapshot arrives. Cancel on an already cancelling job is a
no-op for the store, so the guard was only ever about not having the field. *Alternative:* add the fields and leave
the guards. Rejected: the new field would then affect only the outage merge, and the read would still contradict the
connection.

### D4. The names live on the verdict, filled in the one function that builds it
`StalenessOut` gains `renamed_from: Optional[str] = None` and `output_name: Optional[str] = None`. `staleness_for`
copies `verdict.renamed_from` and `verdict.output_name` (never recomputed in `api/`, so the API cannot disagree with
`scan` or the gate: Principle V); the gate sets both only when `output_renamed` is cited and leaves both `None`
otherwise. The `output_renamed` reason and its names come from the same
`evaluate` call, so they cannot disagree. Both are always present on the wire (the model is not serialized with
`exclude_none`), like `latest_job`'s times: a client reads `null` instead of testing for a missing key. The
exact-equality assertions in the existing tests gain the two keys.
*Alternatives:* (a) a nested `rename: {from, to}` object. Rejected: the triage sketch and the flat style of the
models; two keys cost nothing. (b) `output_name` always set. Rejected: a name with no reason invites showing it where
nothing changed, and "set exactly when `output_renamed`" is testable.

### D5. The note names both files; a null verdict falls back
`REASON_NOTE` stays a `Record` over the union of reasons, so a new reason is still a compile error, but a value is
now `null`, or a function from the `Staleness` verdict to a list of parts, each a string or `{ code: string }`
(`labels.ts` stays JSX-free so `npm test` can run it under Node). For `output_renamed` it returns "The next render
saves the movie as `<output_name>`. The movie `<renamed_from>` stays on disk." and `StalenessCell` renders each
`code` part in a `<code>` element, so a name is told from the words. If either is null it returns today's sentence without names (never a name
made from the title, date or location: Principle I). `StalenessCell` calls the function with the verdict it was given.
`.reason-note` (and its `code`) gets `overflow-wrap: anywhere`, so a long name wraps at 390 and 320 px.
*Alternative:* put names into the reason's short label ("movie name changed") on the list. Rejected: a list row is
one line, and the supervisor's request was for the note.

### D6. OpenAPI and the generated types follow mechanically
`web/openapi.json` is regenerated by `python -m auto_reel_ng.api.openapi`, `schema.d.ts` by `npm run generate:types`.
`test_committed_schema_is_not_stale` fails between the schema edit and the regeneration, which orders the tasks.

## Risks / Trade-offs

- **[Clients that compare a verdict object exactly]** The four existing exact-equality tests fail until updated →
  Task 2.2 lists them; the e2e test and the editorial-write test check the echoed verdict too.
- **[Merge conflict with `api-excluded-clips-read-model`]** Both edit `schemas.py` and `events_read.py` → different
  models and functions; the implementation starts from the main that has both gates, and regenerates the two
  generated files instead of merging them by hand.
- **[`cancel_requested` shown from a stale read]** A read made just before a cancel shows Cancel offered for a
  moment → the connection's delta corrects it as before; the read can only be older, never wrong in kind.
- **[Requeue loop and `worker_id`]** The advanced copy keeps a worker that the requeue cleared → unused by the
  client; revisit only if a screen starts showing the worker.

## Migration Plan

Additive wire change served and consumed by one build: no migration, no flag. Rollback is a revert; the generated
files revert with it.
