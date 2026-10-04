## MODIFIED Requirements

### Requirement: Edit mode adds, renames, reorders and deletes chapters

In Edit mode the operator SHALL be able to change the event's chapters themselves. Every control below SHALL
be reachable with the keyboard and SHALL name, to assistive technology, the chapter it acts on.

- **Add chapter**, after the last chapter, SHALL ask for a name and add an empty chapter with that name at the
  end.
- **Rename** SHALL be done in the title card dialog, in its Name field ("The title card dialog holds every
  name and every title-card setting"), by the one workflow for every chapter. A chapter's header bar SHALL show its name as plain text: not a
  button, with no pencil and no hover or focus change, and pressing it SHALL do nothing. There SHALL be no Rename
  button, no inline name field and no dialog of its own for a name. The event's own chapter (the default chapter,
  whose clips are the event folder's) has no name to rename: it is headed `Main` or `Clips` ("The event's own chapter
  is headed ..." below), its title card shows the event's title, and its Name field edits that title. Clips without a
  chapter of their own join it. While the event lists other chapters, the page SHALL say this in the Clips help ("Each explanation sits behind a Help toggle of its section"), not as a line beside the chapter.
- **Move up** and **Move down** SHALL move a chapter one place among the chapters, and SHALL be offered only
  while the event lists more than one chapter. After such a move, keyboard focus SHALL stay on the pressed
  control. At either end, the control that cannot move further SHALL say that it is unavailable.
- **Delete** SHALL remove a chapter only once it plays no clip. Its clips must first be moved to another
  chapter, or removed when missing. The event's own chapter can be deleted only when, in addition, it lists no
  ignored clip that the page would list under it again after the save: one from the event folder, or from a
  folder no chapter is named after. Such a clip would bring the chapter back, holding only ignored clips.
  When a chapter cannot be deleted, pressing Delete SHALL change nothing and leave focus on Delete. The page
  SHALL show and announce why the chapter cannot be deleted.

**The header bar.** Every chapter's header bar, the event's own chapter's too, SHALL hold, in this order, the chapter's name as plain
text, an **Edit Titlecard** button and the chapter's clip count; the chapter's tools (Move up, Move down, Delete, offered by the rules above) stay in their own row under the bar, which is sticky and keeps one line. The
button SHALL show an icon and the words "Edit Titlecard", SHALL be named "Edit title card for <name>" (the event's own chapter: its
heading) and SHALL open the title card dialog on the "This title card" tab ("A selected title card opens its inspector in Edit mode"). A
chapter's section SHALL show nothing between its header bar and its clips but the tools row and the notes of this requirement and of "Edit mode says what
a chapter's name means for clips added later": no card row, no "Main title card" line, no source line ("from the folder name"). A chapter added in the draft has no saved card, and its
button SHALL be offered all the same: the dialog says that its card is drawn after Save and keeps the preview from the draft.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up or Move down, so that an event never saves without a chapter.

**The Name field.** In the dialog the field SHALL be the first of "This title card" and SHALL be named "Name of chapter <name>"
for a chapter and "Title of the event" for the event's own chapter, where <name> is the name the draft holds when the dialog opens. The
header bar and the dialog's title name the chapter by its name alone.

- An accepted name SHALL be written to the draft as it is typed, so that the dialog's heading, its preview, the chapter's header
  bar behind the dialog and the picker of Move marked to… follow it. A name equal to the chapter's current name, once the spaces
  around it are removed, SHALL change nothing. A rename SHALL be announced once, when keyboard focus leaves the field or the dialog
  closes, and not for each key; typing a name and typing the old one back announces nothing.
- A refused name SHALL be explained under the field in words, in a `role="alert"` that is remounted for each refusal, and the
  field SHALL be marked invalid. The draft keeps the last accepted name, and the field keeps the typed text. Done, with a refused
  name in the field, SHALL keep the dialog open and put keyboard focus in the field. Escape and Close SHALL close the dialog, return the
  field's text to the draft's name, and announce that the name was not changed and why; they SHALL NOT keep a refused name.
- While the field holds a refused name, Ctrl+S SHALL save nothing and SHALL say "Not saved: the name is refused."
- While a save or a move of marked clips is pending, the field and the dialog's other fields SHALL say that they are unavailable
  and SHALL change nothing (the busy-control rule); the bar's Edit Titlecard button SHALL say so too and open nothing.
- Reset, a conflict and Overwrite SHALL treat a name as any other edit; Reset SHALL restore the chapters' names as read.

**The event's own chapter's name is the event's title.** For the event's own chapter the Name field SHALL edit the draft's
title, the one the Details form's Title field edits, in step with it in both directions, counted once in the save bar ("Title") and
undone by Reset as one edit.

- The field SHALL hold the draft's title. While that is blank it SHALL be empty with the title the page resolved from the folder
  name as its placeholder and the words "From the folder name", else the word "Untitled". The page SHALL NOT guess a title.
- Any text SHALL be kept as the title, with no rule of the page's. A blank title means that it inherits from the folder name, and
  the field SHALL say so in the words of the Details form ("Left empty: inherits from the folder name when saved"). The
  service's refusal of an unusable title stays at the Details form and is retired by editing the title in either place.
- While the draft's title differs from the title read, the dialog SHALL say that saving changes the movie's file name, that if the
  movie was already rendered the next render saves it under the new name, and that the movie under its old name stays on disk. It SHALL NOT name a
  file: the event page names them after the save, from the verdict.
- The card's heading follows the name. A card that has its own title ("Card title (overrides the name)") keeps it.

When the browser's primary pointer is coarse, each of these controls, the header bar's Edit Titlecard button, Add chapter and Undo SHALL take a tap
anywhere in an area of at least 44 × 44 CSS pixels around it that reaches no other control, as every button
does ("Every control is large enough to touch").

A name SHALL be accepted only when both of these hold, once the spaces around it are removed. The spaces are
the characters the engine removes from a chapter's name, so a name the page accepts is a name `reel.yaml`
loads:

- it is not empty
- compared by full Unicode case folding, the comparison the engine makes, it differs from the name of every
  other chapter of the event, including a deleted chapter not yet saved, and from `Main`, the name the page
  shows for the event's own chapter. So `ß`, `ss`, `SS` and `ẞ` are one name, as are `Kvällen` and `KVÄLLEN`.

A refused name SHALL be explained at the name field, which keeps keyboard focus when the name was asked for
with Done or in the Add chapter dialog, and nothing SHALL change. The
name saved is the accepted name without the spaces around it. A chapter's name SHALL be described to the
operator as the words on its title card in the movie.

A chapter the page showed when Edit mode opened SHALL, once deleted, stay listed in its place until the edits
are saved, marked as deleted when the edits are saved. It lists none of its clips. Such a chapter offers an **Undo** control that returns it to its place, and keyboard focus SHALL move to that Undo. A
chapter the operator added in this Edit mode and then deletes SHALL simply be gone. A chapter that plays no
clip SHALL say so in Edit mode, and that a chapter without clips is left out of the movie. While the event
lists another chapter, a deleted one aside, it SHALL also say that clips can be dragged into it, or moved into
it with Move marked to… (see "Edit mode drags clips between chapters"). When it is the only
chapter listed, a deleted one aside, it SHALL NOT say that: no other chapter has a clip to drag or to move,
and the page offers no Move marked to… there.

The event's own chapter SHALL be headed `Main` while any other chapter is listed, a deleted one aside, and
`Clips` otherwise, as on the event page. Every change to the chapters SHALL count as an unsaved edit, like a
move:

- it SHALL be announced
- Reset SHALL restore the chapters as read
- leaving with it unsaved SHALL ask first
- the save bar SHALL count it ("Saving an edit writes only what the operator changed")

While a save is in flight, every chapter control and Add chapter SHALL say that it is unavailable and SHALL
change nothing when pressed.

#### Scenario: A first chapter added to a one-chapter event
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter, the
  operator presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** a chapter `Kvällen vid grillen` is listed last, saying that it plays no clip and that clips can be
  dragged into it or moved into it with Move marked to…; the first chapter's heading reads `Main` instead of
  `Clips`; keyboard focus is on the new chapter's heading; the addition is announced; and the save bar says
  "1 chapter added"

#### Scenario: A lone chapter offers only Add chapter
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter
- **THEN** its one chapter offers no Move up, Move down or Delete, its header bar shows `Clips` as plain text with an Edit Titlecard
  button (the dialog's Name field edits the event's title), and the page offers Add chapter after it

#### Scenario: A name already taken, or no name, is refused
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named `kvällen`, then one named
  only with spaces, then one named `main`
- **THEN** each is refused at the name field, which keeps keyboard focus. `kvällen` is refused because a
  chapter called `Kvällen` exists. The blank name is refused because a chapter needs a name. `main` is refused
  because `Main` is the page's name for the event's own chapter. No chapter is added.

#### Scenario: A name the engine would fold into another is refused
- **WHEN** on `2024-09-14 - Gatufest`, an event with a chapter `Straße`, the operator adds a chapter named
  `STRASSE`, then one named `strasse`
- **THEN** each is refused at the name field, which keeps keyboard focus, because a chapter called `Straße`
  exists. No chapter is added. A name that merely resembles it, such as `Strasse 2`, is accepted.

#### Scenario: The spaces the engine removes are removed
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named with a next-line character
  (U+0085) before and after `Hamnen`
- **THEN** the chapter is added as `Hamnen`, without those characters, and the next save writes `Hamnen` to
  `reel.yaml`, which loads

#### Scenario: Renaming a chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses "Edit title card for Kvällen"
- **THEN** a dialog opens on "This title card" with keyboard focus in the Name field, named "Name of chapter Kvällen" and holding
  `Kvällen`; the header bar behind it shows `Kvällen` as plain text with no pencil
- **WHEN** the operator selects the name, types ` Kväll på stranden `, with spaces around it, and presses Done
- **THEN** the dialog is closed, keyboard focus is on that chapter's Edit Titlecard button, the heading reads `Kväll på stranden`, the rename was announced once, and the save bar says that 1
  chapter was renamed. The chapter offers no Rename button and its name is not pressable.

#### Scenario: Renaming with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator tabs to "Edit title card for Kvällen", presses Enter, types `Kväll`
  in the Name field and presses Escape
- **THEN** the chapter is named `Kväll` (an accepted name is already in the draft), the dialog is closed, keyboard focus is on the
  Edit Titlecard button, and the next Tab reaches the chapter's Move up

#### Scenario: Main and a chapter are edited alike
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens "Edit title card for Main" and then "Edit title card for Kvällen"
- **THEN** each opens the same dialog on "This title card" with the Name field first; Main's is named "Title of the event" and holds
  `Två kapitel`, Kvällen's "Name of chapter Kvällen"; neither header bar has a pencil, a card row, a "Main title card" line or a
  "from the folder name" line

#### Scenario: Leaving the field keeps an accepted name
- **WHEN** the operator opens the dialog of `Kvällen`, types `Kväll` in the Name field, and presses Tab
- **THEN** the chapter is named `Kväll`, keyboard focus is on the control after the field and not back in it, the dialog stays open, and the rename is announced once

#### Scenario: Escape drops what was typed
- **WHEN** the operator opens the dialog of `Kvällen`, types `main` in the Name field, and presses Escape
- **THEN** the dialog is closed, keyboard focus is on the chapter's Edit Titlecard button, the chapter is named `Kvällen`, "Name not changed" with the reason is announced, and the page shows no unsaved changes

#### Scenario: Pressing the title and changing nothing
- **WHEN** the operator types `Kväll` in the Name field of `Kvällen` and then `Kvällen`, with spaces around it, and closes the dialog
- **THEN** the chapter is named `Kvällen`, nothing is announced or counted as an edit, and the page shows no unsaved changes

#### Scenario: A refused rename keeps the field open
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `main` in the Name field of `Kvällen`
- **THEN** the field stays as typed, is marked invalid and explains under it that `Main` is how the page names the event's own chapter; the
  refusal is announced, and the draft still holds `Kvällen`. Typing `Morgon` removes the refusal and the chapter is named `Morgon`.
- **WHEN** the operator types `main` again and presses Done
- **THEN** the dialog stays open and keyboard focus is in the field
- **WHEN** the operator presses Escape
- **THEN** the dialog closes, the chapter is named `Morgon`, the last name accepted, and "Name not changed" with the reason is announced

#### Scenario: A refused name is not lost when focus leaves
- **WHEN** the operator types `main` in that field and presses Tab
- **THEN** the field stays as typed with its refusal, keyboard focus is on the control after it, and the chapter is still named `Kvällen`

#### Scenario: An empty name, and a name already taken
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator opens its dialog, deletes the name,
  and then types `KVÄLLEN`
- **THEN** the first is refused because a chapter needs a name, and the second because a chapter called `Kvällen` exists, each in
  the words Add chapter's dialog uses for the same name

#### Scenario: One field at a time
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator renames `Kvällen` to `Kväll` in its dialog, presses Done, and opens "Edit title card for Morgon"
- **THEN** only the dialog of `Morgon` is open, `Kvällen`'s header bar reads `Kväll`, and the save bar counts the one rename

#### Scenario: A name typed and not kept holds Save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator changes the title in the Details form, opens the dialog of `Kvällen`,
  types `main` and presses Ctrl+S
- **THEN** nothing is saved and "Not saved: the name is refused." is announced. After the operator types `Kväll`, closes the dialog and presses
  Ctrl+S, one save is sent and carries both edits.

#### Scenario: Reset closes the field
- **WHEN** the operator renames `Kvällen` to `Kväll` in its dialog, closes it, and presses Reset
- **THEN** the header bar reads `Kvällen`, the page shows no unsaved changes, and "Edit title card for Kvällen" opens a dialog whose Name field holds `Kvällen`

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` has no chapter rename and says that it has no name of its own because its title card shows the event's title; its
  header bar shows `Main`, an Edit Titlecard button and no other title control

#### Scenario: Renaming the main title card edits the event's title
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in which one chapter is listed, and the operator opens "Edit title
  card for Clips" and types `Grillkväll med grannarna` in the field named "Title of the event"
- **THEN** the Details form's Title field holds the same, the dialog's preview shows it, the save bar says "Title" changed, and the
  dialog says that saving changes the movie's file name and names no file. The chapter is still headed `Clips`.
- **WHEN** the operator closes the dialog and types `Grillkväll` in the Details form's Title field and reopens the dialog
- **THEN** the Name field holds `Grillkväll`
- **WHEN** the operator saves
- **THEN** one `PUT` is sent whose metadata title is `Grillkväll` and whose chapters and clips are as read, and the dialog no longer says anything about
  the file name

#### Scenario: Emptying the main title card
- **WHEN** the operator deletes the text of the Name field of `2024-06-27 - Grillning med grannar`, which reads `Grillning med grannar` from `reel.yaml`
- **THEN** the field says "Left empty: inherits from the folder name when saved", shows the title resolved from the folder name as its
  placeholder with "From the folder name", and the Details form's Title field is empty with the same hint

#### Scenario: The main title card with no title at all
- **WHEN** the page has no title for the event, in `reel.yaml` or resolved from the folder name
- **THEN** the field is empty with the placeholder "Untitled"

#### Scenario: Moving a chapter up
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses Move up on `Kvällen`
- **THEN** `Kvällen` is listed first and `Main` second. Keyboard focus is still on `Kvällen`'s Move up, which
  now says that it is unavailable. The move is announced as chapter 1 of 2, and the save bar says that the
  chapter order changed.

#### Scenario: A chapter that plays clips cannot be deleted
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses Delete on `Kvällen`
- **THEN** nothing is deleted, and keyboard focus stays on Delete. The page shows and announces that `Kvällen`
  still plays 3 clips, which must first be moved to another chapter.

#### Scenario: Deleting an emptied chapter, and undoing it
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves all three clips of `Kvällen` to `Main` and
  presses Delete on `Kvällen`
- **THEN** `Kvällen` is listed in its place as deleted when the edits are saved, with an Undo control that has
  keyboard focus. The save bar says that 3 clips moved and that 1 chapter is deleted.
- **WHEN** the operator then presses that Undo
- **THEN** `Kvällen` is listed again, playing no clip. Keyboard focus is on its Delete, and the save bar no
  longer counts a deleted chapter.

#### Scenario: Main stays while it lists an ignored clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710001.mp4` to `Kvällen` and presses
  Delete on `Main`
- **THEN** nothing is deleted, and the page says that `Main` still lists 1 ignored clip that no other chapter
  will take

#### Scenario: Saving a deleted chapter
- **WHEN** after deleting the emptied `Kvällen` of `2024-08-20 - Två kapitel - Tjörn`, the operator saves
- **THEN** `reel.yaml` names one chapter, the event's own, listing `s1710001.mp4`, `Kvällen/s1710002.mp4`,
  `Kvällen/s1710003.mp4` and `Kvällen/s1710004.mp4`, and still ignores `s1710004.mp4`. The page then shows that
  one chapter, headed `Clips`.

#### Scenario: Reset restores the chapters
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen`, adds a chapter `Morgon`, moves
  `Kvällen` up, and presses Reset
- **THEN** the chapters are `Main` and `Kvällen` as read, in that order, and the page shows no unsaved changes

#### Scenario: A chapter edit is an unsaved edit
- **WHEN** the operator renames `Kvällen` on `2024-08-20 - Två kapitel - Tjörn` and presses the browser's Back
- **THEN** the event page stays, with the rename, and asks "Discard unsaved changes?"

#### Scenario: The last chapter stays
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a chapter `Kvällen vid grillen`, moves all
  four clips of `Main` to it, and deletes `Main`
- **THEN** `Kvällen vid grillen` has a Name field in its dialog, but no Delete, Move up or Move down, and the save bar
  says that 4 clips moved, 1 chapter was added and 1 chapter deleted

#### Scenario: Chapter controls on a phone
- **WHEN** the operator opens Edit mode on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area around each of `Kvällen`'s Edit Titlecard, Move up, Move down and Delete, and
  around `Main`'s Edit Titlecard and Add chapter, reaches that control and no other (centred on each, except
  that the areas of Move up and Move down meet at the edge they share, as a clip row's move pair's do), and
  the page does not scroll horizontally

#### Scenario: Chapter controls wait for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a rename pending, the operator presses Save, and the
  service has not answered yet
- **THEN** Add chapter and every chapter's Edit Titlecard, Move up, Move down and Delete say that they are unavailable, and
  pressing them changes nothing and opens nothing

#### Scenario: A lone empty chapter does not point at Move clips
- **WHEN** Edit mode opens on `2024-10-05 - Tom mapp`, an event whose folder holds no clip, and the operator
  presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** the new chapter, the only one listed, counts 0 clips, and it says "No clips. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move marked to…, and the page offers no Move marked to…

#### Scenario: A lone chapter whose only clip is ignored
- **WHEN** Edit mode opens on `2024-10-06 - Bara ignorerad`, an event that lists one chapter, whose only clip
  `s1710004.mp4` is ignored
- **THEN** the chapter lists the ignored clip under its heading and says "It plays no clip. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move marked to…

#### Scenario: A second chapter brings the hint back
- **WHEN** on `2024-10-05 - Tom mapp`, with `Kvällen vid grillen` added, the operator presses Add chapter,
  types `Morgonen` and confirms
- **THEN** both chapters say that they have no clips and that clips can be dragged into them or moved into
  them with Move marked to…
- **WHEN** the operator then deletes `Morgonen`
- **THEN** `Kvällen vid grillen` says again, as it did before the addition, that it has no clips and is left
  out of the movie, without mentioning dragging or Move marked to…

### Requirement: Edit mode drags clips between chapters

While the event lists more than one chapter, a deleted one aside, the operator SHALL be able to drag a clip
on disk (active or new) that a chapter plays into any other listed chapter. The operator SHALL be able to
drop it there before any clip that chapter plays, or after the last of them. Both ways a clip is dragged
within its chapter SHALL do this:

- **with a mouse, pen or touch**, from the clip's handle. While the dragged clip is held near the window's
  top or bottom edge, the page SHALL scroll by itself, so that a chapter out of view can be reached. The
    speed SHALL grow with how far into the edge the pointer is, from nothing at the inner edge of the
    scrolling zone, and with the pointer at the window's very edge it SHALL be at least 600 and at most 2,000
    CSS pixels per second, however many rows the page holds.
- **from the keyboard**, on the clip's handle:
  - Down at a chapter's last position SHALL take the clip to the first position of the next listed chapter.
  - Up at a chapter's first position SHALL take it to after the last clip of the chapter before.
  - A deleted chapter's placeholder SHALL be passed over.
  - Page Down SHALL take the clip to the first position of the next listed chapter, and Page Up to the first
    position of the chapter before, wherever the clip is held. A chapter the clip does not play is entered at
    its first gap, before its first clip, and an empty one at its area. At the last chapter (Page Down) or the
    first (Page Up), and for a missing clip, which stays in its chapter, and while one chapter is listed, the
    key SHALL move nothing. When it moves the clip, the place the clip is then over (the line, or the empty
    chapter's area) and the dragged copy SHALL both be in the window, however far the page had to scroll to
    get there. A Page Down or Page Up pressed while a clip is lifted SHALL NOT otherwise scroll the page, whether
    or not it moved the clip.
  - Escape SHALL cancel and leave every chapter as it was, with the clip's handle in view again (its whole
    row, or its first line when the row is taller than the room left).

A chapter that plays no clip SHALL show, in Edit mode, an area for clips. While the event lists another
chapter, a deleted one aside, the area SHALL say that clips can be dragged into it. When the chapter is the
only one listed, the area SHALL say only what "Edit mode adds, renames, reorders and deletes chapters" states
for it, because no other chapter has a clip to drag. The area SHALL be shown whether or not a drag is under
way. A clip dropped on it SHALL become the chapter's first clip.

While a clip is dragged over another chapter:

- the page SHALL show where a drop puts it: a line at the place between two of that chapter's clips or after
  its last clip, or, for a chapter that plays no clip, its area marked as the target
- a copy of the clip SHALL follow the pointer and SHALL name the target chapter and the position that the drop
  gives the clip
- that chapter's clips SHALL NOT move to make room, and no part of the page SHALL change size or place;
  within the clip's own chapter, its other clips still make room, as before
- the clip's own row SHALL stay in its chapter, marked as the clip being moved, until it is dropped
- while the clip is held by a pointer, no other part of the page SHALL show that the pointer is over it,
  and the pointer SHALL show that it holds the clip
- in forced colors, the line and the copy's edge SHALL stay visible

Within its own chapter, a clip SHALL stay at its place while the pointer is over its own row, however tall
the row is: lifting a clip and releasing it there moves nothing.

A drop into another chapter SHALL be one edit. The clip leaves its chapter and joins the other one at the
position where it was dropped. Every other clip keeps its order. Then:

- its row SHALL show the chapter it came from, and it SHALL count once as a moved clip, in its new chapter's
  heading and in the save bar, as a clip moved with Move marked to… does
- a clip dragged back to the chapter and the position it had when Edit mode opened SHALL count as no move;
  with no other edit, the page SHALL show no unsaved changes
- it SHALL keep its cuts and its other per-clip properties. Its Cuts control SHALL be as it was, and its
  panel stays shown or hidden as it was and keeps any time typed but not added
- Save SHALL write it as it writes a clip moved with Move marked to… ("Saving an edit writes only what the operator
  changed"). Reset, the unsaved-changes question, a conflict and Overwrite SHALL treat it as any other edit

Every target in another chapter SHALL be announced to assistive technology, and so SHALL a drop and a
cancel. The announcement names the clip as its row named it when it was lifted. A target or a drop in another
chapter SHALL name that chapter, and SHALL give the position out of the number of clips that chapter would
then play. Within the clip's own chapter the announcements SHALL stay as "The event page reorders clips
within a chapter" states. While more than one chapter is listed, the instructions for a keyboard drag SHALL
say that the arrows cross into the chapter before or after, and that Page Down and Page Up jump to the next
or the previous chapter.

After a drop into another chapter, by pointer or keyboard, keyboard focus SHALL be on the moved clip's
handle in its new chapter. The handle and the row's first line (its handle, name and Cuts control) SHALL be
fully visible, not covered by the page header, the chapter's heading or the save bar. A row taller than that
space SHALL be scrolled so that its first line is (see "Edit mode keeps keyboard focus in view and never
drops it").

Some clips cannot be marked ("Edit mode marks clips to move together"), so Move marked to… never moves them,
and those SHALL NOT be taken into another chapter by a drag either:

- a missing clip: its drag SHALL stop at its own chapter's edge, from the keyboard too. While more than one
  chapter is listed, its lift SHALL say that it stays in its chapter.
- an ignored clip, and a missing clip the operator removed: neither has a handle

A release over a deleted chapter's placeholder SHALL move nothing and SHALL be announced as a drop that
changed nothing. While a save is in flight, or while a move of marked clips is being applied, no clip SHALL be
lifted, and a drop SHALL move nothing. Move marked to…, and Move up and Move down, SHALL work as they
did before.

In the Clips help ("Each explanation sits behind a Help toggle of its section"), Edit mode SHALL say how clips are moved:

- with one chapter: that a clip is dragged by its handle or moved with its arrows, and that a chapter can be
  added with Add chapter, below the chapters, after which clips can be dragged between chapters
- with more than one chapter: that a clip can also be dragged into another chapter, and that Move marked to… moves the marked clips to a chapter

On a coarse pointer a drag SHALL start only from the handle, as within a chapter. In a window 320 CSS pixels
wide or wider, and in both color schemes, no state of a drag SHALL make the page scroll horizontally. Under
reduced motion, no clip SHALL slide into place, and the dragged copy SHALL NOT slide between positions.

#### Scenario: Dragging a clip into the chapter above
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the operator drags `Kvällen/s1710003.mp4` by its
  handle up into `Main` and holds it over the upper half of `s1710001.mp4`
- **THEN** a line shows above `s1710001.mp4`, the dragged copy says it goes to `Main` at position 1 of 2, and
  `s1710001.mp4` has not moved
- **WHEN** the operator releases it there
- **THEN**
  - `Main` plays `Kvällen/s1710003.mp4` and then `s1710001.mp4`, the first marked as coming from `Kvällen`,
    and its heading says 1 clip moved
  - `Kvällen` plays `s1710002.mp4` and the new `s1710004.mp4`, and its heading counts no clip moved
  - keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`, and the row's first line is fully
    visible above the save bar
  - "s1710003.mp4 moved to “Main”, position 1 of 2" is announced
  - the save bar says that 1 clip moved and that saving adds 1 new clip to `reel.yaml`

#### Scenario: Saving a dragged clip
- **WHEN** after that drag the operator saves
- **THEN** `reel.yaml`'s default chapter lists `Kvällen/s1710003.mp4` and then `s1710001.mp4`, `Kvällen` lists
  `Kvällen/s1710002.mp4` and then `Kvällen/s1710004.mp4`, `s1710004.mp4` is still ignored, and no other line
  of the file changed

#### Scenario: Dragging a clip back leaves nothing to save
- **WHEN** after the drag into `Main` on `2024-08-20 - Två kapitel - Tjörn`, the operator drags
  `Kvällen/s1710003.mp4` back into `Kvällen` and releases it between `s1710002.mp4` and `s1710004.mp4`
- **THEN** both chapters play what they played when Edit mode opened, no row is marked as moved, and the page
  shows no unsaved changes

#### Scenario: Crossing into the next chapter from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator focuses the handle of `s1710001.mp4`, lifts the
  clip and presses Down
- **THEN** "s1710001.mp4 is over “Kvällen”, position 1 of 4" is announced, and a line shows above
  `s1710002.mp4` in `Kvällen`
- **WHEN** the operator presses Down again and drops the clip
- **THEN**
  - `Kvällen` plays `s1710002.mp4`, `s1710001.mp4`, `s1710003.mp4` and `s1710004.mp4`, with `s1710001.mp4`
    marked as coming from `Main`
  - `Main` plays no clip, still lists the ignored `s1710004.mp4`, and shows its area for clips dragged into it
  - "s1710001.mp4 moved to “Kvällen”, position 2 of 4" is announced
  - keyboard focus is on the handle of `s1710001.mp4` in `Kvällen`

#### Scenario: Crossing into the chapter before from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `Kvällen/s1710002.mp4` from the keyboard,
  presses Up once and drops it
- **THEN** "s1710002.mp4 is over “Main”, position 2 of 2" was announced, and `Main` plays `s1710001.mp4` and
  then `Kvällen/s1710002.mp4`

#### Scenario: Page Down jumps to the next chapter from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `s1710001.mp4` from the keyboard and presses
  Page Down
- **THEN** "s1710001.mp4 is over “Kvällen”, position 1 of 4" is announced, and a line shows above
  `s1710002.mp4` in `Kvällen`
- **WHEN** the operator presses Page Down again
- **THEN** the line has not moved and nothing is announced
- **WHEN** the operator presses Page Up
- **THEN** "s1710001.mp4 is over position 1 of 1." is announced, and the line in `Kvällen` is gone
- **WHEN** the operator drops the clip
- **THEN** "s1710001.mp4 dropped at position 1 of 1, unchanged." is announced, and both chapters are as they were

#### Scenario: Page Down and Page Up cross a long chapter in one press
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, `Kväll`, and the operator
  lifts the 200th clip of the first chapter from the keyboard and presses Page Down
- **THEN** "c0200.mp4 is over “Kväll”, position 1 of 4" is announced, and the line above `Kväll`'s first clip
  and the dragged copy are both in the window
- **WHEN** the operator presses Page Up
- **THEN** "c0200.mp4 is over position 1 of 400." is announced, and the first clip's row and the dragged copy
  are both in the window
- **WHEN** the operator presses Escape
- **THEN** the clip is back at position 200 of 400, with its handle in the window

#### Scenario: Page Up jumps to the chapter before from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `Kvällen/s1710004.mp4` from the keyboard
  (the third position of `Kvällen`), presses Page Up and drops it
- **THEN** "s1710004.mp4 is over “Main”, position 1 of 2" was announced, and `Main` plays `Kvällen/s1710004.mp4`
  and then `s1710001.mp4`

#### Scenario: Page keys with one chapter or a missing clip move nothing
- **WHEN** in a window 390 × 600 on `2024-06-27 - Grillning med grannar`, which has one chapter, the operator
  lifts `s1710001.mp4` from the keyboard and presses Page Down with the page scrolled to its top
- **THEN** the clip is still over its own place, nothing is announced, and the page has not scrolled
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator lifts `borttagen.mp4` and
  presses Page Down
- **THEN** the clip is still over its place in `Main`, and `Morgon` plays no clip

#### Scenario: Escape cancels a drag into another chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `s1710001.mp4` from the keyboard, presses
  Down twice, and presses Escape
- **THEN** both chapters are as they were, keyboard focus is on the handle of `s1710001.mp4`, fully visible,
  and "Move cancelled. s1710001.mp4 is back at position 1 of 1." is announced

#### Scenario: A tall row lifted and released in place
- **WHEN** in a window 390 × 844 on `2024-08-20 - Två kapitel - Tjörn`, with the Cuts panel of
  `Kvällen/s1710003.mp4` shown, the operator presses its handle, moves the pointer 10 pixels and releases it
- **THEN** "Picked up s1710003.mp4, position 2 of 3." and "s1710003.mp4 dropped at position 2 of 3,
  unchanged." are announced, and `Kvällen` plays `s1710002.mp4`, `s1710003.mp4` and `s1710004.mp4` as before

#### Scenario: Dragging a clip into an empty chapter
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a chapter `Kvällen vid grillen`
- **THEN** the new chapter shows an area that says clips can be dragged into it
- **WHEN** the operator drags `s1710004.mp4` onto that area
- **THEN** the area is marked as the target, the dragged copy says it goes to `Kvällen vid grillen` at position
  1 of 1, and nothing else on the page has moved
- **WHEN** the operator releases it and saves
- **THEN** `reel.yaml` lists `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4` in the default chapter and
  `s1710004.mp4` in `Kvällen vid grillen`, and the save bar said that 1 chapter was added and 1 clip moved

#### Scenario: A deleted chapter takes no clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator marks all three clips of `Kvällen` and moves them to `Main`
  with Move marked to…, deletes `Kvällen`, adds a chapter `Morgon`, lifts `Kvällen/s1710004.mp4` (last in `Main`)
  from the keyboard and presses Down
- **THEN** "Kvällen/s1710004.mp4 is over “Morgon”, position 1 of 1" is announced: the deleted `Kvällen` was
  passed over
- **WHEN** the operator presses Escape, then drags `Kvällen/s1710004.mp4` with the mouse and releases it over
  the deleted `Kvällen`
- **THEN** no chapter changed, and the drop is announced as one that changed nothing

#### Scenario: A missing clip stays in its chapter
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator lifts `borttagen.mp4`
  from the keyboard
- **THEN** "Picked up borttagen.mp4, position 3 of 3. It is missing, so it stays in “Main”." is announced
- **WHEN** the operator presses Down and drops it
- **THEN** `borttagen.mp4` is still at position 3 of `Main`, and `Morgon` plays no clip

#### Scenario: A dragged clip keeps its cuts and what was typed
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens the Cuts of `Kvällen/s1710002.mp4`, adds a
  cut from 0 to 1.5 seconds, types `2` in the start field, and drags the clip into `Main` after `s1710001.mp4`
- **THEN** in `Main` the clip's Cuts panel is still shown, listing that cut, and its start field holds `2`;
  keyboard focus is on its handle, and the row's first line (handle, name, Cuts control) is fully visible,
  below the chapter's heading and above the save bar; the save bar says that a cut was typed on
  `Kvällen/s1710002.mp4` and not added, and Save says that it is unavailable

#### Scenario: No drag while a save is in flight
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a dragged clip not yet saved, the operator presses Save
  and the service has not answered yet
- **THEN** pressing Space on the handle of `s1710001.mp4` lifts nothing and announces nothing, a mouse drag
  from that handle moves nothing, and every chapter stays as it was

#### Scenario: Dragging by touch on a phone
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, a touch starts on the
  handle of `Kvällen/s1710002.mp4` and moves up into `Main` above `s1710001.mp4` before it lifts
- **THEN** `Main` plays `Kvällen/s1710002.mp4` first, and the page did not scroll horizontally
- **WHEN** a touch starts on that clip's name and moves up
- **THEN** the page scrolls, and no clip moves

#### Scenario: The edge scrolls fast enough to cross a long chapter, and no faster
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, the operator lifts the second
  chapter's first clip with the pointer, with the page scrolled to that chapter, and holds the pointer at the
  window's very top edge (its first pixel row) for 2 seconds
- **THEN** the page scrolled up between 1,200 and 4,000 CSS pixels over those 2 seconds (an average between 600
  and 2,000 per second)
- **WHEN** the operator moves the pointer out of the scrolling zone
- **THEN** the page stops scrolling
- **WHEN** the operator holds the pointer in the middle of the zone (a tenth of the window's height below its
  top edge) for 2 seconds
- **THEN** the page scrolls up by between a quarter and three quarters of what it scrolled at the very edge

#### Scenario: Reaching a chapter out of view
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, and the operator drags the
  second chapter's first clip up and holds it at the window's top edge
- **THEN** the page scrolls up by itself until the first chapter's first clip is in view
- **WHEN** the operator releases the clip over the upper half of that first clip
- **THEN** the clip is at position 1 of 401 in the first chapter, and the second chapter plays 2 clips

#### Scenario: The hint says how to reach other chapters
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, which has one chapter
- **THEN** the Clips help, opened, says that a chapter can be added with Add chapter, below the chapters,
  and that clips can then be dragged between chapters
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the Clips help says that a clip can be dragged into another chapter, and that Move marked to… moves the marked clips to a chapter

#### Scenario: Nothing shifts while dragging over another chapter
- **WHEN** in a window 320 pixels wide, in the light and in the dark scheme, on `2024-08-20 - Två kapitel -
  Tjörn`, the operator drags `s1710001.mp4` over `Kvällen` and holds it between `s1710002.mp4` and
  `s1710003.mp4`
- **THEN** every clip row and both chapter panels keep the size and place they had before the drag, the line
  between the two clips is visible beside the dragged copy, and the page does not scroll horizontally

### Requirement: Edit mode marks clips to move together

In Edit mode, every clip that a chapter plays and that is on disk (active or new) SHALL have a **mark**: a
checkbox in the top-right corner of its thumbnail, named "Mark <name>", where <name> is the clip's name as its row
names it. A marked clip SHALL show a check icon inside the box, so that its state is not told by colour alone, and the
box SHALL be exposed to assistive technology as checked. Pressing the box, or Space on it, SHALL mark an unmarked clip
and unmark a marked one. The box SHALL be 24 CSS pixels square and SHALL lie inside the thumbnail's box, with its
top-right corner within 6 CSS pixels of the thumbnail's top-right corner, in the one-line layout and in the narrow
layout. The thumbnail's own size and place SHALL stay as they are ("Every clip row shows a frame from its clip").

When the browser's primary pointer is coarse, a tap anywhere in a 44 × 44 CSS pixel area around the box SHALL reach the
mark, taking precedence over the clip's Watch button where the two overlap; the rest of the thumbnail SHALL still open
the clip's preview. The areas of the mark and of the row's other controls SHALL NOT otherwise overlap. When the primary
pointer is fine, the mark SHALL keep the 24 pixel box and nothing around it.

Three kinds of clip SHALL have no mark, as a drag does not take them into another chapter ("Edit mode drags
clips between chapters"): a missing clip, an ignored clip, and a missing clip the operator removed. The Clips help SHALL
say so in a few words.

Marking is not an edit. It SHALL NOT show the save bar, SHALL NOT count as an unsaved change, SHALL NOT enable Reset or
Save, and SHALL NOT make leaving Edit mode ask first. Marks SHALL be kept per clip, whichever chapter it is in, and a
mark SHALL stay on its clip when another edit moves the clip (Move up, Move down, a drag of another clip), and when the
Cuts panel is opened or closed.

A line above the chapters SHALL always be present in Edit mode and SHALL hold the Clips help's toggle. How clips are marked, that dragging a marked
clip's handle moves all marked clips, and that Move marked to… moves them to a chapter SHALL be said in the Clips help, not in the line. While at least one clip is marked, the line SHALL show how many ("1 clip
marked", "3 clips marked") and a **Clear marks** button. The line SHALL keep its height whether or not it shows the
count, so that marking the first clip, and clearing the last mark, move no row.

Each change of a mark, and Clear marks, SHALL be announced once to assistive technology, with the clip's name and the
count ("s1710002.mp4 marked. 2 clips marked.", "s1710002.mp4 unmarked. No clips marked.", "Marks cleared."). Marks
SHALL end as follows:

- a clip that a drag or Move marked to… moves into another chapter, or that a group drag moves, SHALL be unmarked by that
  move; a drop that changes nothing SHALL leave every mark
- all marks SHALL end on a successful Save, on Reset, when Edit mode is left, and when the editor reads the event's
  `reel.yaml` again (Reload latest)
- a drag of an unmarked clip, Move up, Move down, adding, renaming or deleting a chapter, and cut edits SHALL leave
  marks as they are

The mark and Clear marks follow the busy-control rule: while a save is in flight or a move of marked clips is being applied, they
SHALL be aria-disabled and ignore presses, never `disabled`. A mark's keyboard focus ring SHALL be visible in both
color schemes and in forced colors. Pressing Clear marks SHALL move keyboard focus to that line, since the button leaves with the count.
The mark SHALL NOT start a drag, and a press on it SHALL NOT lift its row. Marking
a clip in a chapter that plays 400 clips, in a Chromium window 1280 × 900, SHALL reach the next painted frame within
100 ms (the median of five runs, each in a fresh Edit mode).

#### Scenario: Marking two clips
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` and then
  `Kvällen/s1710003.mp4` with the boxes at the top right of their frames
- **THEN**
  - each box shows a check icon and is exposed as checked, named "Mark s1710002.mp4" and "Mark s1710003.mp4"
  - the line above the chapters says "2 clips marked" and offers Clear marks
  - "s1710003.mp4 marked. 2 clips marked." was announced, and the save bar is not shown
  - no row moved when the first mark was made

#### Scenario: Missing and ignored clips have no mark
- **WHEN** on `2024-09-01 - Sommarlov` the operator looks at the row of the missing `borttagen.mp4`, and on
  `2024-08-20 - Två kapitel - Tjörn` at the row of the ignored `s1710004.mp4`
- **THEN** neither row has a mark, and the Clips help, opened, says that missing and ignored clips cannot be
  marked

#### Scenario: Marking by touch next to the Watch button
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, the operator taps in a
  44 × 44 pixel area centred on the box of `Kvällen/s1710002.mp4`, which sits over the top right of its Watch button
- **THEN** the clip is marked and its preview did not open
- **WHEN** the operator taps the middle of that thumbnail
- **THEN** the clip's preview opens and the mark is unchanged

#### Scenario: Marks are not an unsaved change
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710003.mp4`, and then
  leaves Edit mode
- **THEN** no question about unsaved changes was asked and the save bar was never shown
- **WHEN** the operator enters Edit mode again
- **THEN** no clip is marked and the line shows no count

#### Scenario: A mark with the keyboard only
- **WHEN** using only the keyboard on `2024-06-27 - Grillning med grannar`, the operator tabs to the mark of
  `s1710002.mp4`, which shows a focus ring, and presses Space, and then tabs to Clear marks and presses Enter
- **THEN** "s1710002.mp4 marked. 1 clip marked." and then "Marks cleared." were announced, and keyboard focus is on
  the line above the chapters (reachable by script, not by Tab), not lost to the page

#### Scenario: Marks are held while a save is pending
- **WHEN** on `2024-06-27 - Grillning med grannar`, after moving `s1710004.mp4` up one place, the operator presses
  Save and the service has not answered yet, and then presses a clip's mark
- **THEN** the mark does not change, and it is aria-disabled, not `disabled`

#### Scenario: A mark survives other edits and ends on Save
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710002.mp4`, moves `s1710001.mp4` down one
  place, shows the Cuts of `s1710002.mp4`, and then saves
- **THEN** `s1710002.mp4` was still marked after the move and after the Cuts panel, and after the save no clip is
  marked

#### Scenario: Marking in a long chapter
- **WHEN** in a Chromium window 1280 × 900, on an event whose one chapter plays 400 clips, the operator marks the
  200th clip, five times, each in a fresh Edit mode
- **THEN** the median time from the press to the next painted frame is at most 100 ms

### Requirement: Edit mode moves the marked clips to a chapter

While the event lists more than one chapter, a deleted one aside, the line above the chapters that offers Clear marks
and Rotate marked left and right ("Edit mode marks clips to move together") SHALL also offer **Move marked to…**: a
group named by those words, holding a chapter picker and a button named **Move**. No chapter SHALL offer a Move clips
button, and the page SHALL NOT open a dialog to pick clips: the clips to move are the ones marked, and the page SHALL
NOT have a Pick all or a Pick marked control. When the event lists one chapter, the control SHALL NOT be offered, as no
other chapter has a place for a clip.

The picker SHALL be a native `select` named "Chapter to move the marked clips to". It SHALL list every chapter the
page lists, a deleted one aside, in the order the page lists them, each by the name its heading shows (the event's own
chapter as `Main`, as its heading reads), and it SHALL start on a first option that is no chapter, "Choose a chapter".
A chosen chapter that is then deleted SHALL return the picker to that option. Renaming a chapter SHALL change its name
in the list.

**Move** SHALL be `aria-disabled` (never `disabled`, as the busy-control rule says) and SHALL give its reason in words, named by `aria-describedby` and offered as the button's tooltip, and shown in the toolbar's one reason line ("The marks line is one aligned unit") only once Move is pressed in that state, in each of these states, and press nothing. No line of the reason SHALL be shown while Move is not pressed:

- no clip is marked: "Mark a clip to move it."
- no chapter is chosen: "Choose a chapter."
- a save is in flight, or a move of marked clips is pending: "Unavailable while saving."

Pressing Move with a clip marked and a chapter chosen SHALL be one edit, made by the group move of "Dragging a marked
clip moves the whole marked group" and not by logic of its own: the group is every marked clip, from every listed
chapter, in page order; it SHALL leave the chapters it was in and SHALL join the end of the chosen chapter as one run, in
page order. A marked clip that is already in the chosen chapter joins that run too, so the run is the last clips of the
chapter. Every clip that is not marked SHALL keep its order and its chapter. A chapter that loses all its clips SHALL
play none. A clip SHALL NOT be put back after its old predecessors when it returns to the chapter it was in when Edit
mode opened: a move to the end is the same edit as a drop at the end of that chapter.

After the move:

- every moved clip SHALL be unmarked (the group is every marked clip, so no mark is left)
- the move SHALL be announced once, politely, with the number of clips and the chosen chapter's name, "3 clips moved to
  “Dag 2”." or "1 clip moved to “Main”."
- each moved clip that changed chapter SHALL show, in its row, the chapter it came from instead of its old position,
  and SHALL count once as a moved clip in its new chapter's heading and in the save bar, as a clip dragged does; within
  a chapter, the page SHALL count the fewest clips that explain the new order
- a clip SHALL keep its cuts and its other per-clip properties, its Cuts panel shown or hidden as it was, any time
  typed but not added, and its preview open as "Edit mode previews a clip on request" says
- Save SHALL write the order as it writes a drag's, and Reset, the unsaved-changes question, a conflict and Overwrite
  SHALL treat the move as any other edit
- keyboard focus SHALL stay on Move, the chosen chapter SHALL stay chosen, and no row SHALL be scrolled out of the
  operator's view by the move

A move that changes no chapter's order (the marked clips already are the last of the chosen chapter, in page order)
SHALL leave the draft, the marks and the save bar as they are and SHALL be announced as "Nothing moved." A clip that
has no mark (a missing clip, an ignored clip, a removed one) is never moved by this control, as it is never marked.

Move marked to… SHALL stay beside dragging. A drag of a marked clip takes the marked group to the place where it is
dropped (see "Dragging a marked clip moves the whole marked group"), from the keyboard on a handle too; Move marked
to… takes the same group, always to the end of one chosen chapter, with a keyboard, a screen reader or a touch screen
and with no drag at all. A clip's Move up and Move down still never take it into another chapter (see "The event page
reorders clips within a chapter").

On a coarse pointer the picker and Move SHALL each take a tap anywhere in an area at least 44 CSS pixels tall that does
not overlap another control's. The group SHALL wrap in a window 320 CSS pixels wide, on its own row under the marks line's other controls, its label above the picker and the picker beside Move, without a horizontal page scroll, in both color schemes. The group SHALL keep its place and its
height whether or not a clip is marked, so that marking the first clip moves no row, and its focus ring SHALL be
visible in both color schemes and in forced colors. Reading a screen SHALL NOT change what is chosen.

#### Scenario: Moving two marked clips from different chapters to Test
- **WHEN** in Edit mode on an event whose chapters are `Main`, `Kvällen` and `Test`, the operator marks `Main/a.mp4`
  and `Kvällen/c.mp4`, chooses `Test` in the picker and presses Move
- **THEN**
  - `Test` plays what it played before and then `a.mp4` and `c.mp4`, last, in that page order
  - neither clip is marked and the line above the chapters shows no count
  - "2 clips moved to “Test”." was announced once
  - the save bar says that 2 clips moved
  - the picker still shows `Test`, and keyboard focus is on Move
- **WHEN** the operator presses Save
- **THEN** `reel.yaml` lists `a.mp4` and `c.mp4` last in `Test`'s clips and nothing else changed

#### Scenario: Move says why it is unavailable
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, with no clip marked
- **THEN** Move is `aria-disabled` and not `disabled`, and no line of words is beside it, "Mark a clip to move it." is its description and tooltip, and pressing it shows those words in the toolbar's reason line
- **WHEN** the operator marks `Kvällen/s1710002.mp4`
- **THEN** its description reads "Choose a chapter."
- **WHEN** the operator chooses `Main` and presses Move
- **THEN** `s1710002.mp4` is last in `Main`, marked as coming from `Kvällen`, unmarked, and "1 clip moved to “Main”." is
  announced

#### Scenario: Moving with the keyboard only
- **WHEN** using only the keyboard on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` with
  Space, tabs to the picker, chooses `Main` with the arrow keys, tabs to Move and presses Enter
- **THEN** `s1710002.mp4` is last in `Main`, "1 clip moved to “Main”." was announced, and keyboard focus is on Move

#### Scenario: The marked clips already are last
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `Kvällen/s1710002.mp4` to `Main` and marks it
  again, chooses `Main` and presses Move
- **THEN** "Nothing moved." is announced, the clip is still marked, and the save bar counts what it counted before

#### Scenario: One chapter offers no move
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose clips are all in one chapter
- **THEN** the line above the chapters offers no Move marked to…, and no chapter offers a Move clips button

#### Scenario: The old per-chapter control is gone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, in Chrome and in Firefox
- **THEN** the words "Move clips" appear nowhere on the page, in any chapter's controls, dialogs or accessible names

#### Scenario: Move waits for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a clip marked and a chapter chosen, the operator presses Save
  and the service has not answered yet, and then presses Move
- **THEN** Move is `aria-disabled` and says "Unavailable while saving.", and nothing moves

#### Scenario: A deleted chapter leaves the picker
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator chooses `Kvällen` in the picker and then deletes `Kvällen`
- **THEN** the picker lists `Main` only and shows "Choose a chapter"

#### Scenario: The control fits a phone
- **WHEN** on a touch screen 320 pixels wide, in the light and in the dark scheme, on
  `2024-08-20 - Två kapitel - Tjörn`, the operator looks at the line above the chapters
- **THEN** the picker and Move are on a line of their own, each takes a tap in an area at least 44 pixels tall, none
  overlaps another, and the page does not scroll horizontally

### Requirement: The marks line is one aligned unit

The line above the chapters that shows how clips are marked and offers Clear marks, Rotate marked left, Rotate marked right and Move marked
to… ("Edit mode marks clips to move together", "Edit mode moves the marked clips to a chapter") SHALL read as one calm, aligned toolbar from 320 to
1280 CSS pixels wide, in both colour schemes and for both kinds of pointer.

- **One control height.** Clear marks, both Rotate buttons, Move and the chapter picker SHALL have the same height, one size for the line (at least 44 CSS pixels
  where the primary pointer is coarse), and the same corner radius.
- **One axis.** Controls in a row SHALL have their vertical centres within 1 CSS pixel of each other, and a text beside them (the Help toggle, the count of marked clips, the label "Move marked to…") SHALL be centred on the same axis. No item SHALL sit higher or lower than
  its neighbours.
- **Consistent gaps.** The gap between two controls of a group, between two groups and between two rows SHALL each be one value, the same in every row and at every width.
- **Rows.** The first row SHALL hold the Clips help's toggle and, at its end, the count and Clear marks; the second SHALL hold Rotate marked left and right, then the Move marked to… group (label, picker,
  Move) where it fits; the reason SHALL be shown only after Move is pressed while it is unavailable, as one muted line below the controls, starting at the toolbar's left edge, and SHALL go when the marks, the chosen chapter or the save state change the reason. The reason SHALL NOT float beside Move. Marking or unmarking a clip SHALL move no row of the toolbar other than that line.
- **Narrow windows.** Where the toolbar does not fit a row, it SHALL wrap by whole groups: the Move group goes on a row of its own with the label above, the picker filling the
  row beside Move; Rotate marked left and right share a row where they fit and otherwise take a row each at the same width. Every wrapped row SHALL keep the one height and the
  one axis, and nothing SHALL scroll horizontally at 320 CSS pixels.
- The names, descriptions, `aria-disabled` states and reasons of the controls ("Edit mode moves the marked clips to a chapter") are unchanged.

#### Scenario: Controls in a row share a height and an axis
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` at 1280 px, light and dark, with one clip marked
- **THEN** the bounding boxes of Clear marks, Rotate marked left, Rotate marked right, the chapter picker and Move have the same height, and in each row the vertical centres of
  its controls, and of the label "Move marked to…" and the count, differ by at most 1 px

#### Scenario: The reason is one muted line below
- **WHEN** no clip is marked
- **THEN** no reason line is shown, and Move's description is "Mark a clip to move it."
- **WHEN** the operator presses Move
- **THEN** "Mark a clip to move it." is one muted line below the controls, aligned to the toolbar's left edge, and not beside Move
- **WHEN** the operator marks a clip
- **THEN** no row of the toolbar other than that line and no chapter below it moves, and the line says "Choose a chapter."

#### Scenario: The toolbar wraps in aligned rows
- **WHEN** the window is 390 px wide and again 320 px, light and dark
- **THEN** the Move group is on its own row with the label above and the picker beside Move, every row's controls share one height and one centre line (within 1 px), the
  reason line, when shown, is below them, and the page does not scroll horizontally

### Requirement: Running times are written to a fixed width and say what they are

Every time the client shows while something moves (the Timeline's readout under its video, the clip player's header,
the Timeline's trim tip and its movie stat) SHALL be written by one formatter, the **clock**, and
SHALL NOT be written in the form that the Cuts panel writes cut times in (`0:01.5`, `0:02.607`), which keeps its own
job: a cut's time, a typed field, a spoken word. The ruler's tick labels and the chapter list's start times do not
move while something plays and keep that form.

**One scale per readout.** A readout SHALL be written to a scale taken from the longest value it can show, not from
the value it shows. Minutes SHALL be zero-padded to the digits of the longest value's minutes (`0:09.50 of 0:39.84`
when the longest is under ten minutes, `09:59.99 of 12:30.00` when it is not), hours SHALL appear in every value of a
readout or in none (none unless the longest is an hour or more), and seconds SHALL always have two digits. The
fraction SHALL have the same number of digits in every value of every readout of that kind, trailing zeros kept:
two (centiseconds) for the Timeline's and the player's readouts and the summary line, three (milliseconds) for the
trim tip, which shows the time a cut will have. A value SHALL be cut down to those digits, never rounded up, so that
a position never reads later than its total. A value above the longest SHALL be shown as the longest. A value that
is not known (the player's length before the browser has read it) SHALL be shown as dashes in the same places
(`-:--.--`), never as `0:00`. A value that is negative or not a number SHALL NOT be written: it is an error, never a
made-up time.

**Constant width.** A running time SHALL occupy a width that depends on its scale and on nothing else: it SHALL have
a reserved width in the width of a digit of its monospace face, digits of equal width, and its text SHALL stay on
one line. While a clip plays, while the playhead is scrubbed or stepped, and when the playhead passes from one clip
into another, no readout's width and no readout's left edge SHALL change, and nothing after a readout on its line
SHALL move. A readout's width MAY change when its scale does, which only the set of clips (a Prepare job that ends,
a clip that goes) or the clip's length being read can cause, and SHALL NOT change at any other moment.

**Words.** A readout SHALL say what each number is in words that stay on the screen: the Timeline's reads `Clip
0:00.96 of 0:39.84 · Event 1:02.40 of 2:29.76`, the first pair being the time in the clip the playhead is in and that
clip's length, the second the time in the whole timeline (the clips end to end, before cuts) and its length. The
clip pair's scale SHALL be that of the event's longest clip and the event pair's that of the whole timeline's length,
so that passing from a 9-second clip into a 40-second one changes no width. The clip player's header reads `Clip
0:20.48 of 0:20.64`. The Timeline's movie stat reads `Movie 3:20.00 · footage 3:45.00 · cuts −0:33.00 · cards +0:08.00`, every time to the scale of the longest of them. The trim tip reads the time alone, to the scale of its clip's length, and the words it adds when
the edge snaps SHALL NOT move that time.

**The name.** The clip's name in the Timeline's readout SHALL be shown on one line and, when it does not fit, SHALL be
cut with an ellipsis and keep its whole text as its tooltip; it SHALL NOT wrap and SHALL NOT move a number. On a
window 390 CSS pixels wide the name MAY take its own line, and the numbers SHALL then keep their widths.

**Both schemes, every width.** The readouts SHALL meet the page's contrast in the light and the dark scheme and SHALL
NOT make the page scroll horizontally from 320 CSS pixels up.

#### Scenario: Crossing a clip does not move the line
- **WHEN** the Timeline of an event whose clips are 9.00 s, 40.00 s and 6.02 s (55.02 s in all) plays from 0:08 into
  the second clip
- **THEN** the readout reads `Clip 0:08.20 of 0:09.00 · Event 0:08.20 of 0:55.02`, then `Clip 0:00.10 of 0:40.00 ·
  Event 0:09.10 of 0:55.02`, and the width of every time and the left edge of both pairs are the same in the two
  samples

#### Scenario: Nine seconds to ten
- **WHEN** the playhead of a 12-second clip goes from `0:09.99` to `0:10.00`
- **THEN** the readout's text is `0:09.99` and `0:10.00` in cells of one width, and nothing after it moves

#### Scenario: A long name is cut, not pushed
- **WHEN** the clip the playhead is in is named `IMG_20240627_201530_BURST042_final_v2.mp4` and the window is 390
  pixels wide
- **THEN** the name is on one line ending in an ellipsis, its tooltip is the whole name, the numbers have their usual
  widths, and the page does not scroll horizontally

#### Scenario: A cell in the trim tip
- **WHEN** the operator drags a handle on a 6.02 s clip across `0:01.25` and `0:01.30`
- **THEN** the tip reads `0:01.250` then `0:01.300`, the same width, and when the edge snaps the snap words appear
  without moving the time

#### Scenario: The length is not read yet
- **WHEN** a clip player has just opened and the browser has not read the clip
- **THEN** the header reads `Clip 0:00.00 of -:--.--`, with the time in cells as wide as they will be, and when the
  length is read it reads `Clip 0:00.00 of 0:06.02` with no change in the first cell's width

#### Scenario: A spoken form is not padded
- **WHEN** a screen reader reads the Timeline's slider at the moment of the first scenario's second sample
- **THEN** its value text reads `s1710002.mp4, clip 0:00.1 of 0:40; event 0:09.1 of 0:55.02`, in the Cuts panel's
  form, and the visible readout is not the slider's value

## ADDED Requirements

### Requirement: Each explanation sits behind a Help toggle of its section

The event page, in the read view and in Edit mode, SHALL keep instructional and explanatory text out of sight until asked for, and SHALL keep in sight every text that reports a state or needs an action. Each of these sections SHALL have **one** Help toggle in its header, a button named "Help" with an information icon: **Details** (Edit mode), **Poster** (Edit mode), **Timeline** (the read view and Edit mode), **Clips** (Edit mode: the row above the chapters, which holds the marks line) and the **Title cards** tab of the title card dialog. A section with no such text SHALL have no toggle.

The toggle SHALL be a `button` with `aria-expanded` and `aria-controls` naming its panel, operable by Enter and Space, with a target at least 44 CSS pixels high and wide, and with a visible focus ring. Pressed, it SHALL show the panel under the header: a calm, muted block that is not an alert, holds the section's explanations as paragraphs, and moves nothing above it. The panel SHALL stay in the document when closed (`hidden`), so that a control it describes keeps its `aria-describedby`. Closed is the default. Each section's state SHALL be kept per section (not per event) in `localStorage`, read when the section mounts, written when the toggle is pressed, and every access SHALL be guarded: a browser that refuses storage, or throws, SHALL leave the toggle working for the page visit, closed at the start, and SHALL show no error. The Timeline's state SHALL be one state for both modes.

Every text of these classes SHALL be in a panel and SHALL NOT be shown as a line of its own: the Details form's lead ("What reel.yaml says…", "Save writes these to reel.yaml…"), the Poster's "Pick the frame on the Timeline…", the Timeline's note that cards fade ("The Timeline fades a card…"), the note that dismissed suggestions return on reload, the cut fields' hint ("Enter takes a time; Escape puts the old one back"; the fields keep it as their `aria-describedby`), the Clips instructions ("Drag a clip by its handle…", "Mark clips with the box…", "The event's own chapter: …", "Ignored clips are not played and cannot be moved", "A missing clip is not on disk…"), the command that analyses an event (`auto-reel analyze <root>`, then Refresh), and the title cards tab's lead ("Every title card of this event follows these…"). The text SHALL be the same words as before. The classes that SHALL stay visible are: a refusal, an error or a warning; an unsaved or pending change and what saving will add ("Saving adds 2 new clips to reel.yaml"); a count ("2 clips marked", "1 ignored clip, not played"); the state words of a clip, a chapter, the poster and the render; a field's inherited-value hint; a reason an unavailable control gives (see "Edit mode moves the marked clips to a chapter"); the icon legend of the analysis lane; and the empty states of a chapter. Controls, fields, their names and what pressing them does SHALL NOT change.

#### Scenario: A section's help is closed, opens and closes
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` with nothing stored
- **THEN** the Details, Poster, Timeline and Clips sections each show a Help button with `aria-expanded="false"` and no explanation is visible
- **WHEN** the operator presses the Clips Help button, by mouse and again by keyboard
- **THEN** `aria-expanded` is `true` and "Drag a clip by its handle…" is visible under the header; pressing it again hides the panel, which stays in the document

#### Scenario: The state persists across a reload
- **WHEN** the operator opens the Timeline help, reloads the page, and then opens the same event in the read view
- **THEN** the Timeline help is open in both, and the other sections' help is closed

#### Scenario: Storage that throws
- **WHEN** `localStorage` throws on every access
- **THEN** every Help button works for the page visit, starts closed, and no error is shown

#### Scenario: Action and state stay visible
- **WHEN** an event with a missing clip, with an unsaved edit and with an event that needs a render is opened in Edit mode with every help closed
- **THEN** the missing clip's status, the "Needs render" state with its reason, the save bar's unsaved changes and the marks count are visible, and the explanations are not

#### Scenario: Fewer paragraphs of explanation
- **WHEN** `2024-08-20 - Två kapitel - Tjörn` is opened in the read view and in Edit mode, in Chrome and in Firefox, light and dark, at 1280 and 390 px, with every help closed
- **THEN** the number of visible paragraphs of instructional text is lower than before the change in each, the numbers are reported, and nothing overflows horizontally

#### Scenario: A toggle is large enough to touch
- **WHEN** any Help button is measured at 390 px
- **THEN** it is at least 44 CSS pixels high and wide, and it has an accessible name that names its section
