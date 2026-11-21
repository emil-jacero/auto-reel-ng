## ADDED Requirements

### Requirement: The Clip tab offers a clip's edits whether or not the track draws it

With one clip selected, from the track or the bin, the Clip tab SHALL show its name, chapter, position and status in
words, also while the track is not open. For a clip a chapter lists it SHALL offer Move earlier and Move later (one
place, as Move up and Move down; into the next chapter at an edge, but a missing clip's own edge stops it), and if on
disk Move to… and Rotate; Ignore or Include clip; Remove from reel.yaml or Undo for a missing clip. Trims, cuts and
poster need the track.

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
- **THEN** the clip is removed as the bin's remove control removes it, the Clip tab says that it is removed from
  reel.yaml when the edits are saved and offers Undo, which has keyboard focus

#### Scenario: Moving a clip while proxies are being prepared
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar` while its Timeline shows Prepare, and the
  operator presses the bin row of `s1710001.mp4` and then Move later in the Clip tab
- **THEN** `s1710001.mp4` is second in its chapter, the move is announced with its position, keyboard focus stays
  on Move later, and the Clip tab offers no Trim In/Out, cuts or Use frame as poster

#### Scenario: Move later at a chapter's end
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the last clip of `Main` is selected and the operator presses Move
  later in the Clip tab
- **THEN** it becomes the first clip of `Kvällen`, as Alt+Right makes it, and the move is announced

#### Scenario: Move earlier and later by touch
- **WHEN** on a touch screen 390 pixels wide the operator taps the bin row of `s1710003.mp4` and taps Move earlier
  in the Clip tab
- **THEN** the clip moves one place earlier, and Move earlier and Move later each take a tap anywhere in a
  44 × 44 pixel area that reaches no other control

## MODIFIED Requirements

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
assistive technology alone, because the selected row and the Clip tab name the clip on screen. The clip's preview is **open** while the player holds a video for it: pressing the player's Play
SHALL open it, and nothing else SHALL. A new shown clip SHALL close the preview of the clip before it.

**From the row.** In Edit mode, the thumbnail of every clip that offers a Cuts panel SHALL be a button named "Watch
<name>". Pressing it SHALL select the clip alone, show the player when it is hidden, and move keyboard focus to the
player's Play, without playing. Pressing it while that clip is shown SHALL keep its preview as it is and move keyboard
focus to Play. The thumbnail SHALL keep its box, its size and its place in the row: being a button changes no row's
size or position. It SHALL NOT start a drag: the drag handle stays a control of its own, and a clip moves only by its
handle or its move buttons. A thumbnail that could not be shown (its "No preview" box) SHALL act all the same.

**Hide and show.** **Hide player** SHALL remove the player from the bin, close the preview, and give the bin's list the room. A hidden
player SHALL have no bar of its own: a **Show player** button SHALL take its place in the first row of the bin's marks
toolbar, beside the Clips help, and SHALL keep that row's height and the place of the count and Clear marks ("The
marks line is one aligned unit"). Its name SHALL be "Show player", and "Show player, <name>" while a clip is shown,
<name> as its row names it. Show player SHALL bring the player back with the shown clip, its preview closed.
The choice SHALL be kept in the browser for later visits, every read and write of it guarded, and SHALL be "shown"
when the browser keeps nothing.

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
1. **Hide player**, named "Hide the player of <name>" (while hidden, the toolbar's **Show player**, "Show player, <name>")
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
  earlier, Move later, Move to…, Move marked to…), SHALL keep its preview as it was, playing or not, at the same
  time. The move SHALL NOT move keyboard focus into the player and SHALL NOT scroll the bin to it.
- Reset SHALL close the preview. Leaving Edit mode SHALL close it.

#### Scenario: Nothing loads until a preview is opened
- **WHEN** the operator opens Edit mode on `2024-09-15 - Stor dag`, whose root chapter plays 400 clips, each with a
  ready preview copy so that the track draws them, scrolls to its end, and shows the Cuts panels of `c0001.mp4`,
  `c0200.mp4` and `c0400.mp4`
- **THEN** the page holds no clip-preview video element, its one video is the Timeline's, and the only requests made
  for clip media are the Timeline's own, for the clip its playhead is in (the copy, at `…/proxy?clip=c0001.mp4&v=<the copy's version the detail names>`, with no
  first-byte request of its own);
  none names `c0200.mp4` or `c0400.mp4`
- **WHEN** the operator selects `c0001.mp4`, `c0200.mp4` and then `c0400.mp4` on the track, one after the other
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
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, using only the keyboard, the operator tabs to the
  thumbnail of `s1710001.mp4` in the bin, presses Enter and then Space
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
- **THEN** the preview closes, the player is gone from the bin, Show player is in the toolbar's first row, and keyboard focus is on it
- **WHEN** the operator leaves Edit mode, enters it again and selects a clip
- **THEN** the player is still collapsed, and Show player brings it back with keyboard focus on Hide player

#### Scenario: Watching from the row in one press
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with every Cuts panel hidden, the operator tabs
  to the thumbnail of `s1710002.mp4`, which is named "Watch s1710002.mp4", and presses Enter
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

### Requirement: A clip's preview plays its preview copy when one is ready

**Which file plays.** The preview of a clip SHALL play the clip's **preview copy** when the event detail gives
the clip's proxy state as ready and gives the copy's facts a duration above zero, and SHALL play the clip's own
file, the **original**, in every other case: the state absent, stale or failed, a ready state without a usable
duration, or a detail that says nothing of a copy. The choice SHALL be made when the preview opens, from the
detail alone. For a clip whose state is not ready the page SHALL NOT request a preview copy, and SHALL NOT ask for
one to be built. The preview SHALL NOT change file by itself, also not after a failure.

**What it shows of that.** The preview SHALL say in words, under the picture, which file plays (in the bin's side
pane with a fine pointer, on the foot of the picture's box, where "Play original" also sits): "Playing the
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
- **THEN** the player still holds its preview, paused at the same time, playing the original, and its control
  reads "Play preview copy"
- **WHEN** the operator closes the preview and opens it again
- **THEN** it plays the preview copy

#### Scenario: Play original is the last control
- **WHEN** using only the keyboard, the operator opens the preview of a clip with a ready copy and presses Tab
  from Hide player through Play, the playhead, Skip cuts, Set From and Set To
- **THEN** the next stop is "Play original of <name>", and it is the last stop of the preview

### Requirement: The event page plays one video at a time

Whenever a video of the page starts to play while another video of the page is playing, the other SHALL be paused where
it is. This SHALL hold between any two of the page's players, in either order: the Movie section's player, a clip's
player in the read view, a clip's preview in Edit mode and the Timeline's video (Edit mode only), however the video was started (its
own controls, a keyboard key, a chapter jump in the Movie section's chapter list, a thumbnail's play control, the
Timeline's Play, or a player's Play after a thumbnail's control opened it). The rule SHALL be one rule for every video, held in
one place, and not a rule per pair of players: a player added to the page SHALL be covered by it without being named
in it. Neither video SHALL be closed, replaced, restarted or seeked by it, no word SHALL be announced for it, and
pausing SHALL be the only thing the page does: the video that was paused SHALL stay available and play on from its
position when its own Play is pressed. A video that Skip cuts seeks, or that plays on after a seek or after a change of
its file at a clip boundary, SHALL NOT count as starting. A video that is paused or ended SHALL NOT be touched.

#### Scenario: A clip started while the movie plays
- **WHEN** the Movie section's player plays at `1:12` and the operator presses Play in the open player of
  `s1710001.mp4`
- **THEN** the movie is paused at `1:12`, the clip plays, and the Movie section's player is still there

#### Scenario: A clip started from its thumbnail while the movie plays
- **WHEN** the Movie section's player plays at `1:12`, the operator presses "Play s1710001.mp4" on that clip's
  thumbnail, whose player opens paused, and then presses the player's Play
- **THEN** the movie is paused at `1:12` and stays there, the clip plays, and nothing has been closed

#### Scenario: The movie started while a clip plays
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the operator presses play in the Movie section's
  player
- **THEN** the clip's player is paused at `0:03.2`, stays open, and plays on from `0:03.2` when its Play is pressed,
  which pauses the movie

#### Scenario: A chapter jump starts the movie while a clip plays
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the operator presses the second chapter in the Movie
  section's chapter list
- **THEN** the movie plays from that chapter, the clip's player is paused at `0:03.2` and stays open

#### Scenario: Two clips never play together
- **WHEN** the player of `s1710001.mp4` plays and the operator presses "Play s1710002.mp4" on its thumbnail, and then the
  second player's Play
- **THEN** the first player has closed, as one player is open at a time, and only the second clip plays

#### Scenario: The Timeline and a clip's player
- **WHEN** in the read view the operator presses "Play s1710001.mp4" on a thumbnail and then the player's Play
- **THEN** the clip plays and no Timeline video exists to pause: the read view has no Timeline (`event-timeline`, "The
  Timeline is shown only in Edit mode, open from the start"); in Edit mode a clip's preview and the Timeline follow the
  next scenario

#### Scenario: Edit mode's preview and the Timeline
- **WHEN** in Edit mode a clip's preview plays in the bin's player and the operator presses Play on the Timeline
- **THEN** the preview closes as "Edit mode holds one video at a time" says, the player shows the clip's
  thumbnail, and only the Timeline plays


### Requirement: The Clip tab edits the selected clip

With one clip selected, the Clip tab SHALL show the clip's name, chapter and position, and its length in the movie,
and SHALL offer Trim In and Trim Out as typed times, Rotate left and right, **Move earlier** and **Move later**,
**Move to…**, the clip's cuts with remove and "+ Cut at playhead", Use frame as poster. A typed trim SHALL be the same
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


### Requirement: The clip bin holds the chapters' clip lists

The bin SHALL list every chapter with its clips in compact rows (thumbnail, name, kept length, status) and SHALL keep
every action the chapter lists have: reorder and move between chapters by pointer and by keyboard, marks and Move
marked to…, the New and Missing clips with their actions, and the clips the event ignores. Adding, moving, deleting and
renaming chapters SHALL be done in the Event tab's Chapters list ("The Event tab lists the event's chapters"); a
chapter's heading in the bin holds its name and counts and no tool. The bin's player ("Edit mode previews a clip on
request") SHALL sit above its lists and toolbar and SHALL NOT scroll with them.

From 960 CSS pixels wide the bin SHALL be a side pane as wide as 22% of the window, at least 240 and at most 320 CSS pixels; below 960 the panes stack and it is as wide as the window. With a fine pointer, a row of a clip a chapter plays SHALL take two lines and be at most 70 CSS pixels tall: handle, position, name and the row's tools, then the thumbnail, the length it plays, its status and Cuts. In a bin narrower than about 17rem (272 CSS pixels) Rotate left and right go to the second line, before Cuts; from that width all of the row's tools are on the first line. In the bin, with a fine pointer, a clip's status is shown as its icon alone ("State is never shown by color alone"); with a coarse pointer it keeps its words. In a window from 960 CSS pixels wide, a chapter in the bin SHALL list only the clips it plays and the missing clips the operator removed. The bin SHALL list the clips the event ignores after the last chapter and before Add chapter, under the heading "Ignored clips": each chapter's ignored clips together, in the chapters' order and in the order the chapter lists them, under a caption that names the chapter and says how many it holds ("Main · 1 ignored clip, not played"), each named as that chapter names it, marked as ignored, with no position, handle or control. These clips still count as listed by their chapter. The bin SHALL show no such heading when the event ignores no clip. Below 960 CSS pixels each chapter lists its ignored clips after its other clips. The bin SHALL show no line of its own about new clips: the Clips help says when a new clip joins `reel.yaml`, and the top bar's summary says how many saving adds.

#### Scenario: Keyboard reorder in the bin
- **WHEN** the operator focuses `s1710002.mp4`'s drag handle, presses Space, ArrowUp, Space
- **THEN** `s1710002.mp4` is first in its chapter, the move is announced, and the Timeline draws it first

#### Scenario: Clip rows visible at the target window
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, with a fine pointer, no clip marked and the bin's player hidden
- **THEN** in a 1280×720 window the bin shows, below its toolbar and without scrolling, at least 3 whole rows of the clips its chapters play, and in a 1440×900 window all 4 of them; the ignored `s1710004.mp4` is listed after them

#### Scenario: A new clip in the bin
- **WHEN** Edit mode opens on `2024-08-02 - Badutflykt - Varberg`, whose `reel.yaml` lists two of its three clips, and the operator moves `s1710001.mp4` below `s1710003.mp4`
- **THEN** the bin shows no line about new clips, the new clip's row has the status "New, not yet in reel.yaml": with a fine pointer an icon whose tooltip and visually hidden text are those words, with no visible word ("State is never shown by color alone"), the Clips help says when a new clip joins `reel.yaml`, and the top bar's summary says that saving adds 1 new clip to `reel.yaml`

#### Scenario: Ignored clips in the bin
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window, and then in a 900 px wide window
- **THEN** the wide bin shows "Ignored clips" after `Kvällen`, with `Main · 1 ignored clip, not played` above `s1710004.mp4`, and `Main` lists only `s1710001.mp4`; the 900 px page lists `s1710004.mp4` under `Main` and has no such heading ("The event page reorders clips within a chapter")

#### Scenario: 400 clips
- **WHEN** the event has 400 clips
- **THEN** the bin scrolls on its own, the rest of the workspace does not move, and the drag-smoothness gate holds

### Requirement: Workspace shortcuts never act in fields, dialogs, a clip preview or a drag

A workspace shortcut SHALL NOT act, and SHALL leave the key to the browser, in any of these cases:
- focus is in a text field, a select or editable text;
- a dialog is open, or focus is inside an open clip preview or anywhere in the bin's player, open or not;
- a drag on the track or in the bin is in progress, or an input-method composition is in progress;
- the focused control took the key itself;
- an arrow is pressed on a focused widget that takes arrows (a slider, a radio group, a tab list, a list box, a menu
  or a spin button).

#### Scenario: Typing a title with a space
- **WHEN** focus is in Title and the operator types "Två kvällar"
- **THEN** the field reads "Två kvällar" and the Timeline does not play

#### Scenario: Arrows on the Zoom slider
- **WHEN** the Zoom slider has focus and the operator presses Right
- **THEN** the slider zooms one step and the playhead does not move

#### Scenario: Space during a trim drag
- **WHEN** the operator drags a trim handle and presses Space before releasing it
- **THEN** the Timeline does not start or stop playing

#### Scenario: Space on the player's Play after a click on a row's frame
- **WHEN** the operator presses the frame of `s1710002.mp4`'s row in the bin with the pointer, which moves keyboard
  focus to the player's Play, and presses Space
- **THEN** the player plays `s1710002.mp4`, and the Timeline does not play

### Requirement: The marks line is one aligned unit

The line above the chapters that shows how clips are marked and offers Clear marks, Rotate marked left, Rotate marked right and Move marked
to… ("Edit mode marks clips to move together", "Edit mode moves the marked clips to a chapter") SHALL read as one calm, aligned toolbar from 320 to
1280 CSS pixels wide, in both colour schemes and for both kinds of pointer.

- **One control height.** Clear marks, both Rotate buttons, Move and the chapter picker SHALL have the same height, one size for the line (at least 44 CSS pixels
  where the primary pointer is coarse), and the same corner radius.
- **One axis.** Controls in a row SHALL have their vertical centres within 1 CSS pixel of each other, and a text beside them (the Help toggle, the count of marked clips, the label "Move marked to…") SHALL be centred on the same axis. No item SHALL sit higher or lower than
  its neighbours.
- **Consistent gaps.** The gap between two controls of a group, between two groups and between two rows SHALL each be one value, the same in every row and at every width.
- **Rows.** The first row SHALL hold the Clips help's toggle and, at its end, the count and Clear marks, and, while the bin's player is hidden, Show player beside the toggle ("Edit mode previews a clip on request"); the second SHALL hold Rotate marked left and right, then the Move marked to… group (label, picker,
  Move) where it fits; the reason SHALL be shown only after Move is pressed while it is unavailable, as one muted line below the controls, starting at the toolbar's left edge, and SHALL go when the marks, the chosen chapter or the save state change the reason. The reason SHALL NOT float beside Move. Marking or unmarking a clip SHALL move no row of the toolbar other than that line.
- **In the workspace's clip bin from 960 CSS pixels wide.** The side pane is narrow (240 to 320 CSS pixels), so there, with a fine pointer, the toolbar SHALL keep exactly the two rows above and SHALL NOT wrap further. Rotate marked left and right SHALL show an icon only and offer their names as tooltips; the label "Move marked to…" SHALL name the group without being shown; the Clips help toggle SHALL show its icon alone, 32 CSS pixels square, with its name and its tooltip "Help: Clips"; Show player, while the player is hidden, SHALL show its icon alone beside it, 32 CSS pixels square, with its name ("Show player", or "Show player, <name>" when a clip is shown) and the tooltip "Show player", and in a bin narrower than 19rem (304 CSS pixels) Clear marks SHALL then show its icon alone, with its name and the tooltip "Clear marks", so that the first row holds Show player, the count and Clear marks without wrapping; the picker SHALL fill the second row between the Rotate buttons and Move. The toolbar SHALL be at most 88 CSS pixels tall, SHALL stay at the top of the bin while the bin scrolls, and keep its height whether or not a clip is marked, and whether or not the player is hidden. With a coarse pointer the 44 CSS pixel targets stand: the toolbar keeps the icon-only Rotate buttons, but the Move group wraps to a row of its own when the picker would be left under 7rem wide, so that the chosen chapter can always be read, and the toolbar scrolls with the bin rather than staying at its top.
- **Narrow windows.** Outside the side-pane bin (the stacked workspace below 960 CSS pixels, and everywhere off the workspace), where the toolbar does not fit a row, it SHALL wrap by whole groups: the Move group goes on a row of its own with the label above, the picker filling the
  row beside Move; Rotate marked left and right share a row where they fit and otherwise take a row each at the same width. Every wrapped row SHALL keep the one height and the
  one axis, and nothing SHALL scroll horizontally at 320 CSS pixels. While the bin's player is hidden, on a window narrower than 40rem (640 CSS pixels), Show player and Clear marks SHALL
  show their icons alone (with their names and the tooltips "Show player" and "Clear marks"), so that the first row holds the help, Show player, the count and Clear marks at 320 CSS
  pixels and the first mark moves no row.
- The names, descriptions, `aria-disabled` states and reasons of the controls ("Edit mode moves the marked clips to a chapter") are unchanged.

#### Scenario: Controls in a row share a height and an axis
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` at 1280 px, light and dark, with one clip marked
- **THEN** the bounding boxes of Clear marks, Rotate marked left, Rotate marked right, the chapter picker and Move have the same height, and in each row the vertical centres of
  its controls, and of the label "Move marked to…" and the count, differ by at most 1 px

#### Scenario: The reason is one muted line below
- **WHEN** no clip is marked
- **THEN** no reason line is shown, and Move's description is "Mark a clip to move it."
- **WHEN** the operator presses Move
- **THEN** "Mark a clip to move it." is one muted line below the controls, aligned to the toolbar's left edge, and not beside Move
- **WHEN** the operator marks a clip
- **THEN** no row of the toolbar other than that line and no chapter below it moves, and the line says "Choose a chapter."

#### Scenario: The bin's toolbar is two rows
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window with a fine pointer, and the operator marks `Kvällen/s1710002.mp4` and scrolls the bin down
- **THEN**
  - the toolbar's first row holds the Clips help toggle, "1 clip marked" and Clear marks, and its second row Rotate marked left, Rotate marked right, the chapter picker and Move
  - Rotate marked left and right show icons and offer their names as tooltips, and the group around the picker is named "Move marked to…"
  - the toolbar was at most 88 CSS pixels tall before and after the mark, no clip row moved when the clip was marked, and the toolbar stays at the bin's top as it scrolls

#### Scenario: The bin's toolbar with the player hidden
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1280×720 window with a fine pointer and the bin's player hidden, `s1710002.mp4` is selected, and the operator marks `Kvällen/s1710003.mp4`
- **THEN**
  - the toolbar's first row holds the Clips help toggle and Show player, named "Show player, s1710002.mp4", and after the mark "1 clip marked" and Clear marks; the player has no bar of its own
  - the toolbar was 88 CSS pixels tall before and after the mark, no clip row moved when the clip was marked, and no control of the first row wrapped, also in a bin 240 CSS pixels wide, where Clear marks shows its icon alone

#### Scenario: The stacked page's toolbar with the player hidden
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 390×800 window and in a 320×800 window, with a fine pointer and with a coarse pointer, and the bin's player is hidden, and the operator marks `Kvällen/s1710002.mp4`
- **THEN** the toolbar was as tall before the mark as after it, no control of the toolbar moved (only the count and Clear marks appeared in the first row), Show player and Clear marks show icons alone, and the page does not scroll horizontally

#### Scenario: The bin's toolbar with a coarse pointer
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a 1024×768 window with a coarse pointer
- **THEN** the chapter picker is wide enough to show "Choose a chapter" (the Move group is on its own row below the Rotate buttons), every toolbar control is at least 44 px high, and the toolbar scrolls away with the bin

#### Scenario: The toolbar wraps in aligned rows
- **WHEN** the window is 390 px wide and again 320 px, light and dark
- **THEN** the Move group is on its own row with the label above and the picker beside Move, every row's controls share one height and one centre line (within 1 px), the
  reason line, when shown, is below them, and the page does not scroll horizontally
