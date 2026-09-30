## Why

GUI v1 (HLD **§6 phase 8**, §4.10, stack **D-8**) promises "drag-reorder clips (persist to `reel.yaml`), edit
basic metadata". Slices B and C answer "what needs a render" and "what is in this event", but both screens
only read. To change a clip's place or fix a title, the operator still opens `reel.yaml` in an editor, and
legacy auto-reel offered nothing better (HLD §2, problem 8). This change is **slice D**: the event page
learns to edit.

The API side is complete. `editorial-write-api`, `editorial-read-api` and `editorial-client-contract`
landed the following, and nothing more is needed:

- `GET /api/v1/events/{id}/reel`: the document as authored, with a strong `ETag`
- `PUT …/reel`: a complete-state write guarded by `If-Match`, answering 400 (with
  `failure: unusable_metadata` for a missing, impossible or future date, or a missing title), 404, 412 and
  502 by cause

This is therefore a pure `web/` change, following the precedent that screens carry no backend edits
(Principle VIII).

The "Needs attention" rows also get a way out. The MOL archive has three folders whose names give no usable
date: two give a year only, and one an impossible date (`editorial-client-contract` proposal). Until now the
only fix was hand-editing `reel.yaml`, which the list's own detail text asks the operator to do. The write
endpoint accepts a date for exactly those events, so their page can offer the form.

`web-design-system` lands the shared UI this change builds on: `Icon`, `Dialog`, toasts, button classes,
the `markEventsChanged()` signal, and the CSS layers. `editorial-chapter-roundtrip` fixes the engine so a
save keeps the end-of-line comments on clip entries (today every PUT drops them, even an unmodified one,
against Principle II). This editor resends every chapter on each save, so it would make that loss the
common path. Both changes are this change's gates.

## What Changes

- **The event page gets an Edit mode.** It is a toggle on the page, with no new route. Entering it reads
  the editorial document (`GET …/reel`, with its `ETag`) next to the detail the page already shows. While
  editing, the chapters are shown as reorderable lists, with the same per-clip facts as the tables.
- **The operator can reorder clips within a chapter** in three ways:
  - by dragging a row's handle (mouse, pen or touch). A dragged row stops at its chapter's edge.
  - with the keyboard on the handle: Space or Enter lifts, the arrows move, Space or Enter drops, Esc
    cancels. Custom announcements such as "s1710002.mp4 moved to position 3 of 4" tell a screen reader
    what happened.
  - with per-row **Move up** and **Move down** buttons, which keep focus on the moved row

  Cross-chapter moves stay v3 (§4.10). Ignored clips are listed at the end of their chapter, dimmed and
  not movable, because they are not part of the play order. A missing clip keeps its place in the order
  and is never dropped. A NEW clip in a reordered chapter joins `reel.yaml` where the operator put it, and
  the editor says so before the save.
- **The operator can edit the title, date, location and description.**
  - The form shows what `reel.yaml` itself says.
  - An empty field inherits its value, and the value it inherits from the folder name is shown beside it
    ("From the folder name: 2024-06-21"). A field the operator empties says it will inherit.
  - The date is a date field. A half-typed date blocks Save rather than silently clearing the date.
  - When the service refuses a date or title as unusable, the error appears at those fields with the
    service's own explanation.
- **Saves are explicit, and they write only what the operator changed.**
  - A sticky save bar appears while there are unsaved changes. It says what changed (the fields, "2 clips
    moved", "adds 1 new clip to reel.yaml") and offers Reset and Save.
  - Save sends the document exactly as it was read, with only the operator's edits applied. Untouched
    chapters, per-clip trims, the `ignore` list and the `look` override are sent back unchanged. The request
    carries `If-Match`.
  - While a save is in flight the editor is locked, and the pressed Save (or Retry, or Overwrite) shows it is
    busy and keeps keyboard focus.
  - After a successful save, the page says "Saved", leaves Edit mode, and re-reads the event, which then
    shows it needs a render. The list re-reads the next time it is shown, through `markEventsChanged()`.
    A save never enqueues a render.
- **A failed save keeps the operator's edits.** Failures are reported by cause:
  - a conflict (412) offers "Reload latest (discard my changes)", or "Overwrite with mine" after a
    confirmation
  - an unusable date or title (400) is shown at the fields
  - a vanished event (404) is reported as gone
  - a refused save (502, for example a read-only archive) shows the reason and offers Retry
  - an unreachable service offers Retry
- **Unsaved edits are never lost silently.** While edits are unsaved, the page asks "Discard unsaved
  changes?" in these cases:
  - closing or reloading the tab (the browser's own prompt)
  - Back, Forward, a link, or a typed address
  - Refresh
  - leaving Edit mode
- **"Needs attention" rows open their event's page.** When the page's read fails because the event's date
  or title is unusable, it shows the failure *and* the metadata form. Saving a real date makes the event
  readable, and the page re-reads it (dev fixture `2024-02-30 - Omöjligt datum`).
- **One new dependency, the drag-and-drop library that D-8 budgets for.** It is the legacy `@dnd-kit`
  line: `@dnd-kit/core@^6.3.1`, `@dnd-kit/sortable@^10.0.0` and `@dnd-kit/utilities@^3.2.2`. This is one
  MIT library family (see Impact).

## Non-goals

- **No cross-chapter moves, no chapter create, rename or reorder, and no ignore or un-ignore.** Those
  belong to the v3 timeline editor, or to later slices that show a need for them. The editor never changes
  the `ignore` list, the chapter list, or per-clip properties.
- **No trims, rotation, title-card flag or `look` editing** (v2 look editor and analysis review, §4.10).
- **No render button, live progress or cancel.** Those are slice E, `render-progress-screen`.
- **No merge of concurrent edits.** A conflict offers reload or overwrite, not a three-way merge.
- **No autosave and no undo history** beyond Reset. The PUT is a whole-document write under `If-Match`, so
  saving on every drop would open a conflict window per drag.
- **No virtualisation.** A 400-clip chapter is checked for responsiveness. Events that large are rare (the
  largest renderable one has about 380 clips).
- **No API, engine or schema change**, and no dev-library change. The dev library's events cover every state
  the screen shows day to day. Three verification-only states (a 400-clip chapter, a first reorder across
  two folders, an unparseable `reel.yaml`) are added ad hoc in the implementing agent's own library copy
  (see design, "Verification fixtures").
- **No engine change.** The comment loss on clip entries (`event/editorial.py` `_apply_chapters` empties and
  refills every chapter's clip list) is fixed by `editorial-chapter-roundtrip`, a gate of this change. This
  change only checks, in its browser pass, that a save keeps those comments.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: six ADDED requirements. No existing requirement is modified: `web-design-system` already
  removed the "read-only" sentences and added "Reading a screen never changes state", and the
  cross-change ownership rule keeps this change out of requirements that `render-progress-screen` may
  also touch.
  - `Requirement: The event page reorders clips within a chapter`
  - `Requirement: The event page edits the event's metadata`
  - `Requirement: Saving an edit writes only what the operator changed`
  - `Requirement: A failed save keeps the operator's edits and says why`
  - `Requirement: Unsaved edits are never discarded silently`
  - `Requirement: Events that need attention open a page that can fix their metadata`

## Impact

- **Packages:** `web/` only, plus two documentation lines (`docs/high-level-design.md`: §4.10's slice-table
  row D only, and the D-8 budget bullet).
  - New files: `src/api/reel.ts` (the editorial read and write) and `src/edit/` (`EventEditor.tsx`,
    `ClipOrderList.tsx`, `MetadataForm.tsx`, `SaveBar.tsx`, `draft.ts`, `unsaved.ts`, `edit.css`).
  - Small, localized edits to shared files:
    - `src/events/EventDetail.tsx`: the Edit toggle, the editor mount point, the guarded Refresh, and the
      form on an unusable-metadata failure
    - `src/events/EventList.tsx`: the "Needs attention" folder name becomes a link
    - `src/route.ts`: a navigation-guard hook, about 50 lines
  - `package.json` and `package-lock.json`, and `web/README.md`.
- **CLI vs API (Principle V):** untouched. The page uses the existing `GET` and `PUT …/reel`. The write is
  the engine operation `event/editorial.py` `apply_editorial_write`, which any client can call. The CLI has
  no editorial-write subcommand: its editorial path stays hand-editing `reel.yaml`, which it reads through
  the same engine. This change adds no behaviour to `api/`.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs are unchanged. A
  save moves the editorial component, exactly as a hand edit does.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, **no Alembic migration**, and no rescan.
  `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gates:** `web-design-system` **and** `editorial-chapter-roundtrip` must both be archived on main
    first.
    - `web-design-system`: this change uses its `Icon`, `Dialog` (with `initialFocus`), `Pill`, `Alert`,
      `SkeletonRows`, toasts (with `--toast-inset-bottom`), button classes, `CLIP_STATUS_LOOK`,
      `markEventsChanged()`, and CSS layers.
    - `editorial-chapter-roundtrip`: an unchanged chapter's clip list is left untouched by a PUT, and a
      reordered one keeps each entry's comment, so the editor's whole-document saves keep `reel.yaml`'s
      comments (Principle II).
  - **New runtime dependencies (Principle VII, D-8's one drag-and-drop library):** `@dnd-kit/core@^6.3.1`,
    `@dnd-kit/sortable@^10.0.0` and `@dnd-kit/utilities@^3.2.2`. They are MIT licensed, with peer
    `react >=16.8`, and transitively pull in only `@dnd-kit/accessibility` and `tslib`.
  - **Justification:** accessible pointer, touch and keyboard sorting with screen-reader announcements is
    exactly the capability D-8 set aside a slot for. Native HTML5 drag-and-drop has no touch support. The
    successor `@dnd-kit/react` 0.x has an open StrictMode bug (#2116) that breaks dragging under this app's
    `<StrictMode>` (`web/src/main.tsx:12`). The heavier or non-conforming alternatives are weighed in
    design.md.
  - Not added: `@dnd-kit/modifiers`, a form library, or a state library.
- **Parallel work:** `render-progress-screen` is implemented at the same time in another worktree.
  File ownership is declared in design.md. The seam in `EventDetail.tsx` is fixed now, not at merge time
  (design, "Where it mounts"): `load()` never touches `editing`, every Edit-mode exit sets `editing` to false
  and then calls `load()`, and the editor's draft survives a new `event` object. Whichever change is archived
  second wires the rest (re-reads the page starts by itself are deferred while editing, and `RenderControl`
  gets `blockedReason` while editing) and runs one combined browser check (task 6.1).
- **Size (Principle VIII):** one screen mode on an existing page, one capability delta (`web-app`), and one
  package. There are 11 tasks; the documentation edits ride with the page wiring (task 4.1) to make room for
  the conditional integration task (6.1).
