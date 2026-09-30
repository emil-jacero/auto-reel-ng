## ADDED Requirements

### Requirement: The event page reorders clips within a chapter

An event's page SHALL offer an **Edit** mode on the page itself. Entering or leaving it SHALL NOT change the
page's address. Entering Edit mode SHALL read the event's editorial document from the service. When that read
fails, the page SHALL say why, using the same words it uses for a failed event read, and SHALL offer no
editing. Entering Edit mode SHALL keep keyboard focus on the control that entered it, and leaving Edit mode,
by any path, SHALL move keyboard focus to the page's level-one heading.

While in Edit mode, the editor's chapter lists and metadata fields SHALL take the place of the chapter tables,
the facts and the description. Each chapter keeps its level-two heading, and each clip row keeps the facts
the table shows: its position, file name, status in words, size and modification time, with absent facts
shown as absent. The event's verdict and latest job stay shown. Leaving Edit mode, by any path, SHALL read
the event again and show the tables. Only the operator's own actions SHALL end Edit mode or change what it
holds: a read of the event that the page would start by itself while Edit mode is open SHALL NOT discard
the edits.

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
clip's file name and its position out of the number of clips the chapter plays (its ignored clips are not
counted). A clip SHALL NOT be movable into another
chapter: a dragged clip stops at its own chapter's edge. The page SHALL count as moved the fewest clips whose
moves explain the new order, so that moving one clip from position 1 to position 5 moves one clip, not five.
Each clip counted as moved SHALL show its position from when Edit mode opened.

Clips the event ignores are not part of the play order. Each chapter SHALL list them after its other clips,
marked as ignored, and they SHALL NOT be movable or counted in the chapter's positions. A missing clip SHALL
stay listed and movable, and SHALL never be dropped from its chapter. A NEW clip SHALL be movable like any
other.

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

### Requirement: The event page edits the event's metadata

In Edit mode the page SHALL offer the event's title, date, location and description as editable fields. The
fields SHALL be filled with what the event's `reel.yaml` itself says, not with the values the page resolves
from the folder name. A field that `reel.yaml` leaves unset SHALL be shown empty. When the page shows a value
for that field derived from the folder name, that value SHALL be shown next to the field as inherited from
the folder name. A field the operator empties, after `reel.yaml` had set it, SHALL say that it will inherit
from the folder name once saved, and SHALL NOT present the value `reel.yaml` set as the folder name's.

A field left empty, or holding only whitespace, SHALL be saved as unset, so that it inherits again. The date
SHALL be entered as a calendar date. A date the operator has not finished entering SHALL NOT be saved, as
unset or otherwise: the page SHALL say that the date is incomplete and SHALL NOT offer to save until it is
completed or cleared. Beyond that, the page SHALL leave the judgement of whether a date or title is usable,
for example a date in the future, to the service. When the service refuses one, the page SHALL show the
service's explanation at the date and title fields.

#### Scenario: Authored values fill the form
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose `reel.yaml` sets the title
  `Grillkväll med grannarna` and the date `2024-06-27`
- **THEN** the title field holds `Grillkväll med grannarna`, the date field holds `2024-06-27`, and the
  location and description fields are empty

#### Scenario: Inherited values are shown as inherited
- **WHEN** Edit mode opens on `2024-07-14 - kalas`, which has no `reel.yaml`
- **THEN** every field is empty, and the title and date fields show `Kalas` and `2024-07-14` as inherited from
  the folder name

#### Scenario: Clearing a field makes it inherit
- **WHEN** the operator empties the title field of `2024-06-27 - Grillning med grannar`
- **THEN** the field says it will inherit from the folder name, without naming `Grillkväll med grannarna` as
  the folder name's title; and after saving, `reel.yaml` sets no title and the page shows the folder name's
  title, `Grillning med Grannar`

#### Scenario: An unfinished date is never saved as unset
- **WHEN** the operator clears only the day of the date of `2024-06-21 - Midsommar - Dalarna`, leaving the
  date incomplete
- **THEN** the page says the date is incomplete and offers no Save, and `reel.yaml` still sets `2024-06-21`

#### Scenario: A future date is refused at the field
- **WHEN** the operator sets the date of `2024-06-21 - Midsommar - Dalarna` to a day after today and saves
- **THEN** the date and title fields show the service's explanation that the date is in the future, and
  `reel.yaml` is unchanged

### Requirement: Saving an edit writes only what the operator changed

Edits SHALL be saved only when the operator asks. While Edit mode holds changes that differ from what it
read, the page SHALL keep visible:

- which metadata fields changed
- how many clips moved, counted as the reorder requirement counts them
- when saving a new order would add NEW clips to `reel.yaml`, how many
- a **Reset** control, which restores what was read
- a **Save** control

An edit that is undone, such as a clip moved and moved back, SHALL leave no change to save.

Saving SHALL write the editorial document exactly as Edit mode read it, with only the operator's edits
applied:

- **Edited metadata fields** take their new values.
- **A chapter whose order changed** is written in the order shown, with its ignored clips left out and its
  missing and NEW clips kept in place.
- **Everything else** is written exactly as read: every other chapter, every per-clip property, the ignored
  clips and the look.

When `reel.yaml` names no chapters, either because the event has no `reel.yaml` or because its `reel.yaml`
sets none, one exception applies. A save that changes an order SHALL write every chapter as shown, each
without its ignored clips, and a save that changes only metadata SHALL still write no chapters.

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

### Requirement: A failed save keeps the operator's edits and says why

When a save fails, the page SHALL keep every unsaved edit and SHALL say why. It SHALL take the distinction
from the service's answer, not from its prose:

- **The event changed since Edit mode read it** (a conflict). The page SHALL say so and offer two choices:
  - "Reload latest", which discards the edits and reads the current state
  - "Overwrite with mine", which asks for confirmation, with cancelling as the choice focused first, and
    then saves the edits over the other change
- **The service refuses the date or title as unusable.** The explanation SHALL be shown at those fields.
  Any other refused state SHALL be shown with the service's detail.
- **The event no longer exists.** The page SHALL say so and offer the way back to the list.
- **The service could not read or save the event's files.** The page SHALL show the failure kind in the same
  words the list uses when the answer carries one, and the service's detail, and SHALL offer to retry.
- **The service does not answer.** The page SHALL say the service is not reachable and SHALL offer to retry.

#### Scenario: A conflicting edit made elsewhere
- **WHEN** the operator is editing `2024-06-27 - Grillning med grannar`, its `reel.yaml` title is changed by
  hand, and the operator then saves
- **THEN** the page says the event changed since it was read, the operator's edits are still shown, and
  `reel.yaml` still holds the hand-made title

#### Scenario: Overwriting after a conflict
- **WHEN** after that conflict the operator chooses "Overwrite with mine" and confirms
- **THEN** the operator's version is saved, and the page confirms the save

#### Scenario: Reloading after a conflict
- **WHEN** after that conflict the operator chooses "Reload latest"
- **THEN** the edits are discarded, and the page shows the hand-made title

#### Scenario: A read-only event folder
- **WHEN** the operator saves a reorder of `2024-09-01 - Sommarlov` while its folder cannot be written
- **THEN** the page says the save was refused, shows the service's detail naming the operating-system error,
  keeps the reorder, and offers Retry. Once the folder is writable again, Retry saves it.

#### Scenario: The service is down
- **WHEN** the operator saves a reorder of `2024-08-02 - Badutflykt - Varberg` while the service is not
  answering
- **THEN** the page says the service is not reachable, keeps the edits, and offers Retry

### Requirement: Unsaved edits are never discarded silently

While Edit mode holds unsaved changes, every way of leaving them SHALL ask first:

- **Closing or reloading the browser tab** SHALL trigger the browser's own leave-page confirmation.
- **Back, Forward, following a link, or typing another address in the app** SHALL keep the page and ask
  "Discard unsaved changes?". Its default choice keeps editing: choosing it, or pressing Escape, SHALL
  leave the page, its address and its edits as they were. Discarding SHALL continue to where the operator
  was going.
- **Refreshing the event and leaving Edit mode** SHALL ask the same question.

Reset, and "Reload latest" after a conflict, are themselves named discards and SHALL NOT ask. With no unsaved
changes, nothing SHALL ask.

#### Scenario: Back asks before discarding
- **WHEN** the operator has reordered clips on `2024-06-27 - Grillning med grannar` and presses the browser's
  Back
- **THEN** the event page stays, with its address and the reorder, and asks "Discard unsaved changes?"

#### Scenario: Keeping the edits
- **WHEN** the operator answers that question with Escape
- **THEN** the event page, its address and its edits are unchanged

#### Scenario: Discarding the edits
- **WHEN** the operator answers that question with Discard
- **THEN** the list is shown, and `reel.yaml` is unchanged

#### Scenario: Reloading the tab
- **WHEN** the operator reloads the browser tab with unsaved edits on `2024-06-27 - Grillning med grannar`
- **THEN** the browser asks for confirmation before leaving the page

#### Scenario: Refresh asks too
- **WHEN** the operator presses Refresh on the page of `2024-06-27 - Grillning med grannar` with unsaved edits
- **THEN** the page asks "Discard unsaved changes?" before reading the event again

#### Scenario: Nothing to lose, nothing asked
- **WHEN** the operator enters Edit mode on `2024-06-27 - Grillning med grannar`, changes nothing, and presses
  Back
- **THEN** the list is shown without a question

### Requirement: Events that need attention open a page that can fix their metadata

Every row of the list's "Needs attention" group SHALL link to its event's page. When the page's read of an
event fails with the unusable-metadata kind (no real date, no title, or a date in the future), the page SHALL
show that failure, as it does today, together with the metadata form. The form SHALL be filled from the
event's `reel.yaml`, or left empty when there is none. It SHALL save under the same rules as Edit mode, and
SHALL write no chapters the event's `reel.yaml` does not already hold. After a successful save, the page SHALL
read the event again and show it. The list SHALL be read again the next time it is shown. For every other
failure kind, the page SHALL show the failure only, since its detail states the fix.

#### Scenario: The impossible date is fixed from the page
- **WHEN** the operator follows the "Needs attention" row of `2024-02-30 - Omöjligt datum`, enters the date
  `2024-02-29` in the form shown with the failure, and saves
- **THEN** the page reads the event again and shows it with its clip and its title `Omöjligt Datum`. On
  returning, the list shows it among the 2024 events, and it is no longer under "Needs attention".

#### Scenario: A refused fix keeps the failure
- **WHEN** on the same page the operator enters a date after today and saves
- **THEN** the date and title fields show the service's explanation, and the failure is still shown

#### Scenario: Other failures offer no form
- **WHEN** an event's `reel.yaml` cannot be parsed, and the operator follows its "Needs attention" row
- **THEN** the page shows the unparseable-document failure and its detail, and no form
