## Why

HLD §2 lists auto-reel's **sort strategies (datetime / filename / custom order)** among the mechanics "worth
keeping". NG ported none of them. `scan_event` orders an event's clips by a plain, case-sensitive filename
sort, and that order is what seeding writes into a new `reel.yaml` and what NEW-clip adoption appends.

The first real-footage test render (2026-09-27) and a library-wide measurement of the archive (132 events
with two or more root clips) show where that departs from what auto-reel produced:

- **Two cameras in one event are not interleaved.** In `2024-04-20 - Lasse 80 år…`, the clips from four
  sources (`C`, `IMG`, `P`, `S`) play grouped by name prefix, not in the order they were filmed.
- **Uppercase sorts first.** In `2022-04-03 - Olika djur`, `IMG_4933` plays before `img_4863 … img_4932`.
- **Legacy's default was different.** It was `sort: method: datetime` (it is set in the archive's root
  `reel.yaml`), which ordered by exiftool `DateTimeOriginal`, else the file mtime. For 113 of the 132 events,
  the file mtimes fall on or near the event date, so they are recording times.

The operator's decision (2026-09-27): reuse legacy's options, with `datetime` as the default. This belongs
to HLD **§6 phase 3** (seeding). It must land before the real `adopt-renders` run: for an event without a
`reel.yaml`, the seeded order is part of the editorial fingerprint an adoption records.

## What Changes

- **Clips enter a document in a configured order.** Two things add clips from disk: seeding a new document,
  and adopting NEW clips into an existing one. Within each chapter, both order the incoming clips by a
  **sort rule**:
  - `datetime` (the default): by file modification time, oldest first, ties broken by the `filename`
    order. It uses only `stat`, never a probe, so scanning stays probe-free.
  - `filename`: a natural, case-insensitive order (`img_4863 … IMG_4933`, `clip2` before `clip10`).
  - `reverse: true` flips either.

  Chapter order (subfolders by name) is unchanged. A document's existing clip order is **never**
  re-sorted: after seeding, the order is editorial, and it is changed in `reel.yaml` (later, by GUI drag).
- **Project `config.yaml` gains `sort: {method: datetime|filename, reverse: bool}`**, the library default.
  An unknown method or a wrong-typed field fails loud, like every other `config.yaml` field.
- **The rule reaches every seeding site.** That covers the CLI commands, the worker, and the service's
  events reads, all from the same project config, so the order `scan` shows is the order `render` persists.

## Non-goals

- **No per-event `sort:` in `reel.yaml`, and no import of legacy per-event `sort`/`custom_order`/`reverse`.**
  That requires a `reel-document` schema change (a third capability), so it is the follow-up
  `clip-order-legacy-sort`. No event on the archive uses a non-default rule today: its one legacy `reel.yaml`
  says `datetime`. Legacy's `custom` method is NG's native clip list.
- **No exiftool or ffprobe dates.** Reading a date tag is a per-clip probe, which the scan and events-list
  paths forbid (Principle IV, D-A3). Legacy asked exiftool only for `DateTimeOriginal`, which camera MP4s
  rarely carry, so its `datetime` fell back to mtime in practice.
- **No plausibility guard on mtimes.** 18 archive events carry copy or conversion times instead of recording
  times (the legacy-converted ones). Legacy's `datetime` ordered them by those times too, and nearly all of
  them have legacy movies that will be adopted, not re-rendered. The per-event override in the follow-up is
  the fix for any that are re-rendered.
- **No re-sorting of NEW clips into the middle of an existing order.** They are appended, as today, in rule
  order among themselves.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `event-reconcile`: new `Requirement: Clips enter a document in the configured sort order`.
- `project-config`: `Requirement: Load a project config.yaml of shared defaults` gains the optional `sort`
  rule and its validation.

## Impact

- **Packages:**
  - `event/`: `discovery.py` gains the ordering helper; `seed_document` and `load_authored_document` take
    the rule.
  - `config/`: `project.py` adds the `sort` field and its validation.
  - `cli/`: `adoption.py` orders NEW clips, and the commands pass the rule.
  - `api/` and `scheduler/`: pass the rule from the project config they already load.
- **CLI vs API (Principle V):** both read the same config and call the same helpers. There are no new
  surfaces.
- **Rendered output:** the order of clips in newly seeded events changes, which is an editorial input, not
  the graph. **No `RENDER_GRAPH_VERSION` bump.** Events without a `reel.yaml` whose seeded order changes
  report stale through their `editorial` component. None are rendered by NG yet.
- **Schemas:** `config.yaml` gains an optional `sort` key. There is no `reel.yaml` change, no Alembic
  migration, and no rescan.
- **Dependencies:** none.
- **Size (Principle VIII):** one ordering helper, one config key, threading one parameter, two capability
  deltas.
