## Context

`loads_project_config` (`config/project.py`) runs `YAML(typ="safe").load(text)` and catches only
`YAMLError`; it then reads `look`, `layout`, `worker`, ... as opaque values (D-I/D-J). `cli/main.py`
reports any `EngineError` (which `ConfigError` is) as a one-line error, and `api/routes/events.py` maps
`ConfigError` to a typed response, so a `ConfigError` is the only failure the callers already handle.
`staleness/fingerprint._hash_json` is `json.dumps(value, sort_keys=True, default=str)` then SHA-256; it is
the engine of `editorial_hash` (also the API ETag), the **defaults** hash, the clip-set hash and the
combined hash. `reel/parser.py` already converts builtin constructor errors to `ReelParseError` and refuses
an unprintable integer; `reel-schema-value-validation` (a gate, merged before this change is implemented)
adds recursive string-key and lone-surrogate checks on the `reel.yaml` side.

Sequencing: `title-card-whole-clip-cut` (a gate) changes `fingerprint.py` only at `RENDER_GRAPH_VERSION`
and its comment block. This change edits `_hash_json` only and MUST NOT touch the constant or the pinned
fingerprint test values (the pinned test is updated by that gate).

## Goals / Non-Goals

**Goals:**
- A `config.yaml` that cannot be used fails at load as `ConfigError` naming the cause and, where there is
  one, the key path - never as a builtin exception and never later, in an unrelated layer.
- Hashing a `look` map or an editorial dict never raises `TypeError` for key types, and no hash that is
  computable today changes.

**Non-Goals:**
- Interpreting `look` values, or constraining the key types of `worker`, `api`, `thumbnails` (their
  consumers look up named keys; a stray non-string key there is inert).
- Guarding `json.dumps` against exponential alias expansion ("billion laughs"); the scan below visits each
  shared node once, but expansion at hash time is not addressed (no reproduced failure, YAGNI).

## Research & Decisions

### The YAML load: what escapes `except YAMLError`
**Context**: The reported bug is `ValueError` for `2024-02-30`; the triage sketch only listed that.
**Explored**: against the repo's ruamel with `YAML(typ="safe")`: `look: {a: 2024-02-30}` -> `ValueError`;
`a: !!bool maybe` -> `KeyError`; 100000 nested `[` -> `RecursionError`; a decimal integer past 4300 digits
-> `ValueError` (from `int()`); `a: !!int 1_2` loads. `reel/parser.py` handles the same set by catching
`ConstructorError`/`YAMLError` first and a broad `Exception` last (`# pylint: disable=broad-exception-caught`),
naming `str(exc) or type(exc).__name__`.
**Decision**: Mirror that shape: `except YAMLError` keeps its message; a second `except Exception` (same
pylint disable and comment) raises `ConfigError(f"{source}: malformed YAML: {reason}")` with
`reason = str(exc) or type(exc).__name__`. The safe loader has no node-to-line mapping for these, so no line
is reported (a line would need `parser._Constructor`, which is round-trip only; out of scope).
**Rationale**: A fixed tuple would miss the next ruamel leak (`IndexError`, `OverflowError`, ...); the
parser already established the broad catch as the house pattern for exactly this boundary.

### Post-load tree validation, in `config/project.py`
**Context**: The loaded data are plain `dict`/`list`/scalars. Four classes of value pass the loader but
break later: non-str `look` keys, lone surrogates, integers that cannot be printed, self-referencing aliases.
**Explored**: reproduced each; `json.dumps` fails with `TypeError` (keys), `ValueError` (cycle,
digit limit), and `str.encode` with `UnicodeEncodeError`. The `reel-schema-value-validation` checks live in
`reel/values.py` as public, cycle-safe helpers (surrogates, non-str keys); there is none for integers or cycles.
**Decision**: One private function `_validate_tree(data, source)`, called once on the loaded mapping before
any field is read (so a bad `layout` surfaces as the surrogate error, not as a type error). It raises
`ConfigError` with a key path (`look.a[2]`, `layout`) for:
1. any `str` (key or value) that is not UTF-8 encodable -> "contains a lone surrogate";
2. under `look` only: any mapping key that is not a `str` -> "key <repr> is a <kind>, not a string";
3. any `int` for which `str(n)` raises `ValueError` -> "is too large to print";
4. a container reachable from itself -> "refers to itself".
Checks 1 and 2 call the helpers `reel-schema-value-validation` merged as public functions of
`auto_reel_ng.reel.values` (`find_lone_surrogate`, `find_non_str_key`; iterative, each container visited once,
so a cycle cannot loop and a deep file cannot hit `RecursionError`); `config/` words its own messages.
Checks 3 and 4 have no helper, so one private iterative depth-first scan in `config/project.py` does both
(an on-path set detects a cycle; a done set walks a shared, non-cyclic alias once). A `RecursionError` while
*constructing* a deeply nested file is caught at the load (a `ConfigError`, "malformed YAML").
**Rationale**: Checking before the field parsers keeps their error messages about types, not encodings.
Constraining only the key type of `look` keeps the opaque-values decision (D-I/D-J) intact: values stay
uninterpreted, and only `look` is ever hashed or serialised. The scan is small and has no new
dependency (Principle VII). Rejecting rather than repairing a surrogate or a key is Principle I.
**Alternatives**: stringify non-str keys at load (silently changes what the user wrote, and a later
`{1: a, "1": b}` collides) - rejected; a regex over the raw text for surrogates - misses the escaped
`"\ud800"` form that actually produces them - rejected.

### Fallback only on failure, in `_hash_json`
**Context**: The defaults hash must never raise, and no existing hash may move (a changed hash re-renders
the archive; Principle IV).
**Explored**: `default=str` handles values only; `sort_keys=True` fails on mixed `int`/`str` keys and on
`date` keys. Maps of all-`int`, all-`str` or all-`bool` keys hash fine today, and `{1: a}` and `{"1": a}`
serialise identically.
**Decision**: Keep `json.dumps(value, sort_keys=True, default=str)` as the first attempt. Only on
`TypeError` canonicalise and retry:

```python
def _hash_json(value: object) -> str:
    try:
        canonical = json.dumps(value, sort_keys=True, default=str)
    except TypeError:  # a key json cannot order or serialise (date, mixed int/str, tuple)
        canonical = json.dumps(_tag_keys(value), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def _tag_keys(value: object) -> object:  # recursive over Mapping / list / tuple
    # every mapping key becomes f"{type(key).__name__}:{key}"
```

Tagging **every** key (including `str` ones) in the fallback makes it collision-free (`{1: a, "1": b}` stays
two entries) and total (every tagged key is a `str`, so `sort_keys` always works).
**Rationale**: Because the fallback runs only where the old code raised, no previously computable hash can
change, which is verified by a test that recomputes the old formula for native-key inputs. A canonicaliser
applied always (the triage sketch) would have to be proven identical for every native input; try-first needs
no such proof.
**Alternatives**: always-canonicalise with native keys passed through - rejected as above; validating key
types inside `editorial_hash` and raising - rejected: the API ETag and `scan` must not die on a document
that the reel-side validation, not this layer, is responsible for rejecting.

### Why both layers
The loader rejects bad input (user-facing, names the key). The hash fallback is defence in depth for any
other producer of a `look` map (a `ReelDocument` built programmatically, a future writer): the defaults and
editorial hashes run on every scan, so a crash there is amplified across the whole library.

## Failure behaviour

- Every load failure is a `ConfigError` carrying `source` (the file path): `load_project_config` and
  `loads_project_config` raise nothing else for file content. An unreadable or non-UTF-8 file already raises
  `ConfigError` and is unchanged.
- No file is written; no partial state. The check is a pure function of the text, so a re-run, a `--force`
  run and a worker restart each fail identically until the file is fixed (a running worker re-reads
  `config.yaml` per job; it reports the job as failed with the `ConfigError` message, as it does today for a
  wrong-typed field).
- Fingerprinting: pure function of its input; the fallback is deterministic across processes (sorted tagged
  keys, no `id()`/hash-seed dependence).

## Risks / Trade-offs

- [A previously accepted `config.yaml` is now refused: a `look` with a date key or an int key] -> It was
  already crashing `scan`/`render` at the first fingerprint (mixed or date keys), or, for all-`int` keys,
  worked. The all-`int`-key case is the one regression-shaped acceptance change: its message names the key
  and says to quote it. Accepted: `look` is an opaque map of named settings and an int key has no meaning.
- [The fallback hides a malformed in-memory document] -> It hides nothing the user sees: the document was
  validated on its way in; the fallback only keeps the hash total. Covered by a test that asserts the
  fallback hash is stable and differs for different content.
- [Broad `except Exception` swallows a real bug in ruamel's usage] -> It reports `type(exc).__name__` and
  the message, never a default; same trade-off already accepted in `reel/parser.py`.
- [Duplicate scan logic with `reel/`] -> None for surrogates and keys (shared helpers); the integer and cycle
  scan is the one private function.
