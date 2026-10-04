## ADDED Requirements

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
- **WHEN** the Timeline is shown outside Edit mode, or a clip is drawn as a bare block at the lowest zoom of a
  400-clip event
- **THEN** no edge tool, trim cursor or bracket exists for those clips

### Requirement: Dragging an edge trims the clip and ripples the track

Pressing an edge tool with a mouse, a pen or a finger and moving SHALL move the edge by the distance the pointer moves,
as the timeline model places an edge (snapping, joining, limits; "An edge dragged to a place snaps, joins, and makes
one edit"). Moving inward SHALL trim the clip's start or end, moving outward SHALL restore it, up to the start or end
of the file. While dragging, on every frame:

- the block SHALL show the movie as it will play: a dragged Trim In keeps the block's left side where it is and shows
  the new first kept frame there, a dragged Trim Out moves the block's right side with the pointer, and in both cases
  the block's width is the clip's new kept extent and every block, card, chapter band and ruler label after it moves by
  the change, with no gap
- a tip beside the edge SHALL give the signed change in the clip's playing length and its new playing length
  ("−0:00.5 · 0:03.02"), and the words "Joined with cut <n>" when the edge has joined an interior cut
- at the start or end of the file the edge SHALL be shown in the limit's colour with a changed bracket and the words
  "Start of the file" or "End of the file"; at another limit it SHALL say why it stopped ("The clip keeps three
  frames", "The clip keeps 0.1 s", "Held by cut 1"); the words carry the state, not the colour alone
- while snapped, a line SHALL show at the snapping place and the tip SHALL say what it snapped to ("Snapped to the
  playhead", "Snapped to cut 2 start", "Snapped to 0:03")

The rest of the editor SHALL NOT change until release: the Cuts panels, the save bar and the draft show nothing new.
Releasing SHALL make the one edit the model gives for the place (add, trim or remove the edge cut, or nothing), as one
edit of the draft, saved by the existing Save and put back by Reset; the clip's Cuts panel then lists the cut as any
cut. Releasing SHALL announce the result once, politely, through Edit mode's one live region ("s1710001.mp4 start
trimmed by 0.5 s, plays 0:03.02.", "s1710001.mp4 start restored to the start of the file."). Escape, or the browser
cancelling the pointer, SHALL end the drag with the track as it was and no edit; a drag that ends where it began SHALL
make no edit. Only one drag SHALL run at a time on the Timeline (edges, cut handles, card handles).

`S` (with no modifier, while focus is on the track, the playhead or an edge tool) SHALL switch snapping of edge drags
off and on for the page visit and announce the new state; holding Alt during a drag SHALL place the edge without
snapping for as long as it is held.

#### Scenario: Trimming the start of a clip
- **WHEN** in Edit mode at 40 px per second `s1710001.mp4` (6.02 s, 50 fps, cuts 1.0 to 2.5 s and 4.0 to 5.0 s) is
  followed by `s1710002.mp4`, and the operator presses its Trim In and moves 20 px right
- **THEN** the block is 20 px narrower with its left side unmoved and its first tile showing 0:00.5, the block of
  `s1710002.mp4` has moved 20 px left, the tip says "−0:00.5 · 0:03.02", and the Cuts panel and save bar are unchanged
- **WHEN** the operator releases
- **THEN** the clip's Cuts panel lists a `manual` cut 0:00 to 0:00.5, the save bar counts one change, and the live
  region says "s1710001.mp4 start trimmed by 0.5 s, plays 0:03.02."

#### Scenario: Restoring to the start of the file
- **WHEN** the operator presses the same Trim In and moves 40 px left
- **THEN** the edge stops at the start of the file, shown in the limit's colour with the words "Start of the file"
- **WHEN** the operator releases
- **THEN** the cut 0:00 to 0:00.5 is gone from the draft and no save bar is shown if nothing else was edited

#### Scenario: Trimming the end of a clip
- **WHEN** the operator drags Trim Out of `s1710001.mp4` 20 px left
- **THEN** the block's right side and everything after it move 20 px left with the pointer, and releasing adds a
  `manual` cut 0:05.52 to 0:06.02

#### Scenario: Joining an interior cut
- **WHEN** the operator drags Trim In of `s1710001.mp4` to 1.2 s
- **THEN** the block starts at the clip's 2.5 s, the tip says "Joined with cut 1", and cut 1 is no longer drawn
- **WHEN** without releasing the operator moves back to 0.9 s
- **THEN** cut 1 is drawn again as a hatched span inside the block

#### Scenario: Snapping and the switch
- **WHEN** the playhead is at 1.6 s of `s1710002.mp4` and the operator drags its Trim In to within 8 px of the
  playhead
- **THEN** the edge is at 1.6 s, a line shows there and the tip says "Snapped to the playhead"
- **WHEN** the operator holds Alt and moves 1 px
- **THEN** the edge follows the pointer to the nearest frame without snapping
- **WHEN** the operator, after releasing, presses `S` with focus on the track
- **THEN** the live region says that snapping is off, and the next edge drag does not snap

#### Scenario: Escape and a zero move
- **WHEN** the operator drags an edge and presses Escape before releasing
- **THEN** every block is back where it was and the draft is unchanged
- **WHEN** the operator presses an edge and releases without moving
- **THEN** nothing is edited and no save bar appears

#### Scenario: Save writes the trims
- **WHEN** the operator trims the start of `s1710001.mp4` to 0:00.5 and its end to 0:05.5 and presses Save
- **THEN** the event's `reel.yaml` lists, under that clip's `trims`, a span `in: 0, out: 0.5` and a span `in: 5.5,
  out: 6.02` with the reason `manual`, beside its two interior cuts as they were

### Requirement: Each edge is a slider operable by keyboard, with Q and W at the playhead

Each edge tool SHALL be a slider (`role="slider"`, horizontal) reachable by Tab: in each clip the Trim In before the
clip's cut handles and the Trim Out after them, in play order, after the playhead. It SHALL be named "Trim start of
<name>" or "Trim end of <name>" (<name> as the clip's row names it), expose `aria-valuenow` as the edge's place in
the clip in seconds and `aria-valuemin` and `aria-valuemax` as its limits, and a value text giving the trim and the
playing length ("Start trimmed by 0.5 s, plays 0:03.02"; "Start not trimmed, plays 0:03.52"). A visible description,
referenced by `aria-describedby`, SHALL list its keys. With focus on an edge tool:

- Left and Right SHALL move the edge one frame earlier or later, Shift with Left or Right one second (to the nearest
  frame), Home and End to its lowest and highest place; each key SHALL make one edit of the draft (the same edit a
  release would make), stop at a limit, change nothing at a limit, and SHALL NOT scroll the page
- a key's result SHALL be given by the slider's value and SHALL NOT also be announced, except a join or a limit, which
  SHALL be announced
- focus SHALL scroll the edge into the track's view, and pressing or focusing an edge with an edge cut SHALL make that
  cut the selected cut, so its times can be typed in the selected cut's fields

`Q` and `W` (no modifier, while focus is on the track, the playhead, an edge tool or a cut handle, never in a field)
SHALL trim the start, respectively the end, of the clip the playhead is in to the playhead, as one edit with the
limits and joining of a drag, and announce the result. After `Q` the playhead SHALL stay on its frame, now the clip's
first; after `W` it SHALL be at the clip's new end. With the playhead in a title card, or `Q`/`W` at a place the edge
already holds, nothing SHALL change and the live region SHALL say why.

#### Scenario: Frame steps on the start edge
- **WHEN** focus is on "Trim start of s1710001.mp4" (not trimmed, 50 fps) and the operator presses Right three times
- **THEN** the value is 0.06, the value text says "Start trimmed by 0.06 s", and the clip's Cuts panel lists a cut
  0:00 to 0:00.06

#### Scenario: Home restores, End trims to the limit
- **WHEN** the operator presses Home
- **THEN** the start is not trimmed and the cut is gone from the draft
- **WHEN** the operator presses End
- **THEN** the value is 5.92, the clip plays 0.1 s, the tool keeps focus, and the live region says the edge joined
  cuts 1 and 2 and that the clip keeps 0.1 s

#### Scenario: Q trims the start to the playhead
- **WHEN** the playhead is at 3.2 s of `s1710002.mp4` (not trimmed) and the operator presses `Q` with focus on the
  track
- **THEN** that clip lists a `manual` cut 0:00 to 0:03.2, its block starts at that frame, the playhead still shows it,
  and the live region says "s1710002.mp4 start trimmed by 3.2 s, …"

#### Scenario: W trims the end to the playhead
- **WHEN** the playhead is at 3.2 s of `s1710002.mp4` and the operator presses `W`
- **THEN** the clip's end edge is 3.2 s and the playhead is at the clip's new end

#### Scenario: Q in a title card
- **WHEN** the playhead is in a black title card and the operator presses `Q`
- **THEN** nothing changes and the live region says that the playhead is not in a clip

#### Scenario: Keys in a field are left alone
- **WHEN** focus is in the selected cut's start field and the operator types `q`
- **THEN** the field receives the letter and no edge moves

### Requirement: Edge trimming is unavailable while a save or a move is pending, and holds the Timeline's gates

While a save is in flight or a move of marked clips is pending, the edge tools SHALL say that they are unavailable
(`aria-disabled`, a not-allowed cursor, words in the group) and change nothing when pressed, used by key, or by `Q`
and `W`; a drag in progress when a save starts SHALL end as if Escape were pressed. A finger pressing an edge tool and
moving SHALL drag the edge and SHALL NOT scroll the track; a swipe elsewhere still scrolls it. The Timeline SHALL keep
its gates with edge tools: at 400 clips the elements it creates stay bounded by the view (windowing counts edge
tools); at 80 clips under a 4x CPU throttle in Chrome, at most 2 % of the frames of a scripted edge drag take longer
than 25 ms; every width from 320 to 1280 px fits without a horizontal page scroll bar; with `prefers-reduced-motion:
reduce` the brackets, tip and ripple do not animate; the brackets, limit edge, tip and snap line follow the page's
scheme in light and dark with the contrast the page meets; and an edge's state (hovered, focused, dragged, snapped, at
a limit, unavailable) is never shown by colour alone. All of this SHALL hold in Chrome 154 and Firefox 155 or newer.

#### Scenario: A pending save leaves edges inert
- **WHEN** a clip was trimmed, the operator presses Save and the service has not answered
- **THEN** the edge tools say they are unavailable, a press on one moves nothing and `Q` changes nothing, while Play
  and the playhead work

#### Scenario: A long event stays windowed and smooth
- **WHEN** the Timeline of a 400-clip event is open in Edit mode and scrolled to the middle
- **THEN** only the edge tools of the clips in or near the view exist in the page
- **WHEN** an edge of an 80-clip event is dragged by script under a 4x CPU throttle in Chrome
- **THEN** at most 2 % of the frames take longer than 25 ms

#### Scenario: Layouts and schemes
- **WHEN** Edit mode's Timeline is looked at in Chrome and Firefox at 1280 and 390 px, light and dark, during an edge
  drag at the start of the file
- **THEN** the page does not scroll horizontally and the bracket, the limit edge, its words and the tip are legible
