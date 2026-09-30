## Context

See proposal.md, section Why. These code facts shape the approach. They were established on a scratch
project with ruamel.yaml 0.19.1, the installed version (`pyproject.toml` asks for `>=0.18.0`):

- **`reel/parser.py` is the single loader for `reel.yaml`.** `load_document` reads the file, and
  `loads_document` loads it with a round-trip `YAML()`. It raises `ReelParseError` for `OSError` and
  `YAMLError`. It then routes a versionless mapping to `legacy.import_legacy_data` and anything else to
  `schema.build_document`. Every engine path reaches `reel.yaml` through `load_document`:
  - `event/metadata.load_authored_document`, which serves the CLI's `load_or_seed`/`prepare_event`, the
    worker's `load_event_document` and the API's `_load_for_reconcile`
  - `event/editorial.apply_editorial_write`
  - `api/events_read.get_reel`
- **The impossible value fails inside `load`, before any routing.** `YAML().load` constructs every node.
  An unquoted `2024-02-30` resolves to `tag:yaml.org,2002:timestamp`, and
  `ruamel/yaml/util.create_timestamp` (`util.py:85`) raises `ValueError`. The same happens for
  `2024-13-45` and for `2024-02-29T25:00:00` (`util.py:126`). Explicit tags fail the same way, from a
  different constructor: `!!int abc` and `!!float abc` raise `ValueError` from `int()`/`float()`. All of
  them fail identically in v0 and legacy documents and at any depth, `look` included. So the fix belongs
  in `loads_document`'s load step, not in `schema` or `legacy`.
- **`ValueError` is not the only builtin error the load step leaks.** An adversarial review fed 102 odd
  inputs through today's `loads_document`, and 41 of them escaped as builtin errors, not `YAMLError`:
  - raised while one node is constructed:
    - `IndexError` from the round-trip int/float constructors (`!!int ''`, a bare `size: !!int`,
      `!!int -`, `!!float _`, and the plain, untagged `0x_`)
    - `KeyError` from the bool constructor (`!!bool maybe`, a bare `!!bool`)
    - `AttributeError` from the set constructor on a scalar (`!!set abc`)
    - `TypeError` from a complex mapping key holding a list (`? {a: [b]}`) or an `!!omap` with such a key
    - `ValueError` also from a timezone offset of 25 hours, year `0000`, and a 5000-digit integer
  - raised outside any node's construction:
    - the scanner's `ValueError` from `chr()` for a double-quoted escape that names no character
      (`"\UFFFFFFFF"`)
    - a `RecursionError` for a flow list nested 3000 deep
    - a failure in the root collection's constructor after its first `yield`: ruamel drains the root's
      generator in `construct_document`, after the per-node call for the root has returned (a root
      complex key `? {a: [b]}` raises `TypeError` there)

  A per-node handler for `ValueError` alone would still leave 23 of the 102 inputs crashing the batch.
  The reproduction is `scratchpad/c8-review/fuzz_current.py`, `fuzz_extra.py` and `count.py` (outside the
  repo).
- **`UnicodeDecodeError` is a `ValueError`, not an `OSError`.** `path.read_text(encoding="utf-8")` raises it
  on Latin-1 bytes (`Kräftskiva`, byte `0xe4` at offset 32 in the reproduction).
- **Construction goes through one per-node method.** `BaseConstructor.construct_object` calls
  `construct_non_recursive_object(node)` for every node. For a scalar nested in a round-trip mapping, the
  mapping's generator calls `construct_object` on the value node. The innermost call therefore sees the
  failing scalar node, whose `start_mark` gives its position.
- **The callers need nothing new.** `classify_event_failure` maps any `ReelError` that is not an
  `EventMetadataError` to `EventFailure.UNPARSEABLE_REEL_YAML`. `_checked_document` turns `ReelError` into
  an `ERROR` reason, and the worker turns `EngineError` into a `failed` job. With the fix patched in
  in-process on the scratch project, the list answered 200 with one `unparseable_reel_yaml` row, the
  detail and `…/reel` answered 502 carrying that kind, `scan` printed one `ERROR` line and exited 1, and
  the worker's loader raised an `EngineError`.

## Goals / Non-Goals

**Goals:**

- Any failure to read or construct a `reel.yaml`'s content is a `ReelParseError`, so existing per-event
  isolation applies everywhere.
- An impossible value is reported with the value as written and its line (the requirement: "Errors SHALL
  identify the offending location"). A failure that ruamel raises with no node or position is reported
  with the file and ruamel's reason, the finest location available.

**Non-Goals:**

- Any change outside `reel/parser.py` (see proposal, Non-goals, for `import` and `config.yaml`).
- Catching errors from `schema`/`legacy` validation code. Those raise `ReelParseError` themselves, and a
  bare builtin error there would be a bug to fix where it happens, not to mask. Both new handlers wrap
  only the `YAML().load(text)` call, never the routing or `build_document`.

## Research & Decisions

### Where to turn a builtin error into a parse error

**Context**: The timestamp constructor's `ValueError` carries only the arithmetic reason, for example
"day 30 must be in range 1..29 for month 2 in year 2024". It carries neither the scalar as written nor its
line. And, as the Context section lists, ruamel's load step also leaks `IndexError`, `KeyError`,
`AttributeError`, `TypeError` and `RecursionError`, some of them from outside any single node's
construction.

**Explored** (on the scratch copy, in scripts outside the repo):
- **(a) `except ValueError` around `_yaml().load(text)` in `loads_document`.** Two lines. The message
  cannot name `2024-02-30` or a line, so an operator with several dates in a file must work out which one
  "month 2, day 30" is. It also misses every non-`ValueError` leak.
- **(b) Override the timestamp constructor only.** This gives the value and the line for dates, but
  `!!int abc` and `!!float abc` still escape as `ValueError` (verified). It would need a second catch.
- **(c) Override `construct_non_recursive_object` in a `RoundTripConstructor` subclass, catching
  `ValueError`.** It re-raises ruamel's own `ConstructorError`, a marked `YAMLError`, with the node's
  `start_mark`. For the Barbecue fixture it produced the value and `line 4, column 9`, and for a value
  inside a flow list (`clips: [x.mp4, 2024-02-30]`) it produced `line 4, column 20`. But 23 of the
  review's 102 inputs still escaped (`!!bool maybe` as `KeyError`, `!!int ''` as `IndexError`, and so on).
- **(d) (c) catching every non-`YAMLError` exception, plus a location-less backstop around `load`.**
  The hook catches the construction failures with their position. The backstop catches the rest: the
  scanner's `chr()` error, `RecursionError`, and a root generator's failure. All 102 inputs became
  `ReelParseError`, and the full non-DB suite still passed unchanged with the hook patched in (621 passed,
  5 environmental skips, the same as without it).

**Decision**: (d). In `reel/parser.py`:

```python
_TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"


class _Constructor(RoundTripConstructor):
    """ruamel's round-trip constructor, reporting an unconstructible node as a marked YAML error."""

    def construct_non_recursive_object(self, node: Any, tag: Optional[str] = None) -> Any:
        try:
            return super().construct_non_recursive_object(node, tag)
        except YAMLError:
            raise
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raise ConstructorError(
                None, None, f"{_shown(node)} is not a {_kind(node)} ({exc})", node.start_mark
            ) from exc


def _yaml() -> YAML:
    yaml = YAML()  # round-trip mode by default
    yaml.preserve_quotes = True
    yaml.Constructor = _Constructor
    return yaml
```

and in `loads_document`, the load's `except YAMLError` clause gains a sibling:

```python
    try:
        data = _yaml().load(text)
    except YAMLError as exc:
        raise ReelParseError(f"{source}: malformed YAML: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # ruamel failing without a position (scanner chr(), recursion depth, a root generator)
        raise ReelParseError(f"{source}: malformed YAML: {exc}") from exc
```

- `_kind` is `"real date or time"` for the timestamp tag, and otherwise `"valid <tag suffix>"` (`valid int`).
- `_shown` is `repr(node.value)` for a scalar (`'2024-02-30'`), and otherwise the node's tag.
- The hook MUST re-raise a `YAMLError` unchanged, so that ruamel's own marked errors, and a child node's
  error that the hook already converted, keep their original position. The innermost failing node is the
  one reported.
- Both broad clauses MUST wrap only the load step. Routing, `import_legacy_data` and `build_document` stay
  outside them.
- The `# pylint: disable=broad-exception-caught` follows the precedent in `accel/selftest.py`. The snippet
  passes strict mypy, pylint 10.00 with the repo's `pyproject.toml`, and black at line length 100.

This is the resulting message for the Barbecue fixture, type-checked and reproduced:

```
…/2024-07-04 - Barbecue/reel.yaml: malformed YAML: '2024-02-30' is not a real date or time (day 30 must
be in range 1..29 for month 2 in year 2024)
  in "<unicode string>", line 4, column 9:
        date: 2024-02-30
              ^ (line: 4)
```

**Rationale**:
- It is the only option that satisfies "Errors SHALL identify the offending location" for every typed
  scalar.
- It is the only option under which no demonstrated input escapes. The broad catch is not a handler "for
  later" (Principle VII). Each builtin type it absorbs was reproduced above, and five different ones come
  from ruamel's constructors alone. A tuple of today's five types would leave the next one to crash the
  whole batch, and one bad event must not do that (Principle I).
- It reuses the loader's existing `YAMLError` path, which already emits multi-line marked messages for
  syntax errors. Callers and the CLI already print that shape.
- `ConstructorError` is ruamel's own error for "cannot construct this node", and `!!timestamp foo` already
  raises it today. The new errors are the same kind of failure and are reported the same way.
- The hook only acts when construction raises. A document that loads today builds the same objects, so no
  typed field, no fingerprint and no `ETag` moves. On the scratch copy, the five v0 fixtures in
  `tests/test_event_editorial.py` dumped byte-identical with and without the hook, and each was
  byte-stable. Strict mypy is clean on the snippet: ruamel ships `py.typed`.
- No ruamel control flow depends on a builtin error passing through a node's construction. Its only
  broad handler, the bare `except` in `construct_undefined`, swallows a child's error in either form.
- The writer's own `_yaml()` (`reel/writer.py`) is unchanged. It only reloads documents that already
  loaded.

### The non-UTF-8 file

**Decision**: `load_document` gains one clause before `except OSError`:

```python
except UnicodeDecodeError as exc:
    raise ReelParseError(f"{path}: not UTF-8 text ({exc.reason} at byte {exc.start})") from exc
```

Example: `…/reel.yaml: not UTF-8 text (invalid continuation byte at byte 32)`.

**Rationale**: It is the file's content, not the disk, so it is a parse error (`unparseable_reel_yaml`),
not `unreadable_disk`. The byte offset is the location a text editor needs. No encoding is guessed:
decoding as Latin-1 would be fabricating (Principle I).

### No new failure kind, no `api/` change

**Decision**: None. Every new error is a `ReelParseError`. It is classified `unparseable_reel_yaml` by the
existing rule, printed by the CLI's existing `ERROR` path, and fail the job through the worker's existing
`EngineError` catch.

**Rationale**: The `api-service` requirement already lists "an unparseable or invalid `reel.yaml`" as a
per-event failure. These files are exactly that. A new kind would widen a closed, published enumeration
for no client-visible distinction.

### Where the behavior is recorded

**Decision**: In the `reel-document` spec's "Fail-loud parse and validation" requirement. No HLD D-n.

**Rationale**: It is not a graph shape, a fingerprint input or a schema change. It closes a gap in an
existing fail-loud guarantee.

## Failure behavior and idempotency

- **What raises:** `load_document`/`loads_document` MUST raise `ReelParseError` for these files, and never
  a builtin error such as `ValueError`, `KeyError` or `RecursionError`. Nothing is written: loading has no
  side effects.
- **Per event:**
  - `scan`, `render`, `enqueue` and `adopt-renders` print `ERROR <event>: <reason>`, skip that event, and
    exit non-zero
  - the events list shows one error row
  - the detail and `…/reel` answer 502 with the failure kind
  - `PUT …/reel` answers 502 through its leading `get_reel`
  - the worker fails the job with the reason, where today its thread dies and leaves the row `running`
- **No partial file:** unchanged. No render starts for the event, so no `.part` and no manifest.
- **Re-run:** the same error each time, until the author fixes the file. `--force` does not bypass it
  (it bypasses the staleness gate, not parsing). After a worker restart, a requeued job fails the same way,
  as a `failed` row rather than a dead thread.

## Risks / Trade-offs

- **[The hook relies on a ruamel method name]** `construct_non_recursive_object` is not a documented public
  API. If a ruamel upgrade renamed it, the override would silently become dead code. The backstop would
  still turn the error into a `ReelParseError`, but without the value's line. → The parser tests load
  `date: 2024-02-30` and assert a `ReelParseError` naming the line (task 2.1), so an upgrade that bypasses
  the hook fails CI. The method exists unchanged in the installed 0.19.1.
- **["malformed YAML" wording for a well-formed file]** The existing prefix is kept, although the file is
  syntactically valid. → The problem text after it says exactly what is wrong ("is not a real date or
  time"). Adding a second prefix would mean a second `except` path for no behavioral gain.
- **[ruamel's `in "<unicode string>"` in the excerpt]** The marked excerpt names the stream, not the file.
  → This is pre-existing for every syntax error. The file is named by the message's leading `source`.
- **[A broad catch could hide an engine bug]** `except Exception` would also absorb a bug in the hook's
  own `_shown`/`_kind`. → The clauses wrap only `YAML().load(text)`, which runs ruamel over user text plus
  the hook. `schema` and `legacy` validation stay outside, so a bug there still raises as itself. The error
  is chained (`from exc`), so the original traceback survives, and task 2.1's message assertions would
  catch a broken helper.
- **[Backstop errors carry no position]** The scanner's `chr()` failure and `RecursionError` come without a
  mark, so the message names the file and ruamel's reason (`chr() arg not in range(0x110000)`), not the
  line. → Getting a line would mean hooking ruamel's scanner or composer as well, which costs more than such
  rare typos justify. The file is still named, the batch still survives, and the event is still reported
  as failed.

## Migration Plan

There is no data or schema migration. Rollback means reverting `reel/parser.py` and the tests.
