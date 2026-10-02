## Context

See proposal.md. This is a documentation and specification sync. Facts re-checked on `origin/main` 6a7fe16:

- `openspec/specs/web-app/spec.md` line 425-427 still reads "as a hand edit or a render's adoption of that
  NEW clip leaves it". D-12 (`docs/high-level-design.md`) adopts a NEW root clip into the default chapter,
  and `api-service` already states that adoption "adopts no ignored clip". So only a hand edit leaves a
  root clip ignored.
- `auto_reel_ng/config/project.py` loads `database.url`, `worker`, `api` and `thumbnails` (opaque mappings,
  `_require_mapping` fails loud on a non-mapping). The `project-config` spec lists only `look`, layout,
  paths and `sort`. Inner keys of `thumbnails` are validated in `auto_reel_ng/thumbs/settings.py` and are
  already specified, with scenarios, in `clip-thumbnails`; `worker`/`api` keys in `headless-cli` and
  `api-service`.
- `tests/test_api_ws_lifecycle.py` serves the app "with `uvicorn.Server`, the server `auto-reel serve`
  runs"; `auto-reel serve` now runs `ServiceServer(uvicorn.Server)` (`auto_reel_ng/cli/commands.py`). The
  test itself keeps using `uvicorn.Server`; only the sentence is made accurate.
- The README already states that `serve` in a container has its own `XDG_CACHE_HOME` and tells the reader
  to set `thumbnails.cache_dir`, but shows no example. `compose.yaml` sets `XDG_CACHE_HOME: /data/cache`
  for the server and worker and mounts `./data/cache` there.

## Goals / Non-Goals

**Goals:** specs and docs say what the code does; every new `project-config` scenario is backed by a test
at the config loader.

**Non-Goals:** no change to config loading, validation, thumbnails, adoption or the web page. Not
restating the thumbnail key rules (`clip-thumbnails` owns them). Not touching the held items (chapter-name
strictness, pruning superseded movies).

## Decisions

- **`project-config` states that the loader carries the maps through and fails loud on a non-mapping; it
  does not restate the inner keys.** Alternative: copy `position` / `cache_dir` rules into
  `project-config`. Rejected: two homes for one rule drift apart, which is how this gap arose. The
  requirement points at `clip-thumbnails`.
- **One MODIFIED requirement in `project-config`** (its config requirement) rather than a new one, since
  the maps are part of "what `config.yaml` may declare". The Purpose line is not part of a delta for an
  existing capability, so it is edited directly in `openspec/specs/project-config/spec.md`.
- **The web-app scenario keeps its rows and expected THEN; only the setup wording changes.** The rule it
  tests (a chapter listing a clip from another folder names its rows by path) is unchanged.
- **The container example uses the compose stack as the worked case, and both options:** the container sets
  `XDG_CACHE_HOME=/data/cache` (compose does), or `config.yaml` sets
  `thumbnails.cache_dir: /data/cache/auto-reel/thumbnails`. For the host CLI to share the stack's cache,
  `thumbnails.cache_dir` must be the host path of the bind mount (`./data/cache/auto-reel/thumbnails`,
  absolute) and the container path of the same directory when read inside the container; a single
  `config.yaml` can only hold one of them, so the example says the library is configured for the side that
  reads it, and that the cache key hashes the resolved clip path, so a host and a container that see the
  library at different paths do not share entries even from one directory. This caveat is stated in the
  docs, not worked around.
- **No test for prose in README/HLD.** Verification there is review plus a grep that the sentences exist;
  the repo has no doc-content tests and adding one would couple tests to wording.

## Risks / Trade-offs

- [The sharing caveat (resolved clip path is in the cache key) could be wrong or stale] -> the task
  re-reads `auto_reel_ng/thumbs/` for the key before writing the sentence, and the README states only what
  the key hashes.
- [Reworded scenario drifts from the page again] -> unchanged THEN; scenario is already covered by the
  existing web test for it.
