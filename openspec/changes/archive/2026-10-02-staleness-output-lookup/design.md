## Context

See proposal.md, "Why", for the findings. The code on `main` at `6a7fe16`, re-checked on `e55a8cd` (the two gates merged; line numbers may have shifted):

- **`evaluate(event_dir, output_path, fingerprint)`** (`staleness/gate.py:70`) appends the component reasons, then
  `_absent_output_reason(...)` when `not expected.exists()` (`:93`). `rendered_output()` (`:98`) returns the
  expected path when `expected.is_file()` (`:116`), else `_renamed_output(...)`. Its docstring records the split as
  "the accepted edge" (`:108-110`).
- **`_renamed_output`** (`:128`) accepts a recorded value only when it differs from the expected name, is not
  `""`, `.` or `..`, and is a bare file name. It builds the old path with `recorded_output_path(recorded, expected)`
  (`manifest.py:105`), which inverts D-9 (year folder from the name's date prefix) beside the current output
  root, and returns it only for a regular file.
- **The manifest** records `output_path.name` (`render/orchestrator.py:470-475`; `cli/commands.py:983` for
  `adopt-renders`). Nothing else reads the field.
- **The movie route** (`api/media.py:202`) asks `rendered_output(...)`. A folder at the expected path is therefore
  already "no movie" there, and the api-service spec lists it as an exception to "the movie exists iff the verdict
  cites neither `no_manifest` nor `output`".
- **Render with a folder at the path.** `render_movie` (`orchestrator.py:252`) skips on `output_path.exists()` when
  `overwrite` is false. The CLI and the worker always pass `overwrite=True` (`cli/commands.py:338`,
  `scheduler/worker.py:89`), so they reach `os.replace(part, folder)` and get `IsADirectoryError`, an
  `OSError`, not an `EngineError`: `render_batch` (`:480`) isolates only `EngineError`, so the error leaves the batch instead of
  becoming that event's reported failure.

## Goals / Non-Goals

**Goals**

- One definition of "the event's movie" for the verdict, the movie route and `adopt-renders`: a regular file.
- A render that meets a non-file at its output path fails typed and isolated, never skipped and never untyped.
- The by-design lookup rules are tested, not only specified.

**Non-Goals**

- A new way of recording or finding the previous movie (see below).
- A new staleness reason for "a folder is where the movie belongs". `output` already means "no movie at the
  expected path".

## Decisions

### D1. `evaluate()` uses `is_file()`; the lookup order stays

`if not expected.is_file()` replaces `if not expected.exists()`. `_absent_output_reason` is unchanged: it asks
whether the recorded movie is on disk under the old name. A folder at the new path with the old movie kept cites
`output_renamed`, which is true: the render writes the new name and keeps the old file. (It will in fact fail on the
folder; see D3.) `rendered_output` already behaves this way, so the two now agree for every input, and its
docstring drops the "accepted edge" paragraph.

*Alternative: make `rendered_output` use `exists()`.* That would serve a folder as a movie. Rejected: the route
would try to stream a directory.

*Consequence worth stating.* A folder was "fresh" and is now "stale". Every gate caller treats `output` as stale, so
`render`, `enqueue`, `POST /api/v1/jobs` and the worker would attempt a render. D3 makes that attempt fail loudly
and typed. This is correct: before, the GUI said "up to date" and the player said nothing.

### D2. `adopt-renders` tests `is_file()`

`cmd_adopt_renders` already says "output file exists" in its docstring and in the spec. A one-token change makes the
code say it too. A folder is "unrendered, nothing to adopt", with no manifest written. Without it, adoption of an
event with a folder would write a manifest that makes the gate (after D1) cite `output` straight after "adopted",
which is confusing. `cli/commands.py` is near pylint's 1000-line limit (920 lines on `e55a8cd`); the edit adds none.

### D3. `render_movie` raises `RenderError` for a non-file at the output path

After the dry-run branch and before the skip check:

```python
if output_path.exists() and not output_path.is_file():
    raise RenderError(f"{output_path} exists and is not a regular file; refusing to render over it")
```

`RenderError` is an `EngineError`, so `render_batch`, the CLI report and the worker's failure path already handle
it per event (Principle I). The check precedes the skip check, so `overwrite=False` cannot report a folder as an
up-to-date movie. It precedes `_execute`, so no ffmpeg runs and nothing is removed or replaced. It follows the dry
run, which stays side-effect free and disk-free.

Order against the gates: `render-output-name-safety` adds a containment assertion on `output_path` in the same
function. This guard goes after that assertion (a path outside the output directory is refused first) and next to
the skip check. If the gate's final code differs, keep this guard immediately before the skip check.

*Alternative: delete the folder if empty, or replace it.* Rejected. The engine never removes anything it did not
write (spec, "A renamed event keeps its previous movie"), and the operator put the folder there.

### D4. Why the manifest does not record a root (the triage sketch, rejected)

The sketch records the output path relative to the output root, plus the root, so the lookup follows a render into a
different `-o` directory. Re-checked against the code, it gives nothing for any reachable case and costs more.

- The recorded year folder is already exact. `output_relpath` derives the folder from `metadata.date`, and for a
  dated event the name's prefix is that same date, so `recorded_output_path` inverts it exactly. A relative path
  adds information only for an undated title that starts with a date prefix, which is unreachable (proposal 3).
- Following a recorded root *widens what the service can serve*. `rendered_output()` feeds the movie route. A
  root read from a hand-editable sidecar would let the route open files outside the service's output directory,
  and the spec's "a render record cannot point outside the output directory" scenario would have to be dropped.
- It makes a library non-relocatable: moving `output/` to another disk would leave every manifest pointing at the old
  root, and the gate would follow it.
- The verdict is about *the output directory in use*. An event whose last render went elsewhere has no movie here.
  `output` is the true answer, and the next render writes here.
- The earlier decision, "no manifest schema change", was taken on 2026-10-01 for `output-renamed-reason`, and
  nothing found since contradicts it.

*Alternative: cite the other-directory case as its own reason.* Rejected: it widens the published, closed
vocabulary (OpenAPI, the generated client and the GUI's exhaustive label map) for a case the user can only create
by running the CLI with `-o` pointing somewhere else.

The held `prune-renamed` idea would need to locate superseded movies. If the user approves it, it chooses its own
record then (for example a field added with a version bump). This change leaves that open.

### D5. Docs say what was checked

The unreachable and unverified sub-claims are written where a future reader meets them:

- `gate.py` `_renamed_output` docstring: a movie in another output directory is not looked for; a movie that an
  older engine wrote into a nested folder (title with a separator) is recorded by its last component and reads
  `output`.
- `manifest.py` `recorded_output_path` docstring already documents the undated edge; it gains one sentence for
  why that is unreachable (every surface refuses a missing date).
- HLD D-9 gains a dated amendment for the three points: a folder is not a movie, another directory is not searched,
  and a case-insensitive mount is unchanged and unverified here.

## Risks / Trade-offs

- **An event with a folder at its movie path goes stale and its render now errors.** → That is the intent; the error
  names the path. Mitigation for a curious user: the message says what is there and that the engine will not replace it.
- **A forced render of a renamed event that also has a folder at the new path fails**, so the "keeps its previous
  movie" scenario never triggers for it. → Acceptable: nothing is written, the old movie and the manifest are untouched.
- **Gate chain on `orchestrator.py`.** `render-output-name-safety` and `render-progress-monotonic` both edit the
  file. → Task 1.1 checks the base before anything else; the guard is placed by anchor (before the skip check), not by
  line number.
- **`commands.py` is near the pylint line limit.** → Only a token changes. If a gate extracts a module first, the line moves with it.
- **Legacy nested-folder movies** (older engine, title with `/`). → Read `output` (missing), as before. The operator
  can re-render; the new name is a single component.

## Migration Plan

None. No manifest, config, schema or database change. Rolling back is reverting the three code edits.

## Open Questions

None that change what is built. Held for the user and not touched here: whether the engine should ever prune or
refuse to overwrite a superseded renamed movie.
