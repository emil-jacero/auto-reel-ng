## Why

The operator's feedback on Edit mode's chapter editor, 2026-10-03: renaming should only take a click on the
title, and `Main` should be renameable too, "treated as the main title card". Today a chapter is renamed with
a **Rename…** button that opens a dialog (two steps, a button whose only job is a word the heading already
shows), and `Main` offers nothing: the page says it "has no name of its own" and sends the operator to the
metadata form for the one thing the operator reads as Main's name. The operator decided (2026-10-03) that
renaming Main edits the event's title, the text of the main title card.

## What Changes

- **A chapter's title is the control.** In Edit mode every chapter but the event's own shows its name as a
  button with a pencil icon. Pressing it (Enter and Space too) turns the name into an inline text field with
  the name selected. Enter and leaving the field keep the name, Escape drops it, a refused name is explained
  under the field with the engine's chapter-name rules unchanged, and the "what this name means for clips added
  later" notes (D-12) show under the field as the name is typed. The **Rename…** button and its dialog go.
- **Main is the main title card.** The event's own chapter gets a "Main title card" line between its heading
  and its tools, showing the event's title as the same kind of button. Editing it edits `metadata.title` in
  the same draft as the metadata form's Title field, so the two stay in step, and a changed title says what
  it does to the movie's file name. The chapter keeps its name `Main` (or `Clips`) everywhere else: heading,
  control names, announcements, Move clips.
- A name field that holds text not yet kept counts as unfinished, like a typed cut: Ctrl+S is held back with
  a message, and leaving asks first.
- Add chapter keeps its dialog (a chapter that does not exist yet has no title to click); the dialog is
  unchanged.
- No API, engine, `reel.yaml` or staleness change: a rename and a title edit save through the existing
  `PUT /reel` as before.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: "Edit mode adds, renames, reorders and deletes chapters" (Rename becomes an inline edit of the
  title; Main gets the main title card line) and "Edit mode says what a chapter's name means for clips added
  later" (the notes show at the name field instead of in the Rename dialog).

## Impact

- `web/src/edit/`: `ChapterTools.tsx` (Rename button out), `ClipOrderList.tsx` (heading becomes the title
  control, the title card line), a new `InlineName.tsx` and `TitleCard.tsx` with their pure helpers,
  `EventEditor.tsx` (one open field at a time, the title commit, `unfinished`), `ChapterDialogs.tsx`
  (`NameDialog` serves Add chapter only), `MetadataForm.tsx` (exports the inherit hint), `chapters.css`.
  `web/src/events/labels.ts` exports the renamed-movie sentence the Edit mode note reuses.
- Docs: HLD D-13 and §4.10 (the rename gesture, Main as the title card), `web/README.md`.
- Gate: `clip-group-select-drag` merges first and also edits `ClipOrderList.tsx`, `ChapterDrag.tsx` and
  `EventEditor.tsx`; this change builds on top of it.
- No new dependency, no engine, API or schema change, no `RENDER_GRAPH_VERSION` bump.
