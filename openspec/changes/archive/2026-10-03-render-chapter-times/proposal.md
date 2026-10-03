## Why

The render already measures where every chapter begins and throws the numbers away. `render/orchestrator.py`
probes each intermediate's duration, `render/chapters.py` turns them into cumulative `ffmetadata` `[CHAPTER]`
boundaries, and the concat muxes them into the movie. The sidecar that records the render
(`render-manifest.json`, **D-C2**, HLD §4.6) keeps none of it. The movie player on the event page
(**D-15**, HLD §4.10) therefore has no chapter list: its text says "the manifest records no chapter times and
browsers expose none", and names "chapter times in the render manifest" as a v2 item beside the proxy work.
Reading the times back out of the movie would need an ffprobe per event for a screen that is otherwise
probe-free, so the render, which already holds the measured values, records them once.

This is a GUI v2 item (HLD §4.10, §6 item 9) that depends on no open §8 research item and on none of the
proxy/timeline changes. The research round (`synthesis.md` §5) left it unsequenced; this change sequences it as
a Python-only slice. The player screen that would show the list is not part of it.

## What Changes

- **A `chapters` list in the render manifest.** After a successful render, `render-manifest.json` records one
  entry per chapter, in movie order: the chapter name, its start and end in integer milliseconds in the
  rendered movie, and the span of its title card, if the chapter has one (`null` otherwise). The numbers are
  the ones the engine muxes as `[CHAPTER]` markers, computed once from the measured durations of the segments
  that were actually concatenated, and the title-card span comes from the measured duration of the title-card
  segment itself. Nothing is estimated from the plan or from nominal durations (Principle I).
- **Backward compatible, no version bump.** The manifest schema version stays 1, exactly as `superseded` did
  (spec "The render manifest remembers the movie names it superseded"): a manifest without the field reads as
  `chapters = None`, a malformed field reads as `None` without making the manifest unreadable, and a reader
  that predates the field ignores it. A bump to 2 was considered and rejected (design, "No version bump").
- **A null is a statement, not a gap.** An event rendered before this change, or adopted by `adopt-renders`
  (no render happened, so nothing was measured), reads `None`. The engine never derives chapter times for them.
  They gain times on their next real render, which this change does not force.
- **Not a staleness input.** The fingerprint, the gate and `RENDER_GRAPH_VERSION` are untouched. The output
  bytes for identical inputs are unchanged (the `[CHAPTER]` markers already carry these boundaries).
- **Tests on real small renders** (`has_ffmpeg`; the title-card case also `has_fonts`): the recorded times equal
  the `[CHAPTER]` markers ffprobe reads back from the finished movie, and the last chapter ends at the movie's
  probed duration within one frame.
- **HLD:** amend D-15 (its "records no chapter times" sentence), the §4.10 v2 bullet, and the D-C2 sidecar
  text (§4.6) in the same change.

## Non-goals

- **No API, no `web/` change.** No endpoint, schema or generated type exposes `chapters`; the movie player's
  chapter list is a later GUI change that will read it. (The OpenAPI document and web types are untouched.)
- **No chapter times for already-rendered events.** No backfill, no on-read ffprobe of the movie, no
  `--force` render triggered by this change, and `adopt-renders` writes `null`.
- **No new CLI command and no new log line.** There is no consumer of the field yet, so no CLI surface is
  added for it (Principle V's "same change" applies to behaviour the CLI cannot reach, and `render` reaches
  this one).
- **No new fingerprint component, no Alembic migration, no rescan.** Postgres never holds the field
  (Principle II).
- **No per-clip or per-segment times.** The timeline editor (D-20) gets clip positions from proxy facts, not
  from the render; the manifest records chapter-level times and the title card only.
- **No nominal-duration fallback.** If a duration is unavailable the render already fails (a probe error);
  the field is never filled from a guess.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-detection`: `Render manifest sidecar` gains the optional chapter-times record and the
  null-for-unmeasured and tolerant-read rules (MODIFIED).
- `movie-assembly`: new `Requirement: Chapter times are recorded from the same measured timeline`, which says
  what the recorded numbers are and ties them to the muxed markers (ADDED).

## Impact

- **Baseline:** written against `origin/main` at `8fb4d16`.
- **Packages:** `render/` (`chapters.py` computes the times; `orchestrator.py` passes them to the manifest
  write) and `staleness/` (`manifest.py` stores, validates and reads them). Files:
  `auto_reel_ng/render/chapters.py`, `auto_reel_ng/render/orchestrator.py`,
  `auto_reel_ng/staleness/manifest.py`, `auto_reel_ng/staleness/__init__.py` (export),
  `tests/test_render_chapters.py` (new), `tests/test_render_manifest.py`, `tests/test_title_card.py`,
  `tests/test_staleness_manifest.py`, `tests/test_cli_adopt_renders.py`, `docs/high-level-design.md`.
- **CLI vs API (Principle V):** engine-only. `auto-reel render` and the worker both go through
  `render_movie`, so both write the field; the API reads nothing new.
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump**; the staleness
  fingerprint inputs are unchanged (Principle IV); a render that fails, is skipped or is a dry run writes no
  manifest, as before.
- **Schemas:** `render-manifest.json` gains an optional field at the same version; no `reel.yaml` or
  `config.yaml` change, **no Alembic migration**, no rescan.
- **Complexity (Principle VII):** one frozen dataclass, one pure function, one optional keyword on
  `write_manifest`; no config key and no dependency.
- **Size (Principle VIII):** two capability deltas, two packages, 6 tasks (one baseline, one docs, one gates).
