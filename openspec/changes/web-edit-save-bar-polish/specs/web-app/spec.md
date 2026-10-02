## ADDED Requirements

### Requirement: Edit mode's save bar is in the page before the first edit

Once Edit mode has read the editorial document, its save bar SHALL already be part of the page, hidden for as
long as there is nothing to save and no vanished event to explain. The first edit SHALL show it. It SHALL NOT
have to build it.

While the bar is hidden:

- it SHALL take no room in the page and draw nothing
- neither the keyboard nor assistive technology SHALL reach it: Tab SHALL NOT stop on its Reset or Save, and
  the page SHALL NOT list a region named "Unsaved changes"
- it SHALL NOT affect where notifications sit, which stay at the bottom of the window as on a page with no
  save bar, and the page SHALL NOT reserve room at its bottom for it

It SHALL be hidden again whenever nothing is left to save, as before: when every edit is undone, and after
Reset. Showing it SHALL change nothing else about it: what it says, where it is held or rests ("Edit mode's
save bar rests in the page when it would hide the editor"), and that no notification overlaps it ("Notifications
never cover the save bar").

The first edit SHALL cost no more than the next one. In a chapter that plays 400 clips, in a Chromium window
1280 × 900, the time from pressing Move down on a clip to the next painted frame, for the first edit made in
Edit mode, SHALL be at most 50 ms longer than the same press on another clip as the second edit made. The time
is the median of five runs, each in a fresh Edit mode.

#### Scenario: No save bar before the first edit
- **WHEN** in a window 1280 × 900, the operator opens Edit mode on `2024-06-27 - Grillning med grannar`, makes
  no edit, and presses Tab from the Title field through every control of the page
- **THEN** no stop is on a Reset or Save, the page lists no region named "Unsaved changes", and an error
  notification shown at that time sits at the bottom of the window, not raised for a bar

#### Scenario: The first edit shows the bar
- **WHEN** the operator then changes the title
- **THEN** the save bar is held at the window's bottom edge with the title "Unsaved changes", Reset and Save
  (which is its one primary action), and its summary names the changed title
- **AND** an error notification shown then sits above the bar and covers neither Reset nor Save

#### Scenario: An undone edit hides the bar again
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator moves `s1710001.mp4` down one
  place, and then moves it up one place
- **THEN** the save bar was shown after the first move and is hidden after the second, and the page shows no
  unsaved changes

#### Scenario: The first edit in a 400-clip chapter
- **WHEN** in a window 1280 × 900, Edit mode is open on an event whose one chapter plays 400 clips, the
  operator presses Move down on the first clip and then Move down on the second, and the five runs are timed
- **THEN** the median time to the next painted frame of the first press is at most 50 ms longer than the
  second's

### Requirement: Reset leaves keyboard focus on a heading that can be seen

Reset removes the save bar, with the control that was pressed, so keyboard focus SHALL move at once to the
page's heading, never to the page's body. When that heading is not fully visible below the page header, the
page SHALL then scroll the least distance that brings it fully into view, and keyboard focus SHALL stay on it.
When the heading is already fully visible, the page SHALL NOT scroll. This SHALL hold whichever way Reset was
pressed, whether the bar was held or resting, and at every window width from 320 CSS pixels up. The scroll
SHALL be instant: it SHALL NOT animate, with or without a reduced-motion preference.

#### Scenario: Reset from the bottom of a long page
- **WHEN** in windows 1280 × 900 and 390 × 844, in Edit mode on an event whose one chapter plays 400 clips, the
  operator moves its last clip up one place, with the page scrolled to the clip, and presses Reset from the
  keyboard
- **THEN** keyboard focus is on the page's heading, the heading is fully visible below the page header, and
  the clip is back in its place

#### Scenario: Reset with the heading already in view
- **WHEN** in a window 1280 × 900 with the page scrolled to its top, the operator changes the title of
  `2024-06-27 - Grillning med grannar` and presses Reset
- **THEN** keyboard focus is on the page's heading, and the page's scroll position is the same as before the
  press

#### Scenario: Reset with the bar resting
- **WHEN** in a window 320 × 256, the operator changes the title of `2024-06-27 - Grillning med grannar`,
  scrolls to the save bar resting after the last chapter, and presses Reset
- **THEN** keyboard focus is on the page's heading, and the heading is fully visible below the page header

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
- **WHEN** Edit mode opens on `2024-10-05 - Tom mapp`, an event that lists one chapter, the event's own, and
  whose folder holds no clip
- **THEN** the chapter's heading counts 0 clips, and it says "No clips. A chapter without clips is left out of
  the movie." It does not mention dragging clips or Move clips, and it offers no Move clips

#### Scenario: A lone chapter whose only clip is ignored
- **WHEN** Edit mode opens on `2024-10-06 - Bara ignorerad`, an event that lists one chapter, whose only clip
  `s1710004.mp4` is ignored
- **THEN** the chapter lists the ignored clip under its heading and says "It plays no clip. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move clips

#### Scenario: A second chapter brings the hint back
- **WHEN** on `2024-10-05 - Tom mapp`, the operator presses Add chapter, types `Kvällen vid grillen` and
  confirms
- **THEN** both chapters say that they have no clips and that clips can be dragged into them or moved into
  them with another chapter's Move clips
- **WHEN** the operator then deletes `Kvällen vid grillen`
- **THEN** the event's own chapter says again, as it did before the addition, that it has no clips and is left
  out of the movie, without mentioning dragging or Move clips

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
say that the arrows cross into the chapter before or after, and that Page Down and Page Up jump to the next
or the previous chapter.

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
