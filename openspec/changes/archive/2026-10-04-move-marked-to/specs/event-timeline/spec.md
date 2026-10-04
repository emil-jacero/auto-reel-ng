## MODIFIED Requirements

### Requirement: Trimming is unavailable while a save or a move is pending, and where there is nothing to trim

While a save is in flight or a move of marked clips is pending, the trim handles and the selected cut's fields SHALL say that they are unavailable (`aria-disabled`, in words in the group) and SHALL change nothing when used, as the Cuts panel's controls do; the playhead and playing SHALL stay usable. A clip with no ready proxy SHALL have no timeline presence ("The Timeline asks for the clips' proxies when they are missing"), so it has no handle; its cuts stay editable in its Cuts panel by typed times. A drag in progress when a save starts SHALL end as if Escape were pressed.

#### Scenario: A pending save leaves handles inert
- **WHEN** a cut was trimmed, the operator presses Save, and the service has not answered
- **THEN** the handles and fields say that they are unavailable and a press on a handle moves nothing, while Play and the playhead work and keyboard focus stays on Save

#### Scenario: Proxies missing for some clips
- **WHEN** the operator opens the Timeline in Edit mode on an event with a clip whose proxy is absent
- **THEN** the Timeline shows the Prepare state and no handle, and every clip's Cuts panel still adds and removes cuts by typed times

### Requirement: Decisions are unavailable while a save or a move is pending

While a save is in flight or a move of marked clips is pending, Approve, Dismiss and Restore SHALL say that they are unavailable (`aria-disabled` on the buttons, in words in the detail, as the trim handles do) and SHALL change nothing, whether pressed or keyed; selecting a mark, moving between marks and the playhead SHALL stay usable. A decision SHALL never be announced as done when no change was made.

#### Scenario: A pending save blocks the decision
- **WHEN** the operator presses Save and, before the service answers, presses Approve as cut on a pending mark and presses A on another
- **THEN** no cut is added, nothing is announced as approved, the buttons read as unavailable, and when the save has ended both marks are still pending

### Requirement: The card handle is operable by touch, inert while a save is pending, and smooth

The card handle's pressable area SHALL be at least 24 px wide for a fine pointer and 44 px for a coarse one, centred on
the edge, and a swipe starting elsewhere on the Timeline SHALL still scroll it. The handle lies in the card lane, a row of its own above the clips, so its area SHALL NOT cover a trim
handle's. While a save or a move of marked clips is pending the handle SHALL change nothing
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
