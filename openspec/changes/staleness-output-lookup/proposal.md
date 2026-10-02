## Why

Triage of two bug items found one real defect in the staleness gate and three claims that the code does not
support. This change fixes the defect, pins the by-design behaviour with tests so it cannot drift, and records
what was checked and not changed. It was written against `main` at `6a7fe16` and re-checked on `main` at `e55a8cd`, after its two gates
(`render-output-name-safety`, `render-progress-monotonic`) merged. Both are in; line numbers below are from the earlier base.

**Item `media-routes-head-and-conditional-gaps`, the gate half (the real defect).** `evaluate()` tests the
expected output with `Path.exists()` (`staleness/gate.py:93`). The movie lookup, `rendered_output()`
(`gate.py:116`), and so the movie route, test `is_file()`. A folder at the movie's path therefore counts as a
rendered movie in the verdict and not in the route. The verdict is fresh (no reason), and
`GET /api/v1/events/{id}/movie` answers 404. The `api-service` spec lists this as an accepted exception, and
`gate.py:108-110` says "a verdict change is not this function's to make". `adopt-renders` has the same split:
`cmd_adopt_renders` tests `output_path.exists()` (`cli/commands.py:959`), so it would write a manifest asserting
that a folder is a render. The HEAD and `If-Modified-Since` half of this item is change `api-media-head-conditional`.

**Item `output-renamed-lookup-misses`, four sub-claims, re-checked against the code:**

1. *A title or location with `/`* ("Jul/Nyar"): `_execute` records `output_path.name`, the last path component,
   while the file lives under a folder made from the earlier components. The lookup rebuilds the path from the
   bare name and misses. Confirmed on `main`, and fixed by the gate `render-output-name-safety`: after it,
   `output_filename` returns one path component, so the recorded name and the real file agree. This change adds
   a test that pins it (a title with a separator is found as `output_renamed` after a retitle). Movies already
   rendered into a nested folder by an older engine keep a manifest naming only their last component. They read
   `output`, as a missing movie does. Nothing is lost, and the lookup stays a lookup of a bare name.
2. *A render into a different `-o` directory*: confirmed, the rename is cited as `output`. It is the specified
   behaviour, not a defect. The `change-detection` spec says "under the same output directory" on purpose, the
   output directory is the root of the library the verdict is about, and a movie in another directory is not
   that library's movie. The triage sketch (record the output root in the manifest and follow it) is not
   adopted. See design, "Why the manifest does not record a root".
3. *An undated title that starts with `YYYY-MM-DD - `*: unreachable. `require_processable`
   (`event/metadata.py`) refuses an event without a real date before any render or verdict, on the CLI, the
   worker and the API. Only direct library use reaches it, and `recorded_output_path` already documents it.
4. *A case-only rename on a case-insensitive mount (NTFS)*: not reproducible on this host, which has no such
   mount. By construction the expected path exists there, so no output reason is cited, the editorial component
   still differs, and the event re-renders. This is the case the existing spec already states.

## What Changes

- **The gate counts only a regular file as the event's movie.** `evaluate()` tests `is_file()` on the expected
  output. A folder (or any non-file) at the movie's path cites `output`, or `output_renamed` when the previous
  movie is still on disk under its recorded name, exactly like an absent file. The verdict now agrees with
  `rendered_output()` and with the movie route for every event. The `api-service` spec loses its "directory"
  exception.
- **`adopt-renders` adopts only a regular file.** A folder at the output path reads "unrendered, nothing to
  adopt", and no manifest is written.
- **A render refuses a non-file at its output path.** With the verdict change a folder makes the event stale, so
  a render is attempted. Today `render_movie` would skip it without overwrite (it believes the path is a
  finished movie), or die in `os.replace` with an untyped `IsADirectoryError`, which `render_batch` does not
  isolate. `render_movie` now raises `RenderError` naming the path, before it runs ffmpeg and before it touches
  the path.
- **By-design behaviour is pinned and documented**, with no code change: a movie in another output directory is
  not looked for (`output`); a title with a separator is found after a retitle (needs the gate); the undated and
  case-insensitive cases are documented as unreachable and unverified (design, gate docstrings, HLD D-9).
- **Docs:** the `gate.py` docstrings (not the `StalenessReason` docstring, which is published verbatim as the
  OpenAPI description and stays), `manifest.py`'s `recorded_output_path` note, the README sentence about
  the movie route, and a dated amendment under HLD D-9.

## Non-goals

- **No manifest change.** No new field, no new `output` form, no version bump. The 2026-10-01 decision of
  `output-renamed-reason` ("no manifest schema change") stands. The held `prune-renamed` idea, which the triage
  said depends on a relative output path, is not decided here. If the user approves it, it adds what it needs.
- **No new staleness reason**, so `StalenessReason`, `web/openapi.json` and `web/src/api/schema.d.ts` do not change.
- **No HEAD or `If-Modified-Since` handling.** That is `api-media-head-conditional`.
- **No cleanup of an old nested-folder movie** (item 1) and no deleting or pruning of superseded movies (held).
- **No change to what a dry run reports**, to fingerprints or to rendered bytes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-detection`: `Requirement: Staleness gate` defines the expected output as a regular file, adds scenarios
  for a folder at the path and for another output directory. `Requirement: Manifest adoption` adopts only a
  regular file. A new `Requirement: A render refuses a non-file at its output path`.
- `api-service`: `Requirement: Rendered movie endpoint` drops the "directory" exception to "a movie exists exactly
  when the verdict cites neither `no_manifest` nor `output`".

## Impact

- **Baseline:** `main` at `e55a8cd` (designed on `6a7fe16`). Gates (merged): `render-output-name-safety` (names are single components; adds a
  containment assertion in `render_movie`) and `render-progress-monotonic` (rewrites `_Progress` in
  `orchestrator.py`). Both edit `orchestrator.py`. This change adds one guard in `render_movie` and does not
  touch `_Progress` or the `write_manifest` call.
- **Packages:** `staleness/` (`gate.py`, a docstring in `manifest.py`) and `render/` (`orchestrator.py`), plus a
  one-token edit in `cli/commands.py` (`adopt-renders`). Tests: `test_staleness_gate.py`, `test_render.py`,
  `test_render_manifest.py`, `test_cli_adopt_renders.py`, `test_api_media.py`.
- **Complexity (Principle VII):** about ten lines of code: one call changed in the gate, one in `adopt-renders`,
  one guard in `render_movie`.
- **CLI vs API (Principle V):** the verdict is one function, so `scan`, `render`, `enqueue`, the worker and every
  API read change together. No endpoint logic is added.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump**: identical inputs render identical bytes, and
  the guard only turns a case that failed untyped into one that fails typed.
- **Schemas:** no `reel.yaml`, `config.yaml`, manifest, Alembic or OpenAPI change.
- **Behaviour change:** an event with a folder at its movie's path was fresh and is now stale (`output`). No real
  library has one; the triage found it only by constructing it.
- **Size (Principle VIII):** two capability deltas, two packages with real changes, 10 tasks.
