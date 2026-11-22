## ADDED Requirements

### Requirement: The clip bin lists every clip of the event as one plain list

In Edit mode the bin SHALL list, between its player and its information, every clip of the event in one list: the
clips the chapters list, in play order, then the clips the event ignores, then the missing clips removed until Save,
the last two groups under a caption with their count. A row SHALL show the clip's frame, name, chapter and position
(or status), kept length and status icon, and hold no control. The bin SHALL have no chapter section, handle, mark or
move button.

#### Scenario: Tjörn as one list
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the bin lists, in this order:
  - `s1710001.mp4`, "Main · 1 of 1"
  - `s1710002.mp4`, `s1710003.mp4` and the new `s1710004.mp4`, "Kvällen · 1 of 3" to "Kvällen · 3 of 3", the last
    with the New status
  - under "Ignored · 1 clip, not played", the ignored root clip `s1710004.mp4`
- **AND** no row holds a button, a checkbox or a handle, and the bin has no chapter heading and no Add chapter

#### Scenario: A missing clip keeps its place, and a removed one moves to the end
- **WHEN** Edit mode opens on `2024-09-01 - Sommarlov`, whose `reel.yaml` lists the missing `borttagen.mp4` last
- **THEN** its row is third, "Clips · 3 of 3", with the Missing status and an empty frame
- **WHEN** the operator removes it from `reel.yaml` in its Clip tab
- **THEN** its row is listed last, under "Removed from reel.yaml when you save · 1 clip"

#### Scenario: A moved clip says where it was
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator drags `s1710004.mp4` on the track to before
  `s1710001.mp4`
- **THEN** the bin lists `s1710004.mp4` first, its row reading "Main · 1 of 4 · was 4", and no other row says that
  it moved

#### Scenario: Rows in view
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` with a fine pointer, first in a 1280×720 window with
  the player and the information hidden, then in a 1440×900 window with both shown
- **THEN** the first shows all 5 rows whole without scrolling, and the second at least 1

#### Scenario: 400 clips
- **WHEN** the event has 400 clips
- **THEN** the bin's list scrolls on its own, the player and the information stay in place, and the rest of the
  workspace does not move

### Requirement: The bin's list selects clips as the track does and opens their menu

The bin's list SHALL be one keyboard stop. Up, Down, Home and End move focus between rows; Enter (and Space reached by
keyboard) selects the focused clip alone, Ctrl/Cmd+Enter adds or takes it out, Shift+Enter selects a range. A press
on a row SHALL select as a press on a clip block does. A right-click, Shift+F10 or the Menu
key on a row SHALL open the clip's menu. Only the row of an on-disk clip the track does not draw SHALL start a drag,
which includes it on the track.

#### Scenario: Keyboard only
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator tabs into the bin's list, presses Down twice and Enter,
  then Down and Ctrl+Enter, then Shift+F10
- **THEN** after Enter `s1710003.mp4` is selected, the track has scrolled to it, and focus is on its row; after
  Ctrl+Enter `s1710003.mp4` and `s1710004.mp4` are selected; and the menu headed "2 clips" is open

#### Scenario: Shift+click in the list
- **WHEN** the operator presses the row of `s1710001.mp4` and Shift+presses the row of `s1710003.mp4`
- **THEN** the three clips are selected and outlined on the track, and "3 clips selected." is announced once

#### Scenario: Space after a click plays
- **WHEN** the operator clicks the row of `s1710002.mp4` and presses Space
- **THEN** the clip is selected and the Timeline plays, as "Space presses a control reached by keyboard and plays
  after a click" says

#### Scenario: Only an ignored row drags
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator presses the row of `s1710001.mp4` and moves the pointer
  40 px onto the track, and then does the same with the ignored root clip `s1710004.mp4`
- **THEN** the first press drags nothing and only selects; the second drags `s1710004.mp4`, and releasing it on the
  track includes it there

### Requirement: The bin shows what the page knows of the shown clip

Under its list the bin SHALL show the player's shown clip's information: name, status, chapter and position, size,
modification time, length and kept length; from a ready proxy's facts its frame rate (and whether it varies), its
picture's orientation and aspect ratio, its container's rotation and its audio codec; and its cuts, read only. It
SHALL request nothing, SHALL NOT state what the page does not know, and SHALL be hidden and shown as the player is.

#### Scenario: A clip with a ready proxy
- **WHEN** `s1710002.mp4` of `2024-06-27 - Grillning med grannar` (24.9 MiB, 25 fps, 1920×1080 with AAC sound, its
  proxy ready, one cut from 1.0 to 2.5 s) is selected
- **THEN** the information reads its name, "Included", "Clips · 2 of 4", "24.9 MiB", its modification time in the
  page's time format, "Length 0:06.02", "Kept length 0:04.52", "25 fps", "Landscape, 16:9", "Sound AAC", and the
  cut "Cut 1 0:01 to 0:02.5 · 1.5 s · Cut by hand"

#### Scenario: An excluded or ignored clip's cuts do not apply
- **WHEN** an excluded clip, or an ignored one, that `reel.yaml` gives a cut is selected
- **THEN** the information gives its length, no kept length and no cut, and says that its cuts are not applied

#### Scenario: A phone clip turned by its container
- **WHEN** a selected clip's proxy facts give a picture 540 × 960 and a rotation of 90
- **THEN** the information reads "Portrait, 9:16" and "Turned 90° by its container"

#### Scenario: No proxy yet
- **WHEN** a selected clip has no ready proxy and the event detail gives it no duration
- **THEN** the information gives no frame rate, picture or sound and no length, says that they are known once its
  proxy is prepared, and shows nothing as zero

#### Scenario: A missing clip
- **WHEN** the missing `borttagen.mp4` of `2024-09-01 - Sommarlov` is selected
- **THEN** the information reads "Missing from disk", "Clips · 3 of 3", its cuts as `reel.yaml` lists them, and no
  size, time or length

#### Scenario: Nothing is requested
- **WHEN** the operator selects ten clips one after the other
- **THEN** the only requests made for them are their thumbnails

#### Scenario: Hidden information is remembered
- **WHEN** the operator presses Hide information, leaves Edit mode and enters it again
- **THEN** the information is collapsed to its heading and a Show information button, and the list has its room

### Requirement: Edit mode opens on the event's editorial document and keeps the operator's edits

Edit mode SHALL read the event's editorial document on entry, keep the page's address, and keep keyboard focus on the
control that entered it. A failed read SHALL be said in the words of a failed event read, with no editing offered.
Only the operator's own actions SHALL end Edit mode or change what it holds: a read the page starts by itself SHALL
NOT discard edits. Leaving SHALL read the event again and move keyboard focus to the page's heading.

#### Scenario: The editorial document cannot be read
- **WHEN** the operator enters Edit mode on an event whose `reel.yaml` became unparseable after the page was
  read
- **THEN** the page shows the unparseable-document failure in words, with the service's detail, and offers
  no editing

#### Scenario: A read the page starts keeps the edits
- **WHEN** in Edit mode with a clip moved, a proxy job ends and the page reads the event again
- **THEN** the clip is still moved, the top bar still says "1 clip moved", and Edit mode is still open

### Requirement: Edit mode moves clips on the track and in the Clip tab, and counts the fewest moves

A clip SHALL move by a drag on the track, Alt and an arrow, the Clip tab's Move earlier, Move later and Move to…, or
its menu; each move SHALL be announced with the clip's name and position out of the clips its chapter plays. The top
bar SHALL count as moved the fewest clips whose moves explain the new order, each saying in its row where it was. An
ignored clip SHALL move only by being included, and a missing one SHALL stay in its chapter.

#### Scenario: Moving a clip to the front by keyboard
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator selects `s1710004.mp4` in the bin and presses Move
  earlier three times
- **THEN** the chapter plays `s1710004.mp4`, `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4`, each press was
  announced with the new position, and the top bar says "1 clip moved"

#### Scenario: A missing clip stays in its chapter
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator selects the missing
  `borttagen.mp4`, last in `Main`
- **THEN** its Clip tab offers Move earlier, and Move later says that a missing clip stays in its chapter and moves
  nothing

#### Scenario: An ignored clip is not moved
- **WHEN** the ignored root clip `s1710004.mp4` of `2024-08-20 - Två kapitel - Tjörn` is selected
- **THEN** its Clip tab offers Include clip and no Move earlier, Move later or Move to…

#### Scenario: A large chapter is fully editable
- **WHEN** an event holds 400 clips in one chapter
- **THEN** all 400 are listed in the bin, and any of them can be moved to any position in the chapter, by a drag on
  the track or step by step in the Clip tab


## MODIFIED Requirements

### Requirement: Edit mode removes a missing clip from reel.yaml on request

In Edit mode, every clip that `reel.yaml` lists but that is missing from disk SHALL offer **Remove from
reel.yaml**, in its Clip tab and in its menu. The control SHALL say that it removes the clip, SHALL name the clip
to assistive technology by the clip's name, as the event page's table names it, and SHALL be reachable with the
keyboard. No other clip SHALL offer one: a clip that is on disk (included, NEW or ignored) is never removed this
way, and nothing else in the client removes a clip from `reel.yaml`.

Removing a clip SHALL:

- take it out of its chapter's play order, so that the chapter's remaining clips are numbered, and their
  positions announced, without it
- list it in the bin after the ignored clips, under "Removed from reel.yaml when you save", until the edits are
  saved. The row keeps the clip's name, as the event page's table names it, and its status in words (with a fine
  pointer, as the status icon with its words kept as hidden text and tooltip, see "State is never shown by color
  alone"). Its Clip tab and its menu offer an **Undo** control that names the clip that way to assistive
  technology.
- move keyboard focus to that Undo control when Remove was pressed in the Clip tab (from the menu, focus goes back
  to the clip's row), and announce that the clip will be removed from `reel.yaml` when the edits are saved

Undo SHALL return the clip to its chapter's play order, right after whichever of the clips that came before it
when Edit mode opened comes last in the chapter's play order now, or first when none of them is still in the
play order. With no other edit to the chapter, that is the position it had. So removals undone in any order,
with no move between them, leave the chapter's order as read, and however the chapter was reordered meanwhile,
each clip still in the play order that came before it when Edit mode opened comes before it again. Undo in the
Clip tab SHALL then move keyboard focus to the clip's Remove from reel.yaml, and Undo SHALL announce the clip's
position out of the number of clips the chapter plays.

A removal SHALL count as an unsaved change, like a move. The save bar says how many missing clips will be
removed, Reset returns every removed clip to its place, and leaving with a removal unsaved asks first, as
for any unsaved edit. While a save is in flight, the remove and Undo controls SHALL accept no presses.

Saving SHALL write `reel.yaml` without each removed clip, as "Saving an edit writes only what the operator
changed" states, and SHALL NOT create, change or delete any other file. After a successful save, the page
SHALL show the event without the removed clips and SHALL no longer report them as missing.

#### Scenario: Removing the missing clip of Sommarlov
- **WHEN** in Edit mode on `2024-09-01 - Sommarlov`, the operator selects `borttagen.mp4` in the bin and presses
  Remove from reel.yaml in its Clip tab
- **THEN** the chapter plays `s1710002.mp4` and `s1710004.mp4`, numbered 1 and 2; `borttagen.mp4` is listed in
  the bin under "Removed from reel.yaml when you save", still marked as missing; its Clip tab offers Undo, which
  has keyboard focus; and the page says that 1 missing clip will be removed

#### Scenario: Undo puts the clip back
- **WHEN** after removing `borttagen.mp4`, the operator activates its Undo control
- **THEN** `borttagen.mp4` is at position 3 again, keyboard focus is on its Remove from reel.yaml, and the page
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
- **THEN** no clip's Clip tab or menu offers Remove from reel.yaml

#### Scenario: A pending removal is an unsaved edit
- **WHEN** the operator removes `borttagen.mp4` on `2024-09-01 - Sommarlov` and presses the browser's Back
- **THEN** the event page stays, with the removal, and asks "Discard unsaved changes?"

### Requirement: Every clip row shows a frame from its clip

On an event's page, every clip row SHALL show a thumbnail of the clip beside its facts, after its position
number and ahead of its file name in the row's reading order. This applies to the chapter tables, to their
card layout in a narrow window, and to the rows of Edit mode's clip bin. The
thumbnail SHALL be the image the service returns for that clip from
`GET /api/v1/events/{event_id}/thumbnail?clip=<identity>`. The event id and the clip's full identity SHALL
be sent exactly as the event detail gives them, including a chapter folder and non-ASCII letters. The
request SHALL also carry the clip's modification time, exactly as the event detail gives it, as the `v`
parameter, so that a clip replaced on disk gets a new address. The client SHALL NOT choose, crop or compute
the frame itself.

The thumbnail SHALL be shown in a box of fixed 16:9 proportions, of the same size in every row. In the
chapter tables, the box SHALL be 128 × 72 CSS pixels where the chapter's panel is at least 1024 CSS
pixels wide, as in a window 1280 pixels wide, and 80 × 45 in narrower tables and in their card layout. The
whole image SHALL be visible inside the box, never cropped or stretched. A clip displayed in portrait, such
as a phone clip whose container rotates it, SHALL appear as a player shows it, whole, with empty bands at
its sides.

Each thumbnail image SHALL have the text alternative "Frame from <name>", where <name> is the clip's name as
its row shows it. The image itself SHALL NOT be focusable. In the event page's read view the thumbnail of a clip
whose file is on disk carries a play control laid over it ("The event page watches a clip on request"), which
is the only focusable thing in the thumbnail's cell and leaves the image, its text alternative, its box, its
size and its place as they are. In Edit mode no thumbnail SHALL be focusable: the bin's row is the keyboard's stop
("The bin's list selects clips as the track does and opens their menu"). A pointer press on the thumbnail of a clip
on disk SHALL watch it in the bin's player ("Edit mode previews a clip on request"). No thumbnail SHALL start a drag
of its own, and a thumbnail moves with its row.

A MISSING clip SHALL NOT request a thumbnail. Its row SHALL show an empty placeholder box of the same size,
and its status says why the box is empty. An IGNORED clip's thumbnail SHALL be dimmed, like the rest of its
row.

#### Scenario: Each clip of an event shows its frame
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`
- **THEN** each of its four clip rows shows an image whose text alternative is "Frame from <its file name>",
  with one thumbnail request per clip carrying that clip's identity, and as `v` that clip's modification time
  exactly as the event detail gives it

#### Scenario: Frames are larger in a wide window
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide, and again in
  a window 390 pixels wide
- **THEN** every thumbnail box is 128 × 72 CSS pixels in the first and 80 × 45 in the second, each shows its
  whole frame, and no row changes its size or position as the images arrive

#### Scenario: A frame is named as its row names the clip
- **WHEN** `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its root
  chapter and ignores the root clip `s1710004.mp4`
- **THEN** the `Main` table's thumbnails of those two clips have the text alternatives
  "Frame from Kvällen/s1710004.mp4" and "Frame from s1710004.mp4"

#### Scenario: Chapter clips are asked for by their full identity
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the `Kvällen` table's rows request their thumbnails with identities that start with `Kvällen/`,
  including the NEW `Kvällen/s1710004.mp4`, and each row shows the image for its own clip

#### Scenario: An ignored clip's frame is dimmed
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose root clip `s1710004.mp4` is IGNORED
- **THEN** that row shows its thumbnail dimmed together with the row's other facts, and the other rows'
  thumbnails are not dimmed

#### Scenario: A missing clip requests nothing
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, whose `reel.yaml` lists `borttagen.mp4` that is not
  on disk
- **THEN** no thumbnail request names `borttagen.mp4`, its row shows an empty placeholder box of the same size
  as the others, and every other clip's row shows its frame

#### Scenario: Edit mode keeps each frame with its clip
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, enters Edit mode, selects its first clip and
  moves it one place later with the Clip tab's Move later
- **THEN** every bin row shows the same frame its clip showed in the table, the moved clip's frame is now in
  the second row, and the service received no second thumbnail request for any of the four clips

#### Scenario: In Edit mode a clip's frame is a Watch button
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, and then enters Edit mode
- **THEN** in the read view no thumbnail image is focusable, and the play control over the thumbnail of a clip on
  disk is the only stop in its cell
- **AND** in Edit mode no thumbnail is focusable; a pointer press on the thumbnail of `s1710002.mp4`'s row, which
  `Kvällen` names without the folder, shows that clip in the player with keyboard focus on "Play s1710002.mp4", and a
  press on the ignored root clip `s1710004.mp4`'s thumbnail shows it there too

#### Scenario: A clip rotated for display is shown whole
- **WHEN** an event holds a 1920×1080 clip whose container rotates it 90° for display, named with a space,
  a comma and a Swedish letter (`stående klipp, 1.mp4`)
- **THEN** its thumbnail is requested with that name as its `clip` value and arrives taller than wide, its
  box has the same size as a landscape clip's, and the whole frame is visible inside it, turned as a player
  shows it, with empty bands at its sides

### Requirement: Edit mode lists, adds and removes a clip's cuts

A clip's cuts are the spans of it that the movie leaves out. Each has a start and an end, in seconds from the
clip's start, and may have a reason. In Edit mode, the inspector's Clip tab of every selected included or new clip
that `reel.yaml` does not exclude (a clip on disk that a chapter lists, or will list once the edits are saved)
SHALL hold the clip's **Cuts panel**, whether or not the Timeline's track draws the clip. The panel SHALL be
headed by the clip's **cut summary**, which SHALL say how many cuts the clip has and, when it has any, how much
time they cut out, and SHALL name the clip as its row in the bin names it. While the track draws the clip, each
listed cut SHALL also offer **Edit**, which selects the cut, and the panel SHALL offer "+ Cut at playhead"
("The Clip tab edits the selected clip").

The panel SHALL list the clip's cuts in their order, each with its number in the list, its start and end, its
length and its reason in words. A clip without cuts SHALL say that the whole clip plays. A missing clip that
`reel.yaml` does not exclude SHALL show, in its Clip tab, how many cuts it has, and SHALL offer no Cuts panel: its file is not on disk to cut, and
removing it from `reel.yaml` takes its cuts with it. Once the operator removes it, its Clip tab SHALL NOT show its
cuts any more, since the save drops them. An ignored clip SHALL have no cuts and no Cuts panel.
An excluded clip is not in the movie, so its cuts do not apply: its Clip tab SHALL show no cuts and SHALL offer no
Cuts panel, whether the clip is on disk or missing. Its cuts stay in `reel.yaml`, and a save SHALL write
them back unchanged.

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
than three decimals. It SHALL also be refused when its end is not after its start, when it shares more
than an instant with another cut of the clip that is not removed, or when it ends after the clip's length
once the page knows that length (below). A refusal SHALL be shown at the field it concerns, which SHALL
receive keyboard focus. It SHALL be announced, and it SHALL say what to type, which cut the new one overlaps,
or the clip's length. A cut that only touches another, the end of one being the start of the other, SHALL
be accepted. Times SHALL be compared to the millisecond, as they are typed and written, so a cut that starts
where another is shown to end touches it.

An added cut SHALL take its place in the list by its start, after every cut that starts at the same time or
earlier. It SHALL be saved with the reason `manual`. After an addition:

- both fields SHALL be empty again, with keyboard focus on the start field
- the addition SHALL be announced with the cut's times, the clip's name and its new cut count

**The clip's length.** The page knows a clip's length from one of two places, and the first it has wins: the
length the clip's preview has read from the clip's file in this Edit mode ("Edit mode previews a clip on
request"), else the duration the event detail gives the clip when it is not null (a thumbnail of the clip was
made before). The preview's length wins because it is the one Set From and Set To write times from, so a cut
set at the end of the clip is never refused. A null duration is unknown, never zero. When the page knows the
length from neither, the panel SHALL say that the page does not know the clip's length, that a cut that runs
past the clip's end stops there, and that a cut over the whole clip leaves the clip out of the movie, and it
SHALL NOT refuse a cut for its length. Once the page knows the length, from either place, the panel SHALL
state it beside its fields, SHALL refuse a cut that ends after it, and SHALL mark each listed cut that ends
after it ("A clip's preview sets cut times at the playhead and plays the clip as the movie will"), and
it SHALL still say that a cut over the whole clip leaves the clip out of the movie. The
duration of a clip the event detail gives SHALL NOT be sent anywhere, and neither length SHALL be saved.

**What a whole-clip cut does to a title card.** Wherever the panel says that a cut over the whole clip leaves
the clip out of the movie, it SHALL add that when the clip is its chapter's title clip, the chapter's title card
moves to the next clip of the chapter that plays. The render places a chapter's title card before the first
clip it plays when the title clip is cut away, and adds none to a chapter in which every clip is cut away. The
page does not know which clip is a chapter's title clip, so the sentence is conditional and the same for every
clip.

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
not covered by the top bar or cut off by the edge of the inspector.

**Typed but not added.** While a panel's fields hold a typed time that was not added, the event SHALL count as
having unsaved changes. The save bar SHALL say that a cut was typed but not added, naming the clip as its row
names it when only one clip holds one, also after an edit that changes that name. Save, and Overwrite with mine after a conflict, SHALL say that they are unavailable until
the cut is added or its fields are cleared. Selecting another clip SHALL keep what was typed, and so SHALL moving
the clip to another chapter. The bin's row of each clip whose panel holds such a time SHALL say so ("typed"), in
words at every width and to assistive technology, whichever clip is selected, so that the clip holding Save back
is found in the bin; so SHALL its cut summary. Reset SHALL empty every panel's fields.

While a save is in flight, the panel's fields, Add cut, Remove and Undo SHALL say that they are unavailable
and change nothing when used.

Every control in the panel SHALL take a tap anywhere in an area of at least 44 × 44 CSS pixels around it when the
primary pointer is coarse, reaching no other control, as every button does ("Every control is large enough to
touch"). No panel SHALL make the page scroll horizontally from 320 pixels up.

#### Scenario: Opening a clip's cuts
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator presses the bin row of
  `s1710001.mp4`
- **THEN** the Clip tab holds its Cuts panel, which says that the whole clip plays and offers a start and an end
  field and Add cut. Keyboard focus is still on the row.

#### Scenario: Adding a cut with typed times
- **WHEN** in that panel the operator types `0` as the start and `1,5` as the end and presses Enter
- **THEN**
  - the panel lists one cut, from `0:00` to `0:01.5`, 1.5 s long, its reason "Cut by hand"
  - the cut summary reads "1 cut · −1.5 s"
  - both fields are empty, with keyboard focus on the start field
  - the addition is announced
  - the save bar says that 1 cut was added

#### Scenario: Every accepted form of a time
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from ` 0:00:01.25 `
  to `0:02.5`, and then one from `4` to `0:06`
- **THEN** the panel lists the cuts from `0:01.25` to `0:02.5` and from `0:04` to `0:06`, in that order, and the
  cut summary reads "2 cuts · −3.25 s"

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

#### Scenario: A clip never previewed is not checked for length
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose detail gives a duration of `null`
  and whose preview was not opened in this Edit mode, the operator adds a cut from `5` to `7`
- **THEN** the cut is accepted and listed, and the panel says that the page does not know the clip's length and
  that a cut that runs past the clip's end stops there

#### Scenario: A clip whose duration the service gives is checked before any preview
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, whose detail gives a duration of `6.02`
  and whose preview was not opened in this Edit mode, the operator adds a cut from `5` to `7`
- **THEN** the panel says that the clip ends at `0:06.02`, the cut is refused at the end field, which receives
  keyboard focus, saying that `0:07` is after the clip's end at `0:06.02`, and no cut is added
- **WHEN** the operator types `0:06.02` as the end and adds the cut
- **THEN** the cut from `0:05` to `0:06.02` is listed

#### Scenario: The panel says where a whole-clip cut sends the title card
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator selects `s1710001.mp4`, the first
  clip of its chapter, and looks at its Cuts panel before and after opening its preview
- **THEN** both times the panel says that a cut over the whole clip leaves the clip out of the movie and that,
  when it is the chapter's title clip, the chapter's title card moves to the next clip of the chapter that plays

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
- **THEN** selected, `borttagen.mp4`'s Clip tab says that it has 1 cut and offers Remove from reel.yaml but no Cuts
  panel, while `s1710002.mp4` and `s1710004.mp4` show theirs when selected
- **WHEN** the operator presses Remove from reel.yaml in the Clip tab of `borttagen.mp4`
- **THEN** its row is listed as removed when the edits are saved, and its Clip tab no longer says that it has a
  cut

#### Scenario: An excluded clip offers no cuts
- **WHEN** the operator enters Edit mode on an event whose `reel.yaml` excludes `s1710002.mp4`, which is on
  disk and has a cut from `0` to `1.5`
- **THEN** its Clip tab offers no Cuts panel and shows no cut count, the other clips of the chapter still show
  theirs, and saving another edit writes the cut back unchanged

#### Scenario: An ignored clip has no cuts
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** selected, the ignored `s1710004.mp4` shows no Cuts panel in its Clip tab, and every clip `Main` and
  `Kvällen` play shows one, the new `Kvällen/s1710004.mp4` included

#### Scenario: A cut typed but not added holds Save back
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `2` as the start, adds
  nothing, and selects `s1710002.mp4`
- **THEN** the save bar says that a cut was typed on `s1710001.mp4` but not added, and Save says that it is
  unavailable. Selecting `s1710001.mp4` again shows `2` in the start field.
- **WHEN** the operator then presses the browser's Back
- **THEN** the page stays and asks "Discard unsaved changes?"

#### Scenario: A typed cut moves with its clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `2` as the start of a cut on
  `Kvällen/s1710002.mp4`, which `Kvällen` names `s1710002.mp4`, adds nothing, and moves that clip to `Main` with
  Move to… in its Clip tab
- **THEN** the save bar now says that a cut was typed on `Kvällen/s1710002.mp4` but not added, Save says that
  it is unavailable, and the clip's Cuts panel, its clip now in `Main`, still shows `2` in the start field

#### Scenario: Hidden panels holding typed text are marked on their rows
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator types `5` in the start field of `s1710002.mp4`,
  selects `s1710004.mp4` and types `1:00` in its start field, and then selects `s1710001.mp4`
- **THEN** the save bar says that cuts were typed on 2 clips but not added, and the bin rows of those two
  clips, and of no other, say "typed" and that a cut was typed but not added
- **WHEN** the operator selects `s1710002.mp4` and clears its field
- **THEN** its row no longer says so, and the save bar names `s1710004.mp4`

#### Scenario: Cut controls wait for a save
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its panel shown, the
  operator presses Save and the service has not answered yet
- **THEN** the start and end fields, Add cut and the cut's Remove say that they are unavailable, and typing and
  pressing them change nothing

#### Scenario: Cuts on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide, and the
  operator taps the bin row of `Kvällen/s1710002.mp4` and, in its Clip tab, adds a cut from `0` to `1`
- **THEN** the page does not scroll horizontally, and a tap anywhere in a 44 × 44 pixel area around each of the
  panel's fields, Add cut and the cut's Remove reaches that control and no other

### Requirement: Edit mode previews a clip on request

In Edit mode, the top of the clip bin SHALL hold the **player**: a region named "Player for <name>" that holds the
preview of one clip, the **shown clip**, where <name> is the clip's name as its row names it. The shown clip SHALL be
the last clip of the selection, or the clip of a selected cut ("One selection in the workspace", `event-timeline`),
when that clip is on disk. While a title card, a suggestion or nothing is selected, the player SHALL keep the clip it
showed. Before a clip on disk has been selected, and when the shown clip is no longer listed or no longer on disk, the
player SHALL say "Select a clip to watch it." and offer no control but Hide player: it SHALL be an inert placeholder
as tall as the player with a clip shown, with no focusable playhead or button, no "Nothing is loaded" line and no
other control in the accessibility tree, so that showing the first clip changes no row's size or place. The player
SHALL name the shown clip in its heading. In the bin's side pane with a fine pointer that heading MAY be for
assistive technology alone, because the selected row and the Clip tab name the clip on screen. The clip's preview is
**open** while the player holds a video for it: pressing the player's Play SHALL open it, and nothing else SHALL. A
new shown clip SHALL close the preview of the clip before it.

**From the row.** In Edit mode, a pointer press on the thumbnail of a bin row whose clip is on disk SHALL watch it:
select the clip alone, show the player when it is hidden, and move keyboard focus to the player's Play, without
playing. Pressed while that clip is shown, it SHALL keep its preview as it is and move keyboard focus to Play. The
thumbnail is not a stop of its own: from the keyboard, Enter on the row selects the clip, and the player's controls
come before the bin's list in the keyboard order. The thumbnail SHALL keep its box, its size and its place in the
row: a press on it changes no row's size or position. It SHALL NOT start a drag of its own. A thumbnail that could
not be shown (its "No preview" box) SHALL act all the same.

**Hide and show.** **Hide player** SHALL remove the player from the bin, close the preview, and give the bin's list
the room. A hidden player SHALL have no bar of its own: a **Show player** button SHALL take its place in the bin's
header, beside the Clips help, and SHALL keep the header's height and the place of its count. It SHALL show its icon
alone, 32 CSS pixels square with a fine pointer, with the tooltip "Show player". Its name SHALL be "Show player", and
"Show player, <name>" while a clip is shown, <name> as its row names it. Show player SHALL bring the player back with
the shown clip, its preview closed.
Show player, Hide player and a press on a row's thumbnail SHALL each record an explicit choice, kept in the browser
for later visits with every read and write of it guarded; an explicit choice SHALL always win, whatever the window.
While the operator has made no choice, in the bin's side pane (a window 960 pixels wide or more, with no coarse
pointer) the player SHALL start hidden in a window shorter than 70.125rem (1122 CSS pixels at a 16 pixel root: the
height at which the four played rows of `2024-08-20 - Två kapitel - Tjörn` fit whole with the player shown) and shown
in a window that height or taller; a stacked page or a coarse pointer starts shown. With no choice, the player SHALL
follow the window across that height as it is resized, and a resize SHALL change nothing once there is a choice.
When the browser keeps nothing, there is no stored choice, so the height rule decides.

**What it plays.** The preview SHALL play the clip's preview copy when the clip has a ready one, and the clip's
own file, the original, otherwise, as "A clip's preview plays its preview copy when one is ready" requires. The
original is the file the service serves from `GET /api/v1/events/{event_id}/media?clip=<identity>`. The event id
and the clip's full identity SHALL be sent exactly as the event detail gives them, and the clip's modification
time, exactly as the event detail gives it, as `v`. Until its preview is open, the player SHALL show the clip's
thumbnail. It SHALL NOT start playing by itself. A preview SHALL open at the clip's start, also after an earlier
preview of the clip was closed. A clip displayed in portrait, such as a phone clip whose container rotates it, SHALL
be shown whole, turned as a player shows it. Unless a scenario of this requirement says that its clip has a ready
preview copy, it SHALL be read for a clip that has none.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media or its preview copy, and
SHALL NOT create a video element for either, before the operator opens that clip's preview. The one exception is the
Timeline's own video ("The playhead scrubs one video"), which the track brings and which loads the preview copy of the
clip its playhead is in; it is not a clip's preview and no selection moves it. Selecting a clip, and
showing it in the player, SHALL request only its thumbnail, beyond what the Timeline's video had requested before the
selection, and SHALL NOT create a clip-preview video element. This SHALL hold for any number of clips,
for Cuts panels that are shown, and on entering, scrolling and leaving Edit mode. Closing a preview SHALL
stop its playback and any loading of its file, and show the clip's thumbnail again.

**One at a time.** The player holds at most one preview, so that Edit mode never holds more than one clip's video
element. Edit mode SHALL show no movie player: the event's "Movie" section belongs to the read view, which Edit mode
replaces.

**Keyboard and focus.** The player's controls SHALL come in this keyboard order, each reachable and usable by
keyboard alone:
1. **Hide player**, named "Hide the player of <name>" (while hidden, the bin header's **Show player**, "Show player,
   <name>")
2. **Play** / **Pause**, which says which it does
3. the **playhead**, a slider over the clip's length
4. **Skip cuts**
5. **Set From**
6. **Set To**
7. **Play original** or **Play preview copy**, present only while the clip has a ready preview copy

Each control SHALL name the clip as its row names it. Escape, pressed while keyboard focus is in the player, SHALL
close the preview, leave keyboard focus on Play, and leave the selection as it is. Hide player SHALL leave keyboard
focus on Show player, and Show player on Hide player. No control of a closed preview SHALL keep focus.

**Play** SHALL be usable as soon as the player shows a clip. Pressed before the browser has read the clip, it
SHALL play the clip once the browser can. Opening a preview, or Try again, SHALL announce once that the clip is ready
to play, with its length.

**The playhead.**
- Space on it SHALL play or pause the clip, as Play does, and SHALL NOT scroll the page.
- It SHALL take the Left and Down arrows to step back 0.1 seconds and the Right and Up arrows to step on 0.1
  seconds. Page Down and Page Up SHALL step one second, and Home and End SHALL go to the clip's start and
  end. Each step SHALL stay within the clip.
- A press or a drag along it SHALL move to the time under the pointer.
- It SHALL say its value to assistive technology as the time and the clip's length, in the format the Cuts
  panel writes times (`0:01.234 of 0:06.02`), and SHALL add when the time lies inside a cut. While the clip
  plays, the value it says SHALL change at most once a second.
- Until the preview is open and has read the clip's length, the playhead, Set From and Set To SHALL say that they
  are unavailable and change nothing.

The preview SHALL show the playhead's time and the clip's length as a readout that says what it is and keeps its
width, as "Running times are written to a fixed width and say what they are" requires (`Clip 0:01.23 of 0:06.02`).
The slider's value text stays in the Cuts panel's format, above.

**Sizes and look.**
- The picture SHALL be shown whole in a box of fixed 16:9 proportions, as wide as the bin allows up to 640
  CSS pixels and never taller than 360 (the side pane's box below is capped lower, and is then wider than 16:9).
  The box SHALL have that size before the clip's file is read, so that nothing on the page moves when it is.
- In the bin's side pane (a window 960 pixels wide or more) with a fine pointer, the player SHALL stay within a
  height budget of about 200 CSS pixels with its preview closed or open, and also with a preview copy ready (so that
  "Play original" moves nothing): the picture's box is then at most 136 tall, as wide as the pane, and the picture
  sits whole inside it, with bands at its sides when the box is wider than 16:9. Play with the playhead make one
  row, and Skip cuts, Set From and Set To the next. The readout and Hide player lie along the top of the picture's
  box, and the source line and "Play original" along its foot. A coarse pointer or a stacked page keeps its larger
  rows and boxes.
- In a window 320 pixels wide or more, the player SHALL NOT make the page scroll horizontally.
- When the primary pointer is coarse, each of its controls SHALL take a tap anywhere in an area of at least
  44 × 44 CSS pixels around it, reaching no other control. The playhead SHALL take a tap across its whole
  width in an area at least 44 pixels tall.
- It SHALL follow the page's color scheme in both schemes. No state of it SHALL be shown by color alone: a control
  that says it is unavailable (Set From, Set To, the playhead) SHALL also have a dashed edge.
- It SHALL animate nothing. The playhead moves only with playback or a seek.

**What the browser cannot do, by cause.** Each of these SHALL be shown in the player as a note, never as an
alert, and announced once through Edit mode's live region. Keyboard focus SHALL stay in the player, on
Hide player when the control that held it went:
- **No sound.** When the original plays and the browser reports that it finds no audio it can play in the clip, the preview SHALL say
  that this browser finds no sound it can play in the clip, and that if a Sony camera recorded it, its sound
  is PCM, which Firefox does not play and Chrome does, and the render keeps it. The note SHALL NOT state as
  fact a cause or a sound the page does not know of: the clip may have no audio track at all. Playback SHALL
  be otherwise unchanged, never muted. The note SHALL NOT be shown while the preview copy plays. When the clip
  has a ready preview copy whose facts name an audio codec, the note SHALL add that the preview copy plays with
  sound and that Play preview copy plays it; when the facts name none (the clip has no audio), the note SHALL stay
  as it is and SHALL NOT promise sound from the copy.
- **No picture.** When the browser reads the clip but shows no picture of it, the preview SHALL say that this
  browser cannot show the clip's picture, and SHALL offer the clip's file as a download. Its controls SHALL
  stay.
- **It cannot play the clip.** (This is the original's. The preview copy's failures are the ones "A clip's
  preview plays its preview copy when one is ready" lists.) When the browser refuses the original, the page SHALL ask the service for the
  clip's first byte, once, to tell why. It SHALL then say:
  - that the clip is no longer on disk, with the service's detail, when the service answers that it is not a
    clip of the event
  - that the clip changed on disk since the page was read, when the service serves a file whose modification
    time differs from the one the event detail gave
  - in both of these cases, the advice to stop editing (saving first to keep the edits), so that the event is
    read again, and then to open the player again. The page SHALL NOT call this a refresh: in Edit mode the
    page's Refresh leaves Edit mode. The edits SHALL stay untouched until the operator acts.
  - that the clip's file is empty, when the service answers that the file has no first byte
  - that the clip could not be read, with the failure kind's words and the service's detail, when the service
    answers that it cannot read it
  - that this browser cannot play the clip's format, offering the file as a download, when the service serves
    it
  - that the service gave no usable answer, saying which, with a Try again that opens the preview anew, when it
    gives none. Try again SHALL move keyboard focus to the reopened preview's Play.

  A failure SHALL NOT be retried by itself.

**Within Edit mode.**
- Opening, closing, playing and seeking a preview SHALL write nothing and SHALL NOT count as an edit. They
  SHALL bring no save bar and SHALL NOT trigger the unsaved-changes question.
- While a save is in flight or a move of several clips is pending, Set From and Set To SHALL say that they are
  unavailable and change nothing. Play, the playhead, Skip cuts and Hide player SHALL stay usable.
- A move of the shown clip, within its chapter or into another one, by any means (a drag, Alt and an arrow, Move
  earlier, Move later, Move to…), SHALL keep its preview as it was, playing or not, at the same
  time. The move SHALL NOT move keyboard focus into the player and SHALL NOT scroll the bin to it.
- Reset SHALL close the preview. Leaving Edit mode SHALL close it.

#### Scenario: Nothing loads until a preview is opened
- **WHEN** the operator opens Edit mode on `2024-09-15 - Stor dag`, whose root chapter plays 400 clips, each with a
  ready preview copy so that the track draws them, and scrolls the bin's list to its end
- **THEN** the page holds no clip-preview video element, its one video is the Timeline's, and the only requests made
  for clip media are the Timeline's own, for the clip its playhead is in (the copy, at
  `…/proxy?clip=c0001.mp4&v=<the copy's version the detail names>`, with no first-byte request of its own); none
  names `c0200.mp4` or `c0400.mp4`
- **WHEN** the operator selects `c0001.mp4`, `c0200.mp4` and then `c0400.mp4` on the track, one after the other,
  so that the Clip tab shows each one's Cuts panel in turn
- **THEN** the player shows `c0400.mp4`'s thumbnail, the page still holds no clip-preview video element, the
  Timeline's playhead has not moved, and the only requests made for those clips since the selections began are their
  thumbnails
- **WHEN** the operator presses the player's Play
- **THEN** `c0400.mp4` plays from its preview copy, and every request for clip media made since the selections
  began names `c0400.mp4`: the copy's first byte at `…/proxy?clip=c0400.mp4` with no `v`, then the copy at
  `…/proxy?clip=c0400.mp4&v=<tag>`, where `<tag>` is the entity tag (ETag) the first answered; none goes to
  `…/media`, and none carries a modification time as `v` (the original's address does, in a scenario whose clip has
  no ready preview copy)

#### Scenario: Playing and seeking from the keyboard
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, using only the keyboard, the operator moves to the
  row of `s1710001.mp4` in the bin's list, presses Enter, moves back to the player's Play with Shift+Tab and presses
  Space
- **THEN** the clip plays, and the control with focus is now named "Pause s1710001.mp4"
- **WHEN** the operator presses Space again, moves to the playhead, and presses Home, then Right three times
- **THEN** the clip is paused, and the playhead says `0:00.3 of 0:06.02` in a browser that reads the clip's
  length as 6.02 seconds
- **WHEN** the operator presses End, then Page Down
- **THEN** the playhead says `0:05.02 of 0:06.02`
- **WHEN** the operator presses Space on the playhead
- **THEN** the clip plays and the page does not scroll; Space again pauses it

#### Scenario: Opening another preview closes the first
- **WHEN** the preview of `s1710001.mp4` of `2024-06-27 - Grillning med grannar` is playing in the player, and the
  operator presses the block of `s1710002.mp4` on the track
- **THEN** the preview of `s1710001.mp4` is closed and its file is no longer loading. The player shows
  `s1710002.mp4`'s thumbnail with its Play, nothing plays, and keyboard focus is on the block.

#### Scenario: Closing gives focus back
- **WHEN** keyboard focus is on the playhead of an open preview of the selected `s1710001.mp4` and the operator
  presses Escape
- **THEN** the preview closes, the player shows the clip's thumbnail, keyboard focus is on its Play, and
  `s1710001.mp4` is still selected
- **WHEN** the operator opens it again and presses Hide player
- **THEN** the preview closes, the player is gone from the bin, Show player is in the bin's header, and keyboard
  focus is on it
- **WHEN** the operator leaves Edit mode, enters it again and selects a clip
- **THEN** the player is still collapsed, and Show player brings it back with keyboard focus on Hide player

#### Scenario: A short window starts with the player hidden
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window with a fine pointer, with
  nothing stored for the player
- **THEN** the player is hidden, Show player is in the bin's header, and the bin's list shows at least 3 whole rows
  of the clips its chapters play ("The clip bin lists every clip of the event as one plain list")
- **WHEN** the operator presses Show player
- **THEN** the player is shown, and it is still shown when Edit mode is opened again in the same window, and in a
  window as short as 700 pixels
- **WHEN** the operator presses Hide player and opens Edit mode in a 1440×1300 window
- **THEN** the player is still hidden, because the choice wins
- **WHEN** Edit mode opens in a 1440×1300 window with nothing stored for the player
- **THEN** the player is shown, with its empty placeholder or the clip's closed preview
- **WHEN** nothing is stored and the window is resized from 1440×1300 to 1440×900 and back
- **THEN** the player is hidden at 1440×900 and shown again at 1440×1300, and nothing is stored
- **WHEN** nothing is stored and the window is 900 pixels wide and 700 tall (a stacked page)
- **THEN** the player is shown

#### Scenario: Watching from the row in one press
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator presses the thumbnail of
  `s1710002.mp4`'s row in the bin with the pointer
- **THEN** `s1710002.mp4` is selected, the player shows it with keyboard focus on "Play s1710002.mp4", nothing
  plays, and no row changed its size or place
- **WHEN** the player plays `s1710002.mp4` and the operator presses the thumbnail of `s1710001.mp4` with the pointer
- **THEN** the preview of `s1710002.mp4` is closed, the player shows `s1710001.mp4` with keyboard focus on its Play,
  and no drag starts: every clip keeps its place
- **WHEN** the player is hidden and the operator presses the thumbnail of `s1710002.mp4`
- **THEN** the player is shown again, with `s1710002.mp4` and keyboard focus on its Play
- **WHEN** in Edit mode on `2024-10-05 - Trasig`, whose thumbnail shows "No preview", the operator presses the
  thumbnail of `trasig.mp4` and then the player's Play
- **THEN** the player says that the clip's file is empty

#### Scenario: A portrait clip is shown whole
- **WHEN** the event `2024-05-19 - Provklipp` holds `h264-720p-rotate90-aac.mp4`, a 1280×720 clip that its
  container turns to portrait, and the operator opens its preview and plays it
- **THEN** the picture is taller than wide and wholly inside the preview's picture box, with empty bands at its
  sides (the box is 16:9 in a stacked page, and in the side pane it is as wide as the pane and at most 136 px tall).
  The box is as large as the box of a landscape clip in the same player would be.

#### Scenario: No sound for a Sony clip in Firefox
- **WHEN** in Firefox, which plays no PCM audio, the operator opens the preview of `sony-xavc-1080p25-pcm.mp4`
  of `2024-05-19 - Provklipp`, whose preview copy is not ready
- **THEN** the preview says that this browser finds no sound it can play in the clip, and that if a Sony
  camera recorded it, its sound is PCM, which Chrome plays and the render keeps. The note is announced once,
  and the clip plays its picture on request, not muted.
- **WHEN** the same preview is opened in Chrome
- **THEN** no such note is shown
- **WHEN** in Firefox, the operator opens the preview of a clip with no audio track whose preview copy is ready
  and whose facts name no audio codec
- **THEN** the note is shown without the sentence that the preview copy plays with sound

#### Scenario: A picture this browser cannot show
- **WHEN** in Chrome, the operator opens the preview of the HEVC clip `hevc-mov-rotate90-aac.mov` of
  `2024-05-19 - Provklipp`
- **THEN** the preview says that this browser cannot show the clip's picture and offers the clip as a
  download, and its controls stay
- **WHEN** in Firefox, which refuses that clip, the operator opens the same preview
- **THEN** the preview says that this browser cannot play the clip's format and offers the clip as a download

#### Scenario: An empty clip says so
- **WHEN** in Edit mode on `2024-10-05 - Trasig`, whose only clip `trasig.mp4` is an empty file, the operator
  opens its preview
- **THEN** the preview says that the clip's file is empty and that there is nothing to play. The page shows no
  alert, the words are announced once, and keyboard focus is in the preview.

#### Scenario: Try again opens the preview anew
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the service gives no answer when the operator
  opens the preview of `s1710001.mp4`, and then answers again
- **THEN** the preview says that the service is not reachable and offers Try again
- **WHEN** the operator presses Try again
- **THEN** the preview opens anew, ready to play, with keyboard focus on "Play s1710001.mp4", and Escape closes
  it

#### Scenario: A clip removed from disk since the page was read
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, `s1710004.mp4` is deleted from disk and the
  operator then opens its preview
- **THEN** the preview says that the clip is no longer on disk and advises stopping editing, saving first to
  keep the edits, to read the event again, and offers no download

#### Scenario: A clip changed on disk since the page was read
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, after the page was read, `s1710002.mp4` is
  replaced on disk by a file of the same name that no browser can play, and the operator opens its preview
- **THEN** the preview says that the clip changed on disk since the page was read and advises stopping editing,
  saving first to keep the edits, to read the event again, rather than blaming the clip's format. It offers no
  download, and the edits are as they were

#### Scenario: The preview follows its clip
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the preview of `s1710001.mp4` is paused at
  `0:02.5`, and the operator drags that clip's block on the track into `Kvällen`
- **THEN** the player still shows `s1710001.mp4` with its preview open, paused, at `0:02.5`, and keyboard focus
  did not move into the player
- **WHEN** the preview of `Kvällen/s1710002.mp4` is playing and the operator presses Move later in its Clip tab
- **THEN** it keeps playing

#### Scenario: A pending save leaves playback alone
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its preview open, the
  operator presses Save and the service has not answered yet
- **THEN** Set From and Set To say that they are unavailable, and pressing them changes no field, while Play,
  the playhead and Hide player still work and keyboard focus stays on Save

#### Scenario: Previewing is not an edit
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator opens the preview of
  `s1710002.mp4`, plays it, seeks it and closes it, and then presses the browser's Back
- **THEN** no save bar is shown at any time, and the page goes back to the event list without asking about
  unsaved changes

#### Scenario: Reset closes the preview
- **WHEN** on `2024-06-27 - Grillning med grannar`, with the title changed and the preview of `s1710001.mp4`
  open, the operator presses Reset
- **THEN** the preview is closed, the player shows the clip's thumbnail, and the page holds no video element

#### Scenario: A preview on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide, and the
  operator opens the preview of `Kvällen/s1710002.mp4`
- **THEN** the page does not scroll horizontally, and the picture's box is 16:9 inside the player. A tap anywhere
  in a 44 × 44 pixel area around Hide player, Play, Skip cuts, Set From and Set To reaches that control and no other.
  A tap anywhere along the playhead, up to 22 pixels above or below its centre line, moves it.

#### Scenario: The player's time says what it is and does not move
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar` the operator opens the preview of `s1710001.mp4`
  (6.02 s) and plays it to the end
- **THEN** the header reads `Clip 0:00.00 of 0:06.02`, then `Clip 0:01.50 of 0:06.02`, and `Clip 0:06.02 of 0:06.02`
  at the end; the readout's bounding box has the same width in every sample taken during the playthrough, and Hide
  player does not move

### Requirement: A clip's preview sets cut times at the playhead and plays the clip as the movie will

**The cut bar.** Under the picture, the preview SHALL show a bar along the clip's length. It SHALL show:
- every cut the clip's panel lists that is not removed, read and added alike
- each cut that is removed until the save, drawn differently
- while the panel's fields hold a start and an end that the panel would accept as a cut, that typed span,
  drawn differently again
- the playhead

Each kind SHALL differ by its shape, not by its color alone, and a legend SHALL name each kind the bar shows.
A cut that runs past the clip's end SHALL be drawn up to that end. The bar SHALL follow every change to the
panel's cuts and fields at once.

**Set From and Set To.**
- **Set From** SHALL write the playhead's time into the start field of the shown clip's Cuts panel, and **Set To**
  into its end field, whether that panel is shown or hidden.
  The playhead's time is the time of the file that plays, the original or its preview copy, which are the same.
- The time SHALL be written to the millisecond, in the format the panel writes times (`0:01.234`, `0:02.5`).
  The panel SHALL read it back as that same time.
- Keyboard focus SHALL stay on the pressed control, and the new value SHALL be announced.
- Neither SHALL add a cut. The written time SHALL count as a cut typed but not added: the clip's bin row and its
  cut summary SHALL say "typed", and the save bar SHALL hold Save back until the cut is added or its fields
  cleared, as for any typed time.

**Skip cuts** SHALL be a control that says whether it is on, and it SHALL start off.
- While it is on, playback SHALL show no frame that lies wholly inside a cut the panel lists that is not
  removed. Cuts are joined as the render joins them, overlapping or touching ones as one.
- Playback reaching a cut SHALL continue at the cut's end, jumping over each cut once, also when the cut ends
  between two frames. Playback SHALL never stall at a cut.
- A cut that runs to the clip's end, or that ends less than 0.1 seconds before the end the browser reads,
  SHALL stop playback, paused, at that cut's start. Browsers read a clip's length up to 60 ms longer than the
  render does, so a cut that ends where the render's clip ends counts as running to the end.
- Play pressed while the playhead is inside a cut SHALL start at that cut's end. When no footage follows it,
  or when the playhead is at the clip's end, Play SHALL start at the first footage of the clip outside every
  cut. When the cuts cover the whole clip, Play SHALL play nothing and SHALL say that the cuts cover the whole
  clip.
- While it is off, playback SHALL show every moment of the clip.
- In either state, moving the playhead into a cut while the clip is paused SHALL show that moment, so that a
  time can be set from inside a cut.

**The clip's length.** The page SHALL take a clip's length from its preview when the preview has read it, else
from the duration the event detail gives the clip when that is not null, and from nowhere else. The preview reads
it from the file that plays: as the browser reads it from the original's file, or, while the clip's preview copy
plays, as the duration in the copy's facts, which is the original's duration as the engine probed it ("A clip's
preview plays its preview copy when one is ready"). The preview's length SHALL win over the detail's whenever
both exist, because Set From and Set To write times in it, and a browser can read up to 60 ms more than the
probe's duration. A detail duration of `null` SHALL be treated as unknown, never as zero.
- Once it has the length, the clip's panel SHALL say where the clip ends beside its fields (`This clip ends at
  0:06.02`).
- The panel SHALL refuse a cut that ends after the clip's length, compared to the millisecond as the panel
  writes times. The refusal SHALL be at the end field, or at the start field when the start lies at or after
  the length, since no end could then fix it. It SHALL name the cut's time and the clip's length. A cut that
  ends exactly at the length SHALL be accepted.
- Each cut the panel lists that ends after the length SHALL be marked as running past the clip's end. Nothing
  SHALL refuse it, and its Undo SHALL NOT be refused for it.
- The page SHALL keep the length the preview read for the clip while Edit mode stays open: after the preview
  closes, after another opens, and after the clip moves to another chapter. It SHALL forget it when the
  clip's modification time changes, and when Edit mode closes. The detail's duration belongs to the clip's
  current file, so a replaced file's old duration SHALL NOT be used: the next detail gives the new one, or
  `null`.
- When the browser reads a different length for the original while it plays, the panel SHALL use the latest.
  What the browser reads from a preview copy SHALL NOT change the length.
- Neither length SHALL be saved, sent to the service or shown anywhere outside Edit mode.

#### Scenario: The bar shows the clip's cuts
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds with the reason `black`, and in Edit mode the operator opens that clip's preview, adds a cut from
  `3` to `4` and removes the read cut
- **THEN** the bar shows the cut from 3 to 4 seconds as a cut and the span from 0 to 1.2 seconds as removed,
  each drawn differently, and the legend names a cut and a cut removed when you save

#### Scenario: Setting a cut at the playhead
- **WHEN** in the preview of `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, with the playhead at
  `0:01.2`, the operator presses Set From
- **THEN** the start field holds `0:01.2`, keyboard focus is on Set From, "From set to 0:01.2" is announced, the
  clip's bin row says "typed", and the save bar says that a cut was typed on `s1710001.mp4` but not added
- **WHEN** the operator moves the playhead to `0:02.5`, presses Set To, and then presses Add cut
- **THEN** the bar showed the typed span from 1.2 to 2.5 seconds before the addition. The panel then lists the
  cut from `0:01.2` to `0:02.5`, the cut summary reads "1 cut · −1.3 s", and the save bar says that 1 cut was
  added.

#### Scenario: A time set while playing is written to the millisecond
- **WHEN** the preview of `s1710001.mp4` plays and the operator presses Set From while it plays
- **THEN** the start field holds the playhead's time at that moment, rounded to the millisecond and written
  without a trailing zero, such as `0:02.607`, and the panel accepts it

#### Scenario: Skipping cuts while playing
- **WHEN** `s1710002.mp4` of `2024-06-27 - Grillning med grannar` has a cut from `1` to `2`, and the operator
  turns Skip cuts on, moves the playhead to `0:00.5` and plays the clip
- **THEN** no frame between 1 and 2 seconds is shown, and playback continues from 2 seconds
- **WHEN** the operator turns Skip cuts off and plays the clip again from `0:00.5`
- **THEN** the frames between 1 and 2 seconds are shown

#### Scenario: A cut that ends between two frames is jumped over once
- **WHEN** `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, a 50 fps clip, has a cut from `1` to
  `2.01`, which ends between its frames at 2 and 2.02 seconds, and the operator turns Skip cuts on and plays
  the clip from `0:00.5`
- **THEN** playback goes on past 2.5 seconds within a second of reaching the cut, the cut is jumped over once,
  and no frame that lies wholly between 1 and 2.01 seconds is shown

#### Scenario: A cut to the clip's end ends playback
- **WHEN** `s1710002.mp4` also has a cut from `5` to `0:06.02`, where ffprobe and the render end the clip,
  Skip cuts is on, and the operator plays the clip from `0:04.5`, in Chrome, which reads the clip's length as
  6.02 seconds, and again in Firefox, which reads it as 6.08 seconds
- **THEN** in each, playback stops at 5 seconds, paused, with no frame after 5 seconds shown
- **WHEN** the operator presses Play again
- **THEN** playback starts from the clip's start

#### Scenario: Cuts over the whole clip leave nothing to play
- **WHEN** `s1710001.mp4` has one cut from `0` to its end (`0:06.02`, in a browser that reads that length),
  Skip cuts is on, and the operator presses Play
- **THEN** nothing plays, and the page says that the cuts cover the whole clip

#### Scenario: A cut past the clip's end is refused once its length is known
- **WHEN** in a browser that reads its length as 6.02 seconds, the operator opens the preview of
  `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, closes it, and adds a cut from `5` to `7`
- **THEN** the panel says that the clip ends at `0:06.02`. The cut is refused at the end field, which receives
  keyboard focus, saying that `0:07` is after the clip's end at `0:06.02`. No cut is added.
- **WHEN** the operator types `0:06.02` as the end and adds the cut
- **THEN** the cut from `0:05` to `0:06.02` is listed
- **WHEN** the operator adds a cut from `7` to `8` on the same clip, and then one from `0:06.02` to `7`
- **THEN** each is refused at the start field, saying that its start is at or after the clip's end

#### Scenario: A listed cut past the end is marked, not refused
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` a cut from 3723.125 to
  3725.5 seconds, and the operator opens that clip's preview
- **THEN** the cut is listed as running past the clip's end and is not drawn on the bar beyond it. Removing it
  and pressing its Undo is not refused.

#### Scenario: The length stays with the clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens and closes the preview of `s1710001.mp4`,
  moves that clip to `Kvällen` with Move to… in its Clip tab, and adds a cut from `5` to `7` on it there
- **THEN** the cut is refused for ending after the clip's length

#### Scenario: The preview's length wins over the service's duration
- **WHEN** the detail gives `s1710001.mp4` of `2024-06-27 - Grillning med grannar` a duration of `6.02`, and in
  Firefox, which reads its length as 6.08 seconds, the operator opens the preview, presses Set To at the end of
  the clip and adds the cut from `5`
- **THEN** the panel says that the clip ends at `0:06.08`, and the cut from `0:05` to `0:06.08` is listed, not
  refused

#### Scenario: A listed cut past the end is marked from the service's duration
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` a cut from 3723.125 to
  3725.5 seconds, the detail gives that clip a duration of `6.02`, and no preview was opened
- **THEN** the cut is listed as running past the clip's end, and removing it and pressing its Undo is not
  refused

#### Scenario: Cutting to the original's end while its preview copy plays
- **WHEN** the detail gives `s1710001.mp4` of `2024-06-27 - Grillning med grannar` a ready preview copy whose
  facts say `6.02` seconds, the browser reads the copy as 6.0 seconds, and the operator opens the preview, plays
  the copy, and adds a cut from `5` to `0:06.02`
- **THEN** the panel says that the clip ends at `0:06.02` and lists the cut, not refused

### Requirement: The Clip tab edits the selected clip

With one clip selected, the Clip tab SHALL show the clip's name, chapter and position, and its length in the movie,
and SHALL offer Trim In and Trim Out as typed times, Rotate left and right, **Move earlier** and **Move later**,
**Move to…**, the clip's Cuts panel ("Edit mode lists, adds and removes a clip's cuts") with "+ Cut at playhead",
Use frame as poster. A typed trim SHALL be the same
draft edit as the track's edge tools. Which of these a clip offers when the track does not draw it is stated in "The
Clip tab offers a clip's edits whether or not the track draws it".
Move to… SHALL be a chapter picker named "Chapter to move <name> to", listing every chapter the draft lists but the
clip's own, and a Move button that puts the clip at the end of the chosen chapter, the edit a drop on that chapter's
band makes. While no chapter is chosen, or a save or a move of several clips is pending, Move SHALL be `aria-disabled`
and say why. An event with one chapter SHALL offer no Move to….

#### Scenario: Typed Trim In
- **WHEN** the operator types 0:01.50 into Trim In for `s1710001.mp4`
- **THEN** the clip's leading cut is 0 to 1.5 s in the draft, the block shortens and the clips after it move left

#### Scenario: Moving one clip to another chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` `Kvällen/s1710003.mp4` is selected and the operator chooses `Main` in
  the Clip tab's picker and presses Move
- **THEN** `s1710003.mp4` is drawn last in `Main`, the move is announced, keyboard focus stays on Move, and Undo says
  "Undo move of s1710003.mp4"

#### Scenario: One chapter, no Move to
- **WHEN** a clip of `2024-06-27 - Grillning med grannar`, whose clips are all in one chapter, is selected
- **THEN** the Clip tab offers no Move to…

### Requirement: The Clip tab offers a clip's edits whether or not the track draws it

With one clip selected, from the track or the bin, the Clip tab SHALL show its name, chapter, position and status in
words, also while the track is not open. For a clip a chapter lists it SHALL offer Move earlier and Move later (one
place in its chapter's list; into the next chapter at an edge, but a missing clip's own edge stops it), and if on
disk Move to… and Rotate; Ignore or Include clip; Remove from reel.yaml or Undo for a missing clip. Its Cuts panel
takes typed cuts with or without the track; trims, "+ Cut at playhead", a cut's Edit and the poster need the
track.

#### Scenario: An ignored clip is included from the Clip tab
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator presses the bin row of the ignored `s1710004.mp4`
- **THEN** the Clip tab shows `s1710004.mp4`, "Ignored: not in the movie", and Include clip, and no Trim In/Out,
  Rotate or cuts
- **WHEN** the operator presses Include clip
- **THEN** `s1710004.mp4` is drawn last in `Main`, the top bar counts it, keyboard focus stays in the Clip tab, and
  Undo says "Undo include of s1710004.mp4"

#### Scenario: A missing clip is removed from the Clip tab
- **WHEN** on `2024-09-01 - Sommarlov` the operator presses the bin row of the missing `borttagen.mp4`
- **THEN** the Clip tab shows `borttagen.mp4`, "Clips · clip 3 of 3", "Missing from disk", Move earlier and Remove
  from reel.yaml
- **WHEN** the operator presses Remove from reel.yaml
- **THEN** the clip is removed as "Edit mode removes a missing clip from reel.yaml on request" says, the Clip tab
  says that it is removed from reel.yaml when the edits are saved and offers Undo, which has keyboard focus

#### Scenario: Moving a clip while proxies are being prepared
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar` while its Timeline shows Prepare, and the
  operator presses the bin row of `s1710001.mp4` and then Move later in the Clip tab
- **THEN** `s1710001.mp4` is second in its chapter, the move is announced with its position, keyboard focus stays
  on Move later, and the Clip tab offers no Trim In/Out, "+ Cut at playhead" or Use frame as poster, while its Cuts
  panel takes a typed cut

#### Scenario: Move later at a chapter's end
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the last clip of `Main` is selected and the operator presses Move
  later in the Clip tab
- **THEN** it becomes the first clip of `Kvällen`, as Alt+Right makes it, and the move is announced

#### Scenario: Move earlier and later by touch
- **WHEN** on a touch screen 390 pixels wide the operator taps the bin row of `s1710003.mp4` and taps Move earlier
  in the Clip tab
- **THEN** the clip moves one place earlier, and Move earlier and Move later each take a tap anywhere in a
  44 × 44 pixel area that reaches no other control

### Requirement: The Clip tab acts on several selected clips

With two or more clips selected, the Clip tab SHALL say how many and name them (five at most, then "and N more"), and
SHALL offer Rotate left, Rotate right, Move to… and Ignore clips, and Include clips when some of them are ignored,
each one draft edit and one Undo step over every selected clip it applies to. A rotate SHALL turn each clip a quarter
from its own turn. Move to… SHALL put the clips at the end of the chosen chapter, in play order; while it is applied
it is the pending move of several clips.

#### Scenario: Three clips turned right
- **WHEN** on `2024-06-27 - Grillning med grannar` the clips `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4`, with
  turns 0, 90 and 270, are selected and the operator presses Rotate right in the Clip tab
- **THEN** their turns are 90, 180 and 0, "3 clips rotated right." is announced once, the three stay selected, and
  Undo says "Undo rotation of 3 clips"

#### Scenario: Moving two clips from two chapters
- **WHEN** on an event whose chapters are `Main`, `Kvällen` and `Test`, the operator selects `Main/a.mp4` and
  Ctrl+clicks `Kvällen/c.mp4`, chooses `Test` in the Clip tab's picker and presses Move
- **THEN**
  - `Test` plays what it played before and then `a.mp4` and `c.mp4`, last, in that play order
  - "2 clips moved to “Test”." is announced once, and keyboard focus stays on Move
  - the top bar says "2 clips moved", and both clips are still selected
- **WHEN** the operator saves
- **THEN** `reel.yaml` lists `a.mp4` and `c.mp4` last in `Test`'s clips and nothing else changed

#### Scenario: The clips already are last
- **WHEN** the two clips just moved are still selected and the operator presses Move with `Test` chosen again
- **THEN** "Nothing moved." is announced and the draft and the top bar are unchanged

#### Scenario: Ignoring several clips
- **WHEN** `s1710001.mp4` and `s1710003.mp4` are selected and the operator presses Ignore clips
- **THEN** neither is drawn, the bin lists both as ignored, the top bar says "2 clips ignored", nothing is selected,
  and one Undo brings both back

#### Scenario: Move says why it is unavailable
- **WHEN** two clips are selected and no chapter is chosen
- **THEN** Move is `aria-disabled`, not `disabled`, its description and tooltip say "Choose a chapter.", and pressing
  it changes nothing
- **WHEN** a save is pending
- **THEN** Rotate left, Rotate right, Move and Ignore clips say "Unavailable while saving." and change nothing
- **WHEN** only the Clip tab's Move of several clips is pending
- **THEN** Rotate left, Rotate right, Move and Ignore clips say "Unavailable while the clips move." and change
  nothing

#### Scenario: The selection is its own set of clips
- **WHEN** `s1710001.mp4` and `s1710003.mp4` are selected and the operator moves them to `Kvällen` with the Clip
  tab's Move
- **THEN** only `s1710001.mp4` and `s1710003.mp4` moved, and the bin offers no mark: the selection is the only set
  of clips

#### Scenario: Including two ignored clips
- **WHEN** on an event that ignores `a.mp4` and `b.mp4` of `Main`, the operator presses the bin row of `a.mp4`,
  Ctrl+presses the row of `b.mp4`, and presses Include clips in the Clip tab
- **THEN** both are drawn last in `Main`, in the bin's order, the top bar counts them, and one Undo ignores both
  again

### Requirement: Edit mode offers a clip's edits in a menu

In Edit mode a clip's menu SHALL be headed by the clip's name and list four groups: Rotate left and Rotate right;
Cut at playhead and Use frame as poster; Move to «chapter» for each other chapter the Timeline draws; Ignore clip.
Each item SHALL make the draft edit its Clip tab control makes (Move to: a drop on that chapter's band, at its end),
announced as there and undone in one step. The Clip tab SHALL keep all of these controls.

Opened from the clip's row in the bin, the menu SHALL be the same menu. For a clip the track does not draw, Cut at
playhead and Use frame as poster SHALL be unavailable with the reason "The Timeline does not show <name>.". The last
group's item SHALL follow the clip's status: Ignore clip for a clip a chapter plays, **Include clip** for an ignored
clip (Rotate and Move to then unavailable, "Include <name> first."), and **Remove from reel.yaml**, or **Undo
remove**, for a missing clip (Rotate and Move to then unavailable, "<name> is not on disk."). Each makes the edit its
Clip tab control makes.

Opened on a clip that is one of two or more selected clips, the menu SHALL act on every selected clip it applies to:
it SHALL be headed by their count ("3 clips"), list Move to «chapter» for every chapter the Timeline draws, and name
the count in Ignore ("Ignore 3 clips"). Each item SHALL then make the edit the Clip tab makes for several clips ("The
Clip tab acts on several selected clips"), in one Undo step; it SHALL list "Include N clips" when N of them are
ignored. Cut at playhead and Use frame as poster SHALL be unavailable, with the reasons "Select one clip to cut at the
playhead." and "Select one clip to use a frame as poster.".

#### Scenario: The menu of a clip in Kvällen
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator opens the menu of `s1710002.mp4`, drawn in `Kvällen`
- **THEN** it is headed "s1710002.mp4" and lists Rotate left, Rotate right, Cut at playhead, Use frame as poster,
  Move to Main and Ignore clip, in that order, with a separator between the groups

#### Scenario: Rotate right from the menu
- **WHEN** the operator chooses Rotate right in the menu of `s1710002.mp4`
- **THEN** the clip is turned a quarter right on the track and in the picture, the turn is announced once, nothing
  is written, and Undo says "Undo rotation of s1710002.mp4"

#### Scenario: Move to another chapter
- **WHEN** the operator chooses Move to Main in the menu of `s1710003.mp4`
- **THEN** `s1710003.mp4` is drawn as the last clip of Main, after `s1710001.mp4`, "Moved s1710003.mp4. At the end of
  Main." is announced, the top bar says "1 clip moved", and Undo says "Undo move of s1710003.mp4"

#### Scenario: Cut at the playhead
- **WHEN** the playhead is at 0:02.00 of `s1710002.mp4`, which has no cuts, and the operator chooses Cut at playhead
  in its menu
- **THEN** the draft has a cut of that clip from 2.0 to 3.0 s, the cut "+ Cut at playhead" in the Clip tab makes,
  and the top bar says "1 cut added"

#### Scenario: Ignore from the menu
- **WHEN** the operator chooses Ignore clip in the menu of `s1710002.mp4`
- **THEN** it is no longer drawn, the bin lists it as ignored, and the top bar says "1 clip ignored"

#### Scenario: One chapter, no Move to
- **WHEN** the Timeline draws a single chapter and the operator opens a clip's menu
- **THEN** the menu has no Move to item

#### Scenario: The menu of three selected clips
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the clips `s1710001.mp4`, `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4` are selected and the operator right-clicks `s1710002.mp4` and chooses Rotate right
- **THEN** the menu was headed "3 clips", listed Move to Main and Move to Kvällen and "Ignore 3 clips", and showed
  Cut at playhead unavailable under "Select one clip to cut at the playhead."; all three clips are turned a quarter
  right, and one Undo turns them back

#### Scenario: The menu of an ignored clip's row
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator right-clicks the bin row of the ignored `s1710004.mp4`
  and chooses Include clip
- **THEN** the menu was headed "s1710004.mp4", listed Include clip in place of Ignore clip, and showed Rotate left
  unavailable under "Include s1710004.mp4 first."; the clip is drawn last in `Main`, and Undo says "Undo include of
  s1710004.mp4"

#### Scenario: The menu of a missing clip's row
- **WHEN** on `2024-09-01 - Sommarlov` the operator focuses the bin row of the missing `borttagen.mp4`, presses
  Shift+F10 and chooses Remove from reel.yaml
- **THEN** the clip is removed as "Edit mode removes a missing clip from reel.yaml on request" says, keyboard focus is
  back on its row, and its menu now offers Undo remove

#### Scenario: Several clips moved from the menu
- **WHEN** the same three clips are selected and the operator chooses Move to Main in the menu
- **THEN** `Main` draws `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4` in that order, and "3 clips moved to
  “Main”." is announced

### Requirement: Edit mode adds, renames, reorders and deletes chapters

In Edit mode the operator SHALL be able to change the event's chapters themselves, in the Event tab's Chapters list
("The Event tab lists the event's chapters"). Every control below SHALL be reachable with the keyboard and SHALL name,
to assistive technology, the chapter it acts on.

- **Add chapter**, after the last chapter of the Chapters list, SHALL ask for a name and add an empty chapter with
  that name at the end.
- **Rename** SHALL be done in the title card editor, in its Name field ("The title card editor holds every
  name and every title-card setting"), by the one workflow for every chapter. A chapter's row in the Chapters list
  SHALL show its name as plain text: not a
  button, with no pencil and no hover or focus change, and pressing it SHALL do nothing. There SHALL be no Rename
  button, no inline name field and no dialog of its own for a name. The event's own chapter (the default chapter,
  whose clips are the event folder's) has no name to rename: it is headed `Main` or `Clips` ("The event's own chapter
  is headed ..." below), its title card shows the event's title, and its Name field edits that title. Clips without a
  chapter of their own join it. While the event lists other chapters, the page SHALL say this in the Clips help ("Each explanation sits behind a Help toggle of its section"), not as a line beside the chapter.
- **Move up** and **Move down** SHALL move a chapter one place among the chapters, and SHALL be offered only
  while the event lists more than one chapter. After such a move, keyboard focus SHALL stay on the pressed
  control. At either end, the control that cannot move further SHALL say that it is unavailable.
- **Delete** SHALL remove a chapter only once it plays no clip. Its clips must first be moved to another
  chapter, or removed when missing. The event's own chapter can be deleted only when, in addition, it lists no
  ignored clip that the page would list under it again after the save: one from the event folder, or from a
  folder no chapter is named after. Such a clip would bring the chapter back, holding only ignored clips.
  When a chapter cannot be deleted, pressing Delete SHALL change nothing and leave focus on Delete. The page
  SHALL show and announce why the chapter cannot be deleted.

**The row.** Every chapter's row in the Chapters list, the event's own chapter's too, SHALL hold, in this order, the
chapter's name as plain text, the chapter's clip count, an **Edit Titlecard** button and the chapter's tools (Move up,
Move down, Delete, offered by the rules above). Edit Titlecard, Move up, Move down and Delete SHALL show an icon only,
keep their names and reasons, and offer their names (Edit Titlecard: its words) as tooltips. With a fine pointer a
row SHALL be one line at most 36 CSS pixels tall in the inspector; with a coarse pointer it keeps the 44 CSS pixel
targets and wraps onto a second line. The Edit Titlecard button SHALL be named "Edit title card for <name>" (the
event's own chapter: its heading) and SHALL select that card, showing its editor on the inspector's "This title card"
tab ("The title card editor is docked in the inspector"). A chapter's row SHALL show nothing under its line but the
notes of this requirement and of "Edit mode says what a chapter's name means for clips added later": no card row, no
"Main title card" line, no source line ("from the folder name"). The bin SHALL hold no chapter heading and no
chapter tool: its rows name each clip's chapter. A chapter added in the draft has no saved card, and its
button SHALL be offered all the same and keeps the preview from the draft. While the Timeline draws a card built from the event's cards for it ("A chapter added while editing gets the event's card on the Timeline"), the editor SHALL say that until Save its title card is drawn as the event's and that its own settings can be changed after Save; otherwise it SHALL say that its card is drawn after Save.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up or Move down, so that an event never saves without a chapter.

**Focus after the selection leaves the card.** When Escape clears the card selection from inside the editor, keyboard focus SHALL
return to the control that selected the card (the chapter's Edit Titlecard button in the Chapters list, which the Event tab then
shows, or the card block on the Timeline), so that the focused field never
unmounts onto the page body. Selecting something else leaves keyboard focus where the operator put it.

**The Name field.** In the editor the field SHALL be the first of "This title card" and SHALL be named "Name of chapter <name>"
for a chapter and "Title of the event" for the event's own chapter, where <name> is the name the draft holds when the editor opens. The
chapter's row, the bin's rows that name it and the editor's title name the chapter by its name alone.

- An accepted name SHALL be written to the draft as it is typed, so that the editor's heading, its preview, the bin's
  rows that name the chapter, its row in the Chapters list and every chapter picker follow it. A name equal to the chapter's current name, once the spaces
  around it are removed, SHALL change nothing. A rename SHALL be announced once, when keyboard focus leaves the field or the selection leaves the card, and not for each key; typing a name and typing the old one back announces nothing.
- A refused name SHALL be explained under the field in words, in a `role="alert"` that is remounted for each refusal, and the
  field SHALL be marked invalid. The draft keeps the last accepted name, and the field keeps the typed text. Enter, with a refused
  name in the field, SHALL keep the field invalid and announce the refusal. Escape, and the selection of anything else, SHALL return the
  field's text to the draft's name and announce that the name was not changed and why; they SHALL NOT keep a refused name.
- While the field holds a refused name, Ctrl+S SHALL save nothing and SHALL say "Not saved: the name is refused."
- While a save or a move of several clips is pending, the field and the editor's other fields SHALL say that they are unavailable
  and SHALL change nothing (the busy-control rule); the row's Edit Titlecard button SHALL say so too and select nothing.
- Reset, a conflict and Overwrite SHALL treat a name as any other edit; Reset SHALL restore the chapters' names as read.

**The event's own chapter's name is the event's title.** For the event's own chapter the Name field SHALL edit the draft's
title, the one the Details form's Title field edits, in step with it in both directions, counted once in the save bar ("Title") and
undone by Reset as one edit.

- The field SHALL hold the draft's title. While that is blank it SHALL be empty with the title the page resolved from the folder
  name as its placeholder and the words "From the folder name", else the word "Untitled". The page SHALL NOT guess a title.
- Any text SHALL be kept as the title, with no rule of the page's. A blank title means that it inherits from the folder name, and
  the field SHALL say so in the words of the Details form ("Left empty: inherits from the folder name when saved"). The
  service's refusal of an unusable title stays at the Details form and is retired by editing the title in either place.
- While the draft's title differs from the title read, the editor SHALL say that saving changes the movie's file name, that if the
  movie was already rendered the next render saves it under the new name, and that the movie under its old name stays on disk. It SHALL NOT name a
  file: the event page names them after the save, from the verdict.
- The card's heading follows the name. A card that has its own title ("Card title (overrides the name)") keeps it.

When the browser's primary pointer is coarse, each of these controls, the row's Edit Titlecard button, Add chapter and Undo SHALL take a tap
anywhere in an area of at least 44 × 44 CSS pixels around it that reaches no other control, as every button
does ("Every control is large enough to touch").

A name SHALL be accepted only when both of these hold, once the spaces around it are removed. The spaces are
the characters the engine removes from a chapter's name, so a name the page accepts is a name `reel.yaml`
loads:

- it is not empty
- compared by full Unicode case folding, the comparison the engine makes, it differs from the name of every
  other chapter of the event, including a deleted chapter not yet saved, and from `Main`, the name the page
  shows for the event's own chapter. So `ß`, `ss`, `SS` and `ẞ` are one name, as are `Kvällen` and `KVÄLLEN`.

A refused name SHALL be explained at the name field, which keeps keyboard focus when the name was asked for
with Enter or in the Add chapter dialog, and nothing SHALL change. The
name saved is the accepted name without the spaces around it. A chapter's name SHALL be described to the
operator as the words on its title card in the movie.

A chapter the page showed when Edit mode opened SHALL, once deleted, stay listed in its place in the Chapters list
until the edits are saved, marked as deleted when the edits are saved; the bin SHALL no longer list it. It lists none
of its clips. Such a chapter offers an **Undo** control that returns it to its place, and keyboard focus SHALL move to that Undo. A
chapter the operator added in this Edit mode and then deletes SHALL simply be gone. A chapter that plays no
clip SHALL say so in its row, and that a chapter without clips is left out of the movie. While the event
lists another chapter, a deleted one aside, the row SHALL also say that clips can be moved into it with Move to…
(the Clip tab's, or a clip's menu). When it is the only
chapter listed, a deleted one aside, it SHALL NOT say that: no other chapter has a clip to move.

The event's own chapter SHALL be headed `Main` while any other chapter is listed, a deleted one aside, and
`Clips` otherwise, as on the event page. Every change to the chapters SHALL count as an unsaved edit, like a
move:

- it SHALL be announced
- Reset SHALL restore the chapters as read
- leaving with it unsaved SHALL ask first
- the save bar SHALL count it ("Saving an edit writes only what the operator changed")

While a save is in flight, every chapter control and Add chapter SHALL say that it is unavailable and SHALL
change nothing when pressed.

#### Scenario: A chapter's header in the bin is one row
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window with a fine pointer, with
  nothing selected
- **THEN**
  - the bin holds no chapter heading, and its rows name `Kvällen` beside each of its clips
  - the Event tab's Chapters list has a row for `Kvällen` holding, in this order, its name, its clip count, and icon buttons named "Edit title card for Kvällen", "Move chapter Kvällen up", "Move chapter Kvällen down" and "Delete chapter Kvällen", each offering its name as a tooltip
  - that row is one line at most 36 CSS pixels tall

#### Scenario: A first chapter added to a one-chapter event
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter, the
  operator presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** a chapter `Kvällen vid grillen` is listed last in the Chapters list, saying that it plays no clip and
  that clips can be moved into it with Move to…; the first chapter's row and the bin's rows of its clips read
  `Main` instead of `Clips`; keyboard focus is on the new chapter's row; the addition is announced; and the save
  bar says "1 chapter added"

#### Scenario: A lone chapter offers only Add chapter
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter
- **THEN** its one chapter offers no Move up, Move down or Delete, its row shows `Clips` as plain text with an Edit Titlecard
  button (the editor's Name field edits the event's title), and the Chapters list offers Add chapter after it

#### Scenario: A name already taken, or no name, is refused
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named `kvällen`, then one named
  only with spaces, then one named `main`
- **THEN** each is refused at the name field, which keeps keyboard focus. `kvällen` is refused because a
  chapter called `Kvällen` exists. The blank name is refused because a chapter needs a name. `main` is refused
  because `Main` is the page's name for the event's own chapter. No chapter is added.

#### Scenario: A name the engine would fold into another is refused
- **WHEN** on `2024-09-14 - Gatufest`, an event with a chapter `Straße`, the operator adds a chapter named
  `STRASSE`, then one named `strasse`
- **THEN** each is refused at the name field, which keeps keyboard focus, because a chapter called `Straße`
  exists. No chapter is added. A name that merely resembles it, such as `Strasse 2`, is accepted.

#### Scenario: The spaces the engine removes are removed
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named with a next-line character
  (U+0085) before and after `Hamnen`
- **THEN** the chapter is added as `Hamnen`, without those characters, and the next save writes `Hamnen` to
  `reel.yaml`, which loads

#### Scenario: Renaming a chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses "Edit title card for Kvällen"
- **THEN** the inspector shows the Title card tab on "This title card" with keyboard focus in the Name field, named "Name of chapter Kvällen" and holding
  `Kvällen`; the bin's rows of its clips name `Kvällen` as plain text with no pencil
- **WHEN** the operator selects the name, types ` Kväll på stranden `, with spaces around it, and presses Enter
- **THEN** the field holds the name, the card stays selected, the heading reads `Kväll på stranden`, the rename was announced once, and the save bar says that 1
  chapter was renamed. The chapter offers no Rename button and its name is not pressable.

#### Scenario: Renaming with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator tabs to "Edit title card for Kvällen", presses Enter, types `Kväll`
  in the Name field and presses Escape
- **THEN** the chapter is named `Kväll` (an accepted name is already in the draft), nothing is selected, the inspector shows the Event tab, keyboard focus is on the chapter's Edit Titlecard button in its Chapters list, and the next Tab reaches the chapter's Move up

#### Scenario: Main and a chapter are edited alike
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens "Edit title card for Main" and then "Edit title card for Kvällen"
- **THEN** each shows the same editor on "This title card" with the Name field first; Main's is named "Title of the event" and holds
  `Två kapitel`, Kvällen's "Name of chapter Kvällen"; neither row has a pencil, a card row, a "Main title card" line or a
  "from the folder name" line

#### Scenario: Leaving the field keeps an accepted name
- **WHEN** the operator selects the card of `Kvällen`, types `Kväll` in the Name field, and presses Tab
- **THEN** the chapter is named `Kväll`, keyboard focus is on the control after the field and not back in it, the card stays selected, and the rename is announced once

#### Scenario: Escape drops what was typed
- **WHEN** the operator selects the card of `Kvällen`, types `main` in the Name field, and presses Escape
- **THEN** nothing is selected, keyboard focus is on the chapter's Edit Titlecard button, the chapter is named `Kvällen`, "Name not changed" with the reason is announced, and the page shows no unsaved changes

#### Scenario: Pressing the title and changing nothing
- **WHEN** the operator types `Kväll` in the Name field of `Kvällen` and then `Kvällen`, with spaces around it, and presses Escape
- **THEN** the chapter is named `Kvällen`, nothing is announced or counted as an edit, and the page shows no unsaved changes

#### Scenario: A refused rename keeps the field open
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `main` in the Name field of `Kvällen`
- **THEN** the field stays as typed, is marked invalid and explains under it that `Main` is how the page names the event's own chapter; the
  refusal is announced, and the draft still holds `Kvällen`. Typing `Morgon` removes the refusal and the chapter is named `Morgon`.
- **WHEN** the operator types `main` again and presses Enter
- **THEN** the card stays selected, the field is still marked invalid, and the refusal is announced
- **WHEN** the operator presses Escape
- **THEN** nothing is selected, keyboard focus is on the chapter's Edit Titlecard button, the chapter is named `Morgon`, the last name accepted, and "Name not changed" with the reason is announced

#### Scenario: A refused name is not lost when focus leaves
- **WHEN** the operator types `main` in that field and presses Tab
- **THEN** the field stays as typed with its refusal, keyboard focus is on the control after it, and the chapter is still named `Kvällen`

#### Scenario: An empty name, and a name already taken
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator selects its card, deletes the name,
  and then types `KVÄLLEN`
- **THEN** the first is refused because a chapter needs a name, and the second because a chapter called `Kvällen` exists, each in
  the words Add chapter's dialog uses for the same name

#### Scenario: One field at a time
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator renames `Kvällen` to `Kväll` in its editor, and presses "Edit title card for Morgon"
- **THEN** only the card of `Morgon` is selected, the bin's rows of `Kvällen`'s clips name it `Kväll`, and the save bar counts the one rename

#### Scenario: A name typed and not kept holds Save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator changes the title in the Details form, selects the card of `Kvällen`,
  types `main` and presses Ctrl+S
- **THEN** nothing is saved and "Not saved: the name is refused." is announced. After the operator types `Kväll`, presses Escape and then
  Ctrl+S, one save is sent and carries both edits.

#### Scenario: Reset closes the field
- **WHEN** the operator renames `Kvällen` to `Kväll` in its editor, and presses Reset
- **THEN** the chapter's row reads `Kvällen`, the page shows no unsaved changes, and "Edit title card for Kvällen" shows an editor whose Name field holds `Kvällen`

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` has no chapter rename and says that it has no name of its own because its title card shows the event's title; its
  row shows `Main`, an Edit Titlecard button and no other title control

#### Scenario: Renaming the main title card edits the event's title
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in which one chapter is listed, and the operator opens "Edit title
  card for Clips" and types `Grillkväll med grannarna` in the field named "Title of the event"
- **THEN** the Details form's Title field holds the same, the editor's preview shows it, the save bar says "Title" changed, and the
  editor says that saving changes the movie's file name and names no file. The chapter is still headed `Clips`.
- **WHEN** the operator types `Grillkväll` in the Details form's Title field and selects the card again
- **THEN** the Name field holds `Grillkväll`
- **WHEN** the operator saves
- **THEN** one `PUT` is sent whose metadata title is `Grillkväll` and whose chapters and clips are as read, and the editor no longer says anything about
  the file name

#### Scenario: Emptying the main title card
- **WHEN** the operator deletes the text of the Name field of `2024-06-27 - Grillning med grannar`, which reads `Grillning med grannar` from `reel.yaml`
- **THEN** the field says "Left empty: inherits from the folder name when saved", shows the title resolved from the folder name as its
  placeholder with "From the folder name", and the Details form's Title field is empty with the same hint

#### Scenario: The main title card with no title at all
- **WHEN** the page has no title for the event, in `reel.yaml` or resolved from the folder name
- **THEN** the field is empty with the placeholder "Untitled"

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
- **THEN** `Kvällen vid grillen` has a Name field in its editor, but no Delete, Move up or Move down, and the save bar
  says that 4 clips moved, 1 chapter was added and 1 chapter deleted

#### Scenario: Chapter controls on a phone
- **WHEN** the operator opens Edit mode on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area around each of `Kvällen`'s Edit Titlecard, Move up, Move down and Delete, and
  around `Main`'s Edit Titlecard and Add chapter, reaches that control and no other (centred on each, except
  that the areas of Move up and Move down meet at the edge they share), and the page does not scroll
  horizontally

#### Scenario: Chapter controls wait for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a rename pending, the operator presses Save, and the
  service has not answered yet
- **THEN** Add chapter and every chapter's Edit Titlecard, Move up, Move down and Delete say that they are unavailable, and
  pressing them changes nothing and opens nothing

#### Scenario: A lone empty chapter does not point at Move clips
- **WHEN** Edit mode opens on `2024-10-05 - Tom mapp`, an event whose folder holds no clip, and the operator
  presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** the new chapter's row, the only chapter listed, counts 0 clips, and it says "No clips. A chapter without
  clips is left out of the movie." It does not mention moving clips into it.

#### Scenario: A lone chapter whose only clip is ignored
- **WHEN** Edit mode opens on `2024-10-06 - Bara ignorerad`, an event that lists one chapter, whose only clip
  `s1710004.mp4` is ignored
- **THEN** the bin lists the ignored clip, and the chapter's row counts 0 clips and says "It plays no clip. A chapter without
  clips is left out of the movie." It does not mention moving clips into it.

#### Scenario: A second chapter brings the hint back
- **WHEN** on `2024-10-05 - Tom mapp`, with `Kvällen vid grillen` added, the operator presses Add chapter,
  types `Morgonen` and confirms
- **THEN** both chapters' rows say that they have no clips and that clips can be moved into them with Move to…
- **WHEN** the operator then deletes `Morgonen`
- **THEN** `Kvällen vid grillen` says again, as it did before the addition, that it has no clips and is left
  out of the movie, without mentioning moving clips into it

### Requirement: Each explanation sits behind a Help toggle of its section

The event page, in the read view and in Edit mode, SHALL keep instructional and explanatory text out of sight until asked for, and SHALL keep in sight every text that reports a state or needs an action. Each of these sections SHALL have **one** Help toggle in its header, a button named "Help" with an information icon: **Details** (Edit mode), **Poster** (Edit mode), **Timeline** (the read view and Edit mode), **Clips** (Edit mode: the bin's heading row, above its list) and the **Title cards** tab of the title card dialog. A section with no such text SHALL have no toggle.

The toggle SHALL be a `button` with `aria-expanded` and `aria-controls` naming its panel, operable by Enter and Space, with a target at least 44 CSS pixels high and wide (the Clips toggle in the bin from 960 CSS pixels wide with a fine pointer is the one exception: a 32 CSS pixel square showing its icon alone, with the same name and the tooltip "Help: Clips"), and with a visible focus ring. Pressed, it SHALL show the panel under the header: a calm, muted block that is not an alert, holds the section's explanations as paragraphs, and moves nothing above it. The panel SHALL stay in the document when closed (`hidden`), so that a control it describes keeps its `aria-describedby`. Closed is the default. Each section's state SHALL be kept per section (not per event) in `localStorage`, read when the section mounts, written when the toggle is pressed, and every access SHALL be guarded: a browser that refuses storage, or throws, SHALL leave the toggle working for the page visit, closed at the start, and SHALL show no error. The Timeline's state SHALL be one state for both modes.

Every text of these classes SHALL be in a panel and SHALL NOT be shown as a line of its own: the Details form's lead ("What reel.yaml says…", "Save writes these to reel.yaml…"), the Poster's "Pick the frame on the Timeline…", the Timeline's note that cards fade ("The Timeline fades a card…"), the note that dismissed suggestions return on reload, the cut fields' hint ("Enter takes a time; Escape puts the old one back"; the fields keep it as their `aria-describedby`), the Clips instructions ("Press a clip to select it…", "The event's own chapter: …", "Ignored clips are not played; drag one onto the Timeline to include it", "A missing clip is not on disk…", "A new clip joins reel.yaml once its chapter’s order, one of its cuts, or the list of chapters is saved." while a new clip waits), the command that analyses an event (`auto-reel analyze <root>`, then Refresh), and the title cards tab's lead ("Every title card of this event follows these…"). The text SHALL be the same words as before. The classes that SHALL stay visible are: a refusal, an error or a warning; an unsaved or pending change and what saving will add ("Saving adds 2 new clips to reel.yaml"); a count ("1 ignored clip, not played"); the state words of a clip (in the workspace's clip bin with a fine pointer, as the status icon with its words kept as hidden text and tooltip, see "State is never shown by color alone"), a chapter, the poster and the render; a field's inherited-value hint; a reason an unavailable control gives (see "The Clip tab acts on several selected clips"); the icon legend of the analysis lane; and the empty states of a chapter. Controls, fields, their names and what pressing them does SHALL NOT change.

#### Scenario: A section's help is closed, opens and closes
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` with nothing stored
- **THEN** the Details, Poster, Timeline and Clips sections each show a Help button with `aria-expanded="false"` and no explanation is visible
- **WHEN** the operator presses the Clips Help button, by mouse and again by keyboard
- **THEN** `aria-expanded` is `true` and "Press a clip to select it…" is visible under the header; pressing it again hides the panel, which stays in the document

#### Scenario: The state persists across a reload
- **WHEN** the operator opens the Timeline help, reloads the page, and then opens the same event in the read view
- **THEN** the Timeline help is open in both, and the other sections' help is closed

#### Scenario: Storage that throws
- **WHEN** `localStorage` throws on every access
- **THEN** every Help button works for the page visit, starts closed, and no error is shown

#### Scenario: Action and state stay visible
- **WHEN** an event with a missing clip, with an unsaved edit and with an event that needs a render is opened in Edit mode with every help closed
- **THEN** the missing clip's status, the "Needs render" state with its reason, the save bar's unsaved changes and the bin's count of ignored clips are visible, and the explanations are not

#### Scenario: Fewer paragraphs of explanation
- **WHEN** `2024-08-20 - Två kapitel - Tjörn` is opened in the read view and in Edit mode, in Chrome and in Firefox, light and dark, at 1280 and 390 px, with every help closed
- **THEN** the number of visible paragraphs of instructional text is lower than before the change in each, the numbers are reported, and nothing overflows horizontally

#### Scenario: A toggle is large enough to touch
- **WHEN** any Help button is measured at 390 px
- **THEN** it is at least 44 CSS pixels high and wide, and it has an accessible name that names its section

### Requirement: Edit mode's clip list draws only the rows near the view, without moving the page

The bin SHALL let the browser skip drawing the clip rows that are far out of view (CSS `content-visibility: auto`
on each row), giving every row not yet drawn a block size close to a drawn row's and every row once drawn the size it
was drawn at, so that the bin's scroll height and the place of what is in view do not change as rows come into view.
The bin's rows fit its width, so they SHALL be skipped at every width the bin has. Every row SHALL stay in the
page while skipped: reached by the list's keys, read by assistive technology, found by the browser's find in page,
and part of the bin as a drop target for a clip dragged off the track.

Rows coming into view SHALL NOT move the bin: while the operator scrolls it, the row at the top of the view SHALL
keep its place to within 1 px apart from the scroll itself. The bin's scroll height after the whole list has been
scrolled through once SHALL differ from its height on opening by at most 5 %.

Nothing a row draws outside its own box SHALL be cut off by the skipping: the row's focus ring and its selected
look SHALL be drawn whole, in the light and the dark scheme. Selecting rows, a row's menu, dragging an ignored row
onto the track and moving clips SHALL work on skipped rows as on drawn ones; after a move, every row SHALL be drawn and
take clicks where it now is, never where it was.

#### Scenario: Scrolling a 400-clip list moves nothing
- **WHEN** the bin shows an event of 400 clips in one chapter at 1280 × 720, and the bin is scrolled from the top to
  the bottom in steps of half a view, waiting two frames after each step
- **THEN** after each step the top row in view is where the step put it to within 1 px, the scroll height at the
  end differs from the scroll height on opening by at most 5 %, and the rest of the workspace has not moved

#### Scenario: A drag to the end of a long list lands where it was shown
- **WHEN** an event lists 400 clips and ignores a 401st, listed last in the bin, and the operator scrolls the bin to
  that row, drags it onto the track and releases it where the line says "Before c0001.mp4"
- **THEN** the clip is included first in its chapter, as the line showed, the draft's order says so, and its row is
  now drawn first in the bin

#### Scenario: Keyboard reorder far down the list
- **WHEN** the operator presses End in the bin's list of a 400-clip event, Enter, and then Move earlier in the Clip
  tab
- **THEN** the clip is one place earlier, the announcement names its new place, and its row, never drawn before, is
  in view in the bin with its selected look whole

#### Scenario: Nothing is cut off
- **WHEN** a row has keyboard focus, or is selected, in the light and the dark scheme
- **THEN** the focus ring and the selected look are drawn whole

#### Scenario: A skipped row is still found
- **WHEN** the operator moves down the bin's list with Down, or searches the page for the name of the 390th clip
- **THEN** each row is reached in order and the 390th clip's row is scrolled into view and shown

#### Scenario: A moved row takes its clicks where it is
- **WHEN** two selected clips are dragged on the track to the top of another chapter in Chrome, so that the bin's
  rows below their new place move down
- **THEN** a click on a moved row selects that row's clip, and no other row takes the click

### Requirement: Edit mode keeps keyboard focus in view and never drops it

After the operator drops, moves, removes or restores a clip in Edit mode, from the keyboard or with a
pointer, the control that holds keyboard focus SHALL be fully visible, and the clip's row SHALL be scrolled whole
into the bin's view without taking focus. No part of a row that holds focus SHALL be covered or cut off by the
edge of the bin; the bin scrolls, the rest of the workspace does not.

Suppose Edit mode's read of the editorial document failed and the operator presses **Try again**. Then:

- the failure SHALL stay shown while the document is read again
- Try again SHALL keep keyboard focus, and SHALL show that it is busy until the read answers
- when the read fails again, focus SHALL stay on Try again, and the failure SHALL be announced again
- when the read succeeds, focus SHALL move to the heading of the event's fields
- when the event changed on disk in the meantime, focus SHALL move to the control that reads the event
  again

Focus SHALL never fall to the page's body.

When a save is answered, the control that then holds keyboard focus SHALL be fully inside the window.

#### Scenario: The first keyboard drop keeps the dropped clip in view
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with no other edit and in a window
  1280 × 720, the operator selects its first clip, `s1710001.mp4`, in the bin's list with the keyboard and
  presses Move later in its Clip tab
- **THEN** the top bar says "Unsaved", keyboard focus is on Move later, fully visible, and the clip's whole row
  is visible in the bin

#### Scenario: The first drop at phone width
- **WHEN** the operator does the same in a window 390 × 844 with the third clip, `s1710003.mp4`
- **THEN** Move later is fully visible, and the clip's whole row is visible in the bin

#### Scenario: A tall row dropped into another chapter
- **WHEN** in a window 1280 × 720 on `2024-08-20 - Två kapitel - Tjörn`, the operator moves
  `Kvällen/s1710002.mp4` into `Main` with Move to… in its Clip tab
- **THEN** keyboard focus is on Move, and the clip's row, now named for `Main`, is fully visible in the bin

#### Scenario: A conflict in a short window scrolled to its top
- **WHEN** in a window 320 × 568, the operator has changed the location of
  `2024-06-27 - Grillning med grannar`, presses Save, and the save is answered with a conflict
- **THEN** Save keeps keyboard focus and is fully inside the window, and so is the explanation's panel

#### Scenario: A drop far down a long bin
- **WHEN** the operator moves the last clip of a 400-clip chapter one place earlier with the Clip tab's Move
  earlier
- **THEN** its whole row is fully visible in the bin, and the page has not scrolled

#### Scenario: Try again keeps focus while the document is still unreadable
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` became unparseable after its page was read,
  the operator enters Edit mode, and then presses Enter on Try again while the file is still unparseable
- **THEN** Try again shows that it is busy while the read runs, keyboard focus stays on Try again
  throughout and afterwards, and the unparseable-document failure is announced again

#### Scenario: Try again moves focus to the fields once the read succeeds
- **WHEN** after that, the file is repaired and the operator presses Enter on Try again
- **THEN** the event's fields and clip lists are shown, and keyboard focus is on the heading of the event's
  fields

### Requirement: Every control is large enough to touch

When the browser's primary pointer is coarse, such as a finger on a phone, each of these controls SHALL
take a tap anywhere in an area of at least 44 × 44 CSS pixels around it:

- every button
- every option of a segmented choice, such as the list's All / Needs render filter and the color-scheme
  control
- the header's link to the event list, and the event page's link back to it
- a notification's link

No control's area SHALL reach into another control, including two controls stacked one above the other.
In a table row of the list, the area of a control SHALL NOT reach above the top of its own cell, so that
it never covers the line that separates the row from the one above; the area stays 44 pixels tall by
reaching further below the control instead.
Making room for these areas SHALL NOT push text out of the box that holds it, or anything out of the header.
The color-scheme options are the one exception to the width: in a window narrower than 416 pixels the header
has no room for them beside the connection's state in words, and there each option SHALL take a tap in an
area 44 pixels tall and as wide as the option.

When the primary pointer is fine, such as a mouse, every control SHALL keep the size and place it has without
this rule.

#### Scenario: The list on a phone
- **WHEN** the operator opens the dev library's event list on a touch screen 390 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area centred on the Render of
  `2024-06-27 - Grillning med grannar`, on Refresh, or on each filter option reaches that control, a tap
  anywhere in an area 44 pixels tall and as wide as each color-scheme option reaches that option, and the page
  does not scroll horizontally

#### Scenario: The header keeps the connection's state in words
- **WHEN** the jobs connection is connecting, reconnecting, or live with jobs rendering and queued, and the
  operator opens the event list on a touch screen 384, 390, 412, 430, 480 or 528 pixels wide
- **THEN** the connection's state is in words inside its pill, clear of the color-scheme control, the header's
  content stays inside the header, and from 416 pixels a tap anywhere in a 44 × 44 pixel area centred on each
  color-scheme option reaches that option

#### Scenario: A row's Render keeps out of the row above
- **WHEN** the operator opens the dev library's event list on a touch screen 1280 pixels wide, where the
  events are table rows, and taps on the line that separates the `2024-06-27 - Grillning med grannar` row
  from the row above it
- **THEN** the tap does not reach the Render of `2024-06-27 - Grillning med grannar`, and a tap anywhere in
  a 44 pixel tall area as wide as that Render, whose top is no higher than the top of its cell, reaches it

#### Scenario: Two stacked buttons keep their own areas
- **WHEN** the operator saves Edit mode on `2024-06-27 - Grillning med grannar` on a touch screen 390 pixels
  wide, and the save is refused because the event was changed elsewhere
- **THEN** "Reload latest (discard my changes)" and "Overwrite with mine" are stacked, and a tap anywhere in a
  44 × 44 pixel area centred on either reaches that button and never the other

#### Scenario: Moving a clip by touch
- **WHEN** the operator opens Edit mode on `2024-06-27 - Grillning med grannar` on a touch screen 390 pixels
  wide
- **THEN** with `s1710002.mp4` selected, the Clip tab's Move earlier and Move later each take a tap anywhere in a
  44 × 44 pixel area of their own, and no tap meant for Move earlier reaches Move later

#### Scenario: A mouse sees no change
- **WHEN** the operator opens the event list, the page of `2024-06-27 - Grillning med grannar` and its Edit
  mode with a mouse, in windows 1280, 390 and 320 pixels wide
- **THEN** every control has the size and place it had before this rule

### Requirement: Edit mode names clips and the saved event as the other screens do

Edit mode SHALL name each clip by the rule the event page's table uses, applied to the chapter's current name
and to every clip the chapter lists now or listed when Edit mode opened. A chapter names a clip by its file
name while every one of those clips lies in the folder named like the chapter's current name (the event
folder, for the event's own chapter). Otherwise it names the clip by its path inside the event folder. So a
clip moved in and a new name take the names the table will give once saved, while a clip moved out or
removed renames nothing until the edits are saved. The same name SHALL be used in
these places:

- the clip's row in the bin
- the names of the controls that act on it: in its Clip tab and in its menu. A Clip tab button's name starts
  with its visible words and ends with the clip's name, as in "Move later: Kvällen/s1710004.mp4"
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
- **THEN** the bin names `Main`'s clips `s1710001.mp4` and `Kvällen/s1710004.mp4`, and its ignored clip
  `s1710004.mp4`, as the page's table named them, and with the second selected the Clip tab's Move later is named
  "Move later: Kvällen/s1710004.mp4"

#### Scenario: The saved event is named by its title and date
- **WHEN** the operator changes the location of `2024-06-27 - Grillning med grannar` in Edit mode and saves
- **THEN** the notification says the event was saved, and names it "Grillkväll med grannarna" with its date
  2024-06-27

#### Scenario: A clip moved in from another folder is named by its path
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710002.mp4` from `Kvällen` to `Main`
- **THEN** the bin names `Main`'s clips `s1710001.mp4` and `Kvällen/s1710002.mp4`, and its ignored clip
  `s1710004.mp4`, and with the second selected the Clip tab's Move earlier is named
  "Move earlier: Kvällen/s1710002.mp4"

#### Scenario: A renamed chapter names its clips by their paths
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `Kväll`
- **THEN** `Kväll` names its clips `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and `Kvällen/s1710004.mp4`, as
  the event page's table names them once the rename is saved

### Requirement: Edit mode's save bar is in the page before the first edit

Once Edit mode has read the editorial document, the top bar's save controls (the unsaved summary, Reset and Save)
SHALL already be part of the page, hidden for as long as there is nothing to save and no vanished event to
explain. The first edit SHALL show them. It SHALL NOT have to build them.

While they are hidden:

- they SHALL draw nothing, and the top bar SHALL NOT change its height when they show
- neither the keyboard nor assistive technology SHALL reach them: Tab SHALL NOT stop on Reset or Save, and the
  page SHALL NOT list a region named "Unsaved changes"

They SHALL be hidden again whenever nothing is left to save: when every edit is undone, and after Reset.
Showing them SHALL change nothing else about them.

The first edit SHALL cost no more than the next one. In a chapter that plays 400 clips, in a Chromium window
1280 × 900, the time from pressing Move later in the Clip tab of a selected clip to the next painted frame, for the
first edit made in Edit mode, SHALL be at most 50 ms longer than the same press for another clip as the second edit
made. The time
is the median of five runs, each in a fresh Edit mode.

#### Scenario: No save bar before the first edit
- **WHEN** in a window 1280 × 720, the operator opens Edit mode on `2024-06-27 - Grillning med grannar`, makes
  no edit, and presses Tab through every control of the workspace
- **THEN** no stop is on a Reset or Save, and the page lists no region named "Unsaved changes"

#### Scenario: The first edit shows the bar
- **WHEN** the operator then changes the title
- **THEN** the top bar shows "Unsaved", Reset and Save (which is its one primary action), and its summary names
  the changed title, and no pane has moved

#### Scenario: An undone edit hides the bar again
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator moves `s1710001.mp4` down one
  place, and then moves it up one place
- **THEN** the save controls were shown after the first move and are hidden after the second, and the page shows
  no unsaved changes

#### Scenario: The first edit in a 400-clip chapter
- **WHEN** in a window 1280 × 900, Edit mode is open on an event whose one chapter plays 400 clips, the
  operator selects the first clip and presses Move later, then selects the third and presses Move later, and the
  five runs are timed
- **THEN** the median time to the next painted frame of the first press is at most 50 ms longer than the
  second's

### Requirement: A trim made on the timeline is an edit of the same draft as a cut made in the Cuts panel

A cut changed on the Edit-mode Timeline ("Edit mode's cuts are trim handles") SHALL change the cut in the editor's draft, the one the clip's Cuts panel lists, and SHALL be saved, counted, guarded and undone as any other cut edit. There SHALL be no second list of cuts and no save path of the Timeline's own.

- **The cut keeps what it is.** A trimmed cut keeps its place in the clip's list, its number and its reason (a cut an analysis made keeps its reason; a trim does not make it `manual`). Only its start or end changes. The Cuts panel SHALL list the new times at once, and a cut trimmed back to the times it was read with SHALL leave nothing to save, so that an edit and its reverse show no save bar. A cut typed in the Cuts panel and then trimmed stays an added cut.
- **The save bar counts it.** The save bar SHALL say how many cuts were trimmed ("1 cut trimmed"), beside the cuts added and removed, counting a read cut whose saved start or end differs from the one read, on a clip whose saved cuts differ. A trim that leaves the saved cuts as they were SHALL count as nothing. Pressing Save SHALL send the same whole-document write under `If-Match` that every other edit sends, with the clip's changed `trims`: the service edits the span that changed in place and leaves the other spans, their comments and their style as authored ("A changed cut list edits only the spans that differ").
- **Guards and reset.** A trimmed cut SHALL make the event count as having unsaved changes (leaving Edit mode, navigating away and closing the tab ask first, Ctrl+S and Cmd+S save). Reset SHALL put every trimmed cut back to the times it was read with, and the Timeline SHALL show them.
- **A conflict.** When the save is refused because the event was changed elsewhere (412), the page SHALL show the conflict as for any edit, keeping the trims. "Reload latest (discard my changes)" SHALL discard the trims as it discards every edit (it leaves Edit mode and shows the event as read again; Edit mode entered again draws the cuts as saved), and "Overwrite with mine" SHALL write the trims over the latest.
- **Removed neighbours.** A removed cut is not a neighbour: a handle can be moved over the span of a removed cut. An Undo of that cut that would then overlap a cut is refused, as for a cut added in this Edit mode, and names the cut to remove first.
- **Past the clip.** The Timeline's clip length is its proxy's duration. A trim SHALL NOT write a cut that ends after it (a typed time past it is refused), and a cut read from `reel.yaml` that already ends after it is saved as read until its end is moved.
- **Nothing else is written.** Selecting a cut, moving the playhead, scrubbing, and a drag that was cancelled or that ended where it began SHALL write nothing and SHALL NOT count as an edit.

#### Scenario: A trim is saved as a change of one span
- **WHEN** on `2024-06-27 - Grillning med grannar`, `s1710001.mp4` has `trims: [{in: 1, out: 2.5, reason: black}]` with a comment on that line in `reel.yaml`, and the operator drags the cut's end to 3.5 s on the Timeline in Edit mode and presses Save
- **THEN** the save bar before saving says "1 cut trimmed", the write is one `PUT` under `If-Match`, and `reel.yaml` afterwards holds the same span with `out: 3.5`, `reason: black` and the comment, and nothing else changed

#### Scenario: A trim and its reverse leave nothing to save
- **WHEN** the operator trims a read cut's start from 1.0 s to 1.02 s with Right on its handle and then presses Left once on the same handle
- **THEN** the cut is back at 1.0 s, the Cuts panel lists it as read, and no save bar is shown

#### Scenario: A trimmed analysis cut keeps its reason
- **WHEN** a cut with the reason `freeze` is trimmed on the Timeline and saved
- **THEN** the span is written with the new times and the reason `freeze`

#### Scenario: The Cuts panel follows the Timeline
- **WHEN** the operator drags the start of cut 1 of `s1710001.mp4` to 0.5 s with that clip selected
- **THEN** its Cuts panel in the Clip tab lists cut 1 as 0:00.5 to 0:02.5, its cut summary reads the new summary, and the edit is announced

#### Scenario: Reset puts the trims back
- **WHEN** two cuts are trimmed and the operator presses Reset
- **THEN** the Timeline draws both cuts at the times they were read with, no save bar remains, and no handle is selected

#### Scenario: A conflict keeps the trims
- **WHEN** the event's `reel.yaml` was changed elsewhere after Edit mode read it and the operator saves a trim
- **THEN** the page says that the event was changed elsewhere since the operator started editing and offers "Reload latest (discard my changes)" and "Overwrite with mine", and the Timeline still draws the trim
- **WHEN** the operator presses "Reload latest (discard my changes)"
- **THEN** the page leaves Edit mode with no trim kept, no save bar remains, and pressing Edit again shows a Timeline that draws the cuts of the reloaded document

#### Scenario: Undo of a removed cut over a trimmed one
- **WHEN** cut 1 (1.0 to 2.5 s) is removed, cut 2 is trimmed to start at 2.0 s, and the operator presses Undo on cut 1
- **THEN** the Undo is refused in cut 1's row, naming cut 2 as the one to remove first, and cut 1 stays removed

#### Scenario: A look at a cut is not an edit
- **WHEN** the operator tabs through every handle, selects a cut, scrubs the playhead and starts and cancels a drag
- **THEN** no save bar is shown and leaving Edit mode asks nothing

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
- **WHEN** two ignored clips are selected in the bin and the operator drags one of their rows and releases it over the video track
- **THEN** nothing moves, the selection stays, and the live region says a group cannot be dropped on the video track and that Include clips in the Clip tab includes them

### Requirement: The event page shows the event's chapters and clips

An event's page SHALL show, from the event detail the service returns:

- the event's title, or its folder name when it has no title, with its date, location and description
  when present. When the heading shows a title that differs from the event's folder name, the page SHALL
  also show the folder name as secondary text, and SHALL give it to assistive technology as the heading's
  description, so that two events with the same title and date can be told apart.
- whether it needs a render, with every reason in words, or that it is up to date
- its latest job's status and time, when it has one
- counts of its clips, their total size, and its new, missing, excluded and ignored clips

The verdict and the latest job SHALL be shown together, in the one region that holds the page's render
controls, between the page's heading and its chapters. The clip counts SHALL be shown with the event's facts
under the heading, not between that region and the chapters.

Each chapter SHALL be shown as a table, in the order the service returns, with the default chapter's clips
under the label `Main` when the event also has named chapters. Each chapter SHALL first list the clips it
plays, in play order, each with its position in the chapter, numbered from 1. After them it SHALL list the
clips the event ignores, marked as ignored and with no position, because an ignored clip is not part of the
play order. A chapter's heading SHALL count the clips it plays, followed by the number of its ignored clips
when it has any. Every clip SHALL be listed with its name, its status in words, its size and its modification
time. A new, missing or ignored clip SHALL show its status as a status label. An included clip, the usual
case, SHALL show its status as quiet words with its icon, without a label's fill or edge, so that the other
statuses stand out. A clip the service reports without a size or time (a missing clip) SHALL show those as
absent, never as zero or a placeholder date. When `reel.yaml` lists clips that are missing from disk, the
page SHALL name them in a warning above the chapters, and SHALL mark each one that `reel.yaml` excludes as
excluded there. A clip that `reel.yaml` excludes SHALL be marked in its row, as "A clip that reel.yaml excludes
is marked as excluded" says.

A clip's name SHALL be its file name while every clip its chapter lists lies in the chapter's own folder
(the event folder, for the default chapter). A chapter that lists a clip from another folder SHALL name each
of its clips by its path inside the event folder, so that no two of its rows read alike.

The page SHALL read the event from the service when it opens and whenever the operator refreshes it. While
that read runs, the page SHALL show placeholders in the shape of what it will show: its heading, its facts
line, its render region, and clip rows laid out as the loaded rows are, each with its thumbnail box of the
loaded size. The heading SHALL show a placeholder, never a name that the read may replace, and SHALL still be
named by the event's folder name for assistive technology. The placeholders SHALL fit the window as the
loaded page does, without horizontal scroll from 320 CSS pixels up.

#### Scenario: Chapters and clips appear in play order
- **WHEN** an event has root clips and a `Kvällen` chapter
- **THEN** the page shows a `Main` table and a `Kvällen` table, each listing the clips it plays in the order
  the service returns, numbered from 1

#### Scenario: Every clip status is visible
- **WHEN** an event has an included clip, a NEW clip in a named chapter, a MISSING clip and an IGNORED clip
- **THEN** each is listed in its chapter with its status in words: the new, missing and ignored clips as
  status labels, and the included clip as the quiet word "Included" with its icon; and the counts line
  reports one new, one missing and one ignored clip

#### Scenario: An ignored clip has no position
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose `reel.yaml` ignores its root clip
  `s1710004.mp4`
- **THEN** `Main` lists `s1710001.mp4` at position 1 and then `s1710004.mp4`, marked as ignored and with no
  position, and `Main`'s heading counts "1 clip" and "1 ignored"

#### Scenario: A new clip the service lists after an ignored one is numbered before it
- **WHEN** the root folder of `2024-08-20 - Två kapitel - Tjörn` also holds a NEW clip `s1710009.mp4`, which
  the service lists after the ignored `s1710004.mp4` because it sorts after it on disk
- **THEN** `Main` lists `s1710001.mp4` at position 1, `s1710009.mp4` as new at position 2, and then
  `s1710004.mp4`, marked as ignored and with no position, as Edit mode's bin orders them: the clips a chapter plays
  before the ignored ones

#### Scenario: A clip from another folder is named by its path
- **WHEN** `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its root
  chapter and ignores the root clip `s1710004.mp4`, as a hand edit leaves it (a render adopts no ignored
  clip, D-12)
- **THEN** `Main` names its rows `s1710001.mp4`, `Kvällen/s1710004.mp4` and `s1710004.mp4`, and `Kvällen`
  still names its rows `s1710002.mp4` and `s1710003.mp4`

#### Scenario: Two events with the same title are told apart
- **WHEN** the operator opens `2024-07-14 - Kalas` and then `2024-07-14 - kalas`, both titled `Kalas`
- **THEN** each page's heading reads `Kalas` with the date `2024-07-14`, and each page also shows its own
  folder name, `2024-07-14 - Kalas` on the first and `2024-07-14 - kalas` on the second, which assistive
  technology reads as the heading's description

#### Scenario: A folder name that is the title is not repeated
- **WHEN** the operator opens `2024/Blandat`, whose title `Blandat` equals its folder name
- **THEN** the heading reads `Blandat`, and the page shows no separate folder name

#### Scenario: The render state reads as one region
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, which needs a render and whose latest
  job is rendered
- **THEN** "Needs render" with its reasons, the latest job "Rendered" with its time, and Render are shown
  in one region between the heading and the `Clips` table, and the line with its clip count and total size
  is shown under the heading

#### Scenario: The counts name the excluded clips
- **WHEN** the operator opens an event that lists three clips, one of which `reel.yaml` excludes
- **THEN** the facts line reads "3 clips" with the total size and "1 excluded", and the excluded clip is
  one of the three numbered rows

#### Scenario: A missing clip shows no invented facts
- **WHEN** `reel.yaml` lists `borttagen.mp4` and the file is not on disk
- **THEN** its row shows no size and no time, and a warning above the chapters names `borttagen.mp4`

#### Scenario: A stale event says why
- **WHEN** an event's `reel.yaml` was edited after its last render
- **THEN** the page shows that it needs a render, citing the edit in words

#### Scenario: A large event is fully listed
- **WHEN** an event holds 380 clips in one chapter
- **THEN** all 380 are listed, numbered 1 to 380

#### Scenario: A slow read keeps the page's shape
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide, and its read
  takes two seconds
- **THEN** during those seconds the heading shows a placeholder and no visible text, assistive technology
  names the heading `2024-06-27 - Grillning med grannar`, and each placeholder clip row is as tall as a
  loaded row; when the read answers, the heading reads `Grillkväll med grannarna` and the `Clips` table
  starts within 8 pixels of where the placeholder table started

## REMOVED Requirements

### Requirement: The clip bin holds the chapters' clip lists

**Reason**: The bin no longer lists chapters with their clips; it is one plain list.

**Migration**: "The clip bin lists every clip of the event as one plain list" lists every clip. Chapters are edited in the Event tab's Chapters list, and clips are moved on the track and in the Clip tab.

### Requirement: The bin's chapter headings and lists say what they hold

**Reason**: The bin has no chapter headings and no per-chapter lists.

**Migration**: Each row names its clip's chapter and position. The Chapters list counts each chapter's clips, and the bin captions its ignored and removed groups with their counts.

### Requirement: Edit mode drags clips between chapters

**Reason**: The bin is no longer a drag surface. A clip moves into another chapter by a drag on the track, Alt and an arrow at a chapter's edge, Move to… in the Clip tab, or the clip's menu.

**Migration**: Drag the clip's block on the track ("A clip is reordered by dragging it on the track"), or use Move to…. Touch and screen-reader users use the Clip tab's Move earlier, Move later and Move to….

### Requirement: Edit mode marks clips to move together

**Reason**: The selection of several clips (Ctrl/Cmd and Shift on the track and in the bin) replaces the marks, as the operator decided on 2026-11-18.

**Migration**: Select the clips with Ctrl/Cmd+click or Shift+click ("A clip is selected on the track or in the bin"). The marks were never saved, so nothing on disk changes.

### Requirement: Dragging a marked clip moves the whole marked group

**Reason**: A group is dragged on the track now, and the bin is not a drag surface.

**Migration**: Drag one of several selected clips on the track ("Dragging one of several selected clips moves them all").

### Requirement: Edit mode moves the marked clips to a chapter

**Reason**: Move to… acts on the selection, in the Clip tab and the clip's menu.

**Migration**: Select the clips and use Move to… ("The Clip tab acts on several selected clips"). It is the same edit: the clips join the end of the chosen chapter in play order.

### Requirement: The marks line is one aligned unit

**Reason**: The marks line, with Clear marks, Rotate marked and Move marked to…, is gone with the marks.

**Migration**: Rotate, Move to… and Ignore for several clips are in the Clip tab ("The Clip tab acts on several selected clips"). The bin's header holds the Clips help toggle and, while the player is hidden, Show player ("Edit mode previews a clip on request").

### Requirement: The event page reorders clips within a chapter

**Reason**: Edit mode has no chapter lists to reorder in. The rules that still hold are restated in "Edit mode opens on the event's editorial document and keeps the operator's edits" and "Edit mode moves clips on the track and in the Clip tab, and counts the fewest moves".

**Migration**: Reorder on the track (drag, Alt and an arrow) or with the Clip tab's Move earlier and Move later. Entering and leaving Edit mode is unchanged.
