## Context

See proposal.md, "Why". The code on `origin/main` at `6df2680`:

- **`staleness/manifest.py`** `write_manifest(event_dir, fingerprint, *, output, engine_identity)` builds a new
  payload each time and overwrites `render-manifest.json`; `RenderManifest` has `fingerprint`, `components`,
  `output` (a bare file name), `engine_identity`, `written_at`. `read_manifest` returns `None` for anything
  unreadable and never raises. It has two callers: `render/orchestrator.py` after the atomic finalize and
  `cli/commands.py` `cmd_adopt_renders`. `recorded_output_path(recorded, expected_output)` maps a recorded name
  to its D-9 path using the event's expected path only to learn `<output>`.
- **`staleness/gate.py`** treats the recorded name as a movie only when it is a bare file name
  (`_NOT_A_FILE_NAME`, `Path(recorded).name == recorded`) and `is_file()`; this change applies the same test.
- **`cli/context.py`** `project_context(args)` resolves root, config, layout, walk root and output directory,
  refuses an output inside the walked root, and enumerates `ctx.events` (filtered by `--years`).
  `get_layout(name)(walk_root, years)` enumerates all events when `years` is `None`.
- **`cli/commands.py`** `_checked_document` / `_checked_documents` give each event's document or a failure
  reason (`event/claims.checked_claim`); `output_relpath(metadata)` gives an event's expected path under the
  output directory; `find_output_collisions` compares paths case-insensitively and NFC-normalised.
- **The gate, `render-refuses-claimed-movie`** (decision of 2026-10-02, merged first) adds to the shared
  claims rule (`render/claims.py`) a lookup answering "does another event's render manifest record this exact
  file as its output?", used by `render` and the worker before a render replaces an existing file. This
  design was written before it merged; it uses that lookup by role and task 1.1 confirms its name and signature.

## Goals / Non-Goals

**Goals:**
- An operator can see, and with one explicit flag remove, the movies that renames left behind, without
  working out by hand which ones are superseded.
- The engine stays non-destructive: nothing deletes unless the operator ran `prune-renamed --yes`.
- A file that is, or is about to be, another event's movie is never removed.

**Non-Goals:** automatic deletion, an API or GUI surface, manifest cleanup, recovering names superseded before
this change, a race guard against a concurrent render. See proposal.md, "Non-goals".

## Research & Decisions

### The manifest has to remember old names (`superseded`)

**Context**: The user's wording is "lists movies recorded in a manifest under an old name whose event has
since re-rendered successfully under its new name". After that re-render the manifest holds only the new name,
so there is nothing to list.
**Explored**: (a) scanning the output directory for files that look like an event's old title: guesses, and
Principle I forbids guessing; (b) a separate ledger file in the output directory: a second source of truth
with its own failure modes, and an output directory can be shared by projects; (c) a list in the manifest
that already is the sole record of the last render (D-C2).
**Decision**: (c). `write_manifest` reads the previous manifest and writes `superseded` as the previous
`superseded` plus the previous `output` when it differs from the new one, de-duplicated, minus the new
`output`. In outline:

```python
previous = read_manifest(event_dir)
superseded = [*previous.superseded, previous.output] if previous else []
superseded = [n for n in dict.fromkeys(superseded) if n != output]
payload["superseded"] = superseded
```

`RenderManifest` gains `superseded: Tuple[str, ...] = ()` (a default, so existing constructions in tests and
callers are unaffected). `read_manifest` returns `()` for an absent field and for a value that is not a list
of strings, without making the manifest unreadable (the fields that decide staleness are unchanged, so
tolerance here cannot turn a stale event fresh). The schema version stays 1: bumping it would make every
existing manifest read as absent and re-render the whole archive.
**Rationale**: The manifest is already written exactly when a name change becomes real, only after verify, and
the list follows it atomically in the same file. The list is not a fingerprint component, so no verdict and no
`RENDER_GRAPH_VERSION` changes.
**Alternatives**: scanning (guessing); a ledger (second source of truth); keeping the full history with
timestamps (YAGNI, nothing reads it).

### The old movie's path comes from the output directory alone

**Context**: To locate a recorded name the planner needs the D-9 path (`<output>/<YYYY>/<name>` or
`<output>/<name>`). `recorded_output_path` derives `<output>` from an event's current expected path, which a
planner would have to compute by loading every event's document, and an event that fails to load would lose its
prune.
**Decision**: Add `recorded_output_in(recorded: str, output_dir: PathLike) -> Path` in `staleness/manifest.py`:
the year folder of a dated name, else `output_dir` itself. Rebuild `recorded_output_path` on it (derive
`output_dir` from `expected_output`, then call it), so there is one rule. Export it from `staleness/__init__.py`.
**Rationale**: The planner needs no document, so an event that currently fails to load (a half-edited
`reel.yaml`) still gets its old movies pruned, and the planner can never disagree with the gate about where a
recorded name lives. Pure; no filesystem access.
**Alternatives**: calling `recorded_output_path` with a dummy expected path (works by accident, hides intent).

### Which events are superseded, and what "verified" means

**Decision**: An event contributes candidates only when its manifest is readable and
`recorded_output_in(manifest.output, output_dir)` is an existing regular file (`is_file()`, symlinks followed
by the same test the gate uses for a movie; a folder is not a movie). The manifest's `output` is by definition
the last *successful* render's movie, so "the event has re-rendered under its new name" is exactly "the
manifest records a current movie that exists". The planner does not require that `output` equals the event's
*expected* name: an event renamed twice since (A to B rendered, then retitled to C, not rendered) still owns B,
and A is still superseded. An event retitled but never re-rendered has `output` = the old movie and an
empty list, so nothing is offered and its movie is protected. A render into another `-o` directory leaves
the file missing in this one, so nothing is offered for the output directory in use, as with the gate.
**Rationale**: No document load, no fingerprint, no ffprobe, no ffmpeg; the check is the one the user asked
for.

### Claims: what protects a file

**Context**: A candidate file may be the current movie of another event (the takeover case this bug was
filed for), or about to be (an unrendered event whose expected path it is).
**Decision**: The planner walks **all** events of the layout (`get_layout(ctx.layout_name)(ctx.walk_root, None)`),
not `ctx.events`, because an owner outside `--years` must still protect a file. It builds two sets, keyed by the
output-collision comparison key (casefolded, NFC): (1) every event's current movie path from the manifest
(`recorded_output_in(manifest.output, output_dir)`); (2) every loadable event's expected path
(`output_dir / output_relpath(document.metadata)`, using `_checked_documents`; a failing event claims
nothing, as in "Batch commands refuse colliding output paths"). A candidate is dropped when it is in either set
for an event other than its own, and dropped when its key equals its own event's current movie key, or
`os.path.samefile` says it is the same file as the current movie (a case-only rename on a case-insensitive
mount). Set (1) is the gate's lookup: where `render/claims.py` exposes it by a name that takes a file and the
walked events, the planner calls it instead of rebuilding set (1); the baseline task decides. Set (2) is
this command's own (the gate guards a render replacing a file; prune must also not delete a file a pending
render will own).
**Rationale**: One rule for "another event's manifest records this file", shared with the render guard
(Principle V, no duplicated rule). A pending takeover is a claim too: deleting its target would only be undone
by the render, but the operator sees one consistent answer ("someone claims it").
**Alternatives**: protecting only manifest claims (misses the pending takeover); treating another event's
`superseded` list as a claim (two events that both left a name behind would protect it forever).

### Path safety

**Decision**: Before a candidate is listed, all of: the recorded name is a bare file name and not in
`("", ".", "..")` (the gate's test); the path `recorded_output_in` gives is `lstat`-ed and is a regular file
that is not a symbolic link (`stat.S_ISREG(lstat.st_mode)`); and its parent, resolved with `Path.resolve()`,
lies inside the resolved output directory (`Path.is_relative_to`). A year folder that is a symlink to a
directory elsewhere therefore fails the containment check, whatever the manifest says. A failed `lstat` (gone,
unreadable) lists nothing and reports nothing: a file that is already gone is not an error. The delete re-checks
the same conditions immediately before `unlink` (a cheap TOCTOU narrowing, not a race guard).
**Rationale**: The manifest is a user-writable file in the event folder; the command must not turn a
hand-edited or corrupt entry into a deletion outside the archive.

### The command's shape

**Decision**: A new module `cli/prune.py` holds a pure planner and the command, so `commands.py` (932 lines)
does not grow and the planner is testable without argparse:

```python
@dataclass(frozen=True)
class PruneCandidate:
    event_dir: Path
    path: Path          # the superseded movie
    replaced_by: Path   # the event's current movie

def plan_prune(events, all_events, output_dir, expected) -> list[PruneCandidate]: ...
def cmd_prune_renamed(args) -> int: ...
```

`main.py` registers `prune-renamed` with `_add_common_args(prune, output=True)` and `--yes`
(`store_true`; help: "delete the listed movies; without it the run only lists them"). Output, one line per file:

```
-  2024/2024-06-27 - Grillning med Grannar.mp4  (event 2024-06-27 - Grillning med grannar; now 2024/2024-06-27 - Grillkväll med grannarna.mp4)
```

with paths relative to the output directory, `-` marking a candidate in a dry run and `x` a deleted file,
`ERROR  <path>: <strerror>` for a failed delete, and a final line `N superseded movie(s) (dry run: nothing
deleted; pass --yes)` or `N deleted, M failed`. Candidates are sorted by path for a stable output. Exit codes:
0 for a clean run (including "nothing to prune" and a dry run with candidates), 1 when any delete failed or the
layout walk failed. `--yes` is not a prompt: no interactive confirmation, so scripts and tests behave the same.
A zero-event project prints the same "No events found" line the other commands print and exits 0.
**Rationale**: The same listing in both modes, so the dry run is a faithful preview (as `adopt-renders
--dry-run`).
**Alternatives**: a `--dry-run` flag with delete as the default (the opposite of the user's decision; a
forgotten flag deletes); an interactive prompt (breaks non-tty use); extending `scan` (a read-only report
should not be able to delete).

## Risks / Trade-offs

- **Entries before this change are not known.** Mitigated by saying so in the README; the next rename of each
  event starts its list. Accepted: guessing would be worse.
- **A hand-edited manifest** can list any bare name in the output folder as superseded. The containment and
  claim checks keep the damage to a regular file in the event's own year folder that no other event claims, and
  the default is a dry run.
- **`superseded` grows** by one short string per rename. No cap; nothing renames hundreds of times.
- **The gate's lookup may differ in shape** from what is assumed above. The planner's two sets are ordinary
  functions over the walk; if the gate's helper cannot be called with the planner's inputs, the planner keeps
  its own set (1) and the baseline task records why, rather than editing the gate's code.

## Failure behaviour, idempotency

- **Raises / reports:** a layout failure (`LayoutError`, `OSError`) ends the command before any delete with the
  reason and exit 1; an `OSError` from `unlink` is reported per file and the run continues (exit 1). Nothing
  else is raised to the caller.
- **Idempotent:** a second run lists nothing for the deleted files (they are gone); an interrupted run leaves
  a prefix of the files deleted and the rest listed next time. It writes no file, so there is nothing to
  clean up.
