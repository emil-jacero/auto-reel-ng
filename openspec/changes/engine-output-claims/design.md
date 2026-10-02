## Context

See proposal.md, "Why", for the two findings. The code on `origin/main` at `6a7fe16`:

- **CLI claimants.** `cli/commands.py` `_checked_document(ref, today, order)` calls
  `load_or_seed(event_dir, order=order)` (a one-line wrapper over `event.metadata.load_event_document`) and
  `require_processable(...)`, catching `EventMetadataError` (returns `exc.reason`) and `ReelError` (returns
  `str(exc)`). `_checked_documents` collects reasons per event dir; `cmd_scan` (`:408`) and `_staleness_filter`
  (`:283`) call `_checked_document` directly. `_output_collisions` builds
  `{event_dir: output_relpath(md)}` from the *selected* events' already-loaded documents and runs
  `find_output_collisions`. An `OSError` from the loader escapes all of this.
- **API claimants.** `api/events_read.py` `_output_claim(event_dir, order, today)` does the same load with
  `load_event_document` and catches `(ReelError, OSError, ValueError)` → `None`. `output_collision(settings,
  event_dir, today=...)` checks the named event first (returns `None` without walking when it claims
  nothing), then walks `get_layout(settings.layout_name)(settings.walk_root)` and keys every claimant by its
  own root-relative id, never by the folder a symlink resolves to.
- **Worker.** `scheduler/worker.py` `default_build_job` loads the document with `load_event_document`, applies
  `require_processable`, then `prepare_and_persist`, `compute_fingerprint` and `build_render_job_from_event`
  with `overwrite=True`. `Worker._process` then runs the claim-time staleness recheck (job-scheduler). Nothing
  in `scheduler/` references an output collision.
- **The pure comparison** is `render.find_output_collisions(claims: Mapping[K, PurePosixPath])`, with
  `render.output_relpath(metadata)`; both are re-exported by `render/__init__.py` and are used unchanged.
- **The loader raises, today, for a `000` folder.** With no `reel.yaml`, `Path.exists()` is `False`
  (Python 3.14 swallows `EACCES`), so `load_authored_document` seeds, and `seed_document` →
  `scan_event` → `_video_identities` calls `directory.iterdir()`, which raises `PermissionError`. The layout
  walk itself still yields the event (it only lists the parent): `year-event` over `2024/` returns both a `000`
  event and its readable sibling; `flat` returns the year folder. So the failure shows up at the claim, not at
  the walk, on every surface.
- **A sibling change, `event-permission-errors`,** runs in parallel and edits `event/metadata.py` and
  `event/discovery.py`: a `reel_exists` helper that lets `EACCES` surface, and `scan_event` raising
  `PermissionError` for an unsearchable folder. Whether the loader raises a bare `PermissionError` (today) or a
  typed read error (after it), the claim rule must produce the same result, so it catches by class
  (`ReelError`, `OSError`, `ValueError`), not by the loaders' internals. This change does not edit those files.

## Goals / Non-Goals

**Goals:**
- One function decides whether an event claims an output path; one function answers "does another event claim
  mine?", for a caller that has only a walk root, a layout name and a clip order.
- Every failure to load an event is a *reason*, never an exception, and never a claim.
- The wording of the refusal exists once.
- Pure reads: no file is created, written, locked or touched (a seed is in memory only).

**Non-Goals:**
- Replacing `_checked_documents`' bulk helper, `_output_collisions`' selection-scoped comparison, or the API's
  id-keyed `OutputCollision` in this change; the call-site changes do that.
- A job-store guard, a cache of claims across calls, or incremental walks (Risks).

## Research & Decisions

### Why two modules

**Context**: The triage placed both functions in `event/claims.py` and noted that it "imports
`render.find_output_collisions` without editing `orchestrator.py`".
**Explored**: Constitution Principle VI: lower layers MUST NOT import higher ones, and the stack order is
`ingest/` → `reel/`+`event/` → `probe/` → `accel/` → `render/` → `staleness/` → `persistence/`+`scheduler/` →
`api/`. `render/orchestrator.py` already imports `event.plan`; the reverse would be new. `ingest/layouts.py`
imports `event.discovery`, so `event/` importing `ingest/` is a cycle (`event` → `ingest` → `event.discovery`).
The layout-aware check needs `ingest.get_layout` and `render.output_relpath`.
**Decision**: Two modules. `event/claims.py` holds `checked_claim`, which needs only `event.metadata`,
`reel` and `errors`. `render/claims.py` holds `OutputCollision`, `output_collision` and
`output_collision_message`, importing `ingest`, `event.claims` and `render.orchestrator`.
**Rationale**: It keeps the layering intact and still touches only two packages. `render/` is the lowest
package that may see both the layout and the output-naming rule. An `ast` test pins
`event/claims.py`'s package-relative imports to `..errors` and `..reel` (task 1.2).
**Alternatives**: `event/claims.py` for both (violates VI; cyclic with `ingest`); a new top-level `claims/`
package (a sixth layer for two functions, Principle VII); putting the check in `scheduler/` or `api/` (the
reason for this change).

### The failure set: `ReelError`, `OSError`, `ValueError`

**Context**: The CLI catches `ReelError` only; the API catches `ReelError`, `OSError` and `ValueError`.
**Explored**: `ReelError` covers `ReelParseError` and `EventMetadataError`. `OSError` covers a folder that
cannot be listed or a file that cannot be read for any reason (permission, I/O error, a vanished mount). The
API comment calls `ValueError` "a guard only": the loader wraps every `reel.yaml` problem as `ReelParseError`,
so a `ValueError` would be a bug in reading some *other* event.
**Decision**: Catch all three. Map each to a reason string; return `(None, reason)`. Any other exception
(`TypeError`, `RuntimeError`, `KeyboardInterrupt`) propagates (Principle I: a bug is not an event's problem).
**Rationale**: It is the union, so no surface loses a tolerance it has. Keeping `ValueError` costs nothing
and, unlike the API's silent `None`, the CLI will now *print* the reason, so the guard is no longer silent
(Principle I).
**Reason text**: `EventMetadataError` → `exc.reason` (the CLI prefixes `ERROR <event>:` itself);
other `ReelError` → `str(exc)` (as today); `OSError` and `ValueError` → `cannot read the event: <detail>`
with `<detail>` the OS error text (`exc.strerror`, e.g. `Permission denied`) when there is one, else `str(exc)`.
No traceback, no absolute path unless the exception text carries one.

### Signatures

```python
# auto_reel_ng/event/claims.py   (imports: datetime.date, pathlib.Path, ..errors, ..reel, .discovery, .metadata)
def checked_claim(
    event_dir: Path, *, order: ClipOrder, today: date
) -> tuple[Optional[ReelDocument], Optional[str]]:
    """(document, None) for a processable event, or (None, reason). Exactly one is None.

    A failure claims nothing: ReelError/EventMetadataError, OSError and ValueError become the
    reason. Nothing is written; a folder seed lives in memory only."""

# auto_reel_ng/render/claims.py   (imports: ..event.claims, ..ingest, .orchestrator)
@dataclass(frozen=True)
class OutputCollision:
    output_path: PurePosixPath          # relative to the output directory, as output_relpath gives it
    claimed_by: tuple[Path, ...]        # the OTHER claimants' event dirs as the layout yields them, sorted by str

def output_collision(
    event_dir: Path, *, walk_root: Path, layout: str, order: ClipOrder, today: date
) -> Optional[OutputCollision]: ...

def output_collision_message(output_path: PurePosixPath, claimants: Sequence[str]) -> str:
    """'output path <p> is also claimed by <a>, <b>; set a distinct title or location in reel.yaml'"""
```

`checked_claim` is keyword-only for `order` and `today` (the loader's own convention), because the current
CLI helper takes `(ref, today, order)` and a swapped `date`/`ClipOrder` pair would otherwise be easy to write.
`output_collision_message` is today's exact CLI/API sentence, so the existing
`tests/test_cli_output_collisions.py` and `tests/test_api_output_collision.py` strings stay valid when those
callers adopt it.

### `output_collision` semantics

**Context**: The API's algorithm is the most complete (whole project, named event included even if the walk does
not reach it, aliases are claimants of their own); the CLI's is the same rule restricted to a *selection*.
**Decision**: `output_collision` is the API's algorithm with `Path` keys:
1. `document, reason = checked_claim(event_dir, ...)`; no document → return `None` **without walking** (the
   named event claims nothing, so it collides with nothing; a broken walk cannot matter to it).
2. `target = output_relpath(document.metadata)`.
3. Walk `get_layout(layout)(walk_root)` (no years). For each `ref` whose `event_dir` is not the named `event_dir`
   (Path equality, no `resolve()`): `checked_claim(...)`; a failure claims nothing and is skipped; otherwise it
   claims `output_relpath(...)`.
4. `find_output_collisions({event_dir: target, **others})`; no other claimant → `None`; else
   `OutputCollision(target, tuple(sorted(others, key=str)))`.

A walk's own failure (`LayoutError` for an unknown layout name, `OSError` from the walk) **propagates**:
a caller must not enqueue or render an event whose collision it could not check (Principle I). Claimants are
keyed by the path as spelled, never resolved, so a symlinked alias of an event is a claimant of its own, as
the API's `event_id` keying does today (api-service: collision check). The walk is the one the CLI and API use,
so `layout-alias-dedupe` (which collapses aliases inside the layouts) changes both equally.

**Alternatives**: Take `years` and a pre-loaded document map so the CLI could use it too (the CLI's selection
semantics and its already-loaded documents make that a different function; the CLI keeps
`find_output_collisions` and adopts only `checked_claim` and the message); take a `ProjectConfig` (couples the
check to config loading; the three callers each already hold the three scalar inputs).

### What each caller passes (hand-off to the call-site changes)

| Caller | Change that adopts it | Inputs |
|---|---|---|
| `cli` `_checked_document` | `cli-batch-isolation-and-claims` | `checked_claim(ref.event_dir, order=ctx.config.sort, today=...)`; `_output_collisions` keeps its selection-scoped `find_output_collisions` but formats with `output_collision_message` |
| `api` `_output_claim` / `output_collision` | `api-jobs-create-validation` | `_output_claim` delegates to `checked_claim`; `output_collision` calls the engine function with `settings.walk_root`, `settings.layout_name`, `settings.clip_order`, then maps the `Path`s to event ids |
| `scheduler` `default_build_job` | `worker-claim-guards` | `project_root / config.input_dir or project_root`, `config.layout or DEFAULT_LAYOUT`, `config.sort`; on a collision raises an `EngineError` subclass whose text is `output_collision_message(...)` so the existing handler fails the job. Placed right after `require_processable` and **before** `prepare_and_persist`, so a colliding job adopts nothing into `reel.yaml` |

Those changes verify the scenarios of the two deltas at their own surface and **MUST NOT** add a second delta
for the same requirements. `worker-claim-guards` may add its running-job guard by MODIFYING the job-scheduler
requirement below after this change archives.

## Failure behaviour, idempotency

- **Raises:** `LayoutError` (unknown layout) and `OSError` from the layout walk, from `output_collision` only.
  `checked_claim` raises nothing it is meant to map; unexpected exception types propagate.
- **Reported per event:** the reason string; the caller prints it (`ERROR <event>: <reason>` in the CLI), fails
  the job with it (worker) or answers with the existing events-list error row (API).
- **Leaves no partial file:** both functions are read-only. A `reel.yaml` is never written; a folder seed is in
  memory. `RENDER_GRAPH_VERSION`, the `.part` protocol and the manifest are untouched.
- **Idempotent:** same disk, same answer. A re-run, a `--force` run and a worker restart mid-render each
  re-evaluate from disk; `force` is not an input (the rule is never bypassed). A job requeued after a worker
  restart is rechecked at its next claim, so a collision introduced meanwhile fails it then.

## Risks / Trade-offs

- **Cost.** One call loads every event's `reel.yaml` (or lists its folder) in the project, as the API already
  does per `POST /api/v1/jobs`. On the real archive (~140 events) that is the cost of one events-list scan, per
  claimed job. → Acceptable now; a claim cache is a Non-goal. If the worker's per-job cost shows up, the walk can
  be shared across a claim batch by a later change.
- **Worker has no layout override.** `auto-reel serve --layout` / `-l` can override `config.layout`; the worker
  only sees `config.yaml`. The worker's walk therefore uses the configured layout. → Pre-existing for the whole
  worker (it resolves `project_root / job.event_dir` itself); noted for `worker-claim-guards`, not solved here.
- **Races remain narrow, not zero.** A reel.yaml edit between the claim-time check and the finalize can still
  produce a collision for that render. The check closes the "edited after enqueue" and "concurrent enqueue"
  holes; the finalize `os.replace` stays the last line of defence. → Documented; the running-job guard in
  `worker-claim-guards` narrows it further.
- **Spec ahead of code until the follow-ups land.** The deltas describe CLI and worker behaviour that the three
  gated changes deliver. → The gates in the plan order them directly after this change; this change's own
  tests pin the engine half, and each follow-up's tests pin its surface.
- **Behaviour change for the CLI:** a `000` folder used to crash `scan`; it is now an `ERROR` line and a
  non-zero exit, with the rest of the batch processed. A script that relied on the traceback exit status gets
  exit 1 instead (the documented per-event error status).

## Open Questions

None that change the specs or tasks.
