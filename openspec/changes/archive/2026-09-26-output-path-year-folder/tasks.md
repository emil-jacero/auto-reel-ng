## 1. render/ — the path rule and collision finder

- [x] 1.1 Add `output_relpath(metadata) -> PurePosixPath` beside `output_filename` in `render/orchestrator.py`, and export it from `auto_reel_ng.render` (design D-O1). Verify with new cases in `tests/test_render.py`:
  - `2024-06-21` / `Midsummer` / `Dalarna` → `2024/Midsummer - Dalarna.mp4`
  - no location → `2023/Julafton.mp4`
  - no date → the bare `Sommarlov.mp4`
  - the existing `output_filename` test still passes
- [x] 1.2 Add `find_output_collisions(claims)` (NFC + `casefold` comparison key, pure, per design D-O2). Verify with unit tests covering:
  - two same-year claims collide and each maps to the other
  - `Midsommar.mp4` vs `midsommar.mp4` collide
  - NFC `Göteborg` vs NFD `Göteborg` collide
  - the same name in 2023 vs 2024 does not collide
  - a three-way collision lists both others for each key
  - no collisions → an empty result
- [x] 1.3 Make `render_movie` finalize to `output_dir / output_relpath(...)`, and make `_execute` create `output_path.parent` instead of `output_dir` (design D-O3). Verify with a `has_ffmpeg` test (lavfi clip, dated event, no `2024/` folder yet): the movie lands in `<out>/2024/`, `.part` is created in `<out>/2024/`, and a dry-run of the same event creates no `2024/` folder.

## 2. Call sites — mechanical swap

- [x] 2.1 Replace `output_dir / output_filename(...)` with `output_dir / output_relpath(...)` at every site in design §Context:
  - `cli/commands.py`: `_staleness_filter`, `cmd_scan`, `cmd_enqueue`, `cmd_adopt_renders`
  - `scheduler/worker.py`: the claim-time recheck
  - `api/events_read.py`: `staleness_for`
  - `api/routes/jobs.py`
  - the tests that build `project / "output" / output_filename(...)`: `test_cli_jobs.py`, `test_api_editorial_write.py`, `test_api_jobs.py`, `test_api_events.py`

  Verify:
  - `grep -rn "output_filename(" auto_reel_ng` shows only `orchestrator.py`
  - `python -m pytest` is green

- [x] 2.2 Add `default_output_dir(project_root)` to `config/project.py` (design D-O4), and use it in `cli/commands.py` `_project_context`, `api/settings.py` and `scheduler/worker.py`. Update the `-o` help text in `cli/main.py`, and update the tests that rely on `<root>/output` as the default. Verify with:
  - a unit test for `default_output_dir`
  - a CLI test: `scan` after a default-output render reports no `2024` event
  - a green full suite

## 3. cli/ — collision refusal

- [x] 3.1 `render`: in `cmd_render`, build claims from both the stale and fresh candidates returned by `_staleness_filter`, drop the colliding ones from both lists, and add one `build_failures` entry per colliding event, naming the shared path and the other events. Verify in a new `tests/test_cli_output_collisions.py` (with `render_batch` monkeypatched as in `test_cli_render.py`):
  - a same-year pair plus a unique third: the pair gets `ERROR` lines, only the third reaches `render_batch`, and the exit code is 1
  - a fresh owner plus a new sibling: the existing output bytes are unchanged and neither event gets a manifest
  - `--force` and `--dry-run` both still refuse the pair
- [x] 3.2 `enqueue`: add a first pass that loads each document and records `output_relpath`, then report the colliding events as `ERROR` and return 1 if any collided. The existing loop runs over the rest. Verify with a `requires_db` test: two colliding stale events plus one unique event → exactly one job row inserted, and the exit code is 1.
- [x] 3.3 `adopt-renders`: add the same first-pass collision refusal. Verify in `tests/test_cli_adopt_renders.py`:
  - two colliding events with the shared output present → no manifest for either, and the exit code is 1
  - legacy layout: an existing `<out>/2024/<title>.mp4` is found and adopted, and the event then evaluates fresh

## 4. Docs

- [x] 4.1 Update the docs. Verify by rereading both sections against the specs.
  - `README.md`: in the render/CLI section, document the `<output>/<YYYY>/<title>[ - <location>].mp4` layout, the new `<parent>/<root-name>-output` default (and a warning against an output inside the walked root), that undated events go to the output root, and the collision `ERROR` + exit-1 behavior. In the change-detection deploy note, point `adopt-renders` at the legacy year-folder archive.
  - `docs/high-level-design.md`: add **D-9 — Output layout** to §7, with a one-line pointer from §4.3.

## 5. Validation

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng`. Verify that all are clean, apart from the known cairo `no-member` noise.
- [x] 5.2 Run `.venv/bin/python -m pytest`, the full suite including `requires_db`, and verify it is green. Then re-run the 2026-09-26 dogfood reproduction on a scratch project (clips symlinked from `auto-reel-media`, fixture untouched). Verify:
  - `2023-06-23 - Midsommar` and `2024-06-21 - Midsommar` render to `out/2023/Midsommar.mp4` and `out/2024/Midsommar.mp4`, and both evaluate fresh on a second run
  - adding a second `2024-06-22 - Midsommar` makes `render` print `ERROR` for both 2024 events and exit 1, and leaves `out/2024/Midsommar.mp4` unchanged
