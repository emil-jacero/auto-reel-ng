## Why

A renamed event keeps its previous movie on disk by design (HLD §4.3 output layout, **D-9**; change
`output-renamed-reason`), and the render manifest still records that file as the event's output until the event
renders again. Today a render of *another* event that now has the renamed event's old name replaces that kept
movie without a word, because the output-collision rule compares only the events' *current* paths. Re-checked on
`origin/main` at `6df2680`: `render/claims.py` `output_collision` and the CLI's `_output_collisions` build their
claims from `output_relpath` of each event's metadata and never read a manifest; both `cmd_render` and the worker
render with `overwrite=True`. The data loss is documented as an exception (`staleness/gate.py` docstring,
`openspec/specs/change-detection` "A renamed event keeps its previous movie", HLD §4.3), but it is silent: the
renamed event's verdict keeps citing `output_renamed` for a file that is now someone else's movie (Principle I,
fail loud; Principle IV, a file at the output path means one event's verified render).

**USER DECISION (2026-10-02), bug round "Add prune command" incl. the guard:** a render refuses to overwrite a
file another event's manifest records unless forced. The engine still never deletes a movie on its own. The
`prune-renamed` command of that decision is a separate change; this one is the guard only.

This belongs to the 2026-10-02 bug round after HLD §6 phase 8; it depends on no open §8 research item.

## What Changes

- **A shared claim rule** (`render/claims.py`, new `claimed_movie`): given the path a render would write, the
  event being rendered and the project's event directories, it answers which *other* events' render manifests
  record exactly that file as their output. The manifest side (is this recorded name this path?) is one small
  function in `staleness/manifest.py`, which the gate's `output_renamed` lookup reuses so the two cannot
  disagree on what a recorded name means. Read-only; an unreadable manifest claims nothing (the manifest's own
  fail-open convention).
- **The refusal.** Before a non-dry-run render of an event replaces a regular file at its output path, and unless
  forced, `auto-reel render` and the worker refuse when `claimed_movie` finds a claimant. The event fails with a
  typed error (new `ClaimedMovieError`, an `EngineError`) that names the file and the other event(s) and says
  `--force` replaces it. Nothing is rendered, probed or written for it: no `.part`, no manifest, no adopted clip.
  The other events of a batch are unaffected. `--force` (CLI) and a job's `force` (worker) skip the check.
- **Spec.** The third "a render still replaces" case of "A renamed event keeps its previous movie" becomes a
  refusal; "Output naming and overwrite control" says the overwrite is subject to it; one new requirement states
  the rule.
- **Tests** alongside each piece; the worker test is `requires_db`.
- **HLD:** one amendment line on D-9; the `staleness/gate.py` docstring sentence that describes the replacement.

## Non-goals

- **No deletion and no `prune-renamed`.** The engine never removes a movie; the operator command that lists and
  deletes superseded old-named movies is a separate change.
- **No change to `POST /api/v1/jobs`.** Enqueue keeps its checks; a job for such an event is accepted and then
  fails at the worker with the refusal text as its job error. A typed 409 at enqueue would add an
  `EnqueueConflict` value and a client change (`api/` and `web/`), which this change does not carry.
- **No change to the output-collision rule.** Two events whose *current* paths are equal stay the unbypassable
  `output_collision` refusal (D-9); this rule is about a *recorded*, no-longer-current path and is bypassed by
  force.
- **No dry-run diagnostics.** `render --dry-run` still builds and reports commands and checks nothing on disk.
- **No cross-project or cross-output-directory search:** only events of the project's own layout walk are read,
  and only a movie in the output directory in use can match.
- **No manifest schema change.** The manifest already records the movie's bare file name.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-detection`: "A renamed event keeps its previous movie" (the third replacement case becomes a refusal
  unless forced) and a new requirement "A render refuses to replace a movie another event records".
- `movie-assembly`: "Output naming and overwrite control" (the overwrite is subject to that refusal).

## Impact

- **Baseline:** designed against `origin/main` at `6df2680`.
- **Packages:** logic in `render/` and `staleness/`; the call sites are one block each in `cli/` (`cmd_render`)
  and `scheduler/` (`default_build_job`), plus one exception class in `errors.py`. Four packages are touched
  although only two carry logic; the call sites cannot be avoided because the project's event list exists only
  there (design, "Where the check lives"). Files: `staleness/manifest.py`, `staleness/gate.py`, `render/claims.py`,
  `errors.py`, `cli/commands.py`, `scheduler/worker.py`, `docs/high-level-design.md` and their tests.
- **CLI vs API (Principle V):** the rule is engine code; the CLI and the worker (so, jobs created through the API)
  both reach it. Nothing is added to `api/`.
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump**, and the staleness
  fingerprint inputs and gate verdicts are unchanged. A refused event writes no output, manifest or `.part`.
- **Schemas:** no `reel.yaml`, `config.yaml` or manifest change, **no Alembic migration**, no rescan, no OpenAPI
  or `web/` change.
- **Complexity (Principle VII):** one function per package, one exception class, no config key, no dependency.
- **Size (Principle VIII):** two capability deltas, 10 tasks (one docs, one validation).
