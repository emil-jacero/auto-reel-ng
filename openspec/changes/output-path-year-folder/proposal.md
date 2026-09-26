## Why

`movie-assembly` says the output name `<title> - <location>.mp4` is "carried over from auto-reel". It
was carried over only in part. Legacy auto-reel wrote each movie to `<output>/<year>/<name>`
(`movie_merge/project/processor.py:205`: `output_path / str(movie.metadata.year) / filename`). The port
kept the name and **dropped the year folder**. Every event in the library now shares one flat
namespace, and any two events with the same title and location resolve to the **same output file**.

A dogfood run on 2026-09-26 showed the failure. Two events, `2023/2023-06-23 - Midsommar` and
`2024/2024-06-21 - Midsommar`, both rendered to `out/Midsommar.mp4`, and `render` reported `OK` for
both. The second render overwrote the first. Both events then evaluated **fresh** on every later run,
because each has its own manifest and the shared file exists. The 2023 movie is gone, and the tool
will never say so. This breaks Principle I (a failure reported as a success) and the staleness
contract (Principle IV: a fresh verdict must mean the output reflects this event's inputs). Recurring
event names ("Midsommar", "Julafton", birthdays) make this the normal case for a multi-year library,
not an edge case. It blocks the first library-wide run.

Change detection's one-time adoption step (D-C7, `adopt-renders`) is also affected. That step exists
for "years of already-rendered footage", and that archive was written by auto-reel into year
folders. With a flat lookup, `adopt-renders <root> -o <archive>` finds none of those outputs, so
deploying the gate would mean a full-archive re-render: the outcome D-C7 was written to prevent.

This corrects HLD **§6 phase 4** (render pipeline, output naming) and the phase 7 CLI (§4.11). It
lands before GUI v1 (phase 8) continues, because it is a precondition for processing a real library.

## What Changes

- **Output path gains the legacy year folder.** An event with a date renders to
  `<output>/<YYYY>/<title>[ - <location>].mp4`, where `YYYY` is the event's `metadata.date` year. An
  event without a date renders to `<output>/<title>[ - <location>].mp4` at the output root, which
  matches legacy (`year` was `""` when the date was absent). The year is never guessed. One engine
  function computes the path relative to the output directory. Every site that builds an output path
  uses it: `render`, `scan`, `enqueue`, `adopt-renders`, the worker, and the API's staleness and job
  routes.
- **Output-path collisions fail loud.** `render`, `enqueue` and `adopt-renders` check the events they
  selected before they act. When two or more events resolve to the same output path, every event
  involved is reported as an error that names the other events and the shared path. None of them is
  rendered, enqueued or adopted, and the command exits non-zero. The other events proceed (per-event
  isolation). Paths are compared case-insensitively, so a collision that a case-insensitive archive
  filesystem would create is caught too.
- **BREAKING — the default output directory moves outside the project root.** With no `-o` and no
  `config.yaml` `output`, movies go to the sibling folder `<parent>/<root-name>-output` instead of
  `<root>/output`. Year folders inside `<root>/output` would otherwise be walked by the `year-event`
  layout as a year containing "events" made of rendered movies. The `flat` layout already walks
  `<root>/output` as an event today. The CLI, the worker and the API resolve this default through one
  helper.
- The finalize step creates the year folder before writing `.part`. `.part` and the final file stay
  in the same directory, so the atomic rename is unchanged.

## Non-goals

- **No automatic disambiguation** (`Midsommar (2).mp4`, date prefixes). A suffix that depends on scan
  order renames outputs when events are added. A date prefix breaks compatibility with the legacy
  archive that `adopt-renders` exists to adopt. The operator resolves a collision by editing `title`
  or `location` in `reel.yaml`.
- **No collision check in the API or the worker.** `POST /api/v1/jobs` and the worker each handle one
  event and would need a whole-project walk to see siblings. The year folder narrows the remaining
  risk to the same title and location within one year. The GUI that would drive the API path is not
  built yet. A follow-up can add the check when that path is used.
- **No collision reporting in `scan`.** `render --dry-run` surfaces the collision without writing
  anything. After this change, colliding events are never rendered, so `scan` does not report them as
  fresh.
- **No configurable output template.** One layout, the legacy one (Principle VII).
- **No manifest change.** `render-manifest.json` keeps recording the output *filename*, which stays
  accurate. The gate never reads that field: it recomputes the expected path and checks whether it
  exists. Recording the year-relative path would be a third capability delta with no behavioral
  effect.
- **No migration of outputs already rendered flat by auto-reel-ng.** Those exist only in dev
  scratch directories. After this change they evaluate `stale: output` and re-render into year
  folders.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `movie-assembly`: `Requirement: Output naming and overwrite control`. The output path gains the
  `<YYYY>/` folder taken from the event date, or none when the date is absent.
- `headless-cli`: new `Requirement: Batch commands refuse colliding output paths` for `render`,
  `enqueue` and `adopt-renders`, and new `Requirement: Default output directory sits outside the
  project root`.

## Impact

- **Packages:**
  - `config/`: the default-output-directory helper.
  - `render/`: the output-path function, the collision finder, and creating the year folder at
    finalize.
  - `cli/`: the collision check in `render`, `enqueue` and `adopt-renders`, and swapping in the path
    helper at every call site.
  - `scheduler/` and `api/`: swapping in the path helper only.
  - `staleness/` is called exactly as before.
- **CLI vs API (Principle V):** the engine function is shared by both. The collision check is
  CLI-only (see Non-goals). That direction is allowed: the API gains no behavior the CLI lacks.
- **Rendered output:** the bytes are unchanged for identical inputs, so there is **no
  `RENDER_GRAPH_VERSION` bump**. Only the file's location changes.
- **Staleness fingerprint inputs:** unchanged. The gate's missing-output check now looks at the
  year-folder path.
- **Schemas:** no `reel.yaml` change, no project `config.yaml` change, no manifest change, **no
  Alembic migration**, and no rescan.
- **Operator-visible:**
  - Outputs move into year folders.
  - `adopt-renders` becomes usable against the legacy archive.
  - A batch containing a collision now exits non-zero where it used to "succeed".
  - Without `-o` or `config.yaml` `output`, movies land in `<parent>/<root-name>-output`, not
    `<root>/output`.
- **Dependencies:** none added.
- **Size (Principle VIII):** one concern, output identity. The path rule and the collision check ship
  together because either one alone still loses movies silently. The year folder alone leaves
  same-year collisions. The check alone would flag every recurring event name across the whole
  library.
