## Context

See proposal.md for the motivation. Current state, re-checked on main `6a7fe16`:

- `cli/commands.py:76-122` defines `ProjectContext` and `_project_context(args)`. It resolves the
  root (`Path(args.root).resolve()`, else cwd; `FileNotFoundError` if not a directory), loads
  `config.yaml`, derives `walk_root` (`project_root / input_dir`, else the root), then the output
  directory: `-o` as given (relative to cwd), else `project_root / config.output_dir`, else
  `default_output_dir(project_root)`. It never compares the output with `walk_root`.
- `commands._resolve_project_root` (line 583) repeats the root check for `worker`, `jobs`,
  `serve` and `adopt-renders`-style callers.
- `api/settings.py` `resolve_api_settings` repeats the walk-root and output derivation (without
  `-o`; the service has no output flag) and also never compares them. It does not resolve
  `project_root` (it keeps the path it was given).
- `cli/thumbnails.py:38` imports `commands._project_context`. `commands.py` is 995 lines;
  pylint's `max-module-lines` is the default 1000.
- `cli/main.py::main` already turns `EngineError` (which `ConfigError` is) and
  `FileNotFoundError` into `error: …` on stderr and exit 1, so no new plumbing is needed.
- Six `commands.py` callers use `_project_context`: `scan`, `render`, `analyze`, `import`,
  `enqueue`, `adopt-renders`; `thumbs` is the seventh. `serve` uses `resolve_api_settings`.
- `scheduler/worker.default_build_job` resolves its own output dir per claimed job.

## Goals / Non-Goals

**Goals:**
- One helper decides "is this output usable with this walked root" and both the CLI and the API
  settings call it, so they cannot disagree.
- `cli/context.py` is the public home of the project context; nothing imports a private name
  across modules.
- The failure is typed, early (before any walk, probe, write or DB access) and names the fix.

**Non-Goals:**
- No change to `default_output_dir` or to how `-o`, `output` and `input` are layered.
- No change to the worker, the layouts, or any `reel.yaml` behaviour.

## Decisions

### D-1: Where the move lands, and what moves

`ProjectContext`, `resolve_project_root` (from `_resolve_project_root`) and `project_context`
(from `_project_context`) move to `auto_reel_ng/cli/context.py` unchanged in behaviour apart from
the new check. `project_context` calls `resolve_project_root` instead of repeating its first six
lines. `commands.py` imports them (`from .context import ProjectContext, project_context,
resolve_project_root`); `thumbnails.py` imports `project_context` from `.context`.

*Alternatives:* leave the dataclass in `commands.py` and only expose a public alias (rejected:
leaves the file at the pylint cap and the import direction `thumbnails -> commands` intact);
move it to `config/` (rejected: it enumerates events via `ingest`, a higher layer than `config`,
Principle VI). `cli/context.py` imports only `argparse`, `config`, `ingest` and the `api.settings`
helper, none of which import `cli`, so there is no cycle. Tests that patch
`commands._project_context` (`tests/test_cli_commands.py:180,193`) call `context.project_context`
instead; the other commands read it through `commands`, so monkeypatching `commands.project_context`
keeps working for those.

### D-2: The rule: equal or inside is refused; containing is allowed

```python
# api/settings.py
def require_output_outside_walk_root(
    output_dir: Path, walk_root: Path, project_root: Optional[Path] = None
) -> None:
    """Raise ConfigError when output_dir is walk_root or inside it."""
    out, walk = output_dir.resolve(), walk_root.resolve()
    if out == walk or walk in out.parents:
        raise ConfigError(
            f"output directory {output_dir} is inside the walked root {walk_root}; "
            f"choose a folder outside it, for example {default_output_dir(project_root or walk_root)}"
        )
```

Both paths are resolved (symlinks, `..`, relative `-o`) for the comparison only; the stored
`output_dir` and `walk_root` values are left as the caller built them, so every downstream path
and test expectation is unchanged. `Path.resolve()` is non-strict, so a not-yet-created output
directory is fine. The message names both paths as the user wrote them and suggests the sibling
`default_output_dir(project_root)`; the optional `project_root` argument (defaulting to `walk_root`) keeps that suggestion right when `input` is set. `walk_root` is the root the layout walks (`project_root /
input` when `config.yaml` sets `input`), not the project root: `input: media` with `output: out`
keeps `out/` outside the walked tree and stays valid.

The triage sketch also rejected an output that *contains* the walked root. Re-checking against
the code, that case does not produce the failure: movies are written to
`<output>/<YYYY>/<name>.mp4`, and a layout only reads below `walk_root`, so a containing output
is scanned back only if `walk_root` itself equals `<output>/<YYYY>`. Meanwhile `input: media`
with `output: .` (a library whose project root also holds the movies) works today and would
break. The rule therefore stays minimal: equal or inside. Should the narrow `walk_root ==
<output>/<YYYY>` case matter, it is not worth a second rule (Principle VII).

*Alternatives:* a `--allow-output-inside-root` escape hatch (rejected: no real use, and the spec
calls out no legitimate such layout); return a bool and let each caller raise (rejected: two
messages for one rule).

### D-3: Host in `api/settings.py`, raise `ConfigError`

The helper must be callable from `cli/` and `api/` and the package budget is two. `cli` already
imports `api.settings` (`resolve_api_settings`), while `api` must not import `cli`, so the helper
lives in `api/settings.py` next to its second caller and `cli/context.py` imports it. It raises
`config.project.ConfigError`, the typed error `api/settings.py` already uses for a bad
configuration and that `main()` already maps to `error: … ` and exit 1. The `-o` flag is not
`config.yaml`, but one error type for "the combination of settings is unusable" keeps the CLI
and `serve` output identical.

*Alternative:* `config/project.py`, the more natural layer. Rejected only to hold the
two-package limit; it moves there in a one-line change if a third caller appears.

### D-4: Call sites and ordering

`project_context` checks right after the output directory is chosen, before `get_layout(...)` and
before enumerating events, so a refused invocation walks nothing and opens no database.
`resolve_api_settings` checks right after computing `output_dir`, so `serve` fails during
settings resolution, before `create_app` and the bind. Every command that builds a context is
covered, including `thumbs` and `scan`, which do not write movies: they would list the same
bogus events, so one uniform refusal is simpler and safer than per-command exceptions. `worker`
and `jobs` resolve only the root and are unaffected.

`scheduler/worker.default_build_job` still resolves its own output directory for a claimed job.
Job rows are created only through `enqueue` and `POST /api/v1/jobs`, which sit behind the check
(`serve` refuses to start with such a config, `enqueue` refuses to run). A row created before the
upgrade would render into the old location; adding a third call site (and the `scheduler`
package) for that one-off is out of scope.

### D-5: Idempotency and failure behaviour

The check is pure and reads nothing but paths, so a re-run, a `--force` run and a worker restart
all behave identically: the same refusal, exit 1, nothing written, no partial file. It does not
touch the staleness fingerprint or the render graph.

### D-6: Spec placement

The shared rule belongs to `project-config` (it is about which `output` and `input` values are
valid, for any consumer), so it is an ADDED requirement there. `headless-cli` already owns the
sentence being reversed, so the existing requirement is MODIFIED with its full text; its
"explicit output is honoured" scenario is narrowed to a sibling and a refusal scenario is added.
The `api-service` capability has no output requirement, so `serve` is covered by a `project-config`
scenario rather than a third delta (Principle VIII).

## Risks / Trade-offs

- [A library already using an inside-root output now fails] -> Intended: it was producing bogus
  events and errors every run. The error message names the folder to move it to; nothing on disk
  is touched.
- [`Path.resolve()` follows symlinks, so a symlinked output pointing into the root is refused,
  and one pointing out of the root is allowed] -> Matches what the layouts see on disk.
- [Moving the test patch target] -> `tests/test_cli_commands.py` is updated in the same task.
- [Existing tests might use an inside-root `-o`] -> `tests/test_cli_output_collisions.py` and
  others use `tmp_path / "out"` beside the root; the apply task greps for tests passing `-o` or
  `output:` under the root and moves their output to a sibling.
