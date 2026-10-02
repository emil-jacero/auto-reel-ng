## Why

The movie file name is built verbatim from the event's `title` and `location`
(`render/orchestrator.py:output_filename`), and nothing upstream restricts those strings
(`reel/schema.py:_opt_str`, `api/schemas.py:MetadataBody`, `event/metadata.py:require_processable` only
reject blank). A `/` therefore turns the name into extra path components. Re-checked against `main`
(6a7fe16) with the same `output_dir / output_relpath(...)` join `render_movie` performs:

- title `Mid/sommar`, date `2025-01-16` -> `<output>/2025/2025-01-16 - Mid/sommar.mp4`; the render creates a
  stray folder `2025-01-16 - Mid`.
- location `Gamla/stan` -> a stray folder `2025-01-16 - T - Gamla` holding `stan.mp4`.
- title `a/../../../escaped` -> `<output>/2025/2025-01-16 - a/../../../escaped.mp4`, which resolves to
  `<output>/../escaped.mp4`, **outside the output directory**. `_execute` calls
  `output_path.parent.mkdir(parents=True)` first, so the `a`-prefixed folder exists and the `..` components
  resolve. This is a path-traversal write driven by a free-text field that the GUI, the API and a
  hand-edited `reel.yaml` all accept.

Titles such as `Jul/Nyar` are plausible, so rejecting them at save time would make existing events
unrenderable (supervisor decision: replace in the file name at the name builder; the title in `reel.yaml`
stays as written; no save-time rejection). This is the first change in the `render/orchestrator.py` chain
and is security-relevant, so it lands before the others.

## What Changes

- `output_filename` makes the movie name a single path component: every path separator (`/`, `\`) and every
  control character (including NUL) in the title and the location is replaced with `-` in the file name
  only. The authored title and location are untouched in `reel.yaml`, the API and on the title card.
- `render_movie` verifies, before any directory is created, that the computed output path stays inside the
  output directory and raises `RenderError` otherwise (defence in depth: the name builder is the fix, the
  guard is the backstop for any future caller or rule drift).
- The `movie-assembly` "Output naming and overwrite control" requirement gains the single-component rule
  and the containment guard, with scenarios for `Mid/sommar`, `Gamla/stan`, `a/../../../escaped`, and the
  guard.

Rendered output: the movie bytes for identical inputs are unchanged; only the path of an event whose title
or location contained a separator changes. `RENDER_GRAPH_VERSION` is **not** bumped (path changes, bytes do
not). Staleness fingerprint inputs do not change. `reel.yaml` / `config.yaml` schema does not change; no
Alembic migration, no rescan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `movie-assembly`: "Output naming and overwrite control" — the output file name is always one path
  component, and an output path that would leave the output directory is refused.

## Impact

- Package: `auto_reel_ng/render` only (`orchestrator.py`; tests in `tests/test_render.py`).
- Every consumer of `output_relpath` (CLI `scan`/`render`/`enqueue`/`adopt-renders`, the API job and
  media routes, the worker) picks up the sanitised name through the single shared rule; no call site
  changes. CLI and API are both covered with no API-side logic added (Principle V).
- `tests/test_api_media.py`: the `utbrytning` guard test now forces the climbing path by patching
  `output_relpath`, because no real title can produce one any more; it keeps exercising the media guard.
- An event whose title or location contained `/` and was already rendered into a nested folder is looked up
  at the new single-component path; it reads as not rendered and renders again. No existing file is moved
  or deleted (pruning superseded outputs is held for the user).

## Non-goals

- Rejecting or normalising separators at parse time, in `MetadataBody`, or in the GUI; the authored title is
  kept as written.
- Changing the title card text or the `reel.yaml` content.
- Sanitising other characters legal on POSIX (`:`, `*`, `?`, trailing dots/spaces) or filesystem-specific
  reserved names.
- Migrating or deleting movies already written to a nested path.
- Chapter-name strictness in the engine (held for the user).
