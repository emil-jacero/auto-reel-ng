## ADDED Requirements

### Requirement: Edit mode previews a clip on request

In Edit mode, the Cuts panel of every clip that offers one (an included or new clip on disk) SHALL offer a
**Watch** control as the panel's first control. Pressing it SHALL open the clip's preview, a player for the
clip, in the panel, above the clip's cuts, and pressing it while the preview is open SHALL close it. The
control SHALL be named "Watch <name>", where <name> is the clip's name as its row names it, and SHALL say to
assistive technology whether the preview is open. While the preview is open, the control SHALL show that a press
closes it: its words SHALL be "Hide player", and its name "Hide player of <name>". The preview SHALL be a region
named "Player for <name>".

**From the row.** In Edit mode, the thumbnail of every clip that offers a Cuts panel SHALL also be a button
named "Watch <name>" that opens the same preview in one press. Pressing it SHALL show the clip's Cuts panel
when it is hidden, open the preview there, closing any other, and move keyboard focus to the preview's Play.
Pressing it while the preview is open SHALL keep the preview open and move keyboard focus to its Play. The
thumbnail SHALL keep its box, its size and its place in the row: being a button changes no row's size or
position. It SHALL NOT start a drag: the drag handle stays a control of its own, and a clip moves only by its handle or
its move buttons. A thumbnail that could not be shown (its "No preview" box) SHALL open the preview all the
same.

**What it plays.** The preview SHALL play the clip's own file as the service serves it from
`GET /api/v1/events/{event_id}/media?clip=<identity>`. The event id and the clip's full identity SHALL be
sent exactly as the event detail gives them, and the clip's modification time, exactly as the event detail
gives it, as `v`. Until it plays, the preview SHALL show the clip's thumbnail. It SHALL NOT start playing by
itself. A preview opened with Watch, from the panel or the thumbnail, SHALL stand at the clip's start, also
after an earlier preview of the clip was closed elsewhere in it. A clip displayed in portrait, such as a phone
clip whose container rotates it, SHALL be shown whole, turned as a player shows it.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media, and SHALL NOT create a
video element for it, before the operator opens that clip's preview. This SHALL hold for any number of clips,
for Cuts panels that are shown, and on entering, scrolling and leaving Edit mode. Closing a preview SHALL
stop its playback and any loading of its file.

**One at a time.** Opening a preview SHALL close any other clip's preview, so that Edit mode never holds more
than one video element. Edit mode SHALL show no movie player: the event's "Movie" section belongs to the read
view, which Edit mode replaces.

**Keyboard and focus.** Opening a preview SHALL move keyboard focus to its Play control. The preview's
controls SHALL come in this keyboard order, each reachable and usable by keyboard alone:
1. **Close**, named "Close the player of <name>"
2. **Play** / **Pause**, which says which it does
3. the **playhead**, a slider over the clip's length
4. **Skip cuts**
5. **Set From**
6. **Set To**

Each control SHALL name the clip as its row names it. Close, and Escape pressed while keyboard focus is in the
preview, SHALL close the preview and move keyboard focus to the control that opened it: the Watch control, or
the clip's thumbnail. Hiding the Cuts panel SHALL close its preview, leaving keyboard focus on the Cuts
control. No control of a closed preview SHALL keep focus.

**Play** SHALL be usable from the moment the preview opens. Pressed before the browser has read the clip, it
SHALL play the clip once the browser can. A preview opened with Watch, its thumbnail or Try again SHALL announce,
once, that the clip is ready to play, with its length.

**The playhead.**
- Space on it SHALL play or pause the clip, as Play does, and SHALL NOT scroll the page.
- It SHALL take the Left and Down arrows to step back 0.1 seconds and the Right and Up arrows to step on 0.1
  seconds. Page Down and Page Up SHALL step one second, and Home and End SHALL go to the clip's start and
  end. Each step SHALL stay within the clip.
- A press or a drag along it SHALL move to the time under the pointer.
- It SHALL say its value to assistive technology as the time and the clip's length, in the format the Cuts
  panel writes times (`0:01.234 of 0:06.02`), and SHALL add when the time lies inside a cut. While the clip
  plays, the value it says SHALL change at most once a second.
- Until the preview has read the clip's length, the playhead, Set From and Set To SHALL say that they are
  unavailable and change nothing.

The preview SHALL show the time and the clip's length in that same format.

**Sizes and look.**
- The picture SHALL be shown whole in a box of fixed 16:9 proportions, as wide as the panel allows up to 640
  CSS pixels and never taller than 360. The box SHALL have that size before the clip's file is read, so that
  nothing on the page moves when it is.
- In a window 320 pixels wide or more, the preview SHALL NOT make the page scroll horizontally.
- When the primary pointer is coarse, each of its controls SHALL take a tap anywhere in an area of at least
  44 × 44 CSS pixels around it, reaching no other control. The playhead SHALL take a tap across its whole
  width in an area at least 44 pixels tall.
- It SHALL follow the page's color scheme in both schemes. No state of it SHALL be shown by color alone.
- It SHALL animate nothing. The playhead moves only with playback or a seek.

**What the browser cannot do, by cause.** Each of these SHALL be shown in the preview as a note, never as an
alert, and announced once through Edit mode's live region. Keyboard focus SHALL stay in the preview, on
Close when the control that held it went:
- **No sound.** When the browser reports that it finds no audio it can play in the clip, the preview SHALL say
  that this browser finds no sound it can play in the clip, and that if a Sony camera recorded it, its sound
  is PCM, which Firefox does not play and Chrome does, and the render keeps it. The note SHALL NOT state as
  fact a cause or a sound the page does not know of: the clip may have no audio track at all. Playback SHALL
  be otherwise unchanged, never muted.
- **No picture.** When the browser reads the clip but shows no picture of it, the preview SHALL say that this
  browser cannot show the clip's picture, and SHALL offer the clip's file as a download. Its controls SHALL
  stay.
- **It cannot play the clip.** When the browser refuses the clip, the page SHALL ask the service for the
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
- While a save is in flight or a Move clips is pending, Set From and Set To SHALL say that they are unavailable
  and change nothing. Play, the playhead, Skip cuts and Close SHALL stay usable.
- A clip moved within its chapter SHALL keep its preview, playing or not.
- A clip moved into another chapter, by a drag or by Move clips, SHALL keep its preview open at the same time,
  paused. The reopened preview SHALL take no keyboard focus and SHALL NOT scroll the page. After a drop,
  keyboard focus is on the clip's handle, and the handle and the row's first line are fully visible, as
  "Edit mode drags clips between chapters" requires; a row made taller than the view by its preview is
  scrolled so that its first line is, and the preview under it may lie partly outside the view.
- Reset SHALL close every preview. Leaving Edit mode SHALL close it.

#### Scenario: Nothing loads until a preview is opened
- **WHEN** the operator opens Edit mode on `2024-09-15 - Stor dag`, whose root chapter plays 400 clips, scrolls
  to its end, and shows the Cuts panels of `c0001.mp4`, `c0200.mp4` and `c0400.mp4`
- **THEN** the page holds no video element and has made no media request
- **WHEN** the operator presses Watch in the panel of `c0400.mp4`
- **THEN** its preview opens with keyboard focus on "Play c0400.mp4", nothing plays, and every media request
  names `c0400.mp4` and carries its modification time as `v`

#### Scenario: Playing and seeking from the keyboard
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, using only the keyboard, the operator shows the
  Cuts panel of `s1710001.mp4`, presses Watch and then Space
- **THEN** the clip plays, and the control with focus is now named "Pause s1710001.mp4"
- **WHEN** the operator presses Space again, moves to the playhead, and presses Home, then Right three times
- **THEN** the clip is paused, and the playhead says `0:00.3 of 0:06.02` in a browser that reads the clip's
  length as 6.02 seconds
- **WHEN** the operator presses End, then Page Down
- **THEN** the playhead says `0:05.02 of 0:06.02`
- **WHEN** the operator presses Space on the playhead
- **THEN** the clip plays and the page does not scroll; Space again pauses it

#### Scenario: Opening another preview closes the first
- **WHEN** the preview of `s1710001.mp4` of `2024-06-27 - Grillning med grannar` is playing, and the operator
  shows the Cuts panel of `s1710002.mp4` and presses its Watch
- **THEN** the preview of `s1710001.mp4` is closed, its Watch control says that it is not open, and its file
  is no longer loading. The preview of `s1710002.mp4` is open, with keyboard focus on its Play.

#### Scenario: Closing gives focus back
- **WHEN** keyboard focus is on the playhead of an open preview and the operator presses Escape
- **THEN** the preview closes, and keyboard focus is on that clip's Watch control
- **WHEN** the operator opens it again and presses Close
- **THEN** the preview closes, and keyboard focus is on the Watch control again
- **WHEN** the operator opens it again and presses the clip's Cuts control
- **THEN** the panel and the preview are hidden, and keyboard focus stays on the Cuts control

#### Scenario: Watching from the row in one press
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with every Cuts panel hidden, the operator tabs
  to the thumbnail of `s1710002.mp4`, which is named "Watch s1710002.mp4", and presses Enter
- **THEN** the clip's Cuts panel is shown with its preview open, keyboard focus is on "Play s1710002.mp4",
  nothing plays, and no other row changed its size; the rows above it did not move, and the rows after it
  moved down only by the height that the opened panel added to its row
- **WHEN** the operator presses Escape
- **THEN** the preview closes, its panel stays shown, and keyboard focus is on the thumbnail of `s1710002.mp4`
- **WHEN** the operator presses the thumbnail of `s1710001.mp4` with the pointer
- **THEN** the preview of `s1710001.mp4` opens, the one of `s1710002.mp4` is closed, and no drag starts: every
  clip keeps its place
- **WHEN** in Edit mode on `2024-10-05 - Trasig`, whose thumbnail shows "No preview", the operator presses the
  thumbnail of `trasig.mp4`
- **THEN** its preview opens and says that the clip's file is empty

#### Scenario: A portrait clip is shown whole
- **WHEN** the event `2024-05-19 - Provklipp` holds `h264-720p-rotate90-aac.mp4`, a 1280×720 clip that its
  container turns to portrait, and the operator opens its preview and plays it
- **THEN** the picture is taller than wide and wholly inside the preview's 16:9 box, with empty bands at its
  sides. The box is as large as the box of a landscape clip in the same panel would be.

#### Scenario: No sound for a Sony clip in Firefox
- **WHEN** in Firefox, which plays no PCM audio, the operator opens the preview of `sony-xavc-1080p25-pcm.mp4`
  of `2024-05-19 - Provklipp`
- **THEN** the preview says that this browser finds no sound it can play in the clip, and that if a Sony
  camera recorded it, its sound is PCM, which Chrome plays and the render keeps. The note is announced once,
  and the clip plays its picture on request, not muted.
- **WHEN** the same preview is opened in Chrome
- **THEN** no such note is shown

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
  `0:02.5`, and the operator drags that clip into `Kvällen`
- **THEN** in `Kvällen`, the clip's Cuts panel is shown with its preview open, paused, at `0:02.5`
- **AND** keyboard focus is on the clip's handle, and the handle and the row's first line lie fully between the
  bottom of the page header or the chapter's heading and the top of the save bar, also in a window 390 × 844
  pixels
- **WHEN** the preview of `Kvällen/s1710002.mp4` is playing and the operator presses that clip's Move down
- **THEN** it keeps playing

#### Scenario: A pending save leaves playback alone
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its preview open, the
  operator presses Save and the service has not answered yet
- **THEN** Set From and Set To say that they are unavailable, and pressing them changes no field, while Play,
  the playhead and Close still work and keyboard focus stays on Save

#### Scenario: Previewing is not an edit
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator opens the preview of
  `s1710002.mp4`, plays it, seeks it and closes it, and then presses the browser's Back
- **THEN** no save bar is shown at any time, and the page goes back to the event list without asking about
  unsaved changes

#### Scenario: Reset closes the preview
- **WHEN** on `2024-06-27 - Grillning med grannar`, with the title changed and the preview of `s1710001.mp4`
  open, the operator presses Reset
- **THEN** the preview is closed and its panel is hidden, and the page holds no video element

#### Scenario: A preview on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide, and the
  operator opens the preview of `Kvällen/s1710002.mp4`
- **THEN** the page does not scroll horizontally, and the picture's box is 16:9 inside the panel. A tap anywhere
  in a 44 × 44 pixel area around Close, Play, Skip cuts, Set From and Set To reaches that control and no other.
  A tap anywhere along the playhead, up to 22 pixels above or below its centre line, moves it.

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
- **Set From** SHALL write the playhead's time into the panel's start field, and **Set To** into its end field.
- The time SHALL be written to the millisecond, in the format the panel writes times (`0:01.234`, `0:02.5`).
  The panel SHALL read it back as that same time.
- Keyboard focus SHALL stay on the pressed control, and the new value SHALL be announced.
- Neither SHALL add a cut. The written time SHALL count as a cut typed but not added: the clip's Cuts control
  SHALL say "typed", and the save bar SHALL hold Save back until the cut is added or its fields cleared, as for
  any typed time.

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

**The clip's length.** The page SHALL take a clip's length from its preview, as the browser reads it from the
clip's file, and from nowhere else.
- Once it has the length, the clip's panel SHALL say where the clip ends beside its fields (`This clip ends at
  0:06.02`).
- The panel SHALL refuse a cut that ends after the clip's length, compared to the millisecond as the panel
  writes times. The refusal SHALL be at the end field, or at the start field when the start lies at or after
  the length, since no end could then fix it. It SHALL name the cut's time and the clip's length. A cut that
  ends exactly at the length SHALL be accepted.
- Each cut the panel lists that ends after the length SHALL be marked as running past the clip's end. Nothing
  SHALL refuse it, and its Undo SHALL NOT be refused for it.
- The page SHALL keep the length for the clip while Edit mode stays open: after the preview closes, after
  another opens, and after the clip moves to another chapter. It SHALL forget it when the clip's modification
  time changes, and when Edit mode closes.
- When the browser reads a different length for the clip while it plays, the panel SHALL use the latest.
- The length SHALL NOT be saved, sent to the service or shown anywhere outside Edit mode.

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
  clip's Cuts control says "typed", and the save bar says that a cut was typed on `s1710001.mp4` but not added
- **WHEN** the operator moves the playhead to `0:02.5`, presses Set To, and then presses Add cut
- **THEN** the bar showed the typed span from 1.2 to 2.5 seconds before the addition. The panel then lists the
  cut from `0:01.2` to `0:02.5`, the Cuts control reads "1 cut · −1.3 s", and the save bar says that 1 cut was
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
  moves that clip to `Kvällen` with Move clips, and adds a cut from `5` to `7` on it there
- **THEN** the cut is refused for ending after the clip's length

## MODIFIED Requirements

### Requirement: Every clip row shows a frame from its clip

On an event's page, every clip row SHALL show a thumbnail of the clip beside its facts, after its position
number and ahead of its file name in the row's reading order. This applies to the chapter tables, to their
card layout in a narrow window, and to Edit mode's lists (the movable rows, the removed rows and the ignored
rows). The
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
its row shows it. Outside Edit mode, and in Edit mode for a clip that offers no Cuts control (a missing,
removed or ignored clip), the thumbnail SHALL NOT be focusable. In Edit mode, the thumbnail of a clip that
offers a Cuts control SHALL be a button named "Watch <name>" that opens the clip's preview ("Edit mode
previews a clip on request"). Its box, its size and its place in the row SHALL stay as they are, and the
button's name stands in for the image's text alternative. No thumbnail SHALL start a drag of its own. In Edit
mode a clip moves only by its handle or its move buttons, and its thumbnail moves with its row.

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
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, enters Edit mode, and moves its first clip
  down one place with the Move down button
- **THEN** every drag row shows the same frame its clip showed in the table, the moved clip's frame is now in
  the second row, and the service received no second thumbnail request for any of the four clips

#### Scenario: In Edit mode a clip's frame is a Watch button
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, and then enters Edit mode
- **THEN** in the read view no thumbnail is focusable
- **AND** in Edit mode the thumbnail of every clip `Main` and `Kvällen` play is a button named "Watch <name>",
  such as "Watch s1710002.mp4" in `Kvällen`, which names its own clips without the folder, the ignored root clip `s1710004.mp4`'s thumbnail is not
  focusable, and every thumbnail box has the size and place it had before this change

#### Scenario: A clip rotated for display is shown whole
- **WHEN** an event holds a 1920×1080 clip whose container rotates it 90° for display, named with a space,
  a comma and a Swedish letter (`stående klipp, 1.mp4`)
- **THEN** its thumbnail is requested with that name as its `clip` value and arrives taller than wide, its
  box has the same size as a landscape clip's, and the whole frame is visible inside it, turned as a player
  shows it, with empty bands at its sides

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

**The clip's length.** No read of the service gives a clip's length. The page knows it only once the clip's
preview has read it from the clip's file in this Edit mode ("Edit mode previews a clip on request"). Until
then, the panel SHALL say that the page does not know the clip's length, that a cut that runs past the clip's
end stops there, and that a cut over the whole clip leaves the clip out of the movie, and it SHALL NOT refuse
a cut for its length. Once the page knows the length, the panel SHALL state it beside its fields, SHALL refuse
a cut that ends after it, and SHALL mark each listed cut that ends after it ("A clip's preview sets cut times
at the playhead and plays the clip as the movie will").

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

#### Scenario: A clip never previewed is not checked for length
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose preview was not opened in this Edit
  mode, the operator adds a cut from `5` to `7`
- **THEN** the cut is accepted and listed, and the panel says that the page does not know the clip's length and
  that a cut that runs past the clip's end stops there

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
