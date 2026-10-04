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
its row shows it. The image itself SHALL NOT be focusable. In the event page's read view the thumbnail of a clip
whose file is on disk carries a play control laid over it ("The event page watches a clip on request"), which
is the only focusable thing in the thumbnail's cell and leaves the image, its text alternative, its box, its
size and its place as they are. In Edit mode, for a clip that offers no Cuts control (a missing, removed or
ignored clip), the thumbnail SHALL NOT be focusable. In Edit mode, the thumbnail of a clip that
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
- **THEN** in the read view no thumbnail image is focusable, and the play control over the thumbnail of a clip on
  disk is the only stop in its cell
- **AND** in Edit mode the thumbnail of every clip `Main` and `Kvällen` play is a button named "Watch <name>",
  such as "Watch s1710002.mp4" in `Kvällen`, which names its own clips without the folder, the ignored root clip `s1710004.mp4`'s thumbnail is not
  focusable, and every thumbnail box has the size and place it had before this change

#### Scenario: A clip rotated for display is shown whole
- **WHEN** an event holds a 1920×1080 clip whose container rotates it 90° for display, named with a space,
  a comma and a Swedish letter (`stående klipp, 1.mp4`)
- **THEN** its thumbnail is requested with that name as its `clip` value and arrives taller than wide, its
  box has the same size as a landscape clip's, and the whole frame is visible inside it, turned as a player
  shows it, with empty bands at its sides

### Requirement: The event page watches a clip on request

In the event page's read view, the thumbnail of every clip whose file is on disk (a clip of any status but missing:
an included, new, ignored or excluded clip) SHALL carry a **play control**: a button laid over the thumbnail's box,
filling it, with a play glyph (a disc with a triangle) centred in it. The row of a missing clip SHALL offer none
and SHALL NOT keep room for one; its empty placeholder box stays as it is. The control SHALL be the row's one way to
open the player: the file cell SHALL hold no Watch button, only the clip's name and its cuts indicator. The control's
name SHALL be "Play <name>", where <name> is the clip's name as its row names it. While the clip's player is open the
control SHALL show the hide icon instead of the play glyph and its name SHALL be "Hide player of <name>", so that it
never shares a name with the open player's own Play / Pause button ("Play <name>" / "Pause <name>"). It SHALL say to
assistive technology whether the player is open and which region it controls. Pressing it SHALL open the clip's
player, and pressing it while the player is open SHALL close it. The thumbnail's image, its text alternative
"Frame from <name>", its box, its size, its dimming of an ignored clip and its "No preview" box SHALL be as "Every
clip row shows a frame from its clip" says; the control is over them, not instead of them, and it is offered on a
"No preview" box too.

**When the glyph is seen.** The control SHALL be operable at all times and SHALL be reached by Tab at all times,
whether its glyph is seen or not. The glyph SHALL be seen while the pointer is over the thumbnail, while the control
has keyboard focus, and while the player is open, and SHALL always be seen when the primary pointer is coarse. With a
fine pointer that is elsewhere and no focus on it, the glyph MAY be unseen. It SHALL appear at once, with no
animation. Open or closed SHALL NOT be shown by colour alone: the glyph changes and the name and `aria-expanded`
follow. A visible focus ring SHALL show on the control when it has keyboard focus, and the glyph and the ring SHALL be
legible over any frame, light or dark, and in forced-colors mode.

**The area.** The control SHALL fill the thumbnail's box, which is at least 80 × 45 CSS pixels, so that a press
anywhere on the frame reaches it, with a mouse and with a finger, and so that, when the primary pointer is coarse, it
takes a tap anywhere in an area of at least 44 × 44 CSS pixels and reaches no other control. It SHALL start no drag.

**Where the player opens.** The player SHALL open in a row of its own directly under the clip's row, as wide as the
table, as a region named "Player for <name>". That row SHALL be no clip: it SHALL carry no position, SHALL count in
no clip count, and SHALL exist only while the player is open. Opening it SHALL bring it into view whole when it
fits the window, moving the page no further than that takes, and SHALL move keyboard focus to the player's Play
control.

**The player is the preview Edit mode opens.** It is the same component. It SHALL play what "Edit mode previews a
clip on request" says the preview plays, choose its file, say which file plays, offer Play original, and show its
notes by cause, as "A clip's preview plays its preview copy when one is ready" says, with the differences that "A
clip watched on the event page is played, not edited" names and no others. A clip with a ready preview copy SHALL
therefore play it, with sound in Firefox; a clip without one SHALL play its original, and in Firefox a Sony clip's
original SHALL still carry the no-sound note.

**One at a time.** Opening a player SHALL close any other clip's player, so that the read view holds at most one clip
player, in any chapter. Pressing the control of a clip whose player is open SHALL close it.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media, its preview copy or its
filmstrip, and SHALL NOT create a video element for a clip, before the operator opens that clip's player. This SHALL
hold for any number of clips, and on opening the page, scrolling it, refreshing it, and leaving Edit mode. A play
control SHALL be made from the event detail alone. Closing a player SHALL stop its playback and any loading of its
file.

**Closing.** Close, and Escape pressed while keyboard focus is in the player, SHALL close it and move keyboard focus to
the clip's play control, whose glyph is then seen because it has keyboard focus. No control of a closed player SHALL keep focus.

**What a read of the event does to an open player.**
- A re-read the page starts by itself (when the job it shows reaches a finished state, see "A shown screen re-reads in
  place when events change") SHALL leave an open player as it is, playing or paused, at its position, when the clip is
  still on disk with the same modification time.
- When that re-read finds the clip on disk with another modification time, the player SHALL go on with the clip's
  new file, paused at the time it had reached; it SHALL NOT go on with the old file at the old address.
- When that re-read changes only what the detail says of the clip's preview copy (a copy was built or went stale
  meanwhile), the player SHALL stay on the file it plays and SHALL NOT change file by itself; the next player of the
  clip SHALL use the new state.
- When that re-read no longer lists the clip, or lists it as missing, the player SHALL close and its row SHALL go.
  If keyboard focus had been in the player, it SHALL move to the clip's row when the clip is still listed, and
  otherwise to the page's heading, as after any read that removes the control that held it.
- The operator's Refresh, and opening Edit mode, SHALL close the player, as they replace the page's content: the page
  SHALL NOT keep a player across a read that shows placeholders.

**Sizes and look.**
- In a window 320 CSS pixels wide or more, the play control and the open player SHALL NOT make the page scroll
  horizontally, with a clip whose name is 40 characters long.
- The player's box and controls SHALL be as "Edit mode previews a clip on request" sizes them (a fixed 16:9 box as wide
  as the table allows up to 640 CSS pixels and never taller than 360, with its size before the file is read); the row
  SHALL be as wide as the table in every layout the table has, including the narrow ones where each clip row is a
  grid.
- The control and the player SHALL follow the page's color scheme in both schemes. No state of either SHALL be shown
  by color alone: open or closed is said by the glyph, in the name and to assistive technology.
- They SHALL animate nothing.
- The control SHALL add no height to a row: it sits over the thumbnail and adds no line to the file cell, so that no
  clip row is taller than it was with its Watch button.

#### Scenario: A Sony clip is watched with sound in Firefox
- **WHEN** in Firefox 155 or later, the operator opens `2024-05-19 - Provklipp`, whose detail gives
  `sony-xavc-1080p25-pcm.mp4` a ready preview copy, presses "Play sony-xavc-1080p25-pcm.mp4" on its thumbnail and then the player's Play
- **THEN** a region named "Player for sony-xavc-1080p25-pcm.mp4" is open directly under that clip's row, it says
  "Playing the preview copy", the sound it decodes is not silent, and it shows no note that the browser finds no
  sound
- **AND** the control over the thumbnail now shows the hide icon, is named "Hide player of sony-xavc-1080p25-pcm.mp4"
  and says its player is open, and the page has made no request to `…/media` for that clip

#### Scenario: A clip without a ready copy plays its original
- **WHEN** the operator opens the player of `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose detail
  gives no ready preview copy
- **THEN** the player says "Playing the original", offers no Play original control, and the page has made no
  request to `…/proxy`

#### Scenario: A missing clip has no Watch
- **WHEN** `reel.yaml` of `2024-06-27 - Grillning med grannar` lists `borttagen.mp4` and the file is not on disk
- **THEN** the row of `borttagen.mp4` shows no play control over its empty placeholder box, and Tab does not stop in that row except on its
  cuts indicator if it has one

#### Scenario: An ignored and an excluded clip can be watched
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose root clip `s1710004.mp4` `reel.yaml`
  ignores, and an event in which `reel.yaml` excludes `s1710002.mp4`
- **THEN** the thumbnail of each of those rows carries "Play <name>", and the player of the excluded clip shows no cuts

#### Scenario: Nothing loads until a Watch is pressed
- **WHEN** the operator opens `2024-09-15 - Stor dag`, whose root chapter plays 400 clips, scrolls to its end,
  refreshes the page, enters Edit mode and leaves it
- **THEN** after each of those the page holds no video element for a clip and has made no media, preview copy or
  filmstrip request
- **WHEN** the operator presses "Play c0400.mp4" on its thumbnail
- **THEN** the page holds one video element and its requests are for `c0400.mp4` alone

#### Scenario: Escape gives focus back to the row
- **WHEN** the operator opens a player with the keyboard (Enter on "Play s1710001.mp4"), then presses Escape
- **THEN** the player is closed and keyboard focus is on "Play s1710001.mp4", which shows the play glyph again
- **WHEN** the operator opens it again and presses the player's Close
- **THEN** keyboard focus is on that control again

#### Scenario: Opening another player closes the first
- **WHEN** the player of `s1710001.mp4` is open in `Main` and the operator presses "Play s1710002.mp4" on its thumbnail in
  `Kvällen`
- **THEN** the first player is closed, its control shows the play glyph and is named "Play s1710001.mp4", the second player is open and keyboard focus is on
  its Play, and the page holds one video element

#### Scenario: A job finishing leaves the open player playing
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the render job of the event reaches "Rendered", so that
  the page re-reads the event, and the clip is unchanged
- **THEN** the player keeps playing without a pause or a seek

#### Scenario: A copy built under an open player is not switched to
- **WHEN** the player of `sony-xavc-1080p25-pcm.mp4` plays its original, because its detail gave no copy, and a
  proxy job for the event finishes so that the re-read gives the clip a ready copy
- **THEN** the player keeps playing the original, without a pause or a seek, and says "Playing the original"
- **WHEN** the operator closes it and presses its play control again
- **THEN** the player says "Playing the preview copy"

#### Scenario: A clip replaced under an open player
- **WHEN** the player of `s1710001.mp4` is paused at `0:03.2` and a re-read finds the clip with a new modification
  time
- **THEN** the player goes on with the new file, paused at `0:03.2`, and no request after the re-read is for the old
  address
- **WHEN** keyboard focus was in that player (on its Play, say) before the re-read
- **THEN** keyboard focus is on the new player's Play, as after any read that removes the control that held it

#### Scenario: A clip that goes missing closes its player
- **WHEN** the player of `s1710001.mp4` is open with keyboard focus in it and a re-read finds the clip missing
- **THEN** the player and its row are gone, the clip's own row has no play control, and keyboard focus is on the
  clip's row
- **WHEN** instead that re-read no longer lists the clip at all
- **THEN** keyboard focus is on the page's heading

#### Scenario: Refresh and Edit mode close the player
- **WHEN** the operator has a player open and presses Refresh
- **THEN** the page shows its placeholders while it reads, and when it answers no player is open
- **WHEN** the operator has a player open and presses Edit
- **THEN** Edit mode opens with no player open, and its Cuts panels and Watch controls are as they were, and its thumbnails are the "Watch <name>" buttons they were

#### Scenario: Watching on a phone
- **WHEN** in a window 390 pixels wide with a coarse pointer, the operator opens a player under the clip row of
  `2024-05-19 - Provklipp`
- **THEN** the page does not scroll horizontally, every play control shows its glyph, a tap anywhere in an area of at
  least 44 × 44 CSS pixels over the thumbnail reaches that control and no other, and the player's box is as wide as
  the table up to 640 pixels

#### Scenario: The glyph shows on hover and on focus
- **WHEN** in a window 1280 pixels wide with a mouse, the operator opens `2024-06-27 - Grillning med grannar` and has
  not moved the pointer over a clip
- **THEN** no play glyph is seen, and Tab reaches "Play s1710001.mp4", whose glyph and focus ring are then seen
- **WHEN** the pointer moves over the thumbnail of `s1710002.mp4`
- **THEN** its glyph is seen at once, and it is gone again when the pointer leaves the thumbnail

#### Scenario: A press anywhere on the frame plays it
- **WHEN** the operator presses with a mouse on a corner of the thumbnail of `s1710001.mp4`, not on the glyph
- **THEN** the clip's player opens as it does for the glyph, and the row has not been dragged

#### Scenario: The open player's Play does not share the control's name
- **WHEN** the player of `s1710001.mp4` is open
- **THEN** the thumbnail's control is named "Hide player of s1710001.mp4", the player holds a button named "Play
  s1710001.mp4" or "Pause s1710001.mp4", and no two controls of the page share a name

#### Scenario: The file cell holds no button
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide
- **THEN** the file cell of every clip row holds the clip's name and its cuts indicator and no button, and no row is
  taller than it was with its Watch button

### Requirement: The event page plays one video at a time

Whenever a video of the page starts to play while another video of the page is playing, the other SHALL be paused where
it is. This SHALL hold between any two of the page's players, in either order: the Movie section's player, a clip's
player in the read view, a clip's preview in Edit mode and the Timeline's video, however the video was started (its
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
- **WHEN** the Timeline plays, the operator presses "Play s1710001.mp4" on a thumbnail and then the player's Play, and
  then presses the Timeline's Play
- **THEN** the Timeline is paused at its playhead while the clip plays, and then the clip is paused at its place
  while the Timeline plays, and neither player has closed

#### Scenario: Edit mode's preview and the Timeline
- **WHEN** in Edit mode a clip's preview plays and the operator presses Play on the Timeline
- **THEN** the preview closes as "Edit mode holds one video at a time" says, and only the Timeline plays
