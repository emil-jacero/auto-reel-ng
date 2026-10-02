## Why

The worker is the one place that builds and renders a plan without the guards the CLI and the API apply,
and when the shared build path does fail, it fails with text only a developer can use (HLD §4.3 output
layout, **D-9**; §4.6 job scheduler, **D-S1** rebuild at claim time; Principle I, fail loud with a reason
an operator can act on). Two findings, both re-checked on `origin/main` after `engine-output-claims` and `worker-exception-backstop` merged
(first written against `6a7fe16`):

- **A claimed job does not recheck its output path.** `find_output_collisions` is called from
  `cli/commands.py` and `api/events_read.py` only; nothing in `scheduler/` calls it. The worker rebuilds
  the plan from disk at claim time and renders with `overwrite=True` (`default_build_job`). Two jobs
  enqueued with distinct paths, where one event's `reel.yaml` is then edited to the other's date and
  title, are both claimable and both render to the same file and the same `<output>.part`
  (`orchestrator._part_path`): one movie silently replaces the other, or two concurrent renders corrupt
  one `.part`. The enqueue-time refusal cannot see an edit made later, and has a plain race against a
  concurrent enqueue. Static reasoning from the code, not an executed repro (it needs a layout walk and a
  real database).
- **A missing clip fails as a raw absolute path.** Executed on `main`: a scratch event whose `reel.yaml`
  lists `clip1.avi` and `borttagen.mp4` (absent) makes `auto-reel render proj --device cpu` print
  `ERROR  2025-01-16 - Gammal: File does not exist: /tmp/.../input/2025/2025-01-16 - Gammal/borttagen.mp4`.
  `cli/build._probe_clips` calls `probe_media` for every referenced non-excluded clip with no pre-check,
  `probe/media.py` raises `ProbeError("File does not exist: <abs path>")`, and the worker stores
  `str(exc)` as the job error, so the GUI shows the same text. It names a path, not a clip, gives no fix,
  and stops at the first missing clip.

This belongs to the 2026-10-02 bug round after HLD §6 phase 8; it depends on no open §8 research item.

## What Changes

- **Claim-time output-collision guard** (`scheduler/worker.py`, `default_build_job`): after the processable
  check and before anything is written, the worker asks the engine's shared, layout-aware rule
  (`render/claims.output_collision`, from `engine-output-claims`) whether another event of the job's project
  claims the same output path. On a collision the job fails with the shared refusal text through a new
  `OutputCollisionError` (an `EngineError`), which the existing handler records as the job error. `force` does
  not bypass it. The requirement for this is already in `openspec/specs/job-scheduler` ("Claim-time
  output-collision recheck", written by the gate, whose engine half merged without the worker call); this
  change implements and tests it at the worker and adds no second delta for it.
- **Running-job guard** (`scheduler/worker.py`, `Worker._process_job`): before it rebuilds the plan, the worker
  also refuses a job whose output path is the output path of another job that is `running` in the store, which
  covers a shared output directory across projects and an event the layout walk does not reach. The job fails
  with a reason naming the other job's event.
- **Missing-clip pre-check** (`cli/build.py`, `_probe_clips`): before any ffprobe, every referenced,
  non-excluded clip is checked for presence. One `MissingClipsError` (an `EngineError`) names every missing
  clip identity, in document order, with the fix. It is shared by `render` and the worker, so the CLI line and
  the job error are the same text. `probe_media` itself stays a low-level, path-based call.
- **Tests** alongside each fix: stubbed worker jobs against a real database for the worker guards, and the
  CLI plus a stubbed worker job for the missing-clip text.
- **HLD:** one amendment line on D-9 (the worker applies the rule at claim time and refuses a running
  job's output).

## Non-goals

- **No new collision rule and no new wording.** What collides, and the sentence that says so, are
  `engine-output-claims`'; this change only calls them from the worker.
- **No change to the API.** `POST /api/v1/jobs` keeps its enqueue-time 409 (`api-jobs-create-validation`).
  The typed 409 `missing_clips` refusal at enqueue is `api-jobs-missing-clips-refusal`.
- **No heartbeat, lease or reaper** for a `running` row whose worker died, and no requeue-instead-of-fail:
  a refused job fails, as the enqueue refusal does, and the operator re-enqueues after fixing the cause.
- **No change to `probe/media.py`** and no pre-check of excluded, NEW or IGNORED clips.
- **Not a worker `--layout` override.** The worker only sees `config.yaml`, so its walk uses the configured
  layout (design, Risks).
- **No change to chapter-name strictness or to superseded renamed movies** (held for the user).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `job-scheduler`: new `Requirement: A claimed job is refused while another running job writes its output`,
  the running-job guard. The same-project collision rule is the existing requirement "Claim-time
  output-collision recheck"; this change delivers it (design, "Spec ownership").
- `headless-cli`: new `Requirement: A referenced clip missing from disk fails its event by identity`, for
  `render` and for the worker through the shared build path.

## Impact

- **Baseline:** written against `origin/main` at `6a7fe16`; implemented on `origin/main` at `d683264`, after
  `worker-exception-backstop` (`worker.py`) and `engine-output-claims` (`event/claims.py`,
  `render/claims.py`) merged.
- **Packages:** `scheduler/` and `cli/` (plus the top-level `errors.py`, two small exception classes). Files:
  `scheduler/worker.py`, `cli/build.py`, `errors.py`, `tests/test_scheduler_worker.py`,
  `tests/test_cli_render.py`, `docs/high-level-design.md`.
- **CLI vs API (Principle V):** the missing-clip text reaches the CLI (`render`) and the API (job error)
  through the one shared build path; the collision guard is worker-only because the CLI and API already
  refuse at their own surfaces. Nothing is added to `api/`.
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump**, and the staleness
  fingerprint inputs are unchanged. A refused job writes no output, no manifest and no `.part`.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan, no OpenAPI or
  `web/` change.
- **Complexity (Principle VII):** two small exception classes, one worker helper that resolves a job's output
  path, no new config key or dependency.
- **Size (Principle VIII):** two capability deltas, two packages, 9 tasks (one baseline, one docs, one validation).
