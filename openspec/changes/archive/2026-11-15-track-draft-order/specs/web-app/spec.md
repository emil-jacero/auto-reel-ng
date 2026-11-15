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
button SHALL be offered all the same and keeps the preview from the draft. While the Timeline draws a card built from the event's cards for it ("A chapter added while editing gets the event's card on the Timeline"), the dialog SHALL say that until Save its title card is drawn as the event's and that its own settings can be changed after Save; otherwise it SHALL say that its card is drawn after Save.

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
