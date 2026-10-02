## 1. reel/ — shared value scans

- [x] 1.1 Add `auto_reel_ng/reel/values.py` with `find_lone_surrogate(tree)` and `find_non_str_key(tree)`
  (design D5-D7): pure, iterative (explicit stack), walking mappings and lists, returning `None` or the location
  (path string like `look.layers[0]`, plus key and type name for the second). Add `tests/test_reel_values.py`
  and see it fail first: a clean tree returns `None`; a surrogate is found in a value, in a key, nested in a
  list, and a plain astral character is not; a `date` key, an `int` key and a nested list-of-mappings key are
  found with their path; a 5000-level nested structure raises no `RecursionError`; both functions accept a
  ruamel `CommentedMap`/`CommentedSeq`. The tests pass.

## 2. reel/ — numeric and version rules

- [x] 2.1 `_req_time` rejects a non-finite time (D2). In `tests/test_reel_parser.py` first add a test
  parametrised over trims `{in: .nan, out: 5}`, `{in: 0, out: .nan}`, `{in: .nan, out: .nan}`,
  `{in: 1, out: .inf}` (each `ReelParseError` matching `trims\[0\]\.(in|out): time must be finite` and naming
  the clip), `-inf` (still "non-negative"), and keep the existing 400-digit "out of range" test passing. A valid
  `{in: 0, out: 3.2}` still loads.
- [x] 2.2 `_validate_version` accepts only the integer `0` (D3). In `tests/test_reel_parser.py` add a test
  parametrised over `version: false`, `version: 0.0`, `version: '0'`, `version:` (null) and `version: 99`,
  each `ReelParseError` matching `unsupported version`, and one for `version: 0` that loads and reports
  `version == 0`.

## 3. reel/ — ignore, look and surrogate rules

- [x] 3.1 `_parse_ignore` rejects a repeated identity (D4). In `tests/test_reel_parser.py` add a parametrised
  test over `[x.mp4, y.mp4, x.mp4]` and `[x.mp4, ./x.mp4]` matching `duplicate ignore entry 'x.mp4'` with the
  position of the repeat; a list of distinct entries still loads. In `tests/test_event_editorial.py` add a test
  that `apply_editorial_write` with the `ignore` list `[x.mp4, x.mp4]` on a file that ignores `x.mp4` once
  (with a trailing `# first` comment) raises `ReelParseError` and leaves the file bytes unchanged.
- [x] 3.2 `_parse_look` requires string keys at any depth (D5), using `find_non_str_key`. In
  `tests/test_reel_parser.py` add a parametrised test over `look:` with `2024-01-01: x` (date), `{1: a, b: c}`
  (mixed), `{layers: [{1: x}]}` (nested in a list, path `look.layers[0]`) and a legacy `title_card: {1: a}`,
  each a `ReelParseError` naming `look` and the key; and a test that a quoted `'2024-01-01'` key and the
  existing `unknown_future_key: 42` still load and round-trip unchanged through `write_document`. Add the
  regression that `editorial_hash` of a document with a valid `look` is unchanged by the change (compare with
  a hash literal taken before the edit).
- [x] 3.3 Lone surrogates are refused (D6), using `find_lone_surrogate`: in `build_document` after
  `_validate_version`, and in `loads_document`'s legacy branch before the import. In `tests/test_reel_parser.py`
  add a parametrised test over v0 `metadata.title: "Fest \ud800"`, `look: {font: "x\ud800"}`,
  `look: {"a\ud800": 1}`, a `chapters` clip name `"a\ud800.mp4"`, and a legacy document with
  `title: "x\ud800"` and with an unmapped key `"k\ud800": 1`: each raises `ReelParseError` naming the path, and
  `str(exc.value).encode("utf-8")` succeeds. Add a test that `"Fest \U0001F386"` loads. In
  `tests/test_event_editorial.py` add a test that `apply_editorial_write` with the title `"Fest \ud800"` raises
  `ReelParseError` and leaves the file unchanged.

## 4. Whole-suite checks

- [x] 4.1 With the work done, run `.venv/bin/python -m pytest` (DB tests included),
  `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and
  `.venv/bin/python -m black --check auto_reel_ng tests && .venv/bin/python -m isort --check auto_reel_ng tests`;
  all pass (pylint apart from the known cairo `no-member` noise). Confirm `RENDER_GRAPH_VERSION` is unchanged
  and `git diff --stat` touches only `auto_reel_ng/reel/` and the listed tests.
