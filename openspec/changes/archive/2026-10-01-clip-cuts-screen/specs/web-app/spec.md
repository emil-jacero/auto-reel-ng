## ADDED Requirements

### Requirement: Edit mode lists, adds and removes a clip's cuts

A clip's cuts are the spans of it that the movie leaves out. Each has a start and an end, in seconds from the
clip's start, and may have a reason. In Edit mode, every included or new clip (a clip on disk that a chapter
lists, or will list once the edits are saved) SHALL offer a **Cuts** control. The control SHALL say how many
cuts the clip has and, when it has any, how much time they cut out. Pressing it SHALL show or hide a panel
under the clip's row and SHALL leave keyboard focus on the control. The control SHALL say to assistive
technology whether the panel is shown, and SHALL name the clip as its row names it. In the keyboard order, the
Cuts control SHALL come after the row's other controls, and the panel's controls straight after it.

The panel SHALL list the clip's cuts in their order, each with its number in the list, its start and end, its
length and its reason in words. A clip without cuts SHALL say that the whole clip plays. A missing clip SHALL
show, in its row, how many cuts it has, and SHALL offer no Cuts control: its file is not on disk to cut, and
removing it from `reel.yaml` takes its cuts with it. Once the operator removes it, its row SHALL NOT show its
cuts any more, since the save drops them. An ignored clip SHALL have no cuts and no Cuts control.

**Times.** A cut's times are places in the clip, not moments in a day, so the format for moments ("Times are
written one way on every screen") does not apply to them. The page SHALL write a time as minutes and seconds
(`1:02.35`), with hours in front from one hour on (`1:01:15.5`). It SHALL write up to three decimals and no
trailing zero. It SHALL write a length under a minute in seconds (`1.5 s`), and from a minute on as a time. The time a clip's cuts cut out SHALL count, once,
every span that one or more of its cuts covers, as the render does.

**Adding a cut.** The panel SHALL take a start and an end, typed, and add the cut on request. Spaces around a
time SHALL be ignored. A time SHALL be accepted in each of these forms, with an optional decimal part of one
to three digits after `.` or `,`:

- seconds (`75.5`)
- minutes and seconds, the seconds as two digits below 60 (`1:15.5`)
- hours, minutes and seconds, the minutes and seconds each as two digits below 60 (`1:01:15.5`)

The cut SHALL be refused, and nothing added, when either time is empty or in no accepted form, or has more
than three decimals. It SHALL also be refused when its end is not after its start, or when it shares more
than an instant with another cut of the clip that is not removed. A refusal SHALL be shown at the field it
concerns, which SHALL receive keyboard focus. It SHALL be announced, and it SHALL say what to type, or which
cut the new one overlaps. A cut that only touches another, the end of one being the start of the other, SHALL
be accepted. Times SHALL be compared to the millisecond, as they are typed and written, so a cut that starts
where another is shown to end touches it.

An added cut SHALL take its place in the list by its start, after every cut that starts at the same time or
earlier. It SHALL be saved with the reason `manual`. After an addition:

- both fields SHALL be empty again, with keyboard focus on the start field
- the addition SHALL be announced with the cut's times, the clip's name and its new cut count

The page does not know a clip's length. The panel SHALL say that a cut that runs past the clip's end stops
there, and that a cut over the whole clip leaves the clip out of the movie.

**Removing a cut.** Each cut SHALL offer **Remove**, which names the clip and the cut. A cut read from
`reel.yaml` SHALL then stay listed in its place, marked as removed when the edits are saved, with an **Undo**
that puts it back. Keyboard focus SHALL move to that Undo, and after an Undo to the cut's Remove. An Undo that
would make the cut share more than an instant with a cut added in this Edit mode SHALL be refused, as adding
that cut would be: the cut stays removed, keyboard focus stays on its Undo, and the refusal is shown in the
cut's row, announced, and names the cut to remove first. Two cuts read from `reel.yaml` that overlap there
SHALL NOT refuse each other's Undo: an Undo only goes back to what was read. A cut added in this Edit mode SHALL simply be gone.
Keyboard focus SHALL then move to the Remove of the cut that took its place, or of the cut before it, or to
the start field when no cut is left. Each removal and each Undo SHALL be
announced. After any addition, removal or Undo, the control holding keyboard focus SHALL be fully visible,
not covered by the page header, the chapter's heading or the save bar.

**Typed but not added.** While a panel's fields hold a typed time that was not added, the event SHALL count as
having unsaved changes. The save bar SHALL say that a cut was typed but not added, naming the clip as its row
names it when only one clip holds one, also after an edit that changes that name. Save, and Overwrite with mine after a conflict, SHALL say that they are unavailable until
the cut is added or its fields are cleared. Hiding the panel SHALL keep what was typed, and so SHALL moving the
clip to another chapter. The Cuts control of each clip whose panel holds such a time SHALL say so in words, at
every width and to assistive technology, also while its panel is hidden, so that the clip holding Save back
is found on its row. Reset SHALL empty every panel's fields.

While a save is in flight, the panel's fields, Add cut, Remove and Undo SHALL say that they are unavailable
and change nothing when used. The Cuts control SHALL still show and hide its panel, since that changes nothing
to save.

The Cuts control and every control in the panel SHALL take a tap anywhere in an area of at least 44 × 44 CSS
pixels around it when the primary pointer is coarse, reaching no other control, as every button does ("Every
control is large enough to touch"). With every panel hidden, the Cuts control SHALL NOT make a row taller in a
window 320 or 390 pixels wide. No panel SHALL make the page scroll horizontally from 320 pixels up.

#### Scenario: Opening a clip's cuts
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator presses the Cuts control of
  `s1710001.mp4`
- **THEN** a panel under its row says that the whole clip plays and offers a start and an end field and Add
  cut. Keyboard focus is still on the Cuts control, which says that its panel is shown.

#### Scenario: Adding a cut with typed times
- **WHEN** in that panel the operator types `0` as the start and `1,5` as the end and presses Enter
- **THEN**
  - the panel lists one cut, from `0:00` to `0:01.5`, 1.5 s long, its reason "Cut by hand"
  - the Cuts control reads "1 cut · −1.5 s"
  - both fields are empty, with keyboard focus on the start field
  - the addition is announced
  - the save bar says that 1 cut was added

#### Scenario: Every accepted form of a time
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from ` 0:00:01.25 `
  to `0:02.5`, and then one from `4` to `0:06`
- **THEN** the panel lists the cuts from `0:01.25` to `0:02.5` and from `0:04` to `0:06`, in that order, and the
  Cuts control reads "2 cuts · −3.25 s"

#### Scenario: A time the page cannot read
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `1:5` as the start and
  `2` as the end and asks to add the cut, then types `-1` as the start, then `0.1234`
- **THEN** each is refused at the start field, which keeps keyboard focus. The first two are refused as no time
  the page can read, naming the three forms. The last is refused for its four decimals. No cut is added.

#### Scenario: A cut that does not end after it starts
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `3` as the start and
  `2` as the end and asks to add the cut
- **THEN** the cut is refused at the end field, which receives keyboard focus, saying that a cut must end after
  it starts, and no cut is added

#### Scenario: A cut that overlaps another
- **WHEN** `s1710001.mp4` of `2024-06-27 - Grillning med grannar` has a cut from `0:00` to `0:01.5`, and the
  operator adds one from `1` to `2`
- **THEN** it is refused, saying that it overlaps cut 1 (`0:00` to `0:01.5`)
- **WHEN** the operator then adds one from `1.5` to `2`
- **THEN** it is accepted and listed second

#### Scenario: Removing a cut read from reel.yaml, and undoing it
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds with the reason `black`, and in Edit mode the operator presses that cut's Remove
- **THEN** the cut stays listed, marked as removed when the edits are saved, with an Undo that has keyboard
  focus, and the save bar says that 1 cut is removed
- **WHEN** the operator presses that Undo
- **THEN** the cut is listed as before, its reason "Black frames", keyboard focus is on its Remove, and the page
  shows no unsaved changes

#### Scenario: An Undo that would overlap is refused
- **WHEN** with that same `reel.yaml`, the operator removes the cut from 0 to 1.2 seconds of `s1710003.mp4`, adds
  one from `1` to `2`, and presses the removed cut's Undo
- **THEN** the Undo is refused, saying that cut 1 overlaps cut 2 (`0:01` to `0:02`) and that cut 2 must be
  removed first. Cut 1 stays removed, keyboard focus stays on its Undo, and the save bar still says that 1 cut
  was added and 1 removed.

#### Scenario: Read cuts that overlap do not refuse each other's Undo
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` cuts from 0 to 3 seconds
  and from 2 to 4 seconds, and the operator removes both and presses each one's Undo
- **THEN** both are listed as before, and the page shows no unsaved changes

#### Scenario: A cut starts where another is shown to end
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 3.2033333
  seconds, listed as ending at `0:03.203`, and the operator adds one from `3.203` to `4`
- **THEN** it is accepted and listed second

#### Scenario: Removing a cut added in this Edit mode
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from `0` to `1.5`
  and presses its Remove
- **THEN** the panel says that the whole clip plays again, keyboard focus is on the start field, and the page
  shows no unsaved changes

#### Scenario: A missing clip's cuts are shown, not edited
- **WHEN** the `reel.yaml` of `2024-09-01 - Sommarlov` gives the missing `borttagen.mp4` a cut from 0 to 2
  seconds, and the operator opens Edit mode
- **THEN** the row of `borttagen.mp4` says that it has 1 cut and offers Remove but no Cuts control, while
  `s1710002.mp4` and `s1710004.mp4` offer theirs
- **WHEN** the operator presses Remove on `borttagen.mp4`
- **THEN** its row is listed as removed when the edits are saved and no longer says that it has a cut

#### Scenario: An ignored clip has no cuts
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the ignored `s1710004.mp4` offers no Cuts control, and every clip `Main` and `Kvällen` play offers one,
  the new `Kvällen/s1710004.mp4` included

#### Scenario: A cut typed but not added holds Save back
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `2` as the start, adds
  nothing, and hides the panel
- **THEN** the save bar says that a cut was typed on `s1710001.mp4` but not added, and Save says that it is
  unavailable. Opening the panel again shows `2` in the start field.
- **WHEN** the operator then presses the browser's Back
- **THEN** the page stays and asks "Discard unsaved changes?"

#### Scenario: A typed cut moves with its clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `2` as the start of a cut on
  `Kvällen/s1710002.mp4`, which `Kvällen` names `s1710002.mp4`, adds nothing, and moves that clip to `Main`
  with Move clips
- **THEN** the save bar now says that a cut was typed on `Kvällen/s1710002.mp4` but not added, Save says that
  it is unavailable, and the clip's Cuts panel, now in `Main`, is still shown with `2` in the start field

#### Scenario: Hidden panels holding typed text are marked on their rows
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator types `5` in the start field of `s1710002.mp4`
  and hides its panel, then types `1:00` in the start field of `s1710004.mp4` and hides that panel
- **THEN** the save bar says that cuts were typed on 2 clips but not added, and the Cuts controls of those two
  clips, and of no other, say "typed" and that a cut was typed but not added
- **WHEN** the operator clears the field of `s1710002.mp4`
- **THEN** its Cuts control no longer says so, and the save bar names `s1710004.mp4`

#### Scenario: Cut controls wait for a save
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its panel shown, the
  operator presses Save and the service has not answered yet
- **THEN** the start and end fields, Add cut and the cut's Remove say that they are unavailable, typing and
  pressing them change nothing, and the Cuts control still hides and shows the panel

#### Scenario: Cuts on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** each clip row is as tall as on the page before this change, and a tap anywhere in a 44 × 44 pixel area
  around the Cuts control of `Kvällen/s1710002.mp4` reaches that control and no other
- **WHEN** the operator opens that panel and adds a cut from `0` to `1`
- **THEN** the page does not scroll horizontally, and a tap anywhere in a 44 × 44 pixel area around each of the
  panel's fields, Add cut and the cut's Remove reaches that control and no other

### Requirement: The event page shows each clip's cuts

The event page SHALL show, beside the name of each clip that has cuts in `reel.yaml`, how many cuts it has and
how much time they cut out ("2 cuts · −4.5 s"), counted as Edit mode counts them. On request, the page SHALL
show the clip's cuts there, as Edit mode lists them, without any control that changes them. A clip without
cuts SHALL show nothing more than before. The indicator SHALL be operable from the keyboard. It SHALL say to
assistive technology whether the list is shown, and it SHALL be read as the number of cuts and the time cut
out, not as a minus sign. When the primary pointer is coarse, it SHALL take a tap anywhere in an area of at
least 44 × 44 CSS pixels around it, reaching no other control. No shown list SHALL make the page scroll
horizontally from 320 pixels up, whatever the length of its times.

The page SHALL read the cuts from the service each time it reads the event, after the event read, and SHALL
keep showing the cuts it read last until the new read answers. That read SHALL NOT write anything, as no read
does ("Reading a screen never changes state"). When it fails, the page SHALL show the event's clips without
cuts, with a note that says the cuts could not be read and why. The note is part of the page's content, not an
alert.

#### Scenario: A clip's cuts on the event page
- **WHEN** the operator has saved a cut from `0` to `1.5` on `s1710001.mp4` of
  `2024-06-27 - Grillning med grannar`
- **THEN** the event page shows "1 cut · −1.5 s" beside `s1710001.mp4` and nothing beside its other clips
- **WHEN** the operator activates that indicator from the keyboard
- **THEN** it says that its list is shown, and lists the cut from `0:00` to `0:01.5`, 1.5 s long, "Cut by hand",
  with no control to change it

#### Scenario: The cuts cannot be read
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` and the service does not answer the read of
  its cuts
- **THEN** the page shows its chapters and clips, with a note that the cuts could not be read because the
  service is not reachable, and nothing is announced as an alert

#### Scenario: Reading cuts changes nothing
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, opens a clip's cut list, refreshes the page
  and goes back to the list
- **THEN** every request the client made was a read, and no file under the library changed

## MODIFIED Requirements

### Requirement: Saving an edit writes only what the operator changed

Edits SHALL be saved only when the operator asks. While Edit mode holds changes that differ from what it
read, the page SHALL keep visible:

- which metadata fields changed
- how many clips moved, counted as the reorder requirement counts them
- how many missing clips will be removed from `reel.yaml`
- how many chapters were added, renamed and deleted, and whether the chapters' order changed
- how many cuts were added and how many removed
- when saving would add NEW clips to `reel.yaml`, how many
- a **Reset** control, which restores what was read
- a **Save** control

An edit that is undone SHALL leave no change to save: a clip moved and moved back, within its chapter or to
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
- **Everything else** is written exactly as read: every other chapter, every other per-clip property, the
  ignored clips and the look.

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
