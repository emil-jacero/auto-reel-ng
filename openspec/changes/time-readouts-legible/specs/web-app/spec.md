## ADDED Requirements

### Requirement: Running times are written to a fixed width and say what they are

Every time the client shows while something moves (the Timeline's readout under its video, the clip player's header,
the Timeline's trim tip and its "Movie … of footage" line) SHALL be written by one formatter, the **clock**, and
SHALL NOT be written in the form that the Cuts panel writes cut times in (`0:01.5`, `0:02.607`), which keeps its own
job: a cut's time, a typed field, a spoken word. The ruler's tick labels and the chapter list's start times do not
move while something plays and keep that form.

**One scale per readout.** A readout SHALL be written to a scale taken from the longest value it can show, not from
the value it shows. Minutes SHALL be zero-padded to the digits of the longest value's minutes (`0:09.50 of 0:39.84`
when the longest is under ten minutes, `09:59.99 of 12:30.00` when it is not), hours SHALL appear in every value of a
readout or in none (none unless the longest is an hour or more), and seconds SHALL always have two digits. The
fraction SHALL have the same number of digits in every value of every readout of that kind, trailing zeros kept:
two (centiseconds) for the Timeline's and the player's readouts and the summary line, three (milliseconds) for the
trim tip, which shows the time a cut will have. A value SHALL be cut down to those digits, never rounded up, so that
a position never reads later than its total. A value above the longest SHALL be shown as the longest. A value that
is not known (the player's length before the browser has read it) SHALL be shown as dashes in the same places
(`-:--.--`), never as `0:00`. A value that is negative or not a number SHALL NOT be written: it is an error, never a
made-up time.

**Constant width.** A running time SHALL occupy a width that depends on its scale and on nothing else: it SHALL have
a reserved width in the width of a digit of its monospace face, digits of equal width, and its text SHALL stay on
one line. While a clip plays, while the playhead is scrubbed or stepped, and when the playhead passes from one clip
into another, no readout's width and no readout's left edge SHALL change, and nothing after a readout on its line
SHALL move. A readout's width MAY change when its scale does, which only the set of clips (a Prepare job that ends,
a clip that goes) or the clip's length being read can cause, and SHALL NOT change at any other moment.

**Words.** A readout SHALL say what each number is in words that stay on the screen: the Timeline's reads `Clip
0:00.96 of 0:39.84 · Event 1:02.40 of 2:29.76`, the first pair being the time in the clip the playhead is in and that
clip's length, the second the time in the whole timeline (the clips end to end, before cuts) and its length. The
clip pair's scale SHALL be that of the event's longest clip and the event pair's that of the whole timeline's length,
so that passing from a 9-second clip into a 40-second one changes no width. The clip player's header reads `Clip
0:20.48 of 0:20.64`. The Timeline's summary line reads `Movie 3:12.00 of 3:45.00 of footage`, to the scale of the
footage's length. The trim tip reads the time alone, to the scale of its clip's length, and the words it adds when
the edge snaps SHALL NOT move that time.

**The name.** The clip's name in the Timeline's readout SHALL be shown on one line and, when it does not fit, SHALL be
cut with an ellipsis and keep its whole text as its tooltip; it SHALL NOT wrap and SHALL NOT move a number. On a
window 390 CSS pixels wide the name MAY take its own line, and the numbers SHALL then keep their widths.

**Both schemes, every width.** The readouts SHALL meet the page's contrast in the light and the dark scheme and SHALL
NOT make the page scroll horizontally from 320 CSS pixels up.

#### Scenario: Crossing a clip does not move the line
- **WHEN** the Timeline of an event whose clips are 9.00 s, 40.00 s and 6.02 s (55.02 s in all) plays from 0:08 into
  the second clip
- **THEN** the readout reads `Clip 0:08.20 of 0:09.00 · Event 0:08.20 of 0:55.02`, then `Clip 0:00.10 of 0:40.00 ·
  Event 0:09.10 of 0:55.02`, and the width of every time and the left edge of both pairs are the same in the two
  samples

#### Scenario: Nine seconds to ten
- **WHEN** the playhead of a 12-second clip goes from `0:09.99` to `0:10.00`
- **THEN** the readout's text is `0:09.99` and `0:10.00` in cells of one width, and nothing after it moves

#### Scenario: A long name is cut, not pushed
- **WHEN** the clip the playhead is in is named `IMG_20240627_201530_BURST042_final_v2.mp4` and the window is 390
  pixels wide
- **THEN** the name is on one line ending in an ellipsis, its tooltip is the whole name, the numbers have their usual
  widths, and the page does not scroll horizontally

#### Scenario: A cell in the trim tip
- **WHEN** the operator drags a handle on a 6.02 s clip across `0:01.25` and `0:01.30`
- **THEN** the tip reads `0:01.250` then `0:01.300`, the same width, and when the edge snaps the snap words appear
  without moving the time

#### Scenario: The length is not read yet
- **WHEN** a clip player has just opened and the browser has not read the clip
- **THEN** the header reads `Clip 0:00.00 of -:--.--`, with the time in cells as wide as they will be, and when the
  length is read it reads `Clip 0:00.00 of 0:06.02` with no change in the first cell's width

#### Scenario: A spoken form is not padded
- **WHEN** a screen reader reads the Timeline's slider at the moment of the first scenario's second sample
- **THEN** its value text reads `s1710002.mp4, clip 0:00.1 of 0:40; event 0:09.1 of 0:55.02`, in the Cuts panel's
  form, and the visible readout is not the slider's value

## MODIFIED Requirements

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

**What it plays.** The preview SHALL play the clip's preview copy when the clip has a ready one, and the clip's
own file, the original, otherwise, as "A clip's preview plays its preview copy when one is ready" requires. The
original is the file the service serves from `GET /api/v1/events/{event_id}/media?clip=<identity>`. The event id
and the clip's full identity SHALL be sent exactly as the event detail gives them, and the clip's modification
time, exactly as the event detail gives it, as `v`. Until it plays, the preview SHALL show the clip's thumbnail. It SHALL NOT start playing by
itself. A preview opened with Watch, from the panel or the thumbnail, SHALL stand at the clip's start, also
after an earlier preview of the clip was closed elsewhere in it. A clip displayed in portrait, such as a phone
clip whose container rotates it, SHALL be shown whole, turned as a player shows it. Unless a scenario of this
requirement says that its clip has a ready preview copy, it SHALL be read for a clip that has none.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media or its preview copy, and
SHALL NOT create a video element for either, before the operator opens that clip's preview. This SHALL hold for any number of clips,
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
7. **Play original** or **Play preview copy**, present only while the clip has a ready preview copy

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

The preview SHALL show the playhead's time and the clip's length as a readout that says what it is and keeps its
width, as "Running times are written to a fixed width and say what they are" requires (`Clip 0:01.23 of 0:06.02`).
The slider's value text stays in the Cuts panel's format, above.

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

#### Scenario: The player's time says what it is and does not move
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar` the operator opens the preview of `s1710001.mp4`
  (6.02 s) and plays it to the end
- **THEN** the header reads `Clip 0:00.00 of 0:06.02`, then `Clip 0:01.50 of 0:06.02`, and `Clip 0:06.02 of 0:06.02`
  at the end; the readout's bounding box has the same width in every sample taken during the playthrough, and the
  close button does not move

