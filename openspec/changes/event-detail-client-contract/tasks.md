## 1. event/ + api/ — the clip status vocabulary

- [ ] 1.1 Make `ClipStatus` a `StrEnum` in `event/reconcile.py`. Type `ClipOut.status` as `ClipStatus` in `api/schemas.py`, and pass the member from `api/events_read._clip_out` (design "The clip status vocabulary"). Verify:
  - a new `tests/test_api_openapi.py` case asserts `ClipOut.status` references the `ClipStatus` schema component, with exactly `new`/`active`/`missing`/`ignored`
  - `tests/test_event_reconcile.py`, `tests/test_api_events.py` and `tests/test_cli_commands.py` pass unmodified (wire values unchanged)

## 2. api/ — one failure classification for both reads

- [ ] 2.1 Add `classify_event_failure` to `api/events_read.py`, and route `list_events`' per-event handling through it (design "One classifier for both reads"). Verify the existing list error-row tests in `tests/test_api_events_failures.py` pass unmodified.
- [ ] 2.2 Give `EventReadError` an optional `failure`, and make `get_event` catch `(ReelError, OSError)` after `resolve_event_dir` and classify. Add `failure: Optional[EventFailure]` to `ProblemOut`, and have the detail route put `failure` into its 502 body, with `detail` as the engine's unprefixed text (design "One classifier…"). Verify with `tests/test_api_events_failures.py`:
  - an unparseable `reel.yaml` detail gives a 502 with `failure == "unparseable_reel_yaml"` and `event_id` set
  - a `2019-04-31 - …` folder gives a 502 with `unusable_metadata`
  - an unreadable event directory gives a 502 with `unreadable_disk`, where it was a 500 before
  - an unknown ID still gives a 404
  - the database-down detail is still the 503 with `check == "database"`
  - every 502 body validates against `ProblemOut`
- [ ] 2.3 Add the agreement test (design "Test for the list/detail agreement"): for each of the three broken events, the list's error row and the detail's 502 have equal `failure` and equal detail. Verify it passes.

## 3. Generated artifacts and docs

- [ ] 3.1 Regenerate `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and `web/src/api/schema.d.ts` (`npm run generate:types` in the node:22 container). Verify:
  - `tests/test_api_openapi.py` passes
  - `schema.d.ts` types `ClipOut.status` as `components["schemas"]["ClipStatus"]`, and `ProblemOut.failure` as the `EventFailure` union (nullable)
  - `npx tsc --noEmit` passes with no client change
- [ ] 3.2 In `README.md`'s API section, add one line each: a clip's `status` is one of the four values, and the detail's 502 carries the same `failure` kind as the list's error row. Verify by rereading it against the spec.

## 4. Validation

- [ ] 4.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`, including `requires_db`. Verify all are clean or green, apart from the known cairo `no-member` noise.
