## Context

Evidence relied on is the repo at `origin/main` 143f0fc, since none of the three v2 research notes
(`research/v2/synthesis.md`, `proxies.md`, `timeline-library.md`) covers renaming; the user feedback of
2026-10-03 and the plan entry are the requirement.

- Rename is a button in the chapter's tools row (`web/src/edit/ChapterTools.tsx`, `rename` in
  `ChapterToolsModel`) that opens `NameDialog` (`ChapterDialogs.tsx`), shared with Add chapter. The dialog
  checks a name with `checkName` and shows the D-12 notes of `nameDialogNote` as the name is typed
  (`chapterNames.ts`, pure and tested). A confirmed name dispatches `chapter-rename` (`EventEditor.tsx`
  `confirmName`), announces, and `Dialog` returns focus to Rename.
- The event's own chapter has the empty name (`DraftChapter.name === ''`), is headed `Main` (another chapter
  listed) or `Clips` (alone), and offers no Rename; its note says "its title card shows the event's title".
- The event title is `draft.metadata.title` (`MetadataDraft`), edited per keystroke by `MetadataForm`'s Title
  field through the reducer's `field` action. `''` is "inherit from the folder name"; `resolved.title` is that
  inherited value; `inheritHint` words it. `changedFields` and `buildWriteBody` already treat whitespace-only
  as unset. The title card of the movie's first chapter is composed from `metadata.title` (title-card spec,
  "Title card rendered to an image"), so the event title is the main title card's text.
- A title change renames the movie file (`output_renamed`, HLD D-9 "Amended 2026-10-01"): the event page
  already says, after a save, that the next render saves the movie under its new name and keeps the old one
  (`REASON_NOTE.output_renamed` in `events/labels.ts`, spec "The event page says what a render does when the
  movie's name changed").
- "Unfinished" input already blocks Save: an incomplete date and a typed-not-added cut (`unfinished(ready)`,
  `saveHold`, `holdWords`), and count as unsaved for the leave question (`dirty`).
- Many existing scenarios fix the chapter's heading to `Main`/`Clips` ("The chapter's heading is one line that
  reads "Clips", "1 clip moved" and "2 clips""; announcements and Move clips name the chapter `Main`).

## Goals / Non-Goals

**Goals:** one gesture to rename (press the title); Main renameable as the main title card; no change to what
is saved or how; keyboard-only complete; no layout jump when the field opens.

**Non-Goals:** renaming in the read view; renaming via the Timeline; double-click or F2 gestures; a
client-side rule for the title (the service's refusal of an unusable title stays at the metadata form);
changing Add chapter; any engine, API or `reel.yaml` change; the clip marks and group drag (gate
`clip-group-select-drag`).

## Decisions

**D1. The heading stays `Main`/`Clips`; the title card is a line under it.** The operator asked to rename
"the Main". Replacing the heading's text with the event title would make the header read "Grillkväll med
grannarna" while Move clips says "Move to: Main", announcements say "moved to “Main”", clips moved in say "from
Main" and the Timeline says Main. It would also rewrite a dozen scenarios that fix the heading's words and
its one-line fit. Instead the own chapter gets a line directly under its header, before the tools row:
the label "Main title card" and the title as a press-to-edit button (a larger, heading-like type). The
chapter's name for every other purpose is unchanged. *Alternative rejected:* make the heading itself the
title; revisit only if the operator finds the line redundant when they see it.

**D2. One shared inline control, two uses.** `InlineName` renders a native `<button>` showing the text and a
pencil icon (always visible, not only on hover or focus: a hover-only cue is invisible on a phone and the
operator's complaint was that controls did not say what they do). Pressing it swaps in an `<input>` of the same
font, line height and height, so the heading row does not change height and nothing below it moves; the field
has the 3:1 edge of the other fields. The chapter heading's use puts the button inside the `<h2>`
(heading semantics kept; the h2 stays `tabIndex={-1}` for the focus after Add chapter). The button's
accessible name is the text it shows, so the `<h2>` is still named by the chapter's name and the tools row
group, which `aria-labelledby` the h2, is still named by it; that pressing it renames is its accessible
description ("Press to rename this chapter"), through `aria-describedby`, not part of the name. The title card
line's use is a `role="group"` named "Main title card" holding the button, described "Press to edit the event's
title". Props are plain data plus two functions, `check(typed)` and `notes(typed)`,
so `InlineName` knows nothing of chapters: a chapter passes `checkName` and `nameDialogNote` closures, the
title passes a check that accepts anything.

**D3. Commit rules.** Enter (not during IME composition) and blur keep the name; Escape drops it; both
Enter and Escape return focus to the button; blur does not (focus has already gone where the operator went).
A name equal to the current one (after stripping) closes without an edit and without an announcement. A refused
name on Enter keeps focus in the field and shows the refusal in a `role="alert"` under it
(`NAME_REFUSAL`, text unchanged, `aria-invalid`, `aria-describedby`); a refused name on blur leaves the field
open with the refusal and takes no focus. *Why not revert on blur:* typed text vanishing silently is worse
than a field left open; Escape is the way out. *Why not trap focus:* a field that cannot be left breaks Tab
and screen-reader navigation.

**D4. One field open at a time, owned by the editor.** `EventEditor` keeps `naming: ChapterKey | 'title' | null`.
Opening another replaces it (the first is dropped, which only loses a refused or unkept text the operator
walked away from). It is closed by Reset, a save starting, Delete or Move chapter of that chapter, the leave
question, and a re-read. The open chapter's `ChapterToolsModel` carries `naming` (a closure pair only while
open); the others' models are unchanged, so the `toolsCache`/`sameTools` memo still re-renders only the chapter
concerned (the 400-clip chapter rule). Typed text is the field's own state, so a keystroke renders neither the
editor nor a chapter list.

**D5. A kept name is the existing edit.** A chapter commit dispatches the existing `chapter-rename` and
announces `“old” renamed to “new”.` plus the D-12 notes (`notesIn`), as `confirmName` does now. A title commit
dispatches the existing `field` action for `title`, so `MetadataForm`'s Title field, `changedFields`, the
save bar ("Title"), the leave question, Reset and the refusal (`unusable_metadata`, retired on edit) need no
change; the form's Title shows the new value because both read `draft.metadata.title`. The kept value is the
typed text unchanged (the form stores raw text; `asSaved` already treats whitespace-only as unset). An
emptied title says "Left empty: inherits from the folder name when saved", the form's hint, so
`MetadataForm.tsx` exports `inheritHint`.

**D6. What the title line shows.** `draft.metadata.title` when it is not blank, else the title the page
resolved (`resolved.title`, marked "from the folder name"), else the muted word "Untitled". The button's name
is that text. It never shows or guesses a file name.

**D7. The file-name note, before the save.** While `changedFields` holds `title`, the title line adds one
sentence: "Saving changes the movie's file name. If the movie was already rendered, the next render saves it
under the new name and the movie under its old name stays on disk." No file names (Edit mode does not hold
them; the event page's note, after the save, carries them from the verdict). Whatever the page says after the
save is unchanged. *Alternative rejected:* nothing in Edit mode and rely on the event page's note: the
operator would learn after the save, and the feedback asked that the consequence be stated.

**D8. Unfinished.** The field reports "holds text not yet kept" to the editor only when that flips
(`nameUnsent`, a reducer flag), not per keystroke. `unfinished(ready)` gains it, so Save and Ctrl+S are held
back (`saveHold` → `unfinished`, `holdWords` adds "a name is typed and not kept"), and the leave question
counts it. A mouse press on Save blurs the field first, which keeps a valid name before the click lands.
*Alternative rejected:* Ctrl+S commits then saves: the commit is an async reducer step and `submit` reads the
draft it was rendered with.

**D9. Touch and the busy rule.** Both buttons take a 44 × 44 px tap area on a coarse primary pointer without
reaching a neighbour (the existing rule, "Every control is large enough to touch"), by padding and a
`::after` extension as the other buttons do, and `aria-disabled` while a save or a Move clips is pending
(never `disabled`, which drops focus). The field is not opened then.

**D10. The Rename button and `rename` model field are deleted, not hidden.** `NameDialog` keeps only the Add
chapter case, so its `current` and `self` parameters, the select-on-open effect and the Rename wording go.
`chapterNames.ts` (`checkName`, `nameDialogNote`) is unchanged.

## Risks / Trade-offs

- [Gate overlap: `clip-group-select-drag` also edits `ClipOrderList.tsx`, `ChapterDrag.tsx`, `EventEditor.tsx`]
  → this change touches only the panel header, the lines between it and the tools row, the tools model and the
  editor's chapter-dialog state; implement after the gate merges and re-read its header and `EventEditor`
  diff first. If the gate puts its mark count or Clear marks in the panel header, the title line still goes
  below the header and the field never needs the header's right side.
- [A button inside an `<h2>` could change what the heading, the region and the tools group are called] → the
  button's name is the chapter's name and the "renames" cue is a description (D2); a Playwright check asserts
  that the heading, region and group names equal the chapter's name before and after the change.
- [A field left open with a refusal after blur] → one open field at a time, Escape, and `unfinished` keep it
  from being forgotten; a refusal is announced once, not repeated on every blur.
- [The title line adds height to `Main`] → one line (two on a phone with the note); the scenario that fixes
  the heading's fit is about the heading, which does not change.
- [Perf: 400-clip chapter] → typing stays in the field's own state; a commit is one reducer action as Rename
  was; the chapter's list re-renders only when its model changed. Measured as in the existing "first edit"
  budget.

## Migration Plan

None: nothing is stored or sent differently. The old Rename scenarios are replaced by the new ones in the
delta.

## Open Questions

None.
