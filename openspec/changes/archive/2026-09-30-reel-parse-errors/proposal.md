## Why

HLD **§6 phase 3** (`reel.yaml` loader) defect, found while **phase 8** (GUI v1) consumes the events list.
The fix is the rule HLD §5 "Error handling" names: fail loud, and keep per-event isolation so one bad event
does not kill the batch. §2 learning #5 first set that rule for the probe. Constitution Principle I puts it the same way: "one bad event MUST
NOT kill a batch, but it MUST be reported as failed".

`reel.yaml` is hand-written (D-2, HLD §4.6). The `reel-document` spec requires that parsing "SHALL fail
loudly with a clear error on malformed or invalid content", and every caller relies on that error being a
`ReelError`. The events list, the event detail, `…/reel`, and the CLI's `_checked_document` (used by `scan`,
`render`, `enqueue` and `adopt-renders`) each catch `ReelError` to isolate one event. The worker catches
`EngineError` and fails the job with the reason.

`reel/parser.load_document` wraps two kinds of failure as `ReelParseError` today: an `OSError` from reading
the file, and ruamel's own `YAMLError`. **Two failures escape as a bare builtin `ValueError`:**

- **An impossible date.** YAML's core schema reads an unquoted `2024-02-30` as a timestamp. ruamel's
  timestamp constructor then calls `datetime.date(2024, 2, 30)`, which raises `ValueError: day 30 must be
  in range 1..29 for month 2 in year 2024`. This happens during `load`, before the v0 or legacy routing, so
  both formats are affected. It also happens wherever the value appears, `look` included. `2024-13-45`
  and `2024-02-29T25:00:00` fail the same way, and so do the explicit tags `!!int abc` and `!!float abc`.
  A **quoted** `'2024-02-30'` is already a `ReelParseError`, from `schema._parse_date`.
- **A file that is not UTF-8.** `read_text(encoding="utf-8")` raises `UnicodeDecodeError`, a `ValueError`
  and not an `OSError`. An example is a `reel.yaml` saved as Latin-1 with `Kräftskiva` in it.

These two are the likely ones, but ruamel's load step leaks other builtin errors on malformed text as well.
An adversarial review fed 102 odd inputs to today's loader, and 41 escaped as something other than
`ReelParseError`:

- `KeyError` for `!!bool maybe`
- `IndexError` for an empty `!!int`
- `AttributeError` for `!!set abc`
- `TypeError` for a complex key holding a list
- the scanner's `ValueError` for the double-quoted escape `"\UFFFFFFFF"`
- `RecursionError` for deep nesting

Each one crashes the batch in the same way (design, Context).

Reproduced on a scratch project (`2024/2024-07-04 - Barbecue` with `date: 2024-02-30`, and separately
Latin-1 bytes, plus two healthy siblings; ruamel.yaml 0.19.1):

| Caller | Today | Specified |
|---|---|---|
| `GET /api/v1/events` | **500** for the whole list | 2 summaries + 1 `unparseable_reel_yaml` error row |
| `GET /api/v1/events/{id}` | **500** | 502 problem body with the failure kind |
| `GET /api/v1/events/{id}/reel` (and so `PUT`) | **500** | 502 problem body with the failure kind |
| `auto-reel scan` / `render` | **traceback**, no event listed | `ERROR <event>: <reason>`, the rest listed, exit 1 |
| worker `_process` | `ValueError` escapes the `EngineError` catch; the thread dies and the job row stays `running` | job `failed` with the reason |

`classify_event_failure` returns `None` for a bare `ValueError` (or any other builtin error), so the
isolation code can do nothing with it. One mistyped date in one event's `reel.yaml` takes down the whole events screen of the GUI.

## What Changes

- **An impossible scalar is a parse error that names the value and its line.** The parser's YAML loader
  turns any non-YAML error raised while one node is constructed into ruamel's own `ConstructorError`,
  worded from that node's value and position. `loads_document` raises every `ConstructorError` as
  `ReelParseError` under the prefix `invalid value`: the text is well-formed YAML, so the message does not
  call it malformed. Example message:
  `…/reel.yaml: invalid value: '2024-02-30' on line 4, column 9 is not a real date (day 30 must be in
  range 1..29 for month 2 in year 2024)`. This covers v0 and legacy documents alike, any position in the
  document, and every typed tag (`!!int`, `!!float`, `!!bool`, …). The message is one line, because the
  events list's error row shows it in one table cell. A real syntax error keeps the prefix
  `malformed YAML` and ruamel's multi-line excerpt.
- **Anything else the YAML reader raises is a parse error too.** `loads_document` gets one backstop
  clause after `except YAMLError`, around the load call only. It turns a failure that ruamel raises
  without a node, such as the scanner's `chr()` error or a `RecursionError`, into
  `ReelParseError(f"{source}: malformed YAML: {exc}")`. Such a message names the file and ruamel's reason,
  but no line, because ruamel reports none. The constructor hook passes a `RecursionError` through
  unchanged, so a document nested too deep to construct lands here too, instead of being blamed on one node.
- **A non-UTF-8 file is a parse error.** `load_document` wraps `UnicodeDecodeError` as `ReelParseError`:
  `…/reel.yaml: not UTF-8 text (invalid continuation byte at byte 32)`.
- **No caller changes.** Every new error is a `ReelParseError`, so every existing `ReelError` handler applies
  unchanged. `classify_event_failure` maps them to `unparseable_reel_yaml`, and the CLI prints them as
  `ERROR` lines. No new failure kind is added.
- **Tests:**
  - parser unit tests for each path: impossible values and unsatisfiable tags, the backstop, and non-UTF-8
  - one events-list API test (one error row, not a 500)
  - one CLI `scan` test (one `ERROR` line)
  - one worker test (the job ends `failed` with the reason, not `running`)

## Non-goals

- **`auto-reel import` has its own reader.** `cli/commands._read_yaml` and `_has_version` load with
  `YAML(typ="safe")` directly, not through `load_document`. They have the same gap: a legacy
  `metadata.yaml` with `date: 2024-02-30` or Latin-1 bytes crashes `import` (verified). Worse, `import`
  has no per-event isolation at all, and even a malformed `metadata.yaml` (`metadata: [unclosed`) crashes the
  whole run (verified). The `headless-cli` spec has no isolation requirement for `import`. Fixing it is
  its own change in `cli/`: a named follow-up, `import-event-isolation`.
- **Project `config.yaml`.** `config/project.load_project_config` has the same two gaps and raises a bare
  `UnicodeDecodeError`/`ValueError` instead of `ConfigError`. It is a whole-project read, so the list fails
  as a whole either way (500 instead of a shaped error). This is a separate package and a separate
  capability (`project-config`), and a named follow-up.
- **`POST /api/v1/jobs`.** Its output-collision walk is covered by `jobs-project-guards`, which skips a
  sibling that raises `ReelError`. After this change, a bad-date sibling is such a sibling. The target
  event's own unparseable `reel.yaml` staying a bare 500 is that change's named follow-up.
- **No new failure kind.** An impossible value and a non-UTF-8 file are both "a `reel.yaml` that cannot be
  parsed". The closed `EventFailure` set is unchanged.
- **No leniency.** An impossible date is never coerced to a string, clamped, or dropped (Principle I).
- **No change to validation of well-formed values.** `2024-02-29` still loads as a date, and a quoted
  `'2024-02-30'` keeps its existing `metadata.date: invalid date` message.
- **Text that loads but cannot be served.** A double-quoted lone-surrogate escape (`title: "Fest \ud800"`)
  loads today as a string that cannot be encoded as UTF-8. Pydantic's JSON dump and FastAPI's
  `JSONResponse` both reject such a string (verified in isolation). So it can likely break the events
  list's response, but the endpoint itself was not exercised. It is not a load failure but a rule for
  loaded strings in `schema`. Named follow-up.
- **Non-finite trim times.** `in: .nan` and `out: .inf` pass `schema._req_time` today (verified), because
  NaN is neither negative nor `<=` anything. This is a validation gap in the same requirement's "a negative
  time" rule, not a load failure. Named follow-up.
- **The worker's other exceptions.** `scheduler/worker._process` catches only `EngineError`. After this
  change no `reel.yaml` content reaches it as anything else, but any other unexpected exception still kills
  the job's thread and leaves its row `running` until a restart requeues it. Named follow-up.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reel-document`: `Requirement: Fail-loud parse and validation`:
  - an impossible typed scalar, a value its explicit tag cannot hold, other text the YAML reader cannot
    load, and non-UTF-8 bytes all fail as the same parse error as any other malformed content. Each names
    the file and the problem: the value and its line, ruamel's reason when ruamel gives no position, or
    the first bad byte
  - the parser raises no other exception type for document content, so every caller's per-event
    isolation applies

## Impact

- **Packages:**
  - `reel/`: `parser.py` only. It gains a round-trip constructor subclass, a value-level clause for
    `ConstructorError`, a backstop clause around the load call, and a `UnicodeDecodeError` clause
  - `tests/`:
    - `test_reel_parser.py`
    - `test_cli_event_metadata.py` (one `scan` case)
    - `test_api_events_failures.py` (one `requires_db` list case)
    - `test_scheduler_worker.py` (one `requires_db` worker case)
  - nothing else changes
  - `api/` is not touched, because `classify_event_failure` already maps `ReelError` to
    `unparseable_reel_yaml`. Verified on the scratch copy: a quoted bad date, already a `ReelParseError`,
    classifies as that kind
- **CLI vs API (Principle V):** the fix is in the engine loader, so both clients and the worker get it
  through their existing handlers. No CLI flag, endpoint, or status code is added.
- **Wire:** the three events reads answer these files with the shapes their spec already requires: an
  error row, or the 502 problem body with `failure: unparseable_reel_yaml`. Before, they answered with an
  unshaped 500. No schema or OpenAPI change.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.**
- **Fingerprint:** inputs unchanged. A document that loads today loads to the same typed fields. The
  constructor hook only acts when construction raises.
- **Schemas:** no `reel.yaml` or `config.yaml` schema change, **no Alembic migration**, no rescan.
- **Complexity (Principle VII):** a constructor subclass with two small wording helpers (about 35 lines)
  and three `except` clauses. The two `except Exception` clauses are deliberate: the review reproduced six
  builtin error types from ruamel's load step. A narrower catch leaves demonstrated inputs crashing the
  batch (design, "Where to turn a builtin error into a parse error").
- **Dependencies:**
  - no new library: the hook subclasses ruamel.yaml's `RoundTripConstructor`. The tests pass on 0.18.0,
    the `>=0.18.0` floor, and on 0.19.1, the version a fresh venv resolves, so the floor is unchanged
  - gate: none. It can start now
  - it complements `jobs-project-guards` and does not conflict with it: this change touches only
    `reel/parser.py` and its tests
- **Size (Principle VIII):** one module in `reel/`, one capability delta, and tests.
