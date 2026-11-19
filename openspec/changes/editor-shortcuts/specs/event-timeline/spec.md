## MODIFIED Requirements

### Requirement: The track zooms, and draws only what is in view

The Timeline SHALL offer **Zoom out**, a **Zoom** slider, **Zoom in** and **Fit** in its zoom group, and, while the
track has keyboard focus (and in Edit mode's workspace wherever a workspace shortcut acts, as "The workspace answers the
Timeline's keys wherever focus is" in `web-app` says), the keys `+` or `=` (zoom in), `-` (zoom out), `0` (fit) and `\`
(fit, and pressed again at Fit, back to the zoom before it). **Fit** SHALL show the whole timeline in the track's width; zooming out SHALL stop at
Fit, or at 4 px per second when the whole event is longer than the track is wide at that scale. Zooming in SHALL stop
at 240 px per second. Zoom in and Zoom out SHALL change the scale by a factor of 1.5.

The **Zoom** slider SHALL be a slider (a native range input) named "Zoom" whose left end is Fit and whose right end is
240 px per second, with the scale between them logarithmic in the slider's position; its position SHALL always show the
current scale, however it was reached (buttons, keys, wheel or Fit following a resized window). Its value text SHALL be
"Fit" at its left end and otherwise the scale in words, rounded to a whole number ("40 px per second"). Arrow keys on it
SHALL move it in small steps, Page Up and Page Down in larger ones, Home to Fit and End to the maximum. Dragging it SHALL
zoom continuously, drawing at most once per animation frame. When Fit is already 240 px per second (a short event),
the slider SHALL be disabled.

A zoom from the buttons, the keys or the slider SHALL keep the playhead where it was in the track's view when the
playhead is in view, and the moment at the centre of the view otherwise. Turning the wheel with Ctrl held (Cmd on
macOS), and a trackpad pinch, over the track SHALL zoom about the pointer, keeping the moment under the pointer where it
is, and SHALL NOT zoom the page. Over the rest of the Timeline's own part of the page (its tool row and its lanes) it
SHALL zoom as the buttons do, about the playhead or the view's centre, and SHALL NOT zoom the page either. Elsewhere
(in Edit mode: the viewer, the bin, the inspector, the top bar) a Ctrl+wheel SHALL be left to the browser. A wheel
turned without Ctrl or Cmd SHALL scroll as before. The scale SHALL be kept per
event for the browser tab's session: a Refresh, a Save, and leaving and re-entering Edit mode SHALL show the event at
the scale it had (re-bounded to the current Fit and maximum), and a new tab SHALL open at Fit.

The track SHALL scroll horizontally inside its own box; the page SHALL NOT scroll horizontally at any width from 320 to
1280 px. At Fit the track's box SHALL NOT scroll horizontally either: its content SHALL be no wider than its box, with
the playhead at the start or at the end of the timeline, with title card blocks drawn at their minimum width, and under
a fine or a coarse pointer.

The track SHALL draw only the clips, filmstrip tiles and ruler labels that intersect the visible range, plus a margin of
one view width on each side. For an event of 400 clips, at the most zoomed-out level, the track SHALL hold fewer than
100 clip elements. Scrolling and zooming SHALL NOT change which clip a playhead time belongs to. Zooming SHALL write
nothing and send no request other than reads.

#### Scenario: Fit shows the whole event
- **WHEN** the operator presses Fit on an event of 10 minutes in a 1280 px window
- **THEN** the whole event is inside the track's width, with no horizontal scroll bar on the page

#### Scenario: Fit has no scroll bar of its own
- **WHEN** an event with a 3.0 s black title card drawn at its 24 px minimum is at Fit, at 1280 and at 390 px, under a
  fine and a coarse pointer, with the playhead first at the start and then at the end of the timeline
- **THEN** in every case the track's box is not scrollable horizontally (its scroll width equals its client width)

#### Scenario: Zooming keeps the playhead in view
- **WHEN** the playhead is at 0:42 and the operator presses Zoom in three times
- **THEN** the playhead is still inside the track's view, at the same horizontal place it had, and the slider has moved
  right

#### Scenario: Dragging the slider zooms about the playhead
- **WHEN** the playhead is in view and the operator drags the Zoom slider from its left end to its right end
- **THEN** the scale rises continuously to 240 px per second, the playhead stays within 1 px of its horizontal place in
  the view throughout, and the slider's value text reads "240 px per second"

#### Scenario: Backslash toggles Fit
- **WHEN** the track is at 90 px per second and the operator presses `\`, then `\` again
- **THEN** the first press fits the whole event and the slider reads "Fit"; the second returns to 90 px per second

#### Scenario: Ctrl and the wheel zoom at the pointer
- **WHEN** the operator holds Ctrl and turns the wheel up with the pointer over 0:30 on the track
- **THEN** the track zooms in, 0:30 stays under the pointer, and the browser's page zoom is unchanged

#### Scenario: Ctrl and the wheel over the tool row
- **WHEN** the playhead is in view and the operator holds Ctrl and turns the wheel up with the pointer over the
  Timeline's tool row
- **THEN** the track zooms in, the playhead keeps its horizontal place in the view, and the browser's page zoom is
  unchanged

#### Scenario: Ctrl and the wheel over the viewer
- **WHEN** the operator holds Ctrl and turns the wheel with the pointer over the viewer
- **THEN** the Timeline's zoom is unchanged and the wheel is left to the browser

#### Scenario: The zoom is kept for the session
- **WHEN** the operator zooms an event's Timeline to 60 px per second and presses Save, and then opens the same event in
  a new tab
- **THEN** after the save the Timeline is still at 60 px per second; the new tab's Timeline opens at Fit

#### Scenario: A short event cannot zoom
- **WHEN** an event of 3 s fits at 240 px per second
- **THEN** the slider is disabled and Zoom in is unavailable

#### Scenario: A long event is windowed
- **WHEN** an event of 400 clips is shown at its most zoomed-out level
- **THEN** the track holds fewer than 100 clip elements and scrolling to the end shows the last clip

#### Scenario: A phone-width window
- **WHEN** the Timeline is shown 320 px wide
- **THEN** the page has no horizontal scroll bar, the track scrolls inside its box, and its toolbar wraps without
### Requirement: The playhead is operable by keyboard, a frame at a time

The playhead, when it has keyboard focus, SHALL answer: Left and Right, one frame of the clip it is in (its frame rate comes from the proxy's facts; for a variable-frame-rate clip, the nominal frame interval, with no claim of frame accuracy); Shift with either, one second; Page Up and Page Down, five seconds; Home and End, the start and the end of the timeline; Space, Play or Pause. A step across a clip boundary SHALL land on the first frame of the next clip or the last frame of the previous one, and SHALL NOT skip a frame. A key SHALL be handled when the playhead has focus; in Edit mode's workspace Space, Left, Right and Shift with either SHALL also be handled wherever a workspace shortcut acts ("The workspace answers the Timeline's keys wherever focus is", `web-app`), and Up, Down, Page Up, Page Down, Home and End only on the playhead. No key SHALL be taken while focus is in one of the page's fields, so typing is not intercepted. Every control of the Timeline (the toolbar buttons, the playhead, the track) SHALL be reachable by Tab in the order they appear, with a visible focus ring, and SHALL be at least 24 px high, and 44 px under a coarse pointer.

From a key press to the new frame being presented, the 90th percentile over a run of single-frame steps SHALL be at most 60 ms in Chrome 154 and in Firefox 155 or newer, on the event's proxies.

#### Scenario: Three steps back
- **WHEN** the playhead is at 1.00 s of a 25 fps clip and the operator presses Left three times
- **THEN** the playhead is at 0.88 s of that clip and the video shows that frame

#### Scenario: Stepping across a boundary
- **WHEN** the playhead is on the last frame of one clip and the operator presses Right
- **THEN** the playhead is on the first frame of the next clip

#### Scenario: A frame step is quick
- **WHEN** a script presses Right 40 times at one-second intervals on a clip in Chrome 154 and in Firefox 155 or newer
- **THEN** the 90th percentile of the time to the presented frame is at most 60 ms in each

#### Scenario: Keys inside a field are left alone
- **WHEN** keyboard focus is in the page's search or title field and the operator presses the arrow keys
- **THEN** the playhead does not move

#### Scenario: Space after a click on a clip plays
- **WHEN** Edit mode's workspace is open, the operator clicks a clip block on the track and presses Space
- **THEN** the Timeline plays from the playhead
