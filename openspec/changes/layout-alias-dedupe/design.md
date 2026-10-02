## Context

`year_event_layout` and `flat_layout` build rows with `_subdirs` (`iterdir()` + `is_dir()`, which
follows symlinks) and hand them to `_event_refs`, which only skips `.reelignore` events. Every
consumer (CLI `_project_context`, API `_list_event_refs` / `named_event_dir`, worker rebuild)
iterates the layout, so duplicates reach `prepare_event` + `persist`, which write
`<event_dir>/reel.yaml`; through a symlink that is the target's file. Evidence re-checked against
main `6a7fe16`: `layouts.py` has no `resolve()`/`samefile` anywhere; `cli/commands.py`
`_output_collisions` only refuses *after* the seed in one process, and `scheduler/worker.py`
has no such check. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:** one row per real directory for every consumer, decided in one place, deterministic,
visible in the log, no write ever reaching a target through an alias.

**Non-Goals:** see proposal.md. Additionally, no new public symbol: the helper is private to
`layouts.py` and `EventRef` is unchanged.

## Research & Decisions

### Where to dedupe
**Context**: the triage listed two fixes, a per-event ERROR (`_checked_document` /
`_staleness_filter`) or a write-time refusal in `persist`.
**Explored**: `cmd_scan`, `_staleness_filter`, `render_batch`, `scheduler/worker.py`,
`api/events_read.py`: five call sites would each need the new failure; the worker and API have no
`_checked_document` equivalent.
**Decision**: dedupe in the layouts' shared row builder, drop aliases, log a WARNING.
**Rationale**: one edit covers every consumer (Principle V: engine first; VI: the layout owns
"what is an event"; VII: no new failure type). The alias is not lost information, it is the same
directory under a second name; the WARNING keeps it fail-loud rather than silent. A write-time
guard was rejected because it leaves the alias listed as an event that can never be rendered.

### Which path wins
**Context**: the kept name becomes the event's identity (folder-name hint, output name, event id).
**Decision**: a row is *canonical* when `row.resolve() == root.resolve() / <row relative to
root>`, i.e. reaching it crossed no symlink (this also handles a symlinked year directory and a
root that itself sits behind a symlink such as `/var/home -> /home`). Among rows with the same
`resolve()`, the first canonical row wins; if none is canonical (target outside the walk, or two
symlinks), the first in walk order wins. Surviving rows keep walk order.
**Rationale**: the real directory is never the alias, whatever its name sorts as (`Fest` sorts
before `Kalas`, which is what made the bug write the alias name). A deterministic rule keeps ids
stable between runs.

### Scope of the comparison
**Decision**: dedupe over the whole walk, *before* the `year-event` year filter, after the
`.reelignore` skip. An alias in `2025/` of a target in `2024/` is therefore found even with
`--year 2025`; the target is outside the filter, so that run yields neither, and the WARNING
explains why. `.reelignore` first means an ignored target and its aliases are all just skipped
(each logged by the existing INFO line) with no extra alias warning.
**Trade-off**: the year-event walk now lists every year directory even when filtered (directory
listing only, no clip access; layouts still never open clips).

```python
def _dedupe_aliases(root: Path, rows: list[Path]) -> list[Path]: ...
# groups rows by row.resolve(); keeps one per group per the rule above;
# logger.warning("skipping %s: alias of %s (-> %s)", alias, kept, target) for each dropped row
```

`year_event_layout` builds `rows` for all years, calls `_dedupe_aliases`, then applies the year
filter to the survivors; `flat_layout` calls it on its single level. As built, the helper is
`_walk_dirs(root, rows)`: it also owns the `.reelignore` skip (moved out of `_event_refs`, which now
only maps already-filtered rows to refs) so the skip runs before the alias comparison.

## Failure behaviour and idempotency

- Nothing raises: `resolve()` on a dangling symlink is non-strict, and `is_dir()` already
  excluded dangling links from `_subdirs`. A symlink loop makes `is_dir()` false, so it is never a
  row.
- Nothing is written by the walk. A library already corrupted by this bug keeps its bad
  `title:` in `Kalas/reel.yaml` until the user fixes it; this change does not rewrite it.
- Re-running, `--force`, and a worker restart all re-walk and get the same single row; the
  fingerprint and manifests are keyed by the kept directory and are unchanged.

## Risks / Trade-offs

- [A user relied on the alias name for the output file name] -> the WARNING names the kept path;
  rename the real folder instead of symlinking it.
- [Pairs of symlinks to an outside target pick the first by name] -> deterministic, logged.
- [Full-walk listing under a year filter] -> negligible cost, directory entries only.
