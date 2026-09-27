## Why

`reel-document`'s legacy import requirement promises that auto-reel's `sort` is "honored when materializing
order". It never was. `reel/legacy.py` reports `custom`, `custom_order` and `reverse` as unmapped, and claims
`datetime`/`filename` are "honored implicitly". Until `clip-order` they were not, and even now only the
**library** rule applies: a per-event legacy `sort:` is read and then dropped. The operator asked to reuse
auto-reel's sort options (2026-09-27), and the per-event override was deferred here from `clip-order`.

The same importer mishandles legacy's top-level **`title`**. In auto-reel, that field is the movie's full
name stem, which auto-reel builds as `"<YYYY-MM-DD> - <title>"` when it is unset (`config/directory.py:220`).
Written out by hand, it carries the date. NG copies it into `metadata.title`, and output naming (D-9) then
prefixes the date again. On the real archive (read-only survey and `adopt-renders --dry-run`, 2026-09-27):

- `2025-01-13 - Resa till Gran Canaria` holds a legacy `reel.yaml` with `title: "2025-01-13 - Resa till
  Gran Canaria"`. It would render as `2025-01-13 - 2025-01-13 - Resa till Gran Canaria.mp4`.
- It is therefore the one event `adopt-renders` cannot match to its legacy movie: 129 would adopt, not 130.

Both are the legacy-document fidelity HLD §2 promises. This is a precondition for the first real run: that
event must not render a doubled name. It belongs to HLD **§6 phase 3**, and it completes the `clip-order`
work.

## What Changes

- **A v0 `reel.yaml` may carry a `sort` rule for its event.**
  - The form is `sort: {method: datetime|filename|custom, reverse: bool, custom_order: {<file name>: <position>}}`.
  - When set, it overrides the library's `config.yaml` rule for the clips entering that event's document.
  - `custom` orders clips listed in `custom_order` by position, and places unlisted clips after them in
    `filename` order.
  - A malformed `sort` fails loud, like any other v0 field.
- **Legacy `sort` is carried, not reported.** Importing a legacy `sort` (method, `reverse`, `custom_order`)
  maps it onto the v0 `sort`, so it takes effect when the event's clips are first adopted. Only an unknown
  method is still reported as unmapped.
- **A legacy title's date prefix is recognized.** A legacy top-level `title` of the form
  `YYYY-MM-DD - <rest>` imports as `metadata.title: <rest>`, provided the date is real and either equals the
  legacy `metadata.date` or no date is given. When no date is given, the prefix supplies it. Any other title
  imports verbatim, as today.
- The importer's false comment ("honored implicitly") is corrected.

## Non-goals

- **No location stripping.** The 9 legacy `metadata.yaml` files have titles like
  `"Dans hemma - Kungälv"`, which include the location, and importing one would produce
  `… - Kungälv - Kungälv.mp4`. The archive's legacy movies were rendered from folder names (that auto-reel
  version never read `metadata.yaml`). NG's scan never reads `metadata.yaml`, only `import` does. So these
  are unaffected unless the operator imports them, and the README says to set the title by hand first.
- **No re-sorting of existing orders.** An event's `sort` still only orders clips *entering* its document
  (`clip-order`).
- **No `sort` in `config.yaml` beyond `datetime`/`filename`.** `custom` names specific files, so it is
  per-event only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reel-document`:
  - `Requirement: Versioned reel.yaml v0 schema` gains the optional `sort`.
  - `Requirement: Import of auto-reel legacy format` now carries `sort` and recognizes the dated title stem.
- `event-reconcile`: `Requirement: Clips enter a document in the configured sort order`. The event's own
  `sort` overrides the library's, and `custom` is added.

## Impact

- **Packages:**
  - `reel/`:
    - `document.py`: `SortMethod` (now with `CUSTOM`) and `ClipOrder` (now with `custom_order`) move here
      from `event/discovery.py`, because `reel/` sits below `event/`. `event/` re-exports them, so existing
      imports keep working.
    - `schema.py`: parses `sort`.
    - `legacy.py`: maps `sort` and the dated title.
    - `writer.py`: emits `sort` for fresh documents.
  - `event/`: `order_clips` implements `custom`.
  - `cli/`: `adoption.py` uses the document's `sort` over the library rule.
- **CLI vs API (Principle V):** both reach it through `prepare_event`. There is no new surface.
- **Rendered output:** clip order for events with a per-event rule, and the title of an event with a dated
  legacy title. Both are editorial inputs, so there is **no `RENDER_GRAPH_VERSION` bump**. On the archive,
  only `2025-01-13 - Resa till Gran Canaria` changes: its name becomes the legacy one, and its `sort` is
  `datetime`, the default.
- **Schemas:** `reel.yaml` v0 gains an optional `sort` key. `version` stays 0, because the key is additive,
  and an older engine silently ignores it rather than failing. No Alembic migration, no rescan.
- **Real archive after this change:** `adopt-renders --dry-run` reports **130** would-adopt.
- **Dependencies:** none.
- **Size (Principle VIII):** one optional v0 field, two import mappings, one extra sort method, two
  capability deltas.
