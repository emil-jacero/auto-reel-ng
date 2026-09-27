## 1. event/ — the rule and the helper

- [x] 1.1 Add `SortMethod`, `ClipOrder`, `DEFAULT_CLIP_ORDER`, `natural_key` and `order_clips` to `event/discovery.py`, and make `seed_document` order each chapter's clips by `order` (design "The rule and the ordering helper"). Verify with tests in `tests/test_event_reconcile.py`. Use `os.utime` to set mtimes on tmp clips.
  - S/P interleave: `S1600003` at 14:32, `P1110550` at 16:36, `S1600005` at 16:35 → S3, S5, P
  - `filename`: `IMG_4933`, `img_4863`, `clip10`, `clip2` → clip2, clip10, img_4863, IMG_4933
  - equal mtimes fall back to the filename order
  - `reverse` flips the order
  - chapter order is unchanged (root first, then subfolders by name)

## 2. config/ — the library default

- [x] 2.1 Add `sort: ClipOrder` to `ProjectConfig`, with parsing and fail-loud validation in `config/project.py` (design "Configuration"). Verify with `tests/test_project_config.py`:
  - absent `sort` gives `datetime`, not reversed
  - `{method: filename, reverse: true}` parses
  - `{method: custom}` raises `ConfigError` naming `sort.method`
  - `{reverse: "yes"}` raises `ConfigError` naming `sort.reverse`

## 3. Threading — every seeding path uses the configured rule

- [x] 3.1 Add the required keyword `order` to `load_authored_document`, `load_event_document`, `load_or_seed`, `prepare_event` and `prepare_and_persist`. Make `prepare_event` order NEW clips per chapter with `order_clips` before appending. Pass `ctx.config.sort` from `cli/commands.py`, `config.sort` from `scheduler/worker.py`, and `settings.clip_order` (new, filled in `resolve_api_settings`) from `api/events_read.py` and `api/routes/jobs.py`. Verify:
  - `.venv/bin/python -m mypy auto_reel_ng` passes, so no call site is missing
  - `tests/test_event_reconcile.py` or `tests/test_cli_adoption.py`: a `reel.yaml` with a hand-ordered chapter keeps its order after adoption, and two NEW clips are appended in rule order
- [x] 3.2 Add an integration test for a project whose `config.yaml` sets `sort: {method: filename}`, with mtimes set to contradict filename order. `scan` prints clips alphabetically, not in play order, so check play order directly. Verify:
  - `tests/test_cli_render.py`, with the engine patched as in that file: the `reel.yaml` that `render` persists lists the default chapter in filename order
  - `tests/test_api_events.py`: `GET /api/v1/events/{id}` returns the same chapter order
  - without the config line, both follow mtime order

## 4. Docs

- [x] 4.1 Document the default, the options and the new-clip append rule. Verify by rereading them against the specs.
  - `README.md`: add `sort: {method: datetime|filename, reverse: false}` to the `config.yaml` example, and add a sentence on the default (`datetime` by file mtime, as auto-reel), on `filename` being natural and case-insensitive, and on existing orders never being re-sorted.
  - `docs/high-level-design.md` §2: point the "Sort strategies" bullet at the requirement.

## 5. Validation

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`. Verify all are clean or green, apart from the known cairo `no-member` noise.
- [x] 5.2 **Only if** the MOL drive is mounted `ro`, print the seeded play order of `2024-04-20 - Lasse 80 år…` read-only. Use `.venv/bin/python -c` with `load_or_seed(<event dir>, order=ClipOrder())`, and print the default chapter's clip identities. Compare it with `find <event dir> -maxdepth 1 -type f -printf '%T@ %f\n' | sort -n`. Verify:
  - the orders are identical, with `S` and `P` clips interleaved by time
  - nothing is written (the mount is `ro`)

  Otherwise record the task as deferred.

  **Done (2026-09-27, MOL `ro`):** all 58 seeded clips match the mtime order exactly, with S/P interleaved. Nothing was written. Note: `c0001–c0028` and `img_*` carry 2025-08-04 conversion mtimes (the event has an `original/` folder), so they seed after every S/P clip. That is the proposal's known 18-event risk, not a defect.
