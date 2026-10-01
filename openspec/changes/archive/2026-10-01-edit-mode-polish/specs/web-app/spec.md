## ADDED Requirements

### Requirement: Edit mode's save bar stays compact and fits the window

While Edit mode shows its save bar, the bar SHALL fit the window at every width from 320 CSS pixels up.
Nothing the bar shows SHALL make the page scroll horizontally, including a failed save's explanation and
its choices, and every word of it SHALL stay inside the window.

The bar SHALL present exactly one primary action at a time: the way on from its current state.

- **Reload latest** while a conflict holds Save back
- **Back to the event list** when the event no longer exists
- **Save** in every other state

Every other control in the bar SHALL be presented as secondary. A control that the state holds back SHALL
stay in its place, SHALL say that it is unavailable, and SHALL keep keyboard focus when it has it. Save
after a conflict, or after the event is found gone, is one such control.

In a window 390 × 844 CSS pixels, with the bar held at the window's bottom edge, the bar SHALL take at most
a third of the window's height. This includes the times it shows a conflict. A failure to save SHALL show
the service's detail in full, and the bar SHALL then take at most two fifths of the window's height.

The bar SHALL NOT show the browser's own error text. When a save gets no answer at all, the bar SHALL say
that the service is not reachable and offer Retry, without the text the browser gave for the failed request.
An error in the page itself SHALL be shown as a failed save with Retry, and SHALL NOT be reported as an
unreachable service.

#### Scenario: A conflict at phone width
- **WHEN** in a window 390 × 844, the operator is editing the location of
  `2024-06-27 - Grillning med grannar`, its `reel.yaml` title is changed by hand, and the operator saves
- **THEN** the save bar says that the event changed since it was read and offers "Reload latest" and
  "Overwrite with mine", with "Reload latest" as its one primary action. Save is held back, presented as
  secondary, and still has keyboard focus. The bar takes at most a third of the window's height, and the
  page does not scroll horizontally.

#### Scenario: A conflict in the narrowest window
- **WHEN** the same conflict is answered in a window 320 pixels wide
- **THEN** the page does not scroll horizontally, and the alert's title, both choices and the note that the
  edits are kept are all inside the window

#### Scenario: No answer at phone width
- **WHEN** in a window 390 × 844, the operator saves a reorder of `2024-08-02 - Badutflykt - Varberg` and the
  request gets no answer
- **THEN** the save bar says that the service is not reachable, offers Retry, keeps the reorder and shows no
  browser error text such as "Failed to fetch". Save is its one primary action, and the bar takes at most a
  third of the window's height.

#### Scenario: A failed write at phone width
- **WHEN** in a window 390 × 844, the operator saves a reorder of `2024-09-01 - Sommarlov` while its folder
  cannot be written
- **THEN** the save bar says that `reel.yaml` could not be saved, shows the service's whole detail with the
  path it names, and offers Retry. Save is its one primary action, the bar takes at most two fifths of the
  window's height, and the page does not scroll horizontally.

### Requirement: Edit mode keeps keyboard focus in view and never drops it

After the operator drops, moves, removes or restores a clip in Edit mode, from the keyboard or with a
pointer, the control that holds keyboard focus SHALL be fully visible together with its whole row. No part
of either SHALL be covered by the page header, the chapter's heading or the save bar. This SHALL also hold
for the edit that first brings the save bar in.

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

### Requirement: Edit mode lines up with the event page and fits a phone

Entering Edit mode SHALL NOT move each clip's thumbnail, name, status, size or modification time sideways from
where the event page's table showed them. This SHALL hold wherever a chapter's panel is wide enough for both
the table and Edit mode's one-line rows. Only two things SHALL move: the position number makes room for the
drag handle, and the move controls take room from the end of the file column. The control that leaves Edit
mode SHALL be presented like the control that entered it, and never as an unavailable control.

In a window 320 CSS pixels wide or wider, no state of Edit mode SHALL make the page scroll horizontally.

- **A chapter's heading** SHALL stay within its panel. What the chapter holds (moved, missing, removed and
  ignored clips) SHALL NOT make the heading wrap or widen. It SHALL name the chapter, say how many clips
  moved, and say how many clips the chapter plays.
- **The lists of removed clips and of ignored clips** SHALL each say how many clips they hold.
- **A missing clip's row** SHALL keep, in a window 390 pixels wide, the two-line layout of the other rows:
  - the first line holds its name and its move controls
  - its placeholder box sits beside its status, its absent size and time, and its remove control

In both color schemes, each metadata field's edge SHALL have a contrast of at least 3:1 against the surface
around it, so that an empty field is visible.

#### Scenario: Entering Edit mode moves no column
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide and enters
  Edit mode
- **THEN** each clip's thumbnail, file name, status, size and modification time start within one pixel of
  where the table showed them, and the Stop editing control has the same button style that Edit had

#### Scenario: A chapter with a removal and a move in the narrowest window
- **WHEN** in a window 320 pixels wide, in Edit mode on `2024-09-01 - Sommarlov`, the operator removes
  `borttagen.mp4` and moves `s1710004.mp4` up
- **THEN** the page does not scroll horizontally. The chapter's heading is one line that reads "Clips",
  "1 clip moved" and "2 clips". The list below the chapter says "1 clip removed from reel.yaml when you
  save".

#### Scenario: A chapter with an ignored clip
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a window 390 pixels wide
- **THEN** the heading of `Main` reads "Main" and "1 clip", its ignored list says "1 ignored clip, not
  played" and lists `s1710004.mp4`, and the page does not scroll horizontally

#### Scenario: A missing clip's row at phone width
- **WHEN** Edit mode opens on `2024-09-01 - Sommarlov` in a window 390 pixels wide
- **THEN** the row of `borttagen.mp4` shows its name and move controls on its first line, and its placeholder
  box beside "Missing from disk", the absent size and time, and its remove control. The row is at most 8
  pixels taller than the row of `s1710002.mp4`.

#### Scenario: Empty fields are visible in both schemes
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in the light and in the dark scheme
- **THEN** the edges of the empty Location and Description fields measure at least 3:1 against the panel
  around them

### Requirement: Edit mode names clips and the saved event as the other screens do

Edit mode SHALL name each clip as the event page's table names it: by its file name while every clip its
chapter lists lies in the chapter's own folder, and otherwise by its path inside the event folder. The same
name SHALL be used in the clip's row, in the names of its controls (its handle, its move controls, and its
remove or undo control), and in what Edit mode announces about the clip. Moving or removing a clip SHALL NOT
change how its chapter names its clips.

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
(its ignored clips, and the missing clips the operator removed, are not counted). A clip SHALL NOT be movable
into another chapter: a dragged clip stops at its own chapter's edge. The page SHALL count as moved the fewest
clips whose moves explain the new order, so that moving one clip from position 1 to position 5 moves one clip,
not five. Each clip counted as moved SHALL show its position from when Edit mode opened.

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

### Requirement: Edit mode removes a missing clip from reel.yaml on request

In Edit mode, every clip that `reel.yaml` lists but that is missing from disk SHALL offer a control that
removes it from `reel.yaml`. The control SHALL say that it removes the clip, SHALL name the clip to assistive
technology by the clip's name, as the event page's table names it, and SHALL be reachable with the keyboard.
No other clip SHALL offer one: a clip that is on disk (included, NEW or ignored) is never removed this way,
and nothing else in the client removes a clip from `reel.yaml`.

Removing a clip SHALL:

- take it out of its chapter's play order, so that the chapter's remaining clips are numbered, and their
  positions announced, without it
- list it under its chapter, after the clips the chapter plays, as removed from `reel.yaml` when the edits are
  saved. The listing keeps the clip's name, as the event page's table names it, and its status in words, and
  offers an **Undo** control that names the clip that way to assistive technology.
- move keyboard focus to that Undo control, and announce that the clip will be removed from `reel.yaml` when
  the edits are saved

Undo SHALL return the clip to its chapter's play order, right after whichever of the clips that came before it
when Edit mode opened comes last in the chapter's play order now, or first when none of them is still in the
play order. With no other edit to the chapter, that is the position it had. So removals undone in any order,
with no move between them, leave the chapter's order as read, and however the chapter was reordered meanwhile,
each clip still in the play order that came before it when Edit mode opened comes before it again. Undo SHALL
then move keyboard focus to the clip's remove control, and announce the clip's position out of the number of
clips the chapter plays.

A removal SHALL count as an unsaved change, like a move. The save bar says how many missing clips will be
removed, Reset returns every removed clip to its place, and leaving with a removal unsaved asks first, as
for any unsaved edit. While a save is in flight, the remove and Undo controls SHALL accept no presses.

Saving SHALL write `reel.yaml` without each removed clip, as "Saving an edit writes only what the operator
changed" states, and SHALL NOT create, change or delete any other file. After a successful save, the page
SHALL show the event without the removed clips and SHALL no longer report them as missing.

#### Scenario: Removing the missing clip of Sommarlov
- **WHEN** in Edit mode on `2024-09-01 - Sommarlov`, the operator activates the control that removes
  `borttagen.mp4` from `reel.yaml`
- **THEN** the chapter plays `s1710002.mp4` and `s1710004.mp4`, numbered 1 and 2; `borttagen.mp4` is listed
  under the chapter as removed when the edits are saved, still marked as missing, with an Undo control that
  has keyboard focus; and the page says that 1 missing clip will be removed

#### Scenario: Undo puts the clip back
- **WHEN** after removing `borttagen.mp4`, the operator activates its Undo control
- **THEN** `borttagen.mp4` is at position 3 again, keyboard focus is on its remove control, and the page
  shows no unsaved changes

#### Scenario: Undo after a move keeps the move
- **WHEN** on `2024-09-01 - Sommarlov`, the operator removes `borttagen.mp4`, moves `s1710004.mp4` up, and
  then undoes the removal
- **THEN** the chapter lists `s1710004.mp4`, `s1710002.mp4` and `borttagen.mp4`, and the page says that 1 clip
  moved, and no longer says that a missing clip will be removed

#### Scenario: Removals undone in any order restore the chapter
- **WHEN** in Edit mode on an event whose one chapter lists `s1710001.mp4` and then the missing `x.mp4` and
  `y.mp4`, the operator removes `x.mp4`, then `y.mp4`, then undoes the removal of `x.mp4`, then of `y.mp4`
- **THEN** the chapter lists `s1710001.mp4`, `x.mp4` and `y.mp4` as read, and the page shows no unsaved
  changes

#### Scenario: Reset puts every removed clip back
- **WHEN** on `2024-09-01 - Sommarlov`, the operator removes `borttagen.mp4`, moves `s1710004.mp4` up, and
  presses Reset
- **THEN** the chapter lists `s1710002.mp4`, `s1710004.mp4` and `borttagen.mp4` as read, and the page shows
  no unsaved changes

#### Scenario: Saving takes the entry out of reel.yaml
- **WHEN** the operator removes `borttagen.mp4` from `2024-09-01 - Sommarlov` and saves
- **THEN** `reel.yaml` lists `s1710002.mp4` and `s1710004.mp4` only; the line for `borttagen.mp4`, with its
  end-of-line comment, is the only line gone; and the page shows the event with no missing clip, needing a
  render, and offers Render

#### Scenario: The render succeeds once the entry is gone
- **WHEN** after that save the operator presses Render on `2024-09-01 - Sommarlov` and a worker runs the job
- **THEN** the job completes and the page shows the event as rendered and up to date

#### Scenario: Only missing clips can be removed
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, whose clips are included, NEW or ignored,
  and none is missing
- **THEN** no clip offers a control that removes it from `reel.yaml`

#### Scenario: A pending removal is an unsaved edit
- **WHEN** the operator removes `borttagen.mp4` on `2024-09-01 - Sommarlov` and presses the browser's Back
- **THEN** the event page stays, with the removal, and asks "Discard unsaved changes?"
