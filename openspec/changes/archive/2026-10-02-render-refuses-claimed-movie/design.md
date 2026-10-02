## Context

On `origin/main` at `6df2680`:

- **Manifest.** `staleness/manifest.py` `RenderManifest.output` is the movie's bare file name (a manifest has
  recorded only the name since `staleness-output-lookup`); `recorded_output_path(recorded, expected_output)`
  places that name in its own date's year folder beside the output directory `expected_output` implies. The
  gate's `_renamed_output` guards the call (`recorded` not in `("", ".", "..")`, and `Path(recorded).name ==
  recorded`) and then checks `is_file()`.
- **Claims.** `render/claims.py` `output_collision(event_dir, *, walk_root, layout, order, today)` walks the layout
  and compares each processable event's *current* `output_relpath`. It reads no manifest. It is called by the
  worker (`_refuse_disk_collision`) and by `api/events_read.py`; the CLI's `_output_collisions` does the same over
  the batch it already holds.
- **Replacing.** `render_movie` replaces an existing regular file when `options.overwrite` is set. `cmd_render`
  (`_build_job`) and `default_build_job` set `overwrite=True` for every event they build, because the gate has
  already decided whether to render; the CLI knows `args.force`, a worker job carries `job.force`.
- **Who has the project's events.** `cmd_render` holds `ctx.events` (the walked `EventRef`s), `ctx.walk_root`
  and `ctx.layout_name`; the worker resolves `project_root`, `config.input_dir` and `config.layout` itself. The
  engine (`render_movie`) knows only `event_dir` and `output_dir`.

## Goals / Non-Goals

**Goals:**
- A render never silently replaces a movie another event's manifest still records, in the CLI or the worker,
  and the refusal names that event and the way past it.
- One rule for what "records this file" means, shared by the gate and the claim check.
- A refused event leaves the disk exactly as it was.

**Non-Goals:** deleting or moving any movie, the prune command, an API 409, a dry-run report, a search across
output directories or projects. See proposal.md, "Non-goals".

## Research & Decisions

### Where the check lives

**Context**: The decision says the refusal applies to the CLI and the worker and "reuses the shared claims
rule". Finding the claimants needs the project's event directories, which the engine's `render_movie` does not
have.
**Explored**: (a) a field on `RenderOptions` that carries the event directories, checked inside `render_movie`
(one enforcement point, but both builders must populate it, so the same two call sites are edited and the
options grow); (b) a helper in `render/claims.py` called from the two existing refusal sites (`cmd_render`
next to `_output_collisions`; `default_build_job` next to `_refuse_disk_collision`).
**Decision**: (b). The helper takes the event directories as an argument, so the CLI passes the `EventRef`s it
already holds and the worker passes the layout walk it already does for the collision rule.
**Rationale**: Both sites already refuse before anything is written, which is exactly when this must happen
(before `prepare_and_persist` adopts a clip, before any probe). No option bag (Principle VII).
**Alternatives**: (a); and a check inside `render_movie` that walks up to guess the project root, which can
silently miss and so fails open (Principle I).

### The claim rule

```python
# staleness/manifest.py
def recorded_movie_path(recorded: str, expected_output: PathLike) -> Optional[Path]:
    """Where a render recorded as ``recorded`` put its movie, beside ``expected_output``; None
    when ``recorded`` is not a bare file name (empty, ``.``, ``..`` or a path)."""

def records_output(event_dir: PathLike, output_path: PathLike) -> bool:
    """True when ``event_dir``'s readable manifest records exactly ``output_path`` as its movie."""

# render/claims.py
@dataclass(frozen=True)
class ClaimedMovie:
    output_path: Path                 # the file the render would replace
    recorded_by: Tuple[Path, ...]     # the other events' directories, sorted by path

def claimed_movie(
    event_dir: Path, output_path: Path, *, events: Iterable[Path]
) -> Optional[ClaimedMovie]: ...

def claimed_movie_message(output_path: Path, claimants: Sequence[str]) -> str: ...
```

`claimed_movie` returns `None` unless `output_path.is_file()` (a render that creates a new file replaces nothing).
Otherwise it reads the manifest of every event in `events` that is not `event_dir` itself (compared lexically,
`os.path.abspath`, as `output_collision` does, never resolving symlinks) and keeps those for which
`records_output` holds. The comparison is the collision rule's: NFC-normalised and case-insensitive, so a
case-insensitive archive filesystem cannot slip a clash through. It does not require the other event to load or
to be processable: its manifest is a record of a file on disk whatever state its `reel.yaml` is in. It does not
require the other event's *current* path to differ: two events whose current paths are equal never get this
far, because `output_collision` (and the CLI's `_output_collisions`) refused them first, and `force` does not
bypass that.

`ClaimedMovieError(EngineError)` in `errors.py` carries `claimed_movie_message`:
`movie <name> is recorded as the output of <event>[, <event>]; rendering would replace it (render with force to
replace it)`. The event names are the CLI's `ref.event_dir.name` and, in the worker, the path relative to
`project_root`, exactly as each surface names a collision's claimants (`_claimant_name` in the worker). One
sentence serves both surfaces.

### Call sites

- **CLI.** In `cmd_render`, after the `_output_collisions` filter and before the build loop, for each remaining
  candidate when neither `args.force` nor `args.dry_run` is set: `claimed_movie(candidate.ref.event_dir,
  output_dir / output_relpath(metadata), events=[ref.event_dir for ref in ctx.events])`. A claimant moves the
  event to the build failures with the message, as a collision does, so it prints `ERROR`, the batch goes on
  and the exit status is non-zero. Fresh events are not checked: they are not rendered.
- **Worker.** In `default_build_job`, immediately after `_refuse_disk_collision` and before
  `prepare_and_persist`, unless `job.force`: the same call with `events` from `get_layout(layout)(walk_root)`.
  A claimant raises `ClaimedMovieError`, which `Worker._process_job` records as the job error. A walk failure
  (`LayoutError`, `OSError`) propagates, as it does for the collision rule: a job must not render when the check
  could not be made (Principle I).

### Time of the check, and a batch

**Context**: In one `render` batch, the renamed event A and the taker B can both be candidates.
**Decision**: Each event is checked against the manifests as they are when the batch is built, before any render
starts. B is refused even though A would re-render under its new name later in the same batch.
**Rationale**: Order inside a batch is not a contract, and a render-time check would need the options bag
rejected above. After A has rendered, a second `render` finds A's manifest naming the new file and B proceeds
unforced. The cost is one extra run, never a lost movie.

### Idempotency and failure

A refused event writes nothing, so a re-run is the same refusal until the cause changes (A re-rendered under its
new name, the file moved away by the operator, or force). A forced render replaces the file as today and writes
B's manifest; A's manifest still records the file, so A's verdict still cites `output_renamed` for what is now
B's movie, and B's next unforced render (when it is stale again) is refused again until A re-renders or force is
used. This is accepted and stated in the spec: the claim holds as long as A's manifest records the file. A worker
restart mid-job re-claims the job and re-runs the check; nothing was written before it.

## Risks / Trade-offs

- **A stale claim blocks a taker repeatedly.** If A is never re-rendered, B needs force each time its movie is
  stale. Mitigation: the refusal names A, and the prune command (separate change) removes the cause.
- **Walk cost.** The worker reads one small JSON per event of the project per replacing job, and only when the
  output file already exists. Cheap beside a render.
- **No enqueue-time signal.** A GUI user learns of the refusal from the failed job's error. Accepted; the 409 is
  a follow-up.
- **Unreadable manifest claims nothing.** A corrupted manifest of A lets B replace A's kept movie. This is the
  manifest module's existing fail-open convention (it evaluates stale, never skips) and the only alternative,
  refusing on any unreadable manifest, would block healthy projects.
- **CLI reconcile precedes the refusal.** `cmd_render` prepares (seeds / adopts) every event before its gate, so
  an event refused for a claim has had its `reel.yaml` reconciled as a collision-refused event has; only the
  worker decides before `prepare_and_persist`. The refusal adds no write.
- **A fresh job can be refused in the worker.** The worker check runs before the fingerprint exists, so a
  non-forced job for an event that is already fresh, whose file a stale claimant still records, fails with the
  refusal instead of completing as a skipped `done`. Enqueue does not create jobs for fresh events (only a race or
  a forced-then-requeued job can), and a forced job is never checked.
