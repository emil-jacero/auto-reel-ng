## Why

A `reel.yaml` that fails to load is reported by one parse error, and three of its messages still point at
nothing. A YAML syntax error carries ruamel's excerpt, which names the file as `"<unicode string>"` because
the parser reads a string, so the message holds the real path once in its prefix and a placeholder in the
excerpt. A scanner `chr()` failure (`"\U00110000"`, a code point past the last one) is reported as
`malformed YAML: chr() arg not in range(0x110000)` with no position, so a long document gives the user
nothing to search for. A document nested a few hundred levels deep reports
`malformed YAML: maximum recursion depth exceeded`, which does not say the nesting is the problem. None of
this loses data (every case already fails loud with the single parse error); it makes the errors harder to
act on than the invalid-value errors next to them, which name file, value and line.

## What Changes

- A YAML error that carries a position names the real source (the `reel.yaml` path, or the caller's
  `source`) where ruamel printed `"<unicode string>"`. The excerpt, line, column and reason are unchanged.
- A load failure that carries no position (the `chr()` case) additionally says how far reading got: the
  first line it can be no earlier than, taken from the last token the scanner produced before it failed.
  When the failure happens after scanning (the recursion limit) no such line exists; the error then names
  the file and the reason, which is stated as a documented limitation.
- A document nested too deep to load says so (`nested too deeply to load`), keeping the underlying reason.
- Dropped from the backlog item after re-checking on main: a root-level complex key (`? [a, b]`) no longer
  yields `malformed YAML`. It loads, and the legacy importer reports it as an unknown top-level key.
  Rejecting unknown or non-string top-level keys in a v0 document is a separate decision, not made here.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reel-document`: adds the requirement that a load error names the real source and, when it has no
  position of its own, how far reading got.

## Impact

- `auto_reel_ng/reel/parser.py` (`loads_document`'s error handling) and `tests/test_reel_parser.py`.
- Error text only: no accepted document changes, no `ReelParseError` becomes a different kind of error, no
  rendered output changes, so `RENDER_GRAPH_VERSION` is not bumped. Callers print the message verbatim (CLI
  `ERROR <event>:` line, events-list error row, event-detail 502 body) and pick up the better text for free.
- Gated on `reel-schema-value-validation`, which also edits `parser.py` (a lone-surrogate scan after the
  load, in `loads_document`); this change touches only the `except` chain of the same function.
