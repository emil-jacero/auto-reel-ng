## MODIFIED Requirements

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
there they still count as listed by that chapter. Either way they SHALL NOT be moved within a list or counted in the chapter's positions; the one thing that moves an ignored clip is including it, by dragging it from the bin to the video track, or by the row's Include button, which includes it at the end of its chapter ("Clips are included and ignored by dragging between bin and track"). A missing clip SHALL
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
  move controls in the list, only a grip to drag it onto the video track and an Include button that
  includes it at the end of `Main`

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
- **THEN** `Main` lists only `s1710001.mp4`, `Kvällen` follows it directly, and after `Kvällen` and before Add chapter the bin lists, under "Ignored clips" and "Main · 1 ignored clip, not played", `s1710004.mp4` marked as ignored, with no move controls, only the grip and the Include button; in a 900 px wide window `Main` lists `s1710001.mp4` and then `s1710004.mp4`, and there is no "Ignored clips" heading

### Requirement: Saving an edit writes only what the operator changed

Edits SHALL be saved only when the operator asks. While Edit mode holds changes that differ from what it
read, the page SHALL keep visible:

- which metadata fields changed
- how many clips moved, counted as the reorder requirement counts them
- how many clips were ignored and how many included
- how many missing clips will be removed from `reel.yaml`
- how many chapters were added, renamed and deleted, and whether the chapters' order changed
- how many cuts were added and how many removed
- when saving would add NEW clips to `reel.yaml`, how many
- a **Reset** control, which restores what was read
- a **Save** control

An edit that is undone SHALL leave no change to save: a clip ignored and included again (or the reverse), a clip moved and moved back, within its chapter or to
another chapter and back, a removal undone, a chapter renamed back or moved back, a deleted chapter restored,
a chapter added and deleted again, a cut added and removed again, a removed cut restored, or a removed cut
added again with the same times and reason. The cut counts SHALL count only the clips whose saved cuts would
change.

Saving SHALL write the editorial document exactly as Edit mode read it, with only the operator's edits
applied:

- **Edited metadata fields** take their new values.
- **A chapter whose order changed** is written in the order shown, with its ignored clips and its removed
  clips left out, and its other missing clips and its NEW clips kept in place. A chapter's order changes when
  it is reordered, when a missing clip is removed from it, and when a clip is moved into it or out of it.
- **A removed clip's own per-clip properties** (its trims, title-clip choice, rotation and exclusion) are left
  out with it, since `reel.yaml` no longer lists the clip.
- **A clip moved to another chapter keeps its per-clip properties.**
- **A clip whose cuts changed** gets the cuts its panel lists, in that order, without the removed ones. Its
  title-clip choice, rotation and exclusion stay as read. When it is then left with no cut and none of those
  set, its entry is left out of the per-clip properties rather than written empty.
- **A chapter that plays a NEW clip whose cuts changed** is written as a chapter whose order changed, because
  `reel.yaml` can hold a clip's cuts only while a chapter lists the clip.
- **A clip the operator ignored or included** (the draft's ignore/include edit) is added to or removed from the
  document's `ignore`; the other ignored clips stay as read.
- **Everything else** is written exactly as read: every other chapter, every other per-clip property and the look.

Two kinds of save SHALL instead write every chapter the page lists, in the order the chapters are shown and
under its current name. Each chapter's clips are written in the order shown, without its ignored and removed
clips, and with its missing and NEW clips in place. A deleted chapter is left out.

- **A save that changes the chapters themselves**: a chapter added, renamed or deleted, or the chapters'
  order changed. Every NEW clip then joins `reel.yaml` in the chapter where the page shows it. So after the
  save, the page shows each clip where it showed it before, and a chapter's name only decides where clips
  added to its folder later go.
- **A save that changes any order, any chapter or any cut when `reel.yaml` names no chapters**, either because
  the event has no `reel.yaml` or because its `reel.yaml` sets none.

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

#### Scenario: A cut writes only its clip's cuts
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a cut from `0` to `1.5` to `s1710001.mp4`
  and saves
- **THEN** `reel.yaml` gives `s1710001.mp4` one cut, from 0 to 1.5 seconds with the reason `manual`. It holds
  no other per-clip properties than before, its chapters list the same clips in the same order, and its
  metadata is unchanged. The page then shows "1 cut · −1.5 s" beside `s1710001.mp4`.

#### Scenario: A cut on a new clip adds the clip to reel.yaml
- **WHEN** on `2024-08-02 - Badutflykt - Varberg`, whose `reel.yaml` lists two of its three clips, the operator
  adds a cut from `4` to `6` to the NEW `s1710004.mp4`
- **THEN** before saving, the save bar says that 1 cut was added and that saving adds 1 new clip to `reel.yaml`
- **WHEN** the operator saves
- **THEN** `reel.yaml` lists `s1710001.mp4`, `s1710003.mp4` and `s1710004.mp4` and gives `s1710004.mp4` that cut,
  and the page shows `s1710004.mp4` as included, no longer new

#### Scenario: A clip left without cuts leaves no empty entry
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds and nothing else, and the operator removes that cut and saves
- **THEN** `reel.yaml` holds no entry for `s1710003.mp4` among its per-clip properties, and its chapters are
  unchanged

#### Scenario: A cut on a clip of a document without chapters
- **WHEN** the operator adds a cut from `1` to `2` to `s1710003.mp4` of `2024/Blandat`, whose `reel.yaml` names
  no chapters, and saves
- **THEN** `reel.yaml` lists the default chapter with `s1710003.mp4` and gives it that cut

#### Scenario: Undone cut edits leave nothing to save
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a cut to `s1710001.mp4` and removes it
  again
- **THEN** the page shows no unsaved changes, and offers no Save

#### Scenario: An ignored clip is saved
- **WHEN** in Edit mode the operator ignores `s1710001.mp4` and saves
- **THEN** the written `ignore` lists it, and nothing else in the document changed

#### Scenario: A marked group is not dropped on the video track
- **WHEN** two or more clips are marked and the operator drags one of them from the bin and releases it over the video track
- **THEN** nothing moves, the marks stay, and the live region says a group cannot be dropped on the video track
