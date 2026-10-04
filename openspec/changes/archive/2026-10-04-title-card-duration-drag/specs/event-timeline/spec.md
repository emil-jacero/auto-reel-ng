## ADDED Requirements

### Requirement: A card block's end edge is dragged to set the card's length

In Edit mode, the end edge of every title-card block on the Timeline SHALL be a handle that sets that card's
`duration` in the draft. Pressing it with a mouse, a pen or a finger, and moving, SHALL move the edge by the distance
the pointer moves from where the edge was, in whole tenths of a second, snapping to a whole second within 8 screen
pixels, and staying between the card's limits (0.5 s to 60 s, and for a card over video no more than the first span of the
chapter's anchor clip that the draft's cuts keep). While dragging, the block, the handle and a readout in the Timeline's
fixed-width clock style ("Card 4.0 s") SHALL follow the pointer, and the rest of the editor SHALL NOT change: the
chapter list's card row, the save bar and the draft show nothing new until the pointer is released. The readout and
the snap to a whole second SHALL be given in words and by a line, not by colour alone. Releasing SHALL make one edit
of the draft, the card's duration, and announce the result once, politely, through Edit mode's one live region ("Title
card for Reception now 6.0 s. The movie is 2.0 s longer."). Escape, or the browser cancelling the pointer, SHALL end the
drag with the card as it was and no edit. A drag that ends where it began SHALL make no edit. Pressing the handle SHALL
select the card, as pressing its block does.

#### Scenario: A drag sets the length
- **WHEN** at 40 px per second the operator presses the end edge of the opening card (4.0 s, black) and moves the pointer 80 px right
- **THEN** the readout says "Card 6.0 s" while dragging, and the chapter list's card row still says 4.0 s until the pointer is released

#### Scenario: Releasing makes one edit
- **WHEN** the operator releases the pointer there
- **THEN** the card row says 6.0 s, the save bar counts one changed card, the live region says so once, and Save writes `card.duration: 6.0` for that chapter

#### Scenario: Snapping to a whole second
- **WHEN** the operator moves the edge to 4.96 s's worth of pixels at 40 px per second
- **THEN** the card is 5.0 s, a line shows the second, and the readout says it snapped

#### Scenario: The ends of the range
- **WHEN** the operator drags the edge far left, then far right, of a black card
- **THEN** it stops at 0.5 s, then at 60.0 s, and never takes a value between the pointer and a limit that the engine would refuse

#### Scenario: Escape cancels
- **WHEN** the operator presses Escape during a drag
- **THEN** the card is as it was, the draft is unchanged, and the chapter list is unchanged

#### Scenario: A drag that ends where it began
- **WHEN** the operator drags the edge away and back to 4.0 s and releases
- **THEN** the draft is unchanged and the save bar does not count a change

#### Scenario: Reset and Save are as for any edit
- **WHEN** the operator changes a card's length and presses Reset
- **THEN** the card is back at its saved length, and the save bar shows no change

### Requirement: A black card's drag moves everything after it, and a video card's is bounded by its clip

While the end edge of a black card (its own span, adding time) is dragged, every clip, chapter band and card after it
SHALL move with the edge, the Timeline's ruler and length SHALL follow, and the playhead SHALL stay on the moment of
the content it is in. The edge of a card over the start of its chapter's first clip (adding no time) SHALL NOT move
anything else, and SHALL NOT go beyond the length of the first span of that clip that the draft's cuts keep; a cut edited a moment earlier SHALL
already count. A card longer than its clip when the Timeline opens (the clip was trimmed after) SHALL keep its value,
SHALL be draggable only down to the limits, and SHALL be described in words as longer than its clip. A card that
cannot be adjusted (the first kept span of its anchor clip is shorter than 0.5 s; a chapter with no footage has no card block at all) SHALL show its handle
as disabled, with the reason in its accessible description, and SHALL change nothing.

#### Scenario: Later content follows a black card
- **WHEN** the operator drags the opening black card from 4.0 s to 6.0 s in a three-chapter event
- **THEN** every later block starts 2.0 s later while dragging, the length readout is 2.0 s longer, and nothing before the card moved

#### Scenario: The playhead keeps its content
- **WHEN** the playhead is 3.0 s into the second chapter's first clip during that drag
- **THEN** it is on that same moment of the clip, 2.0 s later on the ruler, and the scrub video does not change frame

#### Scenario: A video card cannot outgrow its footage
- **WHEN** the first kept span is 2.45 s and the operator drags the video card's edge to the right
- **THEN** it stops at 2.4 s (or at its current length, when that is longer) and no other block moves

#### Scenario: A trim already counts
- **WHEN** the operator trims the chapter's first clip shorter and then drags its video card
- **THEN** the limit is the clip's length with that trim

#### Scenario: A card longer than its clip
- **WHEN** a video card of 5.0 s sits over a first clip that is now 3.0 s after its cuts
- **THEN** the handle reads 5.0 s, can only be dragged down, and its description says it is longer than its clip

#### Scenario: A card that cannot be adjusted
- **WHEN** a video card's first kept span is shorter than 0.5 s
- **THEN** the handle is disabled, its description says the footage is too short for a card, and a press or a key changes nothing

### Requirement: A card's length is moved by keyboard with slider semantics

A card block's handle SHALL be a slider named for its card ("Title card length, Reception"), with its minimum,
maximum and current value in seconds (`aria-valuemin`, `aria-valuemax`, `aria-valuenow`) and a value text such as
"Card 4.0 s", focusable by Tab in time order with the other handles. With focus on it, each key SHALL make one edit of
the draft and reach only places within the card's limits: Left and Down 0.1 s shorter; Right and Up 0.1 s longer;
Shift with those, to the nearest whole second in that direction; Home the lowest; End the highest. A key past a limit
SHALL stop at the limit and a key at a limit SHALL change nothing. Escape SHALL cancel a drag and otherwise do nothing.
A key SHALL be handled only when the handle has focus, SHALL NOT scroll the page, and SHALL NOT be taken inside a
field. A key's result SHALL be given by the value text and SHALL NOT also be announced through the live region. While
the handle has focus it SHALL be scrolled into view if its edge is outside the Timeline's view.

#### Scenario: Tenths and seconds
- **WHEN** focus is on "Title card length, Reception" (4.3 s) and the operator presses Right, then Shift+Right
- **THEN** the card is 4.4 s, then 5.0 s, and the handle's value text reads "Card 5.0 s"

#### Scenario: Home and End
- **WHEN** the operator presses Home, then End on a black card
- **THEN** the card is 0.5 s, then 60.0 s

#### Scenario: At a limit
- **WHEN** the card is 0.5 s and the operator presses Left
- **THEN** nothing changes and nothing is announced

#### Scenario: Keys inside a field
- **WHEN** focus is in the title field of the card inspector or any other field and the operator presses Right
- **THEN** the card's length is unchanged

### Requirement: The card handle is operable by touch, inert while a save is pending, and smooth

The card handle's pressable area SHALL be at least 24 px wide for a fine pointer and 44 px for a coarse one, centred on
the edge, and a swipe starting elsewhere on the Timeline SHALL still scroll it. The handle lies in the card lane, a row of its own above the clips, so its area SHALL NOT cover a trim
handle's. While a save or a Move clips is pending the handle SHALL change nothing
for any input, as trim handles do. The drag SHALL stay smooth in Chrome and in Firefox 155 or later: at 80 clips, in the median of at least five runs under
a 4x CPU throttle in Chrome, at most 5 % of the frames of a scripted drag of a black card, including the shift of the
later content, take longer than 25 ms (the same page idle takes up to 4 % on a shared host), and in the median of three
runs of the same script unthrottled in Firefox at most 2 %. The later content SHALL be moved with the edge as already
drawn layers, and the real layout drawn once, on release. The handle and its readout SHALL
be legible in light and dark colour schemes at widths from 320 to 1280 px with no horizontal scrolling of the page, and
SHALL NOT animate under reduced motion. No dependency SHALL be added.

#### Scenario: A finger
- **WHEN** a finger presses 20 px to either side of a card's end edge on a coarse-pointer device and moves
- **THEN** the card handle takes it, and a swipe 60 px away scrolls the track

#### Scenario: A card's end above a clip's trim handle
- **WHEN** a card's end edge sits at the same place along the track as a cut's start handle
- **THEN** a press in the card lane takes the card's handle, and a press in the clip row takes the trim handle

#### Scenario: A pending save
- **WHEN** a save is in flight and the operator presses the handle or a key on it
- **THEN** nothing changes

#### Scenario: A long event stays smooth
- **WHEN** a black card is dragged in an 80-clip event under a 4x CPU throttle in Chrome, and unthrottled in Firefox
- **THEN** the median over at least five runs (Chrome) and three runs (Firefox) is at most 5 % and 2 % of the frames over 25 ms, and the figures, with the idle page's in the same session, are recorded

#### Scenario: The later content moves with the edge and lands where it was
- **WHEN** a black card's edge is dragged 2 s longer and released
- **THEN** during the drag every clip, chapter band after the card, card block, trim handle, analysis mark and the playhead behind the card is 2 s further right, the card's own chapter band is 2 s wider, the ruler's labels and the summary line show the new length, and on release the drawn layout is the same one (apart from the fitted zoom), with nothing left moved; Escape puts everything back

#### Scenario: Layouts and schemes
- **WHEN** the Timeline is shown at 1280 px and at 390 px, in light and in dark
- **THEN** the handle, the line and the readout are legible and the page does not scroll horizontally

#### Scenario: The dependency list is unchanged
- **WHEN** `web/package.json` is read after the change
- **THEN** `dependencies` and `devDependencies` hold the same packages as before
