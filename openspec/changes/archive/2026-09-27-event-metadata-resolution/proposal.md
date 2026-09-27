## Why

Principle I, fail loud and never fabricate, is the legacy bug NG exists to fix (HLD §2, problem 5). Event
metadata still breaks it in both directions. The read-only survey of the real archive (2026-09-26) and
`adopt-renders --dry-run` (2026-09-27) show where:

- **A folder name with no usable date loses its title too.** `parse_folder_name` returns nothing for the
  whole name when the date part is year-only (`2004 - Yngve berättar om skövde`,
  `2016 - Kents film - Gran Canaria`) or impossible (`2019-04-31 - Golfträning med Emil - Tjörn`). All three
  events become `Untitled`, and they collide on `Untitled.mp4`. "Untitled" is fabricated, and the actual
  problem, a date that cannot exist, is never reported.
- **A `reel.yaml` hides the folder name completely.** Once a document exists, its metadata is used as-is.
  `2025-01-13 - Resa till Gran Canaria` has a legacy `reel.yaml` with a title but no date, so NG treats the
  event as undated, even though the folder states the date. D-2 (HLD §7) orders resolution as *folder/layout
  seed → project config → event `reel.yaml`*, so the folder is the lowest layer a field falls back to, not a
  layer discarded wholesale.
- **One bad event aborts a whole CLI run.** A document or metadata error in one event escapes the command,
  and `main()` prints a single `error:` and exits. `render` over 141 events stops at the first bad one.
  Principle I allows exactly one softening, per-event isolation, and the batch commands do not have it for
  this class of error.

The operator decided the rules (2026-09-27):
- `reel.yaml` takes priority, field by field.
- An event must end up with a real date and a title.
- A folder name that is well-formed but logically wrong fails loud.
- Nothing is derived from media, and no folder is renamed here. Renaming a folder to match `reel.yaml` is a
  separate, explicit, later change.

This corrects HLD **§6 phase 3** (seeding and metadata) and is a precondition for a library-wide run.

## What Changes

- **Lenient folder-name parsing with a stated problem.** The parser recognizes
  `[<date-token> - ]<title>[ - <location>]` and always extracts the title and location it can. The date
  token is:
  - a valid ISO date, which becomes the date
  - an impossible ISO date (`2019-04-31`)
  - a year only (`2004`)
  - absent

  In the last three cases the date is left unset, and the parse carries a **problem** that names the reason.
  Seeding never raises, and a seeded document never contains a fabricated value such as `Untitled`.
- **Metadata resolves field by field.** Date, title and location each take the event's `reel.yaml` value
  when set, otherwise the folder name's value, whether the document is v0 or legacy. Every place that
  processes an event reads the resolved metadata: output naming, the title card, the staleness
  fingerprint, `scan`, the worker, and the events list and detail. The editorial read/write endpoints keep
  reading and writing `reel.yaml` exactly as authored, and resolution is never written back to disk.
- **An event must resolve to a real date and a title, or it fails loud on its own.** It fails when its
  resolved metadata:
  - has no date, reporting the folder name's problem (impossible date, year only, or no date)
  - has no title
  - has a date after today (a typo)

  The error names the event, the reason, and the fix: set `metadata.date`/`title` in `reel.yaml`, or
  correct the folder name. A folder name's problem is **not** an error when `reel.yaml` supplies that field.
- **The batch commands isolate per-event document errors.** In `scan`, `render`, `enqueue` and
  `adopt-renders`, an event whose `reel.yaml` cannot be parsed or whose metadata fails the rule above is
  reported as `ERROR <event>: <reason>` and skipped. The rest proceed, and the command exits non-zero. The
  worker fails the job with the same reason, and the events reads return their existing per-event problem
  body.
- **The dev library's undated event gets a date in its `reel.yaml`** (`scripts/make_dev_library.py`). This
  keeps the GUI list working (see Non-goals) and exercises "`reel.yaml` over folder name".

## Non-goals

- **Nothing is derived from media.** The survey shows why: the year-only events are digitized footage whose
  file dates are the digitization dates, 19 years off for Yngve. Media-derived dating belongs upstream, in
  reel-ingest and reel-sort, for the unsorted backlog.
- **No folder renames.** Syncing a folder name to its `reel.yaml` is the next change in this area: an
  explicit command with `--dry-run`, never a side effect. The *year folder ≠ date year* check moves there
  too, because it is an out-of-sync state that command resolves, not a parse error.
- **No per-event error rows in the events list.** The list still fails whole (502) when any event fails,
  per `events-list-client-contract`. On the real archive that means the GUI list needs the 3 bad events
  fixed first. Per-event rows are a separate API and web change.
- **No legacy `import` title fix.** A legacy top-level `title` such as `2025-01-13 - Resa till Gran Canaria`
  still becomes `metadata.title` verbatim, so that event resolves to a doubled date. The follow-up change
  `legacy-import-title` (`reel-document`) strips it. It is kept separate to stay within two capability
  deltas.
- **No change to the undated output rule** in `movie-assembly`. It remains the engine-level rule for a plan
  without a date. The project-level rule above means a valid project event never reaches it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `event-reconcile`:
  - `Requirement: Discovery seeds a complete document from folder structure` now covers the lenient parse
    with a stated problem, and never fabricates a title.
  - new `Requirement: Event metadata resolves field by field, reel.yaml over folder name`.
- `headless-cli`: new `Requirement: An event without a real date and title fails on its own`. This covers
  the metadata rule and per-event isolation of document errors in the batch commands.

## Impact

- **Packages:**
  - `event/`: `discovery.py` (parse, seed, resolve and validate helpers).
  - `cli/`: the per-event isolation in `scan`, `render`, `enqueue` and `adopt-renders`, and `load_or_seed`
    returning resolved metadata.
  - `api/` (`events_read.py`) and `scheduler/` (`worker.py`): switched to the resolving loader plus the
    validation call. No new API behavior: failures use the existing per-event problem body and job failure.
  - `ingest/layouts.py`: the folder hint uses the new parse result.
- **CLI vs API (Principle V):** the CLI gains per-event reporting. The API reaches the same rule through the
  same engine helpers.
- **Rendered output:** unchanged for events whose metadata already resolved. **No
  `RENDER_GRAPH_VERSION` bump.** An event whose `reel.yaml` lacked a field the folder supplies now resolves
  it. Its editorial fingerprint component changes, so it reports stale, which is correct: its output name
  or card text changes.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan.
- **Real archive, after this change:** `adopt-renders --dry-run` should report
  - 129 would-adopt
  - `ERROR` for the 3 bad folder names, instead of the `Untitled.mp4` collision
  - 3 unrendered: Spanien, 2012 Emma & Eli, and 2025 Gran Canaria (its doubled date, fixed by
    `legacy-import-title`)
- **Dependencies:** none.
- **Size (Principle VIII):** one parse-and-resolve module plus per-event isolation at four CLI entry points,
  two capability deltas.
