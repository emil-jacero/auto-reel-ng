## 1. event/ — an unchanged save writes nothing

- [ ] 1.1 In `event/editorial.py::apply_editorial_write`, after validation and `require_processable`, return
  the merged document without calling `write_document` when `reel_path` existed and
  `dumps_document(current) == dumps_document(document)`; update the module and function docstrings. Verify
  in `tests/test_event_editorial.py` (fail first on main): a foreign-indented fixture (4-space mappings,
  un-indented chapter sequence, spaced eol comments) applied unmodified leaves bytes and `st_mtime_ns`
  identical and no `.tmp` in the folder (patch `write_document` to assert it is not called); the same
  fixture with a title change writes the canonical style and keeps comments; a state that fails
  cross-reference validation still raises; no `reel.yaml` plus an empty state still creates the file; a
  legacy-format file unmodified stays byte-identical, and a title change migrates it to `version: 0`.
- [ ] 1.2 In `tests/test_api_editorial_write.py`, add a PUT test over the foreign-indented fixture: GET, then
  PUT the body with `If-Match`; assert 200, the same document and `ETag`, and unchanged bytes.

## 2. event/ — per-span cut diff

- [ ] 2.1 Replace `_trims_equal` and the list replacement in `_apply_trims` with the alignment of design
  Decision 2: normalise spans to `(float(in), float(out), reason)`, align with
  `difflib.SequenceMatcher(autojunk=False)`, keep `equal` nodes, edit paired `replace` spans in place
  (only differing keys, `reason` add/change/remove), add fresh `_trim_entry` mappings, drop deleted nodes,
  and skip assigning `entry["trims"]` when nothing differs. Verify in `tests/test_event_editorial.py`: the
  triage repro (two commented flow spans, second `out` 12 to 13) leaves the first span line byte-identical
  and the second in flow style with `# shake`; the same with float inputs (`0.0`, `10.0`) keeps `in: 0`
  and `in: 10`; a `reason` added to one span changes only that mapping; an unchanged list and a
  title-only change leave the trims lines byte-identical.
- [ ] 2.2 Carry span comments with their node through add, removal and in-place edit, reusing the gate's
  comment-lifting helper (or an index-keyed variant beside it that shares its token splitting) to rebuild the
  list's `ca` tokens. Verify in `tests/test_event_editorial.py`: removing the middle of three commented
  spans keeps `# first` and `# third` on their own spans and drops `# second`; an own-line comment above
  a retained span stays directly above it; an appended span carries no comment; lines after the last
  span stay at the end; the file reloads to the same trims. Add the overlapping-spans scenario (both
  spans persisted as given) as a test.

## 3. reel/ — sweep abandoned reel.yaml temporaries

- [ ] 3.1 In `reel/writer.py::write_document`, after `os.replace` succeeds, add a module constant for the
  24-hour age and a helper that unlinks regular, non-symlink files matching
  `^\.<name>\.[0-9a-f]{32}\.tmp$` older than the age, swallowing and debug-logging `OSError`. Verify in
  `tests/test_reel_writer.py` (set mtimes with `os.utime`): a two-day-old matching file is removed; a
  one-minute-old one stays; `.reel.yaml.bak`, `.reel.yaml.1234.tmp` and
  `.other.<hex32>.tmp` stay; a matching symlink stays; a failed write (existing patch of `os.replace` or a
  read-only folder test) leaves an old temporary in place; an unlink that raises `OSError` (monkeypatch
  `Path.unlink` for that name) still returns normally with the new document in place.
- [ ] 3.2 Verify an end-to-end save through `apply_editorial_write` sweeps and an unchanged save does not:
  in `tests/test_event_editorial.py`, plant an old temporary, apply a changing state and assert it is
  gone; plant another, apply an unmodified state and assert it is still there.

## 4. Validation gates

- [ ] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  leaves no diff.
- [ ] 4.2 `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` pass (only
  the known cairo `no-member` noise).
- [ ] 4.3 `.venv/bin/python -m pytest` passes in full, including the existing `editorial-write`,
  `api-service` unmodified-save and `reel-document` round-trip tests; `RENDER_GRAPH_VERSION` is unchanged.
