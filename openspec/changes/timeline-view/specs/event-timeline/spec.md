## Purpose

The event page's Timeline: one read-only track for the whole event, laid out from the facts of each clip's proxy,
that the operator scrubs and plays. It exists so a cut can be judged against the footage around it, which the
one-clip preview of Edit mode cannot show; trimming and analysis overlays build on it in later changes.

## ADDED Requirements

### Requirement: The event page offers a Timeline that loads nothing until it is opened

The event page's read view SHALL show a section headed "Timeline" (a level-two heading), after the Movie section (when the page shows one) and before the event's chapters. The section SHALL have a button, "Open timeline", that opens it; once open, the same button SHALL read "Close timeline". The button SHALL state whether the section is open (`aria-expanded`) and SHALL name the content it controls.

The section SHALL be closed when the page opens, after a Refresh, and after leaving Edit mode. While it is closed the page SHALL create no `<video>` for it and SHALL make no request for a proxy, a filmstrip or a proxy job, whatever the number of clips. In Edit mode the page SHALL show no Timeline section. While the event page is loading, or shows a failure, it SHALL show no Timeline section.

Opening the Timeline SHALL change no state the service holds: it only reads. Starting a proxy job is a separate, explicit control (see "The Timeline asks for the clips' proxies when they are missing").

#### Scenario: A closed timeline costs nothing
- **WHEN** the operator opens the page of an event of 400 clips and does not press "Open timeline"
- **THEN** the page holds no `<video>` for the Timeline and has made no request to a proxy or filmstrip address, and the Timeline section shows its heading and the "Open timeline" button, not expanded

#### Scenario: Edit mode has no timeline
- **WHEN** the operator opens the Timeline of `2024-06-27 - Grillning med grannar` and then presses Edit
- **THEN** the page shows Edit mode and no Timeline section, and leaving Edit mode shows the Timeline section closed

#### Scenario: Opening is a read
- **WHEN** the operator opens the Timeline of an event whose proxies are all ready
- **THEN** every request the client made for it was a read, no file under the library changed, and the jobs the service lists are the same as before

#### Scenario: The movie and the timeline do not play together
- **WHEN** the event's movie is playing and the operator presses Play on the Timeline
- **THEN** the movie pauses and the Timeline plays; pressing the movie's Play while the Timeline plays pauses the Timeline

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
- the **clips end to end** in play order, each as wide as its proxy's duration at the current zoom, labelled with its name as the page names it. A proxy has the source's timestamps, so a time in a proxy is the same time in the source clip. A clip's length SHALL come from its proxy's facts, never from the browser's reading of a file and never defaulted; a clip shorter than a pixel at the current zoom SHALL still be drawn, one pixel wide at least, and the playhead SHALL be able to be put in it by keyboard.
- a **chapter band** above the clips: one segment per chapter spanning its shown clips, labelled with the chapter's name, or as the page headings an unnamed chapter ("Main" beside named chapters, "Clips" when none is named). The band's labels stay in view while their chapter scrolls past.
- each clip's **cuts**, as the event page lists them from `reel.yaml`, drawn over the clip as spans with a hatch pattern and named by their reason in words ("manual", "black", "white", "freeze") in the span's text alternative; overlapping or touching cuts SHALL be drawn as the render joins them, one span; a cut that runs past the proxy's duration SHALL be drawn to the end of the clip only. The spans SHALL be read-only: no handle, no drag, no edit.
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

The Timeline SHALL hold exactly one `<video>`, created when the track opens, showing the proxy of the clip the playhead is in, at the playhead's time in that clip. The playhead SHALL be a slider over the whole timeline: it SHALL have the role `slider`, a name ("Playhead"), `aria-valuemin`, `aria-valuemax` and `aria-valuenow` in the timeline's seconds, and a value text that names the clip and the time in it ("Harbour, 0:12.4 of 0:24.96; 1:12 of 3:12 in all", the times in the page's time format). Dragging on the ruler SHALL move the playhead; so SHALL dragging on the track body with a mouse or a pen, and so SHALL dragging the playhead's own grip. With touch, the ruler SHALL scrub and a swipe on the track body SHALL scroll it. A press on the ruler or the track SHALL move the playhead there.

Moving the playhead into another clip SHALL load that clip's proxy into the same `<video>` and seek it, so the picture is the clip's frame at that time; a short flash between two clips is accepted. While the pointer is moving, the Timeline SHALL keep at most one seek in flight and SHALL seek to the latest pointer position when it completes, so that a scrub across many clips never queues a seek per pointer move. The video SHALL be paused while scrubbing. The picture and the playhead SHALL end where the pointer ended.

Below the video the Timeline SHALL show the clip's name, the playhead's time in the clip and in the whole timeline, in the page's time format, in words readable by assistive technology. The end of a scrub, a key step and a click SHALL be announced once through a polite status region ("Playhead at Harbour, 0:12.40"); the movement of a drag SHALL NOT be announced per update.

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

#### Scenario: The proxy is gone
- **WHEN** a proxy file is removed from the cache after the page read the event, and the playhead moves into that clip
- **THEN** the Timeline says that this clip's proxy is no longer there and offers "Prepare proxies", while the track and the other clips keep working

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

A **Play** button (**Pause** while playing) SHALL play from the playhead. It SHALL play as the movie will: no frame that lies wholly inside a cut is shown, cuts are joined as the render joins them, and a cut that runs to the end of a clip, or ends within 0.1 s of the clip's length, ends playing of that clip at that cut's start (the rules of the clip preview, D-16). At the end of a clip it SHALL go on into the next clip's proxy; at the end of the timeline it SHALL stop with the playhead at the end. The proxy's sound (AAC) SHALL play, in Firefox as in Chrome, including for a clip whose source has PCM audio. The playhead SHALL follow the video while it plays, and the button's state SHALL be in its words ("Play", "Pause"), not in its icon alone. Moving the playhead while playing SHALL continue playing from the new place.

If the browser refuses to start playing without a gesture, or the proxy fails to play, the Timeline SHALL say so by cause in a note, as the clip preview does, and stay paused.

#### Scenario: Cuts are skipped
- **WHEN** a clip lists a cut from 2.0 to 4.0 s and the playhead plays from 1.0 s
- **THEN** no frame between 2.0 and 4.0 s is shown and the playhead goes from 2.0 s to 4.0 s of that clip

#### Scenario: Play goes on into the next clip
- **WHEN** the playhead plays to the end of the first of three clips
- **THEN** the video loads the second clip's proxy and plays on from its first frame, and the playhead keeps moving through the whole timeline

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
