## 1. api/ — job status typed with the persistence enum

- [x] 1.1 Annotate `JobSummaryOut.status`, `JobOut.status` and `CancelResult.status` in `api/schemas.py` as `JobStatus` (imported from `persistence/models.py`), per design "Where the job status vocabulary comes from". Verify:
  - a new test in `tests/test_api_openapi.py` asserts that all three fields reference the `JobStatus` schema component
  - the existing jobs, events and WS API tests pass unmodified (the wire values are unchanged)

## 2. api/ — the problem body in the schema

- [x] 2.1 Add `ProblemOut` to `api/schemas.py` (design "How the problem body reaches the schema"), and declare `responses=` on the `GET /api/v1/events` (502, 503) and `GET /api/v1/events/{event_id}` (404, 502, 503) decorators. Verify with a test asserting the generated schema lists exactly those status codes on each route, each referencing `ProblemOut`.
- [x] 2.2 Add a test that validates every problem body the two events reads can return against `ProblemOut.model_validate`: the 503 database body (`check == "database"`), the scan 502, the per-event 502 (`event_id` set) and the unknown-event 404. Build each through the same code path the existing failure tests in `tests/test_api_events_failures.py` use, and verify it passes.

## 3. Generated artifacts

- [x] 3.1 Regenerate `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and `web/src/api/schema.d.ts` (`npm run generate:types` in the node:22 container). Verify:
  - `tests/test_api_openapi.py` passes
  - `schema.d.ts` types `JobSummaryOut.status` as `components["schemas"]["JobStatus"]` and contains a `ProblemOut` schema
  - `npx tsc --noEmit` passes in the container

## 4. Validation

- [x] 4.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest` (including `requires_db`). Verify all are clean or green, apart from the known cairo `no-member` noise.
