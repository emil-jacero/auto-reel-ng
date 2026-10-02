## Why

`POST /api/v1/jobs` is the one write route a client reaches with an id it typed or built rather than
one `GET /api/v1/events` returned, and it is the last enqueue path that trusts that id and the event
behind it. The jobs-project-guards change left two of its follow-ups open (its Non-goals): canonical
event ids on enqueue, and the route's handling of its *own* unprocessable or unparseable event. The
claimant selection and the permission handling it leans on are the same rule composed in several
places. HLD §6 phase 8 (GUI v1 + editorial write API) puts a Render button on every event, so each of
these becomes one click away. All four were found on `main` at `6a7fe16` and re-checked on `main` at `d683264`, after their gates merged.

1. **A non-canonical event id is enqueued as an event of its own.** `create_job` resolves the id with
   `events_read.named_event_dir` (`api/routes/jobs.py:80`), which only requires a directory under the
   root; `event_id_for` is never compared with `payload.event_id`. With a project holding
   `2024/2024-06-21 - A`, `named_event_dir` accepts all of `2024/./2024-06-21 - A`,
   `2024/2024-06-21 - A/`, `2024/2024-06-21 - A/original`, `2024/2024-06-21 - A/../2024-06-21 - A`, `2024`
   (the year folder) and the empty id (the root); `listed_event_dir` refuses every one of them (checked
   against `6a7fe16` with a scratch project). A job stores the id verbatim as `event_dir`, and the one-active-job rule keys on the
   verbatim string, so the same folder can have several active jobs and several workers can render it at
   once. The GUI matches `job.event_dir === event_id`, so it never sees those jobs. The year folder and
   `original/` are not events at all, so their jobs can only fail in the worker. The media and thumbnail routes already refuse all of these
   spellings through `listed_event_dir`.
2. **`POST /api/v1/jobs` on an event it cannot process is a bare 500 or a doomed job.** `create_job` loads
   the event with `load_or_seed` (`jobs.py:113`) and never calls `require_processable`, which the CLI's
   `_checked_document` does. An event whose `reel.yaml` does not parse is a `ReelParseError` that nothing
   catches: the route answers a bare 500, while `GET /api/v1/events/{id}` for the same event answers 502
   with `failure: unparseable_reel_yaml`. An event with no date or title (`2024/NoDate`; the events list
   shows it as an error row) is enqueued with 201 and fails later in the worker. `ProblemOut` already
   carries `event_id` and `failure`, and `502` is already declared on the route.
3. **The output-collision claimants are selected twice, differently.** "Load, require processable, a
   failure claims nothing" is `cli/_checked_document` (catches `ReelError` only) and the API's
   `_output_claim` (catches `ReelError`, `OSError` and `ValueError`). They differ on `OSError`: a sibling
   folder that cannot be searched makes `auto-reel scan` die with a `PermissionError` traceback, while
   the API skips it as a claimant. `engine-output-claims` adds the one engine function
   (`checked_claim`, and a layout-aware `output_collision` in `render/claims.py`) but migrates no caller;
   `api/events_read.py` is the API's copy, and this change retires it. The CLI's copy is migrated by
   `cli-batch-isolation-and-claims`.
4. **A readable but unsearchable event folder reads as "no reel.yaml".** `GET /api/v1/events/{id}/reel`
   tests `(event_dir / "reel.yaml").exists()` (`events_read.py:483`), and on Python 3.14 `Path.exists()`
   swallows `EACCES`. For a folder with mode `0600` holding a `reel.yaml`, the read answers 200 with the
   empty editorial document, and a client that then edits and saves it has been shown a document it did not
   author. `event-permission-errors` adds `reel_exists`, which lets `PermissionError` through; this
   `exists()` site is the API's.

## What Changes

- **`POST /api/v1/jobs` names an event the events list shows, spelled as the list spells it.** The route
  resolves the id with `listed_event_dir` instead of `named_event_dir`. Any other spelling, and any folder
  the list does not show (the root, a year folder, `original/`, a chapter folder, a `.reelignore`d event,
  a folder outside `input`), answers the 404 an unknown event gets, and nothing is enqueued. A year folder
  that cannot be listed is the scan-failure 502 it already is for the collision walk.
- **An event the route cannot process is refused before anything else.** After the lookup the route loads
  the event's document and requires it processable, once, and answers the scan-failure 502 with the
  `event_id` and the failure kind the events list gives that event: `unparseable_reel_yaml`,
  `unusable_metadata` (no real date or title, or a future date) or `unreadable_disk`. No job row, no
  manifest. The loaded document is the one the fingerprint is computed from, so the event is read once.
- **One claimant rule.** `events_read._output_claim` and the walk in `output_collision` are replaced by the
  engine's `checked_claim` / `output_collision` from `engine-output-claims`. The service and the CLI
  select claimants with one function. The `ValueError` guard goes with the duplicate.
- **`GET /api/v1/events/{id}/reel` fails loud on an unsearchable folder.** The existence test uses
  `reel_exists` inside the read's error handling, so a `PermissionError` is the scan-failure 502 with
  `unreadable_disk`, never the empty document.
- **The jobs-project-guards test about folders outside the walk is replaced.** An unlisted folder is a 404
  now, not a collision case (the "named event the walk does not reach still collides" test).

**BREAKING (wire, intended):**

- `POST /jobs` with an id the list does not show: 201 (or 409 or 200) becomes 404.
- `POST /jobs` for an unparseable event: 500 becomes 502. For an unprocessable event: 201 becomes 502.
- An unprocessable event that also has an active job is a 502, no longer the 409 "active job": a failing
  event claims no path, so the collision check cannot apply, and its job could not render. Nothing is
  enqueued either way.
- `GET /events/{id}/reel` on an unsearchable folder: 200 empty document becomes 502.

## Non-goals

- **No refusal of an event with missing clips.** That is a typed 409 `missing_clips`, in
  `api-jobs-missing-clips-refusal`.
- **No database 503 on the jobs routes.** That is `api-jobs-db-outage-503`, which merges first and owns the
  route wrapper this change's code sits inside.
- **No new engine functions.** `checked_claim` / `output_collision` (`engine-output-claims`) and
  `reel_exists` (`event-permission-errors`) are used as they merged; this change adds no code to `event/`,
  `render/` or `cli/`.
- **No change to the CLI.** Its `_checked_document` and `reel.yaml` existence sites are migrated by
  `cli-batch-isolation-and-claims`; `adoption.py` and `editorial.py` by their own changes.
- **No claim-time recheck in the worker** (`worker-claim-guards`), and no event-list collision flag.
- **No rendered-output change.** A stricter lookup and an earlier refusal change which requests enqueue,
  never what a render writes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - ADDED `Requirement: Enqueue names an event the events list shows and refuses one it cannot process`:
    the listed-id 404, the up-front processable check and its 502, the order of the checks.
  - MODIFIED `Requirement: Enqueue refuses an event whose output path another event claims`: re-based on
    the current text. The claimants are selected by the one engine rule the CLI shares, and the named
    event is always one of the listed events and is checked for processability first.
  - MODIFIED `Requirement: Editorial document read endpoint`: an `reel.yaml` or event folder that cannot be
    searched or read is the scan-failure 502 with `unreadable_disk`, never the empty document.

## Impact

- **Gates (all merged into `origin/main` first):** `event-permission-errors` (`reel_exists`; unsearchable
  folder errors), `engine-output-claims` (`checked_claim`, `output_collision`), `api-jobs-db-outage-503`
  (the jobs routes' `SQLAlchemyError` wrapper in `api/routes/jobs.py`), `api-event-lookup-scope`
  (`events_read.py`: `get_analysis`, which this change does not touch). Task 1.1 re-reads each against the
  code and the specs before any edit.
- **Packages:** `api/` only: `routes/jobs.py` (the lookup, the processable check, the 502) and
  `events_read.py` (the enqueue read-model function, the claim delegation, the `reel_exists` site). No
  other package is edited.
- **CLI vs API (Principle V):** the claimant rule becomes the engine's, which the CLI also calls; what the
  API adds is request shaping (404 / 502 mapping). The service now selects claimants with the rule
  `headless-cli` already states for every surface; `auto-reel enqueue <root>` follows when
  `cli-batch-isolation-and-claims` migrates `_checked_document`, which this change leaves alone.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change; **no Alembic migration**, no rescan. No
  `ProblemOut` change and no new status code: the route already declares 404 and 502, so
  `web/openapi.json` and `web/src/api/schema.d.ts` do not change.
- **Idempotency:** a refused request writes nothing; the same request after the cause is fixed behaves as
  a fresh request. An accepted request is unchanged: the active-job rule, the gate and `store.submit`
  stay as they are, and now key only on the one canonical id of an event.
- **Size (Principle VIII):** one route, one read-model function, one capability delta set (three
  requirements), one package, seven tasks.
