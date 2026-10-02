Conventions for every task below:

- Python runs from the checkout root with `.venv/bin/python -m pytest` (never `.venv/bin/pytest`), with
  `TMPDIR` pointing at the change's own tmp directory (`/tmp` has a small quota). Node runs only in
  `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 ...`.
- A running service or a browser check uses only this change's port, database, dev library and scratch
  directory. Never the shared dev library, `auto-reel-media/`, or another change's resources.
- Run the validation gates (task 4.1) after each task, not only at the end.

## 1. Gate

- [x] 1.1 Confirm that `openspec/changes/archive/*-api-jobs-create-validation` and
  `*-api-excluded-clips-read-model` exist on `main`. If either does not, stop and report. Then re-read this
  change's design "Context" and "Gate" against the code the gates left:
  - `api/routes/jobs.py` `create_job`: the 404 / 502 / `document` it already holds before the active-job
    check, and where the active-job check now sits
  - `api/events_read.py` and `api/schemas.py`: the name and the place of `EventDetailOut.blocking_missing`'s
    computation (task 2.1 adapts to it), and any `blocking_missing_count` on the list
  - the web guards `missingClipsReason` / `MISSING_BLOCKS_ROW` and what feeds them
  - api-service "Jobs lifecycle over REST" and "Enqueue refuses an event whose output path another event
    claims", and web-app's two requirements this change leaves alone

  Re-base the two MODIFIED blocks in `specs/api-service/spec.md` on the archived text. They must differ
  from the archive only by these five edits: (1) "unless the output-collision check or the missing-clip
  check refuses it", (2) the `conflict` paragraph of "Jobs lifecycle over REST" naming `missing_clips`,
  (3) the `missing_clips` bullet of the vocabulary list, (4) "`conflict`, `claimed_by` and `missing`
  fields" in the 502 paragraph, (5) the vocabulary scenario's three members and `missing` list.

  Verify: every line of design "Context" still holds or the design is corrected, and
  `openspec validate api-jobs-missing-clips-refusal --strict` passes.

## 2. api/ — refuse a played, missing clip

- [x] 2.1 In `api/events_read.py`, add `played_missing_clips(event_dir, document)` beside the existing
  `blocking_missing(document, result)` (design "One definition of 'played and missing'"): it is
  `blocking_missing` over `reconcile(scan_event(event_dir).identities, document)`, as a list, and nothing
  else (no second statement of the exclude rule). Export it. Verify with new cases in
  `tests/test_api_events.py` (no database):
  - `reel.yaml` listing the present `00400.mp4`, the absent excluded `gone.mp4` and the absent
    non-excluded `gone2.mp4`: `played_missing_clips == ["gone2.mp4"]`, and the detail's `blocking_missing`
    is the same list while its `missing` still lists both
  - two absent clips, `gone-b.mp4` in the root chapter and `Kväll/gone-a.mp4` in `Kväll`: sorted
    `["Kväll/gone-a.mp4", "gone-b.mp4"]`
  - a NEW clip and an IGNORED clip on disk, nothing absent: `[]`
  - an event with no `reel.yaml` (seeded): `[]`
  - a listing that raises `OSError` propagates (not `[]`)
  - the existing events tests pass unchanged

- [x] 2.2 Add `EnqueueConflict.MISSING_CLIPS = "missing_clips"` and `ProblemOut.missing:
  Optional[List[str]]` (with the field comment of design "The 409 body") to `api/schemas.py`. Regenerate
  with the two commands of `web/README.md`: `.venv/bin/python -m auto_reel_ng.api.openapi >
  web/openapi.json`, then `npm run generate:types` in the node:22 container. Verify in
  `tests/test_api_openapi.py`:
  - the `conflict` component's `enum` is exactly `active_job`, `output_collision`, `missing_clips`
  - `missing` is an array of strings on the problem body
  - the schema staleness test passes
  - `grep` finds `missing_clips` and `missing?:` in `web/src/api/schema.d.ts`
  - `tsc --noEmit` now fails in `web/src/api/jobs.ts` at the `never` default (the intended signal for 3.1)

- [x] 2.3 In `create_job`, after the active-job check and before the staleness gate, call
  `events_read.played_missing_clips(event_dir, document)` with the `document` the route holds, and answer a
  non-empty result with the 409 of design "The 409 body". An `OSError` answers
  `bad_gateway(f"event scan failed: {exc}")`. `force` is not read by this step. Verify in
  `tests/test_api_jobs.py` (`requires_db`; each test builds its own event with a small `_reel` helper
  rather than extending the shared `project` fixture):
  - an event with the present `00400.mp4` and the absent `gone.mp4`: 409, `conflict == "missing_clips"`,
    `missing == ["gone.mp4"]`, `event_id` set, a detail naming `gone.mp4` and saying to restore it or
    remove it from `reel.yaml`; no job row, no manifest, and `reel.yaml` byte-for-byte unchanged
  - the same with `"force": true`: the same 409
  - `gone-b.mp4` and `Kväll/gone-a.mp4` absent: `missing` sorted `["Kväll/gone-a.mp4", "gone-b.mp4"]`
  - only an excluded absent `borta.mp4`: 201, one `queued` row
  - an excluded absent `borta.mp4` plus a non-excluded absent `saknas.mp4`: 409 with
    `missing == ["saknas.mp4"]`
  - a NEW and an IGNORED clip, nothing absent: 201
  - `store.enqueue(...)` first for the event with the absent clip: 409 `active_job` with that job's id
  - the dev-library Kalas pair (the file's `KALAS` / `KALAS_LOWER` helpers) where `kalas` also lists an
    absent clip: 409 `output_collision`
  - `events_read.played_missing_clips` monkeypatched to raise `PermissionError`: 502 and no row
  - `GET /api/v1/events/{id}` for the first event: its `blocking_missing` equals the refusal's `missing`
  - the existing jobs and collision tests pass unchanged

## 3. web/ — tell the refusal

- [x] 3.1 In `web/src/api/jobs.ts`, add the result kind `{ kind: 'missingClips'; missing: string[];
  problem: Problem }` and the `case 'missing_clips':` of the `conflict` switch: returned only when
  `body.missing` is a non-empty array of strings, otherwise `break` to the unpublished fallthrough. In
  `web/src/jobs/labels.ts`, add the words both screens use (design "The client"): the page's full list and
  the toast's first three plus a count. Verify with `tsc --noEmit` in the node:22 container passing
  (the `never` default of the `conflict` switch is cleared by the new case), and by deleting the new `case`
  once to see the same `tsc` fail there, then restoring it.

- [x] 3.2 In `web/src/jobs/RenderControl.tsx`, add the `missingClips` notice and its `Alert` (error tone,
  icon, the clip names, restore-or-remove-in-Edit-mode words), set from `handleEnqueue`, which then calls
  `markEventsChanged()` and `onFinishedRef.current()` so the page re-reads. No new state beyond the notice.
  End the `switch` over `result.kind` with an exhaustiveness check on `result` (the `never` pattern
  `enqueueJob` uses), which this switch lacks, so a future result kind fails `tsc` instead of being
  dropped. Verify with `tsc --noEmit` (and that removing the new `case` makes it fail) and in the browser
  run of 3.4 (page scenarios).

- [x] 3.3 In `web/src/jobs/LiveJobCell.tsx` `tellRowAnswer`, handle `missingClips`: `toast.error(...)` naming
  the event as the row's other toasts do, with the three-names words and the `Open` link, and
  `markEventsChanged()` so the list re-reads. End its `switch` with the same exhaustiveness check.
  Verify with `tsc --noEmit` (and that removing the new `case` makes it fail) and `npm run build` passing
  in the node:22 container.

- [x] 3.4 Verify both screens in a real browser (Playwright, scripts and screenshots only under the scratch
  directory; locators scoped to `main:not([hidden])`; `page.wait_for_timeout`, never `time.sleep`). Build a
  dev library with `scripts/make_dev_library.py` on this change's directory, serve it on this change's port
  and database, route only `**/api/v1/jobs` in the browser, and delete or rename a symlinked clip of the dev
  library only (never a file under `auto-reel-media/`). Check, in light and dark at 1280 and 390 px, and
  look at each screenshot:
  - the page of `2024/2024-06-27 - Grillning med grannar` open, a clip then unlinked, Render pressed: no
    job; the refusal names the clip; after the re-read neither Render nor Render anyway is offered and the
    clip is listed as missing; keyboard focus is on the render status, and no horizontal scroll at 390
  - the same, restoring the clip before the re-read: Render is offered again, pressing it sends one new
    request
  - the list with the same event's row: Render pressed after a clip was unlinked: an error toast with the
    title and date, the clip, and a link; the row then reads "Blocked by missing clips" with no Render
  - a 409 `missing_clips` with `missing: []` fulfilled by the route: the screen says the render was not
    queued with the status, and shows no job

## 4. Validation

- [x] 4.1 Run the validation gates and the web build:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng` (only the known cairo `no-member` noise)
  - `.venv/bin/python -m pytest` (full; podman for the `requires_db` tests)
  - `npx tsc --noEmit` and `npm run build` in the node:22 container

  Verify: all pass, `git diff --stat` shows no change under `render/`, `scheduler/` or
  `staleness/fingerprint.py` (`RENDER_GRAPH_VERSION` is untouched, as the proposal says), and
  `openspec validate api-jobs-missing-clips-refusal --strict` still passes.
