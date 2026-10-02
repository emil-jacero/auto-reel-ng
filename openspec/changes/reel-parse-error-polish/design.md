## Context

`parser.loads_document` loads with `_yaml().load(text)` inside three `except` arms: `ConstructorError`
("invalid value"), `YAMLError` ("malformed YAML") and a generic backstop for ruamel failures with no node to
blame. Re-checked on main (6a7fe16) with `loads_document(text, source="/x/reel.yaml")`:

| input | message today |
|---|---|
| `title: "\x"` (scanner error) | `/x/reel.yaml: malformed YAML: while scanning a double-quoted scalar\n  in "<unicode string>", line 2, column 8: ...` |
| `\t` starting a line, `[a` + `b: : :` (parser error) | same shape: placeholder in every `in "...", line N` excerpt |
| `x: "\U00110000"` on line 4 | `/x/reel.yaml: malformed YAML: chr() arg not in range(0x110000)` (backstop, no position) |
| 250 nested `[` | `/x/reel.yaml: malformed YAML: maximum recursion depth exceeded` (backstop, no position) |
| `a: 1` repeated (`DuplicateKeyError`) | same placeholder |
| `? [a, b]` root complex key | loads; legacy importer: `unknown top-level key ('a', 'b')` (the triage's sub-claim is not reproduced) |

ruamel's `MarkedYAMLError` holds `context_mark` and `problem_mark`, both `StringMark`s whose `name` is
`"<unicode string>"` because the loader was handed a `str`. `YAML.scan(text)` is a public, lazy token
iterator; it is iterative, so it works at any nesting depth.

## Goals / Non-Goals

**Goals:**
- No load error message contains the placeholder `<unicode string>`; it names the real source.
- A position-less failure that happens while scanning says how far reading got.

**Non-Goals:**
- Exact position for a failure that happens after scanning (the recursion limit is hit while composing or
  constructing, from a scanner that read the whole text fine). Stated as a limitation, not worked around.
- Rejecting unknown or non-string top-level keys in a v0 document (the triage's optional extra): a separate
  decision, since `build_document` deliberately ignores unknown top-level keys today.
- The `config.yaml` loader's error text (`config-yaml-hardening` owns it).
- Any change to which documents load.

## Decisions

**D1. Rename the marks, do not rewrite the string.** In the `ConstructorError` and `YAMLError` arms, when
the exception is a `MarkedYAMLError`, set `name = source` on its `context_mark` and `problem_mark` (when not
`None`) before formatting `str(exc)`. Alternative: `str(exc).replace('"<unicode string>"', f'"{source}"')`,
rejected because it also rewrites a document whose own text contains that sequence. Alternative: give ruamel
a named stream (`io.StringIO` has no `name`; a wrapper object would be needed) — more machinery for the same
effect, and `loads_document` must stay a function of `text`. The mark is a throwaway object owned by the
exception, so mutating its `name` has no other reader. One small private helper formats the message so both
arms share it.

**D2. Last scanner token for the position-less backstop.** In the generic backstop only, re-run
`_yaml().scan(text)` inside its own `try`, keep the last token yielded, and if the re-scan raises (the
`chr()` case) append `(reading got as far as line N)`, N = that token's `end_mark.line + 1`. If the re-scan
completes (the recursion case) or raises while starting, add nothing. It is a lower bound, not the failing
line: ruamel holds a simple-key token back until the next token is fetched, so the failure can sit on or a
few tokens after line N; the wording says "as far as", not "at". On the `x: "\U00110000"` document that is
line 4, the right line; on a long multi-line scalar it names the line the scalar starts. Alternative:
walking the traceback for the scanner's `self` and reading its live mark — exact, but depends on ruamel
frame internals, rejected. Cost is a second tokenisation, paid only when a document is already failing.

**D3. Name the nesting.** `RecursionError` is caught explicitly in the backstop (before the generic
`Exception`) and reported as `nested too deeply to load (maximum recursion depth exceeded)`. The reason text
is kept so the cause stays verifiable; the lead says what to fix. No depth limit is invented: a limit
would reject documents that load today.

**D4. Sequencing with `reel-schema-value-validation`.** That change adds a lone-surrogate scan to
`loads_document` after the successful load; this change edits only the `except` chain above it. They do not
overlap, but whoever applies second re-reads `parser.py` rather than relying on line numbers.

## Risks / Trade-offs

- [Re-scan could itself fail or recurse] → wrapped in `try/except Exception`; any failure there only omits
  the extra line, the original error is always raised.
- [The "got as far as" line is a lower bound and may be read as exact] → the wording says so, and the
  scenario pins one case (line 4 of a document whose escape is on line 4) without claiming a general
  equality.
- [ruamel changes `StringMark` attributes] → the pinned dependency is the only reader; the test asserts the
  message holds the source and not the placeholder, so an upgrade that breaks this fails a test.
- [A document that is deep but under the limit still loads] → intended; the limit is Python's, not ours.
