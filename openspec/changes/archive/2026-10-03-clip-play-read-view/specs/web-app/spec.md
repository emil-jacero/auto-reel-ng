## ADDED Requirements

### Requirement: The event page watches a clip on request

In the event page's read view, the row of every clip whose file is on disk (a clip of any status but missing: an
included, new, ignored or excluded clip) SHALL offer a **Watch** control. The row of a missing clip SHALL offer none
and SHALL NOT keep room for one. The control SHALL be a button in the clip's file cell, under the clip's name and
above its cuts indicator. Its words SHALL be visible beside its icon ("Watch") and its name SHALL be "Watch <name>",
where <name> is the clip's name as its row names it. While the clip's player is open its words SHALL be "Hide player"
and its name "Hide player of <name>", and it SHALL say to assistive technology whether the player is open and which
region it controls. Pressing it SHALL open the clip's player, and pressing it while the player is open SHALL close it.
The control SHALL be the same one Edit mode offers in a Cuts panel, in its words, its names and its icon.

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
player, in any chapter. Pressing Watch on a clip whose player is open SHALL close it.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media, its preview copy or its
filmstrip, and SHALL NOT create a video element for a clip, before the operator opens that clip's player. This SHALL
hold for any number of clips, and on opening the page, scrolling it, refreshing it, and leaving Edit mode. A Watch
control SHALL be made from the event detail alone. Closing a player SHALL stop its playback and any loading of its
file.

**Closing.** Close, and Escape pressed while keyboard focus is in the player, SHALL close it and move keyboard focus to
the clip's Watch control. No control of a closed player SHALL keep focus.

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
- In a window 320 CSS pixels wide or more, the Watch control and the open player SHALL NOT make the page scroll
  horizontally, with a clip whose name is 40 characters long.
- The player's box and controls SHALL be as "Edit mode previews a clip on request" sizes them (a fixed 16:9 box as wide
  as the table allows up to 640 CSS pixels and never taller than 360, with its size before the file is read); the row
  SHALL be as wide as the table in every layout the table has, including the narrow ones where each clip row is a
  grid.
- When the primary pointer is coarse, the Watch control SHALL take a tap anywhere in an area of at least 44 × 44 CSS
  pixels around it, reaching no other control.
- The control and the player SHALL follow the page's color scheme in both schemes. No state of either SHALL be shown
  by color alone: open or closed is said in words and to assistive technology.
- They SHALL animate nothing.

#### Scenario: A Sony clip is watched with sound in Firefox
- **WHEN** in Firefox 155 or later, the operator opens `2024-05-19 - Provklipp`, whose detail gives
  `sony-xavc-1080p25-pcm.mp4` a ready preview copy, presses "Watch sony-xavc-1080p25-pcm.mp4" and then Play
- **THEN** a region named "Player for sony-xavc-1080p25-pcm.mp4" is open directly under that clip's row, it says
  "Playing the preview copy", the sound it decodes is not silent, and it shows no note that the browser finds no
  sound
- **AND** the control now reads "Hide player", is named "Hide player of sony-xavc-1080p25-pcm.mp4" and says its
  player is open, and the page has made no request to `…/media` for that clip

#### Scenario: A clip without a ready copy plays its original
- **WHEN** the operator opens the player of `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose detail
  gives no ready preview copy
- **THEN** the player says "Playing the original", offers no Play original control, and the page has made no
  request to `…/proxy`

#### Scenario: A missing clip has no Watch
- **WHEN** `reel.yaml` of `2024-06-27 - Grillning med grannar` lists `borttagen.mp4` and the file is not on disk
- **THEN** the row of `borttagen.mp4` shows no Watch control, and Tab does not stop in that row except on its
  cuts indicator if it has one

#### Scenario: An ignored and an excluded clip can be watched
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose root clip `s1710004.mp4` `reel.yaml`
  ignores, and an event in which `reel.yaml` excludes `s1710002.mp4`
- **THEN** each of those rows offers "Watch <name>", and the player of the excluded clip shows no cuts

#### Scenario: Nothing loads until a Watch is pressed
- **WHEN** the operator opens `2024-09-15 - Stor dag`, whose root chapter plays 400 clips, scrolls to its end,
  refreshes the page, enters Edit mode and leaves it
- **THEN** after each of those the page holds no video element for a clip and has made no media, preview copy or
  filmstrip request
- **WHEN** the operator presses Watch on `c0400.mp4`
- **THEN** the page holds one video element and its requests are for `c0400.mp4` alone

#### Scenario: Escape gives focus back to the row
- **WHEN** the operator opens a player with the keyboard (Enter on "Watch s1710001.mp4"), then presses Escape
- **THEN** the player is closed and keyboard focus is on "Watch s1710001.mp4", which reads "Watch" again
- **WHEN** the operator opens it again and presses the player's Close
- **THEN** keyboard focus is on that control again

#### Scenario: Opening another player closes the first
- **WHEN** the player of `s1710001.mp4` is open in `Main` and the operator presses Watch on `s1710002.mp4` in
  `Kvällen`
- **THEN** the first player is closed, its control reads "Watch", the second player is open and keyboard focus is on
  its Play, and the page holds one video element

#### Scenario: A job finishing leaves the open player playing
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the render job of the event reaches "Rendered", so that
  the page re-reads the event, and the clip is unchanged
- **THEN** the player keeps playing without a pause or a seek

#### Scenario: A copy built under an open player is not switched to
- **WHEN** the player of `sony-xavc-1080p25-pcm.mp4` plays its original, because its detail gave no copy, and a
  proxy job for the event finishes so that the re-read gives the clip a ready copy
- **THEN** the player keeps playing the original, without a pause or a seek, and says "Playing the original"
- **WHEN** the operator closes it and presses Watch again
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
- **THEN** the player and its row are gone, the clip's own row has no Watch control, and keyboard focus is on the
  clip's row
- **WHEN** instead that re-read no longer lists the clip at all
- **THEN** keyboard focus is on the page's heading

#### Scenario: Refresh and Edit mode close the player
- **WHEN** the operator has a player open and presses Refresh
- **THEN** the page shows its placeholders while it reads, and when it answers no player is open
- **WHEN** the operator has a player open and presses Edit
- **THEN** Edit mode opens with no player open, and its Cuts panels and Watch controls are as they were

#### Scenario: Watching on a phone
- **WHEN** in a window 390 pixels wide with a coarse pointer, the operator opens a player under the clip row of
  `2024-05-19 - Provklipp`
- **THEN** the page does not scroll horizontally, the Watch control takes a tap in an area of at least 44 × 44 CSS
  pixels, and the player's box is as wide as the table up to 640 pixels

### Requirement: A clip watched on the event page is played, not edited

The player of a clip in the event page's read view SHALL be read-only. It SHALL differ from Edit mode's preview in
these ways, and in no others:

- **No cut controls.** It SHALL have no Set From and no Set To, neither enabled nor disabled, and nothing in it SHALL
  write a cut field or a cut.
- **The keyboard order** SHALL be: **Close**, **Play** / **Pause**, the **playhead**, **Skip cuts** when the clip has
  cuts to skip, and **Play original** / **Play preview copy** when the clip has a ready preview copy. Each SHALL be
  reachable and usable by keyboard alone, and the control that changes the file SHALL be the last when it is offered,
  as "A clip's preview plays its preview copy when one is ready" says.
- **The cut bar shows the clip's cuts as the page lists them.** The cuts are the ones the event page read from the
  service for its cuts indicator, the cuts read last until a new read answers. The bar SHALL draw them as spans, with
  a legend that names only the kinds drawn (here only "Cut"), and the playhead's spoken value SHALL add "in cut N"
  when the time lies inside one, N being the cut's number in the clip's cut list on the page. A press or a drag along
  the bar SHALL move the playhead and SHALL NOT change a cut. A clip that `reel.yaml` excludes SHALL show no cuts
  on its bar, as the page shows none beside its name. When the page could not read the cuts, the bar SHALL show no
  cuts, the player SHALL offer no Skip cuts, and the page's note that the cuts could not be read SHALL stay the
  only word of it.
- **Skip cuts** SHALL be offered only for a clip that has at least one cut on its bar, and SHALL play the clip as
  the movie will, as "A clip's preview sets cut times at the playhead and plays the clip as the movie will" says of
  Skip cuts. Pressing it SHALL change no file and no state but the player's.
- **The live region.** The read view SHALL have one polite live region for its player, which carries what Edit mode's
  live region carries for a preview: that the clip is ready to play with its length, each note, each failure, and
  which file plays after Play original. Wherever a requirement for Edit mode's preview says "Edit mode's live
  region", the read view's is meant.
- **The advice after a clip that is gone or changed on disk** SHALL be to press Refresh to read the event again and
  then to watch the clip anew. The words SHALL NOT mention editing, saving or Edit mode. The player SHALL NOT
  refresh the page itself, and the failure SHALL NOT be retried by itself.
- **No cut check.** The player SHALL make no check of a cut against the clip's length, as it makes no cut.

Everything else SHALL be as it is in Edit mode, for the same reason: the file that plays, the address, the copy's
probe, the length of the clip while the copy plays, the one-line statement of which file plays, the notes (no sound
in this browser for the original; no picture), the failures by cause, the Download of the original, the Try again
that opens the player anew, the playhead's keys and words, the sizes and the look.

**It writes nothing.** Opening, closing, playing, seeking, Skip cuts and Play original SHALL write no file, enqueue or
cancel no job, send no request but the reads that play the clip, and SHALL NOT change the event page's content, its
counts or its verdict ("Reading a screen never changes state").

#### Scenario: A player without cut controls
- **WHEN** the operator opens the player of `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, which has
  one cut from `0` to `1.5`
- **THEN** the player has Close, Play, the playhead and "Skip cuts of s1710001.mp4" and no Set From or Set To
  anywhere in it, and the bar draws the cut from `0:00` to `0:01.5` with a legend that reads "Cut"
- **WHEN** the operator seeks to `0:01` with the keyboard
- **THEN** the playhead says `0:01 of 0:06.02, in cut 1`, and the clip's cut list on the page is unchanged

#### Scenario: Skip cuts is a view option
- **WHEN** the operator presses "Skip cuts of s1710001.mp4" and then Play with the playhead at `0:00`
- **THEN** playback starts at `0:01.5`, and no frame inside the cut is shown
- **AND** a clip without cuts offers no Skip cuts

#### Scenario: Play original is the last stop
- **WHEN** using only the keyboard, the operator opens the player of a clip that has cuts and a ready preview copy and
  presses Tab from Close
- **THEN** the stops are Play, the playhead, Skip cuts and "Play original of <name>", in that order, and the last is
  "Play original of <name>"

#### Scenario: A clip with unreadable cuts has a plain bar
- **WHEN** the service does not answer the read of `2024-06-27 - Grillning med grannar`'s cuts and the operator
  opens a player
- **THEN** the page shows its note that the cuts could not be read, the player's bar draws no cut, and the player
  offers no Skip cuts

#### Scenario: A clip changed on disk says Refresh, not Stop editing
- **WHEN** the operator opens the player of a clip whose file the service no longer serves, because it was removed
  after the page was read
- **THEN** the player says that the clip is no longer on disk, with the service's detail, and that pressing Refresh
  reads the event again, and says nothing of editing or saving
- **AND** that note is announced once through the read view's live region, and the page has not refreshed

#### Scenario: Watching changes nothing
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, watches `s1710001.mp4`, presses Play, seeks,
  turns Skip cuts on and off, closes the player and goes back to the list
- **THEN** every request the client made was a read, no file under the library changed, and the jobs the service
  lists are the same as before

### Requirement: The event page plays one video at a time

On the event page, when a video starts to play while another video of the page is playing, the other SHALL be
paused where it is. This SHALL hold between a clip's player and the Movie section's player in either order, however the video was started,
a jump in the Movie section's chapter list included. Neither
video SHALL be closed, replaced, restarted or seeked by it, no word SHALL be announced for it, and pausing SHALL be
the only thing the page does: the video that was paused SHALL stay available and play on from its position when its
own Play is pressed. A video that Skip cuts seeks, or that plays on after a seek, SHALL NOT count as starting.

#### Scenario: A clip started while the movie plays
- **WHEN** the Movie section's player plays at `1:12` and the operator presses Play in the open player of
  `s1710001.mp4`
- **THEN** the movie is paused at `1:12`, the clip plays, and the Movie section's player is still there

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
- **WHEN** the player of `s1710001.mp4` plays and the operator presses Watch on `s1710002.mp4` and then Play
- **THEN** only the second clip plays; the first player has closed, as one player is open at a time
