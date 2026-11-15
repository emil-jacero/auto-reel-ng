# Spec Delta

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
text, an **Edit Titlecard** button and the chapter's clip count; the chapter's tools (Move up, Move down, Delete, offered by the rules above) stay in their own row under the bar, which is sticky and keeps one line. In the workspace's clip bin the bar SHALL instead hold those tools itself, after the clip count, so that a chapter takes one row above its clips: there Edit Titlecard, Move up, Move down and Delete SHALL show an icon only, keep their names and reasons, and offer their names as tooltips, and with a fine pointer the bar SHALL be at most 36 CSS pixels tall. The
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

#### Scenario: A chapter's header in the bin is one row
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window with a fine pointer
- **THEN**
  - `Kvällen`'s header is one row holding, in this order, its name, its clip count, and icon buttons named "Edit title card for Kvällen", "Move chapter Kvällen up", "Move chapter Kvällen down" and "Delete chapter Kvällen", each offering its name as a tooltip
  - no row of tools lies between that header and its first clip, and the header is at most 36 CSS pixels tall

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
- **THEN** the chapter lists the ignored clip (under its heading below 960 px; from 960 px under "Ignored clips" directly after it, captioned with the chapter's name) and says "It plays no clip. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move marked to…

#### Scenario: A second chapter brings the hint back
- **WHEN** on `2024-10-05 - Tom mapp`, with `Kvällen vid grillen` added, the operator presses Add chapter,
  types `Morgonen` and confirms
- **THEN** both chapters say that they have no clips and that clips can be dragged into them or moved into
  them with Move marked to…
- **WHEN** the operator then deletes `Morgonen`
- **THEN** `Kvällen vid grillen` says again, as it did before the addition, that it has no clips and is left
  out of the movie, without mentioning dragging or Move marked to…

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
not overlap another control's. The group SHALL wrap in a window 320 CSS pixels wide, on its own row under the marks line's other controls, its label above the picker and the picker beside Move, without a horizontal page scroll, in both color schemes. In the workspace's clip bin the group SHALL instead share the toolbar's second row with Rotate marked left and right, its label being the group's name and not shown ("The marks line is one aligned unit"). The group SHALL keep its place and its
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
- **In the workspace's clip bin.** The bin is narrow at every window size, so there the toolbar SHALL keep exactly the two rows above and SHALL NOT wrap further. Rotate marked left and right SHALL show an icon only and offer their names as tooltips; the label "Move marked to…" SHALL name the group without being shown; the picker SHALL fill the second row between the Rotate buttons and Move. With a fine pointer the toolbar SHALL be at most 88 CSS pixels tall. It SHALL stay at the top of the bin while the bin scrolls, and keep its height whether or not a clip is marked.
- **Narrow windows.** Outside the workspace's clip bin, where the toolbar does not fit a row, it SHALL wrap by whole groups: the Move group goes on a row of its own with the label above, the picker filling the
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

#### Scenario: The bin's toolbar is two rows
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window with a fine pointer, and the operator marks `Kvällen/s1710002.mp4` and scrolls the bin down
- **THEN**
  - the toolbar's first row holds the Clips help toggle, "1 clip marked" and Clear marks, and its second row Rotate marked left, Rotate marked right, the chapter picker and Move
  - Rotate marked left and right show icons and offer their names as tooltips, and the group around the picker is named "Move marked to…"
  - the toolbar was at most 88 CSS pixels tall before and after the mark, no clip row moved when the clip was marked, and the toolbar stays at the bin's top as it scrolls

#### Scenario: The toolbar wraps in aligned rows
- **WHEN** the window is 390 px wide and again 320 px, light and dark
- **THEN** the Move group is on its own row with the label above and the picker beside Move, every row's controls share one height and one centre line (within 1 px), the
  reason line, when shown, is below them, and the page does not scroll horizontally

### Requirement: The clip bin holds the chapters' clip lists

The bin SHALL list every chapter with its clips in compact rows (thumbnail, name, kept length, status) and SHALL keep
every action the chapter lists have: reorder and move between chapters by pointer and by keyboard, marks and Move
marked to…, Add/rename/delete chapter, the New and Missing clips with their actions, and the clips the event ignores.

The bin SHALL be as wide as 22% of the window, at least 240 and at most 320 CSS pixels. With a fine pointer, a row of a clip a chapter plays SHALL take two lines and be at most 70 CSS pixels tall: handle, position, name and the row's tools, then the thumbnail, the length it plays, its status and Cuts. In a bin narrower than about 17rem (272 CSS pixels) Rotate left and right go to the second line, after Cuts; from that width all of the row's tools are on the first line. In the bin, with a fine pointer, a clip's status is shown as its icon alone ("State is never shown by color alone"); with a coarse pointer it keeps its words. In a window from 960 CSS pixels wide, a chapter in the bin SHALL list only the clips it plays and the missing clips the operator removed. The bin SHALL list the clips the event ignores after the last chapter and before Add chapter, under the heading "Ignored clips": each chapter's ignored clips together, in the chapters' order and in the order the chapter lists them, under a caption that names the chapter and says how many it holds ("Main · 1 ignored clip, not played"), each named as that chapter names it, marked as ignored, with no position, handle or control. These clips still count as listed by their chapter. The bin SHALL show no such heading when the event ignores no clip. Below 960 CSS pixels each chapter lists its ignored clips after its other clips. The bin SHALL show no line of its own about new clips: the Clips help says when a new clip joins `reel.yaml`, and the top bar's summary says how many saving adds.

#### Scenario: Keyboard reorder in the bin
- **WHEN** the operator focuses `s1710002.mp4`'s drag handle, presses Space, ArrowUp, Space
- **THEN** `s1710002.mp4` is first in its chapter, the move is announced, and the Timeline draws it first

#### Scenario: Clip rows visible at the target window
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, with a fine pointer and no clip marked
- **THEN** in a 1280×720 window the bin shows, below its toolbar and without scrolling, at least 3 whole rows of the clips its chapters play, and in a 1440×900 window all 4 of them; the ignored `s1710004.mp4` is listed after them

#### Scenario: A new clip in the bin
- **WHEN** Edit mode opens on `2024-08-02 - Badutflykt - Varberg`, whose `reel.yaml` lists two of its three clips, and the operator moves `s1710001.mp4` below `s1710003.mp4`
- **THEN** the bin shows no line about new clips, the new clip's row says New (with a fine pointer, as the row's icon with the words "New" kept as visually hidden text for assistive technology and as the icon's tooltip, and not as a visible word, "State is never shown by color alone"), the Clips help says when a new clip joins `reel.yaml`, and the top bar's summary says that saving adds 1 new clip to `reel.yaml`

#### Scenario: Ignored clips in the bin
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window, and then in a 900 px wide window
- **THEN** the wide bin shows "Ignored clips" after `Kvällen`, with `Main · 1 ignored clip, not played` above `s1710004.mp4`, and `Main` lists only `s1710001.mp4`; the 900 px page lists `s1710004.mp4` under `Main` and has no such heading ("The event page reorders clips within a chapter")

#### Scenario: 400 clips
- **WHEN** the event has 400 clips
- **THEN** the bin scrolls on its own, the rest of the workspace does not move, and the drag-smoothness gate holds

### Requirement: State is never shown by color alone

Every render verdict, job status, clip status and event failure kind a screen shows SHALL be shown as its
words, paired with an icon, and never as a color alone. The same holds for warnings and failure messages:
each shows its words and an icon. Tones SHALL be consistent across screens: the same status has the same
tone and icon on every page.

One carve-out: in the rows of the workspace's clip bin, at every window width, with a fine pointer, a clip's
status SHALL be shown as its icon alone. Its words SHALL stay in the row as visually hidden text, so the status
keeps its name for assistive technology, and SHALL be the icon's tooltip. Each clip status a bin row can show
(Included, New, Missing, Ignored and Excluded) SHALL have its own icon there, distinct in shape from every other
clip status's, so the status is never told by color alone. With a coarse pointer, and everywhere outside the
workspace's clip bin (the event page's tables and its Edit mode without the workspace), a clip's status keeps its
words beside the icon.

In both color schemes, text SHALL meet WCAG 2.1 AA contrast: at least 4.5:1 for normal-size text, and at
least 3:1 for large text and for the focus indicator against its background. This includes the words inside
status labels and secondary ("muted") text. As in WCAG, the label of a control that is currently
unavailable (such as Refresh while it reads) is exempt.

A busy button SHALL show a loader before its label, in place of its icon, drawn in the button's own text
color. In the operating system's forced-colors mode, where the browser replaces the page's colors with the
system palette, that loader SHALL stay visible, in the same color as the button's label.

#### Scenario: Verdicts read in grayscale
- **WHEN** the event list for the dev library is viewed with all color removed
- **THEN** `2024-06-27 - Grillning med grannar` still reads "Needs render" with its reasons, and
  `2023-06-23 - Midsommar - Dalarna` still reads "Up to date"

#### Scenario: Status labels meet contrast in both schemes
- **WHEN** the contrast of every status label's text on its own background, and of the scan time's muted
  text on the page background, is measured in the light and in the dark scheme
- **THEN** every ratio is at least 4.5:1

#### Scenario: A failed job is marked by words and icon
- **WHEN** the list shows `2024-10-05 - Trasig`, whose latest job failed
- **THEN** its job status reads "Failed" beside an icon, and not only in a red color

#### Scenario: A busy button's loader survives forced colors
- **WHEN** the operator's system uses forced colors, and the operator presses Render on
  `2024-06-27 - Grillning med grannar` while the service takes two seconds to answer
- **THEN** during those seconds Render shows a loader in the same color as its label, in place of its icon,
  and the loader is not drawn in the button's background color

#### Scenario: A clip's status in the bin is its icon alone with a fine pointer
- **WHEN** Edit mode opens on `2024-08-02 - Badutflykt - Varberg` in a 1280×720 window with a fine pointer, light and dark
- **THEN** in the bin the new clip's row shows an icon for its status and no visible word "New", the row's text for assistive technology (the visually hidden words) reads "New" and the icon's tooltip is "New", and the icons of Included, New, Missing, Ignored and Excluded differ in shape, not only in color

#### Scenario: The bin's status is icon-only in a narrow window too
- **WHEN** the same event is opened in a 900 px wide window with a fine pointer
- **THEN** the bin's new clip's row shows the icon and no visible word "New", as in the wide window

#### Scenario: A clip's status keeps its words elsewhere
- **WHEN** the same event is opened with a coarse pointer in a 1280×720 window, and the event page is viewed outside the workspace
- **THEN** the new clip's row, and the event page's clip rows, show the word "New" beside its icon

### Requirement: The event page reorders clips within a chapter

An event's page SHALL offer an **Edit** mode on the page itself. Entering or leaving it SHALL NOT change the
page's address. Entering Edit mode SHALL read the event's editorial document from the service. When that read
fails, the page SHALL say why, using the same words it uses for a failed event read, and SHALL offer no
editing. Entering Edit mode SHALL keep keyboard focus on the control that entered it, and leaving Edit mode,
by any path, SHALL move keyboard focus to the page's level-one heading.

While in Edit mode, the editor's chapter lists and metadata fields SHALL take the place of the chapter tables,
the facts and the description. Each chapter keeps its level-two heading, and each clip row keeps the facts the
table shows: its position, the clip's name as the event page's table names it, its status in words (in the clip bin with a fine pointer, as its icon with the words hidden, "State is never shown by color alone"), size and
modification time, with absent facts shown as absent. The event's verdict and latest job stay shown. Leaving
Edit mode, by any path, SHALL read the event again and show the tables. Only the operator's own actions SHALL
end Edit mode or change what it holds: a read of the event that the page would start by itself while Edit mode
is open SHALL NOT discard the edits.

In Edit mode, each chapter SHALL list its clips in the order the page shows them. The operator SHALL be able
to move a clip to any other position **within its own chapter** in each of three ways:

- by dragging the clip's handle with a mouse, pen or touch. A drag SHALL start only from the handle, and a
  tap or click on the handle SHALL NOT start one. A scroll gesture that starts anywhere else on the page
  SHALL scroll it.
- from the keyboard, on the clip's handle: one key lifts the clip, the arrow keys move it, one key drops it,
  and Escape cancels, leaving the order as it was
- with a **Move up** and a **Move down** control on every movable row. After such a move, keyboard focus SHALL
  stay on the moved clip's row.

Every keyboard or control move, and every drop or cancel, SHALL be announced to assistive technology with the
clip's name, as the event page's table names it, and its position out of the number of clips the chapter plays
(its ignored clips, and the missing clips the operator removed, are not counted). Move up and Move down SHALL
NOT take a clip into another chapter. A clip changes chapter only when it is dragged into another chapter (see
"Edit mode drags clips between chapters") or moved with Move marked to… (see "Edit mode moves the marked clips to a chapter"). A missing clip's drag SHALL stop at its own chapter's edge. Among the clips
a chapter held when Edit mode opened and still holds, the page SHALL count as moved the fewest clips whose
moves explain the new order, so that moving one clip from position 1 to position 5 moves one clip, not five.
Each such clip counted as moved SHALL show its position from when Edit mode opened. A clip moved in from
another chapter SHALL count as one moved clip, and SHALL show the chapter it came from instead.

Clips the event ignores are not part of the play order. Each chapter SHALL list them after its other clips,
marked as ignored, except in the workspace's clip bin from 960 CSS pixels wide, which lists every chapter's ignored
clips after the last chapter, under a caption that names the chapter ("The clip bin holds the chapters' clip lists");
there they still count as listed by that chapter. Either way they SHALL NOT be movable or counted in the chapter's positions. A missing clip SHALL
stay listed and movable, and SHALL never be dropped from its chapter, except when the operator removes it
with its own control (see "Edit mode removes a missing clip from reel.yaml on request"). A NEW clip SHALL be
movable like any other.

#### Scenario: Dragging a clip to the front
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator drags `s1710004.mp4` above
  `s1710001.mp4`
- **THEN** the chapter lists `s1710004.mp4`, `s1710001.mp4`, `s1710002.mp4`, `s1710003.mp4`, and
  `s1710004.mp4` shows that it was at position 4

#### Scenario: Reordering from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator focuses the handle of `Kvällen/s1710002.mp4`,
  lifts it, presses Down once, and drops it
- **THEN** `Kvällen` lists `s1710003.mp4`, `s1710002.mp4`, `s1710004.mp4`, and a screen reader hears that
  `s1710002.mp4` moved to position 2 of 3

#### Scenario: Escape cancels a keyboard move
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator lifts `s1710001.mp4` from the keyboard, moves
  it two places, and presses Escape
- **THEN** the clip is back at position 1, the order is unchanged, and the cancel is announced

#### Scenario: The move controls keep focus on the moved clip
- **WHEN** on `2024-09-01 - Sommarlov`, the operator activates **Move down** on `s1710002.mp4`
- **THEN** `s1710002.mp4` is at position 2, keyboard focus is still on its row, and its move is announced

#### Scenario: A clip cannot leave its chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator activates **Move up** on `Kvällen/s1710002.mp4`,
  the first clip of `Kvällen`
- **THEN** the control says that it is unavailable, nothing moves, and `Main` is unchanged: only a drag or Move marked to… takes a clip into another chapter

#### Scenario: A missing clip cannot leave its chapter
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator drags `borttagen.mp4`
  downward toward `Morgon`, past the bottom of `Main`, and releases it
- **THEN** the dragged clip stopped at the bottom edge of `Main`, `borttagen.mp4` is still at position 3 of
  `Main`, and `Morgon` plays no clip

#### Scenario: An ignored clip is listed but cannot move
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a window narrower than 960 px
- **THEN** `Main` lists `s1710001.mp4` and then `s1710004.mp4`, marked as ignored, and `s1710004.mp4` has no
  handle and no move controls

#### Scenario: A missing clip keeps its place
- **WHEN** Edit mode opens on `2024-09-01 - Sommarlov`, whose `reel.yaml` lists the missing `borttagen.mp4`
  last
- **THEN** `borttagen.mp4` is listed at position 3, marked as missing, and can be moved like the others

#### Scenario: A large chapter is fully editable
- **WHEN** an event holds 400 clips in one chapter
- **THEN** all 400 are listed in Edit mode, and any of them can be moved to any position in the chapter

#### Scenario: The editorial document cannot be read
- **WHEN** the operator enters Edit mode on an event whose `reel.yaml` became unparseable after the page was
  read
- **THEN** the page shows the unparseable-document failure in words, with the service's detail, and offers
  no editing

#### Scenario: In the wide bin ignored clips follow the chapters
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window
- **THEN** `Main` lists only `s1710001.mp4`, `Kvällen` follows it directly, and after `Kvällen` and before Add chapter the bin lists, under "Ignored clips" and "Main · 1 ignored clip, not played", `s1710004.mp4` marked as ignored, with no handle and no move controls; in a 900 px wide window `Main` lists `s1710001.mp4` and then `s1710004.mp4`, and there is no "Ignored clips" heading
