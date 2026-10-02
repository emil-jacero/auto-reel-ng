## Why

`reel.yaml` is hand-written (D-2) and the `reel-document` spec says parsing "SHALL fail loudly with a clear
error on malformed or invalid content" and that a value is never coerced to make a document load. Constitution
Principle I puts it the same way. Five kinds of value still load although the rest of the engine cannot use
them, each found by a bug triage against `main` (6a7fe16) and reproduced with `loads_document`:

- **A lone surrogate in a string.** `title: "Fest \ud800"` loads. `metadata.title` is then a `str` that
  `.encode("utf-8")` refuses, so `auto-reel scan` dies in `print(title)` with `UnicodeEncodeError` and
  `GET /api/v1/events/{id}/reel` answers 500 (the JSON body cannot be encoded). The writer escapes the
  character (`"Fest \uD800"`), so an editorial write of one would persist it and the event would then fail
  on every read.
- **A non-finite trim time.** `in: .nan` and `out: .inf` load as `Trim(start=nan, ...)` and `Trim(1.0, inf)`.
  `_req_time` tests `value < 0`, and the later `end <= start` test, and both are False for NaN. The API then
  serializes the span as `null` (`trims: [{"in": null, "out": null}]` with 200), and a NaN never equals itself,
  so every editorial write sees a changed span and re-emits it.
- **`version: false` and `version: 0.0` load as v0.** `_validate_version` compares with `!=`, and `False == 0`
  and `0.0 == 0` in Python. The spec says only the integer `0` is a version.
- **Duplicate `ignore` entries.** `ignore: [x.mp4, y.mp4, x.mp4]` loads. The editorial writer keys each
  entry's comments by identity, so when the list is edited, every copy receives the last copy's comments (the
  first copy's comment is lost). A duplicate has no meaning, and a duplicate chapter reference is already
  rejected for the same reason.
- **A `look` with a non-string key.** `look:` with `2024-01-01: x`, or `{1: a, b: c}`, loads, because
  `_parse_look` only shallow-copies the map. `editorial_hash` then raises `TypeError` (`json.dumps(sort_keys=True)`
  accepts a `date` value through `default=str` but not a `date` key, and cannot sort a mixed `int`/`str` key
  set). `auto-reel scan` dies with a traceback on that event, which kills the whole scan loop and breaks the
  per-event isolation of Principle I, and `GET .../reel` returns 500.

The reel half of the cure belongs in `reel/`, where the document is validated once for every caller (loader,
legacy importer, editorial writer, reconcile). The `config.yaml` halves of the surrogate and key-type items, and
the fingerprint's defence against non-string keys, live in `project-config` and `change-detection`; they are
the follow-up change `config-yaml-hardening`, which reuses the checks defined here.

## What Changes

- A trim `in`/`out` that is not finite (`.nan`, `.inf`, `-inf`) is a parse error naming the span.
- `version` is accepted only as the integer `0`: `false`, `0.0`, `'0'`, and a missing value fail with the
  existing unsupported-version message.
- An `ignore` list that repeats an identity (after normalization) is a parse error naming the identity and the
  position of the repeat, by the rule that already rejects a duplicate chapter reference. **BREAKING** only for a
  `reel.yaml` that already holds a pointless duplicate: it now fails loud with the per-event parse error instead
  of loading.
- Every mapping key inside `look`, at any depth, must be a string; a non-string key is a parse error naming
  `look.<path>`. Names and values stay opaque (D-I), so no existing valid `look` is refused.
- Any string, key or value, anywhere in the document, containing a lone surrogate is a parse error naming the
  key path, for a v0 document, a legacy document, and a document that a writer builds before it is written.
- The two checks that `config-yaml-hardening` needs (find a lone surrogate, find a non-string key) are
  implemented as small pure functions in a `reel` module, returning the location instead of raising, so
  `config/` can raise its own `ConfigError`.
- No `RENDER_GRAPH_VERSION` bump: no document that loaded and rendered meaningfully before renders differently
  (design, Decisions).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reel-document`: "Fail-loud parse and validation" gains finite trim times, integer-only `version`,
  duplicate-free `ignore`, and UTF-8-encodable strings; "`look` is carried opaquely in v0" gains the
  string-keys-only constraint.

## Impact

- Code: `auto_reel_ng/reel/schema.py` (`_req_time`, `_validate_version`, `_parse_ignore`, `_parse_look`, a call
  in `build_document`), `auto_reel_ng/reel/parser.py` (a call before the legacy branch), and a new
  `auto_reel_ng/reel/values.py` (the two scans). One package.
- Tests: `tests/test_reel_parser.py`, `tests/test_event_editorial.py`, new `tests/test_reel_values.py`.
- Callers: none change. They already treat `ReelParseError` as the per-event failure (CLI `ERROR <event>:`
  line, events-list error row, 502 problem body, the editorial write's invalid-state answer).
- Not touched: `config/project.py`, `staleness/fingerprint.py`, `event/editorial.py` (the writer meets the new
  rules through `build_document`).
