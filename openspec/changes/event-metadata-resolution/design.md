## Context

See proposal.md — Why. The code facts that shape the approach:

- **`event/discovery.py`:**
  - `parse_folder_name(name) -> Optional[tuple[date, title, location]]` returns `None` for the whole name
    when the date token is missing, year-only or invalid.
  - `_metadata_from_folder_name` turns that `None` into an empty `Metadata()`, which `output_filename`
    later renders as `Untitled`.
  - Callers: `seed_document`, `ingest/layouts._folder_hint`, `api/events_read.py:123` (list title
    fallback).
- **Document loading has three entry points:**
  - `cli/adoption.load_or_seed(event_dir)`: `load_document(reel.yaml)` or `seed_document`. It is used by
    `prepare_event`, and so by render and the worker, and by `scan`, `enqueue` and `adopt-renders`.
  - `api/events_read._load_for_reconcile` (list, detail, staleness).
  - `api/events_read`'s editorial read, which is **documented as "the document as authored"**.
- **The writer never persists typed-only changes to a loaded document.** `reel/writer.document_to_data`
  reuses the document's `raw` source structure whenever it exists (every loaded document), and builds from
  typed fields only for a freshly seeded one. Replacing a loaded document's typed `metadata` can therefore
  never reach disk through adoption (`add_clip`) or `persist`.
- **Error handling:** `cli/main.main()` catches `EngineError` once, for the whole command. `scan`,
  `enqueue` and `adopt-renders` load documents in plain loops or comprehensions, and `render` loads them in
  `_staleness_filter`. None isolates a per-event `ReelError`. The worker already turns an `EngineError`
  during build into a failed job. The API already maps a per-event `ReelParseError` to `EventReadError`
  (502).

## Goals / Non-Goals

**Goals:**

- One parse, one resolution rule and one validation rule, each a pure function in `event/`, used by every
  consumer.
- No fabricated metadata, and every bad event reported by name without stopping the batch.

**Non-Goals:**

- Folder renames, and the year-folder check (next change).
- Per-event error rows in the events list.
- The legacy `import` title (`legacy-import-title`).

## Research & Decisions

### The parse result

**Decision**: `parse_folder_name` always returns a value:

```python
class FolderNameProblem(StrEnum):
    IMPOSSIBLE_DATE = "impossible_date"  # well-formed YYYY-MM-DD that is not a calendar date
    YEAR_ONLY = "year_only"              # a leading 4-digit year and no month/day
    NO_DATE = "no_date"                  # no leading date token at all
    NO_TITLE = "no_title"                # nothing left after the date token

@dataclass(frozen=True)
class FolderName:
    date: Optional[date]
    title: Optional[str]
    location: Optional[str]
    problems: tuple[FolderNameProblem, ...] = ()
    raw_date: Optional[str] = None       # the token as written, for error messages
```

The grammar is `^(?:(?P<token>\d{4}(?:-\d{2}-\d{2})?)(?:\s*-\s*|$))?(?P<rest>.*)$`. The token decides the
date or the problem. `rest` is split once from the right on `" - "` into title and location, each passed
through the existing `format_title_case`. Whitespace is stripped (so `Lasse 78 år  - Kungälv` still
splits cleanly).

**Rationale**:
- A result object instead of `Optional[tuple]` means a caller can no longer lose the title because the
  date failed.
- The enum keeps the reasons a closed, testable set, and the message text is built from it at the error
  site.
- `raw_date` lets the error say "`2019-04-31` is not a real date" instead of a generic phrase.

`_folder_hint` in `ingest/` and the API's list-title fallback read the new fields. The hint keeps its
meaning: a date is present only if it is real.

### Resolution, and where it is applied

**Decision**: `resolve_metadata(authored: Metadata, folder: FolderName) -> Metadata` takes each of date,
title and location from `authored` when it is set and not blank, else from `folder`. A new
`event/metadata.py` holds it, together with `load_event_document(event_dir) -> tuple[ReelDocument, bool]`:
load or seed, then `dataclasses.replace(doc, metadata=resolve_metadata(doc.metadata, parse_folder_name(event_dir.name)))`.
`cli/adoption.load_or_seed` becomes a thin alias of it. `api/events_read._load_for_reconcile` calls it.
The editorial read endpoint deliberately does **not**: it keeps returning `load_document` output, "as
authored".

**Rationale**:
- Resolving at load means every downstream consumer (output naming, title card, fingerprint, list, worker)
  sees the same metadata without learning about folders.
- The `raw`-structure writer guarantees the resolution is not persisted (see Context), so "reel.yaml as
  authored" holds for the file even though the in-memory document is resolved.
- The fingerprint's editorial component hashes the resolved document. Changing a fallback field (by
  renaming a folder) therefore correctly changes the fingerprint when it changes the output.

**Alternative rejected**: resolving inside `reel/parser.load_document`. `reel/` would have to import folder
parsing from `event/`, which already imports `reel/`: a cycle and a layer inversion (Principle VI).

### Validation, and where it is applied

**Decision**: `require_processable(event_dir: Path, metadata: Metadata, *, today: date) -> None` raises
`EventMetadataError(ReelError)` when:
- the resolved date is `None` (the message names the folder's date problem: impossible, year-only or no
  date)
- the resolved title is `None` (the message names `NO_TITLE` when the folder was expected to supply it)
- the date is after `today`

Each message ends with the fix: "set `metadata.date` in reel.yaml or correct the folder name".

It is called at the project-level entry points, **not inside the loaders**:
- `scan`
- `render` (in `_staleness_filter`, before prepare)
- `enqueue`
- `adopt-renders`
- the worker's `default_build_job`
- the API's `_load_for_reconcile`

The loaders stay lenient. Many unit tests treat a bare `tmp_path` (`test_x0`) as an event, and a library
caller rendering an undated plan is still valid at the engine level (the undated output rule).

`today` is passed in (`date.today()` at the entry points), which keeps the rule deterministic in tests.

### Per-event isolation in the CLI

**Decision**: One helper wraps "load + validate" for a `ref`:

```python
def _checked_document(ref: EventRef, today: date) -> tuple[Optional[ReelDocument], Optional[str]]:
    """(document, None) for a processable event, or (None, reason) — never raises ReelError."""
```

- **`scan`:** prints `ERROR  <event>: <reason>` in place of that event's inventory, and continues.
- **`enqueue` and `adopt-renders`:** build their document maps from it. Failed events are reported beside
  collisions and excluded from the collision check, so a bad event cannot be a claimant.
- **`render`:** `_staleness_filter` returns the failures, and `cmd_render` appends them to
  `build_failures`, so the existing `_report_render` prints them and counts them toward the exit code.

Every command returns 1 when any event failed. `main()`'s catch-all stays as the backstop for errors that
are not per-event (configuration, missing root).

**Rationale**: It reuses each command's existing reporting shape (`build_failures`, the collision `ERROR`
lines), so the output format doesn't fork.

## Failure behavior and idempotency

- **What raises:** `EventMetadataError` and `ReelParseError`, per event, reported and skipped in the batch
  commands, failing the job in the worker, and a 502 on the events reads. No file is written for a failing
  event: no seed persist, no manifest, no job row.
- **Re-runs:** report the same errors until the operator fixes `reel.yaml` or the folder name. Fixing one
  takes effect on the next run, with no state to clear.
- **`--force`** bypasses only staleness. A failing event is never processable.
- **Worker restart:** a requeued job revalidates on claim.
- **No `RENDER_GRAPH_VERSION` bump.** Events whose `reel.yaml` lacked a field the folder supplies change
  their editorial fingerprint and report stale. That is the correct outcome, because their output name or
  card changes.

## Risks / Trade-offs

- **[Fallback changes existing v0 events]** A document written by the editorial API without a date (a
  test does this, `test_editorial_write_e2e`) now resolves the folder's date, so its output moves from the
  root to `YYYY/YYYY-MM-DD - …`. → This is the intended D-2 behavior, and that test's expectation is
  updated. On the real archive, no NG-written document exists yet.
- **[Undated events become errors]** The dev library's `2024/Blandat` and any flat-layout event without a
  date now fail. → The dev library gains a dated `reel.yaml` for Blandat. The GUI's "No date" group becomes
  unreachable for a valid project; it is left in place, because it is harmless.
- **[The events list fails whole on one bad event]** The real archive's 3 bad folders make the GUI list 502
  until each gets a `reel.yaml` date or a corrected name. → This is a documented non-goal, and the CLI
  names each one, so fixing them is three small edits.
- **[`today` makes validation clock-dependent]** A future-dated event becomes valid once its date passes.
  → That's acceptable: it cannot change rendered bytes, only whether an event is processable.

## Migration Plan

No data migration. After deploy, `scan` over the real `Videos/Sorted` reports `ERROR` for
`2004 - Yngve…` (year only), `2016 - Kents film…` (year only) and `2019-04-31 - Golfträning…` (not a
real date), and lists the rest. `adopt-renders --dry-run` reports 129 would-adopt, 3 `ERROR` and 3
unrendered. Rollback means reverting the helpers and the per-event wrapper.
