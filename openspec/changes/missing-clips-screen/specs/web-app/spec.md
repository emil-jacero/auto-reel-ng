## ADDED Requirements

### Requirement: Edit mode removes a missing clip from reel.yaml on request

In Edit mode, every clip that `reel.yaml` lists but that is missing from disk SHALL offer a control that
removes it from `reel.yaml`. The control SHALL say that it removes the clip, SHALL name the clip's file to
assistive technology, and SHALL be reachable with the keyboard. No other clip SHALL offer one: a clip that is
on disk (included, NEW or ignored) is never removed this way, and nothing else in the client removes a clip
from `reel.yaml`.

Removing a clip SHALL:

- take it out of its chapter's play order, so that the chapter's remaining clips are numbered, and their
  positions announced, without it
- list it under its chapter, after the clips the chapter plays, as removed from `reel.yaml` when the edits
  are saved. The listing keeps its file name and its status in words, and offers an **Undo** control that
  names the clip's file to assistive technology.
- move keyboard focus to that Undo control, and announce that the clip will be removed from `reel.yaml` when
  the edits are saved

Undo SHALL return the clip to its chapter's play order, right after as many clips as came before it when Edit
mode opened and are still in the chapter's play order. With no other edit to the chapter, that is the position
it had. So removals undone in any order, with no move between them, leave the chapter's order as read. Undo
SHALL then move keyboard focus to the clip's remove control, and announce the clip's position out of the
number of clips the chapter plays.

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

## MODIFIED Requirements

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
clip's file name and its position out of the number of clips the chapter plays (its ignored clips, and the
missing clips the operator removed, are not counted). A clip SHALL NOT be movable into another chapter: a
dragged clip stops at its own chapter's edge. The page SHALL count as moved the fewest clips whose
moves explain the new order, so that moving one clip from position 1 to position 5 moves one clip, not five.
Each clip counted as moved SHALL show its position from when Edit mode opened.

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
- when saving a new order would add NEW clips to `reel.yaml`, how many
- a **Reset** control, which restores what was read
- a **Save** control

An edit that is undone, such as a clip moved and moved back or a removal undone, SHALL leave no change to
save.

Saving SHALL write the editorial document exactly as Edit mode read it, with only the operator's edits
applied:

- **Edited metadata fields** take their new values.
- **A chapter whose order changed, or from which the operator removed a missing clip,** is written in the
  order shown, with its ignored clips and its removed clips left out, and its other missing clips and its NEW
  clips kept in place.
- **A removed clip's own per-clip properties** (its trims, title-clip choice, rotation and exclusion) are
  left out with it, since `reel.yaml` no longer lists the clip.
- **Everything else** is written exactly as read: every other chapter, every other per-clip property, the
  ignored clips and the look.

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

### Requirement: An event's page schedules its render

An event's page SHALL offer, as explicit controls that name what they do:

- a **Render** control when the event needs a render, has no queued or running job, lists no clip that is
  missing from disk, and the page is not in Edit mode
- when the event is up to date, has no queued or running job, lists no clip that is missing from disk, and
  the page is not in Edit mode: its up-to-date state plus a secondary **Render anyway** control, which asks
  for confirmation before it forces a render

While the page is in Edit mode, it SHALL offer neither control and SHALL instead say that the edits must be
saved, or Edit mode left, before rendering: a render reads the saved `reel.yaml`, not the unsaved edits. A
queued or running job's progress and its Cancel control stay offered in Edit mode.

While the event lists a clip that `reel.yaml` names but that is missing from disk, and the page is not in
Edit mode, the page SHALL offer neither control, because a render fails on a missing clip that it plays.
This holds for every missing clip, including one that `reel.yaml` excludes and that a render would skip,
since the page's read does not say which missing clips are excluded. The page SHALL instead say, in words,
that the clip is missing from disk and that it must be restored, or removed in Edit mode, before rendering.
For one missing clip the words SHALL name it; for several they SHALL give their number. A queued or running
job's progress and its Cancel control stay offered.

Pressing a control SHALL send one enqueue request, and SHALL NOT send another while that one is
unanswered. Until the answer arrives, the pressed control SHALL stay in place, keep keyboard focus, be
marked busy, and ignore further presses. The page SHALL handle every answer the service publishes:

- **job created:** the page follows the new job
- **up to date, not enqueued:** the page says there is nothing to render, and offers Render anyway
- **a job is already active for the event:** the page follows that job, not an error
- **another event claims the same movie file:** the page names each other event, with a link to its page,
  and says the fix: a distinct title or location in `reel.yaml`
- **unknown event:** the page says the event no longer exists
- **the project could not be scanned** (so the service could not check for another claimant): the page
  says so, with the service's detail, and that nothing was queued
- **any other answer, or none:** the page says the render was not queued, with the status it received or
  that the service is not reachable. It MUST NOT name a cause the answer does not carry; a server error
  without a problem body is not reported as a database failure.

The page MUST tell these outcomes apart by the published status and conflict kind, not by the problem's
prose. Only an event page that shows the event's render state offers these controls; a page whose read
failed offers none.

#### Scenario: A stale event is rendered
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, which needs a render, and presses Render
- **THEN** one job is enqueued for it, and the page shows that job as queued

#### Scenario: An up-to-date event is rendered only on purpose
- **WHEN** the operator opens `2024-06-21 - Midsommar - Dalarna`, which is up to date
- **THEN** the page shows it as up to date and offers Render anyway, and a render is enqueued only after
  the operator confirms it

#### Scenario: The event became fresh since the page was read
- **WHEN** the page of `2024/Blandat` showed it as needing a render, a job queued elsewhere then rendered
  it while the page had no live connection, and the operator presses Render
- **THEN** no job is enqueued, the page says there is nothing to render and offers Render anyway, and it
  re-reads to show the event as up to date

#### Scenario: A job is already active
- **WHEN** a job for `2024-08-02 - Badutflykt - Varberg` was enqueued elsewhere after the page was read,
  before the page learned of it, and the operator presses Render
- **THEN** the page shows that existing job's state, with no error and no second job

#### Scenario: Two events claim the same movie file
- **WHEN** the operator presses Render on `2024-07-14 - kalas`
- **THEN** no job is enqueued, and the page names `2024-07-14 - Kalas` as the other claimant, links to it,
  and says to give one of them a distinct title or location in `reel.yaml`

#### Scenario: A double click enqueues once
- **WHEN** the operator double-clicks Render on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** one enqueue request is sent

#### Scenario: Render keeps focus while it waits
- **WHEN** the operator presses Enter on Render on `2024-08-20 - Två kapitel - Tjörn`, and the service takes
  two seconds to answer
- **THEN** during those seconds focus stays on Render, which is marked busy, and pressing Enter again sends
  nothing

#### Scenario: Edit mode holds Render back
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, which needs a render, and enters Edit mode
- **THEN** the page offers no Render control and says to save or leave Edit mode to render, and once Edit
  mode ends, Render is offered again

#### Scenario: An unreadable event offers no Render
- **WHEN** the operator opens the page of `2024-02-30 - Omöjligt datum`, whose read fails
- **THEN** the page shows the failure and offers no Render control

#### Scenario: A missing clip holds Render back
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, which needs a render and whose `reel.yaml` lists the
  missing `borttagen.mp4`
- **THEN** the page offers neither Render nor Render anyway, and says that `borttagen.mp4` is missing from
  disk and to restore it, or remove it in Edit mode

#### Scenario: Several missing clips are counted
- **WHEN** the operator opens `2024-09-02 - Två saknade`, whose `reel.yaml` lists two missing clips
- **THEN** the page offers no Render, and says that 2 clips are missing from disk and to restore them, or
  remove them in Edit mode

#### Scenario: An excluded missing clip still holds Render back
- **WHEN** the operator opens `2024-09-03 - Utesluten`, whose `reel.yaml` lists the missing `borta.mp4` and
  excludes it
- **THEN** the page offers neither Render nor Render anyway, and says that `borta.mp4` is missing from disk
  and to restore it, or remove it in Edit mode

#### Scenario: Edit mode's reason takes the place of the missing clip's
- **WHEN** the operator enters Edit mode on `2024-09-01 - Sommarlov`
- **THEN** the page says to save or leave Edit mode to render, and once Edit mode ends with nothing saved, it
  says again that `borttagen.mp4` is missing from disk

#### Scenario: A job queued for such an event can still be cancelled
- **WHEN** a job for `2024-09-02 - Två saknade` was queued before its page was opened, and no worker is
  running
- **THEN** the page shows the job waiting for a worker, with its Cancel control, says that clips are missing
  from disk, and offers no Render

### Requirement: The event list shows live job state and offers a render

Each event row the list shows with its render state SHALL show that event's job as the progress
requirement describes. The job the connection carries SHALL be matched to the row whose event id equals the
job's event directory. A row that needs a render, has no queued or running job, and lists no clip that is
missing from disk SHALL offer a compact **Render** control, whose accessible name names the event ("Render"
followed by the event's folder name), so that a list of Render controls is told apart by assistive
technology. At phone width, the row's job state keeps its "Last job" label whenever the row shows a job,
including one the connection reported after the list was read, and a row that shows no job has no such
label. The row's Render control, once
pressed, behaves as the page's: one request, focus kept, marked busy. Its answers are handled as on the
event's page, except as follows:

- when the event is up to date, a notification says so and links to the event's page. The list does not
  force a render.
- when another event claims the same movie file, an error notification names the other events and links to
  the pressed event's page.

A row that needs a render, has no queued or running job, but lists a clip that is missing from disk SHALL
NOT offer Render, for the same reason as the event's page. In its place, the row SHALL say, in words with an
icon, that missing clips block its render. The row's count of missing clips stays shown.

Error rows under "Needs attention" SHALL NOT offer Render.

#### Scenario: A row shows a queued job live
- **WHEN** a job is enqueued for `2024-08-02 - Badutflykt - Varberg` from its page, and the operator returns
  to the list
- **THEN** its row shows the job queued, and its progress once a worker runs it, with no refresh

#### Scenario: A stale row is rendered from the list
- **WHEN** the operator presses Render on the `2024-08-20 - Två kapitel - Tjörn` row
- **THEN** a job is enqueued for that event, and the row shows it queued

#### Scenario: Fresh rows and error rows offer no Render
- **WHEN** the list shows `2023-06-23 - Midsommar - Dalarna`, which is up to date, and the `2024-02-30 -
  Omöjligt datum` error row
- **THEN** neither offers Render

#### Scenario: Live rows fit a phone-width window
- **WHEN** the list is shown 390 pixels wide, the `2024-08-20 - Två kapitel - Tjörn` row shows a job
  enqueued after the list was read, and the `2024-06-27 - Grillning med grannar` row offers Render
- **THEN** the page does not scroll horizontally, the Två kapitel job is labelled "Last job", and the
  Grillning control is announced as "Render 2024-06-27 - Grillning med grannar"

#### Scenario: A row with a missing clip offers no Render
- **WHEN** the list shows `2024-09-01 - Sommarlov`, which needs a render and lists one missing clip
- **THEN** its row shows 1 missing clip and its verdict, offers no Render, and says that missing clips block
  its render

#### Scenario: A missing-clip row fits a phone-width window
- **WHEN** the list is shown 390 pixels wide
- **THEN** the page does not scroll horizontally, and the `2024-09-01 - Sommarlov` row still shows its missing
  clip count and the words that missing clips block its render
