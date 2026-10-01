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

#### Scenario: The first keyboard drop keeps the dropped clip in view
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with no other edit and in a window
  1280 × 900, the operator focuses the handle of its first clip, `s1710001.mp4`, lifts the clip, moves it
  down one place and drops it
- **THEN** the save bar appears, keyboard focus is on that handle, and the handle and its whole row are fully
  visible above the save bar

#### Scenario: The first drop at phone width
- **WHEN** the operator does the same in a window 390 × 844 with the third clip, `s1710003.mp4`
- **THEN** its handle and its whole row are fully visible above the save bar

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

Entering Edit mode SHALL NOT move each clip's thumbnail, file name, status, size or modification time
sideways from where the event page's table showed them. This SHALL hold wherever a chapter's panel is wide
enough for both the table and Edit mode's one-line rows. Only two things SHALL move: the position number
makes room for the drag handle, and the move controls take room from the end of the file column. The
control that leaves Edit mode SHALL be presented like the control that entered it, and never as an
unavailable control.

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
