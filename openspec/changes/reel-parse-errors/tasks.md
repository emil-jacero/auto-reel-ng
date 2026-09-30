## 1. Gate

- [x] 1.1 Gate: none; this change can start now. Baseline check:
  - `git diff 6fde515 -- auto_reel_ng/reel/parser.py openspec/specs/reel-document/spec.md` prints nothing.
    If the spec differs, re-base the MODIFIED block before implementing.
  - `.venv/bin/python -m pytest tests/test_reel_parser.py tests/test_cli_event_metadata.py -q` passes.

## 2. reel/ — every content failure is a `ReelParseError`

- [x] 2.1 A value that cannot be constructed is a marked parse error (design "Where to turn a builtin error
  into a parse error"). First add the tests to `tests/test_reel_parser.py` and see them fail on the current
  code with a bare `ValueError`, `KeyError` or `IndexError`. Each test writes a file under `tmp_path` and
  calls `load_document`:
  - parametrized over:
    - v0 `metadata.date: 2024-02-30` on line 4
    - v0 `metadata.date: 2024-13-45`
    - a legacy document (no `version`) with `metadata.date: 2024-02-30`
    - a legacy document with `metadata.date: 2024-13-45`
    - v0 `look: {generated: 2024-02-29T25:00:00}` in block style
    - v0 `look: {n: !!int abc}`
    - v0 `look` with `shadow: !!bool maybe` in block style (`KeyError` today)
    - v0 `look` with `size: !!int` and no value, in block style (`IndexError` today)

    Each case asserts `pytest.raises(ReelParseError)`, and that the message contains the file name, the
    value as written (`''` for the empty one), and `line <n>`, under the prefix `invalid value` and never
    `malformed YAML` (review decision: the text is well-formed).
  - two whole-message cases: the Barbecue date carries Python's own `ValueError` text in parentheses, and
    `!!bool maybe` carries no `KeyError` text (it only repeats `'maybe'`)
  - one `loads_document` case (string source) for `2024-02-30`, which asserts the same error type
  - ruamel's own `ConstructorError` (`!!timestamp foo`) reads `invalid value` too
  - the other builtin types the review found reach `ReelParseError` as well: `AttributeError`
    (`!!set abc`), and `TypeError` from a complex key holding a list, nested and at the root
  - `date: 2024-02-29` still loads as `date(2024, 2, 29)`
  - `date: '2024-02-30'` still fails with the existing `metadata.date: invalid date` message

  Then add `_Constructor` (overriding `construct_non_recursive_object`) and its `_kind`/`_shown` helpers
  to `reel/parser.py`, and set `yaml.Constructor = _Constructor` in `_yaml()`. The hook re-raises a
  `YAMLError` (and a `RecursionError`, task 2.2) unchanged and turns any other `Exception` into a
  `ConstructorError` whose one-line text names the value and the node's `start_mark` line and column,
  with `# pylint: disable=broad-exception-caught`. `loads_document` raises a `ConstructorError` as
  `ReelParseError` under the prefix `invalid value`, before its `except YAMLError`. Update the module and
  `load_document` docstrings to say that a value which cannot be constructed is a parse error.

  Verify:
  - before the code change, the new tests fail with the builtin errors named above
  - after it, `.venv/bin/python -m pytest tests/test_reel_parser.py tests/test_reel_writer.py
    tests/test_event_editorial.py` passes, with the existing round-trip and byte-stable tests unchanged
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
  - `.venv/bin/python -m pylint auto_reel_ng/reel/parser.py` reports nothing new
- [x] 2.2 Anything else the YAML reader raises is a parse error (design "Where to turn a builtin error into
  a parse error", the backstop). Add two tests to `tests/test_reel_parser.py`, each through
  `load_document`:
  - `metadata.title: "Fest \UFFFFFFFF"` in a v0 document: today a scanner `ValueError`
    (`chr() arg not in range(0x110000)`). Write the test text as a raw string (`r'...'`), so that the file
    holds the backslash; in a plain literal, Python itself rejects `\UFFFFFFFF` at compile time.
  - `version: 0\nlook: ` followed by a flow list nested 3000 deep (`"[" * 3000 + "]" * 3000`): today a
    `RecursionError`, raised while composing. Parametrized with 300 levels too: that `RecursionError` is
    raised while constructing, inside the hook, which must pass it through (found at implementation)

  Each asserts `pytest.raises(ReelParseError)` and a message containing the file name and
  `malformed YAML` (and `recursion` for the nesting). See both fail first with the builtin errors named.
  Then add the `except Exception` clause after `except YAMLError` around `_yaml().load(text)` in
  `loads_document`, and only there.

  Verify:
  - `.venv/bin/python -m pytest tests/test_reel_parser.py` passes, the 2.1 tests unchanged, which shows
    the hook still reports those with their line
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
  - `.venv/bin/python -m pylint auto_reel_ng/reel/parser.py` reports nothing new
- [x] 2.3 A non-UTF-8 file is a parse error (design "The non-UTF-8 file"). Add a test that writes
  `version: 0\nmetadata:\n  title: Kräftskiva\n` encoded as Latin-1 and asserts that `load_document`
  raises `ReelParseError`. The message must contain the file name, `not UTF-8 text` and `at byte 32`. See
  the test fail with `UnicodeDecodeError` first. Then add the `except UnicodeDecodeError` clause to
  `load_document`.

  Verify:
  - `.venv/bin/python -m pytest tests/test_reel_parser.py` passes
  - `.venv/bin/python -m mypy auto_reel_ng` is clean

## 3. cli/ — `scan` isolates the event (test only, no code change)

- [x] 3.1 Add `test_scan_isolates_an_impossible_reel_yaml_date` to `tests/test_cli_event_metadata.py`,
  next to `test_scan_lists_the_rest_when_one_reel_yaml_is_unparseable`. The events are the spec scenario's:
  `2024-06-21 - Midsommar`, `2024-07-04 - Barbecue` and `2024-08-01 - Kräftskiva`, and only Barbecue's
  `reel.yaml` sets `metadata.date: 2024-02-30`. Parametrize a second case, where Barbecue's `reel.yaml` is
  Latin-1 bytes.

  Verify:
  - `main(["scan", root])` returns 1 and does not raise
  - the output holds exactly one `ERROR` line, `ERROR  2024-07-04 - Barbecue:`, containing `2024-02-30`
    (or `not UTF-8 text`)
  - Midsommar and Kräftskiva are both listed

## 4. api/ — the events reads isolate the event (test only, no code change)

- [x] 4.1 Add `test_an_impossible_reel_yaml_date_is_an_error_row_not_a_500` (`requires_db`) to
  `tests/test_api_events_failures.py`, next to `test_unparseable_reel_yaml_on_the_list_is_an_error_row`.
  Add `2024-08-01 - Kräftskiva` to the `project` fixture's two events, as the existing error-row test does.
  Barbecue's `reel.yaml` is `version: 0\nmetadata:\n  title: Barbecue\n  date: 2024-02-30\n`.
  Parametrize a second case, where the `reel.yaml` is Latin-1 bytes.

  Verify:
  - `GET /api/v1/events` answers 200 with two summaries and one error row: `event_id` Barbecue, `failure`
    `unparseable_reel_yaml`, and a `detail` naming `2024-02-30` (or `not UTF-8 text`)
  - `GET /api/v1/events/{id}` and `GET …/reel` each answer 502 with `failure: unparseable_reel_yaml`
  - no response is a 500

## 5. scheduler/ — the worker fails the job (test only, no code change)

- [x] 5.1 Add `test_worker_fails_a_job_whose_reel_yaml_holds_an_impossible_date` (`requires_db`) to
  `tests/test_scheduler_worker.py`, next to `test_worker_fails_a_job_for_an_impossible_folder_date`
  (added in review). The job's event `2024-07-04 - Barbecue` has a `reel.yaml` setting
  `metadata.date: 2024-02-30`; the worker builds it with `default_build_job`.

  Verify:
  - on the current code the test fails with the bare `ValueError` (under `run` it killed the job's thread
    and left the row `running`)
  - after 2.1, `worker.process_next()` returns and the job is `failed`, its `error` naming
    `invalid value: '2024-02-30' on line 4`

## 6. Validation

- [x] 6.1 Run the validation gates:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, including `requires_db`

  Verify:
  - all are clean or green, apart from the known cairo `no-member` noise and the environmental title-card
    skips
  - `RENDER_GRAPH_VERSION` in `staleness/fingerprint.py` is unchanged
  - `git diff --stat` touches only `auto_reel_ng/reel/parser.py` and the four test files
