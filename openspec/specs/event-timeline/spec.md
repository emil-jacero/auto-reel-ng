# event-timeline Specification

## Purpose
The event page's Timeline: one track for the whole event, laid out from the facts of each clip's proxy, that the
operator scrubs and plays, with the analysis suggestions as a lane under the clips. It exists so a cut can be judged
against the footage around it, which the one-clip preview of Edit mode cannot show. It is read-only in the read view;
in Edit mode each cut has trim handles that edit the draft, which the editor's Save writes.

## Requirements

### Requirement: The Timeline shows the clips a render plays, in play order

The Timeline SHALL lay out the clips the event page lists in its chapters, in the page's play order (chapter by chapter, clip by clip), leaving out a clip that is missing from disk and a clip that `reel.yaml` excludes. When it leaves clips out it SHALL say how many, in words, in a note on the Timeline ("2 clips are missing from disk and are not shown", "1 clip is excluded and is not shown"), counting each kind apart. An event with no clip to show SHALL show a note saying so and no track.

#### Scenario: Missing and excluded clips are named, not drawn
- **WHEN** an event lists five clips in two chapters, one of them missing from disk and one excluded in `reel.yaml`
- **THEN** the Timeline lays out three clips in play order and its note says that one clip is missing from disk and one is excluded

#### Scenario: An event with nothing to show
- **WHEN** every clip an event lists is missing from disk
- **THEN** the Timeline shows a note that it has no clip to show, and no track and no Prepare button

### Requirement: The Timeline asks for the clips' proxies when they are missing

The track SHALL open only when every clip it shows has a ready proxy, because the clips' lengths, frame rates and filmstrips come from the proxies' facts (the event read carries no duration or frame rate of its own). Otherwise the section SHALL show a Prepare state instead of the track, in place of it:

- the number of clips that are ready, out of the number the Timeline shows, and the clips that are not, counted by state in words: not prepared (never prepared, or the clip changed on disk since: a proxy belongs to one version of the file), damaged (its proxy entry exists but cannot be used), or failed
- a button, "Prepare proxies", that asks the service to prepare the event's proxies (`POST /api/v1/events/{event_id}/proxies`). It SHALL be the only way the page starts that job. A clip whose proxy is damaged or failed SHALL be prepared again by the same button.

The button SHALL behave as the page's Render button does: one request per press, keyboard focus kept, marked busy until the answer arrives. The answers SHALL be handled as follows:

- **created (201):** the Prepare state shows the new job as below
- **all proxies already ready (200):** the page says the proxies are ready and reads the event again, so its states are current; it starts no job
- **a proxy job already queued or running (409):** the Prepare state shows that job; it does not say that anything failed
- **404, 502, or 503 naming the database:** the state says why in words, from the answer, and the button stays; **no answer**, or an answer the service does not publish, is said as such
- the page SHALL NOT start the job a second time because the page was read again, and SHALL NOT start it by opening the Timeline

The job SHALL be shown from the jobs connection the page already holds (no polling): the words "Waiting for a worker" while queued, a determinate progress bar and whole percent while running (stopping at 99% until the service reports the job done), and "Preparing proxies" rather than "Rendering". A shown proxy job SHALL carry its own accessible names ("Proxy progress", not "Render progress"). When the job reaches a finished state the page SHALL read the event again, quietly, and the track SHALL open if every shown clip is now ready. A job that failed or was canceled SHALL be said in words, with the error text the service recorded when the job carries one; the clips it did not prepare stay counted by their state, and the button stays. A job's state changes SHALL be announced once each to assistive technology through a polite status region; progress SHALL NOT be announced on every update. A finished proxy job SHALL raise no notification, and a job started by another tab SHALL be shown as the connection reports it.

If a clip's state is `ready` but the service reports no facts for it, the Timeline SHALL treat the clip as not ready and say so; it SHALL NOT guess a length, a frame rate or a size.

#### Scenario: An unprepared event opens on Prepare
- **WHEN** the operator opens the Timeline of an event of 25 clips of which 25 have no proxy
- **THEN** the section shows "0 of 25 clips are ready", "25 not prepared", and a "Prepare proxies" button, and shows no track and no `<video>`

#### Scenario: Preparing shows live progress
- **WHEN** the operator presses "Prepare proxies" and a worker runs the `proxy` job
- **THEN** the section shows the job waiting, then a determinate bar with a percentage that rises with each update and never shows 100% while the job runs, with no reload, and the render region of the page shows no change

#### Scenario: The track opens when the job ends
- **WHEN** the proxy job for the event finishes while its Timeline is open
- **THEN** the page reads the event again without replacing its content, and the Prepare state is replaced by the track with the playhead at the start, with no reload

#### Scenario: One clip failed
- **WHEN** 24 of an event's 25 clips have a ready proxy and the 25th's state is failed
- **THEN** the Timeline shows "24 of 25 clips are ready" and "1 failed", the Prepare button, and no track

#### Scenario: A press while a job runs
- **WHEN** the operator presses "Prepare proxies" while a proxy job for the event is already queued
- **THEN** the service answers 409, and the section shows that queued job, without an error

#### Scenario: Everything was already ready
- **WHEN** the page was read before another tab prepared the last proxy, and the operator presses "Prepare proxies"
- **THEN** the service answers 200, the page reads the event again, and the track opens

#### Scenario: A source that changed after its proxy
- **WHEN** a clip's file was replaced after its proxy was made and the page is read
- **THEN** that clip is counted as not prepared (the service keys a proxy to one version of the file), the track does not open, and "Prepare proxies" prepares it

#### Scenario: A damaged proxy
- **WHEN** the service reports a clip's proxy as damaged (its entry exists but cannot be used)
- **THEN** that clip is counted as damaged, the track does not open, and "Prepare proxies" prepares it again

### Requirement: The track lays the clips out by their proxies' lengths, with the chapters and the cuts

With every shown clip ready, the Timeline SHALL show, in one horizontally scrolling track:

- a **ruler** with time labels in the page's time format (`m:ss`, with fractions only when zoomed in far enough that labels would repeat)
- the **clips end to end** in play order (a black title card's span, when the event draws one before a chapter, is between them, see "Each chapter's title card is a block on the Timeline"), each as wide as its proxy's duration at the current zoom, labelled with its name as the page names it. A proxy has the source's timestamps, so a time in a proxy is the same time in the source clip. A clip's length SHALL come from its proxy's facts, never from the browser's reading of a file and never defaulted; a clip shorter than a pixel at the current zoom SHALL still be drawn, one pixel wide at least, and the playhead SHALL be able to be put in it by keyboard.
- a **chapter band** above the clips: one segment per chapter spanning its shown clips, labelled with the chapter's name, or as the page headings an unnamed chapter ("Main" beside named chapters, "Clips" when none is named). The band's labels stay in view while their chapter scrolls past.
- each clip's **cuts**, as the event page lists them from `reel.yaml` (in Edit mode: as the Cuts panels list them now, the draft's, with the ones marked removed left out), drawn over the clip as spans with a hatch pattern and named by their reason in words ("manual", "black", "white", "freeze") in the span's text alternative; overlapping or touching cuts SHALL be drawn as the render joins them, one span; a cut that runs past the proxy's duration SHALL be drawn to the end of the clip only. In the read view the spans SHALL be read-only: no handle, no drag, no edit. In Edit mode each cut SHALL have the two trim handles of "Edit mode's cuts are trim handles", drawn over the joined span.
- the **movie's length**: the sum of the shown clips' lengths minus the time the cuts remove, plus the lengths of the black title cards the track draws, beside the source length, in words ("Movie 3:12 of 3:45 of footage"; with black cards, "Movie 3:20 of 3:45 of footage, with 8 s of title cards")

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

#### Scenario: Black cards count in the movie's length
- **WHEN** an event of 3:45 of footage with 33 s of cuts draws two black cards of 4.0 s each
- **THEN** the readout says "Movie 3:20 of 3:45 of footage, with 8 s of title cards", and a video card adds nothing to it

### Requirement: Each clip shows a filmstrip from its proxy's sprite

Each clip on the track SHALL show a filmstrip, drawn from the clip's filmstrip sprite (`GET /api/v1/events/{event_id}/filmstrip?clip=&v=`), which holds one tile per second of the clip in a grid whose geometry the proxy's facts give. The tile shown at each place SHALL be the one for that moment of the clip; at a zoom where tiles would overlap, tiles are left out, not squeezed. The filmstrip SHALL be a picture only (hidden from assistive technology), and SHALL be requested only for clips that are in view (see "The track draws only what is in view"). The address of the sprite, and of the proxy, SHALL carry the proxy file's entity-tag, without its quotes, as the `v` query parameter, so a proxy made again is a new address (Chrome fails to play a replaced file at an address that served the old one, D-15). The event id SHALL be encoded segment by segment, as on every events route.

A sprite that cannot be read SHALL leave that clip without a picture and SHALL NOT break the track or the clip's name, cuts or position; it SHALL be said once, as a note on the Timeline ("A filmstrip could not be loaded"), not once per clip.

A clip shorter than one second has one tile.

#### Scenario: Tiles follow time
- **WHEN** a 25 s clip is drawn at 40 px per second with 96 px tiles
- **THEN** the filmstrip shows tiles for roughly every 2.4 s of the clip, from the first second to the last, each from the sprite position of the second it shows

#### Scenario: A replaced proxy has a new address
- **WHEN** a clip's proxy is made again and the event is read again
- **THEN** the sprite and the proxy are requested at addresses with the new entity-tag as `v`, and the old address is not used for the new file

#### Scenario: One filmstrip fails
- **WHEN** the service answers 404 for one clip's sprite while the others load
- **THEN** that clip shows its name, cuts and position without a picture, the other clips show theirs, and one note on the Timeline says that a filmstrip could not be loaded

#### Scenario: A sub-second clip
- **WHEN** a clip's proxy reports a duration of 0.48 s
- **THEN** its filmstrip is its one tile

### Requirement: The track zooms, and draws only what is in view

The Timeline SHALL offer **Zoom in**, **Zoom out** and **Fit** as buttons, and `+`, `-` and `0` as keys while the track has keyboard focus. **Fit** SHALL show the whole timeline in the track's width; zooming out SHALL stop at Fit, or at 4 px per second when the whole event is longer than the track is wide at that scale. Zooming in SHALL stop at 240 px per second. A zoom SHALL keep the playhead where it was in the track's view. The track SHALL scroll horizontally inside its own box; the page SHALL NOT scroll horizontally at any width from 320 to 1280 px.

The track SHALL draw only the clips, filmstrip tiles and ruler labels that intersect the visible range, plus a margin of one view width on each side. For an event of 400 clips, at the most zoomed-out level, the track SHALL hold fewer than 100 clip elements. Scrolling and zooming SHALL NOT change which clip a playhead time belongs to.

#### Scenario: Fit shows the whole event
- **WHEN** the operator presses Fit on an event of 10 minutes in a 1280 px window
- **THEN** the whole event is inside the track's width, with no horizontal scroll bar on the page

#### Scenario: Zooming keeps the playhead in view
- **WHEN** the playhead is at 0:42 and the operator presses Zoom in three times
- **THEN** the playhead is still inside the track's view, at the same horizontal place it had

#### Scenario: A long event is windowed
- **WHEN** an event of 400 clips is shown at its most zoomed-out level
- **THEN** the track holds fewer than 100 clip elements and scrolling to the end shows the last clip

#### Scenario: A phone-width window
- **WHEN** the Timeline is shown 320 px wide
- **THEN** the page has no horizontal scroll bar, the track scrolls inside its box, and its toolbar wraps without cutting off a control

### Requirement: The playhead scrubs one video

The Timeline SHALL hold exactly one `<video>`, created when the track opens, showing the proxy of the clip the playhead is in, at the playhead's time in that clip. The playhead SHALL be a slider over the whole timeline: it SHALL have the role `slider`, a name ("Playhead"), `aria-valuemin`, `aria-valuemax` and `aria-valuenow` in the timeline's seconds, and a value text that names the clip, the time in it and the time in the whole timeline, each said by its noun ("Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12", the times in the Cuts panel's time format, not padded). Dragging on the ruler SHALL move the playhead; so SHALL dragging on the track body with a mouse or a pen, and so SHALL dragging the playhead's own grip. With touch, the ruler SHALL scrub and a swipe on the track body SHALL scroll it. A press on the ruler or the track SHALL move the playhead there.

Moving the playhead into another clip SHALL load that clip's proxy into the same `<video>` and seek it, so the picture is the clip's frame at that time; a short flash between two clips is accepted. While the pointer is moving, the Timeline SHALL keep at most one seek in flight and SHALL seek to the latest pointer position when it completes, so that a scrub across many clips never queues a seek per pointer move. The video SHALL be paused while scrubbing. The picture and the playhead SHALL end where the pointer ended.

Below the video the Timeline SHALL show the clip's name, the playhead's time in the clip and in the whole timeline, each pair labelled in words ("Clip 0:00.96 of 0:39.84 · Event 1:02.40 of 2:29.76"), in words readable by assistive technology. The readout SHALL be written, kept to a constant width, with the clip's name cut by an ellipsis, as "Running times are written to a fixed width and say what they are" requires, so that it does not change width as the clip plays or as the playhead passes from one clip into another. The end of a scrub, a key step and a click SHALL be announced once through a polite status region ("Playhead at Harbour, 0:12.40"); the movement of a drag SHALL NOT be announced per update.

A proxy whose playing fails SHALL be said by cause, as the clip preview says it: asking once for the file's first byte tells a proxy that is gone (404, "prepare proxies again") from one the service cannot read, from a file the browser cannot decode, from no answer at all. The Timeline SHALL keep the track and the playhead and offer the Prepare state's button for a gone proxy.

#### Scenario: A scrub shows the right frame
- **WHEN** the operator drags the playhead on the ruler to 16.00 s of the second clip's span
- **THEN** the single video shows that clip's proxy, `currentTime` is that time within the clip, and the slider's value text names the clip and the time

#### Scenario: The grip is dragged
- **WHEN** the operator presses on the playhead's grip and drags it along the ruler
- **THEN** the playhead follows the pointer exactly as when the drag starts on the ruler

#### Scenario: A scrub across a boundary
- **WHEN** the operator drags the playhead from the first clip into the third clip within one second
- **THEN** the video ends on the third clip's proxy at the playhead's time, and the page never held more than one video for the Timeline nor more than one seek in flight

#### Scenario: The speed of a scrub
- **WHEN** a scripted drag sweeps the playhead across one clip of each of the event's proxies in Chrome 154 and in Firefox 155 or newer
- **THEN** the median number of distinct frames presented per second is at least 30 in each

#### Scenario: The clips shrink under the playhead
- **WHEN** the page reads the event again, quietly, and the clip the playhead is on is no longer shown (it is missing, excluded or ignored now)
- **THEN** the Timeline stays on the page with the clips that remain, the playhead goes to the start, and nothing is blank or thrown

#### Scenario: The proxy is gone
- **WHEN** a proxy file is removed from the cache after the page read the event, and the playhead moves into that clip
- **THEN** the Timeline says that this clip's proxy is no longer there and offers "Prepare proxies", while the track and the other clips keep working

#### Scenario: The readout says what each number is and holds still
- **WHEN** the Timeline of an event whose clips are 9.00 s, 40.00 s and 6.02 s is played from the start, in Chrome 154
  and in Firefox 155 or newer, light and dark, at 1280 and at 390 pixels wide
- **THEN** every sample of the readout, taken every 100 ms across the first clip's end, reads `Clip <time> of <length>
  · Event <time> of 55.02`, with the same width for each time and the same left edge for each pair, and the slider's
  value text says "clip" and "event" with the same numbers

### Requirement: The playhead is operable by keyboard, a frame at a time

The playhead, when it has keyboard focus, SHALL answer: Left and Right, one frame of the clip it is in (its frame rate comes from the proxy's facts; for a variable-frame-rate clip, the nominal frame interval, with no claim of frame accuracy); Shift with either, one second; Page Up and Page Down, five seconds; Home and End, the start and the end of the timeline; Space, Play or Pause. A step across a clip boundary SHALL land on the first frame of the next clip or the last frame of the previous one, and SHALL NOT skip a frame. A key SHALL be handled only when the playhead has focus, so typing in the page's fields is not intercepted. Every control of the Timeline (the toolbar buttons, the playhead, the track) SHALL be reachable by Tab in the order they appear, with a visible focus ring, and SHALL be at least 24 px high, and 44 px under a coarse pointer.

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

### Requirement: Play follows the playhead through the clips, skipping cuts

A **Play** button (**Pause** while playing) SHALL play from the playhead. It SHALL play as the movie will: no frame that lies wholly inside a cut is shown, cuts are joined as the render joins them, and a cut that runs to the end of a clip, or ends within 0.1 s of the clip's length, ends playing of that clip at that cut's start (the rules of the clip preview, D-16). At the end of a clip it SHALL go on into the next clip's proxy, or into the title card that comes before it ("The Timeline plays the title cards as the movie will"); at the end of the timeline it SHALL stop with the playhead at the end. The proxy's sound (AAC) SHALL play, in Firefox as in Chrome, including for a clip whose source has PCM audio. The playhead SHALL follow the video while it plays, and the button's state SHALL be in its words ("Play", "Pause"), not in its icon alone. Moving the playhead while playing SHALL continue playing from the new place: a touch tap, a click and a drag on the track or the ruler are such moves, and none of them SHALL leave the Timeline paused. Play SHALL wait until the page's read of the cuts has answered, so that no frame inside a cut is shown for want of them (the button SHALL say, in words, that the cuts are being read); where the cuts could not be read, Play SHALL be available and the note that the cuts could not be read SHALL say that Play does not skip cuts.

If the browser refuses to start playing without a gesture, or the proxy fails to play, the Timeline SHALL say so by cause in a note, as the clip preview does, and stay paused.

#### Scenario: Cuts are skipped
- **WHEN** a clip lists a cut from 2.0 to 4.0 s and the playhead plays from 1.0 s
- **THEN** no frame between 2.0 and 4.0 s is shown and the playhead goes from 2.0 s to 4.0 s of that clip

#### Scenario: Play goes on into the next clip
- **WHEN** the playhead plays to the end of the first of three clips
- **THEN** the video loads the second clip's proxy and plays on from its first frame, and the playhead keeps moving through the whole timeline

#### Scenario: A tap while playing goes on playing
- **WHEN** the Timeline is playing and the operator taps (touch) or clicks (mouse, with no delay between press and release) the track at another place
- **THEN** the playhead moves there, the button still says "Pause", and the video's time keeps advancing

#### Scenario: Play waits for the cuts
- **WHEN** the Timeline is open while the page's read of the cuts is still on its way and the operator presses Play or Space on the playhead
- **THEN** nothing plays, the Timeline says that the cuts are being read, and Play works as soon as they have been read

#### Scenario: The cuts could not be read
- **WHEN** the read of the cuts failed and the operator presses Play
- **THEN** it plays, and the note says that Play does not skip cuts

#### Scenario: A Sony PCM clip has sound in Firefox
- **WHEN** the Timeline plays a clip whose source is a Sony XAVC clip with PCM audio in Firefox 155 or newer
- **THEN** the clip's audio is heard (a decoded audio peak above zero), because it is the proxy's AAC track that plays

#### Scenario: Play does not start two videos
- **WHEN** the Timeline is playing and the operator presses Play on the event's movie
- **THEN** the Timeline pauses

### Requirement: The Timeline is accessible, fits every width and respects the color scheme

The Timeline SHALL expose its structure to assistive technology: the section is a region named "Timeline"; the chapter band is a list of chapters; the clips are groups named as the page names them, each with its length and the number of its cuts in its description; the playhead is a slider; each cut span has a text alternative ("Cut 2.0 to 4.0 s, black"). The state of a clip's proxy, of a cut's reason and of the Play button SHALL never be shown by color alone: it SHALL be words, a pattern or an icon with a name. Text and controls SHALL meet the contrast the rest of the page meets, in the light and in the dark scheme, which SHALL follow the page's scheme choice. Every width from 320 to 1280 px SHALL fit without a horizontal scroll bar on the page. With `prefers-reduced-motion: reduce` the Timeline SHALL not animate: no smooth scrolling, no transitions on the playhead or the zoom, and the progress of a job SHALL change without easing. Touch targets under a coarse pointer SHALL be 44 px.

#### Scenario: The structure reads in order
- **WHEN** a screen reader walks the open Timeline of an event with two chapters and three clips
- **THEN** it finds the region "Timeline", a list of two chapters, three named clips with their lengths, the slider "Playhead", and the Play button

#### Scenario: A cut is told in words
- **WHEN** a clip's cut with the reason black is hatched on the track
- **THEN** its text alternative says the cut's start, end and reason, and the span is also distinguished by its pattern, not by its color

#### Scenario: Dark scheme and reduced motion
- **WHEN** the operator's scheme is dark and the system asks for reduced motion
- **THEN** the Timeline is drawn with the dark tokens, the filmstrip and cuts stay legible, and zooming, scrolling and the playhead move without animation

#### Scenario: Touch
- **WHEN** the page is used on a phone-sized window with a coarse pointer
- **THEN** every Timeline button and the playhead's grip are at least 44 px high, and a swipe on the track scrolls it without moving the playhead

### Requirement: The timeline shows the event's analysis suggestions beside its clips

When the Timeline shows its track (the section open and every shown clip's proxy ready), it SHALL read the
event's cached analysis (`GET …/analysis`) and draw each suggestion (a black, white or frozen span that analysis
found) as a **mark** in an analysis lane, a row below the clips' row, under the clip it belongs to, placed by its
start and end in the clip, at the timeline's zoom. The read SHALL be made only then: a closed Timeline, and one
that is still preparing proxies, SHALL make no request for the analysis ("The event page offers a Timeline that
loads nothing until it is opened"). Closing and opening the Timeline, which a Refresh does, SHALL read it
again; a read that closing the Timeline or leaving the page has made pointless SHALL be abandoned. The page
SHALL NOT start an analysis, and the read SHALL NOT change anything.

A mark SHALL have, as text, its kind in words (Black frames, White frames, Frozen picture, or an unrecognised
kind as written), its start, its end and its length, written as times in a clip are everywhere ("Times are
written one way on every screen"), and, as a glyph and a word, its state. A mark SHALL be at least 44 CSS
pixels wide to press, whatever width its span has at the current zoom, and marks that would overlap SHALL stack
and never hide each other, including the last mark of one clip and the first of the next; the lane's height SHALL NOT change as the track scrolls. Only the marks of the clips in view SHALL be drawn, plus the one that has keyboard
focus.

A suggestion's state SHALL be derived from the clip's cuts, never remembered: **cut** when the cuts the clip
lists now (not removed ones) cover its whole span, counting spans to the millisecond and joining overlapping
or touching cuts as the render does; **partly cut** when they cover some of it; **dismissed** when the operator
dismissed it during this page visit and no cut covers any of it; otherwise **pending**. Removing or undoing the
cut that covered a suggestion SHALL return it to pending with no other action, and a cut saved in an earlier
session SHALL show its suggestion as cut on the first read.

The lane SHALL tell the three kinds of "no suggestions" apart: an event whose analysis was never run (no clip has a cached entry, whatever the service's `analyzed` flag says: a
rendered event has a cache directory) SHALL say "Not analyzed" and name the command that runs it; an analysed event with nothing found SHALL say nothing was
found; and in an analysed event a clip with no cached analysis (its file changed since) SHALL be marked "Not
analyzed" in its own row, while a clip analysed with nothing found SHALL show no marks. A read that fails SHALL
leave the timeline usable and show a note, not an alert, that says the suggestions could not be read and why,
in the words the page uses for its other reads.

#### Scenario: A closed or preparing timeline reads no analysis

- **WHEN** the operator opens the page of an analysed event and does not open the Timeline, or opens it while a
  clip's proxy is not ready
- **THEN** no request to `…/analysis` has been made, and the first one is made when the track is shown

#### Scenario: Suggestions are drawn under their clip

- **WHEN** an analysed event's clip `C0012.MP4` has a black span from 0 to 3.2 s and a freeze span from 58.1 to
  60 s, and the timeline is shown
- **THEN** the clip's row has two marks, in time order, named "Black frames 0:00 to 0:03.2 (3.2 s), pending" and
  "Frozen picture 0:58.1 to 1:00 (1.9 s), pending", each with its icon and a `?` glyph

#### Scenario: A narrow span is still pressable

- **WHEN** the timeline is zoomed out so that a 0.4 s freeze span is 3 px wide
- **THEN** its mark is at least 44 px wide to press, and two such marks 10 px apart sit on two rows, both
  fully visible

#### Scenario: A cut covers the suggestion, however it was made

- **WHEN** a clip's black suggestion spans 0 to 3.2033333 s and its draft lists a cut from 0 to 1.5 s and another
  from 1.5 to 3.203 s
- **THEN** the suggestion's state is cut, because the two cuts touch and together cover the span to the
  millisecond

#### Scenario: Removing the cut brings the suggestion back

- **WHEN** a suggestion is cut by a cut the operator then removes in the Cuts panel
- **THEN** its mark reads pending again, without any press on the mark

#### Scenario: A saved approval shows on the first read

- **WHEN** `reel.yaml` holds a trim from 0 to 3.2 s with the reason `black` and analysis lists a black span from 0
  to 3.2 s on that clip
- **THEN** on opening the event page the suggestion reads cut

#### Scenario: A cut over part of the span

- **WHEN** a clip lists a cut from 0 to 1 s and a black suggestion spans 0 to 3.2 s
- **THEN** the suggestion reads partly cut

#### Scenario: Marks of adjacent clips never hide each other

- **WHEN** a clip ends with a black span and the next clip starts with one, so that their 44 px marks reach into
  each other at the current zoom
- **THEN** the two marks sit on two rows and each is fully visible and pressable

#### Scenario: A rendered but never analysed event

- **WHEN** an event has been rendered (its cache directory holds only the render manifest) and was never analysed
- **THEN** the lane says "Not analyzed" and names `auto-reel analyze`, and no clip row says "Not analyzed" or that
  nothing was found

#### Scenario: Never analysed, analysed clean, and a stale clip

- **WHEN** one event has no analysis cache, a second was analysed and nothing was found, and in a third the
  file `C0003.MP4` was replaced after analysis while its siblings have entries
- **THEN** the first says "Not analyzed" and names `auto-reel analyze`, the second says nothing was found, and
  the third marks only `C0003.MP4`'s row "Not analyzed"

#### Scenario: Reopening reads again

- **WHEN** the operator re-runs `auto-reel analyze`, presses Refresh (which closes the Timeline) and opens the
  Timeline again
- **THEN** the lane shows the new suggestions

#### Scenario: A failed read leaves the timeline

- **WHEN** `GET …/analysis` answers 502 for an unreadable disk, or does not answer
- **THEN** the timeline still shows, no marks are drawn, and a note says the suggestions could not be read and
  gives the cause

#### Scenario: Reading the analysis changes nothing

- **WHEN** the page shows the timeline of an analysed event and the operator makes no edit
- **THEN** no request other than reads is made, and no analysis is started

### Requirement: Suggestions are operable by keyboard and never shown by colour alone

The analysis lane of each visible clip SHALL be one group, named "Analysis suggestions of" and the clip's name
as the clip's row names it, and SHALL be one stop in the keyboard order: ArrowLeft and ArrowRight SHALL move
focus to the previous and next suggestion of the clip, and Home and End to its first and last. Moving to a
suggestion outside the part of the timeline in view SHALL bring it into view and focus it. Selecting a
mark (press, Enter, Space or arriving by arrow) SHALL show its detail (the clip, the kind in words, the span, the
length and the state in words) and SHALL move the timeline's playhead to the suggestion's start without starting
playback. The lane SHALL offer no decision outside a Timeline that is given one.

A suggestion's kind and state SHALL each be shown as words and as an icon or glyph, and a legend under the lane
SHALL spell the icons and glyphs out in words, never by colour alone
("State is never shown by color alone"), with text contrast of at least 4.5:1 and a visible focus indicator in
both colour schemes. When the system asks for reduced motion, the lane SHALL NOT animate. In a window 390 CSS
pixels wide, and down to 320, the lane and its detail SHALL NOT make the page scroll horizontally.

#### Scenario: Arrow keys walk the suggestions

- **WHEN** focus is on the first of three marks on a clip and the operator presses ArrowRight twice, then Home
- **THEN** focus is on the third mark, then the first, and each move leaves one mark in the tab order

#### Scenario: A mark out of view is reached

- **WHEN** the timeline is zoomed in and the next suggestion lies beyond the right edge
- **THEN** ArrowRight scrolls it into view and focuses it

#### Scenario: The lane reads in grayscale

- **WHEN** the timeline is viewed with all colour removed
- **THEN** each mark still shows its kind icon and its state glyph, and the detail reads the kind and state in
  words

#### Scenario: The lane fits a phone

- **WHEN** the event page with its timeline is viewed 390 and 320 CSS pixels wide
- **THEN** the page does not scroll horizontally, the lane scrolls with the timeline inside it, and the detail's
  buttons wrap and stay fully visible

#### Scenario: Reduced motion

- **WHEN** the system asks for reduced motion and a mark is selected
- **THEN** nothing in the lane or its detail animates

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
- **THEN** the cut's end handle is drawn at the clip's end, reads 7 with a range that holds 7, and its value text says "0:07" and that the cut runs past the clip's end
- **WHEN** the operator presses Left on it
- **THEN** the end is one frame earlier, at 6.98 s

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
- **WHEN** focus is on "Cut 1 start of s1710001.mp4" (1.0 s, 50 fps) and the operator presses Right three times
- **THEN** the start is at 1.06 s, the handle reads 1.06, and the Cuts panel lists 0:01.06 to 0:02.5

#### Scenario: One and five seconds
- **WHEN** the operator presses Shift+Right on the end handle of cut 1 (2.5 s)
- **THEN** the end is at 3.5 s
- **WHEN** the operator presses Page Up
- **THEN** the end stops at 4.0 s, the start of cut 2

#### Scenario: Home and End reach the limits
- **WHEN** the operator presses Home on the start handle of cut 1, then End
- **THEN** the start goes to 0, then to 2.44 s (three frames before the end), and the Cuts panel lists those times

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

A time typed in a field SHALL be taken on Enter or when the field loses focus, in the forms the Cuts panel accepts (seconds, `m:ss`, `h:mm:ss`, up to three decimals), and SHALL make one edit of the draft. It SHALL be refused, and nothing changed, for the reasons the Cuts panel refuses a typed cut and in its words: unreadable, too precise, an end not after the start, an overlap with another cut of the clip that is not removed (the cut itself excepted), an end after the clip's length (the proxy's duration). A refusal SHALL be shown at the field the Cuts panel's rule names for it and announced; when the time was taken with Enter that field receives keyboard focus, and when it was taken because the field lost focus the refusal stands in the same words and focus stays where the operator put it. Escape in a field SHALL put the cut's current time back. A typed time need not be a frame time: it is taken to the millisecond, as a typed cut is.

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
- **WHEN** cut 1 ends at 2.5 s and cut 2 starts at 2.6 s at 40 px per second (4 px apart), and a finger presses 1 px right of cut 1's end
- **THEN** cut 1's end handle takes the press, and cut 1 is the selected cut
- **WHEN** a finger presses 3 px right of cut 1's end
- **THEN** cut 2's start handle takes it, being the nearer edge

#### Scenario: A swipe scrolls
- **WHEN** a finger swipes sideways over a clip's filmstrip, away from any handle
- **THEN** the track scrolls and no cut changes

### Requirement: Trimming is unavailable while a save or a move is pending, and where there is nothing to trim

While a save is in flight or a move of marked clips is pending, the trim handles and the selected cut's fields SHALL say that they are unavailable (`aria-disabled`, in words in the group) and SHALL change nothing when used, as the Cuts panel's controls do; the playhead and playing SHALL stay usable. A clip with no ready proxy SHALL have no timeline presence ("The Timeline asks for the clips' proxies when they are missing"), so it has no handle; its cuts stay editable in its Cuts panel by typed times. A drag in progress when a save starts SHALL end as if Escape were pressed.

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

### Requirement: In Edit mode a suggestion is approved as a cut of the draft

In Edit mode the analysis lane SHALL offer **Approve as cut** for a suggestion whose state is pending or partly cut, as a button in the detail of the selected mark (44 px high under a coarse pointer) and as the key **A** on the focused mark. Approving SHALL add the suggestion to the clip's cuts in the editor's **draft**, as the Cuts panel's "Add" does, through the same check: the span to the millisecond ("Times are written one way on every screen"), refused when it is empty or reversed, when it ends after the clip's length (the proxy's duration), or when it overlaps a cut of the clip that is not removed. The cut SHALL have the suggestion's kind as its reason (`black`, `white`, `freeze`, or an unrecognised kind as written) and not `manual`; the Cuts panel SHALL list it at once, with that reason in words, numbered as a cut added there, and the Timeline SHALL draw it with its trim handles. Approving SHALL change nothing else: no existing cut is merged, trimmed or removed, and a **partly cut** suggestion SHALL be refused as an overlap, never added as the part that is left.

Approving SHALL write nothing by itself. It is an edit of the draft: the save bar SHALL count one cut added, the unsaved-changes guard SHALL apply, and Save SHALL write the cut to `reel.yaml` as a trim with the kind as its `reason`, by the existing whole-document write ("Saving an edit writes only what the operator changed"). Removing the cut in the Cuts panel, and Reset, SHALL return the suggestion to pending with no other action, and an approval followed by its removal SHALL leave nothing to save. An approved cut, once saved, SHALL read as **cut** on the next read of the page, as a cut saved by hand over the same span does ("The timeline shows the event's analysis suggestions beside its clips").

Approving SHALL be said once, politely, through Edit mode's one live region ("Approved black frames, 0:00 to 0:03.2, of C0012.MP4 as a cut; 1 cut added."). A refusal SHALL add nothing, SHALL be said in the live region and shown in the detail, in the Cuts panel's words ("Not approved: …", an overlap naming the cut by its number in the panel and saying to remove it first), and the suggestion SHALL keep its state. Approving a suggestion that is already cut, or dismissed, SHALL change nothing and say so ("Already cut: …", "Dismissed: … Restore it first."). The read view SHALL offer no approval: reading a screen never changes state.

#### Scenario: Approving adds a cut with the kind as its reason
- **WHEN** in Edit mode a clip `C0012.MP4` of 25 s with no cuts has a pending black suggestion from 0 to 3.2033 s and the operator selects its mark and presses "Approve as cut"
- **THEN** the clip's Cuts panel lists one cut, 0:00 to 0:03.203, with the reason "black", the Timeline draws it with two handles, the mark reads cut, the save bar says that 1 cut was added, nothing has been written, and the live region said "Approved black frames, 0:00 to 0:03.203, of C0012.MP4 as a cut; 1 cut added."

#### Scenario: Save writes the reason
- **WHEN** the operator then presses Save
- **THEN** `reel.yaml` gives `C0012.MP4` a trim from 0 to 3.203 s with the reason `black`, the page reads that trim back, and the mark reads cut

#### Scenario: Removing the cut brings the mark back
- **WHEN** the operator removes that cut in the Cuts panel, or uses Reset
- **THEN** the mark reads pending, the save bar is gone if nothing else was edited, and the Cuts panel lists no cut

#### Scenario: An overlap is refused in words
- **WHEN** the clip lists a cut from 2 to 4 s (cut 1) and the operator approves a freeze suggestion from 3 to 5 s
- **THEN** no cut is added, the detail and the live region say "Not approved: this overlaps cut 1 (0:02 to 0:04). Remove that cut first.", the draft is as it was, and the mark still reads pending

#### Scenario: A partly cut suggestion is not completed for the operator
- **WHEN** the clip lists a cut from 0 to 1 s and the operator approves a black suggestion from 0 to 3.2 s
- **THEN** it is refused for the overlap with cut 1, and no cut from 1 to 3.2 s is added

#### Scenario: A suggestion past the clip's end is refused
- **WHEN** a suggestion ends at 6.2 s on a clip whose proxy is 6.08 s long and the operator approves it
- **THEN** it is refused in the Cuts panel's words for a cut that ends after the clip, and nothing is added

#### Scenario: Approving twice adds one cut
- **WHEN** the operator presses A on a pending mark and presses A again
- **THEN** the draft holds one cut, and the second press says "Already cut: …"

#### Scenario: The read view has no approval
- **WHEN** the Timeline is opened on the event page's read view
- **THEN** the detail of a selected mark has no Approve, Dismiss or Restore, the key A on a mark does nothing, and no request other than reads is made

### Requirement: A suggestion is dismissed for the page visit and restored, without an edit

In Edit mode the analysis lane SHALL offer **Dismiss** for a pending suggestion and **Restore** for a dismissed one, as buttons in the detail of the selected mark and as the key **R** on the focused mark (R on a pending mark dismisses it, R on a dismissed mark restores it). A dismissed suggestion SHALL read **dismissed**, with its glyph and word, unless a cut covers any of its span, in which case it reads by its cuts ("A cut outranks a dismissal"). Restoring SHALL return it to pending. Dismissing SHALL NOT be an edit: no cut is added, the draft SHALL stay as it was, the save bar SHALL NOT appear, Save SHALL stay unavailable if nothing else was edited, and the unsaved-changes guard SHALL NOT apply, because `reel.yaml` has no field for a rejection and nothing is written.

A dismissal SHALL last for the page visit: it SHALL survive opening and closing the Timeline, entering and leaving Edit mode, a Refresh and a Save, and SHALL be gone when the page is reloaded or left. A dismissal whose suggestion a new read of the analysis no longer lists SHALL be dropped silently. While any suggestion can be decided, the lane SHALL say once, as text, that dismissed suggestions come back when the page is reloaded. Dismissing and restoring SHALL each be said once through the live region ("Dismissed black frames, 0:00 to 0:03.2, of C0012.MP4.", "Restored …"). A suggestion that is cut or partly cut SHALL answer Dismiss with a statement ("Already cut: …", "Partly cut: … It is decided by the cut that overlaps it.") and change nothing.

#### Scenario: Dismiss and restore leave the draft alone
- **WHEN** in Edit mode, with nothing edited, the operator presses R on a pending mark, then R again
- **THEN** the mark reads dismissed with its `×` glyph and the word, then pending; no save bar appeared, Save was never enabled, and leaving Edit mode asked nothing

#### Scenario: A dismissal outlives Edit mode and a Refresh
- **WHEN** the operator dismisses a mark, leaves Edit mode, presses Refresh and opens the Timeline again
- **THEN** the mark still reads dismissed; after a reload of the page it reads pending

#### Scenario: A cut outranks a dismissal
- **WHEN** a dismissed suggestion's span is cut by hand in the Cuts panel
- **THEN** the mark reads cut; and when that cut is removed it reads dismissed again

#### Scenario: A dismissed suggestion is restored before it is approved
- **WHEN** the operator presses Approve on a dismissed mark
- **THEN** no cut is added and the live region says "Dismissed: … Restore it first."

#### Scenario: The note is said once
- **WHEN** Edit mode's Timeline shows marks that can be decided
- **THEN** one line under the lane says that dismissed suggestions come back when the page is reloaded; the read view shows no such line

### Requirement: A and R decide only the focused mark, and the buttons decide the same

The keys **A** (approve) and **R** (dismiss or restore) SHALL act only when the focused element is a suggestion's mark, never from the document: typing "a" or "r" in the title, the location or a typed cut time SHALL decide nothing. They SHALL ignore Ctrl, Meta and Alt chords, a key repeat and an input-method composition, SHALL ignore Shift (the key is a letter), and SHALL call `preventDefault` only when they acted; where they did not act (a Timeline without decisions, a pending save) the key SHALL be left to the browser; a key that says why nothing was done ("Already cut") has acted. The detail's buttons SHALL make the same decisions in the same words, and are the route for touch and assistive technology; a mark SHALL advertise its keys (`aria-keyshortcuts="A R"`) only while it can be decided. After a decision keyboard focus SHALL stay on the same mark, and the detail SHALL stay on it, so that Restore is one press away.

#### Scenario: Typing in a field decides nothing
- **WHEN** the operator types "a" and "r" in the event's title field in Edit mode while the Timeline shows pending marks
- **THEN** the title holds the typed letters and no suggestion changed state

#### Scenario: A chord is the browser's
- **WHEN** a mark has focus and the operator presses Ctrl+R or Ctrl+A
- **THEN** nothing is decided and the browser's own action is not prevented

#### Scenario: The decision keeps focus
- **WHEN** the operator presses A on a focused pending mark
- **THEN** the mark now reads cut, keyboard focus is still on it, and the detail still shows it

#### Scenario: The button does what the key does
- **WHEN** the operator selects a pending mark by touch and presses "Dismiss", then "Restore", then "Approve as cut"
- **THEN** the mark reads dismissed, pending, then cut, each said once in the live region, with the draft changed only by the last

### Requirement: Decisions are unavailable while a save or a move is pending

While a save is in flight or a move of marked clips is pending, Approve, Dismiss and Restore SHALL say that they are unavailable (`aria-disabled` on the buttons, in words in the detail, as the trim handles do) and SHALL change nothing, whether pressed or keyed; selecting a mark, moving between marks and the playhead SHALL stay usable. A decision SHALL never be announced as done when no change was made.

#### Scenario: A pending save blocks the decision
- **WHEN** the operator presses Save and, before the service answers, presses Approve as cut on a pending mark and presses A on another
- **THEN** no cut is added, nothing is announced as approved, the buttons read as unavailable, and when the save has ended both marks are still pending

### Requirement: A press handed to a nearer handle selects and focuses the handle that took it

Where the press areas of two trim handles overlap and a press is handed to the nearer one ("Trim handles are large enough for a finger, and a swipe still scrolls"), the cut of the handle that took the press SHALL be the selected cut, and that handle SHALL hold keyboard focus when the press ends, whatever had focus before, for a mouse, a pen and a finger, in Chrome and in Firefox 155 or newer. This SHALL hold also for a mouse press that the browser delivers without pointer events (a bare `mousedown`, `mouseup` and `click`, as Firefox does under touch emulation): such a press SHALL be handed over by position as a pointer press is, and the browser SHALL NOT move focus to, or select the cut of, the handle under the pointer when another took the press. Such a press starts no drag. Tab, a key and a programmatic focus on a handle SHALL select its cut as before, and a secondary mouse button SHALL be left to the browser.

#### Scenario: A mouse press handed to a handle that already has focus
- **WHEN** the end of cut 1 and the start of cut 2 are 4 px apart, the end of cut 1 holds focus, and a mouse press lands 1 px right of cut 1's end, on cut 2's start, which lies on top
- **THEN** cut 1 is selected (the fields read "Cut 1 of g1.mp4"), "Cut 1 end of g1.mp4" holds focus, and nothing is edited, in Chrome and in Firefox

#### Scenario: A mouse press handed to a handle that does not have focus
- **WHEN** the same press lands while cut 2's start holds focus, or while nothing in the Timeline does
- **THEN** the handle that took the press is selected and focused

#### Scenario: A mouse press without pointer events is handed over too
- **WHEN** the browser delivers that press as a `mousedown` with no `pointerdown` (Firefox with touch emulation on)
- **THEN** cut 1 is selected and "Cut 1 end of g1.mp4" holds focus, as with pointer events, and no edit is made

#### Scenario: Tab still selects
- **WHEN** the operator tabs from cut 1's end to cut 2's start
- **THEN** cut 2 is selected

### Requirement: The Timeline pauses, and is paused, like every other player

The Timeline's video SHALL take part in the page's one rule that a video that starts pauses every other playing video
("The event page plays one video at a time"), as one player among the others and with no rule of its own for any other
player. Pressing Play on the Timeline while the Movie section's player or a clip's player plays SHALL pause that
player where it is; a video of the page that starts while the Timeline plays SHALL pause the Timeline.

A Timeline paused that way SHALL stay open, keep its playhead where it stopped, keep every handle and mark usable, and
play on from the playhead when its own Play is pressed. Being paused by another player SHALL NOT be taken for the
operator's Pause in any way that changes the Timeline: it SHALL NOT edit, select or move anything, SHALL NOT announce
anything, and SHALL NOT start the Timeline again by itself. A change of the Timeline's file at a clip boundary SHALL be
the Timeline continuing, not a start of another video: but when another video has started while the file was changing,
the Timeline SHALL NOT take playback back, and SHALL stay paused at the boundary.

#### Scenario: The Timeline starts while a clip plays
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the operator presses Play on the Timeline
- **THEN** the clip's player is paused at `0:03.2` and stays open, and the Timeline plays from its playhead

#### Scenario: A clip starts while the Timeline plays
- **WHEN** the Timeline plays across `s1710001.mp4` and the operator presses "Play s1710002.mp4" on that clip's
  thumbnail and then the player's Play
- **THEN** the Timeline is paused with its playhead at the place it stopped, it is still open, no handle or mark
  has moved, nothing was announced, and the clip plays
- **WHEN** the operator then presses the Timeline's Play
- **THEN** the Timeline plays on from its playhead and the clip is paused

#### Scenario: A start during a clip boundary is kept
- **WHEN** the Timeline plays and, within the moment its file changes at the boundary between two clips, the
  operator presses the Movie section's play
- **THEN** the movie plays, the Timeline stays paused at the boundary and does not start again by itself

#### Scenario: The movie and the Timeline in either order
- **WHEN** the movie plays and the operator presses Play on the Timeline, and then presses the movie's play
- **THEN** each start pauses the other, and neither player has closed or moved

### Requirement: The Timeline shows a clip's turn

The Timeline SHALL show a clip turned by the clip's `rotate` (the draft's in Edit mode, the saved one in the read view),
as "Every picture of a clip shows its turn" requires: its one video, while the playhead is in the clip, and each tile of
the clip's filmstrip. The turn SHALL be a transform of the proxy's picture and of the sprite's tiles; the proxy and the
sprite SHALL NOT be requested again because of a turn. The track's geometry SHALL NOT depend on a turn: a clip's lane
width SHALL stay its proxy's length, its tiles SHALL keep the lane height, and a turned tile SHALL be fitted inside its
tile box, uncropped. The playhead, the chapters, the cuts, the trim handles and the suggestions SHALL keep their places
and times. A change of a turn in the draft SHALL show on the video and the tiles at once. At the swap between clips the
video SHALL be turned by the next clip's turn before it is shown.

#### Scenario: Filmstrip tiles are turned and fitted
- **WHEN** a landscape clip with `rotate: 90` is on the Timeline
- **THEN** each of its tiles shows the frame turned a quarter clockwise, whole inside the tile, and the lane is as wide as before

#### Scenario: The video follows the clip it is in
- **WHEN** play passes from an unturned clip to one turned 90 degrees
- **THEN** the video is shown turned for the second clip, and unturned again after the next unturned clip

#### Scenario: Turning in Edit mode shows at once
- **WHEN** the operator presses Rotate right on a clip while the Timeline is open
- **THEN** its tiles and, when the playhead is in it, the video show the new turn with no request for a sprite or a proxy

### Requirement: Each chapter's title card is a block on the Timeline

The Timeline SHALL show a lane of title cards directly above the clips, from the event detail's resolved cards
(`chapters[].card`) and the detail's `title_cards.enabled` (the draft's Title cards switch while it differs, in Edit mode), with one block per chapter whose card the render draws: a
chapter with a shown clip that has footage left after the cuts, when title cards are enabled. The block
SHALL show the card's title text (its resolved `title`), its length, and its look in words and shape, never by
colour alone:

- a **black** card SHALL be a block of its own, as long as the card's `duration`, **before** the chapter's first
  footage, and SHALL add its length to the track: the clips after it start that much later. A cut at the start of
  the chapter's first clip does not move it: the card opens the chapter, and the leading cut's hatch follows it.
- a **video** card SHALL be a block over the **start** of the chapter's first footage, aligned with the footage it
  covers, joined to the clip by an edge marker, as long as the card's `duration` or the first kept span if that
  is shorter, and SHALL add no time. It SHALL start where the first kept span starts, so a clip whose first 3 s
  are cut puts the block at 3 s.
- the **opening card** (the default chapter's) SHALL be first when the default chapter plays first, as the page
  lists the chapters.

A chapter's card anchors at its first shown clip; when every part of that clip is cut, at the next shown clip of
the chapter that has footage, as the render moves it. A chapter with no shown clip, or whose shown clips are
wholly cut, SHALL have no block. When title cards are not enabled, every chapter with footage SHALL have its block drawn in an off look (a dashed
outline and the word "not enabled", no time added) and the lane SHALL say once that the render draws no title cards for
the event, adding "set by the project's config.yaml" when the detail's `title_cards.source` is `project`. The page
SHALL NOT guess the effective state from `reel.yaml` alone: it SHALL use the detail's `title_cards`, which the
engine resolves from the event and the project, and the movie's length SHALL be presented as final whenever that
answer exists, never with a "not counted" caveat. When `title_cards` is null (`title_cards_error`), the lane SHALL
say so with the service's words and draw no block. When the event's card style or a chapter's card could not
be resolved (`title_card_error`, `card_error`), the lane SHALL say so with the service's words and draw no block
for the cards affected; a card with a duration that is not a finite number above zero SHALL be said as unreadable,
never drawn at a guessed length. A card block SHALL be drawn only when in view (the track's windowing), and its
look SHALL meet the contrast of the rest of the page in the light and in the dark scheme.

Each block SHALL show a miniature of its card as its background: the card's own image ("Card images are fetched
once and kept"), fitted to cover the block, so that a black card is dark and a video card is its text over the
clip's filmstrip. A black card's block SHALL keep a light inner ring in the dark scheme, so that it is told from the
page. The card's title SHALL be written on a solid strip of the block's colour over the miniature when it fits the block, so that the title inside the miniature never shows through behind it, and the block's accessible name
and tooltip SHALL carry it always. A block SHALL be at least 24 px wide however far the track is zoomed out, drawn
over the neighbouring track without moving it, so that a card is still pressed; its time on the track SHALL not
change. While a card's image is missing, the block SHALL show the card's title on black. The Timeline plays and shows
the cards: "The Timeline plays the title cards as the movie will" and "The playhead can be put in a card" say how, and
no note SHALL say that the Timeline does not play cards. A press in a black card's span or block SHALL do
what activating the block does ("A selected title card opens its inspector in Edit mode": it opens the card's dialog in
Edit mode and only selects in the read view) and SHALL also put the playhead there.

#### Scenario: A black card before the second chapter
- **WHEN** an event with the chapters "" (opening card black, 3.0 s) and "Dag 2" (black, 4.0 s) has a 20 s clip in
  each, at 40 px per second
- **THEN** the lane shows the opening block first, 120 px wide, then the clip 800 px wide, then "Dag 2"'s block
  160 px wide before its clip, and the chapter band's "Dag 2" starts at the block

#### Scenario: A video card sits on the footage and adds no time
- **WHEN** "Dag 2" has a video card of 4.0 s and its first clip is 20 s
- **THEN** the block is 160 px wide at the clip's first pixel, the clip does not move, and the movie's length does
  not change

#### Scenario: A leading cut moves a video card, not a black card
- **WHEN** the first clip of each of two chapters has a cut from 0 to 3.0 s, one chapter's card being black and
  the other's video
- **THEN** the black card is drawn before the clip's start, and the video card begins at 3.0 s of the clip

#### Scenario: A card longer than its footage
- **WHEN** a video card of 7.0 s is on a first clip whose first kept span is 3.0 s
- **THEN** the block is 3.0 s wide, as the render clamps it, and its words say "3.0 s of 7.0 s"

#### Scenario: A chapter cut away entirely has no card
- **WHEN** every clip of a chapter is wholly cut
- **THEN** the lane has no block for it

#### Scenario: The title decorator is off
- **WHEN** the detail has `title_cards: {enabled: false, source: "event"}`
- **THEN** the blocks are drawn in the off look with no time added, and the lane says the render draws no title cards

#### Scenario: The decorators are not set in reel.yaml
- **WHEN** the event's `reel.yaml` has no `look.decorators` and the detail has `title_cards: {enabled: true, source: "default"}`
- **THEN** the blocks are drawn as cards that play, their black lengths are in the movie's length, and nothing says
  "unset" or "not counted"

#### Scenario: The project turns them off
- **WHEN** the detail has `title_cards: {enabled: false, source: "project"}`
- **THEN** the blocks are off, and the lane says it is set by the project's config.yaml

#### Scenario: The decorators are not a list
- **WHEN** the detail has `title_cards: null` and `title_cards_error` names `look.decorators`
- **THEN** the lane shows that text and no block, and the movie's length does not claim to count cards

#### Scenario: The switch is turned off in the draft
- **WHEN** in Edit mode the operator turns Title cards Off and has not saved
- **THEN** the blocks go off and the movie's length drops the black cards at once, and Reset brings them back

#### Scenario: A card that cannot be resolved
- **WHEN** the detail has `title_card_error: "look.title_card.font_family"` and every chapter's `card` is null
- **THEN** the lane shows that text in a note and no block, and the clips, cuts and playhead are unaffected

#### Scenario: A press in a black card's span
- **WHEN** the operator presses inside a black card's block with the playhead at 5.0 s of a clip
- **THEN** the card is selected (in Edit mode its dialog opens) and the playhead is in the card at the press, showing its image

#### Scenario: A zoomed-out card stays pressable
- **WHEN** a 3.0 s black card is drawn at 4 px per second (12 px wide)
- **THEN** its block is 24 px wide, the clips after it start where they did, and a press on it selects the card

#### Scenario: A block shows its card
- **WHEN** a black card's image has been fetched and the Timeline is in the dark scheme
- **THEN** the block's background is that image, its title is written on a solid strip over it when it fits, its accessible name
  carries the title, and a light ring marks its edge

### Requirement: Edit mode's chapter list shows each chapter's card as a row

Edit mode's chapter list SHALL show, at the head of each chapter, a row for that chapter's card from the event
detail's resolved card: its title, its subtitle ("No subtitle" when empty), its duration, "Black" or "Video" and
its font name, in words. The default chapter's row SHALL be the opening card and SHALL be the only place the main title card is shown: its heading
line SHALL be the "Main title card" press-to-edit event-title control, which edits the draft's title as before, and the
page SHALL NOT show a second line for it beside the row. The row SHALL be matched to
its chapter by the chapter's key. A chapter added in the draft has no saved card: its row SHALL say that its card
is drawn after Save, and SHALL NOT be selectable. A chapter whose draft name differs from the saved name SHALL show
the saved card and say the saved name. A card that could not be resolved SHALL say so in words in its row and
SHALL NOT show values. A row drawn while title cards are not enabled SHALL say "Not enabled". The row SHALL write nothing and request nothing.

#### Scenario: A row for each chapter
- **WHEN** Edit mode opens on an event with the chapters "" and "Dag 2", the latter with a 4.0 s video card in
  "Sofia Sans" titled "Dag två" with subtitle "Stranden"
- **THEN** each chapter's header is followed by its card row, and "Dag 2"'s says "Dag två", "Stranden", "4.0 s",
  "Video" and "Sofia Sans"

#### Scenario: Main's row is the opening card
- **WHEN** the operator opens the default chapter in Edit mode
- **THEN** there is one opening-card row, named for the opening card, whose heading is the "Main title card" control showing the event title, and that control still edits
  `metadata.title` in the draft and follows the metadata form; no second "Main title card" line exists

#### Scenario: A chapter added in the draft
- **WHEN** the operator adds a chapter "Dag 3" and has not saved
- **THEN** its row says its card is drawn after Save and offers no selection

### Requirement: A card is selected from the Timeline or the list, as one selection

The page SHALL hold one card selection, shared by the Timeline's blocks and Edit mode's rows, kept above both so
that a Refresh or leaving Edit mode, which close the Timeline section, do not end it. Pressing a block or a row
SHALL select that card, and the block and the row SHALL both show it selected, in more than colour. At most one
thing SHALL be selected on the Timeline: selecting a card SHALL end the selection of a cut, and selecting a cut
SHALL end the selection of a card. Pressing the selected card again SHALL leave it selected; Escape SHALL clear
it, unless the card's dialog is open, where Escape closes the dialog and the card stays selected. The selection SHALL end when its chapter is deleted or no longer in the event after a read. A block and a row
SHALL be buttons reached by Tab in document order, pressed by Enter or Space, with `aria-pressed`, named in words
as "Title card for <chapter>, 4.0 s, over video" (or "on black"; the default chapter: "Title card for the opening,
…"; a clamped video card: "…, 3.0 s of 7.0 s, over video"; the off look adds ", not enabled"). In the read view a selection SHALL open nothing but an inspector slot, a labelled region with the selected card's words; it SHALL write nothing, request nothing and be announced once through the polite status region. In Edit mode, pressing a block or a row SHALL also open that card's dialog (`web-app`, "A selected title card opens its inspector in Edit mode"), and there is no inspector slot in the page.

#### Scenario: One selection from either place
- **WHEN** the operator presses the block of "Dag 2" on the Timeline in Edit mode
- **THEN** the block is pressed, "Dag 2"'s row is shown selected, and the card's dialog opens (Edit mode) or the inspector slot names the card (read view)

#### Scenario: Selecting a cut ends a card selection
- **WHEN** a card is selected and the operator presses a cut's span
- **THEN** the cut is selected and the card is not

#### Scenario: Refresh keeps the selection
- **WHEN** a card is selected, the section is closed by a Refresh, and the read still lists the chapter
- **THEN** its row (Edit mode) is shown selected, and the block is pressed when the Timeline is opened again

#### Scenario: A deleted chapter ends the selection
- **WHEN** the selected card's chapter is deleted in the draft
- **THEN** nothing is selected and the slot is gone

#### Scenario: Keyboard and names
- **WHEN** a keyboard user tabs to the "Dag 2" block and presses Space
- **THEN** it is selected, a screen reader says "Title card for Dag 2, 4.0 s, over video, pressed", and the polite
  status says it once

#### Scenario: Reading changes nothing
- **WHEN** a card is selected in the read view or in Edit mode
- **THEN** no request is made and the Save bar shows no unsaved change

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
drag with the card as it was and no edit. A drag that ends where it began SHALL make no edit. Pressing the handle SHALL also select that card, as pressing its block does, but SHALL NOT open the card's dialog (a modal opening under the pointer would end the drag); activating the block's body opens it.

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

#### Scenario: A handle press selects the card
- **WHEN** the operator presses a card's end edge in Edit mode
- **THEN** the card is selected, no dialog opens, and the track has not moved

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

### Requirement: The Timeline plays the title cards as the movie will

When the Timeline plays into a **black** card's span, the player area SHALL show that card's image in place of the
video, fitted inside the same box as the video (letterboxed, uncropped), with the card's fade-in and fade-out as its
opacity over the card's length. The playhead SHALL advance in real time for the card's whole `duration`, without any
video playing, and then playback SHALL go on into the chapter's first clip at that clip's first kept frame. The
Timeline SHALL load and seek that clip's proxy during the card, so that the hand-over shows the clip's frame with no
gap of black or of a stale picture; the card's image SHALL be removed only when that frame is ready to be shown, and
if it is not ready when the card ends the card SHALL stay on its last frame until it is. A **video** card's image
(text on transparency) SHALL be laid over the playing video for the card's window, from the start of the first kept
span to its clamped end, drawn above the video at the same size and position, with the fades as opacity; it SHALL
add no time and SHALL not touch the video. The card's fades SHALL be the project's default fades (2 s in, 2 s out)
scaled so that their sum does not exceed the card's length, as the render clamps them, because the event detail does
not carry them; the Timeline SHALL say once, in the card inspector slot's words, that a fade set by the event's or
the project's `look.title_card` is not shown here.

Pause and Play, Space on the playhead, and a seek SHALL work inside a card: Pause stops the card's clock where it is,
and Play goes on from there. A video that starts elsewhere on the page ("The Timeline pauses, and is paused, like every
other player") SHALL pause the Timeline during a card too, with the playhead where it stopped and no announcement; the
card's clock SHALL NOT go on by itself afterwards. A card's span in a cut-skipping play SHALL be played whole. The
sound of a card is silence; the Timeline SHALL not start an audio element for it.

The card clock SHALL be the browser's frame clock, and SHALL be driven by elapsed time, not by a count of frames, so a
slow frame does not stretch the card. A page that is hidden SHALL pause the clock as it pauses a video.

#### Scenario: Play from zero through the opening card
- **WHEN** an event whose opening card is black and 7.0 s is played from 0:00 on Chrome 154 and on Firefox 155 or
  newer
- **THEN** the card's image is shown, the playhead moves from 0 to 7.0 s over about 7 s, and then the first clip's
  video plays from its first frame with the card gone, and the sampled playhead never goes backwards

#### Scenario: The hand-over has no gap
- **WHEN** the card ends and the clip's proxy was loaded and sought during the card
- **THEN** no sampled frame between the card's last frame and the clip's first shows the page's background, and the
  video's `currentTime` is the clip's first kept time when the card goes

#### Scenario: A video card over the video
- **WHEN** the Timeline plays a chapter whose card is video and 4.0 s over its first clip
- **THEN** the card's image is above the video for 4.0 s of the clip's time, the video keeps playing under it, the
  card's opacity rises over its fade-in and falls over its fade-out, and the image is gone after the window

#### Scenario: Pause and Play inside a card
- **WHEN** the operator presses Pause 1.2 s into a 7.0 s black card and then Play
- **THEN** the playhead stops at 1.2 s of the card, the image stays, the button says "Play", and Play goes on from 1.2 s
  and ends the card 5.8 s later

#### Scenario: Another player starts during a card
- **WHEN** the Timeline is inside a black card and the operator presses Play on the event's movie
- **THEN** the Timeline is paused with its playhead where it was, the movie plays, nothing is announced, and the card
  does not go on

#### Scenario: A slow frame does not stretch the card
- **WHEN** the browser presents no frame for 500 ms during a 7.0 s card
- **THEN** the card still ends 7.0 s after it began, within one frame

### Requirement: The playhead can be put in a card, and the readouts count card time

Pressing or dragging the playhead, on the ruler or on the track, into a black card's span SHALL put the playhead in
that card at that point and show that card's image there (opacity from its fades at that time), with no video change
beyond what the clip after the card needs for "The Timeline plays the title cards as the movie will". The playhead
SHALL be at the pointer in the card; the time it names SHALL count the card. The Event readout SHALL count the cards'
time: with the playhead 1.0 s into the opening card it reads "Event 0:01.00 of 2:43.76", the length being the movie's length with its
black cards, as the readout's scale is chosen from it. Inside a card the Clip readout SHALL read "Card 0:01.20 of
0:07.00" (the time in the card and the card's length, written to one scale so that the readout's width does not
change), and the clip's name cell SHALL name the card ("Title card for the opening"). The playhead slider's value text
SHALL say "title card for <chapter>, 1.2 s of 7.0 s; event 0:01.20 of 2:43.76" in a card, and `aria-valuenow` SHALL be
the position on the whole timeline including cards.

A frame step (Left, Right) and Shift/Page steps SHALL be taken on the timeline including cards: a step by seconds
(Shift, Page Up, Page Down) that lands in a card stops there; a frame step into the card from the clip before it SHALL
land on the card's first instant, and from the card on the clip's first frame; Home SHALL be the start of the opening
card when the opening card is black and End the last frame of the last clip. Within a card, Left and Right SHALL move by
one frame of the movie's output rate if the Timeline knows it, else by 0.1 s; the Timeline SHALL not claim frame
accuracy in a card. The end of a scrub, a key step and a click that end in a card SHALL be announced once ("Playhead at
title card for the opening, 1.20").

#### Scenario: A press into a mid card
- **WHEN** the event has a 4.0 s black card between two chapters and the operator presses the track 1.0 s into the
  card's span
- **THEN** the card's image is shown, the playhead is 1.0 s into the card, the Clip readout reads "Card 0:01.00 of
  0:04.00", and the Event readout reads the clip time before the card plus 1.0 s

#### Scenario: A drag across a card
- **WHEN** the operator drags the playhead from the end of the clip before a card, through the card, to the start of the
  next chapter's clip
- **THEN** the card's image shows while the pointer is in its span and the video returns after it, never more than one
  `<video>` for the Timeline and one seek in flight

#### Scenario: The Event readout counts card time
- **WHEN** the playhead is 3.00 s into the opening card of an event whose movie is 2:43.76 long
- **THEN** the Event readout reads "Event 0:03.00 of 2:43.76" and the Clip readout reads "Card 0:03.00 of" the card's length

#### Scenario: The slider says it is in a card
- **WHEN** a screen reader reads the playhead 1.2 s into the opening card of 7.0 s
- **THEN** its value text names the title card, 1.2 s of 7.0 s, and the event time including cards

### Requirement: Card images are fetched once and kept

When the Timeline opens, the page SHALL ask for every card's image once, for the cards the lane draws, one request at a
time, in play order, from `POST /api/v1/events/{id}/title-card/preview` with each card's resolved text, background and
length (and the draft event title for the opening card, and the draft's style when it differs from the saved one),
and SHALL keep each answer as an object URL keyed by the card's draft body and the style. The page SHALL ask for no
more than one at a time, and SHALL NOT start another request while the previous one is in flight. A `503` SHALL be
waited out for its `Retry-After` (at most 30 s a card, at least 1 s) and asked again up to three times, after which the
card is left without an image and said in words once; any other failure SHALL leave the card without an image and be
said by cause once, as the card inspector's preview does, and never retried by itself. While a card has no image its
block, and the player area during it, SHALL show its title on black. An edit to a card or to the event's card style in
Edit mode SHALL fetch only the cards affected, after the same quiet time as the inspector's preview, and SHALL replace
the old image only when the new one has arrived. Object URLs SHALL be revoked when the card changes, is removed, or the
Timeline closes. The cards' requests SHALL write nothing and SHALL not hold the page's other requests back.

#### Scenario: One request at a time, in order
- **WHEN** the Timeline opens on an event with six chapters
- **THEN** six requests are made one after another in play order, never two at once, and each block shows its image
  as it arrives

#### Scenario: A busy service
- **WHEN** a request is answered 503 with `Retry-After: 2`
- **THEN** the card is asked again after 2 s, the other cards wait behind it, and the page shows the card's title on
  black meanwhile

#### Scenario: Only the edited card is fetched
- **WHEN** the operator edits the third chapter's card title in the inspector and stops typing
- **THEN** one request is made for that card after the quiet time, the other cards' images are kept, and the block
  and the player show the new image when it arrives

#### Scenario: A card that cannot be drawn
- **WHEN** a card's request is answered 502
- **THEN** the card's block and its span in the player show the title on black, the cause is said once in words, and no
  further request is made for that card until it is edited

#### Scenario: Closing the Timeline lets go
- **WHEN** the Timeline section is closed
- **THEN** every object URL it made has been revoked and no request is in flight
