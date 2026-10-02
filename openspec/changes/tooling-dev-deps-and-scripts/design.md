## Context

See proposal.md for the motivation. Two independent edits share a change because both are small, both are
developer-tooling, and neither touches product behaviour.

Current state, re-checked against `origin/main` (6a7fe16):

- `pyproject.toml` dev extra ends `"httpx>=0.28.0"` (line 43); `[tool.pytest.ini_options]` has no
  `filterwarnings`. The main venv has Starlette 1.3.1, FastAPI 0.139.0, httpx 0.28.1, no `httpx2`.
  `starlette/testclient.py` (1.3.1 and every release from 1.4.1 to 1.7.0 checked) does
  `try: import httpx2 as httpx / except ModuleNotFoundError: import httpx` and, on the fallback, warns
  `StarletteDeprecationWarning` (a `DeprecationWarning` subclass) with `stacklevel=2`, so pytest attributes it
  to `fastapi/testclient.py:1`. If neither is installed it raises `RuntimeError`. The triage note's claim that
  1.3.1 prints no warning is wrong: `pytest tests/test_api_app.py` on the main venv shows it today.
- `auto_reel_ng/reel/writer.py` `_yaml()` (lines 25-35) is the single place the canonical block style is set:
  `YAML()`, `preserve_quotes = True`, `indent(mapping=2, sequence=4, offset=2)`. It is used by `document_to_data`
  (structural deep copy) and `_dump_to_str`. `reel/parser.py` has its own, different `_yaml()` (custom
  constructor for fail-loud scalars, no indent: it only loads). Nothing outside `writer.py` calls the writer's.
- `scripts/make_dev_library.py` `_edit_title` and `_ignore` (lines 142-155) are the only two functions that
  load and dump `reel.yaml` with a bare `YAML()`. The other `reel.yaml` files the script creates are literal
  strings already in the canonical style, and phase 1's files come from the worker's `write_document`.
  Reproduced on the worktree: a canonical file through `_edit_title` becomes
  `chapters:\n- name: ''\n  clips:\n  - a.mp4`, and through `_ignore` gains `ignore:\n- x.mp4`.

## Goals / Non-Goals

**Goals:**

- `pytest` on the dev environment declared by `pyproject.toml` prints no `StarletteDeprecationWarning`, and a
  regression to an `httpx`-only environment fails a test.
- The dev library's `reel.yaml` files are in the engine's canonical style after every step the script takes, so
  the first engine write changes only the lines the user edited.
- One definition of the canonical style.

**Non-Goals:**

- Teaching the parser or writer foreign indentation (reel-document: the schema is constrained to the
  canonical style).
- Moving the live-server tests to `httpx2`, or touching runtime dependencies.

## Requirements (tooling, RFC 2119)

No capability spec changes (proposal, "Capabilities": `skip_specs: true`); these are the contract the tasks and
tests enforce, stated in the same terms a spec would use.

1. The `dev` extra of `pyproject.toml` SHALL declare `httpx2` (>= 2.13.1) and SHALL keep `httpx` (>= 0.28.0).
   - Scenario, fresh dev environment: `pip install -e ".[dev]"` then `pytest tests/test_api_app.py` ends
     without a `StarletteDeprecationWarning` in the warnings summary.
   - Scenario, `httpx`-only environment (the state today): the dependency test fails with the warning text,
     naming `httpx2`, instead of the suite passing quietly.
2. `import starlette.testclient` in a fresh interpreter run with `-W error::DeprecationWarning` SHALL succeed in
   the dev environment.
3. `round_trip_yaml()` SHALL return a ruamel round-trip `YAML` with `preserve_quotes` and
   `indent(mapping=2, sequence=4, offset=2)`, and SHALL be the only place that style is set. `write_document`,
   `dumps_document` and `document_to_data` SHALL behave exactly as before.
4. `make_dev_library.py` SHALL rewrite a `reel.yaml` only through `round_trip_yaml()`, SHALL keep comments and
   key order, and its output SHALL be byte-stable under the engine's writer.
   - Scenario, retitle: an engine-style file with a trailing comment and a named chapter, through
     `_edit_title`, differs from the input only on the `title:` line (the comment alignment ruamel
     recomputes is on that line too), and `dumps_document(loads_document(output)) == output`.
   - Scenario, dismiss: the same file through `_ignore` gains exactly an `ignore:` key with one
     entry in the 2/4/2 style (`ignore:\n  - x.mp4`), nothing else changes, and the output loads (the
     parser accepts it) and is byte-stable under the writer.

## Research & Decisions

### Which httpx2 behaviour risk to check
**Context**: `TestClient` is used by 13 test files (`test_api_app`, `_editorial_read`, `_editorial_write`,
`_events`, `_events_failures`, `_jobs`, `_media`, `_openapi`, `_thumbnails`, `_web_mount`, `_ws_e2e`,
`_ws_lifecycle`, `test_editorial_write_e2e`); media routes assert `416`/`Range` headers, the WebSocket tests use
`TestClient.websocket_connect`. Swapping the transport library under them could change behaviour.
**Explored**: scratch targets (never the repo venv) with Starlette 1.7.0 and httpx2 2.13.1 put first on
`PYTHONPATH`, running the 13 files from the worktree, once with only `httpx` (warning, the baseline) and once
with `httpx2` (the candidate), including the `requires_db` cases: both pass in full; the candidate has no
warnings summary. `pip index` shows httpx2 2.13.1 as the current release (BSD-3-Clause, Python >= 3.10);
Starlette 1.4.1, 1.5.1, 1.6.0 and 1.7.0 all carry the same httpx2-first import and the same warning.
**Decision**: add `httpx2>=2.13.1` to the dev extra; keep `httpx`.
**Rationale**: it is the client `TestClient` prefers, it removes the warning at its cause, and it is robust to
Starlette dropping the fallback. The 2.13.1 floor is the version verified; the upper bound is left open because
`TestClient` is the only consumer.

### httpx2 vs a `filterwarnings` entry
**Context**: the triage sketch offered both.
**Explored**: `filterwarnings = ["ignore:Using `httpx` with `starlette.testclient`...:DeprecationWarning"]`.
**Decision**: not taken (kept as the fallback the proposal names only if httpx2 had changed `TestClient`
behaviour, which it did not).
**Rationale**: a filter hides the symptom and leaves the suite exposed to the day the fallback is removed; it
also silences a message that would be the first sign of the next Starlette deprecation.

### How to pin the absence of the warning
**Context**: `StarletteDeprecationWarning` fires once at import, and pytest has already imported
`starlette.testclient` (through `fastapi.testclient`) by the time any test runs, so asserting on pytest's
warnings recorder inside the process cannot see it.
**Explored**: `filterwarnings = ["error::starlette.exceptions.StarletteDeprecationWarning"]` in
`pyproject.toml` (breaks collection of 13 files for a missing dev dependency, but also turns every future,
unrelated Starlette deprecation into a suite-wide collection error); an in-process `importlib.reload`
(mutates global module state other tests share); a subprocess.
**Decision**: one test, `tests/test_dev_dependencies.py`, runs
`[sys.executable, "-W", "error::DeprecationWarning", "-c", "import starlette.testclient"]` and asserts a zero
return code, with the captured stderr as the assertion message. It also asserts `import httpx` still works
(the live-server tests need it).
**Rationale**: isolated, no global state, loud and specific. Tests already spawn subprocesses
(`test_cli_serve*.py`); the "subprocess only in `ffmpeg/`" rule of Principle VI is about product code.

### Where the canonical YAML lives
**Context**: the script needs the engine's exact style. The sketch offered importing the private `_yaml`,
promoting it, or inlining `indent(2, 4, 2)`.
**Decision**: rename `reel/writer.py`'s `_yaml()` to the public `round_trip_yaml()`; both internal call sites
and the script use it. It is not re-exported from `auto_reel_ng.reel`'s `__all__` (it is a writer detail the
script imports from `auto_reel_ng.reel.writer`).
**Rationale**: a script importing an underscore name breaks on the next refactor; an inline copy is the exact
drift this change fixes. `parser._yaml` is deliberately left alone: it differs (custom constructor) and does
not write.

### One round-trip helper in the script
**Decision**: `_roundtrip(reel: Path, mutate: Callable[[CommentedMap], None]) -> None` loads with
`round_trip_yaml()`, applies `mutate`, and dumps back to the same file; `_edit_title` and `_ignore` become
one-line callers. The existing behaviour (write in place, no atomic rename) is kept: it is a throwaway
script run against a directory it just built.

## Risks / Trade-offs

- **[A future httpx2 release changes `TestClient` behaviour]** -> the floor is `>=2.13.1`, the suite exercises
  `TestClient` in 13 files, and the failure would show in CI-equivalent runs, not in production.
- **[The subprocess test is slow]** -> it imports Starlette only; well under a second.
- **[ruamel realigns a trailing comment on the edited line]** -> accepted and asserted (the scenario names it);
  the engine's writer does the same.
- **[Developers with an old venv see the test fail]** -> intended: the message names
  `pip install -e ".[dev]"`.
- **Pre-existing, left alone:** `make_dev_library.py` writes `reel.yaml` non-atomically; a crash mid-run
  leaves a broken fixture the next run rebuilds from scratch.

## Idempotency / failure

Not render-related: no ffmpeg invocation, no job, no `.part` file changes. Re-running the script rebuilds
`DEST` from scratch exactly as before; a failed `_roundtrip` (unreadable or non-mapping `reel.yaml`) raises
the ruamel/`OSError` as today and aborts the build, with nothing swallowed.
