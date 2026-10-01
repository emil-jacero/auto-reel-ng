## Why

GUI v1 (HLD **§6 phase 8**, §4.10) was verified end to end on main 93721b3. The user then decided two open
points (2026-10-01): a renamed event's verdict gets its own reason, and the save bar is fixed at 400 %
zoom. This change is the GUI's part of both. Both problems were reproduced on main before this proposal
(design, "Findings, reproduced"):

- **A renamed event says its movie is missing.** The movie's file name is built from the event's date,
  title and location (**D-9**, HLD §7). So after a title change, `2024-06-27 - Grillning med grannar`'s list
  row and page both read "Needs render · edited since last render, movie file missing", although the movie
  is on disk under its old name. `output-renamed-reason` (Z2, this change's gate) gives the verdict a new
  reason for this case, `output_renamed`. The previous movie is kept, never deleted, and the plain `output`
  reason stays for a movie that really is gone. Labels are exhaustive over the generated vocabulary (web-app,
  "Screen labels are exhaustive"). With only the schema regenerated, `tsc` stops at
  `src/events/labels.ts(11,14)` with TS2741, a missing property for the new member. So Z2 lands one
  provisional entry, the brief's example `'renamed — renders under the new name; the old movie stays'`, and
  leaves the wording to this change. Those words take four lines (81 px) of Grillning's verdict cell at 1280,
  against three for today's "movie file missing". "renamed" alone is also ambiguous: the folder, the event
  or the file? The words must say what a render will do: the next render writes a new movie under the new
  name, and the old movie stays.
- **At 400 % zoom a failed save hides the whole editor.** In a 320 × 256 window (1280 × 1024 at 400 %), a
  conflict makes the sticky `.save-bar` 322 px tall (its card 306 px, its top at y = −66), and a write
  failure makes it 305 px. That is taller than the window. Shift+Tab from Save reaches 18 focus stops, and
  15 to 16 of them are fully hidden under the bar. The plain "Unsaved changes" bar is 117 px there (46 %
  of the window). After the first Move, it leaves the moved clip's row 28 % visible, and at 320 × 230 the
  focused Move button is fully hidden. That breaks WCAG 2.4.11 and edit-mode-polish's rule that a moved
  clip's control is "fully visible together with its whole row".

## What Changes

- **The new reason in words** (`web/src/events/labels.ts`, member `output_renamed`):
  - On the list, the short words **"movie name changed"**, in the same comma-joined reasons line as today.
  - On the event page, the same words, and under them, on a line of their own: **"The next render saves
    the movie under its new name. The movie under its old name stays on disk."** This text comes from a
    new exhaustive map, `REASON_NOTE: Record<StalenessReason, string | null>`, which is null for every other
    reason. `StalenessCell` gains an optional `explain` prop. The page's render panel passes it, which is a
    one-line change in `EventDetail.tsx`. The list does not pass it and is unchanged.
  - No screen names a file. The response carries only the reason (never fabricate, Principle I).
- **The save bar rests in the page when it would hide the editor** (`web/src/edit/EventEditor.tsx`,
  `edit.css`):
  - While the bar's height is more than **two fifths** of the window's height, it is no longer sticky. It
    takes `data-rests`, and `position: static` puts it in flow after the last chapter.
  - At two fifths or less it stays held at the window's bottom, as today. Two fifths is edit-mode-polish's
    own budget for a failed save at 390 × 844, so phone and desktop windows keep the held bar.
  - The decision is re-made whenever the bar's content changes (a layout effect, before the answer's focus
    scroll), when its size changes (the existing `ResizeObserver`), and when the window resizes or zooms (a
    new `resize` listener).
  - The existing answer effect then scrolls the focused control (Save, or the alert) into view, so the page
    scrolls to the bar.
  - When the bar goes from held to resting while one of its controls has keyboard focus, for example a zoom
    to 400 % right after a failed save, that control is scrolled into view. The first prototype left Save
    0 % visible after such a zoom, with its card more than 800 px below the window (design, "A focused
    control follows a bar that starts to rest").
- **The toast contract in both states:**
  - While the bar is held, `--toast-inset-bottom` stays the bar's height.
  - While it rests, the property is removed, because nothing is held at the window's bottom. Otherwise
    `html`'s `scroll-padding-bottom` would reserve 322 px of a 256 px window.
  - `keepToastsClearOf(bar)` stays registered. `ToastRegion` already places toasts above or below a bar that
    rests in the page, so no toast overlaps the bar in either state (measured).
- **Spec:** the web-app scenario "A stale event names every reason" changes. It currently describes a
  renamed event as "the missing output", which Z2 makes false. Two requirements are added: the page's note,
  and the resting bar. "Notifications never cover the save bar" scopes its focus sentence to a bar that is not
  resting for its height, and to no bar (supervisor decision, option (a); design, "Supervisor decisions").
- **Docs:** `web/README.md`: the reasons and the dev library's stale kinds, the Edit-mode paragraph, and the
  Toasts bullet's sentence on `--toast-inset-bottom`.

## Non-goals

- **No engine, API or schema change.** `output-renamed-reason` owns the reason, its slug, the manifest
  comparison, the CLI `scan` wording, `web/openapi.json` and `web/src/api/schema.d.ts`, and the "keep the
  old file" note in HLD D-9. This change neither regenerates nor edits those files.
- **No file names in the note.** Naming the old or the new movie would need the service to publish them.
  A client-side guess at D-9's naming rule is out (Principle I, thin client, Principle V).
- **No action on the old movie.** Nothing deletes, renames or offers to remove it (user decision: keep it).
- **No change to toast placement** (`web/src/ui/ToastRegion.tsx`, `toast.ts`). With one notification shown
  and the bar resting in a short window, the clip row just above the bar can sit under the notification.
  Main already has this at 320 × 568 (15 focus stops), and this change cuts it to 4 there. At 320 × 256 it
  is new: 5 stops, one of them fully covered, where main hid 15 stops under the bar. Both break the focus
  sentence of web-app's "Notifications never cover the save bar" as archived, so this change narrows that
  sentence to a bar that is not resting for its height, and to no bar (supervisor decision, option (a)). A fix
  (room kept above a resting bar, and a `ToastRegion` that places itself again when the bar moves) needs
  `web/src/ui/` and is a follow-up (option (b)).
- **The held bar's budget at 390 × 844 is unchanged** (a third with a conflict, two fifths with a failure),
  and so are its compact layout, its single primary action and the sticky page and panel headers.
- **No new dependency, token, component or animation.** Principle VII: one constant, one attribute, one CSS
  rule, one map and one prop.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - MODIFIED `Requirement: The event list shows every event with its render state`. Only its "A stale event
    names every reason" scenario changes: a renamed event cites the changed movie name, not a missing movie.
    A scenario is added for a movie that really is missing.
  - MODIFIED `Requirement: Notifications never cover the save bar`. Only its focus sentence changes: it holds
    while the bar takes two fifths of the window or less, and with no bar. While the bar rests for its height,
    a notification may cover a control just above it, never the bar.
  - ADDED `Requirement: The event page says what a render does when the movie's name changed`
  - ADDED `Requirement: Edit mode's save bar rests in the page when it would hide the editor`

## Impact

- **Packages:** `web/` only, plus `web/README.md`.
  - `src/events/labels.ts`: `REASON_LABEL`'s new entry, and `REASON_NOTE`
  - `src/events/common.tsx`: `StalenessCell`'s `explain` prop
  - `src/events/EventDetail.tsx`: `RenderPanel` passes `explain`. One line.
  - `src/events/detail.css`: `.render-panel .reason-note`
  - `src/edit/EventEditor.tsx`: `HELD_BAR_MAX_SHARE`, `placeBar`, the bar effect and one layout effect
  - `src/edit/edit.css`: `.save-bar[data-rests]`
- **CLI vs API (Principle V):** untouched. Words for a published reason are the client's job. No behaviour
  moves into `api/`.
- **Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump, and the staleness fingerprint inputs are
  unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, no Alembic migration and no rescan.
  `web/openapi.json` and `schema.d.ts` arrive from the gate as they are.
- **HLD:** no edit. The keep-the-old-movie rule is D-9's amendment, made by `output-renamed-reason`. The words
  for a reason and the two-fifths rule are client layout inside D-10's visual system. They live in the
  web-app spec and `web/README.md`, and no other decision depends on them. §6 phase 8's status is unchanged.
- **Dependencies:**
  - **Gate:** `output-renamed-reason` (Z2) archived on main, with `output_renamed` in `StalenessReason` (Z2's
    proposal). Task 1.1 re-checks the name. If Z2 landed another name, this change uses that one.
  - **Coordination:** Z2's own `tsc` gate cannot pass without an entry in `REASON_LABEL`. So Z2's task 4.1
    adds `output_renamed: 'renamed — renders under the new name; the old movie stays'`, and this change
    replaces those words (design, "Coordination with output-renamed-reason"; Open Questions).
  - **Parallel:** `adopt-into-folder-chapter` (Z1) is engine/CLI only and shares no file.
  - **New runtime dependencies:** none. D-8's budget is unchanged.
- **Size (Principle VIII):** one package, one capability delta (two MODIFIED and two ADDED requirements),
  and 8 tasks.
