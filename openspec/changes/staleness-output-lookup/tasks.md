## 1. Baseline and gate verdict

- [ ] 1.1 Confirm the code this change was designed against, and that its gates have merged. Stop and report if a
  check fails in a way the design does not cover.
  - `git log --oneline origin/main | grep -E "render-output-name-safety|render-progress-monotonic|name safety|monotonic"`
    shows both gate changes merged (or their archives exist under `openspec/changes/archive/`).
  - `grep -n "def output_filename" -A 16 auto_reel_ng/render/orchestrator.py` shows the name builder replacing path
    separators, so an output name is one path component. If it does not, stop: task 2.3 depends on it.
  - `grep -n "expected.exists()" auto_reel_ng/staleness/gate.py` hits `evaluate`;
    `grep -n "output_path.exists()" auto_reel_ng/cli/commands.py` hits `cmd_adopt_renders`;
    `grep -n "output_path.exists() and not options.overwrite" auto_reel_ng/render/orchestrator.py` hits
    `render_movie`. Re-base the MODIFIED blocks in `specs/` on the current spec text if a spec moved
    (`openspec validate staleness-output-lookup --strict`).

  Verify: every check holds, or the difference is in the final report.

- [ ] 1.2 Red first, in `tests/test_staleness_gate.py`, then green in `staleness/gate.py`: `evaluate()` counts only a
  regular file.
  - Replace `test_a_directory_at_the_expected_path_is_not_a_movie` with a test that the verdict cites `output`
    (stale, reasons `("output",)` for a fresh event) and `rendered_output` is `None`.
  - Add a case "folder at the expected path" to `MOVIE_CASES` so the invariant test
    `test_rendered_output_is_the_movie_the_verdict_counts` covers it (movie `None`, `output` cited).
  - Add a test: the retitled Grillning with a folder at its new path and its old movie kept cites
    `("editorial", "output_renamed")`.
  - In `test_a_recorded_value_naming_a_folder_is_never_looked_up`, the spy now also sees the expected path:
    assert `looked_up == [expected]` (nothing is stat'ed for the recorded value).
  - Change `if not expected.exists()` to `if not expected.is_file()`; drop the "accepted edge" paragraph from
    `rendered_output`'s docstring and say in `evaluate`'s that a non-file counts as absent. Leave the
    `StalenessReason` docstring untouched (it is published as the OpenAPI description).

  Verify: `.venv/bin/python -m pytest tests/test_staleness_gate.py` passes, and `tests/test_api_openapi.py` still
  passes (no schema drift).

## 2. By-design lookup, pinned

- [ ] 2.1 Test in `tests/test_staleness_gate.py`: a movie in another output directory is not looked for. Render the
  Grillning fixture into `out_a`, retitle it, and evaluate against `out_b/<new relpath>` (nothing in `out_b`). The
  verdict is `("editorial", "output")`. Spy `Path.is_file` and assert nothing under `out_a` is stat'ed.

  Verify: the test passes without any code change (it pins existing behaviour).

- [ ] 2.2 Test in `tests/test_staleness_gate.py`: a title with a path separator, built with `output_relpath` (never
  a hard-coded sanitised name), is found after a retitle. Write the movie at `out/output_relpath(old)`, a manifest
  recording `output_relpath(old).name`, retitle, and assert `("editorial", "output_renamed")` and that
  `rendered_output` returns the old movie. Also assert the old name is a single component:
  `PurePosixPath(old_name).name == old_name`.

  Verify: passes once the `render-output-name-safety` gate is merged (task 1.1 checks it).

- [ ] 2.3 Test in `tests/test_render_manifest.py` (real ffmpeg, like its neighbours): render an event whose title is
  `Mid/sommar`. `read_manifest(...).output` equals `result.output_path.name`, the output is one file directly under
  the year folder (`result.output_path.parent == out / "2024"` for a dated event, or `out` otherwise), and
  `evaluate(...)` for the unchanged event is fresh.

  Verify: `.venv/bin/python -m pytest tests/test_render_manifest.py`.

## 3. Render and adoption

- [ ] 3.1 Red first in `tests/test_render.py`, then green in `render/orchestrator.py`: `render_movie` refuses a
  non-file at its output path. Tests, each with a folder (holding a file) at the expected path:
  - with `overwrite=True` and with `overwrite=False`: `RenderError` naming the path; the folder and its file are
    unchanged; no `.part`, no manifest; the ffmpeg runtime was never invoked (a spy runtime that fails the test if
    `run` is called);
  - `dry_run=True` still returns the plan and creates nothing;
  - `render_batch` with the bad event and a renderable one: the first is a `BatchOutcome` error, the second renders.

  Add the guard immediately before the existing skip check, after the dry-run branch and after the containment
  assertion from `render-output-name-safety`.

  Verify: `.venv/bin/python -m pytest tests/test_render.py -k "non_file or folder"` passes.

- [ ] 3.2 Red first in `tests/test_cli_adopt_renders.py`, then green in `cli/commands.py`: a folder at the output
  path is "unrendered, nothing to adopt" and writes no manifest (with and without `--dry-run`, same totals). Change
  `output_path.exists()` to `output_path.is_file()` in `cmd_adopt_renders`.

  Verify: `.venv/bin/python -m pytest tests/test_cli_adopt_renders.py`.

## 4. The movie route and the docs

- [ ] 4.1 In `tests/test_api_media.py`, extend `test_a_directory_at_the_expected_path_is_not_the_movie` to assert the
  event's staleness verdict cites `output` as well, and extend the "movie exists exactly when the verdict cites
  neither `no_manifest` nor `output`" check (if the file has one over several events) with the folder event. Update
  `rendered_output`'s mention in `api/media.py` and `api/routes/media.py` docstrings only if they repeat the
  exception.

  Verify: `.venv/bin/python -m pytest tests/test_api_media.py tests/test_api_openapi.py`.

- [ ] 4.2 Docs, no behaviour:
  - `staleness/gate.py`: module and `_renamed_output` docstrings per design D5; `staleness/manifest.py`:
    `recorded_output_path` gains the one sentence on why the undated edge is unreachable.
  - `README.md`: the movie-route sentence ("a directory at the movie's path is answered as absent") now also says the
    event is stale (`output`) and that a render refuses it.
  - `docs/high-level-design.md` D-9: a dated amendment for the three points in design D5.

  Verify: `git grep -n "accepted edge\|directory at the movie" -- auto_reel_ng README.md docs` shows no stale
  statement; `openspec validate staleness-output-lookup --strict` passes.

## 5. Validation

- [ ] 5.1 Full suite and lint on the finished change: `.venv/bin/python -m pytest` (DB tests need podman),
  `.venv/bin/python -m black --check auto_reel_ng tests`, `.venv/bin/python -m isort --check auto_reel_ng tests`,
  `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` (cairo `no-member` noise only).
  `RENDER_GRAPH_VERSION` is not bumped.

  Verify: all pass; the final report names the one behaviour change (a folder at the movie path goes stale).
