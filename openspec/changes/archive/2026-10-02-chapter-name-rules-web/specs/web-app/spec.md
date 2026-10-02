## MODIFIED Requirements

### Requirement: Edit mode adds, renames, reorders and deletes chapters

In Edit mode the operator SHALL be able to change the event's chapters themselves. Every control below SHALL
be reachable with the keyboard and SHALL name, to assistive technology, the chapter it acts on.

- **Add chapter**, after the last chapter, SHALL ask for a name and add an empty chapter with that name at the
  end.
- **Rename** SHALL ask for a new name for a chapter. The event's own chapter (the default chapter, whose clips
  are the event folder's) SHALL NOT offer it. That chapter has no name of its own: its title card shows the
  event's title, and clips without a chapter of their own join it. While the event lists other chapters, the
  page SHALL say this beside it.
- **Move up** and **Move down** SHALL move a chapter one place among the chapters, and SHALL be offered only
  while the event lists more than one chapter. After such a move, keyboard focus SHALL stay on the pressed
  control. At either end, the control that cannot move further SHALL say that it is unavailable.
- **Delete** SHALL remove a chapter only once it plays no clip. Its clips must first be moved to another
  chapter, or removed when missing. The event's own chapter can be deleted only when, in addition, it lists no
  ignored clip that the page would list under it again after the save: one from the event folder, or from a
  folder no chapter is named after. Such a clip would bring the chapter back, holding only ignored clips.
  When a chapter cannot be deleted, pressing Delete SHALL change nothing and leave focus on Delete. The page
  SHALL show and announce why the chapter cannot be deleted.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up, Move down or Move clips, so that an event never saves without a chapter.

When the browser's primary pointer is coarse, each of these controls, Add chapter and Undo SHALL take a tap
anywhere in an area of at least 44 × 44 CSS pixels around it that reaches no other control, as every button
does ("Every control is large enough to touch").

A name SHALL be accepted only when both of these hold, once the spaces around it are removed. The spaces are
the characters the engine removes from a chapter's name, so a name the page accepts is a name `reel.yaml`
loads:

- it is not empty
- compared by full Unicode case folding, the comparison the engine makes, it differs from the name of every
  other chapter of the event, including a deleted chapter not yet saved, and from `Main`, the name the page
  shows for the event's own chapter. So `ß`, `ss`, `SS` and `ẞ` are one name, as are `Kvällen` and `KVÄLLEN`.

A refused name SHALL be explained at the name field, which keeps keyboard focus, and nothing SHALL change. The
name saved is the accepted name without the spaces around it. A chapter's name SHALL be described to the
operator as the words on its title card in the movie.

A chapter the page showed when Edit mode opened SHALL, once deleted, stay listed in its place until the edits
are saved, marked as deleted when the edits are saved. It lists none of its clips. Such a chapter offers an **Undo** control that returns it to its place, and keyboard focus SHALL move to that Undo. A
chapter the operator added in this Edit mode and then deletes SHALL simply be gone. A chapter that plays no
clip SHALL say so in Edit mode, and that a chapter without clips is left out of the movie. While the event
lists another chapter, a deleted one aside, it SHALL also say that clips can be dragged into it, or moved into
it with another chapter's Move clips (see "Edit mode drags clips between chapters"). When it is the only
chapter listed, a deleted one aside, it SHALL NOT say that: no other chapter has a clip to drag or to move,
and the page offers no Move clips there.

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
  dragged into it or moved into it with Move clips; the first chapter's heading reads `Main` instead of
  `Clips`; keyboard focus is on the new chapter's heading; the addition is announced; and the save bar says
  "1 chapter added"

#### Scenario: A lone chapter offers only Add chapter
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`
- **THEN** its one chapter offers no Rename, Move up, Move down, Move clips or Delete, and the page offers Add
  chapter after it

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
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to ` Kväll på stranden `,
  with spaces around it
- **THEN** the chapter's heading reads `Kväll på stranden`. Keyboard focus is back on its Rename control. The
  rename is announced, and the save bar says that 1 chapter was renamed.

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` offers no Rename and says that it has no name of its own because its title card shows the
  event's title, while `Kvällen` offers Rename

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
- **THEN** `Kvällen vid grillen` offers Rename, but no Delete, Move up, Move down or Move clips, and the save bar
  says that 4 clips moved, 1 chapter was added and 1 chapter deleted

#### Scenario: Chapter controls on a phone
- **WHEN** the operator opens Edit mode on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area around each of `Kvällen`'s Rename, Move clips, Move up,
  Move down and Delete, and around Add chapter, reaches that control and no other (centred on each, except
  that the areas of Move up and Move down meet at the edge they share, as a clip row's move pair's do), and
  the page does not scroll horizontally

#### Scenario: Chapter controls wait for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a rename pending, the operator presses Save, and the
  service has not answered yet
- **THEN** Add chapter and every chapter's Rename, Move up, Move down, Move clips and Delete say that they are
  unavailable, and pressing them changes nothing

#### Scenario: A lone empty chapter does not point at Move clips
- **WHEN** Edit mode opens on `2024-10-05 - Tom mapp`, an event whose folder holds no clip, and the operator
  presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** the new chapter, the only one listed, counts 0 clips, and it says "No clips. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move clips, and it offers no Move clips

#### Scenario: A lone chapter whose only clip is ignored
- **WHEN** Edit mode opens on `2024-10-06 - Bara ignorerad`, an event that lists one chapter, whose only clip
  `s1710004.mp4` is ignored
- **THEN** the chapter lists the ignored clip under its heading and says "It plays no clip. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move clips

#### Scenario: A second chapter brings the hint back
- **WHEN** on `2024-10-05 - Tom mapp`, with `Kvällen vid grillen` added, the operator presses Add chapter,
  types `Morgonen` and confirms
- **THEN** both chapters say that they have no clips and that clips can be dragged into them or moved into
  them with another chapter's Move clips
- **WHEN** the operator then deletes `Morgonen`
- **THEN** `Kvällen vid grillen` says again, as it did before the addition, that it has no clips and is left
  out of the movie, without mentioning dragging or Move clips

### Requirement: Edit mode says what a chapter's name means for clips added later

A clip that appears in an event's folder after its `reel.yaml` exists joins, at the next render, the chapter
named after the folder it is in (by case folding, as below), or the event's own chapter when no chapter has
that name. So a
chapter's name decides where clips added to that folder later go. Edit mode SHALL say so wherever an edit
changes that. It SHALL say it in the name dialog, as the name is typed, and beside the chapter after the edit,
until the edits are saved or undone:

- **Renaming or deleting a chapter whose name was the name of a folder of the event that holds clips.** No
  chapter is then named after that folder, so clips added to it later join the event's own chapter.
- **Adding a chapter named after such a folder, or renaming one to that name.** Clips added to that folder
  later join this chapter, and clips from it that other chapters list now stay where they are. The folder's
  ignored clips will be listed under this chapter.
- **Renaming or deleting a chapter that lists ignored clips.** They will be listed under the event's own
  chapter, because the page lists an ignored clip under the chapter named after its folder, or under the
  event's own chapter when none is.
- **Deleting the event's own chapter.** Clips added to the event folder later start a new `Main` chapter at
  the end, and so do the ignored clips of a chapter renamed or deleted in the same edits.

In these words the page SHALL name the event's own chapter by its heading at that moment: `Main` while
another chapter is listed, `Clips` when it is the only one.

A folder counts only while it holds a clip on disk. The page SHALL compare a name with a folder's by full
Unicode case folding, as the engine does: a chapter takes the clips of every folder whose name folds to its
own. A name that differs from a folder's only in case therefore attracts that folder's clips, and a chapter
renamed between two spellings of a folder's name keeps them. The page SHALL say what the edit changes, in the
folder's own spelling, and nothing when it changes nothing.

#### Scenario: Renaming a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Rename on `Kvällen` and types `Kväll`
- **THEN** before the rename is confirmed, the dialog says that no chapter will be named after the folder
  `Kvällen`, so clips added to it later will join `Main`. After it is confirmed, the chapter `Kväll` says the
  same.

#### Scenario: A name that differs from the folder's only in case
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `kvällen`
- **THEN** the rename is accepted, and the page says nothing about later clips, since the folder `Kvällen`
  still joins this chapter

#### Scenario: A new chapter whose name differs from a folder's only in case
- **WHEN** after renaming `Kvällen` to `Kväll` on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a
  chapter and types `KVÄLLEN`
- **THEN** the dialog says that clips added to the folder `Kvällen` later will join this chapter

#### Scenario: A new chapter named after a folder
- **WHEN** after renaming `Kvällen` to `Kväll` on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a
  chapter and types `Kvällen`
- **THEN** the dialog says that clips added to the folder `Kvällen` later will join this chapter, and that
  the clips from it listed in other chapters stay where they are

#### Scenario: Deleting a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves the three clips of `Kvällen` to `Main` and
  deletes `Kvällen`
- **THEN** the deleted chapter says that clips added to the folder `Kvällen` later will join `Clips`, as the
  page now heads the event's own chapter, the only one left

#### Scenario: Renaming a chapter that lists an ignored clip
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` also ignores `Kvällen/s1710004.mp4`, and the
  operator renames `Kvällen` to `Kväll`
- **THEN** the dialog and then the chapter say that its 1 ignored clip will be listed under `Main`. After
  saving, the page lists `Kvällen/s1710004.mp4` as ignored under the event's own chapter, and `Kväll` lists
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4`.

#### Scenario: Deleting a chapter that lists an ignored clip
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` also ignores `Kvällen/s1710004.mp4`, and the
  operator moves the two clips `Kvällen` plays to `Main` and deletes `Kvällen`
- **THEN** the deleted chapter says that its 1 ignored clip will be listed under `Clips`, the event's own
  chapter's heading once it is the only one. After saving, the page lists `Kvällen/s1710004.mp4` as ignored under the event's own chapter.
