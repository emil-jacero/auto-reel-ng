## Why

HLD §2 lists folder conventions from `auto-reel` "worth **keeping**": chapters from subdirectories,
root clips as the default chapter, **`original/` skipped**, **`.reelignore`**. The first two were ported
(`event-reconcile`, `ingest-layout`). The last two never reached a spec or the code:

- `scan_event` treats every immediate subdirectory as a chapter, `original/` included.
- No layout or scan reads `.reelignore`.

A read-only survey of the real archive (the MOL drive, 2026-09-26: 141 events, 6,538 clips under
`Videos/Sorted`) shows that both conventions carry real weight:

- **`original/` holds the pre-conversion camera originals.** Legacy auto-reel converted AVCHD `.MTS` and
  `.M2TS` clips to `.mp4` and moved the originals into `original/`. **963 clips (71.6 GiB) across 17
  events** sit in a top-level `original/` that NG discovers as a chapter named `original`. Every one of
  those events would render its footage **twice**: the converted copy in the default chapter, then the
  original again as a trailing chapter.
- **`.reelignore` marks events and chapters that must not be auto-rendered.** **6 events, 2,840 clips
  and 253 GiB** carry one, including five of the six largest events in the library (Verona, Gran
  Canaria, Toscana, both Norrland trips, Gotland). They are edited by hand (`Videos/Projects/`), and
  legacy skipped them entirely. NG would render all six. One chapter-level `.reelignore` exists
  (Verona's `dålig-kvalitet/`, "poor quality").

Either gap turns the first library-wide `render` into hours of wrong output. That makes this a
precondition for processing the real library, a correction to HLD **§6 phase 3** (discovery). It is
grounded in HLD §2's list of mechanics to keep, and it comes before GUI slice C, which would otherwise
show `original` as a chapter.

## What Changes

- **`original/` is never a chapter.** An event subdirectory named `original` (compared
  case-insensitively) contributes no clips.
  - Deeper `original/` folders, such as `2017-07-10/original/`, already contribute none, because
    discovery reads only one subdirectory level. The spec now states that as the rule.
- **A subdirectory containing `.reelignore` is never a chapter.** Its clips are not discovered.
- **An event directory containing `.reelignore` is not an event.** The built-in layouts do not yield
  it, so `scan`, `render`, `enqueue`, `adopt-renders`, `import`, `analyze` and the API events list all
  skip it with no change of their own. Each skipped event is logged once at INFO level
  (`skipping <dir>: .reelignore`), as legacy did, so a run shows what it left out.
- These rules decide what counts as "a clip on disk" for **every** consumer of the event listing,
  because all five go through `scan_event`: seeding, reconcile, the staleness fingerprint's clip-set,
  the analysis cache and the API. A change inside `original/` or an ignored chapter therefore no
  longer makes an event stale.

## Non-goals

- **No new ignore syntax.** `.reelignore` is a marker file, and its contents are not read, exactly as
  legacy did. There are no patterns and no per-file ignores. Per-file dismissal is the existing
  document-level `ignore` list.
- **No year-level `.reelignore`.** Legacy honoured it at event and chapter level only.
- **No change to the API's by-id routes.** `GET /api/v1/events/{id}` and `POST /api/v1/jobs` resolve an
  event directory by its ID, not through the layout, so a hand-typed ID can still reach an ignored
  event. Nothing lists or offers one. A follow-up closes this when an API change next touches
  `resolve_event_dir`.
- **No migration of already-seeded documents.** A `reel.yaml` seeded by NG before this change that
  lists `original/` clips keeps them. Reconcile then reports them as MISSING, because they are no
  longer on the disk listing, and the operator removes them. On the real library, no NG-written
  document exists yet: its one `reel.yaml` and nine `metadata.yaml` files are legacy and have no
  chapters.
- **No output-naming fix.** The legacy archive's date-prefixed names (`2017/2017-07-20 - Båttur
  ….mp4`) are the next change, which amends D-9.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `event-reconcile`: new `Requirement: Legacy folder conventions exclude clips from discovery`.
  `original/` and `.reelignore`-marked subdirectories contribute no clips to any disk listing, seeding
  or reconcile.
- `ingest-layout`: new `Requirement: An event marked with .reelignore is not an event`. The built-in
  layouts do not yield it, and they log the skip.

## Impact

- **Packages:**
  - `event/`: `discovery.py`'s `scan_event`, plus the two marker names as constants.
  - `ingest/`: `layouts.py`'s two built-in walks.

  No caller changes. The CLI, API, scheduler, staleness and analysis already go through these two
  seams.
- **CLI vs API (Principle V):** both inherit the behavior from the engine, and neither gains a flag.
- **Rendered output:** for an event with `original/` or an ignored chapter, the rendered movie changes
  (the duplicate chapter disappears). The graph does not change, so there is **no
  `RENDER_GRAPH_VERSION` bump**. The change reaches the fingerprint through its existing clip-set
  component, which now hashes the smaller listing, so affected events turn stale on their own.
- **Staleness fingerprint inputs:** same components, and the clip-set input is the corrected listing.
  Events with neither marker keep identical fingerprints.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan.
- **Dependencies:** none.
- **Size (Principle VIII):** two functions in two packages, two capability deltas.
