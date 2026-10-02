## 1. The existence helper

- [x] 1.1 Add `reel_exists(path)` to `auto_reel_ng/event/metadata.py` (`stat()`; `False` only for
  `FileNotFoundError` / `NotADirectoryError`; everything else propagates) and export it. Tests in
  `tests/test_event_metadata.py`: present file `True`; missing file `False`; parent that is a regular file
  `False`; dangling symlink `False`; symlinked `reel.yaml` `True`; a `0600` parent raises
  `PermissionError` (skipped when `os.geteuid() == 0`). Verify with `.venv/bin/python -m pytest
  tests/test_event_metadata.py`.

- [x] 1.2 Make `load_authored_document` decide load-versus-seed with `reel_exists`. Tests in
  `tests/test_event_metadata.py` (reel-document delta scenarios): a `0600` folder holding a `reel.yaml`
  titled `Real` raises `PermissionError` from `load_authored_document` and `load_event_document` and never
  returns a `Fest` seed; a searchable folder with no `reel.yaml` still seeds (`seeded=True`); a searchable
  folder with a `0000` `reel.yaml` raises `ReelParseError` naming the file. Verify the three tests fail on
  `main` (first one returns the seed) and pass after.

## 2. Discovery fails loud

- [x] 2.1 In `auto_reel_ng/event/discovery.py`, add private `_is_dir` / `_is_file` (`stat()`, `False` only
  for `FileNotFoundError` / `NotADirectoryError`) and use them in `scan_event`'s subdirectory filter,
  `_is_chapter_dir`'s `.reelignore` lookup and `_video_identities`. Leave the public `is_reelignored`
  lenient and note in its docstring that the ingest walk relies on that. Tests in
  `tests/test_event_reconcile.py` (event-reconcile delta scenarios, skipped as root): a `0600` event
  folder makes `scan_event` and `seed_document` raise `PermissionError`; a `0600` `Reception/` subfolder
  raises naming `Reception`; a symlinked clip whose target is in an unsearchable folder raises; a
  dangling symlink, a `notes.txt` and a readable event list exactly the real clip with no error;
  `is_reelignored` on a `0600` folder still returns `False` without raising. Verify with
  `.venv/bin/python -m pytest tests/test_event_reconcile.py`.

## 3. Service surface

- [x] 3.1 In `tests/test_api_events_failures.py` (next to the existing `0o000` event test, `requires_db`,
  skipped as root), add a test that a `0600` event folder is one `unreadable_disk` error row in the events
  list while the other event is still a summary, and that its detail answers 502 with the same kind. No
  production change is expected: the existing `OSError` mapping carries it; if the test shows otherwise,
  fix the mapping in this task. Verify with `.venv/bin/python -m pytest tests/test_api_events_failures.py`.

## 4. Quality gate

- [x] 4.1 Run `.venv/bin/python -m pytest` in full, `black` / `isort` (line length 100), `mypy
  auto_reel_ng` and `pylint auto_reel_ng`; all clean apart from the known cairo `no-member` noise, and
  confirm no change to `RENDER_GRAPH_VERSION` (design, decision 5).
