## 1. Baseline

- [x] 1.1 Confirm the code this change was designed against, on `origin/main` after the gates: `event/claims.py`
  has `checked_claim`, `render/claims.py` has `output_collision`, `OutputCollision` and
  `output_collision_message` with the signatures in design.md; `worker.py` has the `except Exception` backstop
  around `_process_job`; `cli/build.py` has no missing-clip check; and the `job-scheduler` and `headless-cli`
  specs have no requirement named "A claimed job is refused while another running job writes its output" or
  "A referenced clip missing from disk fails its event by identity". Stop and report if a check fails in a way
  the design does not cover.

## 2. cli/ — a missing clip fails by identity

- [x] 2.1 Red first, in `tests/test_cli_render.py` (stubbed engine, a scratch project with the repo's
  existing helpers): an event whose `reel.yaml` lists `clip1.avi` and an absent `borttagen.mp4` makes `render`
  print `ERROR` for that event with the one-clip message, no `File does not exist` and no absolute path,
  render a second valid event, and exit non-zero; a four-clip event with two absent clips (one in a
  subfolder) names exactly those two in document order; an absent clip marked `exclude: true` renders
  normally; a dangling symlink is reported as missing; the probe stub is never called for a failing event.
  Verify they fail on the unchanged code.
- [x] 2.2 Add `MissingClipsError(EngineError)` to `auto_reel_ng/errors.py` and the pre-check and message to
  `_probe_clips` in `auto_reel_ng/cli/build.py` as in the design (`exists()`, document order, before any
  `probe_media`). Verify the 2.1 tests pass and `.venv/bin/python -m pytest tests/test_cli_render.py
  tests/test_cli_render_adoption.py` stays green.

## 3. scheduler/ — claim-time guards

- [x] 3.1 Red first, in `tests/test_scheduler_worker.py` (`requires_db`, real Postgres, a scratch project on
  `tmp_path`, `default_build_job` as the build seam with a stubbed runtime, `process_next()`): a job whose
  event has a `reel.yaml` edited, after enqueue, to the date and title of a sibling is `failed` with the
  shared sentence naming the output path and the sibling's event; the same with `force=True`; the sibling's
  job is refused too and an existing movie at the shared path is byte-for-byte unchanged with no `.part`; a
  NEW clip in the refused event is not adopted into `reel.yaml`; a third event with an unparseable
  `reel.yaml` does not change the outcome; a collision-free job still renders (stubbed `render`) and ends
  `done`; a project config naming an unknown layout fails the job with the layout error; a collision with a sibling in the
  claimed event's walk is reported by the event's path relative to `project_root`. Add the same job for
  an event whose clip is missing: the job error equals the text from 2.1. Verify they fail on the unchanged
  worker.
- [x] 3.2 Add `OutputCollisionError(EngineError)` to `auto_reel_ng/errors.py` and the claim-time check to
  `default_build_job` in `auto_reel_ng/scheduler/worker.py` as in the design (after `require_processable`,
  before `prepare_and_persist`, the claimed event's claimants named relative to `project_root`). Verify the
  3.1 tests pass and the existing `default_build_job` tests in the file are unchanged and green.
- [x] 3.3 Red first, same file: with a second `running` job for a different project whose
  `config.yaml` points at the same output directory and whose event resolves to the same path, the claimed
  job is `failed` naming the running job's event while the running job is not touched, also with `force=True`;
  a refused job's `reel.yaml` does not adopt a NEW clip and the build stub is never called; a running job with
  a different output does not refuse; the claimed job's own row is not counted; a running job whose event
  directory is gone claims nothing; after the running job ends the refused event can be enqueued again and
  renders. Verify they fail on the 3.2 worker.
- [x] 3.4 Add `_job_output` and `Worker._refuse_running_output` to `auto_reel_ng/scheduler/worker.py` as in
  the design (inside `_process_job`, in the build `try`, before `self._build_job`, using
  `JobStore.list_by_status(JobStatus.RUNNING)` and `find_output_collisions`). Verify the 3.3 tests pass, that a
  refusal acquires no capacity token (the cpu token is free afterwards), and
  `.venv/bin/python -m pytest tests/test_scheduler_worker.py` is green.

## 4. Docs

- [x] 4.1 Add one amendment sentence to **D-9** in `docs/high-level-design.md`: the worker applies the
  collision rule at claim time and refuses a job whose output another running job writes. Verify
  `grep -n "claim time" docs/high-level-design.md` shows it next to the gate's D-9 amendment.

## 5. Validation

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full
  `.venv/bin/python -m pytest` including `requires_db` (podman). Then run
  `openspec validate worker-claim-guards --strict`. Verify all are clean or green, apart from the known cairo
  `no-member` noise and the five font-dependent skips.
