## Context

- **Where the chapter tools are drawn today.**
  - `edit/ChapterTools.tsx` exports `ChapterTools` (Move up, Move down, Delete and its refusal, and the chapter's
    `Notes`), `DeletedChapter` (the placeholder with Undo) and `AddChapter` (the button and its name dialog,
    `ChapterDialogs.tsx`).
  - `ClipOrderList` draws `ChapterTools` in each chapter's header bar, beside `EditTitlecard`.
  - `EventEditor` draws `DeletedChapter` and `AddChapter` inside the bin's `ChapterDrag`.
- **The handlers** are `onAddChapter`, `onMoveChapter`, `onDeleteChapter` and the restore in `EventEditor.tsx`. They
  dispatch `chapter-add`, `chapter-move`, `chapter-delete` and `chapter-restore`, each guarded by `idle()`,
  announced, and one Undo step.
- **`edit/chapterBar.ts`** holds the bar's pure parts: `editTitlecardName`, `barButton`, `barContent` and
  `chapterToolsParts`.
- **The inspector** (`edit/workspace/Inspector.tsx`) takes the Event tab's content as a node (`event`). That node is
  the Details form, the Poster panel and the "All title cards in this event" button, all built in `EventEditor`.
- **Card selection** comes from `EditTitlecard` (`CardButtonContext`) or a card block. Escape in the card editor
  returns focus to the control that selected the card (`returnFocus.ts`).

## Goals / Non-Goals

**Goals:**
- Move the chapter tools as components, with their handlers, words and tests unchanged.
- Leave the bin a list of clips under plain headings.

**Non-Goals:**
- Any change to a chapter edit's rules, words or draft action.
- Chapter controls on the Timeline.

## Decisions

### D1. `ChapterList` in the Event tab (`edit/ChapterList.tsx`)
```tsx
<section aria-labelledby="chapters-h">          // after Details, before Poster
  <h3 id="chapters-h">Chapters</h3>
  <ol>                                          // the draft's order, deleted chapters in their place
    <li> name · count · <EditTitlecard icon/> <ChapterTools/> <Notes/> </li>
    <li> <DeletedChapter/> </li>
  </ol>
  <AddChapter/>
</section>
```
- **Parts.** `ChapterTools`, `DeletedChapter`, `AddChapter` and `EditTitlecard` are reused as they are: same props,
  names, `aria-disabled` reasons and tooltips. `chapterToolsParts` keeps deciding which tools a chapter offers.
- **Row.** A grid of one line under a fine pointer (name, count, then four 32 px icon buttons, so ≤ 36 px tall in the
  340 px inspector), wrapping under a coarse pointer with 44 px targets. The notes sit under the line.
- **Count.** `barContent`'s count: the clips the chapter plays.
- **Empty hint.** `emptyChapterWords` loses its drag and Move-marked wording for "moved into it with Move to… (the
  Clip tab's, or a clip's menu)". Its unit test is updated.
- **Focus targets.** These keep their current rules, moved to the row's elements:
  - the new chapter's row (`tabIndex=-1`) after Add chapter;
  - Undo after Delete;
  - Delete after Undo;
  - the pressed tool after a move.
- **Always present.** `ChapterList` is built in `EventEditor` from the draft, not by the Timeline, so it is there in
  Prepare and with no track.

### D2. The bin's headings become plain (`ClipOrderList.tsx`, `ChapterDrag.tsx`)
- **What goes.** The header bar keeps the heading, name and counts. `EditTitlecard` and `ChapterTools` leave it, and so
  does the tools row under 960 px.
- **Deleted chapters.** `DeletedChapter` and `AddChapter` leave `ChapterDrag`. A deleted chapter is no longer listed
  in the bin at all. Its drop-target placeholder goes with it: there is nothing to drop on.
- **What stays.** The bin's chapter sections, its empty-chapter drop area, its drag and its marks stay until
  `plain-clip-bin`.

### D3. Focus back from the card editor
- **Inspector state.** When Escape clears a card selection, the inspector shows the Event tab (the selection is
  none). The row's Edit title card button is then mounted, so `returnFocus` finds it.
- **Ordering.** The return runs in a layout effect after the tab switch, so focus never lands on an unmounted node.
- **Fallback.** If the button is gone (its chapter was deleted meanwhile), focus goes to the Chapters heading.

## Research & Decisions

### Where the chapter tools live once the bin is plain
**Context**: the plain list has no chapter sections. The tools need a home that is there for every event.
**Explored**:
- **The track's chapter bands, with a menu.** The track is absent until every shown clip has a ready proxy, and an
  empty chapter has no band. So it cannot be the only home.
- **The card editor (Title card tab).** It holds the Name, but an empty chapter has no card on the Timeline to
  select, and "Add chapter" has no card at all.
- **The Event tab.** It is there whenever nothing is selected, and in Prepare. It is already the home of the event's
  own fields.
- **A new inspector tab.** A fifth tab that follows no selection, which "The inspector follows the selection" does
  not describe.

**Decision**: the Event tab (D1).
**Rationale**: it is the one place that exists for every event state. A band menu can be added later as a second
route.

### Keep the deleted chapter's row and Undo
**Context**: the operator could rely on the top bar's Undo instead.
**Decision**: keep the row with "deleted when you save" and Undo.
**Rationale**: a deleted chapter shows nowhere else (the track draws nothing for it), and the row also carries the note
of where the folder's later clips go ("Edit mode says what a chapter's name means for clips added later").

## Risks / Trade-offs

- [The Event tab gets longer] → The Chapters list is compact (36 px rows). Details and Poster keep their Help toggles.
  The inspector pane scrolls on its own.
- [An operator used to the bin's tools looks there first] → The bin's headings still name the chapters, and the Clips
  help says where the chapter tools are now.
- [Focus return depends on the tab switch's timing] → D3, verified by the "Renaming with the keyboard only" scenario
  in task 2.2.

## Failure behaviour

Layout only: no request, no write. Every chapter edit keeps its guards: while a save is pending, every tool says it is
unavailable and changes nothing.
