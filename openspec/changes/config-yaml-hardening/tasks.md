## 1. config/ - the YAML load

- [ ] 1.1 In `loads_project_config`, keep `except YAMLError` and add a final `except Exception`
  (pylint-disabled with the parser's comment) raising `ConfigError(f"{source}: malformed YAML: {reason}")`,
  `reason = str(exc) or type(exc).__name__`. Add tests in `tests/test_project_config.py` (parametrised) for
  `look: {a: 2024-02-30}`, `a: !!bool maybe` and 100000 nested `[`, each asserting `ConfigError` and that
  the message contains the source; run `.venv/bin/python -m pytest tests/test_project_config.py`.

## 2. config/ - tree validation

- [ ] 2.1 Add private `_validate_tree(data, source)` (design: lone surrogate anywhere, unprintable int,
  non-str key under `look`, self-referencing container, `RecursionError` -> "nested too deeply"; path-set
  cycle detection plus a done set) and call it in `loads_project_config` right after the mapping check,
  before any field parser. Surrogates and `look` key types call `find_lone_surrogate` / `find_non_str_key`
  from `auto_reel_ng.reel.values` (merged by `reel-schema-value-validation`); integers and cycles are a
  private iterative scan. Tests: parametrised refusals with the exact key path in the message (`layout` surrogate,
  `look.a` surrogate in a value and in a key, `database.url`, `look: {2024-01-01: x}`, `look: {1: a, b: c}`,
  `look: {title: {1: x}}`, a 5000-digit hex int, `look: &a {x: *a}`), a shared non-cyclic alias still
  accepted, and acceptance cases (int key under `worker`, `Café`/`日本語` in `look`).
- [ ] 2.2 Through `load_project_config(tmp_path)` (file path form) assert a bad file raises `ConfigError`
  carrying the file path, and that the CLI's `main` reports it as the one-line error with a non-zero exit
  (`tests/test_cli_main.py`, in-process `main(["scan", root])` on an empty library, no media) for the `2024-02-30` case. Update the module docstring
  of `config/project.py` to state that the loader validates `look` key types and string encodability.

## 3. staleness/ - the hash fallback

- [ ] 3.1 In `staleness/fingerprint.py` change `_hash_json` to try the existing `json.dumps` first and, on
  `TypeError`, hash `_tag_keys(value)` (every mapping key -> `f"{type(key).__name__}:{key}"`, recursive over
  mappings, lists and tuples). Do not touch `RENDER_GRAPH_VERSION` or its comment block. Tests in
  `tests/test_staleness_fingerprint.py`: a native-key map (str, all-int, all-bool) hashes equal to the
  SHA-256 of `json.dumps(v, sort_keys=True, default=str)` computed in the test; a `date`-key `look_defaults`
  yields a `compute_fingerprint` result stable across two calls and moved by a value change; mixed
  `{1: .., "b": ..}` `look` on a directly constructed `ReelDocument` gives an `editorial_hash` that moves
  with either value; `{1: "a", "1": "b"}` and `{1: "b", "1": "a"}` differ; a pinned literal for one
  fallback hash, so the tag format cannot drift silently. Run the file's whole suite to prove the existing
  pinned fingerprint test is untouched.

## 4. Validation gates

- [ ] 4.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` (only the known
  cairo `no-member` noise), and confirm all clean.
- [ ] 4.2 Run the full `.venv/bin/python -m pytest` (podman needed for `requires_db`; otherwise
  `-m "not requires_db"` and say so) and confirm it passes with no new skips.
