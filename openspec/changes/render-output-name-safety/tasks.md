## 1. render/ — single-component name

- [x] 1.1 In `render/orchestrator.py`, add a private helper that replaces `/`, `\` and every control
  character (code point < 0x20 and 0x7f, including NUL) with `-`, and apply it to the title and the location
  inside `output_filename` (before the date prefix and joiners; a missing title still gives `Untitled`).
  Verify with `tests/test_render.py` cases: `Mid/sommar` -> `2025/2025-01-16 - Mid-sommar.mp4`, location
  `Gamla/stan` -> `2025-01-16 - T - Gamla-stan.mp4`, `a/../../../escaped` -> `a-..-..-..-escaped`, a
  backslash title, a title containing NUL and a newline, and a title of only `/`; each asserting
  `output_relpath(...)` has exactly the year plus one name component (`len(parts) == 2`, none equal to `..`).
- [x] 1.2 Add a test that sanitising does not alter the input: the `Metadata` object keeps its original
  title and location, and the existing `Midsummer`/`Dalarna`, `Julafton`, undated `Sommarlov` and legacy
  `Båttur med Liljan och Ralf` name tests still pass unchanged.
- [x] 1.3 Add a test that two events dated the same day with titles `A/B` and `A-B` yield the same
  `output_relpath` and that `find_output_collisions` reports them, proving the lossy mapping is still
  caught.

## 2. render/ — containment guard

- [x] 2.1 In `render_movie`, right after computing `output_path` and before the dry-run branch, raise
  `RenderError` (naming the output path and the output directory) when
  `os.path.abspath(output_path)` is not inside `os.path.abspath(options.output_dir)`. Verify with a test
  that patches `output_relpath` (in `render.orchestrator`) to return `PurePosixPath("../escaped.mp4")` and
  asserts `RenderError`, that no `escaped.mp4`, `.part` file or new directory exists under or beside the
  `tmp_path` output dir, and that the same holds with `dry_run=True`.
- [x] 2.2 Add a test that a symlinked year folder (output `2024/` -> another temp dir) is NOT refused by
  the guard and renders into the link target.
- [x] 2.3 Add an end-to-end `render_movie` test (`has_ffmpeg`-marked, like the neighbouring render tests)
  for title `Mid/sommar`: the movie lands at `<output>/2025/2025-01-16 - Mid-sommar.mp4`, no
  `2025-01-16 - Mid` folder exists, and the plan's `metadata.title` still reads `Mid/sommar`.

- [x] 2.4 In `tests/test_api_media.py`, make the `utbrytning` fixture force the climbing path by patching
  `output_relpath` in the media module, since the naming rule can no longer produce one; the media lookup
  guard stays covered (defence in depth), and title-driven climbing is covered in `tests/test_render.py`.

## 3. Validation gates

- [x] 3.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  and confirm no diff remains.
- [x] 3.2 Run `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng`
  (known cairo `no-member` noise only).
- [x] 3.3 Run `.venv/bin/python -m pytest` (podman available) and confirm the suite is green, including the
  new tests; confirm `RENDER_GRAPH_VERSION` is still `3`.
