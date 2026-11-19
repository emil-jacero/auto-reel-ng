## Why

The plain clip list the operator asked for on 2026-11-18 has no chapter sections. Today the bin's chapter header bars
are the only place to:
- add a chapter;
- move a chapter up or down;
- delete a chapter, and undo that until Save;
- open the title card editor of a chapter, which holds its Name field (rename).

So these tools need a new home before the old bin goes.

The track is not that home, although it draws chapter bands. It is absent until every clip it shows has a ready
proxy: the Timeline shows only Prepare ("The Timeline asks for the clips' proxies when they are missing"). And a
chapter without clips has neither a band nor a card on it. A chapter just added, the very one that needs a name and
clips, would have no visible handle. The inspector's Event tab is always there and already holds the event's own fields
(HLD D-28, "The inspector follows it": nothing selected shows Event). The chapters are the event's structure, so they
belong in it.

This is the second of four changes that together build the plain clip list, the third of the four follow-ups agreed on
2026-11-18 (HLD §6 item 10, GUI v3; `docs/editor-workspace.md`). It follows `clip-multi-select`, whose Move to… is what
an empty chapter now points at.

## What Changes

- **A Chapters list in the Event tab**, after the Details form. It has one row per chapter in the draft's order:
  - the name as plain text, and the clip count;
  - icon buttons Edit title card, Move up, Move down and Delete, named and with tooltips;
  - the notes the chapter's header bar shows today (no clips, what the name means for clips added later).

  A deleted chapter keeps its row with "deleted when you save" and Undo. **Add chapter** follows the last row. It works
  whether or not the track is open.
- **The rules do not change.** Every rule of "Edit mode adds, renames, reorders and deletes chapters" carries over:
  - names, refusals and case folding;
  - which chapter offers which tool, and what Delete refuses and why;
  - focus after each control, announcements and save-bar counts;
  - the busy-control rule, and touch sizes.

  Only the place changes. After Escape in the card editor, focus goes back to the row's Edit title card button, as it
  went back to the header bar's.
- **The bin's chapter headings become plain**: name and counts, no buttons, and no Add chapter. The bin keeps its
  chapter sections, drag and marks until `plain-clip-bin`.
- **An empty chapter's hint** now says that clips can be moved into it with Move to… (the Clip tab's, or a clip's
  menu), instead of pointing at the bin's drag and Move marked to….

## Non-goals

- Chapter tools on the track: a chapter band's menu, dragging a band, or a band for an empty chapter. These can come
  later, but none can be the only home while the track may be absent.
- Renaming outside the title card editor. The Name field stays the one rename workflow.
- A tab of its own for chapters. The Event tab already shows when nothing is selected.
- Removing the bin's chapter sections, drag or marks (`plain-clip-bin`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`:
  - ADDED "The Event tab lists the event's chapters".
  - MODIFIED "Edit mode adds, renames, reorders and deletes chapters": its controls move from the header bar to the
    Chapters list rows, and the empty chapter's hint points at Move to….
  - MODIFIED "The clip bin holds the chapters' clip lists": chapter tools are no longer among the bin's actions.
  - MODIFIED "The inspector holds the event's fields and the selected cut": the Event tab holds the Chapters list.
  - MODIFIED "The title card editor is docked in the inspector": a card is opened from the Chapters list, not from the
    bin.
  - MODIFIED "Edit mode drags clips between chapters": the Clips help says that Add chapter is in the Chapters list.

## Impact

- **Web only.**
  - `edit/ChapterTools.tsx`: Move up, Move down, Delete, `DeletedChapter` and `AddChapter` render in the new
    `edit/ChapterList.tsx`, inside the Event tab. Their handlers in `EventEditor.tsx` are unchanged.
  - `edit/EditTitlecard.tsx`: the button moves to the row.
  - `edit/ClipOrderList.tsx` and `edit/ChapterDrag.tsx`: the header bars lose their tools.
  - `edit/workspace/Inspector.tsx`: the Event tab's content.
- **Unchanged:**
  - No API, engine, `reel.yaml` or `config.yaml` schema change, no Alembic migration and no rescan.
  - No change to rendered output, the staleness fingerprint or `RENDER_GRAPH_VERSION`.
  - The CLI is untouched. This is a browser layout change (Principle V).
  - No new dependency, and no new draft action.
- **Depends on** `clip-multi-select`, which must be archived first.
- **Size:** about one day.
