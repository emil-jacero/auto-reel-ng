## 1. event/ — an unchanged save writes nothing

- [x] 1.1 In `event/editorial.py::apply_editorial_write`, after validation and `require_processable`, return
  the merged document without calling `write_document` when `reel_path` existed and
  `dumps_document(current) == dumps_document(document)`; update the module and function docstrings. Verify
  in `tests/test_event_editorial.py` (fail first on main): a foreign-indented fixture (4-space mappings,
  un-indented chapter sequence, spaced eol comments) applied unmodified leaves bytes and `st_mtime_ns`
  identical and no `.tmp` in the folder (patch `write_document` to assert it is not called); the same
  fixture with a title change writes the canonical style and keeps comments; a state that fails
  cross-reference validation still raises; no `reel.yaml` plus an empty state still creates the file; a
  legacy-format file unmodified stays byte-identical, and a title change migrates it to `version: 0`.
- [x] 1.2 In `tests/test_api_editorial_write.py`, add a PUT test over the foreign-indented fixture: GET, then
  PUT the body with `If-Match`; assert 200, the same document and `ETag`, and unchanged bytes.

## 2. event/ — per-span cut diff

- [x] 2.1 Replace `_trims_equal` and the list replacement in `_apply_trims` with the matching of design
  Decision 2: normalise spans to numeric keys, give each desired span the existing node of equal value (else
  same `in`, else same `out`, else the next one left), edit paired nodes in place (only differing keys,
  `reason` add/change/remove), add fresh `_trim_entry` mappings in the style of the span before, drop
  unclaimed nodes, and leave the list alone when nothing differs. Verify in
  `tests/test_event_editorial.py`: the triage repro (two commented flow spans, second `out` 12 to 13) leaves
  the first span line byte-identical and the second in flow style with `# shake`; the same with float inputs
  (`0.0`, `10.0`) keeps `in: 0` and `in: 10`; a `reason` added to or removed from one span changes only that
  mapping; an unchanged list and a title-only change leave the trims lines byte-identical.
- [x] 2.2 Carry span comments with their node through add, removal, move and in-place edit, generalising the
  gate's comment-lifting helpers (entries in order, plus the lines after a block-mapping span, which ruamel
  files on its last key) to rebuild the list's comment tokens. Verify in `tests/test_event_editorial.py`:
  removing the middle of three commented spans keeps `# first` and `# third` on their own spans and drops
  `# second`; own-line comments travel with their span, also when it is moved; an appended span carries no
  comment; lines after the last span stay at the end (also with no end-of-line comment on the flow
  spans); block-style spans do the same; a reordered or trimmed mixed flow/block list saves, a shape
  ruamel cannot emit gives up the header only, and one it cannot re-write at all is a typed 400; removing one span
  while editing another edits the right one; the file reloads to the same trims. Add the
  overlapping-spans scenario (both spans persisted as given) as a test, and an API test in
  `tests/test_api_editorial_write.py` for the repro over JSON.

## 3. reel/ — sweep abandoned reel.yaml temporaries

- [x] 3.1 In `reel/writer.py::write_document`, after `os.replace` succeeds, add a module constant for the
  24-hour age and a helper that unlinks regular, non-symlink files matching
  `^\.<name>\.[0-9a-f]{32}\.tmp$` older than the age, swallowing and debug-logging `OSError`. Verify in
  `tests/test_reel_writer.py` (set mtimes with `os.utime`): a two-day-old matching file is removed; a
  one-minute-old one stays; `.reel.yaml.bak`, `.reel.yaml.1234.tmp` and
  `.other.<hex32>.tmp` stay; a matching symlink stays; a failed write (existing patch of `os.replace` or a
  read-only folder test) leaves an old temporary in place; an unlink that raises `OSError` (monkeypatch
  `Path.unlink` for that name) still returns normally with the new document in place.
- [x] 3.2 Verify an end-to-end save through `apply_editorial_write` sweeps and an unchanged save does not:
  in `tests/test_event_editorial.py`, plant an old temporary, apply a changing state and assert it is
  gone; plant another, apply an unmodified state and assert it is still there.

## 4. Validation gates

- [x] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  leaves no diff.
- [x] 4.2 `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` pass (only
  the known cairo `no-member` noise).
- [x] 4.3 `.venv/bin/python -m pytest` passes in full, including the existing `editorial-write`,
  `api-service` unmodified-save and `reel-document` round-trip tests; `RENDER_GRAPH_VERSION` is unchanged.
