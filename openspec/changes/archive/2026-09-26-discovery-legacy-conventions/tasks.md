## 1. event/ — clip discovery conventions

- [x] 1.1 In `event/discovery.py`, add `ORIGINALS_DIR`, `IGNORE_MARKER`, `is_reelignored()` and `_is_chapter_dir()`, and make `scan_event` skip any subdirectory for which `_is_chapter_dir` is false (design "Where each rule is enforced", "Matching rules"). Verify with new tests in `tests/test_event_reconcile.py`, each building a tmp event:
  - `original/` with `.MTS` twins yields no `original` chapter
  - `Original/` is excluded too
  - a subdirectory with `.reelignore` is excluded, while its sibling chapter is kept
  - `2017-07-10/original/x.MTS` is not discovered
  - a directory named `.reelignore` is not treated as the marker
- [x] 1.2 Add the reconcile and staleness consequences as tests:
  - a document referencing `original/00400.MTS` reconciles it as MISSING, and the file is untouched (`tests/test_event_reconcile.py`)
  - adding a file under `original/` of a rendered event leaves `compute_fingerprint` unchanged (`tests/test_staleness_fingerprint.py`)

  Verify both pass.

## 2. ingest/ — event-level marker

- [x] 2.1 In `ingest/layouts.py`, route both built-in layouts' event yields through one helper that skips `is_reelignored(event_dir)` and logs `skipping <dir>: .reelignore` at INFO. Verify with new tests in `tests/test_ingest_layouts.py`:
  - `year-event` skips the marked event and yields its sibling
  - `flat` skips a marked subdirectory
  - a `.reelignore` at year level or at the root yields every event
  - `caplog` shows exactly one INFO line naming the skipped directory
  - deleting the marker yields the event again

## 3. Integration through the existing callers

- [x] 3.1 Add a CLI test (`tests/test_cli_commands.py`): `scan` over a project with one ignored event and one event with `original/` lists neither the ignored event nor an `original` chapter. Also add an API test (`tests/test_api_events.py`): `GET /api/v1/events` excludes the ignored event. Verify both pass with no change to `cli/` or `api/` source.

## 4. Docs and verification

- [x] 4.1 Update the docs. Verify by rereading them against the specs.
  - `README.md`, in the CLI "Layouts" and "Adoption policy" bullets: document that `original/` is never a chapter, that a subfolder or event containing `.reelignore` is skipped (and logged), and that clips are discovered one level deep.
  - `docs/high-level-design.md` §2: add a pointer from the "`original/` skipped; `.reelignore`" bullet to the two requirements.
- [x] 4.2 **Only if** the MOL drive is attached and confirmed mounted `ro` (`findmnt -no OPTIONS /run/media/emil/MOL` starts with `ro`), run the read-only `auto-reel scan /run/media/emil/MOL/Videos/Sorted`. Verify:
  - 135 events
  - no `original` chapter anywhere in the output
  - 6 INFO lines, each naming a `.reelignore` event

  If the drive is absent, record the task as deferred rather than skipping it silently.

  **DONE (2026-09-26):** run by the operator against the `ro`-mounted MOL drive; reported successful.

## 5. Validation

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`. Verify all are clean or green, apart from the known cairo `no-member` noise.
