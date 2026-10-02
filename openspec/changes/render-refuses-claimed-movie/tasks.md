## 1. staleness/ — what a recorded name means

- [x] 1.1 Red first, in `tests/test_render_manifest.py` and `tests/test_staleness_gate.py`: `recorded_movie_path`
  returns the year-folder path for a dated recorded name and the output-root path for an undated one, and `None`
  for `""`, `"."`, `".."` and a name with a separator; `records_output(event_dir, path)` is true for the exact
  file, true for a path differing only in case or Unicode normalisation, false for another year folder or another
  name, and false for an absent, malformed or wrong-version manifest; the existing `output_renamed` verdict
  scenarios stay unchanged. Verify they fail on the unchanged code.
- [x] 1.2 Add `recorded_movie_path` and `records_output` to `auto_reel_ng/staleness/manifest.py` as in the design,
  and make the gate's `_renamed_output` call `recorded_movie_path` instead of its inline name guard (the
  `recorded != expected.name` test and the `is_file()` stay in the gate). Verify the 1.1 tests pass and
  `.venv/bin/python -m pytest tests/test_staleness_gate.py tests/test_render_manifest.py` stays green.

## 2. render/ — the shared claim rule

- [x] 2.1 Red first, in `tests/test_render_claims.py` (scratch events on `tmp_path`, manifests written with
  `write_manifest`): `claimed_movie` returns the claimant(s), sorted by path, for a file another event records;
  returns `None` when the file does not exist, when only the event itself records it, when no manifest records
  it, when the other manifest is corrupt, and when it records `..`; still finds a claimant whose `reel.yaml` does
  not parse; matches a case-different name; and `claimed_movie_message` names the file, every claimant and the
  force hint. Verify they fail on the unchanged code.
- [x] 2.2 Add `ClaimedMovieError(EngineError)` to `auto_reel_ng/errors.py` and `ClaimedMovie`, `claimed_movie` and
  `claimed_movie_message` to `auto_reel_ng/render/claims.py`, exported from its `__all__`, with a module
  docstring line saying how this rule differs from `output_collision` (a recorded, not a current, path; bypassed
  by force). Verify the 2.1 tests pass.

## 3. cli/ — `render` refuses

- [x] 3.1 Red first, in `tests/test_cli_output_collisions.py` (stubbed engine, scratch project, as the file's
  existing helpers do): an unforced `render` of an event whose output file another event's manifest records
  prints `ERROR` naming that file and event, calls neither the probe nor the render stub for it, leaves the file
  and the event's `reel.yaml` byte-for-byte unchanged, renders a second renderable event, and exits non-zero;
  the same with `--force` renders it; `--dry-run` reports commands and is not refused; a fresh event is not
  checked; an output path nobody records renders as before; a layout where the claimant sits in another year
  folder is found. Verify they fail on the unchanged `cmd_render`.
- [x] 3.2 In `cmd_render` (`auto_reel_ng/cli/commands.py`), after the `_output_collisions` filter and before the
  build loop, refuse each remaining candidate with `claimed_movie` unless `args.force` or `args.dry_run`, adding it
  to `build_failures` with `claimed_movie_message` as `_output_collisions` entries are. Verify the 3.1 tests pass
  and `tests/test_cli_render.py tests/test_cli_render_staleness.py` stay green.

## 4. scheduler/ — the worker refuses

- [x] 4.1 Red first, in `tests/test_scheduler_worker.py` (`requires_db`, real Postgres, a scratch project on
  `tmp_path`, `default_build_job` as the build seam with a stubbed runtime and `process_next()`): a job without
  force for an event whose output file another event's manifest records ends `failed` with the shared message
  naming the other event by its path relative to `project_root`, the file is unchanged with no `.part`, and the
  job's `reel.yaml` is unchanged (a NEW clip is not adopted); the same job with `force=True` is not refused; an
  output path nobody records still renders; a project with an unknown layout fails the job with the layout error.
  Verify they fail on the unchanged worker.
- [x] 4.2 In `default_build_job` (`auto_reel_ng/scheduler/worker.py`), immediately after `_refuse_disk_collision`
  and before `prepare_and_persist`, unless `job.force`, call `claimed_movie` with the events of
  `get_layout(layout)(walk_root)` and raise `ClaimedMovieError` on a claimant, naming claimants with
  `_claimant_name`. Verify the 4.1 tests pass and the existing `tests/test_scheduler_worker.py` collision tests
  stay green.

## 5. Docs and gates

- [x] 5.1 Amend D-9 in `docs/high-level-design.md` (the sentence that says another event's render replaces the
  kept movie becomes the refusal, with force and the separate prune command), and correct the matching sentence
  in the `StalenessReason.OUTPUT_RENAMED` docstring in `auto_reel_ng/staleness/gate.py`. No test: wording only,
  checked by reading it against the spec.
- [x] 5.2 Run the validation gates: `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort
  auto_reel_ng tests`, `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the
  full `.venv/bin/python -m pytest` (with `TMPDIR` set), and confirm `RENDER_GRAPH_VERSION` is unchanged and no
  other test moved.
