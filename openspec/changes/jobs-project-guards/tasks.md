## 1. Gate

- [ ] 1.1 Confirm that `openspec/changes/archive/*-jobs-client-contract` exists on `main`. If it does not, stop and report. Then re-read the following against this change's design "Context":
  - `api/routes/jobs.py` and `api/schemas.py` (`ProblemOut`) as C2 left them
  - the store verbs the routes and the hub now call (`submit`, `cancel`, and `list_finished_since`, the read the hub uses for jobs that became terminal since the previous tick)
  - api-service's "Jobs lifecycle over REST" and "WebSocket live job updates"
  - job-store's "Query jobs"
  - C2's tests that this change meets: the exact-responses case for `POST /api/v1/jobs` in `tests/test_api_openapi.py` (C2 task 3.4), the stale-read cancel test in `tests/test_api_jobs.py` (C2 task 3.2: the app's `store.get` is monkeypatched to return a stale `queued` copy of a job the store holds as `running`), and every `JobsHub(...)` in `tests/test_api_ws_hub.py`, including C2's `cancel_requested` and terminal-since-previous-tick hub tests

  Confirm five things:
  - the active-job 409 (pre-check and enqueue race) carries `job_id`
  - the jobs 404s carry `job_id`
  - this change's two MODIFIED blocks are re-based on the archived text: api-service "Jobs lifecycle over REST" differs from it only by "unless the output-collision check refuses it", the `conflict` paragraph and the `conflict` / "collides with nothing" words in three scenarios; job-store "Query jobs" differs only by the project-root paragraph (both listings) and the three project scenarios
  - the stale copy in C2's stale-read cancel test carries the served project root (it was created through the app or with `str(settings.project_root)`), so it passes unchanged through `_served_job`
  - the C2 tests above exist

  Verify: every line reference used by the tasks below still points at the code it names, or the design
  has been corrected, and `openspec validate jobs-project-guards --strict` passes.

## 2. persistence/ — project-scoped listing

- [ ] 2.1 Give `JobStore.list_by_status` and C2's `JobStore.list_finished_since` a keyword-only `project_root: Optional[str] = None` filter (design "Project scoping at the store"). Verify with new `requires_db` tests in `tests/test_job_store.py`:
  - `queued` jobs for `2024/Blandat` under `/dev/a/library` and `/dev/b/library`: the listing narrowed to `/dev/a/library` returns only its own job
  - the same listing without the filter returns both, oldest first
  - a row inserted with `project_root` NULL (through `session_scope`) is absent from the narrowed listing and present in the unnarrowed one
  - `2024/2024-10-05 - Trasig` jobs under both roots, both transitioned to `failed` after a `list_finished_since` read returned `as_of` `T`: the read from `T` (no overlap) narrowed to `/dev/a/library` returns only `/dev/a/library`'s job, and unnarrowed returns both
  - the existing `list_by_status` and `list_finished_since` tests pass unchanged

## 3. api/ — output collisions on enqueue

- [ ] 3.1 Add `EnqueueConflict` (`active_job`, `output_collision`) and the `ProblemOut.conflict` and `ProblemOut.claimed_by` fields to `api/schemas.py`. Set `conflict=active_job` on both of C2's active-job 409s (design "The conflict vocabulary and its owner"). Verify in `tests/test_api_jobs.py`:
  - the duplicate-enqueue 409 carries `conflict == "active_job"` and the first job's `job_id`
  - C2's race test (the pre-check patched to miss a queued job) also answers `conflict == "active_job"`
  - the existing assertions still hold
- [ ] 3.2 Add `OutputCollision` and `output_collision(settings, event_dir, *, today)` to `api/events_read.py` (design "Which events claim a path"). The ids come from `event_id_for` on the walk's own paths. Verify with a new `tests/test_api_output_collision.py`, which needs no database and builds a project with its own `_touch`:
  - `2024/2024-07-14 - Kalas` with `2024/2024-07-14 - kalas`:
    - for `kalas`, the result is `output_path == 2024/2024-07-14 - kalas.mp4` with `claimed_by == ("2024/2024-07-14 - Kalas",)`
    - the reverse also holds
  - three same-named events give two sorted claimants
  - `2024-07-14 - Kalas` beside `2024-07-15 - Kalas` gives `None`
  - a sibling `2024/2024-02-30 - Omöjligt datum`, and a sibling whose `reel.yaml` is `": ["`, are skipped without raising
  - a named event that is itself unprocessable gives `None`
  - the named event passed as a folder the walk does not reach (outside the `input` that `config.yaml` sets) still collides with its twin, whose id carries the `input/` prefix
  - a twin that is a symlinked event folder pointing outside the project root is named by its in-root id and raises nothing
  - a year folder with mode `000` (restored in `finally`; skipped as root) raises `OSError`
- [ ] 3.3 Wire the check into `create_job` before the active-job check, with the 502 on a failed walk, and add `502` to its `responses=` (design "Order of the checks, and the answers"). Then regenerate `web/openapi.json` and `web/src/api/schema.d.ts` with the `web/README.md` commands.

  Verify in `tests/test_api_jobs.py`, adding the two Kalas folders inside these tests rather than to the shared `project` fixture:
  - `POST` for `kalas`: 409, `conflict == "output_collision"`, `claimed_by == ["2024/2024-07-14 - Kalas"]`, the detail contains `2024/2024-07-14 - kalas.mp4` and `set a distinct title or location in reel.yaml`, and no row is inserted
  - the same with `"force": true`
  - `Kalas`, made fresh with `_adopt_and_write_manifest` (which also writes its output file): 409, not 200, the output file's bytes unchanged, and no row inserted
  - `2024/2024-06-21 - A`: still 201
  - a year folder with mode `000`: 502, and no row inserted

  Also verify:
  - `tests/test_api_openapi.py` gains a case asserting that `conflict` references the `EnqueueConflict` component, whose `enum` is exactly the two values, and that `claimed_by` is an array of strings
  - C2's exact-responses case for `POST /api/v1/jobs` now expects `502` (`ProblemOut`) as well, and `EXPECTED_MODELS` gains `EnqueueConflict`
  - the schema staleness test passes
  - `npx tsc --noEmit` passes in the node:22 container with no client change, and `grep` finds `EnqueueConflict` and `claimed_by` in `web/src/api/schema.d.ts`
  - `tests/test_cli_output_collisions.py` and `tests/test_cli_jobs.py::test_enqueue_refuses_colliding_events` pass unchanged
  - one `output_collision` call is timed read-only (it writes nothing) against the MOL archive if it is mounted, otherwise against the dev library, and the number is recorded in the design's Risks

## 4. api/ — the served project only

- [ ] 4.1 Scope `GET /jobs` (with the store filter) and `GET /jobs/{id}` and cancel (with `_served_job`) to `str(settings.project_root)` (design "Scoping detail, cancel and the WebSocket"). Verify in `tests/test_api_jobs.py`, with a foreign job created by `store.enqueue("/elsewhere/library", "2024/Blandat")`:
  - the foreign job is absent from `GET /jobs` and from `GET /jobs?status=queued`
  - `GET /jobs/{its id}` answers 404 with the same body shape as an unknown id
  - cancelling it answers 404, and the row is still `queued` with `cancel_requested` false
  - the project's own jobs list, show and cancel exactly as before
  - C2's stale-read cancel test (C2 task 3.2) passes unchanged with the project-scoped lookup: `_served_job` reads the stale `queued` copy, and the cancel still answers `flagged-running` with status `running`
- [ ] 4.2 Give `JobsHub` a required keyword-only `project_root`, pass it through `functools.partial` to both hub reads (`_fetch_active_snapshot`'s `list_by_status`, and C2's `list_finished_since` at poller start and on every tick), and wire it in `create_app` from `settings.project_root` (design "Scoping detail, cancel and the WebSocket"). Verify in `tests/test_api_ws_hub.py`, where `FakeStore`'s two listings gain the keyword and filter on it, and every existing `JobsHub(...)` there (C2's included) gains `project_root="/proj"`:
  - with a running job under `/proj` and one under `/other`, the snapshot holds only `/proj`'s job
  - advancing `/other`'s progress and then finishing it produces no delta
  - a `/other` job for `2024/2024-10-05 - Trasig` inserted already `failed` between two ticks (never in any snapshot) produces no delta, while the same for `/proj` produces exactly one delta with status `failed`
  - `/proj`'s deltas are unchanged
  - the existing hub tests and `tests/test_api_ws_e2e.py` pass

## 5. Docs

- [ ] 5.1 Update the docs:
  - In `README.md`'s API service section, add the collision 409 on `POST /api/v1/jobs` (`conflict`, `claimed_by`, force does not override), the 502 on a failed walk, and that the jobs routes and `WS /api/v1/ws/jobs` show only the served project's jobs while `auto-reel jobs` and the worker stay database-wide.
  - In `docs/high-level-design.md`, add `POST /api/v1/jobs` to D-9's list of refusing commands, and add one line to §4.9: "the service serves one project; its jobs views are scoped to it; the queue is shared".

  Verify by rereading both against the specs.

## 6. Validation

- [ ] 6.1 Verify against the dev library, with no worker running. Use a database of this change's own and a dev library of its own (dev-env runbook §9, `SLUG=jobs-project-guards`, `N=3`), served with `auto-reel serve $DEV/library --port 8103`. Use `curl`, plus one short `.venv/bin/python -c` script for the WebSocket. Never touch `../auto-reel-dev`, `auto-reel-media/` or port 8080. Verify each response:
  - `POST /api/v1/jobs` `{"event_id": "2024/2024-07-14 - kalas"}` answers 409 `output_collision` with `claimed_by` `["2024/2024-07-14 - Kalas"]`
  - the same request for `2024/2024-07-14 - Kalas`, with and without `"force": true`, answers 409 `output_collision`, and `$DEV/library-output/2024/2024-07-14 - Kalas.mp4` keeps its `sha256sum`
  - `2024/Blandat` answers 409 `active_job` with the queued job's `job_id`
  - `2024/2024-06-27 - Grillning med grannar` answers 201. Its cancel then answers C2's `canceled-queued`.
  - A job is created for a foreign root with `.venv/bin/python -c`: a `JobStore.enqueue("/tmp/other-library", "2024/Blandat")` on the same `DATABASE_URL`. It is only a database row, and no folder is created. That job:
    - is absent from `GET /api/v1/jobs`
    - answers 404 on `GET /api/v1/jobs/{id}` and on cancel
    - is absent from the first frame of `ws://127.0.0.1:8103/api/v1/ws/jobs`, a `snapshot` that lists this library's `2024/Blandat` job. Read the frame with the installed `websockets` package.
    - is still `queued` according to `auto-reel jobs show $DEV/library <id>`
  - With that WebSocket still open, cancel the foreign job with `auto-reel jobs cancel $DEV/library <id>` (so no later worker on this database claims it). It becomes terminal between two polls without ever being in a frame; no frame naming its id arrives within 3 s (the hub's terminal-since-previous-tick read is scoped too).
- [ ] 6.2 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`, including `requires_db`. Verify that all are clean or green, apart from the known cairo `no-member` noise.
