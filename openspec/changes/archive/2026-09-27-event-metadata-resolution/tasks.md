## 1. event/ — parse, resolve, validate

- [x] 1.1 Replace `parse_folder_name`'s return with `FolderName` plus `FolderNameProblem` in `event/discovery.py` (design "The parse result"). Make `_metadata_from_folder_name` and `seed_document` use the lenient fields and never produce `Untitled`. Update `ingest/layouts._folder_hint` and `api/events_read.py`'s list-title fallback to the new type. Verify with tests in `tests/test_event_reconcile.py`:
  - `2024-06-21 - Midsummer - Dalarna` → date, title, location, and no problems
  - `2019-04-31 - Golfträning med Emil - Tjörn` → `IMPOSSIBLE_DATE`, `raw_date == "2019-04-31"`, title `Golfträning med Emil`, location `Tjörn`
  - `2004 - Yngve berättar om skövde` → `YEAR_ONLY`, title `Yngve Berättar om Skövde`
  - `Blandat` → `NO_DATE`, title `Blandat`
  - `2024-06-21 - ` → `NO_TITLE`
  - `Lasse 78 år  - Kungälv` (double space) splits cleanly
- [x] 1.2 Add `event/metadata.py` with `resolve_metadata`, `load_event_document` and `require_processable` (raising `EventMetadataError(ReelError)`, added to `errors.py`), per design "Resolution…" and "Validation…". Make `cli/adoption.load_or_seed` delegate to `load_event_document`. Verify with new tests in `tests/test_event_metadata.py`:
  - per-field precedence, blank counted as unset
  - a legacy `reel.yaml` without a date takes the folder date
  - `reel.yaml` date `2019-04-30` beats the impossible folder date
  - after `load_event_document` and `persist`, the file on disk still has no date
  - `require_processable` raises for no date (message names `2019-04-31` / "year only" / "no date"), for no title, and for `today + 1 day`; it passes when `reel.yaml` supplies the date despite a bad folder name

## 2. cli/ — per-event isolation

- [x] 2.1 Add `_checked_document(ref, today)` in `cli/commands.py`, and use it in `scan`, `enqueue`, `adopt-renders` and `render`'s `_staleness_filter` (design "Per-event isolation in the CLI"). Failed events print `ERROR  <event>: <reason>`, are excluded from the collision check and from all further steps, and set exit code 1. Verify with a new `tests/test_cli_event_metadata.py`:
  - `render` over the impossible-date event plus two valid events renders the two, reports the one, and exits 1
  - `scan` over a year-only event reports it, then lists it normally after a `reel.yaml` date is added
  - `scan` with one unparseable `reel.yaml` among three lists the other two and exits 1
  - `adopt-renders --dry-run` reports the three bad names as `ERROR`, not as `Untitled.mp4` claimants

## 3. api/ and scheduler/ — same rule, existing error shapes

- [x] 3.1 Make `api/events_read._load_for_reconcile` use `load_event_document`, and call `require_processable` mapping `EventMetadataError` to `EventReadError`. Leave the editorial read on `load_document`. In `scheduler/worker.py`'s `default_build_job`, call `require_processable` so the job fails with the reason. Verify with tests:
  - the events list over a project with one year-only event returns the existing per-event 502 problem body naming it (`tests/test_api_events_failures.py`)
  - the editorial read of a date-less `reel.yaml` returns no date (`tests/test_api_editorial_read.py`)
  - a claimed job for an impossible-date event ends `failed` with the reason in `error` (`tests/test_scheduler_worker.py`)

## 4. Fixtures, dev library, docs

- [x] 4.1 Update the tests whose expectations assumed undated output or `Untitled` (for example `tests/test_editorial_write_e2e.py`'s date-less PUT now resolves the folder date). In `scripts/make_dev_library.py`, give `2024/Blandat` a `reel.yaml` with `metadata: {title: Blandat, date: 2024-11-02}`, and update `web/README.md`'s dev-library bullet to match. Verify:
  - the full suite is green
  - a rebuilt dev library scans with no `ERROR`
- [x] 4.2 Update `README.md`, in the CLI section: metadata resolves field by field (`reel.yaml` over folder name), an event needs a real date and title, bad folder names are reported per event with the fix, and nothing is guessed from media. Update `docs/high-level-design.md` §4.7 (D-2 layering): the folder seed is a per-field fallback, resolved at load and never persisted. Verify by rereading both against the specs.

## 5. Validation

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests scripts && .venv/bin/python -m isort auto_reel_ng tests scripts`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`. Verify all are clean or green, apart from the known cairo `no-member` noise.
- [x] 5.2 **Only if** `findmnt -no OPTIONS /run/media/emil/MOL` starts with `ro`, run:

  ```bash
  auto-reel adopt-renders /run/media/emil/MOL/Videos/Sorted -o /run/media/emil/MOL/Videos/Completed-auto-reel --dry-run
  ```

  Verify:
  - **129 would-adopt**
  - **3 `ERROR`**: `2004 - Yngve…` year only, `2016 - Kents film…` year only, `2019-04-31 - Golfträning…` not a real date
  - **3 unrendered**: Spanien, the 2012 Emma & Eli event, and 2025 Gran Canaria (doubled date until `legacy-import-title`)
  - no collision lines
  - exit code 1

  Otherwise record the task as deferred and do not remount.
