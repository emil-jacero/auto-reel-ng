## ADDED Requirements

### Requirement: The Event tab lists the event's chapters

The inspector's Event tab SHALL hold a **Chapters** list after the Details form: one row per chapter, in the draft's
order, with the chapter's name and clip count and its tools, a deleted chapter's row until Save, and Add chapter
after the last row. It SHALL work whether or not the Timeline's track is open, and SHALL be the only place in Edit
mode that adds, moves or deletes a chapter ("Edit mode adds, renames, reorders and deletes chapters").

#### Scenario: Chapters while proxies are being prepared
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` while its Timeline shows Prepare and no track
- **THEN** the Event tab lists `Main` (1 clip) and `Kvällen` (3 clips) with their tools and Add chapter, and moving
  `Kvällen` up works

#### Scenario: An empty chapter is listed
- **WHEN** the operator adds a chapter `Morgon` to `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the Event tab lists `Morgon` last, counting 0 clips, saying that it has no clips and is left out of the
  movie, although the Timeline draws no band and no card for it

#### Scenario: The bin holds no chapter tool
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window
- **THEN** the bin's chapter headings hold each chapter's name and counts and no button, and the bin offers no Add
  chapter

## MODIFIED Requirements

### Requirement: Edit mode adds, renames, reorders and deletes chapters

In Edit mode the operator SHALL be able to change the event's chapters themselves, in the Event tab's Chapters list
("The Event tab lists the event's chapters"). Every control below SHALL be reachable with the keyboard and SHALL name,
to assistive technology, the chapter it acts on.

- **Add chapter**, after the last chapter of the Chapters list, SHALL ask for a name and add an empty chapter with
  that name at the end.
- **Rename** SHALL be done in the title card editor, in its Name field ("The title card editor holds every
  name and every title-card setting"), by the one workflow for every chapter. A chapter's row in the Chapters list,
  and its heading in the bin, SHALL show its name as plain text: not a
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

**The row.** Every chapter's row in the Chapters list, the event's own chapter's too, SHALL hold, in this order, the
chapter's name as plain text, the chapter's clip count, an **Edit Titlecard** button and the chapter's tools (Move up,
Move down, Delete, offered by the rules above). Edit Titlecard, Move up, Move down and Delete SHALL show an icon only,
keep their names and reasons, and offer their names (Edit Titlecard: its words) as tooltips. With a fine pointer a
row SHALL be one line at most 36 CSS pixels tall in the inspector; with a coarse pointer it keeps the 44 CSS pixel
targets and wraps onto a second line. The Edit Titlecard button SHALL be named "Edit title card for <name>" (the
event's own chapter: its heading) and SHALL select that card, showing its editor on the inspector's "This title card"
tab ("The title card editor is docked in the inspector"). A chapter's row SHALL show nothing under its line but the
notes of this requirement and of "Edit mode says what a chapter's name means for clips added later": no card row, no
"Main title card" line, no source line ("from the folder name"). In the bin, a chapter's heading SHALL hold its name
and counts ("The bin's chapter headings and lists say what they hold") and no button, and the bin SHALL offer no Add
chapter. A chapter added in the draft has no saved card, and its
button SHALL be offered all the same and keeps the preview from the draft. While the Timeline draws a card built from the event's cards for it ("A chapter added while editing gets the event's card on the Timeline"), the editor SHALL say that until Save its title card is drawn as the event's and that its own settings can be changed after Save; otherwise it SHALL say that its card is drawn after Save.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up or Move down, so that an event never saves without a chapter.

**Focus after the selection leaves the card.** When Escape clears the card selection from inside the editor, keyboard focus SHALL
return to the control that selected the card (the chapter's Edit Titlecard button in the Chapters list, which the Event tab then
shows, or the card block on the Timeline), so that the focused field never
unmounts onto the page body. Selecting something else leaves keyboard focus where the operator put it.

**The Name field.** In the editor the field SHALL be the first of "This title card" and SHALL be named "Name of chapter <name>"
for a chapter and "Title of the event" for the event's own chapter, where <name> is the name the draft holds when the editor opens. The
chapter's row, its heading in the bin and the editor's title name the chapter by its name alone.

- An accepted name SHALL be written to the draft as it is typed, so that the editor's heading, its preview, the chapter's
  heading in the bin, its row in the Chapters list and every chapter picker follow it. A name equal to the chapter's current name, once the spaces
  around it are removed, SHALL change nothing. A rename SHALL be announced once, when keyboard focus leaves the field or the selection leaves the card, and not for each key; typing a name and typing the old one back announces nothing.
- A refused name SHALL be explained under the field in words, in a `role="alert"` that is remounted for each refusal, and the
  field SHALL be marked invalid. The draft keeps the last accepted name, and the field keeps the typed text. Enter, with a refused
  name in the field, SHALL keep the field invalid and announce the refusal. Escape, and the selection of anything else, SHALL return the
  field's text to the draft's name and announce that the name was not changed and why; they SHALL NOT keep a refused name.
- While the field holds a refused name, Ctrl+S SHALL save nothing and SHALL say "Not saved: the name is refused."
- While a save or a move of several clips is pending, the field and the editor's other fields SHALL say that they are unavailable
  and SHALL change nothing (the busy-control rule); the row's Edit Titlecard button SHALL say so too and select nothing.
- Reset, a conflict and Overwrite SHALL treat a name as any other edit; Reset SHALL restore the chapters' names as read.

**The event's own chapter's name is the event's title.** For the event's own chapter the Name field SHALL edit the draft's
title, the one the Details form's Title field edits, in step with it in both directions, counted once in the save bar ("Title") and
undone by Reset as one edit.

- The field SHALL hold the draft's title. While that is blank it SHALL be empty with the title the page resolved from the folder
  name as its placeholder and the words "From the folder name", else the word "Untitled". The page SHALL NOT guess a title.
- Any text SHALL be kept as the title, with no rule of the page's. A blank title means that it inherits from the folder name, and
  the field SHALL say so in the words of the Details form ("Left empty: inherits from the folder name when saved"). The
  service's refusal of an unusable title stays at the Details form and is retired by editing the title in either place.
- While the draft's title differs from the title read, the editor SHALL say that saving changes the movie's file name, that if the
  movie was already rendered the next render saves it under the new name, and that the movie under its old name stays on disk. It SHALL NOT name a
  file: the event page names them after the save, from the verdict.
- The card's heading follows the name. A card that has its own title ("Card title (overrides the name)") keeps it.

When the browser's primary pointer is coarse, each of these controls, the row's Edit Titlecard button, Add chapter and Undo SHALL take a tap
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
with Enter or in the Add chapter dialog, and nothing SHALL change. The
name saved is the accepted name without the spaces around it. A chapter's name SHALL be described to the
operator as the words on its title card in the movie.

A chapter the page showed when Edit mode opened SHALL, once deleted, stay listed in its place in the Chapters list
until the edits are saved, marked as deleted when the edits are saved; the bin SHALL no longer list it. It lists none
of its clips. Such a chapter offers an **Undo** control that returns it to its place, and keyboard focus SHALL move to that Undo. A
chapter the operator added in this Edit mode and then deletes SHALL simply be gone. A chapter that plays no
clip SHALL say so in its row, and that a chapter without clips is left out of the movie. While the event
lists another chapter, a deleted one aside, the row SHALL also say that clips can be moved into it with Move to…
(the Clip tab's, or a clip's menu). When it is the only
chapter listed, a deleted one aside, it SHALL NOT say that: no other chapter has a clip to move.

The event's own chapter SHALL be headed `Main` while any other chapter is listed, a deleted one aside, and
`Clips` otherwise, as on the event page. Every change to the chapters SHALL count as an unsaved edit, like a
move:

- it SHALL be announced
- Reset SHALL restore the chapters as read
- leaving with it unsaved SHALL ask first
- the save bar SHALL count it ("Saving an edit writes only what the operator changed")

While a save is in flight, every chapter control and Add chapter SHALL say that it is unavailable and SHALL
change nothing when pressed.

#### Scenario: A chapter's header in the bin is one row
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window with a fine pointer, with
  nothing selected
- **THEN**
  - `Kvällen`'s heading in the bin is one row holding its name and counts and no button
  - the Event tab's Chapters list has a row for `Kvällen` holding, in this order, its name, its clip count, and icon buttons named "Edit title card for Kvällen", "Move chapter Kvällen up", "Move chapter Kvällen down" and "Delete chapter Kvällen", each offering its name as a tooltip
  - that row is one line at most 36 CSS pixels tall

#### Scenario: A first chapter added to a one-chapter event
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter, the
  operator presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** a chapter `Kvällen vid grillen` is listed last in the Chapters list, saying that it plays no clip and
  that clips can be moved into it with Move to…; the first chapter's row and heading read `Main` instead of
  `Clips`; keyboard focus is on the new chapter's row; the addition is announced; and the save bar says
  "1 chapter added"

#### Scenario: A lone chapter offers only Add chapter
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter
- **THEN** its one chapter offers no Move up, Move down or Delete, its row shows `Clips` as plain text with an Edit Titlecard
  button (the editor's Name field edits the event's title), and the Chapters list offers Add chapter after it

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
- **THEN** the inspector shows the Title card tab on "This title card" with keyboard focus in the Name field, named "Name of chapter Kvällen" and holding
  `Kvällen`; the chapter's heading in the bin shows `Kvällen` as plain text with no pencil
- **WHEN** the operator selects the name, types ` Kväll på stranden `, with spaces around it, and presses Enter
- **THEN** the field holds the name, the card stays selected, the heading reads `Kväll på stranden`, the rename was announced once, and the save bar says that 1
  chapter was renamed. The chapter offers no Rename button and its name is not pressable.

#### Scenario: Renaming with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator tabs to "Edit title card for Kvällen", presses Enter, types `Kväll`
  in the Name field and presses Escape
- **THEN** the chapter is named `Kväll` (an accepted name is already in the draft), nothing is selected, the inspector shows the Event tab, keyboard focus is on the chapter's Edit Titlecard button in its Chapters list, and the next Tab reaches the chapter's Move up

#### Scenario: Main and a chapter are edited alike
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens "Edit title card for Main" and then "Edit title card for Kvällen"
- **THEN** each shows the same editor on "This title card" with the Name field first; Main's is named "Title of the event" and holds
  `Två kapitel`, Kvällen's "Name of chapter Kvällen"; neither row nor bin heading has a pencil, a card row, a "Main title card" line or a
  "from the folder name" line

#### Scenario: Leaving the field keeps an accepted name
- **WHEN** the operator selects the card of `Kvällen`, types `Kväll` in the Name field, and presses Tab
- **THEN** the chapter is named `Kväll`, keyboard focus is on the control after the field and not back in it, the card stays selected, and the rename is announced once

#### Scenario: Escape drops what was typed
- **WHEN** the operator selects the card of `Kvällen`, types `main` in the Name field, and presses Escape
- **THEN** nothing is selected, keyboard focus is on the chapter's Edit Titlecard button, the chapter is named `Kvällen`, "Name not changed" with the reason is announced, and the page shows no unsaved changes

#### Scenario: Pressing the title and changing nothing
- **WHEN** the operator types `Kväll` in the Name field of `Kvällen` and then `Kvällen`, with spaces around it, and presses Escape
- **THEN** the chapter is named `Kvällen`, nothing is announced or counted as an edit, and the page shows no unsaved changes

#### Scenario: A refused rename keeps the field open
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `main` in the Name field of `Kvällen`
- **THEN** the field stays as typed, is marked invalid and explains under it that `Main` is how the page names the event's own chapter; the
  refusal is announced, and the draft still holds `Kvällen`. Typing `Morgon` removes the refusal and the chapter is named `Morgon`.
- **WHEN** the operator types `main` again and presses Enter
- **THEN** the card stays selected, the field is still marked invalid, and the refusal is announced
- **WHEN** the operator presses Escape
- **THEN** nothing is selected, keyboard focus is on the chapter's Edit Titlecard button, the chapter is named `Morgon`, the last name accepted, and "Name not changed" with the reason is announced

#### Scenario: A refused name is not lost when focus leaves
- **WHEN** the operator types `main` in that field and presses Tab
- **THEN** the field stays as typed with its refusal, keyboard focus is on the control after it, and the chapter is still named `Kvällen`

#### Scenario: An empty name, and a name already taken
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator selects its card, deletes the name,
  and then types `KVÄLLEN`
- **THEN** the first is refused because a chapter needs a name, and the second because a chapter called `Kvällen` exists, each in
  the words Add chapter's dialog uses for the same name

#### Scenario: One field at a time
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator renames `Kvällen` to `Kväll` in its editor, and presses "Edit title card for Morgon"
- **THEN** only the card of `Morgon` is selected, `Kvällen`'s heading in the bin reads `Kväll`, and the save bar counts the one rename

#### Scenario: A name typed and not kept holds Save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator changes the title in the Details form, selects the card of `Kvällen`,
  types `main` and presses Ctrl+S
- **THEN** nothing is saved and "Not saved: the name is refused." is announced. After the operator types `Kväll`, presses Escape and then
  Ctrl+S, one save is sent and carries both edits.

#### Scenario: Reset closes the field
- **WHEN** the operator renames `Kvällen` to `Kväll` in its editor, and presses Reset
- **THEN** the chapter's row and its heading in the bin read `Kvällen`, the page shows no unsaved changes, and "Edit title card for Kvällen" shows an editor whose Name field holds `Kvällen`

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` has no chapter rename and says that it has no name of its own because its title card shows the event's title; its
  row shows `Main`, an Edit Titlecard button and no other title control

#### Scenario: Renaming the main title card edits the event's title
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in which one chapter is listed, and the operator opens "Edit title
  card for Clips" and types `Grillkväll med grannarna` in the field named "Title of the event"
- **THEN** the Details form's Title field holds the same, the editor's preview shows it, the save bar says "Title" changed, and the
  editor says that saving changes the movie's file name and names no file. The chapter is still headed `Clips`.
- **WHEN** the operator types `Grillkväll` in the Details form's Title field and selects the card again
- **THEN** the Name field holds `Grillkväll`
- **WHEN** the operator saves
- **THEN** one `PUT` is sent whose metadata title is `Grillkväll` and whose chapters and clips are as read, and the editor no longer says anything about
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
- **THEN** `Kvällen vid grillen` has a Name field in its editor, but no Delete, Move up or Move down, and the save bar
  says that 4 clips moved, 1 chapter was added and 1 chapter deleted

#### Scenario: Chapter controls on a phone
- **WHEN** the operator opens Edit mode on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area around each of `Kvällen`'s Edit Titlecard, Move up, Move down and Delete, and
  around `Main`'s Edit Titlecard and Add chapter, reaches that control and no other (centred on each, except
  that the areas of Move up and Move down meet at the edge they share), and the page does not scroll
  horizontally

#### Scenario: Chapter controls wait for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a rename pending, the operator presses Save, and the
  service has not answered yet
- **THEN** Add chapter and every chapter's Edit Titlecard, Move up, Move down and Delete say that they are unavailable, and
  pressing them changes nothing and opens nothing

#### Scenario: A lone empty chapter does not point at Move clips
- **WHEN** Edit mode opens on `2024-10-05 - Tom mapp`, an event whose folder holds no clip, and the operator
  presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** the new chapter's row, the only chapter listed, counts 0 clips, and it says "No clips. A chapter without
  clips is left out of the movie." It does not mention moving clips into it.

#### Scenario: A lone chapter whose only clip is ignored
- **WHEN** Edit mode opens on `2024-10-06 - Bara ignorerad`, an event that lists one chapter, whose only clip
  `s1710004.mp4` is ignored
- **THEN** the bin lists the ignored clip, and the chapter's row counts 0 clips and says "It plays no clip. A chapter without
  clips is left out of the movie." It does not mention moving clips into it.

#### Scenario: A second chapter brings the hint back
- **WHEN** on `2024-10-05 - Tom mapp`, with `Kvällen vid grillen` added, the operator presses Add chapter,
  types `Morgonen` and confirms
- **THEN** both chapters' rows say that they have no clips and that clips can be moved into them with Move to…
- **WHEN** the operator then deletes `Morgonen`
- **THEN** `Kvällen vid grillen` says again, as it did before the addition, that it has no clips and is left
  out of the movie, without mentioning moving clips into it

### Requirement: The clip bin holds the chapters' clip lists

The bin SHALL list every chapter with its clips in compact rows (thumbnail, name, kept length, status) and SHALL keep
every action the chapter lists have: reorder and move between chapters by pointer and by keyboard, marks and Move
marked to…, the New and Missing clips with their actions, and the clips the event ignores. Adding, moving, deleting and
renaming chapters SHALL be done in the Event tab's Chapters list ("The Event tab lists the event's chapters"); a
chapter's heading in the bin holds its name and counts and no tool.

From 960 CSS pixels wide the bin SHALL be a side pane as wide as 22% of the window, at least 240 and at most 320 CSS pixels; below 960 the panes stack and it is as wide as the window. With a fine pointer, a row of a clip a chapter plays SHALL take two lines and be at most 70 CSS pixels tall: handle, position, name and the row's tools, then the thumbnail, the length it plays, its status and Cuts. In a bin narrower than about 17rem (272 CSS pixels) Rotate left and right go to the second line, before Cuts; from that width all of the row's tools are on the first line. In the bin, with a fine pointer, a clip's status is shown as its icon alone ("State is never shown by color alone"); with a coarse pointer it keeps its words. In a window from 960 CSS pixels wide, a chapter in the bin SHALL list only the clips it plays and the missing clips the operator removed. The bin SHALL list the clips the event ignores after the last chapter and before Add chapter, under the heading "Ignored clips": each chapter's ignored clips together, in the chapters' order and in the order the chapter lists them, under a caption that names the chapter and says how many it holds ("Main · 1 ignored clip, not played"), each named as that chapter names it, marked as ignored, with no position, handle or control. These clips still count as listed by their chapter. The bin SHALL show no such heading when the event ignores no clip. Below 960 CSS pixels each chapter lists its ignored clips after its other clips. The bin SHALL show no line of its own about new clips: the Clips help says when a new clip joins `reel.yaml`, and the top bar's summary says how many saving adds.

#### Scenario: Keyboard reorder in the bin
- **WHEN** the operator focuses `s1710002.mp4`'s drag handle, presses Space, ArrowUp, Space
- **THEN** `s1710002.mp4` is first in its chapter, the move is announced, and the Timeline draws it first

#### Scenario: Clip rows visible at the target window
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, with a fine pointer and no clip marked
- **THEN** in a 1280×720 window the bin shows, below its toolbar and without scrolling, at least 3 whole rows of the clips its chapters play, and in a 1440×900 window all 4 of them; the ignored `s1710004.mp4` is listed after them

#### Scenario: A new clip in the bin
- **WHEN** Edit mode opens on `2024-08-02 - Badutflykt - Varberg`, whose `reel.yaml` lists two of its three clips, and the operator moves `s1710001.mp4` below `s1710003.mp4`
- **THEN** the bin shows no line about new clips, the new clip's row has the status "New, not yet in reel.yaml": with a fine pointer an icon whose tooltip and visually hidden text are those words, with no visible word ("State is never shown by color alone"), the Clips help says when a new clip joins `reel.yaml`, and the top bar's summary says that saving adds 1 new clip to `reel.yaml`

#### Scenario: Ignored clips in the bin
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window, and then in a 900 px wide window
- **THEN** the wide bin shows "Ignored clips" after `Kvällen`, with `Main · 1 ignored clip, not played` above `s1710004.mp4`, and `Main` lists only `s1710001.mp4`; the 900 px page lists `s1710004.mp4` under `Main` and has no such heading ("The event page reorders clips within a chapter")

#### Scenario: 400 clips
- **WHEN** the event has 400 clips
- **THEN** the bin scrolls on its own, the rest of the workspace does not move, and the drag-smoothness gate holds

### Requirement: The inspector holds the event's fields and the selected cut

The inspector SHALL have an Event tab (Details form, the Chapters list of "The Event tab lists the event's chapters",
Poster, and a button "All title cards in this event" that
shows the Title card tab on its "All title cards in this event" tab, with whether title cards are on in words), a Clip tab (the selected
clip's or cut's fields), a Title card tab (the docked card editor) and a Suggestion tab (the selected suggestion's decision), as "The inspector follows the selection" says. The tabs SHALL work by arrow keys. Choosing a cut or a
suggestion on the track SHALL show its tab and leave focus on the track.

#### Scenario: Selecting a cut
- **WHEN** the operator presses a cut's handle on the track
- **THEN** the inspector shows the Clip tab with that cut's start and end fields

#### Scenario: The card style and the switch stay in the dialog
- **WHEN** title cards are on and the operator presses "All title cards in this event" in the Event tab
- **THEN** the Event tab said "Title cards are on for this event", and the inspector shows the Title card tab on its "All title cards in
  this event" tab, which holds the card style and the Title cards switch

### Requirement: The title card editor is docked in the inspector

Selecting a title card, on the track or with its chapter's Edit Titlecard button in the Event tab's Chapters list,
SHALL show its editor in the inspector's Title
card tab: the tabs "This title card" and "All title cards in this event", the fields, and one live preview above them.
No modal dialog SHALL open. Edits SHALL go into the one draft; the top bar counts a changed card.

#### Scenario: Card from the track
- **WHEN** the operator presses the "Kvällen" card block
- **THEN** the inspector shows "Title card for Kvällen" with its preview and fields, the track and the picture stay
  visible, and no dialog is open

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
  added with Add chapter in the Event tab's Chapters list, after which clips can be dragged between chapters
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
- **THEN** the Clips help, opened, says that a chapter can be added with Add chapter in the Event tab's
  Chapters list, and that clips can then be dragged between chapters
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the Clips help says that a clip can be dragged into another chapter, and that Move marked to… moves the marked clips to a chapter

#### Scenario: Nothing shifts while dragging over another chapter
- **WHEN** in a window 320 pixels wide, in the light and in the dark scheme, on `2024-08-20 - Två kapitel -
  Tjörn`, the operator drags `s1710001.mp4` over `Kvällen` and holds it between `s1710002.mp4` and
  `s1710003.mp4`
- **THEN** every clip row and both chapter panels keep the size and place they had before the drag, the line
  between the two clips is visible beside the dragged copy, and the page does not scroll horizontally
