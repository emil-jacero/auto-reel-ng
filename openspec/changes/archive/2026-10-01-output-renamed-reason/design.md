## Context

See proposal.md, "Why", for the finding and the reproduction. The code on `main` at `93721b3`:

- **The gate** (`auto_reel_ng/staleness/gate.py`). `evaluate(event_dir, output_path, fingerprint)` (`:54`) returns
  `NO_MANIFEST` when `read_manifest()` gives `None` (`:65-67`). Otherwise it maps each changed component through
  `StalenessReason(name)` (`:69-73`) and appends `StalenessReason.OUTPUT` when `Path(output_path).exists()` is
  false (`:74-75`). `StalenessReason` (`:28-43`) has six members. Its docstring is published verbatim as the
  OpenAPI description of `StalenessReason` and lands in `web/src/api/schema.d.ts` (`:774-784`).
- **The expected path.** All seven call sites pass `output_dir / output_relpath(metadata)` for the *current*
  metadata:
  - `cli/commands.py:305` (`render`'s filter), `:426` (`scan`), `:652` (`enqueue`), `:958` (`adopt-renders`, which
    calls the gate only when that path exists, so it never sees either output reason);
  - `api/events_read.py:421` (`staleness_for`: list, detail, and the PUT echo);
  - `api/routes/jobs.py:119` (`POST /jobs`);
  - `scheduler/worker.py:269` (claim-time recheck).

  `output_relpath` (`render/orchestrator.py:125-135`) is D-9: `<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`
  when dated, `<title>[ - <location>].mp4` when not. The name comes from `output_filename` (`:111-122`).
- **The manifest** (`staleness/manifest.py`). `RenderManifest.output: str` (`:37`, read at `:92` as any string) is
  the bare file name: both
  writers pass `output=output_path.name` (`render/orchestrator.py:470-475` after the atomic `os.replace` at
  `:464`; `cli/commands.py:980-985` in `adopt-renders`). Nothing reads `manifest.output` today, and the
  `output-path-year-folder` proposal said so on purpose ("The gate never reads that field").
- **The engine never touches a previous movie.** `render_movie` computes the new path (`orchestrator.py:247`),
  skips when it exists and overwrite is off (`:252`), unlinks only its own `.part` (`:263`) and replaces only
  `output_path` (`:464`). No other module removes or renames anything in the output directory (grep for
  `unlink`/`os.replace`/`rmtree` in `auto_reel_ng/`, excluding thumbnails and the `reel.yaml` writer).
- **Where reasons surface.** `StalenessOut.reasons: List[StalenessReason]` (`api/schemas.py:89`), so the API needs
  no code to publish a new member. `cmd_scan` prints `', '.join(verdict.reasons)` (`cli/commands.py:445`). The GUI
  maps each reason through `REASON_LABEL` (`web/src/events/labels.ts:11-18`, an exhaustive
  `Record<StalenessReason, string>`) and joins the labels (`web/src/events/common.tsx:92`).
- **Specs.** change-detection's "Staleness gate" says stale when "the recorded output file is missing from the
  output directory", but the code checks the *expected* path. web-app's scenario "A stale event names every
  reason" (requirement "The event list shows every event with its render state") expects a renamed event to cite
  "the missing output". `renamed-label-and-zoom-bar` owns that capability and corrects it.

## Supervisor decisions (2026-10-01)

Recorded before implementation. Where they differ from a section below, they win, and that section says so.

- **Context.** The brief is `plan/brief-decisions.md` (Z2). The operator agreed to a precise reason instead of
  "movie file missing" when the name changed, and to keeping the old movie.
- **Reason name: `output_renamed`.** `renamed-label-and-zoom-bar` (Z3) uses the same name.
- **Replace-only (R1)**, cited only where `output` would have been: confirmed.
- **The bare-file-name and regular-file check** on the manifest's recorded output: accepted.
- **The one `REASON_LABEL` entry** in `web/src/events/labels.ts` is added here so `tsc` passes after the
  regeneration. It uses the FINAL list wording, `movie name changed`, not the provisional words this design first
  proposed (see "The published wording and the interim label"). Z3 adds the page sentence.
- **The change-detection "Staleness gate" text correction** (expected path, not "the recorded output file")
  belongs in this change: confirmed.
- **Showing the old and new file names** in the CLI or the API: a follow-up, not here.
- **The web-app scenario "A stale event names every reason"** is left to `renamed-label-and-zoom-bar`.
- **Review additions** (after implementation):
  - a CLI test that `enqueue` queues a renamed event exactly as it queues one whose movie is gone;
  - a worker test for the cancelled arm of "A failed render after a rename changes nothing";
  - `recorded_output_path` re-exported from `staleness/__init__.py`, like the other manifest names.

## Goals / Non-Goals

**Goals:**
- A renamed event whose last movie is still on disk is reported as renamed (`output_renamed`), everywhere the
  verdict is shown: `scan`, the list, the detail, and the PUT echo. A movie that is really gone is still `output`.
- Not one stale/fresh decision changes, so `render`, `enqueue`, `POST /jobs`, the worker and `adopt-renders`
  behave exactly as before.
- "Keep the previous movie" becomes a stated, tested rule, recorded in D-9.
- The client build stays green on `main` between this change and `renamed-label-and-zoom-bar`.

**Non-Goals:**
- Any code change in `api/`, `cli/`, `scheduler/` or `render/`. The new member flows through existing code.
- A manifest field, a schema version bump, or a change to what the writers record.
- GUI wording beyond one interim `REASON_LABEL` entry.

## Research & Decisions

### Reproduction

**Context**: The finding came from a different library and an older build; the rule needed a fresh, local case for
every rename shape D-9 can produce.

**Explored**: A scratch dev library (`scripts/make_dev_library.py`, own database
`arel_spec_output_renamed_reason`, `serve` on port 8123, all under the session scratchpad; the database was dropped
afterwards). Starting state from the script:
- Grillning was rendered and then retitled `Grillkväll med grannarna`.
- `scan` printed `stale: editorial, output`, and so did `GET /api/v1/events`.

Edits through `PUT …/reel` with `If-Match`, exactly as Edit mode sends them:
- the location `Dalarna` → `Leksand` on `2024-06-21 - Midsommar - Dalarna` (same year folder);
- the date `2023-06-23` → `2022-06-23` on `2023-06-23 - Midsommar - Dalarna` (another year folder).

Both PUT echoes and the list returned `["editorial", "output"]`. A deleted `2024-07-14 - Kalas.mp4` returned
`["output"]`, the same reason. Each old movie was still on disk.

**Decision**: These named cases are the spec scenarios, and the scenarios use the dev library's names.

**Rationale**: They are real events the implementer and the GUI change can recreate with one script.

### The reason's name: `output_renamed`

**Context**: The brief suggested `renamed` as an example. The vocabulary's wire values are snake_case slugs of
what changed (`output`, `editorial`, `clip_set`).

**Explored**: `renamed` and `output_renamed`. In this code base, "renamed" also describes clips (HLD §4.13: clips
"added / removed / renamed") and event folders (README: "renaming a folder changes only the fields `reel.yaml`
leaves unset").

**Decision**: `output_renamed`, as `StalenessReason.OUTPUT_RENAMED`. It is declared right after `OUTPUT`, so the
published enum reads `no_manifest, output, output_renamed, editorial, defaults, clip_set, engine`.

**Rationale**: It names *what* was renamed and pairs visibly with `output`, the reason it stands in for. It is
also the name the completeness critic's own fix suggested (final end-to-end pass, "Changing an event's title,
date or location orphans its rendered movie"). `renamed-label-and-zoom-bar` is gated on this change and reads the
name from the regenerated schema.

### When it is cited: only in place of `output`

**Context**: The agreed decision was a new reason "when the render manifest's recorded output path differs from
the current expected path AND the old file still exists".

**Explored**:
- **(R1) Replace only.** Decide `output_renamed` only when the expected movie is absent, that is, where `output`
  would be cited.
- **(R2) Whenever names differ.** Cite it whenever the recorded name differs from the expected one and the recorded
  file exists, even when the expected file exists too.

R2 changes decisions. Suppose the naming rule changed (as it did on 2026-09-27, `output-name-date-prefix`) and both
files exist with a matching fingerprint: today that event is fresh, and under R2 it would turn stale and re-render.
R2 would also cite the reason beside a leftover file at the new path, which the next render replaces anyway (D-C4).
The agreed decision says the verdict names the rename "instead of 'movie file missing'", and that "the plain
`output` reason stays for a truly missing movie". That is a replacement within the absent-movie case, and R1 is
exactly that.

**Decision**: R1. When the expected output is absent:
- `OUTPUT_RENAMED` if `manifest.output != expected.name` and the recorded movie exists (a regular file, found by a
  bare file name; see "Only a bare file name, only a regular file");
- `OUTPUT` otherwise.

When the expected output exists, neither is cited.

**Rationale**: The set of stale events is unchanged for every input, so the change is safe at all seven call
sites without touching them. A test pins this ("The rename reason never changes the decision").

### Locating the previous movie

**Context**: The manifest records only a file name (`2024-06-27 - Grillning med Grannar.mp4`). D-9 puts a dated
movie in its year folder, so a date moved to another year leaves the old movie in a folder the expected path does
not name. The gate receives the expected *path*, not the output directory.

**Explored** (prototyped in a scratch copy of the code, against the library above; results below):
- **(A) Same folder only:** `expected.with_name(manifest.output)`. One line. It found the title and location
  renames, but reported the date moved from 2023 to 2022 as `output`, the very misreport this change removes.
- **(B) Where D-9 puts the recorded name.** A dated name (`YYYY-MM-DD - …`) lives in `<output>/<YYYY>/`; an undated
  name lives in `<output>/`. `<output>` is the expected path's grandparent when the expected path sits in its own
  date's year folder, and its parent otherwise. About fifteen lines, pure. It found all three shapes on the library.
  A scratch test checked it against `render.output_relpath` for 25 old×new metadata shapes: dated, undated, with
  and without location, and year 999 (`0999`). Every pair round-tripped.
- **(C) Record the year-relative path in the manifest**, and pass the output directory to the gate. This is the
  cleanest data model. But it changes both writers (`render/`, `cli/`), all seven gate call sites (`cli/`, `api/`,
  `scheduler/`) and the manifest's meaning, and old manifests would still need (A) or (B). That is five packages,
  so it would have to be split, and would buy nothing over (B) for any name D-9 produces.
- Importing `output_relpath` into `staleness/` to avoid restating D-9 does not work. `render/orchestrator.py`
  imports `staleness.manifest`, so the import is circular. It would also give the forward rule, and the gate needs
  the inverse.

**Decision**: (B), as `recorded_output_path()` in `staleness/manifest.py`. A test pins it to `output_relpath` for
every shape the rule produces.

**Rationale**: (B) is the only in-budget option that covers every rename the operator can make: the title, the
location, the date in the same year and the date in another year. Adding or removing a date is not among them:
`require_processable` (`event/metadata.py:72-90`) refuses an event without a real date in `scan`, `render`,
`enqueue`, `adopt-renders`, the API reads and `POST /jobs`, and a save that would remove the date answers 400
`unusable_metadata`. So the undated half of D-9 matters only for a manifest written before dates were required
(change `event-metadata-resolution`). (B) inverts both halves anyway, because the round-trip test is simplest
against the whole of `output_relpath`. The one name it cannot place is an undated event whose *title* starts with
`YYYY-MM-DD - `, which no surface evaluates today. The lookup then misses, and the gate says `output`, as today.

The round-trip test is what keeps a second encoding of D-9 from drifting. The movie-assembly rule that "every
component derives the path by this one rule" is about an event's *own* path. Every call site still derives that
by `output_relpath`; this helper only locates a file the last render already wrote.

### Only a bare file name, only a regular file

**Context**: `read_manifest` accepts any string as `output` (`str(payload["output"])`, `manifest.py:92`). The
manifest is engine-written, but it is a JSON file in the event folder that a person can copy or edit.

**Explored**: In a review spike (session scratchpad, `review/spike_helper.py`, not committed), the
prototype's `.exists()` lookup cited `output_renamed` for a retitled event whose manifest recorded:
- `""`, which resolves to the year folder itself;
- `2024`, the year folder's own name;
- an absolute path to an existing file, because `Path / "/abs"` discards the left side;
- `../elsewhere.mp4`.

In each case nothing proves the event's previous movie is on disk. A bare-name check
(`Path(recorded).name == recorded`) together with `.is_file()` cites `output` for all four. It still finds the
title, location, same-year and cross-year renames (`review/spike_hardened.py`).

**Decision**: The gate looks up the recorded name only when it is a bare file name, and accepts only a regular
file (`.is_file()`), never a directory. `_DATE_PREFIX` matches ASCII digits (`[0-9]`), the only digits D-9 writes
(`date.isoformat()`, `f"{year:04d}"`).

**Rationale**: The reason claims a fact about disk. It is cited only when the engine's own kind of record names an
existing movie file, so a malformed manifest can only fall back to today's `output` and never claims a rename. It
costs one condition and the same single `stat`.

### Keep the previous movie

**Context**: The completeness critic proposed deleting or renaming the old movie after the new one verifies. The
operator decided to keep it.

**Explored**: Today's behaviour is keep: see Context, "The engine never touches a previous movie". The real
archive is an NTFS drive mounted with `ignore_case` that has dropped off USB once (memory: MOL survey). There,
deleting a 100 MB+ file automatically on a path computed from edited metadata is the riskiest thing the engine
could do.

**Decision**: The engine never deletes, moves, renames or overwrites the previous movie. The next render writes the
new path. The manifest then records the new name, the event is fresh, and the old file is an ordinary file nothing
refers to. This is recorded as a dated amendment to D-9 and as the change-detection requirement "A renamed event
keeps its previous movie". It is pinned by real renders through the CLI (`render`, and `render --force`) and
through the worker (`POST /jobs`). The one exception is the path being the same file: a render replaces whatever is
at its own expected path (D-C4). That includes a case-only rename on a case-insensitive filesystem; see Risks.

**Rationale**: Nothing is lost silently, and the operator decides. The reason's wording tells them both facts, so
the duplicate is never a surprise.

### The published wording and the interim label

**Context**: The decision requires the reason to say that the next render writes under the new name and that the
old file stays. The API publishes the enum's docstring as its schema description. The GUI needs words, and its
build fails without them: `TS2741 … Property 'output_renamed' is missing`, reproduced by adding the member to a
scratch copy of `web/` and running `npx tsc --noEmit` in `docker.io/library/node:22`.

**Explored**: Leave `labels.ts` to `renamed-label-and-zoom-bar`. That would leave `npm run build` red on `main`
until it lands, because it is gated on this change being archived. The other choice is to add one entry here.

**Decision**: The `StalenessReason` docstring says what every member means. For `output_renamed` it says: the
event's movie name (its title, date or location) changed since the last render; that render's movie is still on
disk under its old name; the next render writes the movie under the new name and leaves the old file where it is.
`REASON_LABEL` gains `output_renamed: 'movie name changed'`, the final list wording (supervisor decision; this
design first proposed the brief's example, `'renamed — renders under the new name; the old movie stays'`).
`renamed-label-and-zoom-bar` keeps the rest of the wording decision: it adds the full sentence on the page.

**Rationale**: `main` stays buildable, and the generated client already enforces the rule that a reason is never
shown as a slug.

### What does not change

**Context**: Principle IV, and the proposal rules.

**Decision**:
- No `RENDER_GRAPH_VERSION` bump: no rendered byte changes.
- The fingerprint is unchanged: the gate reads the manifest's name, not a new input.
- The manifest is unchanged: same version and keys, and nothing is written differently.
- No `reel.yaml` or `config.yaml` change, and no Alembic migration.
- No code in `api/`, `cli/`, `scheduler/` or `render/`.

**Rationale**: The only new behaviour is one more way to explain an absent expected movie.

## Code shape

`auto_reel_ng/staleness/manifest.py`:

```python
#: A D-9 movie name's ISO date prefix; its year names the folder the movie lives in.
_DATE_PREFIX = re.compile(r"([0-9]{4})-[0-9]{2}-[0-9]{2} - ")


def recorded_output_path(recorded: str, expected_output: PathLike) -> Path:
    """Where the output-naming rule (D-9) put a movie named ``recorded``, beside ``expected_output``.

    ``expected_output`` is the event's current expected path: ``<output>/<YYYY>/<name>`` for a
    dated name, ``<output>/<name>`` for an undated one. It supplies ``<output>``. A dated
    ``recorded`` name lives in its own date's year folder, an undated one directly in
    ``<output>``. ``recorded`` is a bare file name; the gate checks that before calling. Pure:
    no filesystem access. An undated title that itself starts with ``YYYY-MM-DD - `` is placed
    in that year's folder, where it is not (gate: ``output``).
    """
    expected = Path(expected_output)
    expected_year = _year_folder(expected.name)
    in_year_folder = expected_year is not None and expected.parent.name == expected_year
    output_dir = expected.parent.parent if in_year_folder else expected.parent
    recorded_year = _year_folder(recorded)
    if recorded_year is None:
        return output_dir / recorded
    return output_dir / recorded_year / recorded


def _year_folder(name: str) -> Optional[str]:
    """The year folder D-9 puts a movie of this name in, or ``None`` for an undated name."""
    match = _DATE_PREFIX.match(name)
    return match.group(1) if match else None
```

`auto_reel_ng/staleness/gate.py`:

```python
class StalenessReason(StrEnum):
    NO_MANIFEST = "no_manifest"  # no manifest to compare sub-hashes against
    OUTPUT = "output"  # the event's movie is not on disk
    OUTPUT_RENAMED = "output_renamed"  # its name changed; the last render's movie is still on disk
    EDITORIAL = "editorial"  # ─┐ one per fingerprint component, in COMPONENTS order
    ...

def evaluate(event_dir, output_path, fingerprint) -> Verdict:
    ...
    expected = Path(output_path)
    if not expected.exists():
        reasons.append(_absent_output_reason(manifest, expected))
    ...

def _absent_output_reason(manifest: RenderManifest, expected: Path) -> StalenessReason:
    """Explain an absent expected movie: renamed since the last render, or gone."""
    recorded = manifest.output
    if (
        recorded != expected.name
        and Path(recorded).name == recorded  # a bare file name, never a path
        and recorded_output_path(recorded, expected).is_file()  # a movie, never a folder
    ):
        return StalenessReason.OUTPUT_RENAMED
    return StalenessReason.OUTPUT
```

The module docstring of `gate.py` changes "the manifest's recorded output file is missing" to "the event's
expected output file is missing (with the rename told apart)". The prototype of this code passed, before the
bare-name and regular-file conditions were added:
- the existing staleness, CLI scan/render/adopt and manifest tests unchanged, except the two this change must
  update: the component-mirror test (its non-component tuple) and the OpenAPI drift test;
- 32 scratch tests for the new behaviour.

The review re-ran the code exactly as shown here (scratch copy `review/proto-hardened/`). The 32 scratch tests and
the existing `test_staleness_*.py` and `test_cli_render_staleness.py` gave 61 passed, with `-m "not requires_db"`.
The one failure was the component-mirror test this change updates.

## Failure behavior & idempotency

- **Never raises.** `recorded_output_path` is pure. `.is_file()` on a path that cannot be reached returns
  `False`: a vanished mount, or a permission error on a folder (checked on the host's Python 3.14). The gate then
  falls back to `output`, today's answer, and never claims a rename it cannot see. A recorded value that is not a
  bare file name is never looked up. An unreadable manifest is still "absent" (`no_manifest`) before any of this
  runs.
- **Read-only.** The gate still writes nothing. The extra `stat` happens only when the expected movie is absent,
  so a list of fresh events does no extra I/O, and the clip-set signal stays content-free.
- **Re-run / `--force` / worker restart.** Unchanged, because no stale/fresh decision changes:
  - a re-run of `render` skips the fresh events and renders the renamed ones;
  - `--force` renders the event regardless and still leaves the previous movie in place;
  - a worker killed mid-render leaves at most a `.part` at the *new* path, no manifest change, and the verdict
    still cites `output_renamed`;
  - the requeued job renders as before.
- **Repeated renames before a render** (A → B → C): the manifest still records A, so the gate looks for A's movie,
  and only A was ever written. After the render, A stays and C is written; B never existed.
- **Renamed back before a render** (A → B → A): the expected path is A's own and it exists, so neither reason is
  cited. If the document matches the manifest again, the event is fresh.

## Risks / Trade-offs

- **[Risk] D-9 encoded twice.** If the naming rule changes and `recorded_output_path` does not, renames could be
  reported as `output` again. → **Mitigation:** a parametrised test feeds `output_relpath` every shape (dated or
  undated × location or not × another year × year 999) as both old and new. It asserts the helper finds exactly
  the path the rule produced, so a D-9 change fails `pytest` until the helper follows.
- **[Trade-off] Duplicates accumulate by design.** Every metadata fix followed by a render leaves the previous
  movie in place. The operator decided this, and the reason says so up front. → A clean-up command or option is a
  separate, explicit decision (proposal, Non-goals).
- **[Risk] A case-only rename** (`Grannar` → `grannar`) depends on the filesystem:
  - case-sensitive (Linux/ext4): the expected path is absent and the old file exists, so the gate cites
    `output_renamed` and the next render writes a second file that differs only in case;
  - case-insensitive (the MOL NTFS mount): the expected path "exists", so neither reason is cited and the next
    render replaces the file, as today.

  Both are truthful about what the next render will do. No change. The keep requirement states the
  case-insensitive case explicitly, so "never overwrites the previous movie" does not overclaim there.
- **[Risk] A title or location containing `/`.** Nothing validates this today. D-9 then nests the movie one folder
  deeper and the manifest records only the last segment, so the lookup misses and the gate says `output`, as today.
  Validating titles is out of scope.
- **[Risk] A renamed event rendered into another output directory** (`-o` different from the last render): the
  lookup is under the *current* output directory, so it reports `output`. That is true: no movie is there.
- **[Trade-off] Wire change for one situation.** A renamed event's reasons change from `output` to
  `output_renamed`. The generated web client is the only client, and the interim label keeps it compiling. An
  untyped client (none exists) would see an unknown string.
- **[Risk] Spec window.** Between this archive and `renamed-label-and-zoom-bar`'s, the web-app scenario "A stale
  event names every reason" still says a renamed event cites "the missing output". → That change owns web-app and
  is gated on this one. The supervisor brief lists this hand-off.

## Migration Plan

Nothing to migrate: no schema, manifest or file changes. Existing manifests already record the name this rule
reads. On deploy, renamed events with their old movie on disk start reading `output_renamed`. Every other event
reads exactly as before. Rollback is reverting the commit and regenerating `web/openapi.json` and
`web/src/api/schema.d.ts`. The interim label must go with it, or `tsc` reports an excess key.
