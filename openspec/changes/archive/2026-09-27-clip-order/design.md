## Context

See proposal.md — Why. The code facts that shape the approach:

- **`event/discovery.py`:**
  - `scan_event` groups clips into chapters (root first, then subfolders by name), with each group
    `sorted()` by identity, which is a case-sensitive plain sort.
  - `seed_document` turns that listing into chapters.
  - `DiskListing.identities`, the flat sorted set, feeds reconcile and the fingerprint's clip-set. Its order
    is irrelevant there.
- **Where clips enter a document:**
  - `event/metadata.load_authored_document`: seeds when there is no `reel.yaml`.
  - `cli/adoption.prepare_event`: appends `result.new`, in sorted-identity order, via `add_clip`.
- **Call sites** that load or prepare an event (all must carry the rule):
  - `cli/adoption.py:64,80`
  - `cli/build.py:51,121`
  - `cli/commands.py:132,279`
  - `event/metadata.py:47,58`
  - `scheduler/worker.py:73-74`
  - `api/routes/jobs.py:60`
  - `api/events_read.py:106,275`

  Each already has the project config in reach: the CLI's `ctx.config`, the worker's per-job
  `load_project_config`, and the API's `resolve_api_settings`, which loads it.
- **Legacy** (`auto-reel/movie_merge`):
  - `config/sort.py` defines `SortMethod{DATETIME, FILENAME, CUSTOM}`, `reverse`, `custom_order`.
  - `movie/processor.py:_sort_clips` orders `datetime` by `creation_date`.
  - `clip/processor.py:217` takes that as exiftool `DateTimeOriginal`, else `st_mtime`.

## Goals / Non-Goals

**Goals:**

- Legacy's `datetime`/`filename`/`reverse` semantics as the order clips *enter* a document, set per library.
- One rule, one helper, and every seeding path using the configured rule.

**Non-Goals:**

- A per-event rule and the legacy import mapping (`clip-order-legacy-sort`).
- Tag-based dates (proposal: Non-goals).

## Research & Decisions

### The rule and the ordering helper

**Decision**:

```python
# event/discovery.py
class SortMethod(StrEnum):
    DATETIME = "datetime"
    FILENAME = "filename"

@dataclass(frozen=True)
class ClipOrder:
    method: SortMethod = SortMethod.DATETIME
    reverse: bool = False

DEFAULT_CLIP_ORDER = ClipOrder()

def natural_key(name: str) -> tuple:
    """Digit runs as ints, everything else casefolded: clip2 < clip10, img_4863 < IMG_4933."""

def order_clips(identities: Sequence[str], event_dir: Path, order: ClipOrder) -> tuple[str, ...]:
    """Order ``identities`` (event-relative) by ``order``; datetime uses os.stat(...).st_mtime."""
```

- `datetime` uses the key `(st_mtime, natural_key(basename))`.
- `filename` uses `natural_key(basename)`, then the full identity, to break ties deterministically.
- `reverse` reverses the list.
- `stat` follows symlinks (dev and test libraries are symlinked), which is the target file's mtime, as
  intended.

**Rationale**:
- This is legacy's semantics minus exiftool, which is a probe (Principle IV).
- Natural, case-insensitive `filename` fixes `IMG_4933`, and matches plain order for every
  single-prefix camera event in the archive.
- The helper takes identities, not paths, so reconcile and adoption can use it directly.

### Where it applies

**Decision**:
- `seed_document(event_dir, *, order=DEFAULT_CLIP_ORDER)` orders each chapter's clips with `order_clips`.
- `load_authored_document`, `load_event_document`, `load_or_seed`, `prepare_event` and
  `prepare_and_persist` take a **required keyword** `order: ClipOrder`.
- `prepare_event` orders `result.new` per target chapter with `order_clips` before appending.
- `scan_event` keeps its sorted listing, because nothing reads its order as editorial.

**Rationale**: Making `order` required on the production loaders turns a forgotten call site into a mypy
error, instead of a silent default that ignores the library's `config.yaml`. `seed_document` keeps a
default because unit tests and library callers use it directly.

### Configuration

**Decision**: `ProjectConfig` gains `sort: ClipOrder`, parsed from `sort: {method, reverse}`.
- An unknown `method` raises `ConfigError` naming `sort.method`.
- A non-bool `reverse` raises `ConfigError` naming `sort.reverse`.
- The worker reads `config.sort` from the job's own project. `ApiSettings` gains `clip_order`, filled
  from the config it already loads.

**Rationale**: This is D-2 layering. The library default lives in `config.yaml`, and the per-event layer
arrives with the follow-up change.

### Fingerprint consequence

**Decision**: No new fingerprint input.

**Rationale**: For an event without a `reel.yaml`, the seeded chapter order is part of the document the
editorial component already hashes. A changed rule or a touched clip mtime therefore re-stales it
correctly, and the clip-set component already changes on an mtime change anyway. A persisted `reel.yaml`
fixes its order, so the rule no longer affects it.

## Failure behavior and idempotency

- **A malformed `sort`** fails loud at config load, before any event is touched.
- **A `stat` failure** on a listed clip raises `OSError`, which is per-event in the batch commands, like any
  unreadable clip. Listing just succeeded, so this is rare.
- **Re-runs** seed identically while the files are unchanged.
- **`--force`** has no bearing.
- **Worker restart** uses the same rule from the same config.
- **No `RENDER_GRAPH_VERSION` bump.** The order is an editorial input, not the graph.

## Risks / Trade-offs

- **[18 archive events carry copy or conversion mtimes]** Under `datetime`, they seed in conversion order;
  `Olika djur`, for example, would reverse. → Nearly all have legacy movies and are adopted, not
  re-rendered. The follow-up per-event `sort: filename` fixes any that get re-rendered, and a hand-ordered
  `reel.yaml` always wins.
- **[mtime ties at second resolution]** → They fall back to the natural filename order,
  deterministically.
- **[An adoption recorded before this change]** would re-stale. → None exists yet. The real
  `adopt-renders` runs after this change.

## Migration Plan

Deploy, then run the real `adopt-renders` (the operator's step). Seeded orders recorded from then on are
`datetime`. Rollback means reverting the helper and threading. Events adopted under `datetime` would then
report `editorial` stale if their order differs by name.
