## Why

GUI v1 (HLD **§6 phase 8**, §4.10, stack **D-8**) now renders an event from its page and from its list row
(`render-progress-screen`, slice E) and edits its clip order (`event-edit-screen`, slice D). An event whose
`reel.yaml` lists a clip that is not on disk (a MISSING clip) is still offered **Render**, and that render
always fails. The dev library shows it: `2024-09-01 - Sommarlov` lists `borttagen.mp4`, and its job fails at
probe with `File does not exist: …/2024-09-01 - Sommarlov/borttagen.mp4` (`probe/media.py:65`), whether
the page, the row or `auto-reel render` started it.

The engine keeps a MISSING entry on purpose. The CLI's adoption policy (**D-CLI3**, `project-cli`) reports
it loudly and never removes it, and the editorial write accepts it (**D-E4**, `editorial-write-api`).
Silently dropping the operator's record of a detached clip is the silent-loss class of bug this project
exists to avoid (HLD §2, problem 5: fail loud, never fabricate). So the fix belongs to the operator:
restore the file, or remove the entry. The GUI offers neither:

- Edit mode keeps every MISSING clip in the order by design ("never dropped", `event-edit-screen`), so the
  only way out is hand-editing `reel.yaml`.
- Meanwhile the page and the row keep offering a render that cannot succeed.

The API can already do the removal. This was checked against `auto-reel serve` on a copy of the dev library
(design, "What the service does with a removed entry"). A `PUT …/reel` whose chapter omits
`borttagen.mp4` answers 200 and writes `reel.yaml` without that line: its `# MISSING` comment goes with it,
and every other line stays. The next detail and list reads then report no missing clip, and the render
succeeds. This is therefore a `web/`-only change.

## What Changes

- **Edit mode can remove a missing clip from `reel.yaml`.**
  - Each MISSING row gets a **Remove** control named for its file ("Remove borttagen.mp4 from reel.yaml").
    No other row gets one. A clip that is on disk is never removed this way, so a removal never touches a
    file.
  - A removed clip leaves its chapter's play order, and the remaining clips renumber. It is listed after
    the play order, under "Removed from reel.yaml when you save", with an **Undo** control. Undo puts it
    back after the clips it followed when Edit mode opened, so removals undone in any order restore the
    chapter as read. Keyboard focus follows the clip, and each step is announced.
  - The save bar counts removals ("1 missing clip removed"). Reset restores every removed clip, and an undone
    removal leaves nothing to save. The unsaved-changes guard covers removals like any other edit.
  - Save writes the document without the clip's entry. It also leaves out the clip's own per-clip
    properties (trims, title, rotate, exclude): the engine refuses properties for a clip no chapter lists,
    as measured (400, "dangling clip properties"). Everything else goes back as read, as today.
- **A missing clip holds the render back.**
  - **Event page:** while the event lists any missing clip, the render region shows a reason instead of
    Render or Render anyway. For one clip: "borttagen.mp4 is missing from disk. Restore it, or remove it in
    Edit mode." For several: "2 clips are missing from disk. Restore them, or remove them in Edit mode."
    While the page is in Edit mode, Edit mode's own reason ("Save or leave Edit mode to render") is shown
    instead.
  - **Event list:** a row that needs a render but lists a missing clip offers no Render. Its job cell says
    "Blocked by missing clips", with an icon, beside the row's existing "N missing" badge.
  - A job already queued or running for such an event keeps its progress and its Cancel on both screens.
- **Docs:** `web/README.md` (the screens paragraph), and one sentence in HLD §4.10's slice table (row D).

## Non-goals

- **No API, engine or schema change.** `POST /jobs` still accepts an event with a missing clip. Its job
  fails loud at probe, as `auto-reel render` does. A server-side refusal (a typed conflict the CLI would
  share), and an engine error that names the fix rather than a bare absolute path, are follow-ups.
- **No removal of on-disk clips**, no ignore or un-ignore, and no chapter edits. These stay out, as in
  `event-edit-screen`.
- **No restoring or relinking of files** from the GUI. Restoring a file is a disk operation outside the app.
- **No "remove all missing" control.** Each clip is removed on its own, and Reset undoes them all. Missing
  clips are rare and few (the dev library has one), so a bulk action does not earn its place yet
  (Principle VII).
- **No distinction for excluded missing clips.** A missing clip marked `exclude: true` is skipped by the
  render, which then succeeds (measured, design "Excluded missing clips"). It still holds the render
  back, because neither the detail nor the list says whether a clip is excluded. This is recorded as a
  follow-up for the API.
- **No dev-library change.** The two-missing-clips and excluded-clip states are added ad hoc to the
  implementing agent's own library copy only (design, "Verification fixtures").

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: one ADDED requirement and four MODIFIED requirements. The modified ones are written by
  `event-edit-screen` and `render-progress-screen`. Each MODIFIED block is re-based on the archived text at
  the gate (task 1.1), so neither change's wording is lost.
  - added `Requirement: Edit mode removes a missing clip from reel.yaml on request`
  - modified `Requirement: The event page reorders clips within a chapter`: a missing clip is never dropped
    from its chapter except by the operator's removal, and a removed clip is not counted in positions
  - modified `Requirement: Saving an edit writes only what the operator changed`: the save bar counts
    removed missing clips, and a save leaves each removed clip, and its own properties, out of `reel.yaml`
  - modified `Requirement: An event's page schedules its render`: no Render or Render anyway while the event
    lists a missing clip, with the reason in words for one clip and for several
  - modified `Requirement: The event list shows live job state and offers a render`: no row Render while
    the event lists a missing clip, with the reason in words

## Impact

- **Packages:** `web/` only, plus two documentation edits.
  - `src/edit/`: `draft.ts` (the removal helpers, and the write body without removed clips),
    `EventEditor.tsx` (the removals in the draft, and the save bar's count), `ClipOrderList.tsx` (Remove,
    the removed list, Undo) and `edit.css`.
  - `src/jobs/`: `LiveJobCell.tsx` (a `blockedReason` prop and its note), `labels.ts` (the reason sentences)
    and `jobs.css` (one rule).
  - Shared screens, one localized edit each: `src/events/EventDetail.tsx` (the `blockedReason` expression the
    Edit-mode seam added) and `src/events/EventList.tsx` (one prop on the row's job cell).
  - `web/README.md`, and `docs/high-level-design.md` §4.10 (row D of the slice table, one sentence).
- **CLI vs API (Principle V):** untouched. A removal is the existing `PUT …/reel`, that is, the engine
  operation `event/editorial.py` `apply_editorial_write`. The CLI's editorial path stays hand-editing
  `reel.yaml`. The render guard reads only what the API already publishes (`EventDetailOut.missing`,
  `EventSummaryOut.missing_count`); it withholds a control and adds no behaviour to `api/`.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs are unchanged. A
  saved removal moves the editorial component, as any edit does.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, **no Alembic migration**, and no rescan.
  `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gates:** `event-edit-screen` **and** `render-progress-screen` must both be archived on main.
    `event-edit-screen` is (`2026-09-30-event-edit-screen`). `render-progress-screen` is implemented and was
    being rebased onto it during this review. This change builds on the editor, the render region and the
    Edit-mode seam between them, which `render-progress-screen` wires because it archives second.
  - **New runtime dependencies:** none (D-8's budget is unchanged).
- **Parallel changes:**
  - `job-summary-times` touches `api/` and `jobs/JobProgress.tsx`, which this change leaves alone.
  - `clip-thumbnails-screen` touches the same editor files: `ClipOrderList.tsx` (`RowBody`, `IgnoredRow`),
    `edit.css` (the row grid) and `EventEditor.tsx`.

  The overlaps are kept local (design, "Files and parallel changes"), and whichever change lands second
  rebases.
- **Size (Principle VIII):** one package, one capability delta and 8 tasks.
