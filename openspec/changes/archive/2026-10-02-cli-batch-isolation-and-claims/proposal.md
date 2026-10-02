## Why

Principle I allows one softening: **one bad event MUST NOT kill a batch, but it MUST be reported as failed.**
Four CLI paths still break that rule or misreport, all reproduced or re-read on `origin/main` at `6a7fe16`
(Python 3.14.7):

- **`import` has no per-event isolation.** `cmd_import` loops `_import_event` with no `try`. `_read_yaml`
  and `_has_version` read with a bare `path.read_text(encoding="utf-8")`, and `_has_version` catches only
  `OSError`. Repro: a project with `2024-05-01 - Good/metadata.yaml`, `2024-05-02 - Bad/metadata.yaml`
  (bytes `ff fe fa`) and `2024-05-03 - Good2/metadata.yaml`: `auto-reel import <root>` writes
  `Good/reel.yaml`, prints `OK`, then dies with a raw `UnicodeDecodeError` traceback from `_read_yaml`;
  `Good2` is never imported and no summary line is printed. A malformed-YAML file (`YAMLError`) and a
  non-mapping file (`ValueError`) take the same path. `_has_version` on a malformed or non-UTF-8
  `reel.yaml` raises from inside `_legacy_source`, so the same abort happens before any import is tried.
- **`enqueue` classifies "already queued" from its own earlier read.** `cmd_enqueue` reads
  `store.active_job(...)`, then calls `store.enqueue(...)`, then prints `+ queued` or `= already queued`
  from the earlier read. `JobStore.submit` already returns `Submission(job_id, created)` from the insert's
  own unique-index verdict (its docstring: "the report is therefore the insertion's own verdict"), and
  `POST /api/v1/jobs` already uses it. Two concurrent `enqueue` runs can both read `None` and both print
  `+ queued` and count `created`; a job that finishes between the read and the insert prints `=` for a row
  that was in fact inserted. Found by code reading; a concurrent repro was not run.
- **Claimant selection raises in the CLI, and is quiet in the API.** `_checked_document` catches only
  `EventMetadataError` and `ReelError`. An event folder with mode `000` and no `reel.yaml` makes
  `load_event_document` raise `PermissionError` from `scan_event`, so `scan` (and `render`, `enqueue`,
  `adopt-renders`, which share the helper) end the whole batch with a traceback, while
  `events_read._output_claim` returns "claims nothing" for the same folder. The gate change
  `engine-output-claims` supplies one engine rule, `checked_claim`, with the union of both behaviours; the
  CLI adopts it here.
- **An unsearchable event folder seeds from its name.** On Python 3.14 `Path.exists()` swallows `EACCES`, so
  `scan`'s `(event_dir / REEL_FILENAME).exists()` (`commands.py:415`) and `import`'s three `exists()` calls
  read "the disk refused to answer" as "there is no file". The gate change `event-permission-errors`
  supplies `reel_exists`, which lets the `PermissionError` through; the CLI call sites adopt it here (the
  triage also names `adoption.py`, but it holds no `exists()` call on `main`: it only delegates to
  `load_event_document`, which the gate fixes).

This is bug-round work (2026-10-02) after HLD section 6 phase 8's start; it resolves no section 8 research
item and depends on none. It reuses D-9 (output identity) and the D-CLI isolation convention.

## What Changes

- `import`: each event is imported inside a per-event guard. A read, decode, YAML, shape, import or write
  failure prints `ERROR  <event>: <reason>`, the batch continues, and the command exits 1 if any event
  failed. One safe reader (UTF-8 read plus safe YAML load, raising on a non-mapping) serves `_read_yaml` and
  `_has_version`, so a malformed `reel.yaml` is an `ERROR` for its event and not a crash. The final summary
  line is always printed and states the failure count.
- `enqueue`: the pre-read and its "best effort" comment go. The command calls `JobStore.submit` and branches
  on `Submission.created` for both the printed line and the `created` count. The `active_job` docstring stops
  naming the CLI as a pre-read user (docstring only; no behaviour change in `persistence/`).
- `scan`, `render`, `enqueue`, `adopt-renders`: claimant selection (`_checked_document`) delegates to the
  engine's `checked_claim`, so an `OSError` from loading or seeding an event is a per-event `ERROR` line and a
  non-zero exit, never a traceback. The same step lists the event folder once, so a folder that holds a
  `reel.yaml` but cannot be listed (mode `0300`) fails there too instead of at the later `scan_event` inside
  fingerprinting or adoption. `scan`'s reel.yaml-presence test uses `reel_exists`.
- Specs (`headless-cli`): `import`, `enqueue` and `scan` requirements are MODIFIED with the isolation, the
  insertion-verdict and the unsearchable-folder rules.
- **Rendered output:** unchanged for identical inputs, no `RENDER_GRAPH_VERSION` bump. **Staleness
  fingerprint inputs:** unchanged. **Schemas:** no `reel.yaml` or `config.yaml` change, no Alembic migration,
  no rescan.

## Non-goals

- **No new engine code.** `checked_claim` (`engine-output-claims`) and `reel_exists` / strict `scan_event`
  (`event-permission-errors`) are consumed, not written, here. This change starts only after both and
  `cli-project-context-module` have merged.
- **No API change.** `events_read._output_claim` adopts `checked_claim` in `api-jobs-create-validation`.
- **No change to what collides.** `_output_collisions` keeps checking the selected events only, so `--years`
  still narrows the check, and keeps its wording.
- **Not the worker.** A job claimed for an unreadable event is `worker-claim-guards` /
  `worker-exception-backstop`.
- **No new flag, config key, dependency or `JobStore` method.** `JobStore.enqueue` stays for its other
  callers; only the CLI stops using it.
- **`import` does not change what it imports.** `import_legacy` and the `--overwrite` rule for a v2
  `reel.yaml` are unchanged; the `version` probe treats an empty or non-mapping `reel.yaml` as not v2
  (as before), and `--overwrite` skips the probe.
- **Other `reel.yaml` lookups.** `event/editorial.py` (the save path) and `api/events_read.py` (the read
  model) still use `Path.exists()`; they are API-side and out of scope here, owned by a later change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `headless-cli`: `Requirement: import adopts auto-reel legacy metadata` (per-event isolation, exit code,
  summary), `Requirement: enqueue records jobs without rendering` (the created/active report is the
  insertion's verdict), and `Requirement: scan/list reports inventory without rendering` (an event whose
  folder cannot be searched is an `ERROR`, not an empty or folder-seeded event).

## Impact

- **Packages:** `auto_reel_ng/cli` (`commands.py`; `cli/context.py` is where `cli-project-context-module` puts
  `project_context`, which this change calls but does not edit) and `auto_reel_ng/persistence` (one docstring
  in `job_store.py`). CLI only; the API is untouched (Principle V).
- **Tests:** new `tests/test_cli_import.py` and `tests/test_cli_enqueue.py`; additions to
  `tests/test_cli_output_collisions.py` and `tests/test_cli_commands.py`.
- **Baseline and gates:** re-based onto `origin/main` at `d683264`, where the three gate changes have merged;
  the design lists the interfaces consumed and tasks.md starts with a check of them.
- **Complexity (Principle VII):** no abstraction added. One private reader replaces two ad hoc ones;
  `_checked_document` shrinks to a call.
- **Size (Principle VIII):** one capability delta (three requirements), two packages, 8 tasks including the
  gates.
