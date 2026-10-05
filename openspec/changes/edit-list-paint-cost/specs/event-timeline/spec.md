## ADDED Requirements

### Requirement: Zooming, scrubbing and playing leave the Edit page around the Timeline alone

In Edit mode, zooming the Timeline (the Zoom slider, the zoom buttons and keys, Ctrl/Cmd+wheel), scrubbing the
playhead and playing SHALL NOT re-render any clip row of the page's clip list, nor any other part of the page outside the
Timeline, and SHALL NOT make the browser repaint the clip rows that are out of view.

A drag of the Zoom slider SHALL stay smooth on a large event: for an event of 400 clips in one chapter, in a
1280 × 900 window with the Timeline in view, a scripted drag of the slider from its left end to its right end and back
in 180 pointer moves SHALL take longer than 25 ms for at most 2 % of its frames, as the median of at least five runs in
Chrome 154 under a 4x CPU throttle and of at least three runs unthrottled in Firefox 155 or newer. Each figure SHALL be
recorded with the same page's idle figure (the same frame count with no drag) from the same session. The Timeline's
scrub (at least 30 distinct frames presented per second) and frame-step (90th percentile at most 60 ms) figures SHALL
still hold on the same event.

#### Scenario: A zoom renders no clip row
- **WHEN** the Timeline of an event of 400 clips is zoomed with the slider from Fit to 240 px per second, the playhead
  is scrubbed across 20 clips, and the Timeline plays for 5 s
- **THEN** a render count of the clip rows, taken in a measurement build, is the same before and after

#### Scenario: The slider drag on 400 clips is smooth in Chrome
- **WHEN** the scripted 180-move slider drag runs five times on the 400-clip event in Chrome 154 at a 4x CPU throttle
- **THEN** the median share of frames over 25 ms is at most 2 %, recorded with the idle page's share from the same
  session

#### Scenario: The slider drag on 400 clips is smooth in Firefox
- **WHEN** the same drag runs three times unthrottled in Firefox 155 or newer
- **THEN** the median share of frames over 25 ms is at most 2 %

#### Scenario: The scrub gates still hold
- **WHEN** the scrub and frame-step scripts run on the 400-clip event in Chrome 154 and in Firefox 155 or newer
- **THEN** the scrub presents a median of at least 30 distinct frames per second and the frame-step 90th percentile is
  at most 60 ms in each

## MODIFIED Requirements

### Requirement: In Edit mode a clip block's edges are Trim In and Trim Out tools

In Edit mode, each clip block the Timeline draws with its detail (not drawn as a bare block for being too narrow) SHALL
have two **edge tools**: **Trim In** on its left edge (the clip's start edge) and **Trim Out** on its right edge (its
end edge). An edge tool's pointer zone SHALL lie inside its own block, along the edge: 8 px wide with a fine pointer
and 24 px wide with a coarse one, never wider than a third of the block, and the track's height; so at the boundary of
two clips the left clip's Trim Out zone and the right clip's Trim In zone lie side by side and do not overlap. Over a
zone the pointer SHALL show a trim cursor shaped as a bracket with arrows (`[` for Trim In, `]` for Trim Out), given
as an image with the `ew-resize` keyword as its fallback, and the edge SHALL show a highlighted bracket, so the tool
is visible without a cursor (a finger). Where a zone and an interior cut handle's area overlap, a press SHALL go to
the nearer edge, the earlier of two equally near, and SHALL select and focus the tool that took it. The edge tools
SHALL NOT exist in the read view, on a clip drawn as a bare block, or on a clip outside the window the track draws,
except that the tools of a clip whose edge tool holds focus stay until focus leaves them (a key that narrows the block
to a bare one does not take the tool from under the keyboard);
zooming in gives a narrow clip its tools.

While a zoom is in progress (a Zoom-slider drag from press to release, a burst of Ctrl/Cmd+wheel or pinch input, the
zoom buttons or the `=` and `-` keys pressed or held in repeat), the edge tools SHALL NOT exist on any clip, as they do
not exist behind a rippling drag, except the one edge tool that holds focus when the zoom starts, which SHALL stay
rendered and focused. The zoom SHALL count as **settled** on the slider's release, or 150 ms after the last zoom input
of any other kind; on settle the edge tools of every clip drawn with its detail SHALL be rendered once at the new zoom,
and the trim cursor and the bracket SHALL show again where the pointer rests, without the pointer having to move.
Zooming SHALL NOT edit the draft, move focus or announce anything about the edge tools.

#### Scenario: Hovering a clip's left edge
- **WHEN** in Edit mode at 40 px per second the mouse rests 3 px inside the left edge of `s1710001.mp4`'s block
- **THEN** the cursor is the Trim In bracket (the computed `cursor` holds an image and the fallback `ew-resize`), and
  the edge shows its bracket
- **WHEN** the mouse moves to the middle of the block
- **THEN** the cursor is the block's ordinary cursor and no bracket is highlighted

#### Scenario: A boundary between two clips
- **WHEN** the mouse rests 3 px left of the boundary between `s1710001.mp4` and `s1710002.mp4`, then 3 px right of it
- **THEN** it is first the Trim Out tool of `s1710001.mp4`, then the Trim In tool of `s1710002.mp4`

#### Scenario: No tools outside Edit mode or on a bare block
- **WHEN** the operator is in the read view (which shows no Timeline), or a clip is drawn as a bare block at the lowest
  zoom of a 400-clip event
- **THEN** no edge tool, trim cursor or bracket exists for those clips

#### Scenario: The edge tools step aside while the slider is dragged
- **WHEN** in Edit mode on an 80-clip event the operator presses the Zoom slider's thumb and drags it
- **THEN** while the thumb is held no Trim In or Trim Out tool exists in the page and no trim cursor is shown
- **WHEN** the operator releases the thumb
- **THEN** every clip in view that is drawn with its detail has its Trim In and Trim Out tools again, placed at the new
  zoom

#### Scenario: The trim cursor comes back without moving the mouse
- **WHEN** the mouse rests over the track and the operator zooms with the `=` key, and once the zoom has settled a Trim
  In zone lies under the resting pointer
- **THEN** the cursor is the Trim In bracket and that edge shows its bracket, without the mouse moving

#### Scenario: Wheel and key zooms settle after a pause
- **WHEN** the operator zooms with five Ctrl+wheel steps 40 ms apart, or holds `=` in key repeat
- **THEN** no edge tool exists from the first step until 150 ms after the last one, when the tools of the clips in view
  exist again

#### Scenario: A focused edge tool keeps focus through a zoom
- **WHEN** focus is on "Trim end of s1710001.mp4" and the operator presses `=` three times, then zooms with three
  Ctrl+wheel steps
- **THEN** during each zoom that one tool still exists and holds focus (no other edge tool exists), and after the zoom
  settles focus is still on it and every clip in view has its tools again
- **WHEN** the operator then presses the Zoom slider
- **THEN** focus moves to the slider, as a press on it always does, and no edge tool is kept during that drag
