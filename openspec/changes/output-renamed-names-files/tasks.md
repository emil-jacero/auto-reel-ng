## 1. staleness/

- [x] 1.1 Add `renamed_from: Optional[str] = None` and `output_name: Optional[str] = None` to `Verdict`
  (`staleness/gate.py`), documented as set exactly when `OUTPUT_RENAMED` is cited. In `evaluate()`, resolve the
  old movie once through `_renamed_output` and set `renamed_from` to the returned path's `.name` (never
  `manifest.output`) and `output_name` to the expected output's `.name`; the reason and the names come from the
  same lookup. Update the `StalenessReason.OUTPUT_RENAMED` and `evaluate` docstrings.
- [x] 1.2 Gate tests in `tests/test_staleness_gate.py`: for the retitle, the location change and the date moved to
  another year, assert `renamed_from`/`output_name` are the two bare file names (no year folder); for fresh,
  `no_manifest`, `output` (renamed event whose old movie was deleted, plain deletion) and component-only
  verdicts, assert both are `None`; assert `stale` and `reasons` are unchanged by the names.

## 2. cli/

- [x] 2.1 In `_print_inventory` (`cli/commands.py`), print the `output_renamed` entry as
  ``output_renamed (was <repr(renamed_from)>, now <repr(output_name)>)`` via a small private helper; every other
  verdict prints as before. Only `scan`/`list` formats reasons, so no other command changes.
- [x] 2.2 CLI tests: update the two exact `stale: ...output_renamed` assertions in
  `tests/test_cli_render_staleness.py` to the new line (names asserted literally); add a `scan` test in
  `tests/test_cli_commands.py` with a non-ASCII old and new name that pins the one-line format, and one that a
  deleted movie prints `stale: output` with no names. `tests/test_cli_jobs.py` keeps passing unchanged (prefix
  match).

## 3. Docs and validation gates

- [x] 3.1 Update the `README.md` paragraph on `output_renamed` and its `scan` example to show the two file names.
- [x] 3.2 Run `black` and `isort` over `auto_reel_ng tests`; `mypy auto_reel_ng`; `pylint auto_reel_ng` (known
  cairo `no-member` noise only).
- [x] 3.3 Run `.venv/bin/python -m pytest` (full suite; `-m "not requires_db"` and say so if podman is
  unavailable).
