## Context

See proposal.md "Why". Current state on `main` (research `analysis/findings.md`, paths under `auto_reel_ng/`):

- `api/events_read.py:757 get_analysis` walks `scan_event(event_dir).identities`, stats each clip
  (`analysis/cache.py clip_signal`, size + `mtime_ns`) and returns `AnalysisOut{analyzed, segments}`; `analyzed`
  starts as `(event_dir / CACHE_SUBDIR).is_dir()`, which a render manifest also creates. `read_entry` swallows
  every `OSError` as "cold".
- `routes/events.py enqueue_proxies` is the enqueue precedent: `listed_event_dir` (404) → `scan_event` (502
  `unreadable_disk`) → `active_job(kind=)` (409 `active_job`) → freshness (200) → `submit(kind=)` (201, or the
  race's 409), wrapped in `job_store_unreachable` (503). Its read helpers live in `api/proxy_read.py` because
  `events_read.py` is at pylint's module-size limit.
- `api/schemas.py` imports `JobKind` from `persistence/models.py`, so the published enum follows the store's;
  `serialize.jobs_to_out` drops (and logs) a row of a kind the enum lacks; `api/ws.py` reads every kind.
- The gate `analysis-job` (plan entry; merges first) adds `JobKind.ANALYSIS`, an `AnalysisJobHandler` that
  analyzes each clip whose entry is missing or stale (all with `force`), a **failure marker keyed by the clip
  signal** for a clip whose analysis failed (not retried until the clip changes or a forced job runs), atomic
  sidecar writes, the claim order render > proxy > analysis, `analysis_slots`, and `auto-reel analyze <root>
  --enqueue [--force]`.

## Goals / Non-Goals

**Goals:** the two enqueue routes, an honest per-event and per-clip state on `GET …/analysis`, one selection rule
shared with the CLI, `analysis` in the published job-kind vocabulary.

**Non-Goals:** anything the proposal's Non-goals list; any change to how analysis runs or what it writes.

## Gate

Checked against the merged `analysis-job` (archived `2026-10-05-analysis-job`, `main` at `704d8e3`) before code:

| Needed from the gate | Expected (plan entry) | What the gate built |
|---|---|---|
| `JobKind.ANALYSIS = "analysis"` in `persistence/models.py` | yes | holds |
| A reader for the failure marker for (event, identity, signal) | in `analysis/cache.py` | `read_failure(event_dir, identity, signal) -> Optional[str]` (the one-line cause); `read_entry` answers `None` for a marker. Neither tells an absent file from an unreadable or another signal's, so `cache.py` gains `inspect_entry` (D1), keeping the format private to `cache.py` |
| The per-clip "needs analysis" decision the handler and `--enqueue` use | missing or stale entry, no marker for the current signal | the handler (`scheduler/analysis_job.py _analyze_one`) decides per clip at run time; `analyze --enqueue` **selects nothing**: it queues one job per selected event through `submit_analysis` (the gate's job-scheduler requirement "`auto-reel analyze` can queue analysis jobs" says so), and a job over a fresh event costs a `stat` and a JSON read per clip and leaves it fresh. See D6 |
| `submit(kind=ANALYSIS, force=)` stores `force` | `jobs.force` column exists | holds; the shared enqueue is `scheduler.submit_analysis(store, project_root, event_dirs, *, force)`, which also **forces a `queued` unforced active job** (`JobStore.force_queued`) and reports `forced=False` for a `running` one. Both routes call it (Principle V) |
| `openapi.json` regenerated with `analysis` in `JobKind` | likely, the drift test forces it | already there, and in `schema.d.ts`; `web/src/jobs/kinds.ts` uses predicates, so the web compiles unchanged |
| MODIFIED `api-service` requirements | copied text | "Job kind is a closed, published vocabulary" was MODIFIED by the gate (adds `analysis` and the scenario "An analysis job says it is an analysis job on every read"): this change's delta starts from that text. "Analysis results are exposed read-only" is unchanged on `main` and still says "SHALL NOT need the database and SHALL declare no 503", which this change reverses (D4) |

## Decisions

### D1. State is an engine function in `analysis/state.py`, the job overlay is in `api/`

```python
class ClipAnalysisState(StrEnum):   # disk-derived; "analyzing" is added by the service
    NEVER = "never"; STALE = "stale"; CURRENT = "current"; FAILED = "failed"

@dataclass(frozen=True)
class ClipAnalysis:
    identity: str
    state: ClipAnalysisState
    detail: str | None          # the failure marker's message, when it has one

def clip_analysis_states(event_dir: Path) -> list[ClipAnalysis]: ...   # stat + JSON only
def needs_analysis(clips: Sequence[ClipAnalysis]) -> bool: ...        # any NEVER or STALE
```

`analysis/cache.py` gains `inspect_entry(event_dir, identity, signal) -> EntryRecord` (`absent`, `result` with its
segments, `failure` with its cause, `other`), which opens the entry itself and lets any `OSError` but
`FileNotFoundError` propagate; `read_entry`/`read_failure` keep their "cold" contract for the job. `state.py` maps
the record to a state and wraps an unreadable entry or an unstattable clip in `AnalysisStateError` (`errors.py`). A
clip that vanished between the listing and its `stat` is left out, as the read always did.

Per clip, for the clip's current size+mtime signal: a valid entry → `current`; else a failure marker for that
signal → `failed`; else an entry or marker for another signal, or an entry file that exists but is unparseable or
of another version → `stale`; else (no entry file, no marker) → `never`. A missing entry file is `never`; any other
`OSError` reading it (permission denied) **raises** — the state of a clip that cannot be read is never guessed
(Principle I).

Per event (the first rule that holds): a queued or running analysis job → `analyzing`; no clips, or every clip
`current` → `current`; every clip `never` → `never`; any clip `never` or `stale` → `stale`; otherwise (only
`current` and `failed`) → `failed`. A clip reads `analyzing` when a job is active and the clip is `never` or
`stale`, or `failed` under a forced job; a `current` clip stays `current` under a forced job (its suggestions are
still valid until replaced).

*Why `analysis/`:* Principle V and VI — `analysis-auto-sweep` (scheduler) needs the same selection, and a lower
layer cannot import `api/`. The job overlay needs the store, so it stays in
`api/analysis_read.py`. *Alternative:* compute in `api/` only — rejected, the CLI could not reach the rule.

### D2. The enqueue mirrors the proxy enqueue, with `force`

`POST /api/v1/events/{event_id:path}/analysis`, registered before the greedy detail route, body
`AnalysisEnqueueRequest{force: bool = False}`, optional (no body = `force: false`). Order: event (404, 502) →
`active_job(kind=ANALYSIS)` (409 `active_job`; with `force`, a `queued` unforced job is first given `force` with
`JobStore.force_queued`, as the gate's `analyze --enqueue --force` does, so a Re-analyze that meets the sweep's
queued job is not lost; a `running` one is left; the body's `forced` is `force_queued`'s answer for a forced
request and the job's own `force` otherwise, so the client tells a Re-analyze that took effect from one lost behind
a running unforced job, as the CLI's note does) → states (502 without a kind when a clip or entry cannot be read) →
unless `force`, `needs_analysis` false → 200 `AnalysisFreshResult{event_id, status: "fresh", clip_count,
failed_count}` → `submit_analysis(store, root, [event_dir], force=force)` → 201 `JobOut` or the race's 409 (the gate's function
has already forced a queued job it met; `forced` is the submission's for a forced request, else the winner's
`force`). 503 via
`job_store_unreachable`. The route writes only the job row: **Re-analyze does not delete failure markers in the
request**; the forced job overrides them when it runs (the gate's behaviour) — a request that wrote the sidecar
would race the worker and break "endpoints do lifecycle only". With `force` and no clips the answer is still 200
`fresh` (`clip_count` 0): a job with nothing to do is not created.

*201, not 202:* the plan entry says "202 + job"; the existing render and proxy enqueues answer 201 with the created
job row and the web already handles that shape, so 201 keeps one enqueue contract. Flagged for the supervisor.

### D3. Analyze all is one request over the events list

`POST /api/v1/analysis`, no body. Walk the events the events list shows, in its order (the list's own walk, so a
`.reelignore`d folder or year folder is never a target); for each: active analysis job → `active += 1`; states
unreadable or the event folder unreadable → an `unreadable` item `{event_id, detail, failure}` and go on (per-event
isolation, Principle I); `needs_analysis` false → `fresh += 1`; else `submit_analysis(…, force=False)` → `queued += 1`
(a lost race counts as `active`). 200 `AnalyzeAllResult{queued, fresh, active, unreadable[]}`. A walk that fails → 502, nothing queued.
The store failing mid-walk → 503; rows already inserted stay (each is a valid job, and a repeat is idempotent
because those events then count as `active`). `reel.yaml` is never read, as for the per-event route.

The cost is the per-event read times the number of events (stat per clip + one small JSON per clip) plus one
`latest_by_project(kind=ANALYSIS)` query, never per-event queries. No cap: the user asked for all; the claim order
puts every analysis job behind renders and proxies.

### D4. `AnalysisOut` grows additively; the read now needs the store

```python
class AnalysisState(StrEnum): NEVER, STALE, CURRENT, ANALYZING, FAILED
class ClipAnalysisOut(BaseModel):
    state: AnalysisState
    detail: str | None = None
class AnalysisOut(BaseModel):
    analyzed: bool                     # legacy, value unchanged, documented as such
    segments: dict[str, list[SegmentOut]] = {}
    state: AnalysisState               # required
    clips: dict[str, ClipAnalysisOut]  # required; one per clip file the event lists
    job: JobOut | None                 # the active analysis job, else null
```

`state` and `clips` are required (a client can switch exhaustively); `analyzed` and `segments` keep their exact
values. Because `analyzing` comes from the job store, the read now declares **503** when the store is unreachable,
rather than reporting a state it cannot know. The 404 / 502 rules are unchanged.

### D5. Job kind vocabulary and per-kind independence

No code beyond what the gate adds: `JobKind` drives the schema, `jobs_to_out` and the hub already carry every
known kind. The spec gains `analysis` in the vocabulary and an "analysis job does not block other kinds"
requirement; tests pin both. `latest_job` already reads `kind=RENDER` only.

### D6. `analyze --enqueue` keeps the gate's contract; the rule is the service's and the sweep's

The draft had the CLI's `--enqueue` select with `needs_analysis`. The gate's `--enqueue` queues one job per selected
event (job-scheduler "`auto-reel analyze` can queue analysis jobs"), and changing that would be a third capability
delta (job-scheduler) and a `cli/` edit for no behaviour the user lacks: a job over a fresh event analyzes nothing
(the gate's "an analysis job leaves a fresh event fresh"). So the CLI is not touched. Parity (Principle V) holds
because both enqueue through `submit_analysis` and the selection is the engine function `needs_analysis` in
`analysis/`, not code in `api/`; the auto-sweep will call it. The spec drops the "CLI and service select the same"
scenarios.

## Research & Decisions

### Where "analyzed" comes from
**Context**: the web cannot trust `analyzed`. **Explored**: `findings.md` §2 (`events_read.py:776`, render manifest
creates the folder; `suggestions.ts` collapses three states). **Decision**: a closed `state` vocabulary per event and
clip; `analyzed` kept unchanged as legacy. **Rationale**: additive, no client breaks, the web change can switch on it.

### Enqueue shape
**Context**: Re-analyze and Analyze all. **Explored**: `findings.md` §3 (`submit` idempotent, generic unique active
index, no migration), §5 Q6 (mirror the proxy route; one project-wide endpoint for CLI parity). **Decision**: D2 and
D3. **Rationale**: one enqueue contract across kinds; the batch is one request with the CLI's selection.

### Re-analyze and failure markers
**Context**: the plan says force "clears failure markers for that event". **Explored**: the gate's force semantics
(ignore entries and markers). **Decision**: the forced job clears/overwrites them; the request writes nothing but
the job row. **Rationale**: Principle V ("endpoints do lifecycle"), no API/worker write race on the sidecar.

## Failure behaviour and idempotency

- Nothing in this change starts a process, probes, decodes or writes a file; every route writes at most job rows.
- Repeat `POST …/analysis` while active → 409 with the same job; after it ends → 200 `fresh` (or 201 if a clip
  failed and `force` is set). Repeat `POST /analysis` → previously queued events count as `active`.
- Worker restart mid-job is the gate's (requeue); the state reads `analyzing` while the row is queued or running.

## Risks / Trade-offs

- [The gate names its marker reader or selection differently] → task 1.1 adapts names before code; the spec is
  behavioural.
- [`analysis-auto-sweep` writes its own selection in parallel] → the selection lives in `analysis/state.py`
  (`clip_analysis_states`, `needs_analysis`); the supervisor should land this before the sweep or have the sweep
  call it (noted in the result). *Materialized:* the sweep landed first with its own `cache.entry_state` /
  `pending_clips`. At landing this change keeps both (its `EntryKind` became `EntryFileKind` to avoid the clash),
  states the agreement in the spec (`never`/`stale` exactly when `missing`; an unreadable entry is an error here)
  and pins it with a test; folding the two into one function is a follow-up.
- [Analyze all on the 13-year MOL library queues hundreds of rows] → each is one cheap row at the lowest claim
  rank; cancel is per job; the response's `queued` tells the user what happened.
- [A clip that cannot be read makes `GET …/analysis` a 502] → intended (fail loud); the analyze-all route
  isolates it per event.

## Migration Plan

None: additive fields, new routes, no schema migration. Rollback = revert; queued `analysis` rows are the gate's.
