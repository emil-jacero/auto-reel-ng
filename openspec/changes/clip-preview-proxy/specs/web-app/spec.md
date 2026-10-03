## ADDED Requirements

### Requirement: A clip's preview plays its preview copy when one is ready

**Which file plays.** The preview of a clip SHALL play the clip's **preview copy** when the event detail gives
the clip's proxy state as ready and gives the copy's facts a duration above zero, and SHALL play the clip's own
file, the **original**, in every other case: the state absent, stale or failed, a ready state without a usable
duration, or a detail that says nothing of a copy. The choice SHALL be made when the preview opens, from the
detail alone. For a clip whose state is not ready the page SHALL NOT request a preview copy, and SHALL NOT ask for
one to be built. The preview SHALL NOT change file by itself, also not after a failure.

**What it shows of that.** The preview SHALL say in words, under the picture, which file plays: "Playing the
preview copy" or "Playing the original". When the original plays because the state is stale, because it failed,
or because a ready state had no usable duration, the words SHALL give that reason ("its preview copy is out of
date", "its preview copy could not be built", "its preview copy has no usable length"). The words SHALL be
present from the moment the preview opens and SHALL NOT move the picture or the controls.

**The address.** The preview copy SHALL be played from
`GET /api/v1/events/{event_id}/proxy?clip=<identity>&v=<tag>`, the event id and the clip's full identity sent
exactly as the event detail gives them. `v` SHALL be the entity tag the service gives the copy's file, read by a
request for the copy's first byte made when the preview opens and before the picture is asked for, so that a
copy that was replaced is played from a new address. Nothing of the copy's file other than that one byte SHALL be
requested before the operator opens the preview. A copy's answer without an entity tag SHALL be treated as the
service giving no usable answer. The preview SHALL NOT request the copy's filmstrip.

**Play original and Play preview copy.** While the clip has a ready preview copy, the preview SHALL offer one
control that changes the file that plays, as the last of its controls in keyboard order. While the copy plays it
SHALL read "Play original" and be named "Play original of <name>"; while the original plays it SHALL read "Play
preview copy" and be named "Play preview copy of <name>". Pressing it SHALL:
- keep the playhead's time, to the millisecond, and the time shown, the cut bar and the playhead slider with it
- keep playing when the clip was playing, and stay paused when it was paused
- keep keyboard focus on the control, and announce "Playing the original of <name>." or "Playing the preview copy
  of <name>." through Edit mode's live region
- change nothing in the clip's cuts or fields, and count as no edit

The file chosen SHALL stay with the clip while its preview is open, also when the clip moves to another chapter,
and SHALL be forgotten when the preview closes: the next preview of the clip opens on the file the rule above
gives. The control SHALL be absent while the clip has no ready copy.

**Times mean the same in both files.** Time in the preview copy SHALL be time in the original: the preview copy
has the original's timing, so the playhead, the cut bar, Set From, Set To and Skip cuts SHALL act on the playhead
of whichever file plays, to the millisecond and in the same format, and no time SHALL be offset, scaled or
rounded differently for the copy.

**The clip's length** while the preview copy plays SHALL be the duration in the copy's facts, which is the
original's duration as the engine probed it, and SHALL NOT be the length the browser reads from the copy, which
differs from the original's by about 20 ms and can be the shorter. The playhead's end, the panel's "This clip ends
at" and the check on a cut's end SHALL use it. A browser's reading of the copy's length SHALL NOT change it.

**Sound.** The preview copy carries the clip's sound in a form every supported browser plays. While it plays, the
preview SHALL NOT show the note that the browser finds no sound; it SHALL NOT make up a cause for a silent copy.
The note belongs to the original, as "Edit mode previews a clip on request" says.

**When the preview copy cannot be played.** Each of these SHALL be shown in the preview as a note, never as an
alert, announced once through Edit mode's live region, with keyboard focus kept in the preview, and each SHALL
offer **Play original** beside any other action it offers:
- that the preview copy is no longer there, with the service's detail, when the service answers that it has no
  copy of the clip (the detail was read before the copy was removed)
- that the preview copy could not be read, with the failure kind's words and the service's detail
- that the preview copy is empty
- that this browser cannot play the preview copy, when the service serves it and the browser refuses it
- that the service gave no usable answer, saying which, with Try again, which asks for the copy anew and moves
  keyboard focus to the reopened preview's Play

The page SHALL NOT call a copy "changed on disk", and SHALL NOT compare the copy's modification time with the
clip's. Any Download offered in the preview SHALL be the original file. A failure SHALL NOT be retried by itself.
Pressing Play original SHALL open the original as the preview would have opened it without a copy, with
keyboard focus on its Play.

#### Scenario: A Sony clip has sound in Firefox
- **WHEN** in Firefox 155 or later, the event detail of `2024-05-19 - Provklipp` gives
  `sony-xavc-1080p25-pcm.mp4` a ready preview copy, and the operator opens its preview and presses Play
- **THEN** the preview says "Playing the preview copy", the sound it decodes is not silent, and it shows no note
  that the browser finds no sound
- **AND** the page has requested `…/proxy?clip=sony-xavc-1080p25-pcm.mp4&v=<tag>` and has made no request to
  `…/media` for that clip

#### Scenario: Play original keeps the time and the state
- **WHEN** the preview copy of `sony-xavc-1080p25-pcm.mp4` plays and the operator presses "Play original of
  sony-xavc-1080p25-pcm.mp4" while the playhead says `0:02.5`
- **THEN** the original plays on from `0:02.5`, the control now reads "Play preview copy", the preview says
  "Playing the original", "Playing the original of sony-xavc-1080p25-pcm.mp4." is announced, and keyboard focus
  is on the control
- **WHEN** this is Firefox, which finds no sound in the original
- **THEN** the preview shows the note that this browser finds no sound it can play, and the note says that the
  preview copy plays with sound
- **WHEN** the operator pauses and presses "Play preview copy" at `0:04.2`
- **THEN** the preview copy is shown paused at `0:04.2` and the note is gone

#### Scenario: Set From writes the same time from either file
- **WHEN** the operator seeks the preview copy of `s1710001.mp4` of `2024-06-27 - Grillning med grannar` to
  `0:02.5` and presses Set From, then presses Play original, seeks to `0:02.5` and presses Set From again
- **THEN** both presses write `0:02.5` into the start field and the panel accepts it

#### Scenario: A clip with no ready copy plays its original
- **WHEN** the detail gives `s1710002.mp4` the proxy state absent, and the operator opens its preview
- **THEN** the preview says "Playing the original", offers no Play original control, and the page has made no
  request to `…/proxy`
- **WHEN** the detail gives it the state stale
- **THEN** the preview says "Playing the original" and that its preview copy is out of date, and the page has
  made no request to `…/proxy`

#### Scenario: A copy that has gone since the page was read
- **WHEN** the detail gives `s1710001.mp4` a ready copy that the service no longer has, and the operator opens
  its preview
- **THEN** the preview says that the preview copy is no longer there, with the service's detail, as a note and
  not an alert, and offers Play original
- **WHEN** the operator presses Play original
- **THEN** the original is ready to play with keyboard focus on "Play s1710001.mp4"

#### Scenario: A cut to the original's end is accepted while the copy plays
- **WHEN** the detail gives a 50 fps clip of `2024-05-19 - Provklipp` the duration `25.003` in its facts, the
  preview copy reads 24.981 seconds in the browser, and the operator adds a cut from `20` to `0:25.003`
- **THEN** the panel says that the clip ends at `0:25.003` and lists the cut, not refused

#### Scenario: The choice follows the clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator has pressed Play original on `s1710001.mp4`, and
  drags that clip into `Kvällen`
- **THEN** its preview reopens in `Kvällen` paused at the same time, playing the original, and its control reads
  "Play preview copy"
- **WHEN** the operator closes the preview and opens it again
- **THEN** it plays the preview copy

#### Scenario: Play original is the last control
- **WHEN** using only the keyboard, the operator opens the preview of a clip with a ready copy and presses Tab
  from Close through Play, the playhead, Skip cuts, Set From and Set To
- **THEN** the next stop is "Play original of <name>", and it is the last stop of the preview

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
- **No sound.** When the original plays and the browser reports that it finds no audio it can play in the clip, the preview SHALL say
  that this browser finds no sound it can play in the clip, and that if a Sony camera recorded it, its sound
  is PCM, which Firefox does not play and Chrome does, and the render keeps it. The note SHALL NOT state as
  fact a cause or a sound the page does not know of: the clip may have no audio track at all. Playback SHALL
  be otherwise unchanged, never muted. The note SHALL NOT be shown while the preview copy plays. When the clip
  has a ready preview copy, the note SHALL add that the preview copy plays with sound and that Play preview copy
  plays it.
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
  The playhead's time is the time of the file that plays, the original or its preview copy, which are the same.
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
