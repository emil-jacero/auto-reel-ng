## Why

When an event directory is reachable under two names inside the project root (a symlink
`2024/2024-07-20 - Fest -> 2024-07-20 - Kalas`), the layouts yield both as separate events. The
first one processed seeds `reel.yaml` *through the symlink* into the shared real directory, so
`Kalas/reel.yaml` is written with `title: Fest` (verified on main `6a7fe16`; `ingest/layouts.py`
`_subdirs`/`_event_refs` never compare real paths). Principle II (disk is the source of truth)
and Principle I (fail loud, never fabricate) are both hit: an editorial file is silently
corrupted with metadata that belongs to a different folder name, and the worker path
(`prepare_and_persist`) has no collision check, so it renders under the alias name. This is
HLD §6 phase 8 hardening of the D-6 ingest layouts; no research item (§8) is involved.

## What Changes

- The built-in layouts (`year-event`, `flat`) yield each real event directory **once**: rows whose
  `Path.resolve()` is equal are collapsed to one. The canonical path (reached without crossing a
  symlink) wins; if none is canonical, the first in walk order wins.
- Each dropped alias is logged once per walk at WARNING, naming the alias, the kept path and the
  resolved target, so the run reports what it left out (same pattern as `.reelignore`).
- Because the fix is in the shared walk, CLI `scan`/`render`/`enqueue`/`adopt`/`import`/`analyze`,
  the service's events list and listed-event lookups are all covered with no `cli/`, `scheduler/`
  or `api/` edit. A dropped alias is no longer an event: it is not seeded, enqueued, rendered or
  listed, and listed-event lookups report it as not found.
- Regression tests: the Kalas/Fest repro at layout level, through `scan`, and through
  `prepare_event` + `persist` (target `reel.yaml` untouched, nothing created through the alias).

Non-goals:
- Reporting the alias as a per-event ERROR row (needs a new failure channel in `cli/` and `api/`;
  rejected in design.md).
- `POST /api/v1/jobs` with an explicit alias id and `GET /api/v1/events/{id}` of an alias: both
  take the id as spelled (`named_event_dir` / `resolve_event_dir`), not through the walk, so they
  still accept it; the worker renders the job's own `event_dir`. Left for a follow-up.
- A write-time guard in `persist`/`prepare_event`, hardlinks, bind mounts, or a symlink that
  points *outside* the project root (a single row, so not a duplicate; left as the user's choice).
- Any change to `reel.yaml`, `config.yaml`, the staleness fingerprint or rendered output: **no
  `RENDER_GRAPH_VERSION` bump**, no schema change, no Alembic migration, no rescan.

## Capabilities

### New Capabilities

### Modified Capabilities
- `ingest-layout`: adds a requirement that aliases of one real event directory are walked once,
  and that the dropped alias is logged.

## Impact

- Package: `auto_reel_ng/ingest` only (`layouts.py`). Tests: `tests/test_ingest_layouts.py`,
  plus one test each in `tests/test_cli_commands.py`, `tests/test_cli_adoption.py` and
  `tests/test_api_events.py`. `tests/test_api_jobs.py` and `tests/test_api_output_collision.py`
  change: their in-project-alias cases pinned the alias as a row of its own and now pin that it
  claims nothing.
- CLI and API are both touched only indirectly (they consume the layouts); no new surface.
- Existing libraries that deliberately symlinked a second name for an event will stop seeing the
  second name; its WARNING says which path is kept.
