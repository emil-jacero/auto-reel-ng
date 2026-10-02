## Context

See proposal.md, "Why". Written against `main` at `6a7fe16`, **before** its two gates merge. Line numbers are
omitted on purpose: both gates move `api/routes/jobs.py` and `api/events_read.py` (see "Gate").

**What a render does with a missing clip** (`cli/build.py`, `event/resolution.py`, `event/reconcile.py`):
- `reconcile(disk_identities, document)` classifies a clip the document references and the disk lacks as
  `MISSING`. It never removes it from the document.
- `_probe_clips` skips a clip whose `ClipProperties.exclude` is true ("excluded clips never reach the plan")
  and calls `probe_media` on every other referenced clip. `probe_media` raises for a path that is not
  there, so the job fails and is reported failed (Principle I). `resolve` likewise drops excluded clips.
- Played therefore means: `identity in document.referenced_identities()` and not
  `document.clips[identity].exclude`. A NEW clip is adopted by the render and is on disk; an IGNORED one is
  not referenced. Neither can be missing.

**`POST /api/v1/jobs` today** (`api/routes/jobs.py`): resolve the event (`named_event_dir`), the
output-collision check (409 `output_collision`, 502 on a failed walk), the active-job check (409
`active_job`), `load_or_seed`, the fingerprint, the staleness gate (200 `fresh`), and `store.submit` (201,
or the race's 409 `active_job`). Nothing looks at the clips. Triage evidence (re-checked on `6a7fe16`): a
document with an excluded absent clip and a non-excluded absent clip gets 201 with and without `force`; the
second job fails at probe.

**What the client sees today:** `GET /events/{id}` publishes `missing` (all missing identities) and, from
`api-excluded-clips-read-model`, `blocking_missing` (those not excluded). The page and the row hold Render
back from `blocking_missing` only, from the last read. `enqueueJob` in `web/src/api/jobs.ts` has a closed
`switch` on the 409 `conflict` kind with a `never` default, so a new kind is a `tsc` error until handled;
`RenderControl.handleEnqueue` and `LiveJobCell.tellRowAnswer` are the two consumers of the result.

## Gate

Both gates are merged into `origin/main` before this change is implemented (task 1.1 confirms it; they are archived as `2026-10-02-api-jobs-create-validation` and `2026-10-02-api-excluded-clips-read-model`).

- **`api-jobs-create-validation`** rewrites the first half of `create_job`: it resolves with
  `listed_event_dir` and requires `event_id_for(...) == payload.event_id` (404 otherwise); it loads and
  runs `require_processable` inside a `try/except` that answers 502 with the classified failure; its
  `_output_claim` delegates to the engine's `checked_claim`. After it, `create_job` already holds a loaded,
  processable `document` before the active-job check, and a canonical `event_id`. This change adds one step
  after the active-job check and uses that `document`; it does not load the document a second time and does
  not re-derive the event id.
- **`api-excluded-clips-read-model`** adds `EventDetailOut.blocking_missing` (missing and not excluded),
  computed in `events_read`, and makes the page and row guards use it. This change reuses that
  computation, `events_read.blocking_missing` (confirmed on `main`). The refusal calls it through
  `played_missing_clips` below. The two must stay one definition: it is what makes "the server refuses exactly what
  the page already holds back" true.

The two MODIFIED requirements in the `api-service` delta ("Jobs lifecycle over REST", "Enqueue refuses an
event whose output path another event claims") were copied from `main` at `6a7fe16`. The gates also edit
the first of them (the 404 and 502 words). Task 1.1 re-bases both blocks on the archived text: our blocks
must differ from the archive only by the five edits listed in task 1.1.

## Goals / Non-Goals

**Goals**
- One definition of "a played clip is missing", used by the detail's `blocking_missing` and by the enqueue.
- A typed, client-selectable refusal (`conflict: missing_clips`, `missing: [...]`), never a prose match.
- A stale screen learns why its press did nothing and corrects itself.

**Non-Goals** (beyond the proposal's)
- No new store verb, no migration, no job column, and no new job status: a refusal leaves no row.
- No change to `render/`, `probe/`, `scheduler/` or the worker. A clip lost between the check and the
  probe still fails the job at probe (see Risks).

## Research & Decisions

### Where the refusal sits in the order
**Context**: the route has three refusals before the gate (collision, active job, and now missing clips)
and the gate itself.
**Explored**: (a) before the collision check; (b) after collision and before the active-job check; (c)
after the active-job check and before the gate.
**Decision**: (c): collision, active job, missing clips, staleness gate, submit.
**Rationale**: the collision check stays first (it is the only one that protects data, and the spec says
so). An event that already has a queued or running job is answered by following that job, which is what
both screens do for `active_job`; refusing first would hide the job from a client that is about to show
it. The refusal sits before the gate so that `force` cannot reach the submit (the render would only fail
at probe) and so that the 200 `fresh` answer never reports "nothing to render" for an event that has a
played clip missing. A fresh verdict with a played clip missing cannot arise today (a render only succeeds with every played clip on disk, and deleting one afterwards changes the
clip-set component, which hashes the on-disk clips, so the gate reports the event stale), so (c) costs no
behavior; it keeps the order independent of that accident.

### One definition of "played and missing"
**Context**: `blocking_missing` (read model) and the enqueue refusal must agree.
**Decision**: `api/events_read.py` already holds the one rule (from `api-excluded-clips-read-model`):
```python
def blocking_missing(document: Optional[ReelDocument], result: ReconcileResult) -> Tuple[str, ...]:
    """The missing clips a render needs: listed, absent from disk, and not excluded."""
```
(sorted, because `ReconcileResult.missing` is). This change adds one function beside it, the route's entry
point:
```python
def played_missing_clips(event_dir: Path, document: ReelDocument) -> List[str]:
    """`blocking_missing` for `document` against `event_dir`'s listing. OSError propagates."""
    return list(blocking_missing(document, reconcile(scan_event(event_dir).identities, document)))
```
The detail build keeps calling `blocking_missing` with the `ReconcileResult` it already holds. The route calls
`played_missing_clips` with the document it already loaded. `reconcile` marks a clip `MISSING` only when the
document references it, and a seeded document (no `reel.yaml`) lists exactly what the listing holds, so it can
never be missing: passing the seeded document is correct and needs no seeded flag.
**Alternatives**: filtering `result.missing` inline in the route duplicates the exclude rule, which is the
exact drift this change closes; having the route call `get_event` is a full detail build (staleness,
chapters, job store) for one list.
**Rationale**: the route stays composition (Principle V); the rule is the engine's (`reconcile` and the
document's `exclude`), not a new one.

### The 409 body
**Decision**: `EnqueueConflict.MISSING_CLIPS = "missing_clips"`, and `ProblemOut.missing:
Optional[List[str]]` ("on a `missing_clips` 409: the played clips absent from disk, as sorted identities").
The name matches `EventDetailOut.missing`, which is also identities. The route builds it with the existing
`conflict(...)` helper, like the collision's:
```python
return conflict(
    f"{payload.event_id} plays clips that are missing from disk: {', '.join(missing)}; "
    "restore them, or remove them from reel.yaml",
    event_id=payload.event_id,
    conflict=EnqueueConflict.MISSING_CLIPS.value,
    missing=missing,
)
```
`responses=` already declares 409 and 502 (`ProblemOut`); only the model's fields change. `openapi.json` and
`schema.d.ts` are regenerated with the `web/README.md` commands; the schema-staleness test fails until they
are.
**Failure behavior**: `scan_event` raising `OSError` (an unlistable folder) answers the events list's
scan-failure 502 (`bad_gateway(f"event scan failed: {exc}")`, as the collision check does) and enqueues
nothing, never "no clips missing" (Principle I).

### Idempotency
A refusal writes nothing: no job row, manifest, output or `reel.yaml`. Repeating the request after the clip
is restored enqueues normally; repeating it while the clip is absent answers the same 409. `force` makes no
difference. A worker restart is not involved: no job exists. A job already queued for the event is not
touched by the refusal, and the active-job check still answers it first.

### The client
**Decision**: `enqueueJob` gains a result kind `{ kind: 'missingClips'; missing: string[]; problem: Problem }`
and a `case 'missing_clips':` that returns it only when `body.missing` is a non-empty array of strings,
else `break`s to the existing unpublished fallthrough. The `never` default keeps compile-time
exhaustiveness. Words live in `jobs/labels.ts` (next to `NOT_QUEUED`, `SCAN_FAILED`), one function used by
both screens: `refusedForMissingClips(missing)` (all names for the page; three and a count for a toast).
- **Page** (`RenderControl.handleEnqueue`): a `missingClips` notice (`Notice` union), shown by an error
  `Alert` in the render region, then `markEventsChanged()` and `onFinishedRef.current()` as the `fresh` and
  `eventGone` cases do, so the page re-reads and its own `blockedReason` takes over. Focus uses the
  existing rule: a control removed while focused hands focus to the status element (`focusIsLost`).
- **Row** (`LiveJobCell.tellRowAnswer`): `toast.error(`${name}: ${NOT_QUEUED} ${words}`, open)` and
  `markEventsChanged()` so the list re-reads and the row swaps Render for "Blocked by missing clips".
**Alternatives**: a new global store for "events known to be blocked": rejected (Principle VII; the re-read
already yields the truth). Auto-removing the missing clips from `reel.yaml` on refusal: rejected, it is an
editorial write the operator must choose (the Edit-mode removal exists for it).

### Spec deltas and the two gates
**Context**: both gates edit "An event's page schedules its render" and "The event list shows live job
state and offers a render" in `web-app` (the excluded-clip scenario and the row guard). A MODIFIED block
for either would replace their text wholesale at archive.
**Decision**: the web-app delta is one ADDED requirement that extends "every answer the service
publishes" by reference. In `api-service` the vocabulary lives in an existing requirement and the
"always enqueues unless" sentence is wrong without this change, so those two edits are MODIFIED (small,
re-based in task 1.1); the behavior itself is an ADDED requirement.
**Alternative**: MODIFY all four requirements: larger blocks and a guaranteed merge conflict with the gates.

### Not folded into the HLD
No D-n entry: the decision does not touch the graph, the fingerprint inputs or a schema that outlives the
API contract; it is recorded in the `api-service` requirement.

## Risks / Trade-offs

- **The clip disappears between check and probe.** The window is small and the outcome is the one before
  this change: a failed job with the engine's error. → Not closed here; closing it needs the worker to
  re-verify at claim, which is `scheduler/`.
- **`auto-reel enqueue` still queues such an event.** The API refuses what the CLI's `enqueue` accepts, a
  gap against Principle V. `auto-reel render` reaches the same outcome by failing the event at probe, so
  nothing is unreachable from the CLI, but `enqueue` should refuse too. → A follow-up change in `cli/` with
  `blocking_missing` moved to the engine (`event/`); not done here to hold the two-package cap. Reported in
  the hand-off.
- **A very long `missing` list** (a whole card gone). → The body carries all identities (a client can show a
  count); the toast shows three and a count; the page names all and wraps (checked at 390 px).
- **The page's notice outlives the re-read** when the clip came back. → It is cleared by the next press, like
  the other notices. It never claims a job exists.
- **The detail's `blocking_missing` and the refusal drift** if someone inlines the rule again. → One
  function (above), and the API test asserts both on the same event.

## Open Questions

None that change the specs or tasks.
