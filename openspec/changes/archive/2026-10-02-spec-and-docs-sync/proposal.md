## Why

Merged changes left four statements out of date, none of them a behaviour bug: a web-app scenario still
says a render's adoption of a NEW clip can leave a root clip ignored (it cannot since D-12); the
`project-config` capability never mentions the `thumbnails`, `worker`, `api` and `database` entries the
loader has read for several changes; a test docstring names the wrong server class; and nothing in the
README or the HLD shows how a host CLI and a container service share one thumbnail cache. Specs are the
contract, so they should say what the code does.

## What Changes

- Reword the web-app scenario "A clip from another folder is named by its path": the root clip is ignored
  "as a hand edit leaves it", and a render never ignores a clip (D-12).
- Extend `project-config` to list the `thumbnails`, `worker`, `api` and `database.url` entries, say that
  each is a mapping that fails loud otherwise, and add scenarios for the `thumbnails` map (carried through,
  absent, wrong-typed) and for `worker` / `api`. The capability's Purpose line is edited to match.
- The docstring of `tests/test_api_ws_lifecycle.py` names `ServiceServer`, the `uvicorn.Server` subclass
  `auto-reel serve` runs.
- README ("Clip thumbnails") and HLD D-11 get a short example of one cache shared by the host CLI and a
  container service, with the compose stack's `XDG_CACHE_HOME=/data/cache` as the worked case.
- No code behaviour changes. `RENDER_GRAPH_VERSION` is untouched: rendered output for identical inputs is
  the same.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: the scenario "A clip from another folder is named by its path" (inside the requirement "The
  event page shows the event's chapters and clips") is reworded; no behaviour changes.
- `project-config`: the requirement "Load a project config.yaml of shared defaults" lists the `database`,
  `worker`, `api` and `thumbnails` maps and gains scenarios for them.

## Impact

- `openspec/specs/web-app/spec.md`, `openspec/specs/project-config/spec.md` (via archive; the Purpose line
  is edited directly), `README.md`, `docs/high-level-design.md`, `tests/test_api_ws_lifecycle.py`
  (docstring only), `tests/test_project_config.py` (one test per new scenario).
- Gate: `jobshub-stop-and-db-timeouts` also touches `tests/test_api_ws_lifecycle.py` and is already merged
  to `origin/main`; this change edits only the module docstring on top of it.
