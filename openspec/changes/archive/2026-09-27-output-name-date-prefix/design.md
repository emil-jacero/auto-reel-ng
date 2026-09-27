## Context

See proposal.md — Why. The facts that shape the approach:

- `render/orchestrator.py` owns the rule as two functions:
  - `output_filename(metadata)` returns `<title>[ - <location>].mp4`
  - `output_relpath(metadata)` adds `<YYYY>/` when dated

  Every caller (render, `scan`, `enqueue`, `adopt-renders`, the worker, both API reads, the jobs
  route) goes through `output_relpath`. `find_output_collisions` compares the resulting relative paths.
- **Legacy naming**, traced end to end:
  - `directory.py:220` sets `config.title = f"{date:%Y-%m-%d} - {metadata.title}"` when the yaml's
    top-level `title` is unset.
  - `processor.py:201-205` writes `output_path / str(metadata.year) / f"{movie.title}[ - {location}].mp4"`.
  - The archive was produced by a version whose `METADATA_FILE` is `reel.yaml`, so the 9 events' later
    `metadata.yaml` titles never influenced a name. The archive's `2023-12-08 - Dans Hemma - Kungälv.mp4`
    is the folder-derived title.
- **Survey facts** (read-only, 2026-09-26):
  - 138 events from 2017 onward.
  - A date-prefixed `output_relpath` found 129 exact matches: no case-only differences, none needing
    normalization.
  - `Completed-auto-reel/temp/` holds 22 legacy debris files that no event claims.
- **`cmd_adopt_renders`** parses only the common options. Passing `--dry-run` is an argparse error today,
  so there is no latent write-under-dry-run path to worry about.

## Goals / Non-Goals

**Goals:**

- `output_relpath` reproduces legacy's archive names exactly for folder-seeded events.
- A safe, reproducible way to measure that against the real archive, which is also the operator's
  deploy-time preview.

**Non-Goals:**

- The legacy `import` title mapping and seeding of unparseable names (next change).
- Cleaning up `Completed-auto-reel/temp/`. It's the operator's data, and nothing in NG writes there.

## Research & Decisions

### Where the date goes

**Decision**: The prefix belongs to the file name, which is where legacy put it, so
`output_filename` gains it:

```python
def output_filename(metadata: Metadata) -> str:
    """``[<YYYY-MM-DD> - ]<title>[ - <location>].mp4``, the legacy auto-reel name.

    A dated event's name starts with its ISO date (legacy ``directory.py:220``);
    an undated event has no prefix. The location, when present, is appended.
    """
    stem = metadata.title or "Untitled"
    if metadata.date is not None:
        stem = f"{metadata.date.isoformat()} - {stem}"
    if metadata.location:
        return f"{stem} - {metadata.location}.mp4"
    return f"{stem}.mp4"
```

`output_relpath` is unchanged in shape: `<YYYY>/` plus `output_filename`, or the bare filename when
undated. `date.isoformat()` is `YYYY-MM-DD` for every `datetime.date`, and it is the same string legacy's
`strftime('%Y-%m-%d')` produced.

**Alternative rejected**: the prefix in `output_relpath` only. That would leave `output_filename` returning
a name no file on disk has. Keeping the function whose name is "the file name" honest is cheaper than
documenting why it lies.

### How to verify against the archive without writing to it

**Context**: The acceptance number is "129 of 138 legacy outputs found". It can only be measured on the
real drive, which is the operator's archive. The implementing session may not have my survey script.

**Explored**:
- (a) a one-off script in `scripts/`
- (b) running `adopt-renders` on a copy of the archive (2.3 TiB)
- (c) `adopt-renders --dry-run`

**Decision**: (c). `cmd_adopt_renders` takes a `dry_run` flag. It runs the full evaluation (document
load, `output_relpath`, collision check, fingerprint, gate), then prints each outcome prefixed `would`
instead of calling `write_manifest`. The summary line ends with `(dry run: nothing written)`. The exit
code rule is unchanged: non-zero when a collision was reported.

**Rationale**:
- (a) duplicates the command's own logic, so the number it produces could disagree with what the real
  command does.
- (b) is impractical at 2.3 TiB.
- (c) measures *the command the operator will run*, and it is also exactly the preview the D-C7 deploy
  step lacked. On a read-only mount it cannot write, and it attempts no write, so it completes cleanly.
  That is the second scenario, and a real test of "attempts no write".

### Tests that hardcode names

**Decision**: Update the tests that assert a literal output name to the prefixed form:
- `test_render.py`: the `output_filename` and `output_relpath` cases, and the year-folder render test.
- `test_cli_output_collisions.py`: its colliding pairs become same-date pairs; the 06-21/06-22 case moves
  to "not a collision".
- `test_cli_adopt_renders.py` and `test_cli_render_staleness.py`: `2024/Party.mp4` becomes
  `2024/2024-06-21 - Party.mp4`.
- `test_scheduler_worker.py`: `2024/Reunion.mp4` and the edited-title pair.

Tests that build paths through `output_relpath(...)` need no edit, which shows the single-rule design
working.

## Failure behavior and idempotency

- **Nothing new raises.**
- **NG-rendered outputs under old names** (dev only) are reported `stale: output` and re-render under the
  new name. The old file is left in place: NG never deletes an output.
- **A dry run** writes nothing, so running it twice gives identical output.
- **A real `adopt-renders` after a dry run** adopts exactly the events the dry run said it would, provided
  the disk did not change in between.
- **`--force`** is unaffected.
- **Worker restart mid-render:** the worker derives the same new path, so no change.
- **No `RENDER_GRAPH_VERSION` bump**, because no rendered bytes change.

## Risks / Trade-offs

- **[`import` doubles the date]** An imported legacy `title: "2025-01-13 - Resa …"` becomes
  `metadata.title`, so the name gets two dates. → The proposal Non-goals say so, and the README tells the
  operator not to `import` before adopting. The next change fixes the mapping. One event on the drive is
  affected.
- **[Long names]** The prefix adds 13 characters, and the longest folder today gives a name of about 83
  characters. → That is well under NTFS's 255-character limit, and legacy already wrote these names to
  this filesystem.
- **[Dev library pair]** `2024-07-14 - Kalas` and `2024-07-15 - Kalas` stop colliding. → The builder
  switches to a same-date, case-differing pair, which a case-sensitive dev filesystem allows.
- **[The acceptance check needs the drive]** → The task is explicitly deferred when the drive is absent,
  and never silently skipped.

## Migration Plan

1. Land the change. No data migration is needed.
2. Operator deploy step, when ready (this change runs only the preview):
   - mount the archive read-only
   - `auto-reel adopt-renders /run/media/emil/MOL/Videos/Sorted -o /run/media/emil/MOL/Videos/Completed-auto-reel --dry-run`
   - read the counts
   - remount read-write only for the real run
3. HLD **D-9** is amended in place (the layout line gains the date prefix, plus a note of the
   correction and its evidence). The README's output-layout and deploy text follows.

Rollback means reverting the two functions and the flag. Outputs rendered under the prefixed names
would then report `stale: output`, and none would be deleted.
