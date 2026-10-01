## Why

auto-reel took its chapters from subfolders and nothing else (HLD §2, "chapter-from-subdirectory
convention"), and they never reached the container (§2, learning 3). auto-reel-ng made them real: each
named chapter gets its own title card and a chapter marker (decision D-E), and `reel.yaml` holds the
chapter list (D-2). Since **D-12** a chapter's name also decides where clips that arrive later in its
folder go. The engine and the API have carried the whole chapter list since `editorial-write-api` (the
complete-state `PUT …/reel`, D-E2).

The GUI cannot touch any of it. GUI v1's Edit mode (HLD **§6 phase 8**, §4.10 slice D) reorders clips
**within** a chapter and nothing more: it cannot add a chapter, rename one, delete one, or move a clip into
another. §4.10 put "reorder across chapters" in v3, with the timeline editor. So to split an event into
chapters, or to give a chapter a real name instead of its folder's, the operator still renames folders or
hand-edits `reel.yaml`. That is the auto-reel habit this rewrite exists to retire.

The operator asked for this ("do 1 and 2"). This change is item 1, chapter management. Item 2, cut editing
with typed times, is `clip-cuts-screen`, which builds on this one.

## What Changes

- **Chapter controls in Edit mode** (the event page, no new screen):
  - **Add chapter**, after the last chapter. A dialog asks for the name. The chapter is added empty, at the
    end.
  - **Rename…** on every named chapter, in the same dialog. The event's own chapter (`""`, shown as `Main`)
    keeps no name: its title card is the event's (D-E), and clips without a chapter of their own join it
    (D-12). The page says so beside it.
  - **Move up** and **Move down** on each chapter, when the event has more than one.
  - **Delete**, only once the chapter plays no clip. Until saved, a deleted chapter stays listed in its
    place, with **Undo**. Main can be deleted only when it also lists no ignored clip, because the page
    lists the event folder's ignored clips under it whatever is saved.
  - The only chapter left keeps no Delete, Move up, Move down or Move clips: an event never saves without a
    chapter.
  - **Name rules.** A name is trimmed and must not be empty. It must differ, ignoring case, from every other
    chapter's name, including a deleted one, and from `Main`, always. These rules are stricter than the engine's
    (exact-match uniqueness only, and whitespace is accepted), for reasons the design gives.
- **Move clips…** on each chapter, when the event has more than one. A dialog lists the clips the chapter
  plays that are on disk, as checkboxes, and the other chapters, as radio buttons. The picked clips join
  the end of the chosen chapter. A clip moved back to the chapter it started in returns to its place, so a
  move and its reverse leave nothing to save. Missing clips are not offered: restore the file or remove the
  entry. Ignored clips are not offered either, since they are not played. Dragging across chapters stays
  v3, and the rows gain no control.
- **D-12 in words.** Wherever an edit changes what a name means for clips added later, the name dialog and
  the chapter say so. That covers renaming or deleting a chapter named after a folder, a new name equal to
  a folder's, and the ignored clips of a renamed or deleted chapter, which the page then lists under
  Main.
- **What a save writes.** Moving clips writes the two chapters involved, as a reorder does today. A change
  to the chapters themselves (add, rename, delete, chapter order) writes **every** chapter as shown. Every
  NEW clip then joins `reel.yaml` where the page shows it, so the page shows after the save what it showed
  before. The save bar counts chapters added, renamed and deleted, and a changed chapter order, beside the
  moves, the removals and the NEW clips it adds.
- **Counts, names, focus.**
  - A clip moved in from another chapter counts as moved and shows where it came from.
  - A chapter names its clips as the event page's table will name them after the save: by path once it
    holds a clip from another folder, or once it is renamed away from its folder's name.
  - Every chapter action is announced, keeps or hands on keyboard focus, and is locked while a save is in
    flight. Reset, the unsaved guard, conflicts, Overwrite and the toasts work as before.
- **The read view.** A chapter with no clips (one the operator added and saved empty) shows its heading and
  says that it has no clips and is left out of the movie, instead of an empty table.
- **Docs.**
  - `web/README.md`, the Edit-mode paragraph and the file tree.
  - `docs/high-level-design.md`: a new **D-13** pulls moving clips between chapters, and editing the chapter
    list, forward from v3. Dragging across chapters stays v3. It also gets §4.10's v1 bullet, v3 line and slice row D.

## Non-goals

- **Dragging a clip into another chapter.** It stays v3 (§4.10). It needs one `DndContext` across chapters,
  cross-container keyboard coordinates and new announcements. The design measured that it is not cheap.
- **A per-row "Move to chapter" control.** It would take room the rows do not have at 320 px, and
  `clip-cuts-screen` needs that room for its per-row Cuts control. See the design.
- **Splitting a chapter at a clip, range selection (Shift-click), and merging two chapters in one action.**
  These are follow-ups. Today they take a few checkbox presses.
- **Cut editing.** That is `clip-cuts-screen`, gated on this change.
- **Keeping a renamed chapter's clip comments.** The engine matches chapters by name, so a renamed chapter
  is written as a new one, without its clips' `reel.yaml` comments. The `editorial-write` spec states this
  ("A renamed chapter is a new chapter"), and a real `PUT` confirmed it. The same holds for a clip moved
  into a chapter that `reel.yaml` does not name yet. An engine fix is a recommended follow-up, not this
  change.
- **Server-side name rules.** The engine still accepts a whitespace-only name, and two names that differ
  only in case. The GUI never sends either. The CLI and hand edits are unaffected.
- **Renaming the event's own chapter, any API, engine, schema or dependency change, and any change to the
  render.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`. All of the following are in the one capability.
  - Four ADDED requirements:
    - `Requirement: Edit mode adds, renames, reorders and deletes chapters`
    - `Requirement: Edit mode moves clips to another chapter`
    - `Requirement: Edit mode says what a chapter's name means for clips added later`
    - `Requirement: The event page shows an empty chapter as empty`
  - Three MODIFIED requirements:
    - `Requirement: The event page reorders clips within a chapter`: a dragged clip still stops at its
      chapter's edge, but "a clip SHALL NOT be movable into another chapter" becomes "only through Move
      clips", and a clip moved in is counted and marked
    - `Requirement: Saving an edit writes only what the operator changed`: the save bar's chapter counts,
      and the write rules for moves between chapters and for chapter edits
    - `Requirement: Edit mode names clips and the saved event as the other screens do`: a chapter's names
      follow a clip moved in from another folder, and a new name

## Impact

- **Packages:** `web/` only, plus two documentation files.
  - `web/src/edit/`:
    - `draft.ts`: the chapter list model, the write body and the counts
    - new `chapterNames.ts`: the name rules and the D-12 notes, pure
    - new `ChapterTools.tsx`: the chapter toolbar, the deleted placeholder and Add chapter
    - new `ChapterDialogs.tsx`: the name dialog and the Move clips dialog
    - new `chapters.css`
    - `EventEditor.tsx`: the reducer, the wiring, the summary and focus
    - `ClipOrderList.tsx`: keyed by chapter, the toolbar slot, the empty state, the "from" badge and names
  - `web/src/ui/Icon.tsx`: two icons, `plus` for Add chapter and `arrow-right` for Move clips.
  - `web/src/ui/Dialog.tsx`: a `.dialog-fields` child is left out of the dialog's description, as the
    `.dialog-actions` row is. Without it a Move clips dialog over a 400-clip chapter would be read out whole
    as its description when it opens.
  - `web/src/events/EventDetail.tsx` and `events/detail.css`: the empty chapter's words in `ChapterPanel`.
  - `web/README.md` and `docs/high-level-design.md` (D-13, §4.10).
- **CLI vs API (Principle V):** neither is touched. The GUI writes through the existing `PUT …/reel`, the
  same engine operation (`apply_editorial_write`) any client reaches, and the CLI never edits chapters.
- **Rendered output:** unchanged for identical inputs. There is no `RENDER_GRAPH_VERSION` bump, and the
  fingerprint's inputs are unchanged. A saved chapter edit moves the editorial component, as any edit does,
  so the event reads "edited since last render".
- **Schemas:** no change to `reel.yaml` or `config.yaml`, and no API change. No Alembic migration and no
  rescan. `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gate:** none. The change starts from main at `d0bc1d5` or later.
  - `clip-cuts-screen` (G2) is gated on this change being archived and designs against its spec. The two
    share `draft.ts` and `EventEditor.tsx`: this change owns the chapter structure, and G2 adds per-clip
    properties.
  - **New runtime dependencies:** none. D-8's budget is unchanged: the dialogs use the shared `Dialog`, and
    the moves use no drag-and-drop.
- **Size (Principle VIII):** one package plus docs, one capability delta (4 added, 3 modified), and 9
  tasks.
