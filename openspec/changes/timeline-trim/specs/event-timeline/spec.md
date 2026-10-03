## REMOVED Requirements

### Requirement: The event page offers a Timeline that loads nothing until it is opened
**Reason**: Replaced by "The read view and Edit mode each offer a Timeline that loads nothing until it is opened". The requirement said that Edit mode shows no Timeline section, and its scenario "Edit mode has no timeline" is the opposite of what this change builds (the Timeline is where a cut is trimmed, and the draft, Save and the 412 conflict belong to Edit mode). A MODIFIED block cannot drop or rename that scenario, so the requirement is re-stated under a new name.
**Migration**: None for clients. The rest of the requirement (closed until opened, nothing loaded while closed, opening is a read, the movie and the Timeline do not play together) is carried over unchanged into the new one.

## MODIFIED Requirements

### Requirement: The track lays the clips out by their proxies' lengths, with the chapters and the cuts

With every shown clip ready, the Timeline SHALL show, in one horizontally scrolling track:

- a **ruler** with time labels in the page's time format (`m:ss`, with fractions only when zoomed in far enough that labels would repeat)
- the **clips end to end** in play order, each as wide as its proxy's duration at the current zoom, labelled with its name as the page names it. A proxy has the source's timestamps, so a time in a proxy is the same time in the source clip. A clip's length SHALL come from its proxy's facts, never from the browser's reading of a file and never defaulted; a clip shorter than a pixel at the current zoom SHALL still be drawn, one pixel wide at least, and the playhead SHALL be able to be put in it by keyboard.
- a **chapter band** above the clips: one segment per chapter spanning its shown clips, labelled with the chapter's name, or as the page headings an unnamed chapter ("Main" beside named chapters, "Clips" when none is named). The band's labels stay in view while their chapter scrolls past.
- each clip's **cuts**, as the event page lists them from `reel.yaml` (in Edit mode: as the Cuts panels list them now, the draft's, with the ones marked removed left out), drawn over the clip as spans with a hatch pattern and named by their reason in words ("manual", "black", "white", "freeze") in the span's text alternative; overlapping or touching cuts SHALL be drawn as the render joins them, one span; a cut that runs past the proxy's duration SHALL be drawn to the end of the clip only. In the read view the spans SHALL be read-only: no handle, no drag, no edit. In Edit mode each cut SHALL have the two trim handles of "Edit mode's cuts are trim handles", drawn over the joined span.
- the **movie's length**: the sum of the shown clips' lengths minus the time the cuts remove, beside the source length, in words ("Movie 3:12 of 3:45 of footage")

If the cuts cannot be read (the same read the page's cut summaries use), the Timeline SHALL show the track without cut spans and SHALL say in a note that the cuts could not be read, and SHALL NOT show the movie's length as if there were no cuts.

#### Scenario: Clip widths follow the facts
- **WHEN** an event has clips whose proxies report 24.96 s, 3.2 s and 0.48 s at 40 px per second
- **THEN** the clips are drawn about 998, 128 and 19 px wide, in play order, each labelled with its name, with the 0.48 s clip still focusable

#### Scenario: A rotated phone clip keeps its source time
- **WHEN** a clip's source is a rotated phone clip of 12.0 s and its proxy reports a duration of 12.0 s
- **THEN** the clip is drawn 12.0 s long, and a cut at 3.0 to 4.5 s in `reel.yaml` is drawn from 3.0 to 4.5 s of that clip

#### Scenario: Chapters are bands, not guesses
- **WHEN** an event has the chapters "Dag 1" with two clips and "Kvällen" with one
- **THEN** the band shows "Dag 1" over the first two clips and "Kvällen" over the third, and an event with a single unnamed chapter shows "Clips" over all of them

#### Scenario: Overlapping cuts are one span
- **WHEN** a clip lists cuts 2.0 to 4.0 s and 3.5 to 5.0 s
- **THEN** the track draws one hatched span from 2.0 to 5.0 s, and the movie's length is shorter by 3.0 s for that clip

#### Scenario: A cut that cannot be read
- **WHEN** reading `reel.yaml`'s cuts fails while the proxies are ready
- **THEN** the track is shown without cut spans, a note says that the cuts could not be read, and no movie length is shown

#### Scenario: The same cut in the read view and in Edit mode
- **WHEN** a clip lists a cut from 2.0 to 4.0 s, and the operator opens the Timeline in the read view and then in Edit mode
- **THEN** the read view draws the hatched span from 2.0 to 4.0 s with no handle, and Edit mode draws the same span with a start and an end handle

## ADDED Requirements

### Requirement: The read view and Edit mode each offer a Timeline that loads nothing until it is opened

The event page SHALL show, in its read view and in Edit mode, a section headed "Timeline" (a level-two heading). In the read view it comes after the Movie section (when the page shows one) and before the event's chapters; in Edit mode it comes after the metadata form and before the chapters' lists, and it is the Timeline on which the operator trims cuts ("Edit mode's cuts are trim handles"). The section SHALL have a button, "Open timeline", that opens it; once open, the same button SHALL read "Close timeline". The button SHALL state whether the section is open (`aria-expanded`) and SHALL name the content it controls.

The section SHALL be closed when the page opens, after a Refresh, on entering Edit mode and after leaving it; a Timeline open in the read view is closed by pressing Edit, and Edit mode's starts closed. While it is closed the page SHALL create no `<video>` for it and SHALL make no request for a proxy, a filmstrip or a proxy job, whatever the number of clips. While the event page is loading, or shows a failure, it SHALL show no Timeline section.

Opening the Timeline SHALL change no state the service holds: it only reads. Starting a proxy job is a separate, explicit control (see "The Timeline asks for the clips' proxies when they are missing").

In Edit mode the Timeline SHALL draw its clips, chapters and proxies as the event was last read (a proxy job that ends while Edit mode is open reads the event again, quietly, and the Timeline follows it; the editor's draft is not touched by that read), and its cuts as the draft lists them. It SHALL NOT draw the draft's unsaved order or chapters: when the draft has moved a clip, reordered or renamed a chapter, or added or deleted one, the Timeline SHALL say in a note that it shows the order last saved, and the cuts of every clip stay editable. Play on the Timeline SHALL skip the draft's cuts as they are now, so that a trim is heard and seen before it is saved. In Edit mode the cuts are never "being read" and never "unreadable": the draft holds them.

#### Scenario: A closed timeline costs nothing
- **WHEN** the operator opens the page of an event of 400 clips and does not press "Open timeline"
- **THEN** the page holds no `<video>` for the Timeline and has made no request to a proxy or filmstrip address, and the Timeline section shows its heading and the "Open timeline" button, not expanded

#### Scenario: Edit mode has its own, closed timeline
- **WHEN** the operator opens the Timeline of `2024-06-27 - Grillning med grannar` and then presses Edit
- **THEN** the page shows Edit mode with a Timeline section after the metadata form, closed, holding no `<video>` and having made no proxy or filmstrip request for it; and leaving Edit mode shows the read view's Timeline section closed

#### Scenario: Opening is a read
- **WHEN** the operator opens the Timeline of an event whose proxies are all ready
- **THEN** every request the client made for it was a read, no file under the library changed, and the jobs the service lists are the same as before

#### Scenario: The movie and the timeline do not play together
- **WHEN** the event's movie is playing and the operator presses Play on the Timeline
- **THEN** the movie pauses and the Timeline plays; pressing the movie's Play while the Timeline plays pauses the Timeline

#### Scenario: A reorder is not drawn
- **WHEN** in Edit mode the operator moves `s1710002.mp4` above `s1710001.mp4` in its chapter's list and opens the Timeline
- **THEN** the Timeline draws `s1710001.mp4` first, as last saved, and a note says that it shows the order last saved; after Save the Timeline draws the new order

#### Scenario: Play skips a trim that is not saved
- **WHEN** in Edit mode the operator trims the cut of `s1710001.mp4` to 1.0 to 3.5 s and plays the Timeline from 0.5 s
- **THEN** no frame between 1.0 and 3.5 s is shown, and nothing has been written

#### Scenario: Proxies prepared while editing
- **WHEN** in Edit mode the Timeline shows its Prepare state, the operator presses "Prepare proxies", and the job ends
- **THEN** the page reads the event again, the Timeline shows the track with the draft's cuts, and the draft, the save bar and the Cuts panels are as they were

### Requirement: Edit mode's cuts are trim handles

In Edit mode, each cut the Timeline draws on a clip that offers a Cuts panel (an included or new clip on disk whose proxy is ready) SHALL have two **trim handles**, one on its start and one on its end. The handles belong to the cut as the clip's Cuts panel lists it: the cut keeps its place in the list, its number, its reason and its identity while a handle moves, and a cut marked removed has no handle. A handle SHALL be a slider (`role="slider"`, horizontal), reachable by Tab, in the order of time: the clips in play order, and in each clip the cuts by start, a cut's start handle before its end handle, after the playhead. It SHALL be named "Cut <n> start of <name>" or "Cut <n> end of <name>", where <name> is the clip as its row names it and <n> the cut's number in that clip's Cuts panel (the panel's own numbering, removed cuts counted), so no two handles of a clip share a name. It SHALL expose `aria-valuenow` as its time in the clip in seconds, and `aria-valuemin` and `aria-valuemax` as the least and greatest time it can take now, and a value text that gives its time in the Cuts panel's time format followed by the cut's span in words ("0:01.5, the cut runs 0:01.5 to 0:03"). A visible description, referenced by `aria-describedby`, SHALL list the keys of "A trim handle is moved by keyboard".

A handle SHALL take only places the cut can legally take, and its range SHALL always hold the value it has:

- the **start** can go no earlier than the clip's start or the end of the nearest cut before it that it does not overlap, and no later than three frames of the clip before its own end
- the **end** can go no later than the clip's length (the proxy's duration) or the start of the nearest cut after it that it does not overlap, and no earlier than three frames of the clip after its own start
- a cut already shorter than three frames, a cut that runs past the clip's end, and cuts that overlap each other in `reel.yaml` SHALL keep a range that holds their current times; looking at a cut SHALL NOT change it
- the limits are frame times of the clip's own frame rate (taken from the proxy's facts), so that Home and End reach a time the clip can show
- a cut touching another, one's end at the other's start, is a legal place

A cut that runs past the clip's end SHALL have its end handle drawn at the clip's end, while the handle's value stays the cut's own end.

Cuts the render joins into one span SHALL still have a handle each at their own edges.

Handles SHALL exist exactly where the track draws the clip's cut spans: a clip drawn too narrow to show its cuts (the track draws it as a block) has no handle until the operator zooms in, and a clip outside the window the track draws has none either ("The track zooms, and draws only what is in view"). Moving the playhead scrolls the view to it, which brings the clips around it, and so their handles, into the window; this is how keyboard focus reaches a cut that is far from the view.

#### Scenario: Handles are named and carry their limits
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, whose `s1710001.mp4` (6.02 s, a 25 fps proxy) has a cut from 1.0 to 2.5 s and one from 4.0 to 5.0 s, the operator opens the Timeline and tabs to its first handle
- **THEN** the handle is named "Cut 1 start of s1710001.mp4", has `aria-valuenow` 1, `aria-valuemin` 0 and `aria-valuemax` 2.38, and says "0:01, the cut runs 0:01 to 0:02.5"; the next Tab stops at "Cut 1 end of s1710001.mp4" with `aria-valuemin` 1.12 and `aria-valuemax` 4

#### Scenario: A removed cut has no handle
- **WHEN** the operator removes cut 1 of `s1710001.mp4` in its Cuts panel
- **THEN** the Timeline draws no handle for it and the handles of the other cut keep the names "Cut 2 start of s1710001.mp4" and "Cut 2 end of s1710001.mp4"; pressing Undo brings cut 1's handles back

#### Scenario: A cut shorter than three frames is not widened
- **WHEN** a cut of 5.000 to 5.050 s was read from `reel.yaml`, and the operator focuses its end handle and then its start handle
- **THEN** the end handle's range begins at 5.05 and the start handle's ends at 5.0, so each can only widen the cut; the cut is unchanged by focusing, and Left on the end handle (which would shorten it further) changes nothing

#### Scenario: A cut past the clip's end
- **WHEN** `s1710001.mp4` (6.02 s) lists a cut from 5.0 to 7.0 s
- **THEN** the cut's end handle is drawn at the clip's end, reads 7 with a range that holds 7, and its value text says "0:07" and that the cut runs past the clip's end
- **WHEN** the operator presses Left on it
- **THEN** the end is one frame earlier, at 6.96 s

#### Scenario: A clip too narrow to show its cuts
- **WHEN** at the lowest zoom of a 400-clip event a clip is drawn as a block with no cut spans
- **THEN** it has no handle, its cuts are still listed and editable in its Cuts panel, and zooming in until its cuts are drawn gives it its handles

#### Scenario: Overlapping cuts from disk
- **WHEN** a clip lists cuts 2.0 to 4.0 s and 3.5 to 5.0 s
- **THEN** the track draws one joined span with four handles, each with a range that holds its current time, and no range is inverted

### Requirement: A handle is dragged to a place within its limits and snaps to nearby edges

Pressing a trim handle with a mouse, a pen or a finger, and moving, SHALL move the edge by the distance the pointer moves, from where the edge was, so the edge does not jump to the pointer when it is grabbed off its centre. The edge SHALL stay within the handle's limits and SHALL take the clip's frames: a place without a snap SHALL be the frame time nearest the pointer. It SHALL **snap** when a snapping place lies within 8 px (screen pixels, at the current zoom) of where the pointer puts the edge. The snapping places are: the clip's start and end, the start and end of every other cut of the clip, and the playhead when it is inside the clip. Of two places equally near, the earlier SHALL be taken. A snap that the limits would move the edge off SHALL NOT be shown as a snap. While the edge is snapped the Timeline SHALL show a line at the snapping place and SHALL say, in words beside the dragged edge, what it snapped to ("Snapped to the playhead", "Snapped to cut 2 start", "Snapped to the clip's end"); the line and the words are the state, not a color alone.

While dragging, the edge, the cut's span and the time beside the handle SHALL follow the pointer on every frame, and the rest of the editor SHALL NOT change: the Cuts panel, the save bar and the draft SHALL show nothing new until the pointer is released. Releasing SHALL make one edit of the draft: the cut's new time. Pressing Escape, or the browser cancelling the pointer, SHALL end the drag with the edge back where it was and no edit. A drag that ends where it started SHALL make no edit. Releasing SHALL announce the result once, politely, through Edit mode's one live region ("Cut 1 of s1710001.mp4 now 0:01 to 0:03.5, snapped to the playhead. 2 cuts, 2.5 seconds cut out."), and SHALL NOT announce every move.

The drag SHALL stay smooth: at 80 clips under a 4x CPU throttle in Chrome, at most 2 % of the frames of a scripted drag take longer than 25 ms. Pointer drag has a keyboard and typed alternative ("A trim handle is moved by keyboard", "The selected cut's times can be typed").

#### Scenario: A drag moves the edge by the distance moved
- **WHEN** at 40 px per second the operator presses the end handle of cut 1 (ending at 2.5 s) of `s1710001.mp4` 5 px off its centre and moves the pointer 40 px right
- **THEN** the edge is at 3.5 s, the end handle reads 3.5, and the Cuts panel still lists the cut as ending at 0:02.5 until the pointer is released

#### Scenario: Releasing makes one edit
- **WHEN** the operator releases the pointer there
- **THEN** the Cuts panel lists cut 1 as 0:01 to 0:03.5 with its reason unchanged, the save bar says that 1 cut was trimmed, and the draft changed once

#### Scenario: A snap to a neighbour's edge
- **WHEN** at 40 px per second the operator drags the end of cut 1 to 6 px before the start of cut 2 (4.0 s)
- **THEN** the edge is exactly 4.0 s, a line shows at cut 2's start, and the words say that it snapped to cut 2 start
- **WHEN** the operator drags it 12 px before cut 2's start
- **THEN** it does not snap and takes the frame nearest the pointer

#### Scenario: Snapping to the playhead
- **WHEN** the playhead is at 1.6 s of `s1710001.mp4` and the operator drags the start of cut 1 to within 8 px of it
- **THEN** the edge is exactly 1.6 s and the words say that it snapped to the playhead

#### Scenario: A drag stops at the neighbour
- **WHEN** the operator drags the end of cut 1 past the start of cut 2
- **THEN** the edge stops at 4.0 s, and the two cuts touch without overlapping

#### Scenario: Escape cancels a drag
- **WHEN** the operator drags an edge and presses Escape before releasing
- **THEN** the edge is back at its start place and the draft is unchanged, with no save bar if nothing else was edited

#### Scenario: A drag ending where it began
- **WHEN** the operator presses a handle and releases it without moving
- **THEN** nothing is edited and no save bar appears

### Requirement: A trim handle is moved by keyboard

A trim handle that has keyboard focus SHALL answer these keys, each making one edit of the draft and each reaching only places within the handle's limits:

- Left and Right: one frame earlier or later, of the clip's own frame rate; an edge not on a frame (a typed time) moves to the nearest frame in that direction
- Shift with Left or Right: one second; Page Down and Page Up: five seconds; the result takes the nearest frame
- Home and End: the lowest and the highest time the handle can take
- Enter: sets the edge at the playhead, as Set From and Set To do in the clip's preview, when the playhead is inside the clip (its end included); otherwise it SHALL change nothing and say, politely, that the playhead is not in that clip
- Escape: no effect on the handle, and it SHALL NOT leave Edit mode

A key that would pass a limit SHALL stop at the limit, and a key at the limit SHALL change nothing. A key SHALL be handled only when the handle has focus, so typing in a field is never intercepted. Keys SHALL NOT scroll the page. Each key's result SHALL be given by the handle's value (`aria-valuenow`, value text), and SHALL NOT also be announced through the live region, which would say it twice; an Enter refused or stopped by a limit SHALL be announced. While the handle has focus it SHALL be scrolled into view if its edge is outside the track's view.

#### Scenario: Frame steps
- **WHEN** focus is on "Cut 1 start of s1710001.mp4" (1.0 s, 25 fps) and the operator presses Right three times
- **THEN** the start is at 1.12 s, the handle reads 1.12, and the Cuts panel lists 0:01.12 to 0:02.5

#### Scenario: One and five seconds
- **WHEN** the operator presses Shift+Right on the end handle of cut 1 (2.5 s)
- **THEN** the end is at 3.5 s
- **WHEN** the operator presses Page Up
- **THEN** the end stops at 4.0 s, the start of cut 2

#### Scenario: Home and End reach the limits
- **WHEN** the operator presses Home on the start handle of cut 1, then End
- **THEN** the start goes to 0, then to 2.38 s (three frames before the end), and the Cuts panel lists those times

#### Scenario: Enter sets the edge at the playhead
- **WHEN** the playhead is at 1.6 s of `s1710001.mp4` and the operator presses Enter on the end handle of cut 1
- **THEN** the end is at 1.6 s

#### Scenario: Enter with the playhead elsewhere
- **WHEN** the playhead is in `s1710002.mp4` and the operator presses Enter on a handle of `s1710001.mp4`
- **THEN** nothing changes and the live region says that the playhead is not in `s1710001.mp4`

#### Scenario: A key at a limit
- **WHEN** the operator presses Home twice on the start handle of cut 1
- **THEN** the second press changes nothing and the draft holds one edit

#### Scenario: Keys inside a field are left alone
- **WHEN** keyboard focus is in the selected cut's start field and the operator presses Left
- **THEN** the field's caret moves and no edge moves

### Requirement: The selected cut's times can be typed, and stay in step with the handles

Under the track the Timeline SHALL show the **selected cut** in a group named "Cut <n> of <name>" with two text fields, "Start of cut <n> of <name>" and "End of cut <n> of <name>", showing the cut's times in the Cuts panel's time format. A cut SHALL be selected when one of its handles gets keyboard focus or is pressed, or its span is pressed; the selection SHALL stay until another cut is selected or the cut is removed. With no selected cut the group SHALL say so and hold no field.

A time typed in a field SHALL be taken on Enter or when the field loses focus, in the forms the Cuts panel accepts (seconds, `m:ss`, `h:mm:ss`, up to three decimals), and SHALL make one edit of the draft. It SHALL be refused, and nothing changed, for the reasons the Cuts panel refuses a typed cut and in its words: unreadable, too precise, an end not after the start, an overlap with another cut of the clip that is not removed (the cut itself excepted), an end after the clip's length (the proxy's duration). A refusal SHALL be shown at the field the Cuts panel's rule names for it, which receives keyboard focus, and announced. Escape in a field SHALL put the cut's current time back. A typed time need not be a frame time: it is taken to the millisecond, as a typed cut is.

The fields, the handles, the span drawn and the Cuts panel's list SHALL show the same times at all times: a drag or a key updates the fields on every change, and a typed time moves the handle. A field being typed in (it has focus and its text differs from the cut's time) SHALL NOT be overwritten by a handle moving, but SHALL NOT be taken either until Enter or blur.

#### Scenario: A drag updates the fields
- **WHEN** cut 1 is selected and the operator drags its end from 2.5 s to 3.5 s
- **THEN** the "End of cut 1" field reads 0:03.5 while the pointer is still down and when it is released, and the Cuts panel lists 0:01 to 0:03.5

#### Scenario: A typed time moves the handle
- **WHEN** the operator types `0:00.5` in the "Start of cut 1" field and presses Enter
- **THEN** the start handle reads 0.5, the span is drawn from 0:00.5, the Cuts panel lists 0:00.5 to 0:02.5, and the save bar says that 1 cut was trimmed

#### Scenario: A refused typed time
- **WHEN** the operator types `3` in the "Start of cut 1" field and presses Enter
- **THEN** it is refused at the End field, which receives keyboard focus, saying that a cut must end after it starts (0:02.5 is not after 0:03), announced, and the cut is unchanged
- **WHEN** the operator types `4.5` in the "End of cut 1" field
- **THEN** it is refused, saying that it overlaps cut 2 (0:04 to 0:05)

#### Scenario: A time past the clip's end
- **WHEN** the operator types `7` in the "End of cut 2" field of `s1710001.mp4` (6.02 s)
- **THEN** it is refused, saying that 0:07 is after the clip's end at 0:06.02

#### Scenario: A field being typed in is left alone
- **WHEN** the operator has typed `0:0` in the start field without pressing Enter and presses Shift+Right on the cut's end handle, then returns to the field
- **THEN** the field still reads `0:0`, and Enter takes what is in it

### Requirement: Trim handles are large enough for a finger, and a swipe still scrolls

When the primary pointer is coarse, each trim handle SHALL take a press anywhere in an area at least 44 px wide and 44 px high around its edge, reaching no other control; the area SHALL extend outward from the cut (a start handle's to the left of its edge, an end handle's to the right) so that the two handles of a short cut do not overlap. Where the areas of two handles still overlap (the end of one cut near the start of the next), a press SHALL go to the handle whose edge is nearer to it, and to the earlier of two equally near. With a fine pointer the area SHALL be at least 24 px wide and the track's height. Pressing a handle with a finger and moving SHALL drag the edge and SHALL NOT scroll the track; a horizontal swipe elsewhere on the track SHALL scroll it, as in the read view, and SHALL NOT move an edge or the playhead. The selected cut's fields and every button of the Timeline SHALL be 44 px high under a coarse pointer.

#### Scenario: A short cut on a phone
- **WHEN** in a 390 px wide window with a coarse pointer a cut is 20 px wide on the track
- **THEN** its start handle's area lies left of the cut's start and its end handle's right of the cut's end, each 44 px wide and tall, and neither covers the other

#### Scenario: Two neighbours' edges
- **WHEN** cut 1 ends at 2.5 s and cut 2 starts at 2.6 s at 40 px per second (4 px apart), and a finger presses 3 px right of cut 1's end
- **THEN** cut 1's end handle takes the press

#### Scenario: A swipe scrolls
- **WHEN** a finger swipes sideways over a clip's filmstrip, away from any handle
- **THEN** the track scrolls and no cut changes

### Requirement: Trimming is unavailable while a save or a move is pending, and where there is nothing to trim

While a save is in flight or a Move clips is pending, the trim handles and the selected cut's fields SHALL say that they are unavailable (`aria-disabled`, in words in the group) and SHALL change nothing when used, as the Cuts panel's controls do; the playhead and playing SHALL stay usable. A clip with no ready proxy SHALL have no timeline presence ("The Timeline asks for the clips' proxies when they are missing"), so it has no handle; its cuts stay editable in its Cuts panel by typed times. A drag in progress when a save starts SHALL end as if Escape were pressed.

#### Scenario: A pending save leaves handles inert
- **WHEN** a cut was trimmed, the operator presses Save, and the service has not answered
- **THEN** the handles and fields say that they are unavailable and a press on a handle moves nothing, while Play and the playhead work and keyboard focus stays on Save

#### Scenario: Proxies missing for some clips
- **WHEN** the operator opens the Timeline in Edit mode on an event with a clip whose proxy is absent
- **THEN** the Timeline shows the Prepare state and no handle, and every clip's Cuts panel still adds and removes cuts by typed times

### Requirement: Edit mode holds one video at a time

Edit mode SHALL never hold more than one `<video>`: the Timeline's, which exists while its track is open ("The playhead scrubs one video"), or one clip preview's. Opening a clip's preview ("Edit mode previews a clip on request") SHALL release the Timeline's video, stopping its playback and its loading, and keep the Timeline open with the playhead where it stood and every handle usable. Moving the playhead, or pressing Play, on the Timeline SHALL close any open clip preview and create the Timeline's video again at the playhead (it loads the proxy of the clip the playhead is in, as when the track opens). Releasing and creating the video SHALL NOT be an edit, SHALL NOT disturb a drag or a typed time, and SHALL NOT move keyboard focus off the control that had it.

#### Scenario: A preview releases the timeline's video
- **WHEN** in Edit mode the Timeline's video has been scrubbed to 1.6 s of `s1710001.mp4` and the operator presses Watch in that clip's Cuts panel
- **THEN** the page holds one video, the clip's preview; the Timeline is still open with its playhead at 1.6 s and its handles working

#### Scenario: Scrubbing closes the preview
- **WHEN** a clip's preview is open and the operator moves the Timeline's playhead
- **THEN** the preview closes, the Timeline's video shows the playhead's frame, and the page holds one video

### Requirement: The timeline's gates and layout hold with handles

With trim handles on the track in Edit mode, the Timeline SHALL keep its gates and its layout: at 400 clips the number of elements it creates SHALL stay bounded by the view (windowing counts handles); the scripted scrub SHALL still present at least 30 distinct frames per second at the median, and the single-frame step SHALL still be presented within 60 ms at the 90th percentile, in Chrome 154 and in Firefox 155 or newer; every width from 320 to 1280 px SHALL fit without a horizontal scroll bar on the page; with `prefers-reduced-motion: reduce` handles, snap lines and the selected cut's fields SHALL not animate; the handles, the snap line, the words and the fields SHALL follow the page's scheme in light and dark with the contrast the page meets; and the state of a handle (focused, dragged, snapped, unavailable) SHALL never be shown by color alone.

#### Scenario: A long event stays windowed
- **WHEN** the Timeline of an event of 400 clips, each with one cut, is open in Edit mode and scrolled to the middle
- **THEN** only the handles of the clips in or near the view exist in the page

#### Scenario: Layouts and schemes
- **WHEN** Edit mode's Timeline is looked at in Chrome and Firefox at 1280 and 390 px, light and dark, with a cut selected and an edge snapped
- **THEN** the page does not scroll horizontally, the handles, line, words and fields are legible, and the same holds with reduced motion
