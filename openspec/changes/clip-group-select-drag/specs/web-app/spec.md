## ADDED Requirements

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

Three kinds of clip SHALL have no mark, as Move clips does not offer them ("Edit mode moves clips to another
chapter"): a missing clip, an ignored clip, and a missing clip the operator removed. The line above the chapters SHALL
say so in a few words.

Marking is not an edit. It SHALL NOT show the save bar, SHALL NOT count as an unsaved change, SHALL NOT enable Reset or
Save, and SHALL NOT make leaving Edit mode ask first. Marks SHALL be kept per clip, whichever chapter it is in, and a
mark SHALL stay on its clip when another edit moves the clip (Move up, Move down, a drag of another clip), and when the
Cuts panel is opened or closed.

A line above the chapters SHALL always be present in Edit mode, saying how clips are marked and that dragging a marked
clip's handle moves all marked clips. While at least one clip is marked, the same line SHALL show how many ("1 clip
marked", "3 clips marked") and a **Clear marks** button. The line SHALL keep its height whether or not it shows the
count, so that marking the first clip, and clearing the last mark, move no row.

Each change of a mark, and Clear marks, SHALL be announced once to assistive technology, with the clip's name and the
count ("s1710002.mp4 marked. 2 clips marked.", "s1710002.mp4 unmarked. No clips marked.", "Marks cleared."). Marks
SHALL end as follows:

- a clip that a drag or Move clips moves into another chapter, or that a group drag moves, SHALL be unmarked by that
  move; a drop that changes nothing SHALL leave every mark
- all marks SHALL end on a successful Save, on Reset, when Edit mode is left, and when the editor reads the event's
  `reel.yaml` again (Reload latest)
- a drag of an unmarked clip, Move up, Move down, adding, renaming or deleting a chapter, and cut edits SHALL leave
  marks as they are

The mark and Clear marks follow the busy-control rule: while a save is in flight or a Move clips is being applied, they
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
- **THEN** neither row has a mark, and the line above the chapters says that missing and ignored clips cannot be
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

### Requirement: Dragging a marked clip moves the whole marked group

While two or more clips are marked, lifting any marked clip SHALL lift all marked clips, in each of the ways a clip
is lifted ("The event page reorders clips within a chapter", "Edit mode drags clips between chapters"): by its handle
with a mouse, pen or touch, and from the keyboard on its handle. Only a marked clip's handle lifts a group. Lifting an
unmarked clip SHALL lift that clip alone, with the marks left as they are, and a drag of one marked clip while no other
is marked SHALL be a drag of that clip alone. A drag SHALL still start only from a handle, and a coarse-pointer
scroll that starts anywhere else SHALL scroll the page.

The **group** is every marked clip, from every listed chapter, in page order: the chapters as listed, and in each its
play order. A drop SHALL be one edit. The group SHALL leave the chapters it was in, and SHALL join the chapter it is
dropped in as one run, in its page order, at the place of the drop. The place is a **gap** of that chapter: the line
above one of its clips, or the line after its last clip, or the area of a chapter that plays none. The run SHALL go
before the first clip at or after the gap that is not itself in the group, or at the chapter's end when there is none.
Every clip that is not in the group SHALL keep its order and its chapter. A chapter that loses all its clips SHALL
play none.

Every chapter, the group's own too, is a target of gaps while a group is held:

- the page SHALL show the line at the gap, and for a chapter that plays none its area marked as the target, in the
  own chapter as in another
- no row SHALL move to make room, in any chapter, and no part of the page SHALL change size or place
- a copy of the lifted clip SHALL follow the pointer, naming the number of clips and the target chapter and the
  position the run would start at out of the number of clips that chapter would then play ("3 clips to “Main”,
  starting at position 1 of 4"); within the group's only chapter it SHALL name the position without the chapter
- every held row SHALL be marked as held, by words available to assistive technology and by dimming, and the lifted
  clip's own row SHALL be marked as the clip being moved; no row's position number SHALL change while the group is
  held
- in forced colors, the line and the copy's edge SHALL stay visible

After the drop:

- each moved clip SHALL show the chapter it came from instead of its old position when it changed chapter, and SHALL
  count once as a moved clip in its new chapter's heading and in the save bar, as a clip moved with Move clips does;
  within a chapter the page SHALL count the fewest clips that explain the new order, as for any reorder
- a clip that returns to the chapter and place it had when Edit mode opened SHALL count as no move; with no other
  edit, the page SHALL show no unsaved changes
- each clip SHALL keep its cuts and its other per-clip properties, its Cuts panel shown or hidden as it was, and any
  time typed but not added
- Save SHALL write the order as it writes the order after Move clips, and Reset, the unsaved-changes question, a
  conflict and Overwrite SHALL treat it as any other edit
- the moved clips SHALL be unmarked, and keyboard focus SHALL be on the lifted clip's handle in its new place, with the
  row's first line fully visible, below the page header and the chapter's heading and above the save bar
- a drop that leaves every chapter's order as it was SHALL change nothing, SHALL leave the marks, and SHALL be
  announced as unchanged

From the keyboard, a held group SHALL be moved through the gaps of every chapter in page order with the Up and Down
arrows, and to the first gap of the next or the previous chapter with Page Down and Page Up, as a clip is moved across
chapters; Escape SHALL cancel. The instructions for a keyboard drag SHALL say, while two or more clips are marked, that
a marked clip moves with all the marked clips.

Every lift, target, drop and cancel SHALL be announced to assistive technology: "Picked up 3 marked clips.", "3 marked
clips are over “Main”, starting at position 1 of 4.", "3 clips moved to “Main”, starting at position 1 of 4.", "3
marked clips dropped, unchanged." and "Move cancelled. 3 marked clips are back where they were." Within the group's
only chapter a target is spoken as "starting at position 2 of 4" without the chapter's name.

No group SHALL be lifted, and a drop SHALL move nothing, while a save is in flight or a Move clips is being applied.
A release over a deleted chapter's placeholder SHALL move nothing and SHALL be announced as unchanged. A cancelled
drag SHALL leave the marks. While a pointer holds a group, no other part of the page SHALL show the pointer over it
and the pointer SHALL show that it holds the clips, as for a clip. Under reduced motion the copy SHALL NOT slide between
positions. In a window 320 CSS pixels wide or wider, in both color schemes, no state of a group drag SHALL make the page
scroll horizontally. Dropping a group of 50 clips into another chapter on a page whose chapters play 400 clips SHALL
reach the next painted frame within 150 ms longer than dropping one clip there (the median of five runs, in a Chromium
window 1280 × 900).

#### Scenario: Dragging two marked clips into the chapter above
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, drags the handle of `Kvällen/s1710003.mp4` up into `Main` and holds it over the upper half
  of `s1710001.mp4`
- **THEN** a line shows above `s1710001.mp4`, the copy says "2 clips to “Main”, starting at position 1 of 3", the
  two held rows are dimmed and marked as held, and no row has moved
- **WHEN** the operator releases it
- **THEN**
  - `Main` plays `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and then `s1710001.mp4`, the first two marked as
    coming from `Kvällen`, and its heading says 2 clips moved
  - `Kvällen` plays the new `s1710004.mp4` alone
  - no clip is marked and the line above the chapters shows no count
  - keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`
  - "2 clips moved to “Main”, starting at position 1 of 3." is announced
  - the save bar says that 2 clips moved and that saving adds 1 new clip to `reel.yaml`

#### Scenario: A group from two chapters lands as one run in page order
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `s1710001.mp4` (in `Main`) and
  `Kvällen/s1710003.mp4`, drags the handle of `Kvällen/s1710003.mp4` down, and releases it on the line after the last
  clip of `Kvällen`
- **THEN** `Kvällen` plays `Kvällen/s1710002.mp4`, the new `s1710004.mp4`, `s1710001.mp4` and then
  `Kvällen/s1710003.mp4` (the group in page order: `Main`'s clip first), `Main` plays no clip and shows its area for
  clips, and "2 clips moved to “Kvällen”, starting at position 3 of 4." is announced

#### Scenario: Moving a group within its own chapter
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710003.mp4`, drags the
  handle of `s1710001.mp4` and holds it between `s1710003.mp4` and `s1710004.mp4`
- **THEN** a line shows between those two clips, the copy says "2 clips, starting at position 2 of 4" without a chapter
  name, and no row moved to make room, including `s1710002.mp4`
- **WHEN** the operator releases it
- **THEN** the chapter plays `s1710002.mp4`, `s1710001.mp4`, `s1710003.mp4` and `s1710004.mp4`, the save bar counts
  the fewest clips that explain that order, nothing is marked, and "2 clips moved, starting at position 2 of 4." is
  announced
- **WHEN** the operator saves
- **THEN** `reel.yaml` lists the four clips in that order and no other line of the file changed

#### Scenario: A drop beside the group changes nothing
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710002.mp4` and `s1710003.mp4` and drops them on
  the line between them
- **THEN** the chapter plays what it played, "2 marked clips dropped, unchanged." is announced, the save bar is not
  shown, and both clips are still marked

#### Scenario: Dragging an unmarked clip moves only that clip
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710002.mp4`, and drags
  the handle of the unmarked `s1710004.mp4` above `s1710001.mp4`
- **THEN** the chapter plays `s1710004.mp4`, `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4`, the other rows made
  room while it was dragged as they did before this change, and `s1710001.mp4` and `s1710002.mp4` are still marked

#### Scenario: One marked clip drags as a clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks only `Kvällen/s1710003.mp4` and drags its handle
  up into `Main` over the upper half of `s1710001.mp4`
- **THEN** the copy says it goes to `Main` at position 1 of 2 as for any single clip, `Main` plays
  `Kvällen/s1710003.mp4` and then `s1710001.mp4`, and the clip is no longer marked

#### Scenario: A group dragged back leaves nothing to save
- **WHEN** after the first scenario on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4` in `Main` again and drags them back to the line above the new `s1710004.mp4` in `Kvällen`
- **THEN** both chapters play what they played when Edit mode opened, no row is marked as moved, and the page shows no
  unsaved changes

#### Scenario: A group with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, using only the keyboard, the operator marks `Kvällen/s1710002.mp4`
  and `Kvällen/s1710003.mp4`, focuses the handle of `Kvällen/s1710003.mp4`, lifts it with Space, presses Up
  until the gap above `s1710001.mp4` and drops it
- **THEN** "Picked up 2 marked clips." and "2 marked clips are over “Main”, starting at position 1 of 3." were
  announced before "2 clips moved to “Main”, starting at position 1 of 3.", `Main` plays the two clips and then
  `s1710001.mp4`, and keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`
- **WHEN** the operator repeats the lift on the marked clips in `Main` and presses Escape
- **THEN** "Move cancelled. 2 marked clips are back where they were." is announced, the order is unchanged, and the
  clips are still marked

#### Scenario: Page Down takes the group to the next chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `s1710001.mp4` and `Kvällen/s1710003.mp4`, lifts
  `s1710001.mp4` from the keyboard and presses Page Down
- **THEN** "2 marked clips are over “Kvällen”, starting at position 1 of 4." is announced and a line shows above
  `Kvällen/s1710002.mp4`

#### Scenario: No group while a save is in flight
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with two clips marked and an unsaved reorder, the operator presses
  Save and the service has not answered yet
- **THEN** pressing Space on a marked handle lifts nothing and announces nothing, a mouse drag from it moves
  nothing, and every chapter stays as it was

#### Scenario: A group dragged by touch
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, with `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4` marked, a touch starts on the handle of the first and moves up into `Main` above
  `s1710001.mp4` before it lifts
- **THEN** `Main` plays both clips first, and the page did not scroll horizontally
- **WHEN** a touch starts on a marked clip's name and moves up
- **THEN** the page scrolls and no clip moves

#### Scenario: Reaching a long chapter with a group
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, `Kväll`, the operator marks the
  second chapter's first two clips, lifts one with the pointer and holds it at the window's top edge
- **THEN** the page scrolls up as for one clip ("Edit mode drags clips between chapters"), and releasing the group over
  the upper half of the first chapter's first clip puts both at positions 1 and 2 of 402 there, leaving `Kväll` with 1
  clip

#### Scenario: A held group changes nothing's size
- **WHEN** in a window 320 pixels wide, in the light and in the dark scheme, on `2024-08-20 - Två kapitel - Tjörn`, the
  operator holds the marked `s1710001.mp4` and `Kvällen/s1710003.mp4` over `Kvällen`, between `s1710002.mp4` and the new
  `s1710004.mp4`
- **THEN** every clip row and both chapter panels keep the size and place they had before the drag, the line between
  the two clips is visible beside the copy, no position number changed, and the page does not scroll horizontally

#### Scenario: A group drop is fast
- **WHEN** in a Chromium window 1280 × 900, on an event whose first chapter plays 400 clips and whose second plays 3, the
  operator marks 50 clips of the first chapter and drops them into the second, five times in a fresh Edit mode each
- **THEN** the median time from the release to the next painted frame is at most 150 ms longer than that of dropping
  one unmarked clip from the first chapter into the second
## MODIFIED Requirements

### Requirement: Edit mode moves clips to another chapter

While the event lists more than one chapter, a deleted one aside, each chapter SHALL offer **Move clips**. It
SHALL let the operator pick any of the clips the chapter plays that are on disk, and one of the other
chapters, and SHALL move the picked clips there. Two kinds of clip SHALL NOT be offered, and the page SHALL say
why:

- a missing clip, which stays in its chapter until its file is restored or it is removed from `reel.yaml`
- an ignored clip, which is not played

A chapter that plays no clip SHALL say that it has none to move. When exactly one other chapter is listed, it
SHALL be chosen already. A **Pick all** control SHALL pick every clip offered at once, or clear them all, and
SHALL show that it is mixed while only some are picked. A **Pick marked** control SHALL pick the clips offered that are
marked ("Edit mode marks clips to move together"), and no other, besides any already picked. When no clip of the chapter
is marked, pressing it SHALL pick nothing and the dialog SHALL say so beside it, in words; it SHALL follow the
busy-control rule (aria-disabled, never `disabled`) and SHALL NOT close the dialog.

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
- it SHALL be unmarked; a marked clip that was not moved SHALL stay marked

A clip moved to another chapter keeps its per-clip properties. Asking to move with no clip picked, or with no
chapter chosen, SHALL say which is missing, move keyboard focus to it, and move nothing. Cancelling, or
pressing Escape, SHALL move nothing and SHALL return focus to Move clips.

Move clips SHALL stay offered beside dragging. A drag takes one clip into another chapter, to the place where
it is dropped (see "Edit mode drags clips between chapters"), and a drag of a marked clip takes every marked clip
(see "Dragging a marked clip moves the whole marked group"). Move clips moves any number of picked clips at
once, always to the end of one chosen chapter. A clip's Move up and Move down still never take it into another chapter (see "The event page reorders
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

#### Scenario: Picking the marked clips
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` and `s1710001.mp4`, opens
  Move clips on `Kvällen`, and presses Pick marked
- **THEN** the dialog says 1 of 3 picked, with only `s1710002.mp4` checked
- **WHEN** the operator moves the picked clip to `Main`
- **THEN** `Kvällen/s1710002.mp4` is last in `Main` and no longer marked, `s1710001.mp4` is still marked, and "1 clip
  moved to “Main”." is announced

#### Scenario: Pick marked with nothing marked here
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with only `s1710001.mp4` marked, the operator opens Move clips on
  `Kvällen` and presses Pick marked
- **THEN** no clip is picked, the dialog stays open and says that no clip of `Kvällen` is marked, and keyboard focus
  stays on Pick marked
