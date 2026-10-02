## 1. reel/ — source-named load errors

- [x] 1.1 Name the real source in positioned YAML errors (D1). In `tests/test_reel_parser.py` first add a
  parametrised test over `title: "\x"`, a tab starting a line, an unclosed `[a` flow sequence and a repeated
  top-level key, loaded through `load_document` on a `tmp_path` file and through `loads_document` with a
  stated `source`: the message contains the path (or the stated source) in the excerpt, still contains the
  `line N` of the failure, and never contains `<unicode string>`; see it fail on the placeholder. Then in
  `parser.py` set the marks' `name` to `source` in the `ConstructorError` and `YAMLError` arms through one
  shared formatting helper, and verify the test passes and the existing invalid-value tests (`2024-02-30`,
  `!!bool maybe`) still pass unchanged.
- [x] 1.2 Say how far reading got for a position-less scanner failure (D2). Test first: a document whose
  line 4 is `  x: "\U00110000"` raises the parse error containing the file, `chr() arg not in range` and
  `line 4`; a valid document loads and never runs the re-scan (assert via a counting subclass or by a
  successful load with the iterator patched to fail). Then add the guarded `scan` re-scan to the generic
  backstop and verify the test passes and a failing re-scan still raises the original error.
- [x] 1.3 Name excessive nesting (D3). Test first: `title: ` plus 250 nested `[`/`]` raises the parse error
  containing the file, `nested too deeply` and `maximum recursion depth exceeded`, and no `line N`; a
  document nested 50 deep still loads. Then catch `RecursionError` ahead of the generic backstop and verify
  the test passes.

## 2. reel/ — callers and gates

- [x] 2.1 Confirm the callers pass the improved text through unchanged: add a third case to the parametrised
  `test_an_impossible_reel_yaml_date_is_an_error_row_not_a_500` in `tests/test_api_events_failures.py` with
  content `version: 0\ntitle: "\x"\n`, asserting the error row's `detail` names that event's `reel.yaml` and
  does not contain `<unicode string>`, and the event-detail 502 body likewise. Verify with that test
  (requires the throwaway Postgres container).
- [x] 2.2 Run `.venv/bin/python -m pytest -m "not requires_db"`, `mypy auto_reel_ng`, `pylint auto_reel_ng`,
  `black` and `isort`, all clean (cairo `no-member` noise excepted), and record in `reel/parser.py`'s
  module docstring that a failure after scanning (the recursion limit) reports no line.
