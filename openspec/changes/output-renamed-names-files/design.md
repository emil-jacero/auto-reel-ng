## Context

`evaluate()` already knows both file names when it cites `output_renamed`. `expected` is the event's expected
output (`Path(output_path)`), and `_renamed_output(manifest, expected)` returns the `Path` of the old movie that
`rendered_output()` and the movie route also use. Only the `StalenessReason` slug leaves the function.
`scan` is the one command that prints reasons (`_print_inventory`); the other gate call sites (`render`, `enqueue`,
`adopt-renders`, the worker's recheck, the API) read `verdict.stale`, and the API serialises `verdict.reasons`.

Two gate changes touched the same code and are already on `main`:

- `staleness-output-lookup` (archived) changed `gate.py`: `_renamed_output(manifest, expected)` resolves the
  recorded bare name through `recorded_output_path` (the year folder of its date prefix under the output directory
  in use) and returns the `Path` only for a regular file; `evaluate()` uses `is_file()` for the expected output and
  `_absent_output_reason` picks `output_renamed` or `output`. `manifest.output` stays the recorded bare file name.
  This design takes `renamed_from` from the **returned path**, never from `manifest.output`: the returned path is
  a file the gate has just confirmed exists.
- `cli-serve-forced-stop-and-lifespan` (merged) changed `commands.py` in the `serve` code only. `_print_inventory`
  is untouched there.

## Goals / Non-Goals

**Goals:**
- A verdict that cites `output_renamed` says which file is on disk and which file the next render writes.
- `scan` prints both, in one line, with the reason.
- No existing caller's behaviour changes; the new fields cannot be misread (set exactly when `output_renamed` is
  cited).

**Non-Goals:**
- API schema, OpenAPI and web client types, GUI (change `api-job-summary-and-renamed-fields`).
- Full paths. The file names are enough to tell the two movies apart; the year folder follows from the date prefix
  of each name (D-9) and is printed by nothing else on the line either.
- Any new decision about what happens to the old movie.

## Decisions

### The detail lives on `Verdict`, as two optional fields

```python
@dataclass(frozen=True)
class Verdict:
    stale: bool
    reasons: tuple[StalenessReason, ...] = ()
    renamed_from: Optional[str] = None  # old movie's file name; set iff OUTPUT_RENAMED is cited
    output_name: Optional[str] = None   # expected output's file name; set iff OUTPUT_RENAMED is cited
```

The two fields are `None` for every verdict that does not cite `output_renamed` (including `output`,
`no_manifest` and fresh), so a consumer can test `verdict.renamed_from is not None` or `OUTPUT_RENAMED in reasons`
interchangeably; the gate tests assert both directions. The defaults keep every existing `Verdict(...)`
construction and equality comparison valid.

**Alternatives considered.** A `detail: Mapping[reason, str]` was rejected as an option bag for one reason
(Principle VII). Returning the `Path` instead of the name was rejected: a path leaks the output root into the
API and the CLI line for no gain, and `rendered_output()` already serves callers that need the path.

### Names, not paths; taken from the resolved file

`renamed_from = resolved.name`, where `resolved` is the `Path` `_renamed_output` returned, and
`output_name = Path(output_path).name`. Because `renamed_from` is the name of a file the gate has just confirmed
is a regular file, it is by construction a bare name that exists on disk; it is never the manifest's raw string
(which may be a relative path, or a hand-edited value the gate refuses to look up).

`_absent_output_reason` (today it calls `_renamed_output` and returns only the reason) is reshaped so that
`evaluate()` calls `_renamed_output` itself once and derives the reason from `is not None`, so the lookup still
runs exactly once per verdict and the reason and the detail cannot disagree.

### `scan` appends the detail to the reason it explains

```
  stale: editorial, output_renamed (was '2024-06-27 - Grillning med Grannar.mp4', now '2024-06-27 - Grillkväll med grannarna.mp4')
```

`output_renamed` is appended after the component reasons and is the only reason with detail, so the suffix ends
the line. The names are written with `repr()`, which quotes them and keeps non-ASCII text as is; a name containing
a quote is still unambiguous. A verdict without `output_renamed` prints as before (`stale: no_manifest`,
`stale: editorial, output`, `fresh`), so scripts that match on those keep working. The formatting is a small
private helper next to `_print_inventory`, not a method on `Verdict`: the gate owns the vocabulary and the data,
the CLI owns how it reads.

**Alternative considered.** A separate second line (`  renamed: was ..., now ...`) would leave the `stale:` line
byte-identical. Rejected: the one-line form is what triage proposed, it keeps the reason and its explanation
together, and the only in-repo matchers of that line are tests updated here. `tests/test_cli_jobs.py` matches the
prefix `stale: editorial, output_renamed` with `in`, which the new line still contains.

### Failure behaviour and idempotency

Nothing new can raise: the fields are read from values the gate already holds, with no extra filesystem access.
The gate stays read-only, so a re-run, a `--force` run and a worker restart all yield the same fields for the same
disk state; a render that fails or is cancelled leaves the disk state, hence the detail, unchanged (the existing
"A failed render after a rename changes nothing" scenario). A render that succeeds writes the new name and the
event becomes fresh, at which point both fields are `None`.

## Risks / Trade-offs

- **Shared edit surface** with `staleness-output-lookup` in `gate.py`. Mitigated by depending only on what
  `_renamed_output` returns, and by the gate tests, which exercise the three rename shapes end to end through
  `evaluate()` rather than through private helpers.
- **A longer `scan` line** for renamed events. Accepted; file names are the point.
- **`repr()` quoting** is Python-specific; acceptable for a human-facing CLI line, and pinned by a test with a
  non-ASCII name.
