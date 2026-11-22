## MODIFIED Requirements

### Requirement: Edit mode holds one video at a time

Edit mode SHALL never hold more than one `<video>`: the Timeline's, which exists while its track is open ("The playhead scrubs one video"), or the preview's in the bin's player. Opening a clip's preview, with the player's Play ("Edit mode previews a clip on request"), SHALL release the Timeline's video, stopping its playback and its loading, and keep the Timeline open with the playhead where it stood and every handle usable. Moving the playhead, or pressing Play, on the Timeline SHALL close the player's preview, which shows its clip's thumbnail again, and create the Timeline's video again at the playhead (it loads the proxy of the clip the playhead is in, as when the track opens). Selecting a clip on the track SHALL NOT release the Timeline's video: the player shows the clip's thumbnail until its Play is pressed. Releasing and creating the video SHALL NOT be an edit, SHALL NOT disturb a drag or a typed time, and SHALL NOT move keyboard focus off the control that had it.

#### Scenario: A preview releases the timeline's video
- **WHEN** in Edit mode the Timeline's video has been scrubbed to 1.6 s of `s1710001.mp4`, the operator presses that clip's block and then Play in the bin's player
- **THEN** after the press on the block the page still holds the Timeline's video; after Play it holds one video, the clip's preview, and the Timeline is still open with its playhead at 1.6 s and its handles working

#### Scenario: Scrubbing closes the preview
- **WHEN** a clip's preview is open in the bin's player and the operator moves the Timeline's playhead
- **THEN** the preview closes, the player shows the clip's thumbnail, the Timeline's video shows the playhead's frame, and the page holds one video


### Requirement: A clip is reordered by dragging it on the track

In Edit mode a primary-button press with a mouse or a pen on a clip block's body that moves more than 3 px SHALL start a drag: the block follows the
pointer, the other clips make room live, and a line with words shows the drop place. Release SHALL make one draft edit
(reorder, or move into another chapter when the place is in another chapter's span or on its band). Escape or a
release outside the track SHALL cancel with no edit, and Escape SHALL only cancel the drag. Touch SHALL NOT start it.

#### Scenario: Drag to reorder
- **WHEN** the operator drags `s1710002.mp4` left until the line says "Before s1710001.mp4" and releases
- **THEN** the track and the bin show `s1710002.mp4` first, the top bar says "1 clip moved", nothing is written

#### Scenario: Drop on a chapter band
- **WHEN** the operator drags `s1710003.mp4` onto the band "Main" and releases
- **THEN** `s1710003.mp4` is the last clip of "Main" in the draft

#### Scenario: Touch does not drag
- **WHEN** with touch the operator swipes on a clip block
- **THEN** the track scrolls and no drag starts; a finger reorders with Move earlier and Move later in the Clip tab

#### Scenario: Escape
- **WHEN** during a drag the operator presses Escape
- **THEN** every clip returns to its place and the draft is unchanged


### Requirement: The Edit-mode Timeline draws the draft's order and chapters

The Timeline SHALL draw the draft's chapters in the draft's order and names, a deleted chapter drawing nothing, and in
each chapter its clips in the draft's order, at once and before Save; Reset SHALL draw the saved order again. Each
clip's facts SHALL be those of the last read; a clip that read no longer has SHALL NOT be drawn. No note about the
order last saved SHALL be shown. Play on the Timeline SHALL follow the drawn order.

#### Scenario: A reorder is drawn before Save
- **WHEN** in Edit mode the operator selects `s1710002.mp4` and presses Move earlier in its Clip tab, so that it
  stands above `s1710001.mp4`
- **THEN** the Timeline draws `s1710002.mp4` first at once, no note about the order last saved is shown, nothing has
  been written, and Play from 0 plays `s1710002.mp4` before `s1710001.mp4`

#### Scenario: Reset draws the saved order again
- **WHEN** the operator has moved `s1710003.mp4` from "Kvällen" to "Main" and presses Reset
- **THEN** the Timeline draws `s1710003.mp4` in "Kvällen" where it was saved

#### Scenario: A deleted chapter draws nothing
- **WHEN** the operator deletes the chapter "Kvällen" (listed with Undo until Save) whose clips moved to "Main"
- **THEN** the Timeline draws no band named "Kvällen" and no card for it, and draws the moved clips in "Main"

#### Scenario: A clip gone from disk mid-edit
- **WHEN** in Edit mode a proxy job ends, the page reads the event again, and `s1710004.mp4` is no longer in the read
- **THEN** the Timeline no longer draws `s1710004.mp4`, and the draft and its lists are as they were
