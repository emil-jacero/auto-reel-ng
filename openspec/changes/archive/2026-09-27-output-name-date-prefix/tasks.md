## 1. render/ — the legacy file name

- [x] 1.1 Give `output_filename` in `render/orchestrator.py` the ISO-date prefix for dated events (design "Where the date goes"); `output_relpath` keeps its shape. Update the naming tests in `tests/test_render.py`. Verify:
  - `2024-06-21` / `Midsummer` / `Dalarna` → `2024/2024-06-21 - Midsummer - Dalarna.mp4`
  - `2023-12-24` / `Julafton` → `2023/2023-12-24 - Julafton.mp4`
  - undated `Sommarlov` → `Sommarlov.mp4`
  - a seeded `2017-07-20 - Båttur med Liljan och Ralf` folder → `2017/2017-07-20 - Båttur med Liljan och Ralf.mp4`
  - the year-folder render test passes with the prefixed name
- [x] 1.2 Update every test that asserts a literal output name to the prefixed form. Collision pairs become same-date pairs. Add "same title on different dates is not a collision" and "two undated same-title events collide" to `tests/test_cli_output_collisions.py`. Files:
  - `tests/test_cli_output_collisions.py`
  - `tests/test_cli_adopt_renders.py` (including `manifest.output`)
  - `tests/test_cli_render_staleness.py`
  - `tests/test_cli_render.py` (the default-output scan test)
  - `tests/test_scheduler_worker.py`

  Verify with `grep -rn '"2024" / "' tests` that only prefixed names remain, and that the full suite is green.

## 2. cli/ — adopt-renders --dry-run

- [x] 2.1 Add `--dry-run` to the `adopt-renders` parser and thread it into `cmd_adopt_renders` (design "How to verify against the archive without writing to it"):
  - full evaluation as a real run
  - `would` outcomes instead of `write_manifest`
  - a `(dry run: nothing written)` summary
  - the same exit code

  Also fix `cli/main.py`'s module docstring, which claims the options are shared. Verify with new tests in `tests/test_cli_adopt_renders.py`:
  - a dry run over 3 rendered events and 1 unrendered event reports 3 would-adopt and 1 unrendered, and writes no manifest (the `.auto-reel/` directory is absent)
  - a following real run adopts exactly those 3
  - a dry run over a colliding pair exits 1
  - a dry run over a read-only project directory (`chmod -R a-w` on a tmp tree, restored in a `finally`) completes with exit 0

## 3. Dev library and docs

- [x] 3.1 In `scripts/make_dev_library.py`, change the clash pair to `2024/2024-07-14 - Kalas` (rendered in phase 1) plus `2024/2024-07-14 - kalas` (added in phase 2, same date, differing only in case). Update the `web/README.md` bullet to match. Verify: rebuild the dev library, and `auto-reel render ../auto-reel-dev/library --dry-run` reports both Kalas events as `ERROR` colliding on `2024/2024-07-14 - Kalas.mp4`.
- [x] 3.2 Amend **D-9** in `docs/high-level-design.md` §7 (and its §4.3 pointer): the layout line becomes `<output>/<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`, with a one-sentence note on the 2026-09-26 correction and its evidence (0 → 129 of 138). Update `README.md`:
  - the "Output layout" bullet
  - the "Deploying onto an already-rendered archive" paragraph: preview with `--dry-run` on a read-only mount first, and do not run `import` before adopting

  Verify by rereading all three against the specs.

## 4. Verification

- [x] 4.1 Run `.venv/bin/python -m black auto_reel_ng tests scripts && .venv/bin/python -m isort auto_reel_ng tests scripts`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`. Verify all are clean or green, apart from the known cairo `no-member` noise.
- [x] 4.2 **Only if** the MOL drive is attached **and** `findmnt -no OPTIONS /run/media/emil/MOL` starts with `ro`, run the preview:

  ```bash
  auto-reel adopt-renders /run/media/emil/MOL/Videos/Sorted -o /run/media/emil/MOL/Videos/Completed-auto-reel --dry-run
  ```

  Verify:
  - **129 would-adopt**
  - **3 colliding** on `Untitled.mp4`: `2004 - Yngve…`, `2016 - Kents film…` and `2019-04-31 - Golfträning…`, whose names fail to seed (the next change fixes this)
  - **3 unrendered**: `2020-02-23 - Spanien`, the undated `2025-01-13 - Resa till Gran Canaria`, and `2012-07-18 - Emma & Eli trubadur - Tjörn` (no legacy output)
  - **0 already fresh**
  - the `.reelignore` trips are absent
  - exit code 1, because of the collisions
  - no write error

  If the drive is absent or mounted read-write, record the task as deferred and do not remount it yourself.

  **Done (2026-09-27):** run on a read-only mount. Result: 129 would adopt, 0 already fresh,
  3 unrendered, 3 colliding on `Untitled.mp4`, the six `.reelignore` events absent, exit code 1,
  and no write errors.
