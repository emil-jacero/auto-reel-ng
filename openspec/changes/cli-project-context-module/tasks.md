## 1. cli/: the public project context

- [ ] 1.1 Create `auto_reel_ng/cli/context.py` holding `ProjectContext`, `resolve_project_root`
  (from `commands._resolve_project_root`) and `project_context` (from `commands._project_context`),
  behaviour unchanged, `project_context` reusing `resolve_project_root`. Delete them from
  `commands.py`, import them there (`from .context import …`) and replace every use. Verify:
  `.venv/bin/python -m pytest tests/test_cli_commands.py tests/test_cli_render.py -m "not requires_db"`
  passes with `tests/test_cli_commands.py:180,193` now calling `context.project_context`, and
  `grep -rn "_project_context\|_resolve_project_root" auto_reel_ng tests` finds nothing.
- [ ] 1.2 Point `cli/thumbnails.py` at `from .context import project_context` and update the
  `thumbs` docstring cross-reference. Verify: `.venv/bin/python -m pytest tests/test_cli_thumbs.py`
  passes, and `wc -l auto_reel_ng/cli/commands.py` is below 945 (about 50 lines freed).
- [ ] 1.3 Update the `api/settings.py` module docstring that cites `_project_context`. Verify by
  reading it (no test).

## 2. api/: the shared check

- [ ] 2.1 Add `require_output_outside_walk_root(output_dir, walk_root)` to `api/settings.py`
  (design D-2): resolve both, raise `ConfigError` naming both paths and suggesting
  `default_output_dir` when the output equals the walk root or has it as a parent; export it in
  `__all__`. Call it in `resolve_api_settings` right after `output_dir` is built. Verify with new
  cases in `tests/test_api_settings.py`: `output: out` raises (message names both paths), `output:
  out/renders` raises, `output: .` with no `input` raises, a symlink to an inside folder raises,
  and the default, `output: ../renders`, `input: media` + `output: out`, and `input: media` +
  `output: .` all resolve.

## 3. cli/: refuse before walking

- [ ] 3.1 Call the helper in `project_context` after the output directory is chosen and before
  `get_layout(...)` enumerates events. Verify with new tests in
  `tests/test_cli_output_collisions.py` (or `tests/test_cli_output_inside_root.py`), using
  `main([...])` and `capsys`: `scan` with `-o <root>/out` over `<root>/2024/2024-07-20 - A/a.mp4`
  plus `<root>/out/2024/2024-07-20 - A.mp4` returns 1, stderr contains `inside the walked root`,
  stdout has no `ERROR  2024: no date` line, and `<root>` is byte-for-byte unchanged; the same with
  `--layout flat` never lists `out`; `render -o <root>` returns 1 and renders nothing (mock
  `render_batch` is not called).
- [ ] 3.2 Add the config-driven and allowed cases: `config.yaml` `output: out` makes `scan`,
  `enqueue` (monkeypatch the job-store builder so no DB is needed) and `thumbs` return 1; `input:
  media` + `output: out` still renders to `<root>/out`; the sibling default and an explicit
  sibling `-o` are unchanged. Verify with those tests passing.
- [ ] 3.3 `serve` fails at settings resolution: test that `main(["serve", <root>])` with
  `config.yaml` `output: out` returns 1 with the error on stderr without constructing the app
  (monkeypatch `create_app` and `ServiceServer` to fail the test if reached).
- [ ] 3.4 Grep the existing suite for tests that pass `-o`/`--output` or set `output:` under the
  walked root and move those outputs to a sibling folder. Verify:
  `.venv/bin/python -m pytest -m "not requires_db"` passes.

## 4. Docs

- [ ] 4.1 Rewrite the README output-layout bullet: replace "Do not point the output inside the
  walked root" with the enforced rule (an output equal to or inside the walked root is refused with
  an error and exit 1; an output beside a distinct `input` directory is fine), and note that
  `serve` applies it at startup. Verify by reading the rendered bullet next to the spec wording.

## 5. Validation gates

- [ ] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort
  auto_reel_ng tests`; `.venv/bin/python -m mypy auto_reel_ng`; `.venv/bin/python -m pylint
  auto_reel_ng` (no `too-many-lines` on `commands.py`, only the known cairo `no-member` noise);
  then the full `.venv/bin/python -m pytest` (podman for the `requires_db` tests). All clean.
