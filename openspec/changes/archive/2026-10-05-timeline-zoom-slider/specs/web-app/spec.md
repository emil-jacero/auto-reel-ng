## MODIFIED Requirements

### Requirement: Edit mode chooses the event's poster on the Timeline
In Edit mode the Timeline SHALL offer **Use as poster**. Pressed, it SHALL set the draft's poster to the clip
under the playhead and the playhead's time in that clip, in seconds to the millisecond and before the clip's cuts
(a time inside a cut is allowed), and SHALL take the frame the Timeline's video shows as the draft picture of
the poster area. It SHALL be unavailable when the playhead is outside every clip (the playhead
never rests on a title-card block: it stays on footage), when the video has no decoded frame at the playhead, and while a save or a move of marked clips is pending. The reason SHALL be given in words as the button's tooltip and
accessible description and, when the operator presses the button while it cannot act, in a tip that takes no room in
the Timeline's toolbar and once through the Timeline's live region; it SHALL NOT be written as text beside the button,
and a reason that comes and goes (a seek's frame loading) SHALL NOT move any control of the toolbar (`event-timeline`,
"The Timeline's toolbar keeps its place while the Timeline seeks, loads and plays"). A snapshot that fails SHALL
change nothing and say so. Keyboard focus SHALL stay on the button and the
change SHALL be announced once.

Edit mode's **poster area** (a Poster panel above the Timeline; the page header's cover belongs to the read view) SHALL say what the poster is:
**Default: first clip** when the draft has no poster, **Chosen frame** when it has one as saved, and **Chosen
frame, not saved** for a draft that differs from the saved one. **Use default** SHALL remove the draft's poster and
SHALL be unavailable when there is none. The poster is a part of the one draft: Save writes `poster` with the
existing editorial write (`poster: {clip, at}`, or `null` to remove, and nothing when the poster was not
changed), Undo of the poster and Reset restore the saved one, an unmodified draft writes nothing, the save bar
says "poster changed", and Unsaved edits are never discarded silently. After a save the poster area shows the
image from the poster endpoint, not the snapshot. A poster whose clip the draft removes, moves out of the event
or ignores SHALL be marked in the poster area ("this clip does not play, the default is used") and SHALL NOT be
rewritten silently. A chosen clip that the detail reports with a `poster_note` SHALL show that note. Clips whose
rotation the page shows turned (`rotate`) SHALL be snapshotted and shown turned.

#### Scenario: Use as poster sets the draft from the playhead
- **WHEN** the playhead is at 0:12.500 of `s1710002.mp4` in Edit mode and Use as poster is pressed
- **THEN** the draft's poster is that clip at 12.5 s, the poster area shows that frame as "Chosen frame, not
  saved", the save bar says "Poster changed", and focus is still on the button

#### Scenario: Saving writes the poster once
- **WHEN** the draft's poster is changed and Save is pressed
- **THEN** one `PUT …/reel` carries `poster: {clip, at}`, a save of an unchanged poster carries none, and the poster
  area then shows the served image as "Chosen frame"

#### Scenario: Use default removes the chosen frame
- **WHEN** an event with a saved poster is edited, Use default is pressed and Save is pressed
- **THEN** the write carries `poster: null`, the area says "Default: first clip", and Reset before Save restores
  the saved poster

#### Scenario: The button is off where it cannot act
- **WHEN** a save is pending, an open clip preview holds the page's video, or the video has no decoded frame
- **THEN** Use as poster is unavailable, its tooltip and accessible description say why, and pressing it shows the
  reason in a tip and says it once, with no text added to the toolbar and no control moved

#### Scenario: A rotated clip is chosen turned
- **WHEN** the clip is shown turned and Use as poster is pressed on it
- **THEN** the draft picture is turned the same way

#### Scenario: The same behavior in Chrome and Firefox, in both schemes, at 1280 and 390 px
- **WHEN** the steps above are run in Chrome and in Firefox, light and dark, at 1280 and 390 px width
- **THEN** each has the same words and results, nothing overflows, and every control is large enough to touch

#### Scenario: Reading does not write
- **WHEN** the list, the page and Edit mode are opened and the Timeline's playhead is moved without pressing Use as
  poster
- **THEN** no request other than reads is sent

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
- **WHEN** the operator drags the start of cut 1 of `s1710001.mp4` to 0.5 s and the Cuts panel of that clip is shown
- **THEN** the panel lists cut 1 as 0:00.5 to 0:02.5, the Cuts control of the clip reads the new summary, and the edit is announced

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
- **WHEN** in Edit mode a clip's preview plays and the operator presses Play on the Timeline
- **THEN** the preview closes as "Edit mode holds one video at a time" says, and only the Timeline plays
