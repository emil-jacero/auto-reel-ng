## Context

Every route into a `ReelDocument` ends in `reel/schema.build_document`: `parser.loads_document` (v0), the
legacy importer (`legacy.import_legacy` builds a v0 mapping then calls it), `event/editorial.apply_editorial_write`,
`event/reconcile` and `cli/adoption`. A rule enforced there holds for the loader and for every writer, and a
writer fails before `write_document` runs, so nothing reaches disk. That is why all five checks sit in
`reel/`. A legacy document's unmapped fields never reach `build_document`; for the surrogate check only,
the parser therefore also scans the raw legacy mapping.

Checked against `main` (6a7fe16):

- `_req_time` (schema.py) rejects non-numbers and `value < 0`, then `float(value)` with an `OverflowError`
  guard for integers past 1.8e308. `nan < 0` and `nan <= x` are False, so NaN passes every later comparison
  too, including `end <= start` in `_parse_trims`.
- `_validate_version` is `version != SCHEMA_VERSION`.
- `_parse_ignore` normalizes each entry with `_parse_identity` and returns a tuple, no uniqueness check.
  `_validate_cross_references` already rejects a clip referenced twice across chapters.
- `_parse_look` is `dict(raw)`. Triage repro: `look: {2024-01-01: x}` loads, then `editorial_hash` raises
  `TypeError: keys must be str, int, float, bool or None, not datetime.date`.
- `loads_document` loads with the custom round-trip constructor, then routes on `"version" not in data`.
- The editorial writer `_apply_ignore` on `["x.mp4", "x.mp4"]` today writes both lines (probed); after the
  change `build_document` raises before `write_document`.

## Goals / Non-Goals

**Goals:**

- Each of the five invalid values is a `ReelParseError` naming its location, for every caller, with no new
  error type and no change to a caller.
- The surrogate and key-type checks are importable by `config/` (`config-yaml-hardening` gates on this change).

**Non-Goals:**

- `config.yaml` validation and the fingerprint canonicaliser: `config-yaml-hardening`.
- `look` values: still opaque (D-I). A `look` value that is `.nan` or a `date` is not refused here.
- Replacing `<unicode string>` in ruamel's error text and other parse-error wording: `reel-parse-error-polish`
  (it edits `parser.py` after this change merges).
- Chapter-name strictness and the legacy importer's silent drops: held or separate.

## Decisions

**D1. Reject, never repair.** A non-finite time, a `false` version, a repeated ignore entry, a non-string key
and a lone surrogate are refused with an error. Dropping the duplicate, replacing the surrogate with U+FFFD, or
stringifying the key would be a silent coercion, which the spec forbids ("A value is never coerced, clamped or
dropped to make a document load") and Principle I forbids. Alternative for the duplicate ignore (triage):
tolerate it and key `_entry_comments` by position. Rejected: it keeps a meaningless state alive in the schema
and adds a second code path in the writer (Principle VII); the duplicate-chapter-reference rule is the
precedent.

**D2. Trim times: finite after conversion.** In `_req_time`, keep the type check and the negative check, convert
with the existing `OverflowError` guard, then require `math.isfinite(result)`; the error reads
`time must be finite, got nan`, at the `in`/`out` location the function already receives. `-inf` is caught by the
negative check first (its message stays "non-negative"). Order matters: converting first means an integer
past the float range still reports "out of range" and not "not finite".

**D3. Version: exact integer.** `isinstance(version, bool) or not isinstance(version, int) or version != 0`
raises the existing message unchanged (`unsupported version False; this engine supports version 0`). The tests
only assert the message prefix, so callers that match it keep working. A ruamel `HexInt`/`ScalarInt` is an
`int` subclass and still passes, as `0x0` does today.

**D4. Duplicate ignore: first repeat wins the message.** In `_parse_ignore`, track normalized identities seen;
on a repeat raise `<source>: ignore[i]: duplicate ignore entry 'x.mp4' (first at ignore[j])`. Normalized, so
`./x.mp4` repeats `x.mp4`, which is the same clip. No change to `event/editorial.py`: a desired list with a
duplicate now raises from `build_document`, and the editorial route already answers `ReelError` as an invalid
submitted state. `reconcile.ignore_clip` is idempotent and never appends a duplicate.

**D5. `look` keys: iterative walk, string keys only.** `_parse_look` calls a scan that walks the `look`
mapping with an explicit stack, descending into mappings and into lists, and returns the first non-`str` key
with its path (`look.layers[0]`, rendered with the same dotted/indexed style as the other locations). Iterative,
not recursive, so a deep structure cannot raise `RecursionError` here: the loader limits nesting by what
ruamel can construct, but `build_document` also receives API-built mappings. The error names the key (`repr`)
and its type name. Quoted `'2024-01-01'` is a `str` and passes. Keys elsewhere are already validated by their
own parsers (`clips` by `_parse_identity`, `sort.custom_order` by name).

**D6. Surrogates: one scan, two call sites.** The same kind of walk visits every key and every string value of
the whole mapping and returns the path of the first string for which `s.encode("utf-8")` raises
`UnicodeEncodeError`. It is called (a) in `build_document`, right after `_validate_version` and before any
section parser, so no later message can embed the raw string and so every writer is covered; and (b) in
`parser.loads_document`, on the raw mapping in the legacy branch only, before `import_legacy_data`, because the
importer copies only the fields it maps. A v0 document reaches (a) once; it is not scanned twice. The message
quotes the offending key or path with `repr` (which escapes the surrogate: `'Fest \ud800'`) and never the raw
string, so the CLI's `ERROR <event>: <reason>` line can print it. Test with `.encode("utf-8")` on the message.

Alternative: a regex `[\ud800-\udfff]` per string. Equivalent in effect; `encode` states the actual
requirement (UTF-8 encodable) and needs no character-class literal that is itself a surrogate range. The
astral character `\U0001F386` is a single code point in Python, so it is not flagged.

**D7. Where the helpers live: `reel/values.py`.** Two pure functions, `find_lone_surrogate(tree)` and
`find_non_str_key(tree)`, each returning `None` or the location (path string, plus the offending key for the
second). They return rather than raise because `reel/` raises `ReelParseError` and `config/` must raise
`ConfigError`. `config/` may import `reel/` (it already imports `event/`, which imports `reel/`); `reel/` does
not import `config/`, so the layer order (Principle VI) holds. No re-export from `reel/__init__.py` (YAGNI);
`config-yaml-hardening` imports from `reel.values`.

**D8. No `RENDER_GRAPH_VERSION` bump.** Principle IV requires a bump when a change alters rendered bytes for
identical inputs. Inputs that load today and now fail were never rendering to a usable result: a NaN trim span
cannot be applied by the normalize step or compared by the staleness gate; the others crash `scan` or the
hash. Documents that remain valid hash and render exactly as before (`editorial_hash` of a valid `look`,
`ignore` and version is unchanged), so existing manifests stay fresh.

## Risks / Trade-offs

- [An existing `reel.yaml` with a repeated ignore entry, a `version: false`, or a non-string `look` key now
  fails to load] → Intended and loud: the event shows as an error row / `ERROR <event>:` line naming the
  location, and the other events are unaffected (per-event isolation). The fix is a one-line edit. All three were
  already broken or meaningless states (the latter crashed `scan`).
- [A `look` value later gets a non-JSON-able value (`.nan`)] → Out of scope here; values stay opaque. The
  fingerprint's `default=str` handles dates; `config-yaml-hardening` adds key-level canonicalisation.
- [The walk costs time on large documents] → One pass over a document of a few hundred scalars; negligible
  next to YAML construction.
- [`values.py` is a new module for two small functions] → Justified by the second consumer (`config/`),
  and keeps `schema.py` from holding a generic tree walker.
