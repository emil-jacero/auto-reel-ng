## 1. Specs

- [x] 1.1 Edit the Purpose line of `openspec/specs/project-config/spec.md` to list the `database`, `worker`,
  `api` and `thumbnails` entries; verify `openspec validate --specs --strict` still passes.
- [x] 1.2 Add tests in `tests/test_project_config.py` for the new `project-config` scenarios: the
  `thumbnails` map is carried as written, an absent map is empty, and `api` / `worker` keys are carried
  (the wrong-typed `thumbnails` and `worker` tests exist; keep them); verify
  `.venv/bin/python -m pytest tests/test_project_config.py` passes.
- [x] 1.3 Verify the reworded web-app scenario's rows still match `tests/test_api_events.py` and the naming
  rule in `web/src/events/common.tsx` (same rows, same chapters); no test change is expected.

## 2. Docs and test wording

- [x] 2.1 Reword the docstring of `tests/test_api_ws_lifecycle.py` to name `ServiceServer`, the
  `uvicorn.Server` subclass `auto-reel serve` runs; verify `.venv/bin/python -m pytest
  tests/test_api_ws_lifecycle.py` passes and `git diff` shows only the docstring changed.
- [x] 2.2 Add to the README "Clip thumbnails" section a short example of one cache shared by the host CLI
  and a container service (compose's `XDG_CACHE_HOME=/data/cache`, or `thumbnails.cache_dir`), including
  that the cache key hashes the resolved clip path; verify by grep that the example names
  `thumbnails.cache_dir` and `XDG_CACHE_HOME`, and that `compose.yaml` still sets what the text says.
- [x] 2.3 Add the same fact to HLD D-11 ("The cache" bullet) in one or two sentences; verify the README and
  HLD agree.

## 3. Check

- [x] 3.1 Verify `openspec validate spec-and-docs-sync --strict` passes, `.venv/bin/python -m pytest -m
  "not requires_db"` passes, and black, isort, mypy and pylint report nothing new.
