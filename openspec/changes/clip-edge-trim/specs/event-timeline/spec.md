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
- the dragged clip's own analysis marks SHALL be hidden (they are drawn from its committed extent and would stray from
  its footage); the marks of the clips after it move with them, and the release draws every mark where it belongs

The rest of the editor SHALL NOT change until release: the Cuts panels, the save bar and the draft show nothing new,
and `Q` and `W` pressed while any press or drag on the Timeline is held SHALL edit nothing.
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
than 25 ms; at every width from 320 to 1280 px the edge tools, their tip and the ripple SHALL NOT widen the page beyond what it
is without them (the Edit page's own 17 px overflow at 320 px predates this change and is not its gate); with `prefers-reduced-motion:
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

## MODIFIED Requirements

### Requirement: Edit mode's cuts are trim handles

In Edit mode, each cut the Timeline draws on a clip that offers a Cuts panel (an included or new clip on disk whose proxy is ready) SHALL have two **trim handles**, one on its start and one on its end. The handles belong to the cut as the clip's Cuts panel lists it: the cut keeps its place in the list, its number, its reason and its identity while a handle moves, and a cut marked removed has no handle. A handle SHALL be a slider (`role="slider"`, horizontal), reachable by Tab, in the order of time: the clips in play order, and in each clip the cuts by start, a cut's start handle before its end handle, after the playhead. It SHALL be named "Cut <n> start of <name>" or "Cut <n> end of <name>", where <name> is the clip as its row names it and <n> the cut's number in that clip's Cuts panel (the panel's own numbering, removed cuts counted), so no two handles of a clip share a name. It SHALL expose `aria-valuenow` as its time in the clip in seconds, and `aria-valuemin` and `aria-valuemax` as the least and greatest time it can take now, and a value text that gives its time in the Cuts panel's time format followed by the cut's span in words ("0:01.5, the cut runs 0:01.5 to 0:03"). A visible description, referenced by `aria-describedby`, SHALL list the keys of "A trim handle is moved by keyboard".

A handle SHALL take only places the cut can legally take, and its range SHALL always hold the value it has:

- the **start** can go no earlier than the clip's start or the end of the nearest cut before it that it does not overlap, and no later than three frames of the clip before its own end
- the **end** can go no later than the clip's length (the proxy's duration) or the start of the nearest cut after it that it does not overlap, and no earlier than three frames of the clip after its own start
- a cut already shorter than three frames, a cut that runs past the clip's end, and cuts that overlap each other in `reel.yaml` SHALL keep a range that holds their current times; looking at a cut SHALL NOT change it
- the limits are frame times of the clip's own frame rate (taken from the proxy's facts), so that Home and End reach a time the clip can show
- a cut touching another, one's end at the other's start, is a legal place

A leading or trailing cut ("The track lays the clips out") is not drawn and SHALL have no handle; it stays listed and editable in its Cuts panel, and a cut that runs past the clip's end is such a trailing cut. A handle MAY be dragged or stepped to the clip's start or end, or to touch a leading or trailing cut, within its limits: on release the cut becomes part of the leading or trailing cut, its block shortens and its handles are gone. If it was the selected cut, it stays selected when it is now the clip's edge cut (the leading cut that ends latest, or the trailing cut that starts earliest), whose times its Trim In or Trim Out ("In Edit mode a clip block's edges are Trim In and Trim Out tools") and the selected cut's fields now edit; otherwise nothing is selected.

Cuts the render joins into one span SHALL still have a handle each at their own edges.

Handles SHALL exist exactly where the track draws the clip's cut spans: a clip drawn too narrow to show its cuts (the track draws it as a block) has no handle until the operator zooms in, and a clip outside the window the track draws has none either ("The track zooms, and draws only what is in view"). Moving the playhead scrolls the view to it, which brings the clips around it, and so their handles, into the window; this is how keyboard focus reaches a cut that is far from the view.

#### Scenario: Handles are named and carry their limits
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, whose `s1710001.mp4` (6.02 s, a 50 fps proxy, three frames are 60 ms) has a cut from 1.0 to 2.5 s and one from 4.0 to 5.0 s, the operator opens the Timeline and tabs to its first handle
- **THEN** the handle is named "Cut 1 start of s1710001.mp4", has `aria-valuenow` 1, `aria-valuemin` 0 and `aria-valuemax` 2.44, and says "0:01, the cut runs 0:01 to 0:02.5"; the next Tab stops at "Cut 1 end of s1710001.mp4" with `aria-valuemin` 1.06 and `aria-valuemax` 4

#### Scenario: A removed cut has no handle
- **WHEN** the operator removes cut 1 of `s1710001.mp4` in its Cuts panel
- **THEN** the Timeline draws no handle for it and the handles of the other cut keep the names "Cut 2 start of s1710001.mp4" and "Cut 2 end of s1710001.mp4"; pressing Undo brings cut 1's handles back

#### Scenario: A cut shorter than three frames is not widened
- **WHEN** a cut of 5.000 to 5.050 s was read from `reel.yaml`, and the operator focuses its end handle and then its start handle
- **THEN** the end handle's range begins at 5.05 and the start handle's ends at 5.0, so each can only widen the cut; the cut is unchanged by focusing, and Left on the end handle (which would shorten it further) changes nothing

#### Scenario: A cut past the clip's end
- **WHEN** `s1710001.mp4` (6.02 s) lists a cut from 5.0 to 7.0 s
- **THEN** the Timeline draws no span and no handle for it, the clip's block ends at 5.0 s of the clip, and the cut is listed in its Cuts panel with its times unchanged

#### Scenario: A handle taken to the clip's start makes a leading cut
- **WHEN** `s1710001.mp4` has a cut from 1.0 to 2.5 s and the operator presses Home on its start handle and then leaves the handle
- **THEN** the cut runs from 0 to 2.5 s in the draft, the Timeline draws no span and no handle for it, the clip's block starts at 2.5 s of the clip and is 2.5 s shorter, the clips after it start 2.5 s earlier on the track, and cut 1 stays selected as the clip's start edge cut, its fields showing 0 to 2.5 s

#### Scenario: A clip too narrow to show its cuts
- **WHEN** at the lowest zoom of a 400-clip event a clip is drawn as a block with no cut spans
- **THEN** it has no handle, its cuts are still listed and editable in its Cuts panel, and zooming in until its cuts are drawn gives it its handles

#### Scenario: Overlapping cuts from disk
- **WHEN** a clip lists cuts 2.0 to 4.0 s and 3.5 to 5.0 s
- **THEN** the track draws one joined span with four handles, each with a range that holds its current time, and no range is inverted
