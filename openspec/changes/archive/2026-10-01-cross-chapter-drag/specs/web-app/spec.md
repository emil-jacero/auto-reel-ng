## ADDED Requirements

### Requirement: Edit mode drags clips between chapters

While the event lists more than one chapter, a deleted one aside, the operator SHALL be able to drag a clip
on disk (active or new) that a chapter plays into any other listed chapter. The operator SHALL be able to
drop it there before any clip that chapter plays, or after the last of them. Both ways a clip is dragged
within its chapter SHALL do this:

- **with a mouse, pen or touch**, from the clip's handle. While the dragged clip is held near the window's
  top or bottom edge, the page SHALL scroll by itself, so that a chapter out of view can be reached.
- **from the keyboard**, on the clip's handle:
  - Down at a chapter's last position SHALL take the clip to the first position of the next listed chapter.
  - Up at a chapter's first position SHALL take it to after the last clip of the chapter before.
  - A deleted chapter's placeholder SHALL be passed over.
  - Escape SHALL cancel and leave every chapter as it was, with the clip's handle in view again (its whole
    row, or its first line when the row is taller than the room left).

A chapter that plays no clip SHALL show, in Edit mode, an area that says clips can be dragged into it. The
area SHALL be shown whether or not a drag is under way. A clip dropped on it SHALL become the chapter's first
clip.

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
  heading and in the save bar, as a clip moved with Move clips does
- a clip dragged back to the chapter and the position it had when Edit mode opened SHALL count as no move;
  with no other edit, the page SHALL show no unsaved changes
- it SHALL keep its cuts and its other per-clip properties. Its Cuts control SHALL be as it was, and its
  panel stays shown or hidden as it was and keeps any time typed but not added
- Save SHALL write it as it writes a clip moved with Move clips ("Saving an edit writes only what the operator
  changed"). Reset, the unsaved-changes question, a conflict and Overwrite SHALL treat it as any other edit

Every target in another chapter SHALL be announced to assistive technology, and so SHALL a drop and a
cancel. The announcement names the clip as its row named it when it was lifted. A target or a drop in another
chapter SHALL name that chapter, and SHALL give the position out of the number of clips that chapter would
then play. Within the clip's own chapter the announcements SHALL stay as "The event page reorders clips
within a chapter" states. While more than one chapter is listed, the instructions for a keyboard drag SHALL
say that the arrows cross into the chapter before or after.

After a drop into another chapter, by pointer or keyboard, keyboard focus SHALL be on the moved clip's
handle in its new chapter. The handle and the row's first line (its handle, name and Cuts control) SHALL be
fully visible, not covered by the page header, the chapter's heading or the save bar. A row taller than that
space SHALL be scrolled so that its first line is (see "Edit mode keeps keyboard focus in view and never
drops it").

Move clips does not offer some clips, and those SHALL NOT be taken into another chapter by a drag either:

- a missing clip: its drag SHALL stop at its own chapter's edge, from the keyboard too. While more than one
  chapter is listed, its lift SHALL say that it stays in its chapter.
- an ignored clip, and a missing clip the operator removed: neither has a handle

A release over a deleted chapter's placeholder SHALL move nothing and SHALL be announced as a drop that
changed nothing. While a save is in flight, or while a Move clips move is being applied, no clip SHALL be
lifted, and a drop SHALL move nothing. The Move clips control and its dialog, and Move up and Move down,
SHALL work as they did before.

Above the chapters, Edit mode SHALL say how clips are moved:

- with one chapter: that a clip is dragged by its handle or moved with its arrows, and that a chapter can be
  added with Add chapter, below the chapters, after which clips can be dragged between chapters
- with more than one chapter: that a clip can also be dragged into another chapter, and that a chapter's Move
  clips moves several clips at once

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
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves all three clips of `Kvällen` to `Main`
  with Move clips, deletes `Kvällen`, adds a chapter `Morgon`, lifts `Kvällen/s1710004.mp4` (last in `Main`)
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

#### Scenario: Reaching a chapter out of view
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, and the operator drags the
  second chapter's first clip up and holds it at the window's top edge
- **THEN** the page scrolls up by itself until the first chapter's first clip is in view
- **WHEN** the operator releases the clip over the upper half of that first clip
- **THEN** the clip is at position 1 of 401 in the first chapter, and the second chapter plays 2 clips

#### Scenario: The hint says how to reach other chapters
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, which has one chapter
- **THEN** the hint above the chapters says that a chapter can be added with Add chapter, below the chapters,
  and that clips can then be dragged between chapters
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the hint says that a clip can be dragged into another chapter, and that a chapter's Move clips moves
  several clips at once

#### Scenario: Nothing shifts while dragging over another chapter
- **WHEN** in a window 320 pixels wide, in the light and in the dark scheme, on `2024-08-20 - Två kapitel -
  Tjörn`, the operator drags `s1710001.mp4` over `Kvällen` and holds it between `s1710002.mp4` and
  `s1710003.mp4`
- **THEN** every clip row and both chapter panels keep the size and place they had before the drag, the line
  between the two clips is visible beside the dragged copy, and the page does not scroll horizontally

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
(its ignored clips, and the missing clips the operator removed, are not counted). Move up and Move down SHALL
NOT take a clip into another chapter. A clip changes chapter only when it is dragged into another chapter (see
"Edit mode drags clips between chapters") or moved with its chapter's Move clips control (see "Edit mode moves
clips to another chapter"). A missing clip's drag SHALL stop at its own chapter's edge. Among the clips
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
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator activates **Move up** on `Kvällen/s1710002.mp4`,
  the first clip of `Kvällen`
- **THEN** the control says that it is unavailable, nothing moves, and `Main` is unchanged: only a drag or Move
  clips takes a clip into another chapter

#### Scenario: A missing clip cannot leave its chapter
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator drags `borttagen.mp4`
  downward toward `Morgon`, past the bottom of `Main`, and releases it
- **THEN** the dragged clip stopped at the bottom edge of `Main`, `borttagen.mp4` is still at position 3 of
  `Main`, and `Morgon` plays no clip

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

### Requirement: Edit mode moves clips to another chapter

While the event lists more than one chapter, a deleted one aside, each chapter SHALL offer **Move clips**. It
SHALL let the operator pick any of the clips the chapter plays that are on disk, and one of the other
chapters, and SHALL move the picked clips there. Two kinds of clip SHALL NOT be offered, and the page SHALL say
why:

- a missing clip, which stays in its chapter until its file is restored or it is removed from `reel.yaml`
- an ignored clip, which is not played

A chapter that plays no clip SHALL say that it has none to move. When exactly one other chapter is listed, it
SHALL be chosen already. A **Pick all** control SHALL pick every clip offered at once, or clear them all, and
SHALL show that it is mixed while only some are picked.

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

Move clips SHALL stay offered beside dragging. A drag takes one clip into another chapter, to the place where
it is dropped (see "Edit mode drags clips between chapters"). Move clips moves any number of picked clips at
once. A clip's Move up and Move down still never take it into another chapter (see "The event page reorders
clips within a chapter").

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

#### Scenario: Picking every clip at once
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Kvällen` and checks Pick all
- **THEN** all three clips are picked and the dialog says 3 of 3 picked
- **WHEN** the operator then clears one clip
- **THEN** Pick all shows that it is mixed, and checking it again picks all three; checking it once more picks
  none

#### Scenario: Escape moves nothing
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Kvällen`, picks
  `s1710002.mp4`, and presses Escape
- **THEN** the dialog closes, both chapters are as they were, and keyboard focus is on `Kvällen`'s Move clips

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
clip SHALL say so in Edit mode. It SHALL also say that clips can be dragged into it, or moved into it with
another chapter's Move clips (see "Edit mode drags clips between chapters").

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

### Requirement: Edit mode keeps keyboard focus in view and never drops it

After the operator drops, moves, removes or restores a clip in Edit mode, from the keyboard or with a
pointer, the control that holds keyboard focus SHALL be fully visible together with its whole row. No part
of either SHALL be covered by the page header, the chapter's heading or the save bar. This SHALL also hold
for the edit that first brings the save bar in. The one exception is a drop into another chapter (see "Edit
mode drags clips between chapters"): then the moved clip's handle and its row's first line (its handle,
name and Cuts control) SHALL be fully visible and not covered, and a row taller than the room between the
chapter's heading and the save bar SHALL be scrolled so that its first line is.

Suppose Edit mode's read of the editorial document failed and the operator presses **Try again**. Then:

- the failure SHALL stay shown while the document is read again
- Try again SHALL keep keyboard focus, and SHALL show that it is busy until the read answers
- when the read fails again, focus SHALL stay on Try again, and the failure SHALL be announced again
- when the read succeeds, focus SHALL move to the heading of the event's fields
- when the event changed on disk in the meantime, focus SHALL move to the control that reads the event
  again

Focus SHALL never fall to the page's body.

When a save is answered, the control that then holds keyboard focus SHALL be fully inside the window. This
SHALL hold when the answer makes the save bar taller than the room below the editor's top, such as a
conflict in a short window scrolled to its top.

#### Scenario: The first keyboard drop keeps the dropped clip in view
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with no other edit and in a window
  1280 × 900, the operator focuses the handle of its first clip, `s1710001.mp4`, lifts the clip, moves it
  down one place and drops it
- **THEN** the save bar appears, keyboard focus is on that handle, and the handle and its whole row are fully
  visible above the save bar

#### Scenario: The first drop at phone width
- **WHEN** the operator does the same in a window 390 × 844 with the third clip, `s1710003.mp4`
- **THEN** its handle and its whole row are fully visible above the save bar

#### Scenario: A tall row dropped into another chapter
- **WHEN** in a window 390 × 600 on `2024-08-20 - Två kapitel - Tjörn`, the operator adds four cuts in the
  Cuts panel of `Kvällen/s1710002.mp4`, so that its row is taller than the room left, and drags the clip
  into `Main` after `s1710001.mp4`
- **THEN** keyboard focus is on its handle in `Main`, and its handle, name and Cuts control are fully visible
  below the chapter's heading and above the save bar

#### Scenario: A conflict in a short window scrolled to its top
- **WHEN** in a window 320 × 568 scrolled to its top, the operator has changed the location of
  `2024-06-27 - Grillning med grannar`, presses Save, and the save is answered with a conflict
- **THEN** Save keeps keyboard focus and is fully inside the window, and so is the rest of the save bar

#### Scenario: Try again keeps focus while the document is still unreadable
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` became unparseable after its page was read,
  the operator enters Edit mode, and then presses Enter on Try again while the file is still unparseable
- **THEN** Try again shows that it is busy while the read runs, keyboard focus stays on Try again
  throughout and afterwards, and the unparseable-document failure is announced again

#### Scenario: Try again moves focus to the fields once the read succeeds
- **WHEN** after that, the file is repaired and the operator presses Enter on Try again
- **THEN** the event's fields and clip lists are shown, and keyboard focus is on the heading of the event's
  fields
