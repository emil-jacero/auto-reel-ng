## 1. ingest/ (`auto_reel_ng/ingest/layouts.py`)

- [x] 1.1 Add the private `_dedupe_aliases(root, rows)` (built as `_walk_dirs`, which also owns the `.reelignore` skip) (group by `resolve()`, canonical-first, else first in walk order, WARNING per dropped row) and apply it in `flat_layout`. Test in `tests/test_ingest_layouts.py`: symlink `Fest -> Kalas` beside the real dir yields only `Kalas` even though `Fest` sorts first; the WARNING names alias, kept path and target (caplog); an unduplicated symlink to an outside dir is kept with no warning.
- [x] 1.2 Apply it in `year_event_layout` over all years before the year filter and after the `.reelignore` skip. Tests: alias in `2025/` of a `2024/` target under `years=["2025"]` yields nothing with a WARNING; symlinked year dir `2023 -> 2024` yields each event once under `2024/`; a `.reelignore` target and its alias are both skipped with only the INFO lines.

## 2. Consumers (tests only; no `cli/`, `scheduler/` or `api/` code change)

- [x] 2.1 `tests/test_cli_adoption.py`: build the Kalas/Fest repro, run `prepare_event` + `persist` for every ref from `get_layout("year-event")`, and assert `Kalas/reel.yaml` has title `Kalas` (created once) and, with a pre-existing `reel.yaml`, is byte-identical afterwards.
- [x] 2.2 `tests/test_cli_commands.py`: `main(["scan", root])` over the repro prints Kalas once, never Fest, and exits 0.
- [x] 2.3 `tests/test_api_events.py`: the events list over the repro contains one event, and a listed-event lookup (`listed_event_dir`) of the alias's id raises the existing not-found error. Also update the in-project-alias cases in `tests/test_api_jobs.py` and `tests/test_api_output_collision.py`, which pinned the old alias-as-row behaviour.

## 3. Validation gates

- [x] 3.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests` clean; `.venv/bin/python -m mypy auto_reel_ng` clean; `.venv/bin/python -m pylint auto_reel_ng` shows no new messages beyond the known cairo `no-member`.
- [x] 3.2 `.venv/bin/python -m pytest` passes (DB tests need podman; if unavailable run `-m "not requires_db"` and say so).
