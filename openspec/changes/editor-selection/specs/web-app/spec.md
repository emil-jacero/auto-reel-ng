## ADDED Requirements

### Requirement: The inspector follows the selection

The inspector SHALL show the tab for what is selected: Clip for a clip or a cut, Title card for a card, Suggestion for
a suggestion, and Event when nothing is selected. The operator MAY still pick another tab by hand; the next selection
SHALL pick the tab again. Each tab's controls SHALL edit the one draft, as every Edit-mode change does.

#### Scenario: Clip selected
- **WHEN** the operator presses the body of `s1710003.mp4`'s block on the track
- **THEN** the inspector shows the Clip tab with `s1710003.mp4`, "Kvällen · clip 2 of 3", its Trim In/Out fields,
  rotate buttons and its cuts

#### Scenario: Nothing selected
- **WHEN** the operator presses Escape with a clip selected
- **THEN** nothing is selected and the inspector shows the Event tab with the Details form

### Requirement: The Clip tab edits the selected clip

The Clip tab SHALL show the clip's name, chapter and position, and its length in the movie, and SHALL offer Trim In
and Trim Out as typed times, Rotate left and right, the clip's cuts with remove and "+ Cut at playhead", Use frame as
poster. A typed trim SHALL be the same draft edit as the track's edge tools.

#### Scenario: Typed Trim In
- **WHEN** the operator types 0:01.50 into Trim In for `s1710001.mp4`
- **THEN** the clip's leading cut is 0 to 1.5 s in the draft, the block shortens and the clips after it move left

### Requirement: The title card editor is docked in the inspector

Selecting a title card, on the track or from its chapter in the bin, SHALL show its editor in the inspector's Title
card tab: the tabs "This title card" and "All title cards in this event", the fields, and one live preview above them.
No modal dialog SHALL open. Edits SHALL go into the one draft; the top bar counts a changed card.

#### Scenario: Card from the track
- **WHEN** the operator presses the "Kvällen" card block
- **THEN** the inspector shows "Title card for Kvällen" with its preview and fields, the track and the picture stay
  visible, and no dialog is open

## MODIFIED Requirements

### Requirement: The inspector holds the event's fields and the selected cut

The inspector SHALL have an Event tab (Details form, Poster, and a button "All title cards in this event" that
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

### Requirement: Edit mode adds, renames, reorders and deletes chapters

In Edit mode the operator SHALL be able to change the event's chapters themselves. Every control below SHALL
be reachable with the keyboard and SHALL name, to assistive technology, the chapter it acts on.

- **Add chapter**, after the last chapter, SHALL ask for a name and add an empty chapter with that name at the
  end.
- **Rename** SHALL be done in the title card editor, in its Name field ("The title card editor holds every
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
heading) and SHALL select that card, showing its editor on the inspector's "This title card" tab ("The title card editor is docked in the inspector"). A
chapter's section SHALL show nothing between its header bar and its clips but the tools row and the notes of this requirement and of "Edit mode says what
a chapter's name means for clips added later": no card row, no "Main title card" line, no source line ("from the folder name"). A chapter added in the draft has no saved card, and its
button SHALL be offered all the same and keeps the preview from the draft. While the Timeline draws a card built from the event's cards for it ("A chapter added while editing gets the event's card on the Timeline"), the editor SHALL say that until Save its title card is drawn as the event's and that its own settings can be changed after Save; otherwise it SHALL say that its card is drawn after Save.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up or Move down, so that an event never saves without a chapter.

**Focus after the selection leaves the card.** When Escape clears the card selection from inside the editor, keyboard focus SHALL
return to the control that selected the card (the chapter's Edit Titlecard button, or the card block on the Timeline), so that the focused field never
unmounts onto the page body. Selecting something else leaves keyboard focus where the operator put it.

**The Name field.** In the editor the field SHALL be the first of "This title card" and SHALL be named "Name of chapter <name>"
for a chapter and "Title of the event" for the event's own chapter, where <name> is the name the draft holds when the editor opens. The
header bar and the editor's title name the chapter by its name alone.

- An accepted name SHALL be written to the draft as it is typed, so that the editor's heading, its preview, the chapter's header
  bar behind the editor and the picker of Move marked to… follow it. A name equal to the chapter's current name, once the spaces
  around it are removed, SHALL change nothing. A rename SHALL be announced once, when keyboard focus leaves the field or the selection leaves the card, and not for each key; typing a name and typing the old one back announces nothing.
- A refused name SHALL be explained under the field in words, in a `role="alert"` that is remounted for each refusal, and the
  field SHALL be marked invalid. The draft keeps the last accepted name, and the field keeps the typed text. Enter, with a refused
  name in the field, SHALL keep the field invalid and announce the refusal. Escape, and the selection of anything else, SHALL return the
  field's text to the draft's name and announce that the name was not changed and why; they SHALL NOT keep a refused name.
- While the field holds a refused name, Ctrl+S SHALL save nothing and SHALL say "Not saved: the name is refused."
- While a save or a move of marked clips is pending, the field and the editor's other fields SHALL say that they are unavailable
  and SHALL change nothing (the busy-control rule); the bar's Edit Titlecard button SHALL say so too and select nothing.
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
with Enter or in the Add chapter dialog, and nothing SHALL change. The
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
  button (the editor's Name field edits the event's title), and the page offers Add chapter after it

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
  `Kvällen`; the header bar behind it shows `Kvällen` as plain text with no pencil
- **WHEN** the operator selects the name, types ` Kväll på stranden `, with spaces around it, and presses Enter
- **THEN** the field holds the name, the card stays selected, the heading reads `Kväll på stranden`, the rename was announced once, and the save bar says that 1
  chapter was renamed. The chapter offers no Rename button and its name is not pressable.

#### Scenario: Renaming with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator tabs to "Edit title card for Kvällen", presses Enter, types `Kväll`
  in the Name field and presses Escape
- **THEN** the chapter is named `Kväll` (an accepted name is already in the draft), nothing is selected, keyboard focus is on the chapter's Edit Titlecard button, and the next Tab reaches the chapter's Move up

#### Scenario: Main and a chapter are edited alike
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens "Edit title card for Main" and then "Edit title card for Kvällen"
- **THEN** each shows the same editor on "This title card" with the Name field first; Main's is named "Title of the event" and holds
  `Två kapitel`, Kvällen's "Name of chapter Kvällen"; neither header bar has a pencil, a card row, a "Main title card" line or a
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
- **THEN** only the card of `Morgon` is selected, `Kvällen`'s header bar reads `Kväll`, and the save bar counts the one rename

#### Scenario: A name typed and not kept holds Save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator changes the title in the Details form, selects the card of `Kvällen`,
  types `main` and presses Ctrl+S
- **THEN** nothing is saved and "Not saved: the name is refused." is announced. After the operator types `Kväll`, presses Escape and then
  Ctrl+S, one save is sent and carries both edits.

#### Scenario: Reset closes the field
- **WHEN** the operator renames `Kvällen` to `Kväll` in its editor, and presses Reset
- **THEN** the header bar reads `Kvällen`, the page shows no unsaved changes, and "Edit title card for Kvällen" shows an editor whose Name field holds `Kvällen`

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` has no chapter rename and says that it has no name of its own because its title card shows the event's title; its
  header bar shows `Main`, an Edit Titlecard button and no other title control

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

### Requirement: The title card dialog holds every name and every title-card setting

The title card editor, docked in the inspector's Title card tab ("The title card editor is docked in the inspector"), SHALL be the one place in Edit mode for a chapter's
name and for every title-card setting, the same for the event's own chapter and for every other chapter. The page SHALL hold no
other control for a name, a card or the event's card style. The editor SHALL have one live preview of the card being edited, drawn by the
service from the draft ("The preview is drawn by the service while the operator edits"), visible whichever tab is shown, and two tabs in a
tab list named "Title card settings" (`role="tablist"`, each tab `role="tab"` with `aria-selected`, its panel `role="tabpanel"` named
by the tab). Left and Right Arrow, Home and End SHALL move between the tabs, and Tab SHALL move from the tab list into the shown panel.
Two tabs, not two stacked groups, keep the editor the height of one tab and keep the preview in view while the operator edits either.

- **"This title card"** SHALL be shown when a card is selected, except as the last bullet says. In this order it SHALL hold: the **Name**
  ("Edit mode adds, renames, reorders and deletes chapters"); **Card title (overrides the name)** with a **Use the name** button, only for a card
  whose draft has its own `title`, and no control that adds one; the **Subtitle**; **Background**; **Font**; **Title size**;
  **Subtitle size**; **Text colour**; **Position**; and **Length**. Each field but the Name SHALL have **Use event style** ("A card's fields are
  overrides that follow the event style until set"). The card's heading follows the Name: a card with no title of its own draws the name
  (the event's title for the opening card), and the preview, the editor's name and the Timeline's blocks follow it as it is typed.
  Use the name SHALL remove the card's own title from the draft; the key goes from `reel.yaml` on Save.
- **Length** SHALL be a number field in seconds named "Length of the title card (seconds)", showing the card's length, else the event's default
  length as its placeholder with the words "Event style". It SHALL take whole tenths, from 0.5 to 60, and for a card over video no more than
  the first span of the chapter's anchor clip that the draft's cuts keep ("A black card's drag moves everything after it, and a video card's is bounded by its clip"), the limits the
  length drag has; a card whose limit makes it not adjustable SHALL say why and take no value. A typed length outside the limits, or not a number, SHALL be
  refused in words under the field that name the limits (never rounded to a value the operator did not type), SHALL keep the text, mark the field invalid and leave the draft as it was; an accepted one SHALL be written
  to the draft as it is typed, as the drag's release is, and a length equal to the one read SHALL count as no change. The field and the Timeline's length drag
  are two ways to edit the same `duration`: after a drag, the field shows the new length, and a length typed here is drawn on the Timeline
  at once. Use event style SHALL remove the card's `duration`.
- **"All title cards in this event"** SHALL hold the event-wide style fields of "Edit mode edits the event's card style in one place" and the
  Title cards On or Off switch of "Edit mode switches the event's title cards On or Off". Its edits SHALL change the preview of the card shown.
- A tab that holds a problem the operator cannot see, a refusal by the service at one of its fields or a field the editor refused, SHALL say so in its label ("All title
  cards in this event, 1 problem"), and the editor SHALL show the first tab that holds one when a card is selected and the service's last answer named one.
- Every field SHALL work with the keyboard alone, have a visible label, be at least 44 × 44 CSS pixels where the primary pointer is coarse, and fit 320 to
  1280 CSS pixels without a horizontal page scroll in both colour schemes.

Every edit in either tab SHALL go into the page's one draft and be counted, saved, guarded and undone as every other Edit-mode edit: a
name as "chapter renamed" or "Title", a card as "title card changed", the style as "Card style changed", the switch as "Title cards turned off" or "Title cards
turned on". Save SHALL send the same whole-document `PUT` under `If-Match` that every edit sends, with only the keys of what changed.

#### Scenario: Two tabs, the name first
- **WHEN** the operator presses "Edit title card for Kvällen" on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the editor shows the tab "This title card" whose first field is the Name, named "Name of chapter Kvällen" and holding `Kvällen`,
  followed by Subtitle, Background, Font, Title size, Subtitle size, Text colour, Position and Length; the preview is shown above them at 390 px and beside
  them at 1280 px; and the tab "All title cards in this event" is one Arrow key away

#### Scenario: Switching tabs keeps the preview and the draft
- **WHEN** the operator types `Dag 2` in the Name field, moves to "All title cards in this event" with the Right Arrow, picks the text
  color `#FFD700`, and moves back
- **THEN** the preview was shown throughout and now shows `Dag 2` in `#FFD700`, the Name field still holds `Dag 2`, and the save bar says
  "1 chapter renamed" and "Card style changed"

#### Scenario: A card with its own title
- **WHEN** the chapter `Kvällen`'s card in `reel.yaml` has `title: Kväll på stranden` and the operator selects its card
- **THEN** the editor shows the Name (`Kvällen`) and then "Card title (overrides the name)" holding `Kväll på stranden` with "Use the name"
- **WHEN** the operator presses Use the name
- **THEN** the field is gone, the preview draws `Kvällen`, and the next Save removes `title` from that card

#### Scenario: A card with no title of its own offers none to add
- **WHEN** the operator selects the card of a chapter whose card sets no `title`
- **THEN** there is no "Card title" field and no control that would add one, and the card's heading is the Name

#### Scenario: The same dialog for Main
- **WHEN** the operator opens "Edit title card for Main"
- **THEN** it has the same tabs and fields as a chapter's, its Name field is named "Title of the event" and edits the event's title, and its heading
  and the preview follow it

#### Scenario: Typing a length
- **WHEN** the operator types `6` in the Length field of a black card of 4.0 s
- **THEN** the draft holds `duration: 6.0`, the Timeline's card block is 6.0 s long, and the save bar counts one changed card
- **WHEN** the operator types `0.3`, and then `90`
- **THEN** each is refused under the field in words that name the limits 0.5 s and 60 s, the text is kept, and the card stays at 6.0 s

#### Scenario: A video card's length is bounded by its clip
- **WHEN** a card over video lies over a clip whose first kept span is 3.4 s and the operator types `5`
- **THEN** the field refuses it in words that name 3.4 s as the longest, and the draft is unchanged

#### Scenario: The drag and the field are one edit
- **WHEN** the operator drags a card's end edge to 6.0 s, releases, and looks at the card's editor
- **THEN** the Length field holds 6.0
- **WHEN** the operator types `7`
- **THEN** the card block on the Timeline is 7.0 s long and Save writes `card.duration: 7.0`

#### Scenario: A problem in the other tab is shown on the tab
- **WHEN** the service answers a Save with 400 naming `look.title_card.title_font_size` and the operator selects a card
- **THEN** the editor shows "All title cards in this event", whose label says "1 problem", with the message at the field

#### Scenario: Nothing else on the page edits a name or a card
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, in light and dark at 1280 and 390 px
- **THEN** the page holds no pencil, no click-to-rename title, no "Main title card" line, no card row, no "Card style for this event" section and no Title cards
  section; each chapter's section is its header bar and its clips

#### Scenario: One save writes the keys that changed
- **WHEN** the operator renames `Kvällen` to `Kväll`, edits the opening card's event title, sets the style's position to Top and turns the cards Off, in the editors, and saves
- **THEN** one `PUT` under `If-Match` is sent whose chapter is named `Kväll`, whose metadata title is the new title, whose `look.title_card.position` is `top`
  and whose `look.decorators` is `[]`, and no other key differs from `reel.yaml` as read

### Requirement: Edit mode edits the event's card style in one place

The title card editor's second tab, **All title cards in this event**, SHALL edit the event-wide title-card style, the `look.title_card` of
`reel.yaml`, and it is the only place that does: the page SHALL NOT hold a "Card style for this event" section or any other control for it. It SHALL offer these
fields: font family, title size, subtitle size, text color, position (center, top or bottom), default length, and default background (Black or
Video), each with a **Use project default** button. The font family SHALL be chosen from the families the service lists (`GET /api/v1/fonts`), each shown
in its own face or with the service's preview image, never typed. A field the style leaves unset SHALL say that
it follows the project default, with the value in force when the page read it as a placeholder; when the
operator clears a value that the saved style set, the field SHALL say "Project default" without a number,
because the page does not know it, and SHALL NOT show a value it does not have. Every field SHALL be reachable
and operable with the keyboard, and have a label, and a tap area of at least 44 by 44 pixels while the
primary pointer is coarse. The tab SHALL be disabled with Edit mode's other edit controls while a save is in flight.

The editor's one live preview, drawn by the service from the draft (not the saved) style and the card being edited, SHALL show an
event-style edit at once, under the same rules as the card preview: debounced, a stale request cancelled, the previous image kept while the next
loads, and a failure told in words. When the service cannot resolve the saved event style (the event detail's `title_card_error`), the docked editor SHALL show this tab
with that error in words and the stored values as typed, so the operator can correct them.

#### Scenario: Setting a font and a colour for every card
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` in Edit mode, the operator selects the card of Main ("Edit title card for Main"), chooses the tab "All title cards in this event",
  picks the font `DM Serif Display` and sets the text color `#FFD700`
- **THEN** the preview shows the opening card in that face and color before anything is saved, and the save
  bar says the card style changed

#### Scenario: An unset field follows the project default
- **WHEN** the event's `reel.yaml` sets no `look.title_card` and the operator shows the tab
- **THEN** each field shows the project default value as a placeholder and none shows as set

#### Scenario: Use project default clears a field
- **WHEN** the saved style sets a title size of 80 and the operator presses Use project default on it
- **THEN** the field says "Project default" and the save bar counts the change

#### Scenario: A cleared value does not invent a default
- **WHEN** the saved style sets a title size of 80 and the operator clears the field
- **THEN** the field says "Project default" with no number, the preview shows the card without the size, and
  the save bar counts the change

#### Scenario: A style the engine refuses is told and correctable
- **WHEN** the event's `look.title_card.position` is hand-written as `middle` and the operator selects a title card
- **THEN** the docked editor shows "All title cards in this event", with the service's refusal naming `position` and `middle` in the field, and
  choosing `center` clears the refusal

#### Scenario: The control is usable at a narrow width
- **WHEN** the window is 320 pixels wide and the operator opens the tab
- **THEN** every field is fully visible without horizontal page scroll

## REMOVED Requirements

### Requirement: A selected title card opens its inspector in Edit mode
**Reason**: The card editor no longer opens in a modal dialog; it is docked in the workspace's inspector.
**Migration**: "The title card editor is docked in the inspector".
