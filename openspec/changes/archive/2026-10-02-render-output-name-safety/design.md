## Context

`output_relpath(metadata)` is the single rule every call site uses for an event's output path
(movie-assembly, "Output naming and overwrite control"): `<YYYY>/<output_filename>` for a dated event, the
bare filename otherwise. `output_filename` interpolates `metadata.title` and `metadata.location` verbatim,
and `render_movie` joins the result onto `options.output_dir`, then `_execute` runs
`output_path.parent.mkdir(parents=True, exist_ok=True)`. See proposal.md for the observed failures.

Every produced name ends in `.mp4` and (when dated) starts with an ISO date, so once separators are gone the
name can never equal `.` or `..`.

## Goals / Non-Goals

**Goals:**
- The file name is exactly one path component for any title/location string.
- A path that would leave the output directory is a loud, typed failure before anything is created.
- The fix lives at one place (the name builder) so every caller inherits it.

**Non-Goals:**
- Any change to parse/save-time validation, API schemas, or the title card (see proposal Non-goals).

## Research & Decisions

### Replacement character and scope of the sanitiser
**Context**: `/` must not reach the path; `\` is a separator on the SMB/Windows side of the archive (the
MOL drive is shared), and NUL or other control characters are invalid or hostile in file names.
**Explored**: Triage (`slash-in-titles-engine`) sketched `-` or U+2215. Reproduced the three failures on
`main` by joining `output_relpath(Metadata(...))` onto a temp output dir.
**Decision**: Replace each of `/`, `\` and every character with code point `< 0x20` or `0x7f` by a single
ASCII `-`, applied to the title and the location separately, before the date prefix and the ` - `
joiners are added. No collapsing of runs, no trimming: `Mid/sommar` -> `Mid-sommar`, `a/../../../escaped`
-> `a-..-..-..-escaped`, `A//B` -> `A--B`. A title that is only separators yields `-` characters, not an
empty name; a missing title still yields `Untitled`.
**Rationale**: ASCII `-` is legal on every filesystem the archive touches and reads naturally next to the
existing ` - ` joiners; U+2215 would look right but defeats search and shell typing. Runs are not collapsed
so the mapping stays trivially predictable and total. Two events that sanitise to the same name are already
caught by `find_output_collisions` (case/NFC-insensitive), so the lossy mapping cannot silently overwrite a
sibling.

### Containment guard: lexical, in `render_movie`
**Context**: Defence in depth if a future change reintroduces a way to form `..` components.
**Explored**: `output_path.resolve().is_relative_to(output_dir.resolve())` (triage sketch) versus a lexical
check.
**Decision**: In `render_movie`, immediately after computing `output_path` and **before** the dry-run
branch, the exists/skip check and `_execute`, compare `os.path.abspath(output_path)` against
`os.path.abspath(output_dir)` (lexical normalisation, no filesystem access); if the former is not equal to
or inside the latter, raise `RenderError` naming the output path and the output directory. Nothing is
created, no `.part` exists, the job reports failed (Principle I; per-event isolation in `render_batch`
already turns it into a failed outcome).
**Rationale**: `resolve()` follows symlinks, and a symlinked year folder (for example `2024/` pointing at
another disk) is a legitimate archive layout that a resolving check would refuse. The threat is `..`/absolute
components in the name, which a lexical check catches without touching the disk and without a TOCTOU.

### No `RENDER_GRAPH_VERSION` bump
**Context**: Principle IV bumps the version when rendered bytes change for identical inputs.
**Decision**: No bump. The `.mp4` content is identical; only the destination path of events whose title or
location contained a separator changes, and the fingerprint does not include the output path. The rendered
manifest records `output_path.name`, which is now the sanitised single component, consistent with the file
actually on disk.

### Failure behaviour, idempotency
- Guard trips: `RenderError`, nothing written, nothing to clean up. A dry run trips it too (it is planned
  before the dry-run return) so `--dry-run` cannot report a plan that a real run would refuse.
- Re-run / `--force` / worker restart: the sanitiser is a pure function of the metadata, so the same event
  always maps to the same single-component path; a re-run skips an existing output, `--force` replaces it,
  a restart mid-render leaves only the `.part` in the right directory.
- An event previously rendered into a nested path is not found at its new path and renders again; the old
  file is left in place.

## Risks / Trade-offs

- [Lossy mapping: `A/B` and `A-B` produce the same name] -> `find_output_collisions` already refuses two
  events claiming one output path in a batch; no new mechanism (Principle VII).
- [Existing nested outputs become orphaned and the event re-renders] -> Accepted; only events with a
  separator (including a backslash, a legal file-name character on POSIX) in
  title/location are affected, and deleting superseded files is held for the user.
- [Lexical guard does not stop a pre-existing symlink inside the output tree from redirecting writes] ->
  Out of scope: the operator controls the output tree; the threat model here is the free-text metadata.
