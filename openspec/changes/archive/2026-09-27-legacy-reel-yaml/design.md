## Context

See proposal.md — Why. The code facts that shape the approach:

- **`reel/schema.build_document`** parses `metadata`, `look`, `chapters`, `clips` and `ignore`. Other
  top-level keys are ignored, not rejected, so an additive `sort` key is safe for older engines.
- **`reel/legacy.import_legacy`:**
  - `_import_metadata` copies the top-level `title` verbatim into `metadata.title`, and `metadata.date`
    only from the legacy `metadata` block.
  - `_report_sort` reports `custom`, `custom_order` and `reverse` as unmapped.
  - `load_document` routes every versionless file through `import_legacy_data` on **every load**, not
    only through `auto-reel import`.
- **`event/discovery.py`** defines `SortMethod{DATETIME, FILENAME}`, `ClipOrder(method, reverse)`,
  `natural_key` and `order_clips`. `config/project.py` builds `ProjectConfig.sort: ClipOrder`.
  `cli/adoption.prepare_event(event_dir, *, order)` orders `result.new` with `order_clips(..., order)`.
- **Layering:** `reel/` sits below `event/`. `event/discovery.py` imports from `reel/`, never the reverse.

## Goals / Non-Goals

**Goals:**

- auto-reel's per-event `sort` (including `custom`/`custom_order`/`reverse`) works end to end, from legacy
  files and from v0.
- A dated legacy title never doubles the date, and the real archive's one such event adopts.

**Non-Goals:**

- Location de-duplication for imported `metadata.yaml` titles (proposal: Non-goals).
- `custom` in `config.yaml`.

## Research & Decisions

### Where the sort types live

**Decision**: Move `SortMethod` (gaining `CUSTOM = "custom"`) and `ClipOrder` (gaining
`custom_order: Mapping[str, int] = MappingProxyType({})`) into `reel/document.py`, and re-export both from
`event/discovery.py` and `auto_reel_ng.event`. `ReelDocument` gains `sort: Optional[ClipOrder] = None`.

**Rationale**:
- The document must carry the rule, and `reel/` cannot import `event/` (Principle VI).
- The type describes an editorial fact, so it belongs with the document model.
- The re-export keeps every `from ..event import ClipOrder` working unchanged.

### Parsing and writing `sort`

**Decision**:
- `schema._parse_sort` validates:
  - `method` in the enum
  - `reverse` is a `bool`
  - `custom_order` is a mapping of `str` to `int`, allowed only with `method: custom`

  Errors raise `ReelParseError` naming `sort.<field>`.
- `config/project.py` keeps rejecting `custom` for the library rule, and refers to the shared enum.
- The writer's fresh-document path emits `sort` when it is set. Loaded documents round-trip `sort` through
  `raw` untouched, which is the existing behavior for any key.

### Precedence

**Decision**: `prepare_event` uses `effective = document.sort or order`, where `order` is the library
rule passed in, whenever it orders NEW clips. `seed_document` has no document yet (no `reel.yaml`), so it
always uses the library rule.

**Rationale**:
- An event's own rule wins, as in auto-reel, where per-event `reel.yaml` overrode the project's.
- The only way a per-event rule exists before structure does is a `reel.yaml` without chapters (legacy,
  or hand-written), and in that case every clip enters through adoption. The per-event rule therefore
  materializes exactly on the first adoption, which is legacy's "materialize order" semantics.

### `custom`

**Decision**: `order_clips` gains the `custom` branch. The key for a listed clip is
`(0, position, natural_key(basename))`, and for an unlisted one `(1, natural_key(basename))`. `reverse`
then flips the whole list. Keys match the clip's **file name** (basename), as legacy keyed on
`x.path.name`. The rule is applied per chapter, so a basename that appears in two chapters is placed within
each chapter independently.

**Rationale**: This is legacy's semantics, where unlisted clips sort after listed ones (legacy used `inf`),
with NG's deterministic tie-break in place of legacy's arbitrary filesystem order.

### The dated legacy title

**Decision**: In `_import_metadata`, when the top-level `title` matches `^(\d{4}-\d{2}-\d{2}) - (.+)$`:
- If the date parses, and the legacy `metadata.date` is absent or equal to it, then `title = rest`, and the
  date is set if it was absent.
- If the date is not real, or disagrees with `metadata.date`, the title is left verbatim. Nothing is
  reported, because the title is valid text and D-2 resolution and validation still apply downstream.

**Rationale**: This follows exactly the stem legacy composed (`directory.py:220`), and it never discards
information. When the date is taken from the title, the title stops carrying it, which is the whole point.

## Failure behavior and idempotency

- **A malformed `sort`** fails loud at document load. In the batch commands that is a per-event `ERROR`
  (`event-metadata-resolution`).
- **Re-runs:** loading the same legacy file yields the same document.
- **A persisted v0 document** keeps its `sort` for later NEW clips.
- **`--force`** has no bearing.
- **Worker restart** uses the same rule.
- **No `RENDER_GRAPH_VERSION` bump.** Order and titles are editorial inputs.

## Risks / Trade-offs

- **[A hand-written title that merely starts with a date]** A v0 title is never touched: only legacy
  top-level titles are, and only when the date matches. So "2024-06-21 - Midsommar" typed into a v0
  document still renders with the date twice. → That's intended: a v0 title is the operator's literal text.
- **[`custom_order` naming files that don't exist]** Those names simply match nothing, as in legacy. →
  They are not an error: the rule orders only the clips it is given.

## Migration Plan

Deploy. On the archive, `adopt-renders --dry-run` then reports 130 would-adopt, with
`2025-01-13 - Resa till Gran Canaria` now matched. There is nothing to migrate. Rollback means reverting
the import mapping, the `sort` field and the precedence.
