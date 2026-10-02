## Why

After a title, date or location edit and a re-render, the previous movie stays on disk by design: the engine
never deletes a movie (HLD §4.3 / **D-9**, capability `change-detection`, "A renamed event keeps its previous
movie"). Old files therefore accumulate in the archive, and the only way to remove them is for the operator
to work out by hand which ones are superseded. The user decided on 2026-10-02 ("Add prune command") to keep
the engine non-destructive and give the operator one explicit, dry-run-by-default command for it (Principle I,
no silent deletion; Principle V, the CLI surface; HLD §8 backlog item "renamed event: old movie").

The command needs to know which files are superseded, and the render manifest cannot say: it records only the
**current** movie name, so a re-render overwrites the old name and nothing remembers it. Re-checked on
`origin/main` at `6df2680`: `write_manifest` (`staleness/manifest.py`) writes a fresh payload each time, with a
single `output` field. This is the finding `renamed-event-old-name-takeover-replaces-kept-movie` in the
2026-10-02 bug triage; its other half, the render guard, is the gate change `render-refuses-claimed-movie`.

## What Changes

- **The manifest remembers superseded names** (`staleness/manifest.py`): `write_manifest` carries over the
  previous manifest's `output` when the new render records a different file name, keeping a de-duplicated list
  `superseded` of bare movie file names. The manifest `version` stays 1: an older manifest has no list and
  reads as empty, and an older reader ignores the field. `adopt-renders` writes through the same function, so
  it keeps the list too. A small pure helper `recorded_output_in(recorded, output_dir)` resolves a recorded
  name to its D-9 path from the output directory alone (`recorded_output_path` is rebuilt on it).
- **`auto-reel prune-renamed <root>`** (`cli/`): takes the common project options (`-o/--output`, `--layout`,
  `--years`) and lists every superseded movie in the output directory whose event has since rendered
  successfully under another name: the event's manifest records a current movie that exists as a regular
  file. It prints each old file with its event and the file that replaced it. **Dry run by default**; it
  deletes only with `--yes`. It never deletes a file that another event still claims (another event's manifest
  records it as its movie, or another event's current expected path is that file), never a path outside the
  output directory, and never anything but a regular file. A file it cannot delete is reported and the run
  continues; the exit code is non-zero on any such error. Manifests are never written by it.
- **Docs:** README command list and a short section, a D-9 amendment in the HLD, and the `cli/main.py` module
  docstring.
- **Tests** alongside each piece: manifest round trips and the carry-over; the planner on scratch trees; the
  command's dry run, `--yes`, exit codes and every refusal.

## Non-goals

- **The engine still never deletes a movie on its own.** Prune is an operator command; no render, worker, scan
  or API path calls it, and no `DELETE` endpoint or GUI button is added (Principle V allows the API to follow).
- **No render guard here.** Refusing a render that would overwrite a file another event's manifest records is
  `render-refuses-claimed-movie` (the gate, merged first). This change reuses the lookup it adds; it adds no
  second rule.
- **No manifest rewrite by prune.** A superseded name stays in the list after its file is deleted; a later
  run finds the file gone and says nothing about it. No cleanup pass, no new file, no database table.
- **No history for movies renamed before this change.** A manifest written by an older engine has no list, so
  files it superseded earlier are not found; they are removed by hand or become known after the event's next
  rename. Not guessed from file names.
- **No race protection** against a render that starts between the plan and the delete; the command is for an
  idle archive.
- **No change to `RENDER_GRAPH_VERSION`:** rendered bytes and the staleness fingerprint inputs are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `headless-cli`: the entry-point requirement now lists `prune-renamed` (eleven subcommands); new
  `Requirement: prune-renamed removes superseded movies only on request`.
- `change-detection`: new `Requirement: The render manifest remembers the movie names it superseded`.

## Impact

- **Baseline:** written against `origin/main` at `6df2680`, before the gate `render-refuses-claimed-movie`
  merged; the design reuses the gate's lookup by role (design, "Claims"), and task 1.1 confirms its name.
- **Packages:** `cli/` and `staleness/`. Files: `cli/prune.py` (new), `cli/main.py`, `staleness/manifest.py`,
  `staleness/__init__.py`, `tests/test_staleness_manifest.py`, `tests/test_cli_prune_renamed.py` (new),
  `README.md`, `docs/high-level-design.md`.
- **CLI vs API (Principle V):** the CLI gains the capability first; the API is untouched.
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump**; no fingerprint input
  changes (the new manifest field is not part of the fingerprint or the verdict).
- **Schemas:** `render-manifest.json` gains an optional `superseded` array (version stays 1); no `reel.yaml`,
  `config.yaml`, database or OpenAPI change, no `web/` change.
- **Complexity (Principle VII):** one new CLI module, one optional manifest field, one pure path helper; no
  new config key, flag beyond `--yes`, or dependency.
- **Size (Principle VIII):** two capability deltas, two packages, 9 tasks (one baseline, one docs, one
  validation).
