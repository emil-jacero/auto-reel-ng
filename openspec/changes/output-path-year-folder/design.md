## Context

Eight call sites each build an event's output path as `output_dir / output_filename(metadata)`:

| Package | Site | Purpose |
|---|---|---|
| `render/` | `orchestrator.py` `render_movie` | the path the movie is finalized to |
| `cli/` | `commands.py` `_staleness_filter` | gate for `render` |
| `cli/` | `commands.py` `cmd_scan` | gate for `scan` (read-only) |
| `cli/` | `commands.py` `cmd_enqueue` | gate for `enqueue` |
| `cli/` | `commands.py` `cmd_adopt_renders` | "does an output exist to adopt?" |
| `scheduler/` | `worker.py` claim-time recheck | gate for the worker |
| `api/` | `events_read.py` `staleness_for` | list/detail verdicts |
| `api/` | `routes/jobs.py` | gate for `POST /jobs` |

`output_filename` returns a bare name (`orchestrator.py:110`). Nothing checks whether two events map to
the same name. `_execute` creates `options.output_dir` and writes `.part` next to the final path, so the
atomic rename relies on `.part` and the final file sharing a directory. The render manifest records
`output_path.name`, and the gate never reads that field: `evaluate()` checks
`Path(output_path).exists()` on the path it is handed. See proposal.md for why this matters.

## Goals / Non-Goals

**Goals:**

- One function owns the output-path rule, and every site above calls it.
- Colliding events are refused before any side effect: no render, no job row, no manifest.
- The existing atomic-finalize and staleness guarantees hold unchanged inside year folders.

**Non-Goals:**

- The collision check does not reach the API or the worker (proposal: Non-goals).
- No change to the manifest, the fingerprint, or `RENDER_GRAPH_VERSION`.

## Research & Decisions

### Legacy output layout

**Context**: The spec says the naming is "carried over from auto-reel". We needed to know what was
actually carried over, because `adopt-renders` must find the legacy archive's files.

**Explored**: `auto-reel/movie_merge/project/processor.py:199-205` builds
`self.config.output_path / str(movie.metadata.year) / filename`, with `filename` =
`f"{movie.title} - {location}.mp4"` or `f"{movie.title}.mp4"`. In `config/directory.py:32-34`, `year`
is `str(self.date.year) if self.date else ""`, so an undated event lands at the output root.

**Decision**: Reproduce that layout exactly: `<YYYY>/<name>`, or `<name>` when the date is absent.

**Rationale**: This is the only layout under which `adopt-renders` finds the existing archive's outputs
(D-C7). Any other scheme (date prefix, event-folder mirror) turns deployment into a full-archive
re-render.

### Reproducing the collision

**Context**: We needed to confirm that the flat namespace fails silently, not loudly.

**Explored**: A dogfood run on 2026-09-26 over a scratch project (clips symlinked from
`auto-reel-media`). Events `2023/2023-06-23 - Midsommar` and `2024/2024-06-21 - Midsommar` both
rendered `OK` to `out/Midsommar.mp4`. A second `render` reported both as `FRESH`, and
`scan -o out` reported both as `fresh`. The 2023 movie no longer exists anywhere.

**Decision**: Fail loud on collision (D-O2) in addition to the year folder (D-O1).

**Rationale**: The year folder removes cross-year collisions, but same-year collisions (two
"Kalas" events in one year) still fail silently. Only a check removes silent loss.

## Decisions

### D-O1 — One path function, in `render/`

```python
# auto_reel_ng/render/orchestrator.py
def output_filename(metadata: Metadata) -> str:          # unchanged
    """``<title> - <location>.mp4`` (location omitted when absent)."""

def output_relpath(metadata: Metadata) -> PurePosixPath:
    """The output path relative to the output directory (legacy layout).

    ``<YYYY>/<output_filename>`` when ``metadata.date`` is set, else the bare
    filename at the root. The year is never inferred from anything else.
    """
    name = output_filename(metadata)
    if metadata.date is None:
        return PurePosixPath(name)
    return PurePosixPath(f"{metadata.date.year:04d}") / name
```

All eight sites change from `output_dir / output_filename(md)` to `output_dir / output_relpath(md)`.
`output_relpath` is exported from `auto_reel_ng.render` next to `output_filename`.

- *Why `render/`:* the rule describes where the engine finalizes a movie, and `cli/`, `scheduler/`
  and `api/` already import `output_filename` from `render/`. Placing it there adds no new layer edge
  (Principle VI).
- *Why return a relative path rather than take `output_dir`:* call sites already hold their own
  `output_dir` (CLI context, worker options, API settings). A relative path is also the natural key
  for comparing collisions.
- *Alternative rejected: infer the year from the layout's `<year>/` folder.* The `flat` layout has
  no such folder, and legacy used the metadata date. Using the date keeps one rule for every layout.

### D-O2 — Collision detection is a pure engine function; the CLI enforces it

```python
def find_output_collisions(
    claims: Mapping[K, PurePosixPath],
) -> dict[K, tuple[K, ...]]:
    """Map each key whose output path is shared to the other keys claiming it.

    Paths compare by ``unicodedata.normalize("NFC", str(p)).casefold()``; keys not
    in any collision are absent from the result. Pure: no filesystem access.
    """
```

`K` is whatever identifies an event at the call site. The CLI uses the `EventRef` event directory.

- **`render`**: `_staleness_filter` already prepares every selected event and returns
  `(stale, fresh)` candidates. `cmd_render` builds claims from **both** lists (a fresh event owns its
  output and must be protected from a new sibling), removes every colliding candidate from both, and
  appends one entry per colliding event to the existing `build_failures` list. `_report_render`
  prints that list as `ERROR` lines and counts it toward the non-zero exit. No new reporting path is
  added.

  ```
  ERROR  2024-06-22 - Midsommar: output path 2024/Midsommar.mp4 is also claimed by 2024-06-21 - Midsommar; set a distinct title or location in reel.yaml
  ```

  The check runs before `_build_job`, so a colliding event is never probed, planned or rendered, in
  dry-run as well. `--force` changes only the gate, and the collision check sits outside the gate.
- **`enqueue`** and **`adopt-renders`**: each iterates `ctx.events` in a single loop today. Each
  gains a first pass that loads the document (`load_or_seed`, which is read-only and probe-free,
  exactly as the loop does now) and records `output_relpath`. It calls `find_output_collisions`,
  prints `ERROR` lines for the colliding events, then runs the existing loop over the rest. Both
  commands return `1` when any collision was reported (today `enqueue` always returns `0`).
- **Comparison key**: NFC then `casefold()`. The archive drive's filesystem is not known here (see
  Risks). A case-insensitive target would otherwise let `Midsommar.mp4` and `midsommar.mp4`
  overwrite each other while this check reported no collision. The key only ever *adds* collisions,
  so its false positives are the safe direction (for example `Groß` vs `Gross` under `casefold`).
- *Alternative rejected: auto-suffix (`Midsommar (2).mp4`).* The suffix depends on scan order, so
  adding an event can rename another event's existing output. Its staleness verdict flips to
  `output`, and the archive churns.
- *Alternative rejected: check inside `render_batch`.* `render_batch` sees only the jobs being
  rendered, not the fresh events whose outputs they would overwrite, and `enqueue` and
  `adopt-renders` never reach it.

### D-O3 — Finalize creates the output's own directory

In `_execute`, `Path(options.output_dir).mkdir(parents=True, exist_ok=True)` becomes
`output_path.parent.mkdir(parents=True, exist_ok=True)`. `_part_path` already derives `.part` from
`output_path`, so `.part` lands in the year folder and `os.replace` stays a same-directory,
same-filesystem rename. `_plan_only` (dry-run) returns before `_execute` and creates nothing.

### D-O4 — Default output directory is a sibling of the project root

Implementation surfaced a regression. The default output directory was `<root>/output`, and
`year_event_layout` treats **every** subfolder of the walk root as a year: it has no digit check.
Before this change `<root>/output` held only files, so it yielded no events. With year folders,
`<root>/output/2024/` is walked as the event `2024`, whose "clips" are rendered movies. The `flat`
layout already walks `<root>/output` itself as an event.

Decision (operator's choice, 2026-09-26): with no `-o` and no `config.yaml` `output`, the default
becomes `<root.parent>/<root.name>-output`.

```python
# auto_reel_ng/config/project.py
def default_output_dir(project_root: Path) -> Path:
    """``<parent>/<root-name>-output``: outside the walk, so outputs are never scanned."""
    return project_root.parent / f"{project_root.name}-output"
```

The three places that hard-code `project_root / "output"` call it: `cli/commands.py`
`_project_context`, `api/settings.py`, and `scheduler/worker.py`. The `-o` help text is updated to
match.

- *Alternative rejected: exclude events under the output folder at the walk sites.* Considered, and
  it would also cover a configured output inside the root. The operator chose the default move
  instead.
- *Alternative rejected: require 4-digit year folders.* That changes the layout's contract and leaves
  the `flat` layout's version of the bug in place.

### Failure behavior and idempotency

- **Collision:** reported per event as `ERROR`, with non-zero exit. No file, job row or manifest is
  written for either side. An existing output at the shared path is untouched.
- **Undated event:** not an error. It renders at the output root, as legacy did.
- **Re-run:** the same paths are computed, so fresh events stay fresh and collisions are re-reported
  until the operator edits `reel.yaml`.
- **`--force`:** bypasses staleness only. Collisions are still refused.
- **Worker restart mid-render:** unchanged. The requeued job recomputes the same year-folder path,
  and the claim-time recheck uses it.

### HLD fold-back

The output layout outlives this change, so it is recorded in `docs/high-level-design.md` as **D-9 —
Output layout** in §7, with a one-line pointer from §4.3: `<output>/<YYYY>/<title>[ - <location>].mp4`,
undated at the root, and collisions refused by the batch commands.

## Risks / Trade-offs

- **[The real archive may not match the legacy code's layout]** The MOL drive was not mounted while
  this was designed, so the layout comes from legacy source, not from inspecting the archive. →
  `adopt-renders` reports every event whose output it cannot find as `unrendered`. Run it before
  `render` and read the unrendered count. A large count means stop and check, not render.
- **[Legacy title casing vs NG seeding]** Adoption finds an output only if NG's `metadata.title`
  matches the name legacy wrote. Events carrying a legacy `reel.yaml` title are imported verbatim.
  Folder-seeded titles go through NG's title-casing, whose parity with legacy `format_title_case` is
  not re-verified here. → Same mitigation: the mismatch shows up as `unrendered`, not as a silent
  re-render.
- **[Selection-scoped check]** `render --years 2024` does not see a 2023-folder event whose date is
  in 2024. → That event's date and folder disagree, which is already an editorial inconsistency. The
  unscoped `render` catches it. The risk is documented in the spec rather than fixed with a
  whole-library walk on every scoped run.
- **[API/worker path unchecked]** `POST /api/v1/jobs` can still enqueue one side of a same-year
  collision. → No GUI drives that path yet. A follow-up adds the check there once it is used
  (proposal: Non-goals).
- **[Explicit output inside the root is still scanned]** `-o <root>/out` or `config.yaml`
  `output: out` (with no `input`) puts year folders back under the walk. → The spec states that an
  explicit output is honored as given. README warns against pointing output inside the walked root.
  A follow-up can add a fail-loud check.
- **[Behavior change for scripts]** A batch with a collision now exits `1` where it used to exit `0`.
  → This is intended: the old `0` was false.

## Migration Plan

1. Land the change. Existing auto-reel-ng outputs in a flat layout (dev scratch only) evaluate
   `stale: output` and re-render into year folders on the next `render`.
2. For the legacy archive, run `auto-reel adopt-renders <root> -o <legacy-output-root>`. It now
   resolves `<year>/<name>.mp4`. Check its `unrendered` count before the first library-wide `render`.
3. Rollback: revert the commit. Year-folder outputs then evaluate `stale: output` under the flat rule
   and would re-render flat. No output is deleted either way.
