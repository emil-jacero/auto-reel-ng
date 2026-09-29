## 1. api/ — error rows

- [x] 1.1 Add `EventFailure`, `EventErrorOut`, required `kind` on `EventSummaryOut`, and the discriminated `EventRowOut` to `api/schemas.py` (design "The row types"). Make the list route's `response_model` `List[EventRowOut]`. Verify with a new test in `tests/test_api_openapi.py` asserting:
  - the list's item schema is a `oneOf` with a `kind` discriminator
  - `kind` is required on both members
  - `EventFailure` is an enum of the three kinds
- [x] 1.2 In `api/events_read.list_events`, isolate each event (design "Classifying and isolating per event"): metadata error → `unusable_metadata`, other `ReelError` → `unparseable_reel_yaml`, `OSError` → `unreadable_disk`. Keep the detail route's `EventReadError` 502. Verify by rewriting `tests/test_api_events_failures.py` for the list:
  - one unparseable `reel.yaml` among three events gives 200, with two summaries and one error row of that kind
  - a `2004 - Yngve…` folder gives an `unusable_metadata` row whose detail mentions "year only"
  - an unreadable event directory (`chmod 000` on a tmp dir, restored in `finally`) gives `unreadable_disk`
  - the detail route's 404/502 are unchanged
  - the 503 database tests are unchanged
- [x] 1.3 Map a walk failure (`LayoutError`, `OSError` from `_list_event_refs`) to the scan-failure 502 in `routes/events.get_events` (design "Whole-list failures"). Verify with a test: a project whose walk root is unreadable returns a 502 `ProblemOut` rather than a 500.

## 2. Generated artifacts

- [x] 2.1 Regenerate `web/openapi.json` and `web/src/api/schema.d.ts` (the `web/README.md` commands). Verify:
  - `tests/test_api_openapi.py` passes
  - `schema.d.ts` shows `kind: "event"` and `kind: "error"` as non-optional
  - `tsc --noEmit` now **fails** in `web/` until task 3.1, which is the drift pipeline working

## 3. web/ — the screen

- [x] 3.1 Update `web/src/api/events.ts` (the `EventRow`, `EventError` and `EventFailure` aliases, with `ok` carrying `EventRow[]`) and `events/labels.ts` (`FAILURE_LABEL`). In `events/EventList.tsx`, partition by `kind` and render the "Needs attention" section first, extend the summary line, keep error rows visible under the filter, and simplify `describeProblem` (design "The screen"). Verify `npx tsc --noEmit` and `npm run build` pass in the node:22 container.

## 4. Dev library and docs

- [x] 4.1 Add `2024/2024-02-30 - Omöjligt datum` in phase 2 of `scripts/make_dev_library.py` (design "The dev library"), and update `web/README.md`'s dev-library bullets (10 events: 9 plus 1 needs-attention). In `README.md`'s API section, note that list rows carry `kind` and that error rows exist. Verify: rebuild the dev library, and the builder exits 0.

## 5. Verification

- [x] 5.1 With `auto-reel serve ../auto-reel-dev/library` and the Vite dev server running, open <http://127.0.0.1:5173/>. Verify:
  - "Needs attention" appears first, with `2024-02-30 - Omöjligt datum`, the metadata-kind words, and the detail naming `2024-02-30`
  - the summary reads "6 of 9 events need rendering · 1 needs attention"
  - the filter keeps the attention row
  - `podman stop auto-reel-ng-dev-db`, then refresh, still gives the database message; restart the database afterwards
- [x] 5.2 Run `.venv/bin/python -m black auto_reel_ng tests scripts && .venv/bin/python -m isort auto_reel_ng tests scripts`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, the full `.venv/bin/python -m pytest`, and `tsc --noEmit` plus `npm run build` in the container. Verify all are clean or green, apart from the known cairo `no-member` noise.
