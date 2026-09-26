## Context

See proposal.md — Why. The code facts that shape the approach:

- **`event/discovery.py` `scan_event(event_dir)` is the single disk listing.**
  - It lists video files at the event root (the default chapter), then each immediate subdirectory's own
    video files (named chapters). `_video_identities` does not recurse, so depth ≥ 2 is already invisible.
  - Its five callers are `seed_document`, `cli/adoption.py` (reconcile), `staleness/fingerprint.py`
    (`_hash_clip_set`), `analysis/cache.py` and `api/events_read.py`. Changing it changes all five
    consistently.
- **`ingest/layouts.py` has two built-in walks.** `year_event_layout` and `flat_layout` both yield
  `EventRef`s from `_subdirs(...)`, and it already imports `parse_folder_name` from `event/discovery.py`
  for the folder-name hint. Every enumeration of events goes through a registered layout: the CLI's
  `_project_context` and the API's `_list_event_refs`.
- **Legacy behavior** (`auto-reel/movie_merge`):
  - `constants.py`: `IGNORE_FILE = ".reelignore"`.
  - `project/processor.py:51` skips an event directory containing it and logs "Ignoring directory (found
    .reelignore)" at INFO.
  - `movie/processor.py:235,258` skips a chapter directory that is named `original` or contains the
    marker.
  - `utils/file.py:138` drops `original` at any depth of its walk.
- **The archive** (survey, 2026-09-26):
  - every `original` folder is lowercase
  - `.reelignore` files are empty
  - 6 are event-level and 1 is chapter-level (inside an event that is itself ignored)
  - no `.reelignore` sits at year level

## Goals / Non-Goals

**Goals:**

- The archive's two conventions hold for every consumer, from exactly two code points.
- Nothing excluded is touched on disk, and a skipped event is visible in the log.

**Non-Goals:**

- The API's by-id routes (proposal: Non-goals).
- Custom-layout enforcement. Only the built-ins exist; a future custom layout's change states whether it
  honors the marker (Principle VII: no hook for a layout nobody has written).

## Research & Decisions

### Where each rule is enforced

**Context**: Two scopes. An *event* marker affects enumeration, while *chapter* markers and `original/`
affect the clip listing.

**Explored**:
- (a) filter in each walk caller (`_project_context`, `_list_event_refs`)
- (b) wrap every layout inside `get_layout`
- (c) the built-in layouts, plus `scan_event`

**Decision**: (c).
- `scan_event` skips an immediate subdirectory whose name casefolds to `original`, or that contains
  `.reelignore`.
- The built-in layouts skip an event directory that contains `.reelignore`, via one shared helper.
- The marker names live in `event/discovery.py` as `ORIGINALS_DIR = "original"` and
  `IGNORE_MARKER = ".reelignore"`, with a predicate `is_reelignored(directory: Path) -> bool` that
  `ingest/` imports, as it already imports `parse_folder_name`.

```python
# event/discovery.py
ORIGINALS_DIR = "original"
IGNORE_MARKER = ".reelignore"

def is_reelignored(directory: Path) -> bool:
    """True when ``directory`` carries the legacy ``.reelignore`` marker (contents unread)."""
    return (directory / IGNORE_MARKER).is_file()

def _is_chapter_dir(subdir: Path) -> bool:
    """An event subdirectory contributes clips unless it holds originals or is ignored."""
    return subdir.name.casefold() != ORIGINALS_DIR and not is_reelignored(subdir)
```

**Rationale**:
- (a) repeats the rule at two call sites and misses any future third.
- (b) changes what `get_layout` returns, so the registry tests and custom registrations stop seeing
  the layout they registered.
- (c) puts each rule in the one function that already owns its scope, and it matches legacy's structure
  (walk-level event skip, chapter-level skip in the movie scan).

### How a skip is reported

**Context**: The spec requires a skipped event to be visible, not silently dropped.

**Decision**: The layout helper logs `logger.info("skipping %s: %s", event_dir, IGNORE_MARKER)` once
per yield decision. The CLI already prints INFO lines on stderr (`Selected amd profile …`), so `scan`,
`render` and the rest show the skip. The API service's log shows it too. A skipped chapter or `original/`
is **not** logged: it is routine (17 events have `original/`), and logging it on every scan and every
events-list request would bury the event-level lines.

**Alternative rejected**: returning skipped events alongside the yielded ones and printing them in
`scan`. That changes the layout protocol (`Iterable[EventRef]`) for every caller, to serve one
command's output.

### Matching rules

**Decision**:
- `original` is compared with `casefold()`. The NTFS archive is case-preserving and is read through a
  case-insensitive mount on some hosts, and a camera or Windows user could write `Original`.
  Over-matching only ever *excludes* a folder named some case variant of "original", and it is the
  legacy name.
- `.reelignore` is matched exactly, as a regular file (`is_file()`), because a directory named
  `.reelignore` is not the marker.
- Depth stays one level. It is now a requirement rather than an accident of `_video_identities`, which
  is what keeps a chapter's own `original/` out.

## Failure behavior and idempotency

- **Nothing new raises.** An unreadable subdirectory raises from `iterdir()` exactly as before.
- **No file is created, moved or deleted.** The markers are only ever `stat`ed.
- **Re-running a walk** yields the same events. Adding or removing a marker takes effect on the next
  walk, with no cached state to invalidate. `list_events` and `scan` are per-request (D-A3).
- **`--force`** has no bearing: an ignored event is never enumerated, so no gate is consulted.
- **Worker restart mid-render:** a job enqueued before a marker was added still renders when claimed,
  because the worker resolves the job's event directory directly, not through a layout. This is
  accepted and documented. It would need an enqueue before the marker existed. Deleting the queued
  job, or `jobs cancel`, handles it.
- **Rendered output:** events with `original/` or an ignored chapter lose the duplicate chapter. Their
  clip-set sub-hash changes, so the gate reports them stale for re-render. **No
  `RENDER_GRAPH_VERSION` bump**: the graph is unchanged, and the input change is already in the
  fingerprint.

## Risks / Trade-offs

- **[A legitimate chapter named `original`]** An operator who names a real chapter "Original" loses
  it. → This is the legacy convention the archive was built on. The survey found no such chapter, and
  renaming the folder restores it.
- **[An NG-seeded document that already lists `original/` clips]** These clips turn MISSING. → None
  exist on the real library. The dev library and fixtures have no `original/`. Reconcile reports it
  loudly, and removing the chapter from `reel.yaml` resolves it.
- **[An ignored event reachable by ID]** The detail and jobs routes do not walk the layout. → No UI or
  CLI path offers the ID. Closed in a later `api/` change (proposal: Non-goals).
- **[A log line on every events-list request]** The service logs 6 lines per list request on the real
  library. → That's acceptable at INFO. If it proves noisy under the GUI's refresh, lower it to DEBUG
  in the API only.

## Migration Plan

Nothing to migrate: no NG-written documents exist on the real library. After deploy, `scan` over
`Videos/Sorted` should report 135 events (141 − 6), with no chapter named `original`, and 6 INFO skip
lines. Task 4.2 verifies this read-only. Rollback means reverting the two functions.

HLD §2 already lists both conventions as "worth keeping", so no new D-n entry is needed. §2 gains a
pointer to the two requirements that now carry them.
