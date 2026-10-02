## 1. Baseline

- [x] 1.1 Confirm the code this change was designed against, on `origin/main` after the gate
  `render-refuses-claimed-movie` merged: `write_manifest` has no `superseded` parameter or field,
  `recorded_output_in` does not exist, `main.py` has ten subcommands and no `prune-renamed`, the `headless-cli`
  and `change-detection` specs have no requirement named "`prune-renamed` removes superseded movies only on
  request" or "The render manifest remembers the movie names it superseded", and note the name and signature
  of the gate's "another event's manifest records this file" lookup in `render/claims.py` (task 3.1 uses
  it). Stop and report if a check fails in a way the design does not cover.

## 2. staleness/ — the manifest remembers superseded names

- [x] 2.1 Red first, in `tests/test_staleness_manifest.py`: a second `write_manifest` with a different
  `output` records the first as `superseded`; three renames give `[A, B]` in order; a write with the same
  `output` keeps the list unchanged; renaming back to a listed name removes it from the list; a manifest
  without the field, and one whose field is a string or a list holding a number, read with `superseded == ()`
  and still count as valid; an unreadable previous manifest contributes nothing; the fingerprint, components
  and `written_at` handling are unchanged; `recorded_output_in("2024-06-27 - X.mp4", out) == out/"2024"/…` and an
  undated name is directly under `out`, and `recorded_output_path` agrees with it on the existing cases.
  Verify they fail on the unchanged code.
- [x] 2.2 Add `superseded: Tuple[str, ...] = ()` to `RenderManifest`, the carry-over to `write_manifest`, the
  tolerant read to `read_manifest`, and `recorded_output_in` (with `recorded_output_path` rebuilt on it) in
  `auto_reel_ng/staleness/manifest.py`, exported from `auto_reel_ng/staleness/__init__.py`, as in the design.
  Verify the 2.1 tests pass and `.venv/bin/python -m pytest tests/test_staleness_manifest.py
  tests/test_render_manifest.py tests/test_cli_adopt_renders.py` stays green.

## 3. cli/ — `prune-renamed`

- [x] 3.1 Red first, new `tests/test_cli_prune_renamed.py` (scratch projects on `tmp_path`, manifests written
  with `write_manifest` and empty `.mp4` files as movies, no ffmpeg): the planner and a dry run list the
  superseded movie with its event and replacement and delete nothing; an event retitled but not re-rendered, an
  event whose current movie is missing or a folder, an event without the field, and an event whose manifest is
  unreadable list nothing; a file that another event's manifest records as its movie, a file that is another,
  unrendered, event's expected output path, and an owner outside `--years` each protect the file; a
  renamed-back event and a case-only rename list nothing; `../x.mp4`, `a/b.mp4`, `..`, a symlinked year folder
  pointing outside the output, a symlink at the old name and a folder at the old name list nothing and leave
  the outside file unchanged. Verify they fail (the module does not exist).
- [x] 3.2 Add `auto_reel_ng/cli/prune.py` with `PruneCandidate`, `plan_prune` and the listing printer, using the
  gate's lookup for the manifest-claim set where task 1.1 found it fits (design, "Claims"). Verify the 3.1
  planner and dry-run tests pass.
- [x] 3.3 Red first, same file: `--yes` deletes the old movie and leaves the new movie and the manifest
  byte-for-byte unchanged, prints the deleted file, and exits 0; a second run lists nothing; a delete that fails
  (a read-only year folder, or `unlink` patched to raise `PermissionError` for one file) is reported with the
  operating system's reason, the other file is still deleted, and the exit code is 1; a layout walk that raises
  `OSError` deletes nothing and exits 1; `--years` restricts the candidates but not the claims; `-o` selects the
  output directory; a project with no events exits 0 with the standard message; `--help` lists
  `prune-renamed` (eleven subcommands, updating the existing count assertion in `tests/test_cli_main.py`) and
  `--yes`. Verify they fail on the 3.2 module.
- [x] 3.4 Add `cmd_prune_renamed` (delete with the design's re-check, per-file error report, exit codes) to
  `auto_reel_ng/cli/prune.py` and register `prune-renamed` and `--yes` in `auto_reel_ng/cli/main.py` (module
  docstring updated). Verify the 3.3 tests pass and `.venv/bin/python -m pytest tests/test_cli_main.py
  tests/test_cli_adopt_renders.py tests/test_cli_commands.py` stays green.

## 4. Docs

- [x] 4.1 Add `auto-reel prune-renamed <root> [--yes]` to the command list and a short "Removing superseded
  movies" paragraph in `README.md` (dry run first, what is protected, movies renamed before this version are
  not known), one amendment sentence on **D-9** in `docs/high-level-design.md` (dated, change
  `prune-renamed-command`: the engine still never deletes; the operator command removes superseded movies; the
  manifest records `superseded`). Verify `grep -n "prune-renamed" README.md docs/high-level-design.md
  auto_reel_ng/cli/main.py` shows all three.

## 5. Validation

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full
  `.venv/bin/python -m pytest` including `requires_db` (podman). Then run
  `openspec validate prune-renamed-command --strict`. Verify all are clean or green, apart from the known cairo
  `no-member` noise and the five font-dependent skips.
