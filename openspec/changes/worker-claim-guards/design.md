## Context

See proposal.md, "Why", for the two findings. The code on `origin/main` at `d683264` (the spec was first written at `6a7fe16`):

- **`scheduler/worker.py` `default_build_job(job, *, runtime, profile, render_node)`** resolves
  `project_root`/`event_dir` from the job row, loads the project's `config.yaml`, loads the document with
  `load_event_document(event_dir, order=config.sort)`, applies `require_processable`, then
  `prepare_and_persist` (which can write `reel.yaml` to adopt NEW clips), `compute_fingerprint` and
  `build_render_job_from_event(..., overwrite=True)`. Nothing in `scheduler/` references an output collision.
- **`Worker._process`** calls the injectable `build_job`, handles `EngineError` by failing the job with
  `str(exc)`, then runs `_is_fresh` (the claim-time staleness recheck), `resolve_target`, acquires a capacity
  token and renders. A job is `running` from the moment `claim_next` returns it, so every job a worker is
  building, waiting on a token for, or rendering is a `running` row.
- **`cli/build._probe_clips(document, event_dir, runtime)`** loops `document.referenced_identities()`, skips
  clips whose `document.clips[identity].exclude` is set, and calls `probe_media(event_dir / identity)`. A
  missing file reaches `probe/media.py`, which raises `ProbeError(f"File does not exist: {media_path}")`.
  `_probe_clips` is reached through `build_render_job_from_event`, which `cmd_render` (through
  `_build_job`) and the worker both call, so one fix there serves both.
- **`Job.output_path`** exists as a column but no code sets it at enqueue, so the store cannot say where a
  running job writes. A running job's output has to be resolved from its project and event on disk.
- **`engine-output-claims`** (the gate for the collision half, merged) added `event/claims.py` (`checked_claim(event_dir,
  *, order, today) -> (document | None, reason | None)`) and `render/claims.py` (`output_collision(event_dir,
  *, walk_root, layout, order, today) -> OutputCollision | None`, `OutputCollision(output_path:
  PurePosixPath, claimed_by: tuple[Path, ...])`, and `output_collision_message(output_path, claimants:
  Sequence[str])`). Its design hands the worker the inputs: `project_root / config.input_dir` (or
  `project_root`), `config.layout or DEFAULT_LAYOUT`, `config.sort`. It lists "an `EngineError` subclass whose
  text is `output_collision_message(...)`" as this change's job, and says this change may add the running-job
  guard. The signatures above were re-read on `origin/main`; the CLI and the API do not call
  `render/claims.py` yet (they keep their own copies of the wording), so the worker is its first caller.
- **`worker-exception-backstop`** (the gate for `worker.py`, merged) renamed the body of `_process` to `_process_job`
  and wraps it in a single `except Exception`. This change adds one call inside `_process_job` and edits
  `default_build_job`, which the backstop does not touch; an exception my code does not type (for example an
  `OSError` from the layout walk) reaches the backstop and fails the job as `OSError: ...`.

## Goals / Non-Goals

**Goals:**
- A claimed job never renders into a path another event, or another running job, owns, and the refusal is a
  job error an operator can act on.
- A missing clip fails the event with its identity and the fix, once, naming all of them, on every surface
  that builds a plan.
- Refusals are decided before anything is written or probed.

**Non-Goals:** liveness of stale `running` rows, requeue-instead-of-fail, a claim cache, the worker's
`--layout`, the API's `missing_clips` 409. See proposal.md, "Non-goals".

## Research & Decisions

### Spec ownership: one requirement per rule

**Context**: `engine-output-claims` merged and its `job-scheduler` requirement "Claim-time output-collision
recheck" is in `openspec/specs/` (it states the same-project rule, the order before the staleness recheck, that
`force` does not bypass, and that an unwalkable layout fails the job). Its engine half (`event/claims.py`,
`render/claims.py`) merged without the worker call, which is this change's job.
**Decision**: This change adds no delta for that requirement: the implementation and its worker-level tests
satisfy it as written. The `job-scheduler` delta ADDS only the behaviour no requirement states: the running-job
guard ("A claimed job is refused while another running job writes its output").
**Rationale**: No requirement is owned twice, and the delta validates and archives on its own.
**Alternatives**: restating the collision rule in a second requirement (two places to keep in step); no
`job-scheduler` delta (the running-job guard would have no spec).

### The collision guard sits in `default_build_job`, before `prepare_and_persist`

**Context**: Where to ask "does another event claim my path?" so that nothing is written for a refused job.
**Explored**: `prepare_and_persist` writes `reel.yaml` when it adopts NEW clips (`persist`), so a check after
it would let a refused job modify the event. The processable check sits just before it and already loads the
document the output path comes from.
**Decision**: In `default_build_job`, directly after `require_processable` and before `prepare_and_persist`:

```python
walk_root = project_root / config.input_dir if config.input_dir else project_root
collision = output_collision(
    event_dir, walk_root=walk_root, layout=config.layout or DEFAULT_LAYOUT,
    order=config.sort, today=date.today(),
)
if collision is not None:
    raise OutputCollisionError(
        output_collision_message(
            collision.output_path,
            [c.relative_to(project_root).as_posix() for c in collision.claimed_by],
        )
    )
```

`OutputCollisionError(EngineError)` is added to `errors.py`; `Worker._process`'s existing `except EngineError`
records `str(exc)` as the job error, so the text reaches the job unchanged and the exception backstop is not
involved. A claimant outside `project_root` (a layout that walks beyond it) is named by `str(path)` instead
of raising from `relative_to`. `force` is not read: the rule is never bypassed, as for the CLI.
**Rationale**: Reuses the shared rule and wording (Principle V, one rule on three surfaces), and a refusal
leaves no trace. The check also runs on a job that would have been judged fresh: a fresh event whose
`reel.yaml` now collides is a real collision, and the CLI refuses fresh events too.
**Alternatives**: checking in `Worker._process` after the build (writes `reel.yaml` first, and the output path
there comes from the already-built plan); `RenderError` instead of a new class (it means "a movie could not
be rendered", and the test for this behaviour should assert the type); returning a reason string from the
helper instead of raising (a second error channel next to the existing `EngineError` handler).

### The running-job guard is a store read in `_process_job`, before the build

**Context**: The disk rule is symmetric: if two events of a project claim one path, both jobs fail. It cannot
see two cases: a different project with the same output directory, and an event the layout walk does not
reach but a job names. Only the store knows what else is `running`.
**Explored**: `JobStore.list_by_status(JobStatus.RUNNING)` already lists every project's running rows, so
no store method or migration is needed. `Job.output_path` is never set, so each running row's output is
resolved from disk. Placing the check after the build (where the claimed job's output is on the built job)
would let a refused job already have adopted clips into `reel.yaml` and probed every clip, which the refusal
contract forbids; the claimed job's own output is therefore resolved from disk by the same helper as the
others', before the build.
**Decision**: In `_process_job`, inside the existing `try` and ahead of `self._build_job(job)`, call
`self._refuse_running_output(job)`. It resolves the claimed job's output with a module function
`_job_output_path(job, today)` and, when that is not `None`, lists the running rows, skips the claiming job's
id, resolves each other row the same way, and asks `find_output_collisions({job.id: own, **others})` (any
hashable key works, so the rule's case-insensitive, NFC comparison is reused):

```python
def _job_output_path(job: Job, *, today: date) -> Optional[PurePosixPath]:
    """The output a job writes, as an absolute path, or None when it claims nothing."""
    project_root = Path(job.project_root) if job.project_root else Path.cwd()
    try:
        config = load_project_config(project_root)
    except (EngineError, OSError):
        return None
    document, _reason = checked_claim(project_root / job.event_dir, order=config.sort, today=today)
    if document is None:
        return None
    output_dir = project_root / config.output_dir if config.output_dir else default_output_dir(project_root)
    return PurePosixPath(output_dir / output_relpath(document.metadata))
```

A hit raises `OutputCollisionError(f"output path {relpath} is also being rendered by the running job for
{event}; ...")`, which the same `except EngineError` records. The claimed job's own failure to resolve (bad
config, unprocessable event) refuses nothing: the build then fails with its own, better reason.
**Rationale**: Closes the cross-project and outside-the-walk holes with a read, no new column, no lock, and
refuses before any write. A `fresh` job is refused too (the build that would have found it fresh has not run):
two jobs for one output are a real conflict either way. The refused job fails, like the enqueue refusal; it
does not requeue (a requeue would spin against a long render).
**Alternatives**: persisting the resolved output on the row at claim (migration, a new store method, and
still racy); an in-process set of paths (blind to a second worker); a `pg_advisory_lock` on the path (holds a
connection for a whole render; the other job would block instead of failing); checking after the build (writes
`reel.yaml` first).

### The tie when two jobs are claimed together

**Context**: Rows turn `running` at claim, before their check, so two jobs for one output claimed at the
same moment can each see the other.
**Decision**: The guarantee is "at most one renders", not "both are refused": whichever check runs after the
other job is `running` refuses, and the first to fail leaves the row terminal so its rival can pass. A job
that already passed when the other was still `queued` is not affected; the second is refused.
**Rationale**: No ordering key to invent, no lock; the invariant that matters (one writer per output path)
holds. Re-enqueueing a refused job after the other ends is one action. (The same-project disk rule is
symmetric and refuses every claimant, as the batch commands do.)
**Alternatives**: let the oldest `created_at` win (a second ordering rule, wrong when the older job is the one
that must change).

### Stale `running` rows can refuse a job

**Decision**: Accepted, and documented here. A `running` row left by a dead worker blocks a job for the same
output until a worker starts and reconciles (`find_orphaned_running`). Two active jobs for one event cannot
exist (`ux_jobs_active_identity`), and two events of one project are caught by the disk rule whether or not
a row is stale, so only a different project or an unwalked event is affected; re-enqueueing after the next
worker start works. A heartbeat is out of scope (`render-stall-watchdog` has no DB heartbeat either).

### The missing-clip check in `_probe_clips`

**Context**: `probe_media` is a low-level, path-based library whose `File does not exist: <path>` is right
for a caller that holds a path. The identity and the fix are known only where the document and the event
folder are, which is `_probe_clips`.
**Decision**: In `_probe_clips`, collect the included identities first, then:

```python
missing = [i for i in included if not (event_dir / i).exists()]   # follows symlinks: a dangling one is missing
if missing:
    raise MissingClipsError(missing_clips_message(missing))
```

`MissingClipsError(EngineError)` is added to `errors.py`. The message, built in `cli/build.py`:

- one: `clip 'borttagen.mp4' is listed in reel.yaml but is missing from the event folder; restore the file, or remove the clip from the event (Edit mode, or reel.yaml)`
- several: `3 clips are listed in reel.yaml but missing from the event folder: 'b.mp4', 'Dag 2/c.mp4', 'e.mp4'; restore the files, or remove the clips from the event (Edit mode, or reel.yaml)`

Identities are relative to the event folder, in document order; the event's name is added by the caller
(`ERROR <event>: ...`, the job's event reference). `exists()` rather than `is_file()`: a directory or special
file named like a clip is not "missing", and `probe_media` keeps reporting it as `Not a regular file`; a
dangling symlink is missing.
**Rationale**: A single check shared by the CLI and the worker (the job error is `str(exc)`), no change to a
public library function, and the user gets all the clips to fix in one round.
**Alternatives**: reuse `PreparedEvent.reconcile.missing` (it is the same set but is computed from disk
listing and includes excluded clips, so the excluded rule would be applied twice); change `probe_media` to
take an identity (breaks its path-based contract, and it has other callers); only the first missing clip (the
reported bug).

## Failure behaviour, idempotency

- **Raises:** `OutputCollisionError` and `MissingClipsError`, both `EngineError`s, so the worker's existing
  handler fails the job and `cmd_render`'s per-event handler reports `ERROR` and carries on. `LayoutError`
  (unknown layout) is an `EngineError` too and fails the job with its message; an `OSError` from the walk is
  not, so it reaches the exception backstop and fails the job as `OSError: ...` (never a silent unchecked
  render).
- **Reported per event/job:** the reason text, nowhere else. **Leaves no partial file:** the collision guard
  runs before `prepare_and_persist`, the running guard before the build, the token and any segment, the missing-clip
  check before any ffprobe; none of them creates `.part`, a manifest or a `reel.yaml` write.
- **Idempotent:** same disk and store, same answer. A re-run or a `--force` run is checked again and `force`
  is not an input; a worker restart requeues the job and it is checked at its next claim, so a collision
  introduced meanwhile fails it then. Fixing the cause and enqueueing again works at once (the failed row is
  terminal).
- **CPU fallback / ffmpeg args:** untouched; these checks run before the plan is resolved.

## Risks / Trade-offs

- **Cost.** The collision walk loads every event's `reel.yaml` in the project per claimed job (the cost the
  gate's design accepts for the API per enqueue); the running guard adds one query and a config plus
  document load per other running job (a handful). → Acceptable; a claim cache is a non-goal.
- **Worker has no layout override.** `serve --layout`/`enqueue --layout` override `config.layout` for that
  process, but the worker only sees `config.yaml`; the job row records no layout. → The worker's walk uses
  the configured layout, as the rest of `default_build_job` already does.
- **Races remain narrow, not zero.** A `reel.yaml` edited after the claim-time check can still collide, and
  two jobs claimed in the same moment are both refused. The finalize `os.replace` stays the last line of
  defence; the running guard narrows the window further.
- **A stale `running` row can refuse a cross-project job** (above). → Documented; re-enqueue after the next
  worker start.
- **Behaviour change:** a job whose event collides, which used to render and silently replace a movie, now
  fails. A job whose clip is missing fails with different text (still failed).
- **Overlap with `worker-exception-backstop`.** It edits `_process`/`_process_job`; this change adds one call
  in `_process_job` and edits `default_build_job` and `cli/build.py`. Implementation follows its merge, and
  task 1.1 re-reads the code.
