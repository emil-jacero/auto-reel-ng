## 1. Preconditions

- [x] 1.1 Confirm the gates are merged and match the design's interface table: `event.claims.checked_claim`,
  `event.metadata.reel_exists`, a strict `scan_event`, and `cli.context.project_context` exist on the base
  branch; `grep -n "_project_context\|exists()" auto_reel_ng/cli/` shows only the renamed call and the
  output-file `exists()`; record any name or import-path difference in the change's design.md before coding
  (a behavioural mismatch is reported, not worked around). Verified by running the existing CLI suite green
  on the base: `.venv/bin/python -m pytest tests/test_cli_*.py -m "not requires_db"`.

## 2. cli/ - import isolation

- [x] 2.1 Replace `_read_yaml` and `_has_version` with one `_read_legacy_mapping` that raises `ReelParseError`
  (path in the message) for an unreadable file, non-UTF-8 bytes, malformed YAML (any ruamel failure) and a
  non-mapping root; `_has_version` is `"version" in _read_legacy_mapping(path)` and no longer swallows
  `OSError`. Verified by `tests/test_cli_import.py` unit cases: bad-UTF-8, malformed, list-root, empty file
  and a `0000` file each raise `ReelParseError` naming the path; a mapping with and without `version` gives
  True and False.
- [x] 2.2 Guard each event in `cmd_import` with `except (OSError, ReelError)`: print
  `ERROR  <event>: <reason>`, continue, count failures, print `imported N event(s)` plus `, M failed` when any,
  and return 1 when any failed. Swap the `exists()` calls in `_legacy_source` and `_import_event` for
  `reel_exists`. Verified by `tests/test_cli_import.py` end-to-end `main(["import", root])` over three events
  each: a bad-UTF-8 `metadata.yaml`, a malformed one and a list-root one, in the middle, each followed by a
  good event that still gets its `reel.yaml`; rc is 1, output has one `ERROR` naming the bad event, the
  count line says `2 event(s), 1 failed`, and the bad event has no `reel.yaml`. Also: a `SKIP` of an
  existing v2 `reel.yaml` exits 0, a malformed `reel.yaml` with no `metadata.yaml` is an `ERROR`, and a
  `0600` event folder is an `ERROR` (skipped when `os.geteuid() == 0`).

## 3. cli/ - enqueue report from the insert

- [x] 3.1 In `cmd_enqueue`, replace the `active_job` pre-read, its comment and the `enqueue` call with
  `store.submit(...)` and branch on `Submission.created` for the printed line and the `created` count; update
  the `JobStore.active_job` docstring (`persistence/job_store.py`) so it no longer names the CLI. Verified by
  `tests/test_cli_enqueue.py` with a fake store: `submit` returning `created=False` while `active_job` would
  return `None` prints `=  ... already queued/running (<id>)` and counts 0 of N newly queued; `created=True`
  prints `+  ... queued (<id>)` and counts 1; the totals line is unchanged. The existing `requires_db`
  `test_enqueue_twice_reports_existing_and_inserts_no_duplicates` (`tests/test_cli_jobs.py`) keeps covering the
  real store: one row and an `already queued` line on the second run.

## 4. cli/ - claims and unreadable events

- [x] 4.1 Make `_checked_document` call `checked_claim(ref.event_dir, order=order, today=today)`, then list the
  folder once with `scan_event` and turn an `OSError` into the reason `cannot read <dir>: <error>`; use
  `reel_exists` for `cmd_scan`'s presence test. Verified by `tests/test_cli_output_collisions.py` and
  `tests/test_cli_commands.py`: with a `0000` sibling (no `reel.yaml`), a `0600` sibling and a `0300` sibling
  (holding a `reel.yaml`), each of `scan`, `render --dry-run`, `enqueue` (fake store) and
  `adopt-renders --dry-run` prints `ERROR` for that sibling only, still handles the good events, exits 1, and
  the `0600` event is not listed with its folder-name title; two good events that collide are still both
  refused when a `0000` sibling is present. Permission tests restore modes in `finally` and skip as root.
- [x] 4.2 Re-copy the current text of the three modified `headless-cli` requirements from
  `openspec/specs/headless-cli/spec.md` into this change's delta if a gate's archive changed them, and keep the
  delta valid. Verified by `openspec validate cli-batch-isolation-and-claims --strict`.

## 5. Validation gates

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`;
  both leave no diff. `wc -l auto_reel_ng/cli/commands.py` is at most 990, else the import helpers move
  unchanged to `cli/legacy_import.py` first (design, decision 5).
- [x] 5.2 Run `.venv/bin/python -m mypy auto_reel_ng && .venv/bin/python -m pylint auto_reel_ng` (only the
  known cairo `no-member` noise remains) and `.venv/bin/python -m pytest` (podman for the DB tests; if podman
  is unavailable run `-m "not requires_db"` and say so).
