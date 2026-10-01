## Why

The title, date and location of an event all feed its movie's path (**D-9**, HLD §7 and §4.3:
`<output>/<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`). GUI v1 made changing them one click, and the
staleness gate (HLD §4.13, change-detection) then says something false. After a retitle, the gate finds no file
at the *new* expected path and cites `output`, which the GUI shows as "movie file missing". The movie is not
missing: it is on disk under the name the last render gave it. The final end-to-end pass of GUI v1 found this
(completeness critic, verified and not refuted). On 2026-10-01 the operator agreed to the fix: a precise reason
instead of "missing", and a recorded rule for the old file.

Reproduced on a scratch dev library built by `scripts/make_dev_library.py`, with its own database, a `serve` on
port 8123, and `main` at `93721b3`:

- `2024-06-27 - Grillning med grannar`: rendered to `library-output/2024/2024-06-27 - Grillning med Grannar.mp4`
  (135 721 684 bytes; the manifest records that name), then retitled `Grillkväll med grannarna`.
  `auto-reel scan` prints `stale: editorial, output`. `GET /api/v1/events` and the detail read both return
  `["editorial", "output"]`, and the GUI reads "edited since last render, movie file missing".
- The same holds after a GUI-style `PUT …/reel` that changes the location (`2024-06-21 - Midsommar - Dalarna` →
  `Leksand`, same year folder). It also holds for a date moved to another year (`2023-06-23` → `2022-06-23`): the
  old movie stays in `2023/` and the new expected path is in `2022/`. The PUT's own echoed verdict already says
  `output`.
- A movie that is really gone (`2024-07-14 - Kalas.mp4` deleted) reads exactly the same: `["output"]`. Today the
  operator cannot tell "renamed" from "deleted".

The cause is in `auto_reel_ng/staleness/gate.py:74-75`. `evaluate()` appends `OUTPUT` whenever
`Path(output_path)` does not exist. Every caller computes that path from the *current* metadata (`cli/commands.py`
`:305`, `:426`, `:652`, `:958`; `api/events_read.py:421`; `api/routes/jobs.py:119`; `scheduler/worker.py:269`). The
manifest's recorded `output` (`staleness/manifest.py:37`, read at `:92`, written as `output_path.name` at
`render/orchestrator.py:473` and `cli/commands.py:983`) is written but never read. Reporting a movie as missing
when it is on disk is a false fact on the operator's screen. Principle I ("never fabricate", HLD §2 row 5)
applies to status as much as to metadata.

HLD §6 **phase 8** (GUI v1): a follow-up decided after the final end-to-end pass. It refines §8.14's settled
edge case "missing/partial output" and depends on no open §8 research item.

## What Changes

- **A new staleness reason, `output_renamed`** (`StalenessReason.OUTPUT_RENAMED`), in the gate's closed
  vocabulary. The gate cites it *instead of* `output` when three things hold:
  1. the event's expected movie is absent;
  2. the manifest's recorded output name differs from the expected name;
  3. the recorded name is a bare file name, and a regular file with that name still exists where the output-naming
     rule puts a movie of that name, under the same output directory: its date prefix's year folder, or the output
     directory itself for an undated name.

  Otherwise the gate cites `output`, as today, for a movie that is really gone. So Grillning reads
  `["editorial", "output_renamed"]`, and Kalas keeps `["output"]`.
- **No event changes between stale and fresh.** `output_renamed` only replaces `output`, in exactly the cases where
  `output` would have been cited. Every gate call site makes the same decision as before: `render`'s filter,
  `enqueue`, `POST /api/v1/jobs`, the worker's claim-time recheck and `adopt-renders`.
- **The previous movie is kept: decided and recorded.** The engine never deletes, moves, renames or overwrites the
  movie the last render wrote when an event's path changes. The next render writes the new path beside it and
  records the new name in the manifest, and the event is fresh again. The old file stays as an ordinary file that
  the operator may delete. This is what the code already does (only `.part` files are ever removed,
  `render/orchestrator.py:263`). The change makes it a stated rule, pinned by a test that really renders. The
  reason's published description says the same: the next render writes under the new name and the old movie
  stays. A render still replaces the file at its own expected path, as every render does. On a case-insensitive
  filesystem a case-only rename names the old file itself, so that file is replaced (spec, "A renamed event keeps
  its previous movie").
- **The API publishes the new member.** `StalenessOut.reasons` already uses the gate's enum
  (`api/schemas.py:89`), so the list, the detail, and the verdict echoed by `PUT …/reel` cite `output_renamed` with
  no route change. `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated; the drift test enforces it.
- **The client build stays green.** `REASON_LABEL` in `web/src/events/labels.ts` is an exhaustive
  `Record<StalenessReason, string>`, so the regenerated union fails `tsc --noEmit` (`TS2741 … 'output_renamed' is
  missing`, reproduced on a scratch copy of `web/`). This change adds that one entry, worded as the design says.
  Change `renamed-label-and-zoom-bar` keeps ownership of the wording (short on the list, full on the page).
- **`auto-reel scan` prints the new reason** with no CLI code change (`stale: editorial, output_renamed`): it joins
  the verdict's reasons (`cli/commands.py:445`).
- **Spec text matches the code.** change-detection's "Staleness gate" said "the recorded output file is missing".
  The gate has always checked the event's *expected* path; the text now says so, and the reason rule follows it.
- **Docs:** a dated D-9 amendment in `docs/high-level-design.md` (keep the old movie; the reason). README's
  change-detection section names `output_renamed` and what to do about the old file.

## Non-goals

- **No deleting, moving or renaming the old movie**, automatically or on request. The operator agreed to keep it.
  A "remove the previous movie after a verified render" option is a separate decision, with its own risks on a
  shared NTFS archive mounted with `ignore_case`.
- **No new field naming the old and new paths** in the verdict or in `scan`'s output. The reason says what happens.
  Showing the file names is a later API addition if the GUI wants it.
- **No manifest schema change.** The manifest keeps recording the output *file name*; nothing writes a
  year-relative path. Locating the old movie from its name and D-9 covers every rename the operator can make: the
  title, the location, and the date within a year or across years (design, "Locating the previous movie"). Every
  surface refuses an event without a real date (`event/metadata.py` `require_processable`, and a save that would
  remove the date is a 400), so the undated half of D-9 only matters for a manifest written before dates were
  required. The helper still inverts both halves exactly.
- **No GUI wording beyond the one label entry**, and no web-app spec change. The web-app scenario "A stale event
  names every reason" says a renamed event cites "the missing output". Once this change is archived that is
  outdated, and correcting it belongs to `renamed-label-and-zoom-bar`, which owns the web-app capability in this
  round.
- **No change to a case-only rename on a case-insensitive filesystem** (the MOL archive): the expected path exists
  there, so no output reason is cited and the next render replaces that file, as today.
- No change to the fingerprint, the render graph, the collision rule, or `adopt-renders`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-detection`: `Requirement: Staleness gate` defines staleness on the event's expected output path (a
  text correction to match the code). It adds `output_renamed` to the closed vocabulary with its exact rule, and
  states that the reason never changes whether an event is stale. A new
  `Requirement: A renamed event keeps its previous movie` records the keep decision.
- `api-service`: `Requirement: Staleness reasons are a closed, published vocabulary` publishes `output_renamed`.
  Every read and write that echoes a verdict cites it for a renamed event. No existing reason's wire value
  changes, and a client's exhaustive label map must name the new member to compile.

## Impact

- **Baseline:** written against `main` at `93721b3`.
- **Dependencies:** gate: none. Unblocks `renamed-label-and-zoom-bar`, which labels the reason and is gated on
  this change being archived.
- **Packages:** `staleness/` only: `gate.py` (the enum member, the reason rule, docstrings) and `manifest.py` (a
  pure helper that locates the recorded movie). `api/` has no code change: the enum flows through `StalenessOut`.
  Its published artifacts are regenerated (`web/openapi.json`, `web/src/api/schema.d.ts`). `web/`: one
  `REASON_LABEL` entry. Tests: `test_staleness_gate.py`, `test_staleness_manifest.py`,
  `test_cli_render_staleness.py`, `test_api_events.py`, `test_api_editorial_write.py`, `test_api_openapi.py`,
  `test_editorial_write_e2e.py`.
  Docs: HLD D-9, `README.md`, and the `make_dev_library.py` comment that names Grillning's reasons.
- **CLI vs API (Principle V):** both read the verdict through the same gate. Neither has a code change. `scan`
  and every API read cite the new reason the same way.
- **Complexity (Principle VII):** about twenty lines: one enum member, one helper that inverts D-9's placement
  of a dated or undated name, and one branch in `evaluate()` that looks up only a bare file name and only a
  regular file. The helper restates where D-9 puts a file, so a test
  checks it against `render.output_relpath` for every shape the rule produces. If D-9 changes, that test fails
  (design, Risks).
- **Dependencies (third-party):** none.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** The fingerprint's inputs are unchanged and so
  is every stale/fresh decision. Only the reason that explains an absent expected movie can differ.
- **Schemas:** no `reel.yaml`, `config.yaml` or manifest change, **no Alembic migration**, no rescan. The OpenAPI
  enum `StalenessReason` gains `output_renamed`.
- **Clients:** a renamed event's reasons change on the wire from `output` to `output_renamed`. The only client is
  the generated web app, and its build fails until the reason has a label, which this change adds.
- **Size (Principle VIII):** two capability deltas (change-detection, api-service), one Python package with code
  changes (`staleness/`), plus regenerated API artifacts. 10 tasks, including one baseline task and two validation
  tasks.
