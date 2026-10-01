## ADDED Requirements

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
  ignored clip, because the page lists the event folder's ignored clips under that chapter whatever is saved.
  When a chapter cannot be deleted, pressing Delete SHALL change nothing and leave focus on Delete. The page
  SHALL show and announce why the chapter cannot be deleted.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up, Move down or Move clips, so that an event never saves without a chapter.

When the browser's primary pointer is coarse, each of these controls, Add chapter and Undo SHALL take a tap
anywhere in an area of at least 44 × 44 CSS pixels around it that reaches no other control, as every button
does ("Every control is large enough to touch").

A name SHALL be accepted only when both of these hold, once the spaces around it are removed:

- it is not empty
- ignoring case, it differs from the name of every other chapter of the event, including a deleted chapter not
  yet saved, and from `Main`, the name the page shows for the event's own chapter

A refused name SHALL be explained at the name field, which keeps keyboard focus, and nothing SHALL change. The
name saved is the accepted name without the spaces around it. A chapter's name SHALL be described to the
operator as the words on its title card in the movie.

A chapter the page showed when Edit mode opened SHALL, once deleted, stay listed in its place until the edits
are saved, marked as deleted when the edits are saved. It lists none of its clips. Such a chapter offers an **Undo** control that returns it to its place, and keyboard focus SHALL move to that Undo. A
chapter the operator added in this Edit mode and then deletes SHALL simply be gone. A chapter that plays no
clip SHALL say so in Edit mode, and say that clips are moved into it with another chapter's Move clips.

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
- **THEN** a chapter `Kvällen vid grillen` is listed last, saying that it plays no clip and how clips are moved
  into it; the first chapter's heading reads `Main` instead of `Clips`; keyboard focus is on the new
  chapter's heading; the addition is announced; and the save bar says "1 chapter added"

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
- **THEN** nothing is deleted, and the page says that `Main` still lists 1 ignored clip from the event folder

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

### Requirement: Edit mode moves clips to another chapter

While the event lists more than one chapter, a deleted one aside, each chapter SHALL offer **Move clips**. It
SHALL let the operator pick any of the clips the chapter plays that are on disk, and one of the other
chapters, and SHALL move the picked clips there. Two kinds of clip SHALL NOT be offered, and the page SHALL say
why:

- a missing clip, which stays in its chapter until its file is restored or it is removed from `reel.yaml`
- an ignored clip, which is not played

A chapter that plays no clip SHALL say that it has none to move. When exactly one other chapter is listed, it
SHALL be chosen already.

The moved clips SHALL join the end of the chosen chapter's play order, in the order they had. The one
exception is a clip that returns to the chapter it was in when Edit mode opened. It SHALL go right after
whichever of the clips that came before it then comes last in that chapter's play order now, or first when
none of them is still there. So clips moved to another chapter and back, with no move in between, leave
nothing to save.

After the move:

- keyboard focus SHALL be on the Move clips control that was used
- the move SHALL be announced with the number of clips and the chosen chapter's name
- each moved clip SHALL show, in its row, the chapter it came from, instead of its old position
- it SHALL count once as a moved clip, both in its new chapter's heading and in the save bar

A clip moved to another chapter keeps its per-clip properties. Asking to move with no clip picked, or with no
chapter chosen, SHALL say which is missing, move keyboard focus to it, and move nothing. Cancelling, or
pressing Escape, SHALL move nothing and SHALL return focus to Move clips.

Dragging a clip, and its Move up and Move down, still never take it into another chapter (see "The event page
reorders clips within a chapter").

#### Scenario: Moving two clips to Main
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Kvällen`, picks
  `s1710002.mp4` and `s1710003.mp4`, and moves them to `Main`
- **THEN**
  - `Main` plays `s1710001.mp4`, `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4`, the last two marked as
    coming from `Kvällen`, and its heading says 2 clips moved
  - `Kvällen` plays `s1710004.mp4` alone, and its heading counts no clip moved
  - keyboard focus is on `Kvällen`'s Move clips
  - "2 clips moved to Main" is announced
  - the save bar says that 2 clips moved

#### Scenario: Moving a clip with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, using only the keyboard, the operator activates Move clips on
  `Kvällen`
- **THEN** a dialog opens, named "Move clips from “Kvällen”", with keyboard focus on the box of `s1710002.mp4`.
  It lists `s1710002.mp4`, `s1710003.mp4` and the new `s1710004.mp4`, and offers `Main`, already chosen as the
  only other chapter.
- **WHEN** the operator checks that box with Space, then moves focus to the dialog's button that moves the
  clips, and presses Enter
- **THEN** the dialog closes, `Kvällen/s1710002.mp4` is last in `Main`, and keyboard focus is back on
  `Kvällen`'s Move clips

#### Scenario: Moving clips back leaves nothing to save
- **WHEN** after moving `s1710002.mp4` and `s1710003.mp4` from `Kvällen` to `Main` on
  `2024-08-20 - Två kapitel - Tjörn`, the operator moves both back to `Kvällen` with `Main`'s Move clips
- **THEN** `Kvällen` plays `s1710002.mp4`, `s1710003.mp4` and `s1710004.mp4` as read, and the page shows no
  unsaved changes

#### Scenario: Asking to move nothing
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator opens Move clips
  on `Kvällen` and asks to move without picking a clip
- **THEN** the dialog stays open and says at the clips that one must be picked, with keyboard focus on the
  first clip's box
- **WHEN** the operator picks `s1710002.mp4` and asks again
- **THEN** the dialog says at the chapters that one must be chosen, with keyboard focus on the first chapter's
  choice, and nothing has moved

#### Scenario: Ignored and missing clips are not offered
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Main`
- **THEN** the dialog lists only `s1710001.mp4`, not the ignored `s1710004.mp4`
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator opens Move clips on `Main`
- **THEN** the dialog lists `s1710002.mp4` and `s1710004.mp4`, not the missing `borttagen.mp4`, and says that a
  missing clip stays in its chapter until its file is restored or it is removed

#### Scenario: Picking clips by touch
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips
  on `Kvällen`
- **THEN** each clip's box and each chapter's choice takes a tap anywhere in a row at least 44 pixels tall and
  as wide as the dialog's list, the rows do not overlap, and the dialog fits the window without scrolling the
  page horizontally

#### Scenario: Escape moves nothing
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Kvällen`, picks
  `s1710002.mp4`, and presses Escape
- **THEN** the dialog closes, both chapters are as they were, and keyboard focus is on `Kvällen`'s Move clips

### Requirement: Edit mode says what a chapter's name means for clips added later

A clip that appears in an event's folder after its `reel.yaml` exists joins, at the next render, the chapter
named exactly after the folder it is in, or the event's own chapter when no chapter has that name. So a
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

A folder counts only while it holds a clip on disk. The page SHALL compare a name with a folder's exactly, as
the render does. A name that differs from a folder's only in case attracts nothing from that folder, and the
page SHALL say so as for any other name.

#### Scenario: Renaming a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Rename on `Kvällen` and types `Kväll`
- **THEN** before the rename is confirmed, the dialog says that no chapter will be named after the folder
  `Kvällen`, so clips added to it later will join `Main`. After it is confirmed, the chapter `Kväll` says the
  same.

#### Scenario: A name that differs from the folder's only in case
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `kvällen`
- **THEN** the rename is accepted, and the page says that no chapter will be named after the folder
  `Kvällen`, so clips added to it later will join `Main`

#### Scenario: A new chapter named after a folder
- **WHEN** after renaming `Kvällen` to `Kväll` on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a
  chapter and types `Kvällen`
- **THEN** the dialog says that clips added to the folder `Kvällen` later will join this chapter, and that
  the clips from it listed in other chapters stay where they are

#### Scenario: Deleting a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves the three clips of `Kvällen` to `Main` and
  deletes `Kvällen`
- **THEN** the deleted chapter says that clips added to the folder `Kvällen` later will join `Main`

#### Scenario: Renaming a chapter that lists an ignored clip
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` also ignores `Kvällen/s1710004.mp4`, and the
  operator renames `Kvällen` to `Kväll`
- **THEN** the dialog and then the chapter say that its 1 ignored clip will be listed under `Main`. After
  saving, the page lists `Kvällen/s1710004.mp4` as ignored under the event's own chapter, and `Kväll` lists
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4`.

#### Scenario: Deleting a chapter that lists an ignored clip
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` also ignores `Kvällen/s1710004.mp4`, and the
  operator moves the two clips `Kvällen` plays to `Main` and deletes `Kvällen`
- **THEN** the deleted chapter says that its 1 ignored clip will be listed under `Main`. After saving, the
  page lists `Kvällen/s1710004.mp4` as ignored under the event's own chapter.

### Requirement: The event page shows an empty chapter as empty

The event page SHALL show a chapter that plays no clip and lists no ignored clip with its heading and its
count of 0 clips. In place of a table, the page SHALL say that the chapter has no clips and is left out of
the movie. A chapter without clips has no title card and no chapter marker in the rendered movie.

#### Scenario: A saved empty chapter
- **WHEN** the operator adds a chapter `Kvällen vid grillen` to `2024-06-27 - Grillning med grannar` and saves
- **THEN**
  - `reel.yaml` lists the chapter after the event's own chapter, with no clips
  - the event page shows a `Kvällen vid grillen` panel counting 0 clips, saying that it has no clips and is
    left out of the movie, with no table
  - the page does not scroll horizontally in a window 320 pixels wide

## MODIFIED Requirements

### Requirement: The event page reorders clips within a chapter

An event's page SHALL offer an **Edit** mode on the page itself. Entering or leaving it SHALL NOT change the
page's address. Entering Edit mode SHALL read the event's editorial document from the service. When that read
fails, the page SHALL say why, using the same words it uses for a failed event read, and SHALL offer no
editing. Entering Edit mode SHALL keep keyboard focus on the control that entered it, and leaving Edit mode,
by any path, SHALL move keyboard focus to the page's level-one heading.

While in Edit mode, the editor's chapter lists and metadata fields SHALL take the place of the chapter tables,
the facts and the description. Each chapter keeps its level-two heading, and each clip row keeps the facts the
table shows: its position, the clip's name as the event page's table names it, its status in words, size and
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
(its ignored clips, and the missing clips the operator removed, are not counted). None of these three ways
SHALL take a clip into another chapter: a dragged clip stops at its own chapter's edge. A clip changes chapter
only through its chapter's Move clips control (see "Edit mode moves clips to another chapter"). Among the clips
a chapter held when Edit mode opened and still holds, the page SHALL count as moved the fewest clips whose
moves explain the new order, so that moving one clip from position 1 to position 5 moves one clip, not five.
Each such clip counted as moved SHALL show its position from when Edit mode opened. A clip moved in from
another chapter SHALL count as one moved clip, and SHALL show the chapter it came from instead.

Clips the event ignores are not part of the play order. Each chapter SHALL list them after its other clips,
marked as ignored, and they SHALL NOT be movable or counted in the chapter's positions. A missing clip SHALL
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
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator drags `Kvällen/s1710003.mp4` upward toward the
  `Main` chapter, past the top of `Kvällen`, and releases it
- **THEN** the dragged row stopped at the top edge of `Kvällen`, the clip is now first in `Kvällen`, and
  `Main` is unchanged

#### Scenario: An ignored clip is listed but cannot move
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
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

### Requirement: Saving an edit writes only what the operator changed

Edits SHALL be saved only when the operator asks. While Edit mode holds changes that differ from what it
read, the page SHALL keep visible:

- which metadata fields changed
- how many clips moved, counted as the reorder requirement counts them
- how many missing clips will be removed from `reel.yaml`
- how many chapters were added, renamed and deleted, and whether the chapters' order changed
- when saving would add NEW clips to `reel.yaml`, how many
- a **Reset** control, which restores what was read
- a **Save** control

An edit that is undone SHALL leave no change to save: a clip moved and moved back, within its chapter or to
another chapter and back, a removal undone, a chapter renamed back or moved back, a deleted chapter restored,
or a chapter added and deleted again.

Saving SHALL write the editorial document exactly as Edit mode read it, with only the operator's edits
applied:

- **Edited metadata fields** take their new values.
- **A chapter whose order changed** is written in the order shown, with its ignored clips and its removed
  clips left out, and its other missing clips and its NEW clips kept in place. A chapter's order changes when
  it is reordered, when a missing clip is removed from it, and when a clip is moved into it or out of it.
- **A removed clip's own per-clip properties** (its trims, title-clip choice, rotation and exclusion) are left
  out with it, since `reel.yaml` no longer lists the clip.
- **A clip moved to another chapter keeps its per-clip properties.**
- **Everything else** is written exactly as read: every other chapter, every other per-clip property, the
  ignored clips and the look.

Two kinds of save SHALL instead write every chapter the page lists, in the order the chapters are shown and
under its current name. Each chapter's clips are written in the order shown, without its ignored and removed
clips, and with its missing and NEW clips in place. A deleted chapter is left out.

- **A save that changes the chapters themselves**: a chapter added, renamed or deleted, or the chapters'
  order changed. Every NEW clip then joins `reel.yaml` in the chapter where the page shows it. So after the
  save, the page shows each clip where it showed it before, and a chapter's name only decides where clips
  added to its folder later go.
- **A save that changes any order or any chapter when `reel.yaml` names no chapters**, either because the
  event has no `reel.yaml` or because its `reel.yaml` sets none.

A save that changes only metadata SHALL still write the chapters as read, and none when `reel.yaml` names
none.

The save SHALL be conditional on the editorial state being the one Edit mode read, so that a change made
elsewhere in the meantime is detected rather than overwritten. While a save is in flight, the page SHALL
NOT start another save or accept further edits. The control that started it (Save, Retry, or the overwrite
after a conflict) SHALL show that it is busy and SHALL keep keyboard focus until the service answers.

When a save succeeds, the page SHALL:

- confirm it
- leave Edit mode
- read the event again, which then shows the event as needing a render
- read the list again the next time the list is shown

A save SHALL NOT enqueue a render. Entering Edit mode also has a guard. When the event's chapters as the page
shows them no longer agree with the editorial document it just read (the event changed on disk in between),
Edit mode SHALL say so and offer to read the event again, and SHALL NOT offer to save.

#### Scenario: Reordering one chapter leaves the rest untouched
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `Kvällen/s1710004.mp4` (NEW) to the
  front of `Kvällen` and saves
- **THEN** `reel.yaml` lists `Kvällen` as `Kvällen/s1710004.mp4`, `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, lists `Main` as `s1710001.mp4` alone, and still ignores `s1710004.mp4`

#### Scenario: The editor says a reorder adopts NEW clips
- **WHEN** on `2024-08-02 - Badutflykt - Varberg`, whose `reel.yaml` lists two of its three clips, the
  operator moves `s1710001.mp4` below `s1710003.mp4`
- **THEN** before saving, the page says that saving adds 1 new clip to `reel.yaml`, and after saving,
  `reel.yaml` lists `s1710003.mp4`, `s1710001.mp4` and `s1710004.mp4`

#### Scenario: A missing clip survives a reorder
- **WHEN** on `2024-09-01 - Sommarlov`, the operator swaps `s1710002.mp4` and `s1710004.mp4` and saves
- **THEN** `reel.yaml` lists `s1710004.mp4`, `s1710002.mp4` and `borttagen.mp4`, and `borttagen.mp4` keeps
  its end-of-line comment

#### Scenario: A metadata edit leaves the clip order alone
- **WHEN** the operator changes only the location of `2024-06-27 - Grillning med grannar` to `Hönö` and saves
- **THEN** `reel.yaml` gains the location, and its chapters are unchanged

#### Scenario: A document without chapters stays without chapters
- **WHEN** the operator changes only the title of `2024/Blandat`, whose `reel.yaml` names no chapters, and
  saves
- **THEN** the saved `reel.yaml` has the new title and still names no chapters

#### Scenario: A first reorder writes every chapter
- **WHEN** an event with clips in two chapter folders has no `reel.yaml`, and the operator reorders one
  chapter and saves
- **THEN** the new `reel.yaml` lists both chapters with every clip: the reordered one in its new order, the
  other in the order the page showed

#### Scenario: An undone move leaves nothing to save
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator moves `s1710002.mp4` down and then back up
- **THEN** the page shows no unsaved changes, and offers no Save

#### Scenario: Save keeps focus while it is in flight
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a reorder pending, the operator presses Enter on
  Save and the service has not answered yet
- **THEN** Save shows that it is busy, keyboard focus is still on Save, a second Enter sends no second save,
  and the clip lists and fields accept no edits

#### Scenario: A saved edit makes the event need a render
- **WHEN** the operator saves a new title for `2024-06-21 - Midsommar - Dalarna`
- **THEN** the page confirms the save, leaves Edit mode, and shows the new title and that the event needs a
  render because of the edit. No job was enqueued, and on returning to the list, the list is read again and
  shows the new title.

#### Scenario: The event changed on disk before editing
- **WHEN** a clip is added to `reel.yaml` of `2024-09-01 - Sommarlov` by hand after its page was read, and
  the operator then enters Edit mode
- **THEN** Edit mode says the event changed since the page was read, offers to read it again, and offers no
  Save

#### Scenario: A removed clip leaves with its own properties only
- **WHEN** on `2024-09-02 - Två saknade`, whose `reel.yaml` lists the missing `gone-a.mp4` with an end-of-line
  comment in its root chapter and gives the missing `Kväll/gone-b.mp4` of its `Kväll` chapter a trim, the
  operator removes `Kväll/gone-b.mp4` and saves
- **THEN** `reel.yaml` lists `Kväll` as `Kväll/s1710003.mp4` alone and holds no properties for
  `Kväll/gone-b.mp4`, and its root chapter, including `gone-a.mp4` and its comment, is unchanged

#### Scenario: A removal is counted apart from moves
- **WHEN** on `2024-09-01 - Sommarlov`, the operator removes `borttagen.mp4` and moves `s1710004.mp4` to the
  front
- **THEN** the page says that 1 clip moved and that 1 missing clip will be removed

#### Scenario: Moving clips writes the two chapters
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710002.mp4` and `s1710003.mp4` from
  `Kvällen` to `Main` and saves
- **THEN** `reel.yaml` lists the default chapter as `s1710001.mp4`, `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, and `Kvällen` as `Kvällen/s1710004.mp4`, which was NEW. The save bar said before the
  save that it adds 1 new clip to `reel.yaml`, and `s1710004.mp4` is still ignored.

#### Scenario: A moved clip keeps its cut
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` gives `Kvällen/s1710002.mp4` a cut from 0 to
  1.5 seconds, and the operator moves that clip to `Main` and saves
- **THEN** `reel.yaml` lists `Kvällen/s1710002.mp4` in the default chapter and still gives it that cut

#### Scenario: A renamed chapter keeps its new clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `Kväll` and saves
- **THEN** `reel.yaml` lists `Kväll` as `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and
  `Kvällen/s1710004.mp4` and names no chapter `Kvällen`. The page shows `Kväll` with those three clips, none of
  them new.

#### Scenario: A chapter added to a document without chapters
- **WHEN** the operator adds a chapter `Morgon` to `2024/Blandat`, whose `reel.yaml` names no chapters, and
  saves
- **THEN** `reel.yaml` lists the default chapter with `s1710003.mp4`, then `Morgon` with no clips, and the page
  shows `s1710003.mp4` as included, no longer new

### Requirement: Edit mode names clips and the saved event as the other screens do

Edit mode SHALL name each clip by the rule the event page's table uses, applied to the chapter's current name
and to every clip the chapter lists now or listed when Edit mode opened. A chapter names a clip by its file
name while every one of those clips lies in the folder named like the chapter's current name (the event
folder, for the event's own chapter). Otherwise it names the clip by its path inside the event folder. So a
clip moved in and a new name take the names the table will give once saved, while a clip moved out or
removed renames nothing until the edits are saved. The same name SHALL be used in
these places:

- the clip's row
- the names of its controls: its handle, its move controls, and its remove or undo control
- the Move clips dialog
- what Edit mode announces about the clip

Moving a clip within its chapter, or removing one, SHALL NOT change how its chapter names its clips. Two edits
can change it. A clip from another folder moved into a chapter makes the chapter name its clips by their
paths, and so does a new name that is no longer its folder's.

When a save succeeds, the notification that confirms it SHALL name the event by the title the save left it
with, followed by that date when it is known, since titles repeat. When the title is not known to the page,
the notification SHALL name the event by its folder name. The page SHALL NOT guess a title or a date that the
service resolves from the folder name.

#### Scenario: A chapter that lists a clip from another folder
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its default
  chapter after `s1710001.mp4`, and the operator opens Edit mode
- **THEN** `Main` names its clips `s1710001.mp4` and `Kvällen/s1710004.mp4`, and its ignored clip
  `s1710004.mp4`, as the page's table named them, and the handle of the second is named
  "Reorder Kvällen/s1710004.mp4"

#### Scenario: The saved event is named by its title and date
- **WHEN** the operator changes the location of `2024-06-27 - Grillning med grannar` in Edit mode and saves
- **THEN** the notification says the event was saved, and names it "Grillkväll med grannarna" with its date
  2024-06-27

#### Scenario: A clip moved in from another folder is named by its path
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710002.mp4` from `Kvällen` to `Main`
- **THEN** `Main` names its clips `s1710001.mp4` and `Kvällen/s1710002.mp4`, and its ignored clip
  `s1710004.mp4`, and the second's Move up is named "Move Kvällen/s1710002.mp4 up"

#### Scenario: A renamed chapter names its clips by their paths
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `Kväll`
- **THEN** `Kväll` names its clips `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and `Kvällen/s1710004.mp4`, as
  the event page's table names them once the rename is saved
