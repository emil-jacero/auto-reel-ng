## Why

`config.yaml` is read by every client (`scan`, `render`, `enqueue`, `worker`, `serve`), and its content
flows on into the staleness fingerprint (the **defaults** component, D-2/D-C1) and into names, logs and
JSON bodies. Three ways a hand-edited file gets through the loader and then breaks something far from the
file were reproduced on main (6a7fe16) against `loads_project_config` and `staleness/fingerprint.py`:

- **A bare builtin error instead of `ConfigError`.** `look: {a: 2024-02-30}` makes ruamel's safe constructor
  build `datetime.date(2024, 2, 30)`, which raises `ValueError: day 30 must be in range 1..29 ...`.
  `a: !!bool maybe` raises `KeyError`, and deeply nested flow sequences raise `RecursionError`. The loader
  catches only `YAMLError`, so callers that handle `ConfigError` (the API's events route, the CLI's error
  path) see a traceback instead. `reel.yaml` already converts all of these to `ReelParseError`
  (`reel/parser.py`); `config.yaml` is the odd one out (Principle I, fail loud with a typed error).
- **Non-string `look` keys load, then crash the fingerprint.** `look: {2024-01-01: x}` and
  `look: {1: a, b: c}` both load. `_hash_json(dict(look_defaults))` then raises `TypeError` (`default=str`
  covers values, not keys; mixed `int`/`str` keys cannot be sorted). The defaults hash is computed for every
  event on every `scan`, so one bad key in the shared file kills the whole scan loop (Principle I:
  per-event isolation is the only tolerated softening, and a project-level file is not an event). The same
  `TypeError` is reachable through any editorial `look` that is not validated, via `editorial_hash`, which
  also serves as the API's ETag.
- **Lone surrogates in strings.** `layout: "x\ud800"` loads; `.encode("utf-8")` on the value then raises
  `UnicodeEncodeError` wherever it is printed, logged, hashed or sent as JSON. The same hole exists for
  every string the file carries.
- **Values that cannot be printed or hashed.** A hexadecimal integer longer than Python's int-to-str digit
  limit (`look: {a: 0xfff...}`) loads, then `json.dumps` raises `ValueError` while fingerprinting; a
  self-referencing alias (`look: &a {x: *a}`) loads, then raises `ValueError: Circular reference detected`.
  `reel.yaml` refuses the integer already (`reel/parser.py`, `_Constructor`); `config.yaml` does not.

The `reel.yaml` halves of the key-type and surrogate items are fixed by `reel-schema-value-validation`
(merged first); this change is the `config.yaml` loader and the fingerprint halves. HLD §6 phase 8 hardening
round; depends on no §8 research item.

## What Changes

- `loads_project_config` turns every failure of the YAML load (`ValueError`, `KeyError`, `IndexError`,
  `RecursionError`, `OverflowError`, ...) into `ConfigError("<source>: malformed YAML: ...")`, with the
  same catch order as `reel/parser.py`.
- After a successful load the loader validates the tree before any field is read, and raises
  `ConfigError` naming the key path for: a non-string key anywhere under `look`; a string (key or value,
  anywhere in the file) that is not encodable as UTF-8 (a lone surrogate); an integer that cannot be
  printed; a mapping or list that contains itself.
- `staleness.fingerprint._hash_json` stays byte-identical for every input it hashes today; for an input
  that plain JSON cannot key (`TypeError`), it hashes a canonical form with type-tagged keys instead of
  raising. `editorial_hash` and the **defaults** hash therefore never raise because of a key type.

Non-goals: no change to `reel.yaml` parsing or to the `ReelDocument` schema (`reel-schema-value-validation`
owns it); no new `config.yaml` keys; `look`, `worker`, `api` and `thumbnails` values stay opaque (D-I/D-J),
only the key type of `look` is constrained; no change to how `NaN`/`inf` numbers in config values hash
(they hash today and are not part of this bug); no schema or Alembic migration; no CLI or API surface change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `project-config`: a new requirement, "A config.yaml that cannot be loaded or used fails loud as a
  configuration error", covers the builtin-error conversion and the post-load tree validation.
- `change-detection`: a new requirement, "Fingerprinting does not raise on an editorial or defaults map",
  covers key types, with existing hashes unchanged.

## Impact

- **Packages:** `auto_reel_ng/config` (`project.py`) and `auto_reel_ng/staleness` (`fingerprint.py`). Both
  CLI and API are affected only in that a bad file now reports as `ConfigError` through their existing
  handlers (Principle V: no behaviour in `api/`).
- **Rendered output:** unchanged for identical inputs, so **no `RENDER_GRAPH_VERSION` bump**. Fingerprint
  inputs and every currently computable fingerprint are unchanged (see design, "Fallback only on failure").
  `title-card-whole-clip-cut` bumps the constant independently; this change must not touch that line.
- **Schema:** no `reel.yaml` change, no `config.yaml` key added; a file that was accepted and then crashed
  or misbehaved downstream is now rejected at load. No Alembic migration, no rescan.
- **Dependencies:** none.
