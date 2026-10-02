## Why

The output-collision rule (HLD §4.3, **D-9**) says which events *claim* an output path, and that is decided
twice, by two functions that do not agree, and not at all in the third place that needs it:

- `cli/commands.py` `_checked_document` selects claimants for `render`, `scan`, `enqueue` and `adopt-renders`.
  It maps `ReelError` and `EventMetadataError` to a per-event reason and nothing else.
  `api/events_read.py` `_output_claim` selects them for `POST /api/v1/jobs` and also maps `OSError` (and a
  `ValueError` guard) to "claims nothing". The api-service spec already says an event "whose files cannot be
  listed ... SHALL claim no path"; the headless-cli spec says nothing for that case. Reproduced on `main` at
  `6a7fe16` (Python 3.14.7): an event folder with permissions `000` and no `reel.yaml` makes
  `load_event_document` raise `PermissionError` from `scan_event` (`_video_identities` → `directory.iterdir()`).
  In the CLI that is the uncaught traceback of `scan` (`commands.py:408` → `_checked_document`) and aborts the
  whole batch; the same folder in the API is a quiet "claims nothing". This is the opposite of Principle I's
  one tolerated softening: *one bad event MUST NOT kill a batch, but it MUST be reported as failed.*
- The worker has **no** collision check. `find_output_collisions` is called from `cli/commands.py` and from
  `api/events_read.py` only; `scheduler/` never calls it. The worker rebuilds the plan from disk at claim time
  (job-scheduler: "Worker claims jobs and rebuilds the plan at claim time") and renders with
  `overwrite=True`. So two jobs enqueued with distinct output paths, where one event's `reel.yaml` is then
  edited to the other's title and date, are both claimable and both render to the same file and the same
  `<output>.part` (`orchestrator._part_path`). One movie silently replaces the other, or two concurrent
  renders corrupt the one `.part`. The enqueue-time refusal cannot see an edit made afterwards (and has a
  plain TOCTOU against a concurrent enqueue). Static reasoning from the code; not executed, as it needs the
  layout walk plus a real database.

Both come from one gap: the rule exists only as caller-private code that is welded to `ApiSettings` (API) or
to `ProjectContext` (CLI). The fix is one engine rule that the CLI, the API and the worker can all call.
Principle V (engine first, thin API) and the project's own `headless-cli` and api-service specs already
promise the same behaviour on every surface; this change makes that promise true in one place.

This belongs to the 2026-10-02 bug round after HLD §6 phase 8; it depends on no open §8 research item.

## What Changes

- **A shared claim-selection rule in the engine** (`event/claims.py`): `checked_claim(event_dir, *, order,
  today)` loads the event (reel.yaml, or a folder seed), applies the processable-event rule, and returns
  either the document or a reason. `ReelError` (including `EventMetadataError`), `OSError` and `ValueError`
  all become a reason; **a failure claims nothing and is reported, never raised**. This is the union of the
  two current rules, so the CLI gains the API's tolerance and the API loses nothing.
- **A shared, layout-aware collision check in the engine** (`render/claims.py`): `output_collision(event_dir,
  *, walk_root, layout, order, today)` answers "which other events of this project claim the output path of
  `event_dir`?". It takes no `ApiSettings` and no CLI context, only what a worker also has: the walk root,
  the layout name and the clip order. It is the API's current algorithm (named event plus every walked event,
  compared by `render.find_output_collisions`) with `Path` keys. `output_collision_message(...)` holds the
  one wording of the refusal that the CLI, the API and the worker print.
- **Specs** state the rule once: `headless-cli` says which events claim a path and that an unreadable event
  fails on its own like a malformed `reel.yaml` (so a `chmod 000` sibling is a per-event `ERROR`, not a crash);
  `job-scheduler` says the worker applies the rule at claim time, before the staleness recheck, and fails the
  job with the collision reason.
- **Tests:** `tests/test_event_claims.py` and `tests/test_render_claims.py` (real temp project trees, including
  a `chmod 000` sibling and the "edited into a collision after enqueue" case).
- **HLD:** D-9 gains an amendment line recording that the claim rule is one engine function.
- **Delivery split (named, gated).** The call sites adopt this in their own changes, each of which is gated on
  this one and edits files that are in other serial chains: `cli-batch-isolation-and-claims` (`cli/commands.py`),
  `api-jobs-create-validation` (`api/events_read.py`) and `worker-claim-guards` (`scheduler/worker.py`). This
  change edits none of them. The observable CLI, API and worker behaviour in the spec deltas is therefore
  delivered by those three changes, which verify it at their own surface and add no duplicate delta (design,
  "Hand-off to the call-site changes").

## Non-goals

- **No call-site change.** `cli/`, `api/` and `scheduler/` are untouched; no existing test is edited. The
  engine functions have no caller until the three follow-ups land.
- **No change to what collides.** `render.find_output_collisions` and `render.output_relpath` are used
  unchanged (case-insensitive, NFC-normalised, never auto-suffixed). `render/orchestrator.py` is not edited:
  it is the head of the `render-output-name-safety` serial chain.
- **No "another RUNNING job has the same output" guard.** That reads the job store, so it is a scheduler
  concern and belongs to `worker-claim-guards`; this change gives it the claim-time collision rule only.
- **No change to the CLI's selection semantics.** `--years` still narrows what a *command* selects; the
  worker and the API check the whole project, as they do today. `output_collision` takes no years.
- **Not the unsearchable-folder seeding bug.** An event folder with a `reel.yaml` but no search permission
  being seeded from its folder name is `event-permission-errors` (it edits `event/metadata.py` and
  `event/discovery.py`). `checked_claim` is written to be correct before and after that change, because it
  catches `OSError` whichever loader raises it.
- **No new config key, flag, dependency, schema or migration.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `headless-cli`: `Requirement: Batch commands refuse colliding output paths` states which events claim a path
  (only an event that loads and is processable) and that an event that fails to load claims none and does not
  fail another event's check. `Requirement: An event without a real date and title fails on its own` extends
  its per-event isolation to an event whose folder or `reel.yaml` cannot be read.
- `job-scheduler`: new `Requirement: Claim-time output-collision recheck`: the worker applies the same rule
  before the staleness recheck and fails a colliding job with the shared reason. (The change-detection
  capability listed in the triage is not touched: its only mention of the collision check is the informative
  clause in "A renamed event keeps its previous movie", which stays true.)

## Impact

- **Baseline:** written against `origin/main` at `6a7fe16`.
- **Packages:** `event/` (new `claims.py`) and `render/` (new `claims.py`). Both are new files; no existing
  source file is edited, and the packages' `__init__.py` files are not touched (callers import the
  submodules, which keeps this change off the shared export lists). Tests: two new files. Docs:
  `docs/high-level-design.md` D-9.
- **CLI vs API (Principle V):** neither surface changes in this change. This is an extraction of a rule that
  already exists on two surfaces, not a new capability; the CLI surface of the extraction is
  `cli-batch-isolation-and-claims`, gated on this change.
- **Layering (Principle VI):** `event/claims.py` imports only `event/` and `reel/`. The layout-aware check
  imports `ingest/`, which itself imports `event/`, and `render.output_relpath`, so it must sit in `render/`,
  not `event/`: an `event/` module importing `render/` would have a lower layer import a higher one (design,
  "Why two modules").
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Staleness fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. OpenAPI schema
  and `web/` unchanged.
- **Complexity (Principle VII):** two small functions and one dataclass, replacing two private copies of the
  rule once adopted. No option bag, no plugin hook.
- **Size (Principle VIII):** two capability deltas, two packages, 8 tasks (two validation).
