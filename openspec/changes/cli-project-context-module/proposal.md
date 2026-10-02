## Why

Two defects share one function, `_project_context` in `cli/commands.py`, and its API twin
`resolve_api_settings`.

1. **An output directory inside the walked root is accepted silently.** The ingest layouts walk
   the root's subfolders, and a render files movies into `<output>/<YYYY>/…`. With
   `-o <root>/out` (or `output: out` in `config.yaml`) the next `scan` reads `out/2024` as a year
   folder and reports a bogus event (`ERROR  2024: no date: folder name has a year only (2024)`);
   with `--layout flat`, `out` itself is listed as an event. Every render into such an output
   grows more bogus events. Only a README sentence warns, and the `headless-cli` spec
   explicitly blesses it ("used as given, even when it lies inside the project root"). That
   breaks Principle I (fail loud): a layout that cannot work should be refused before anything
   is walked or written. The reference is the default-output decision (the `<root>-output`
   sibling) from the `output-path-year-folder` change, which exists for exactly this hazard.
2. **`cli/thumbnails.py` imports the private `commands._project_context`.** That is a layering
   smell, not a runtime bug, but `commands.py` is 995 lines against pylint's 1000-line
   `too-many-lines` limit (the `clip-thumbnails` change already had to split `thumbs` out for
   that reason), so the check cannot be added there without tripping pylint. The two are fixed
   together because both edit the same function.

HLD §4.9 (thin API, one behaviour for CLI and API) applies: the check must live in one helper
that both `_project_context` and `resolve_api_settings` call.

This is bug-round maintenance outside the §6 phase roadmap (phases 1-7 and change detection are
done; phase 8 is the GUI). It resolves no §8 research item.

## What Changes

- New module `auto_reel_ng/cli/context.py` with the public `ProjectContext`, `resolve_project_root`
  and `project_context` (moved from `commands.py`, where `_resolve_project_root` duplicates the
  root check). `commands.py` and `thumbnails.py` import them; the private import is gone.
- New shared helper `require_output_outside_walk_root(output_dir, walk_root)` in
  `api/settings.py` raising `ConfigError`. Called by `project_context` and by
  `resolve_api_settings` after both paths are resolved.
- An output directory that equals the walked root or lies inside it is refused. The refusal
  names both paths and suggests a sibling folder. The CLI prints `error: …` and exits 1 before
  any walk, render or write; `auto-reel serve` fails at startup the same way.
- The same gate applies whether the directory came from `-o`, `config.yaml` `output` or the
  default. The default is a sibling, so it never trips.
- **BREAKING** (deliberately): a library that today passes `-o <root>/out` or sets
  `output: out` is refused instead of producing bogus events. The spec sentence "used as given,
  even when it lies inside the project root" is withdrawn.
- README output note is rewritten from "do not" advice into the enforced rule.

Rendered output for identical inputs does not change, so `RENDER_GRAPH_VERSION` is not bumped.
The staleness fingerprint inputs do not change. No `reel.yaml` or `config.yaml` key is added
(an existing key's valid values narrow). No Alembic migration and no rescan is needed. Packages:
`cli/` and `api/` only. Both the CLI and the API service are affected, by one shared helper.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `headless-cli`: the output-directory requirement no longer honours an output inside the walked
  root; the CLI refuses it with a non-zero exit before walking or writing.
- `project-config`: an added requirement that an effective output directory (from `-o`,
  `config.yaml` or the default) never equals or lies inside the walked root, for the CLI and the
  API service alike.

## Non-goals

- Refusing an output directory that *contains* the walked root. A movie lands in
  `<output>/<YYYY>/`, which is outside the walked root unless that year folder is the root
  itself, so no scan-back occurs. Refusing it would break a working layout such as
  `input: media` with `output: .` (see design D-2).
- The worker's job-time output resolution (`scheduler/worker.default_build_job`). Jobs are
  created through `enqueue` or `POST /api/v1/jobs`, both behind the check; a stale job row
  from before the upgrade is not re-validated (design D-4).
- Any change to the layouts' walk, to `default_output_dir`, or to the chapter-name strictness and
  superseded-movie pruning items held for the user.

## Impact

- Code: new `auto_reel_ng/cli/context.py`; `cli/commands.py` (~55 lines out, imports in),
  `cli/thumbnails.py` (import), `api/settings.py` (helper + call).
- Tests: `tests/test_cli_commands.py` (patch target moves), `tests/test_cli_output_collisions.py`
  (or a new `tests/test_cli_output_inside_root.py`), `tests/test_api_settings.py`.
- Docs: `README.md` output-layout bullet. Specs: `headless-cli`, `project-config`.
- Users: a library with its output inside the walked root must move it before the next run.
