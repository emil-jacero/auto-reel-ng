## Why

Two development-tooling defects, neither visible to a user of the engine, the CLI or the API; both cost the
developer trust in the signals the tooling gives (Principle I, "fail loud": a warning nobody can act on teaches
everyone to ignore warnings, and a fixture builder whose output differs from the engine's own is a fixture that
lies about what the engine writes).

- **A deprecation warning in every test run that touches `TestClient`.** `fastapi.testclient` re-exports
  Starlette's `TestClient`, and `starlette/testclient.py` (installed 1.3.1) prefers `httpx2` and, when it is
  absent, falls back to `httpx` with `StarletteDeprecationWarning: Using httpx with starlette.testclient is
  deprecated; install httpx2 instead.` The dev extra declares only `httpx>=0.28.0`, so the warning is printed by
  `pytest tests/test_api_app.py` (and by all 13 test files that import `TestClient`) at import time. The
  triage note called the warning latent on the main venv (Starlette 1.3.1); re-checked, it is **not** latent:
  1.3.1 already carries the fallback warning and prints it. A later Starlette is free to drop the `httpx`
  fallback, which would turn the warning into an `ImportError`/`RuntimeError` at collection.
- **`scripts/make_dev_library.py` rewrites two `reel.yaml` files in a style the engine does not write.**
  `_edit_title` and `_ignore` round-trip a file the worker already wrote through a bare `YAML()`. The engine's
  writer (`reel/writer.py`, decision **D-G**, the round-trip guarantee the reel-document spec states) uses
  2-space mappings, 4-space sequences with offset 2; ruamel's defaults are flush (`chapters:\n- name: ''`).
  The dev library's `Grillning med grannar` and `Två kapitel - Tjörn` events therefore carry a foreign
  indentation that the engine's first real write (a GUI save, a reconcile apply) re-indents wholesale, so
  every diff against the dev library after a save is polluted by indentation noise. Two archived changes
  worked around it in their verification tasks (`chapter-management-screen`, `clip-cuts-screen`: "first
  normalise each `reel.yaml`"); this change removes the cause.

HLD §6 phase 8 (v1 polish round); depends on no open §8 research item and on no other change.

## What Changes

- **`httpx2` joins the dev extra; `httpx` stays.** `pyproject.toml` `[project.optional-dependencies].dev` gains
  `httpx2>=2.13.1`. `httpx` is kept because `tests/test_cli_serve.py` and `tests/test_cli_serve_signals.py` use
  it directly as a real HTTP client (`httpx.get`, `httpx.TransportError`, `httpx.ReadTimeout`), which
  `httpx2` does not provide under that name. `TestClient` then runs on `httpx2`, and the warning is gone.
  Checked, not assumed: all 13 `TestClient` files pass (DB-backed cases included) on Starlette 1.7.0 with
  `httpx2` 2.13.1 as well as with `httpx` (design, "Research & Decisions").
- **A test pins the absence of the warning** (importing `starlette.testclient` in a fresh interpreter with
  `StarletteDeprecationWarning` turned into an error succeeds), so a dev environment that regresses to `httpx`-only fails loudly
  instead of printing a line that scrolls by.
- **The engine's canonical round-trip YAML becomes a public helper.** `reel/writer.py`'s private `_yaml()` is
  renamed `round_trip_yaml()` (same body, same indent settings, same two internal call sites), so the script
  and any other tooling that must rewrite a `reel.yaml` outside `write_document` use the one definition
  instead of a private import or a copy that drifts.
- **`make_dev_library.py` edits via that helper.** `_edit_title` and `_ignore` share one
  `_roundtrip(reel, mutate)` that loads and dumps with `round_trip_yaml()`; comments and key order are kept,
  and an engine-style file stays engine-style (byte-stable apart from the edited lines).
- **A test pins the script's output** is byte-stable under the engine's writer, for both edits.

## Non-goals

- No change to the engine's, CLI's or API's behaviour; no `reel.yaml` or `config.yaml` schema change; no new
  parser tolerance for foreign indentation (the schema stays constrained to the canonical style, reel-document
  "Round-trip preserving writer").
- No `filterwarnings` entry that hides the warning; that would leave the dependency drift in place
  (considered and rejected in the design). No pin of Starlette.
- No migration of `tests/test_cli_serve*.py` from `httpx` to `httpx2`.
- `scripts/seed_compose_library.py` is untouched (it copies a fixture; it does not round-trip YAML).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none: no capability's requirements change. The change is dev tooling only, so it opts out of specs
     with `skip_specs: true` in .openspec.yaml instead of inventing a requirement. -->

## Impact

- **Rendered output / fingerprint:** unchanged. No `RENDER_GRAPH_VERSION` bump, no staleness-fingerprint input
  change.
- **Schema:** no `reel.yaml` / `config.yaml` change; no Alembic migration; no rescan.
- **Packages:** `scripts/` (`make_dev_library.py`) and `auto_reel_ng/reel/` (`writer.py`, a rename only), plus
  `pyproject.toml` and `tests/`. CLI and API untouched (Principle V).
- **New dependency (Principle VII justification):** `httpx2` in the **dev** extra only, never a runtime
  dependency. It is the client Starlette's own `TestClient` now prefers; keeping only `httpx` is a standing
  deprecation warning today and a possible hard failure when Starlette drops the fallback. Its dependencies
  (`httpcore2`, `anyio`, `idna`, `truststore`) are small and `anyio` is already present via Starlette.
  Developers re-run `pip install -e ".[dev]"` to pick it up.
