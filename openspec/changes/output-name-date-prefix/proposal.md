## Why

**D-9** (HLD §7, change `output-path-year-folder`) set the output layout to
`<output>/<YYYY>/<title>[ - <location>].mp4`, calling it "the legacy auto-reel layout, so `adopt-renders`
finds the existing archive". It is not the legacy layout.

- **Legacy prefixed the date.** Legacy builds its movie title as `f"{date:%Y-%m-%d} - {metadata.title}"`
  (`auto-reel/movie_merge/config/directory.py:220`) before appending the location. D-9 was designed from
  the naming line in `project/processor.py` without following `movie.title` back to that line.
- **The drive confirms it.** The read-only survey of the real archive (2026-09-26) shows every legacy
  output named like `Completed-auto-reel/2017/2017-07-20 - Båttur med Liljan och Ralf.mp4`.
- **The mismatch breaks adoption.** Under D-9 as written, `adopt-renders` finds **0 of the 138** events
  from 2017 onward. With the date prefix it finds **129**, every name an exact match. The remaining 9 all
  have known causes: six `.reelignore` trips that legacy never rendered, two undated cases that the next
  change fixes, and one event legacy never rendered.

The promise at stake is change detection's D-C7: deploying the staleness gate onto years of
rendered footage must not trigger an archive-wide re-render. With D-9 as it stands, it would re-render
**275 GiB** of legacy output. This corrects HLD **§6 phase 4**'s output naming, and it is the last naming
blocker before a real-library run.

The survey also found **no tool to preview adoption safely**. `adopt-renders` writes a render manifest into
every adopted event's folder on the archive, and a preview today would mean an ad-hoc script. The operator
needs to see, before writing, how many events it would adopt and which it would not.

## What Changes

- **A dated event's output file name starts with its date.** The layout becomes
  `<output>/<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`, with the folder year and the name date
  both taken from `metadata.date`. An undated event is unchanged: `<output>/<title>[ - <location>].mp4`.
  The single path rule (`output_relpath`) changes, so every caller follows.
- **The collision check is unchanged, but its examples change.** Two same-titled events on different
  dates no longer collide. A collision now needs the same date, title and location (compared
  case-insensitively), or two undated events with the same title. The scenarios are rewritten to match.
- **`adopt-renders --dry-run` previews adoption without writing.** It reports, per event, whether it would
  adopt, already fresh, unrendered or colliding, with the same totals and exit code as a real run. It
  writes no manifest.
- **D-9 is amended in the HLD, and the README's output-layout text is corrected.**
- **The dev library's clash pair changes** (`scripts/make_dev_library.py`). `2024-07-14 - Kalas` and
  `2024-07-15 - Kalas` no longer collide, so the pair becomes two same-date events that differ only in
  folder-name case.

## Non-goals

- **No fix for the legacy `import` title.** `import` copies a legacy top-level `title` into
  `metadata.title`. Legacy used that field as the whole movie-name stem, often already `YYYY-MM-DD - …`,
  so an imported event would get the date twice. One event on the drive has such a file, and it is not
  imported. The next change (seeding and import) corrects the mapping. Until then, **do not run `import`
  before `adopt-renders`** on the real archive. Folder-seeded titles already match legacy exactly.
- **No change to undated events.** Legacy refused to render them; NG renders them at the output root.
  Making seeding fail loud on unparseable names is the next change.
- **No auto-suffixing** (the `output-path-year-folder` decision stands).
- **Real adoption is not run by this change.** Verification uses `--dry-run` only. Writing manifests
  onto the archive stays an explicit operator step.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `movie-assembly`: `Requirement: Output naming and overwrite control`. A dated event's file name is
  prefixed with its ISO date.
- `headless-cli`:
  - `Requirement: Batch commands refuse colliding output paths`: the scenarios are rewritten for
    date-prefixed names.
  - new `Requirement: adopt-renders previews without writing`.

## Impact

- **Packages:**
  - `render/`: `output_filename` / `output_relpath`, one function pair.
  - `cli/`: `adopt-renders` gains `--dry-run`.
- **Also touched:** the tests that hardcode output names, `scripts/make_dev_library.py`, `README.md`,
  `web/README.md` and `docs/high-level-design.md`.
- **CLI vs API (Principle V):** the path rule is shared, so the API's staleness verdicts follow
  automatically. `--dry-run` is CLI-only, and adoption has no API surface.
- **Rendered output:** the bytes are unchanged. **No `RENDER_GRAPH_VERSION` bump.** Only the file name
  changes.
- **Staleness fingerprint inputs:** unchanged. NG-rendered outputs under the old names (dev only) report
  `stale: output` and re-render under the new names. The old files are left in place, never deleted.
- **Schemas:** no `reel.yaml`, `config.yaml` or manifest change, **no Alembic migration**, no rescan.
- **Dependencies:** none.
- **Size (Principle VIII):** one naming function, one CLI flag, two capability deltas.
