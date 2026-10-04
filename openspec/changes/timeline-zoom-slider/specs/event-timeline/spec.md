## ADDED Requirements

### Requirement: The Timeline is shown only in Edit mode, open from the start

The event page SHALL show a section headed "Timeline" (a level-two heading) only in Edit mode, after the metadata form
and the Poster panel and before the chapters' lists; it is the Timeline on which the operator trims cuts ("Edit mode's
cuts are trim handles"). The section SHALL be open whenever Edit mode shows: pressing Edit opens Edit mode with the
Timeline open, and a Refresh or a save keeps it open. It SHALL have no button that opens or closes it.

The read view SHALL show no Timeline: no section, no heading, no "Open timeline" or "Close timeline" button, no line
or region naming a selected title card, and SHALL create no `<video>` for a Timeline and make no request for a proxy, a
filmstrip, the analysis or a proxy job on its behalf, whatever the number of clips. The read view SHALL keep everything
else it shows: the event's chapters and clips with their play controls, cut summaries and turns, the Movie section and
the poster. While the event page is loading, or shows a failure, it SHALL show no Timeline section.

An open Timeline of an event whose proxies are not all ready SHALL show its Prepare state and nothing else. Showing the
Timeline SHALL change no state the service holds: it only reads. Starting a proxy job is a separate, explicit control
(see "The Timeline asks for the clips' proxies when they are missing").

The Timeline SHALL draw its clips, chapters and proxies as the event was last read (a proxy job that ends while Edit
mode is open reads the event again, quietly, and the Timeline follows it; the editor's draft is not touched by that
read), and its cuts as the draft lists them. It SHALL NOT draw the draft's unsaved order or chapters: when the draft
has moved a clip, reordered or renamed a chapter, or added or deleted one, the Timeline SHALL say in a note that it
shows the order last saved, and the cuts of every clip stay editable. Play on the Timeline SHALL skip the draft's cuts
as they are now, so that a trim is heard and seen before it is saved. The cuts are never "being read" and never
"unreadable": the draft holds them.

#### Scenario: The read view has no Timeline
- **WHEN** the operator opens the page of an event of 400 clips whose proxies are all ready
- **THEN** the read view has no heading "Timeline", no "Open timeline" button and no title card line, the page holds no
  `<video>` for a Timeline, and no request was made to a proxy, filmstrip, analysis or proxy-job address

#### Scenario: Edit opens the Timeline, leaving closes it
- **WHEN** the operator presses Edit on `2024-06-27 - Grillning med grannar` and later leaves Edit mode
- **THEN** Edit mode shows a Timeline section after the metadata form, open and showing its track, with no "Open
  timeline" or "Close timeline" button; after leaving, the read view shows no Timeline section and its clip list,
  Movie section and poster as before

#### Scenario: Edit mode without proxies shows Prepare
- **WHEN** the operator presses Edit on an event none of whose proxies is prepared
- **THEN** the open Timeline shows its Prepare state with "Prepare proxies", the chapters' Edit Titlecard buttons and the
  Details form work, and the page holds no `<video>` for the Timeline

#### Scenario: Showing is a read
- **WHEN** the operator presses Edit on an event whose proxies are all ready
- **THEN** every request the client made for the Timeline was a read, no file under the library changed, and the jobs
  the service lists are the same as before

#### Scenario: A reorder is not drawn
- **WHEN** in Edit mode the operator moves `s1710002.mp4` above `s1710001.mp4` in its chapter's list
- **THEN** the Timeline draws `s1710001.mp4` first, as last saved, and a note says that it shows the order last saved;
  after Save the Timeline draws the new order

#### Scenario: Play skips a trim that is not saved
- **WHEN** in Edit mode the operator trims the cut of `s1710001.mp4` to 1.0 to 3.5 s and plays the Timeline from 0.5 s
- **THEN** no frame between 1.0 and 3.5 s is shown, and nothing has been written

#### Scenario: Proxies prepared while editing
- **WHEN** in Edit mode the Timeline shows its Prepare state, the operator presses "Prepare proxies", and the job ends
- **THEN** the page reads the event again, the Timeline shows the track with the draft's cuts, and the draft, the save
  bar and the Cuts panels are as they were

### Requirement: The Timeline's toolbar keeps its place while the Timeline seeks, loads and plays

The Timeline's toolbar (Play, the playhead's readout with the clip's name and the Clip and Event times, the zoom group
and Use as poster) SHALL lay out each control in a slot whose position and size do not depend on the Timeline's state:
every control's box SHALL be the same, to within 1 CSS pixel, while the Timeline is idle, while a seek is loading its
frame, while it plays, while the playhead is in a title card, and whether or not Use as poster can act. The clip's name
SHALL stay on one line in its slot, cut with an ellipsis when it does not fit, with its whole text as its tooltip. No
state SHALL add text to the toolbar's rows: the reason Use as poster cannot act SHALL be its tooltip and its accessible
description, and SHALL be shown, in a tip that takes no room in the toolbar, and said once through the Timeline's
polite live region, when the operator presses the button while it cannot act (`web-app`, "Edit mode chooses the event's
poster on the Timeline"). Where the controls do not fit one row the toolbar MAY take more rows, at most three rows of
controls plus the movie stat's row (at 390 CSS pixels: Play and the readout, the zoom group, Use as poster); each
control SHALL then be in the same row and box in every state. The toolbar SHALL NOT make the page scroll
horizontally at any width from 320 to 1280 px, in the light or the dark scheme.

#### Scenario: A seek does not move the toolbar
- **WHEN** at 1280 px the operator clicks the ruler far from the playhead, so the frame takes a moment to load, and Use
  as poster cannot act until it has
- **THEN** no text appears beside Use as poster, the clip's name and the Clip and Event times stay on one line, and
  every control's box is the same as before the click and after the frame arrived

#### Scenario: Playing and a card do not move the toolbar
- **WHEN** the Timeline plays from a clip into a black title card and is paused there
- **THEN** Play, the readout, the zoom group and Use as poster have the same boxes as when the Timeline was idle

#### Scenario: The poster reason is given on demand
- **WHEN** the video has no decoded frame at the playhead and the operator presses Use as poster
- **THEN** a tip under the button says "The picture is still loading.", the live region says it once, the toolbar does
  not change, and the poster is not changed

#### Scenario: A phone-width toolbar
- **WHEN** the Timeline is shown 390 px wide, idle, then seeking, then playing
- **THEN** the toolbar has the same rows in each state (at most three rows of controls and the movie stat's row),
  each control in the same box, and the page has no horizontal scroll bar

## MODIFIED Requirements

### Requirement: The track zooms, and draws only what is in view

The Timeline SHALL offer **Zoom out**, a **Zoom** slider, **Zoom in** and **Fit** in its zoom group, and, while the
track has keyboard focus, the keys `+` or `=` (zoom in), `-` (zoom out), `0` (fit) and `\` (fit, and pressed again at
Fit, back to the zoom before it). **Fit** SHALL show the whole timeline in the track's width; zooming out SHALL stop at
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
is, and SHALL NOT zoom the page; a wheel turned without Ctrl or Cmd SHALL scroll as before. The scale SHALL be kept per
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
  cutting off a control

### Requirement: The track lays the clips out by their proxies' lengths, with the chapters and the cuts

With every shown clip ready, the Timeline SHALL show, in one horizontally scrolling track:

- a **ruler** with time labels in the page's time format (`m:ss`, with fractions only when zoomed in far enough that labels would repeat)
- the **clips end to end** in play order (a black title card's span, when the event draws one before a chapter, is between them, see "Each chapter's title card is a block on the Timeline"), each as wide as its proxy's duration at the current zoom, labelled with its name as the page names it. A proxy has the source's timestamps, so a time in a proxy is the same time in the source clip. A clip's length SHALL come from its proxy's facts, never from the browser's reading of a file and never defaulted; a clip shorter than a pixel at the current zoom SHALL still be drawn, one pixel wide at least, and the playhead SHALL be able to be put in it by keyboard.
- a **chapter band** above the clips: one segment per chapter spanning its shown clips, labelled with the chapter's name, or as the page headings an unnamed chapter ("Main" beside named chapters, "Clips" when none is named). The band's labels stay in view while their chapter scrolls past.
- each clip's **cuts**, as the Cuts panels list them now (the editor's draft, with the ones marked removed left out), drawn over the clip as spans with a hatch pattern and named by their reason in words ("manual", "black", "white", "freeze") in the span's text alternative; overlapping or touching cuts SHALL be drawn as the render joins them, one span; a cut that runs past the proxy's duration SHALL be drawn to the end of the clip only. Each cut SHALL have the two trim handles of "Edit mode's cuts are trim handles", drawn over the joined span.
- the **movie's length**: the sum of the shown clips' lengths minus the time the cuts remove, plus the lengths of the black title cards the track draws, beside the source length, in words ("Movie 3:12 of 3:45 of footage"; with black cards, "Movie 3:20 of 3:45 of footage, with 8 s of title cards")

The cuts are the draft's, so the track never shows them as being read or as unreadable.

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
- **WHEN** reading `reel.yaml`'s cuts for the read view's cut summaries fails and the operator presses Edit
- **THEN** the Timeline draws the cuts the editor's draft holds, with no note that the cuts are being read or could not
  be read

#### Scenario: The same cut in the read view and in Edit mode
- **WHEN** a clip lists a cut from 2.0 to 4.0 s, and the operator looks at the read view and then presses Edit
- **THEN** the read view shows the cut in the clip's cut summary and draws no Timeline, and Edit mode's Timeline draws
  the hatched span from 2.0 to 4.0 s with a start and an end handle

#### Scenario: Black cards count in the movie's length
- **WHEN** an event of 3:45 of footage with 33 s of cuts draws two black cards of 4.0 s each
- **THEN** the readout says "Movie 3:20 of 3:45 of footage, with 8 s of title cards", and a video card adds nothing to it

### Requirement: In Edit mode a suggestion is approved as a cut of the draft

In Edit mode the analysis lane SHALL offer **Approve as cut** for a suggestion whose state is pending or partly cut, as a button in the detail of the selected mark (44 px high under a coarse pointer) and as the key **A** on the focused mark. Approving SHALL add the suggestion to the clip's cuts in the editor's **draft**, as the Cuts panel's "Add" does, through the same check: the span to the millisecond ("Times are written one way on every screen"), refused when it is empty or reversed, when it ends after the clip's length (the proxy's duration), or when it overlaps a cut of the clip that is not removed. The cut SHALL have the suggestion's kind as its reason (`black`, `white`, `freeze`, or an unrecognised kind as written) and not `manual`; the Cuts panel SHALL list it at once, with that reason in words, numbered as a cut added there, and the Timeline SHALL draw it with its trim handles. Approving SHALL change nothing else: no existing cut is merged, trimmed or removed, and a **partly cut** suggestion SHALL be refused as an overlap, never added as the part that is left.

Approving SHALL write nothing by itself. It is an edit of the draft: the save bar SHALL count one cut added, the unsaved-changes guard SHALL apply, and Save SHALL write the cut to `reel.yaml` as a trim with the kind as its `reason`, by the existing whole-document write ("Saving an edit writes only what the operator changed"). Removing the cut in the Cuts panel, and Reset, SHALL return the suggestion to pending with no other action, and an approval followed by its removal SHALL leave nothing to save. An approved cut, once saved, SHALL read as **cut** on the next read of the page, as a cut saved by hand over the same span does ("The timeline shows the event's analysis suggestions beside its clips").

Approving SHALL be said once, politely, through Edit mode's one live region ("Approved black frames, 0:00 to 0:03.2, of C0012.MP4 as a cut; 1 cut added."). A refusal SHALL add nothing, SHALL be said in the live region and shown in the detail, in the Cuts panel's words ("Not approved: …", an overlap naming the cut by its number in the panel and saying to remove it first), and the suggestion SHALL keep its state. Approving a suggestion that is already cut, or dismissed, SHALL change nothing and say so ("Already cut: …", "Dismissed: … Restore it first.").

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
- **WHEN** the operator looks at the event page's read view of an event with pending suggestions
- **THEN** it shows no Timeline, no mark and no Approve, Dismiss or Restore, and no request other than reads is made

### Requirement: A suggestion is dismissed for the page visit and restored, without an edit

In Edit mode the analysis lane SHALL offer **Dismiss** for a pending suggestion and **Restore** for a dismissed one, as buttons in the detail of the selected mark and as the key **R** on the focused mark (R on a pending mark dismisses it, R on a dismissed mark restores it). A dismissed suggestion SHALL read **dismissed**, with its glyph and word, unless a cut covers any of its span, in which case it reads by its cuts ("A cut outranks a dismissal"). Restoring SHALL return it to pending. Dismissing SHALL NOT be an edit: no cut is added, the draft SHALL stay as it was, the save bar SHALL NOT appear, Save SHALL stay unavailable if nothing else was edited, and the unsaved-changes guard SHALL NOT apply, because `reel.yaml` has no field for a rejection and nothing is written.

A dismissal SHALL last for the page visit: it SHALL survive leaving and re-entering Edit mode, a Refresh and a Save, and SHALL be gone when the page is reloaded or left. A dismissal whose suggestion a new read of the analysis no longer lists SHALL be dropped silently. While any suggestion can be decided, the lane SHALL say once, as text, that dismissed suggestions come back when the page is reloaded. Dismissing and restoring SHALL each be said once through the live region ("Dismissed black frames, 0:00 to 0:03.2, of C0012.MP4.", "Restored …"). A suggestion that is cut or partly cut SHALL answer Dismiss with a statement ("Already cut: …", "Partly cut: … It is decided by the cut that overlaps it.") and change nothing.

#### Scenario: Dismiss and restore leave the draft alone
- **WHEN** in Edit mode, with nothing edited, the operator presses R on a pending mark, then R again
- **THEN** the mark reads dismissed with its `×` glyph and the word, then pending; no save bar appeared, Save was never enabled, and leaving Edit mode asked nothing

#### Scenario: A dismissal outlives Edit mode and a Refresh
- **WHEN** the operator dismisses a mark, leaves Edit mode, presses Refresh and presses Edit again
- **THEN** the mark still reads dismissed; after a reload of the page it reads pending

#### Scenario: A cut outranks a dismissal
- **WHEN** a dismissed suggestion's span is cut by hand in the Cuts panel
- **THEN** the mark reads cut; and when that cut is removed it reads dismissed again

#### Scenario: A dismissed suggestion is restored before it is approved
- **WHEN** the operator presses Approve on a dismissed mark
- **THEN** no cut is added and the live region says "Dismissed: … Restore it first."

#### Scenario: The note is said once
- **WHEN** Edit mode's Timeline shows marks that can be decided
- **THEN** one line under the lane says that dismissed suggestions come back when the page is reloaded

### Requirement: The Timeline shows a clip's turn

The Timeline SHALL show a clip turned by the clip's `rotate` (the draft's),
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
- **WHEN** the operator presses Rotate right on a clip in Edit mode
- **THEN** its tiles and, when the playhead is in it, the video show the new turn with no request for a sprite or a proxy

### Requirement: Each chapter's title card is a block on the Timeline

The Timeline SHALL show a lane of title cards directly above the clips, from the event detail's resolved cards
(`chapters[].card`) and the detail's `title_cards.enabled` (the draft's Title cards switch while it differs), with one block per chapter whose card the render draws: a
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
what activating the block does ("A selected title card opens its inspector in Edit mode": it selects the card and opens its
dialog) and SHALL also put the playhead there.

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
- **THEN** the card is selected, its dialog opens, and the playhead is in the card at the press, showing its image

#### Scenario: A zoomed-out card stays pressable
- **WHEN** a 3.0 s black card is drawn at 4 px per second (12 px wide)
- **THEN** its block is 24 px wide, the clips after it start where they did, and a press on it selects the card

#### Scenario: A block shows its card
- **WHEN** a black card's image has been fetched and the Timeline is in the dark scheme
- **THEN** the block's background is that image, its title is written on a solid strip over it when it fits, its accessible name
  carries the title, and a light ring marks its edge

### Requirement: A card is selected from the Timeline or the list, as one selection

The page SHALL hold one card selection, shared by the Timeline's blocks and Edit mode's chapter header bars, kept above both so
that a Refresh, a Save or leaving and re-entering Edit mode, which mount the Timeline again, do not end it. Pressing a block, or a chapter's Edit Titlecard button, SHALL select that card, and the block and the button SHALL both show it selected, in more than colour (the button as pressed, with `aria-pressed`). At most one
thing SHALL be selected on the Timeline: selecting a card SHALL end the selection of a cut, and selecting a cut
SHALL end the selection of a card. Pressing the selected card again SHALL leave it selected; Escape SHALL clear
it, unless the card's dialog is open, where Escape closes the dialog and the card stays selected. The selection SHALL end when its chapter is deleted or no longer in the event after a read. A block and the button SHALL be buttons reached by Tab in document order, pressed by Enter or Space, with `aria-pressed`, named in words
as "Title card for <chapter>, 4.0 s, over video" (or "on black"; the default chapter: "Title card for the opening,
…"; a clamped video card: "…, 3.0 s of 7.0 s, over video"; the off look adds ", not enabled"). Pressing a block or the button SHALL also open that card's dialog (`web-app`, "A selected title card opens its inspector in Edit mode"); a selection SHALL be announced once through the polite status region, and the page SHALL have no inspector slot or other line naming the selected card.

#### Scenario: One selection from either place
- **WHEN** the operator presses the block of "Dag 2" on the Timeline in Edit mode
- **THEN** the block is pressed, "Dag 2"'s Edit Titlecard button is shown pressed, and the card's dialog opens

#### Scenario: Selecting a cut ends a card selection
- **WHEN** a card is selected and the operator presses a cut's span
- **THEN** the cut is selected and the card is not

#### Scenario: Refresh keeps the selection
- **WHEN** a card is selected, the operator presses Refresh, and the read still lists the chapter
- **THEN** its Edit Titlecard button is shown pressed, and so is its block on the Timeline

#### Scenario: A deleted chapter ends the selection
- **WHEN** the selected card's chapter is deleted in the draft
- **THEN** nothing is selected

#### Scenario: Keyboard and names
- **WHEN** a keyboard user tabs to the "Dag 2" block and presses Space
- **THEN** it is selected, a screen reader says "Title card for Dag 2, 4.0 s, over video, pressed", and the polite
  status says it once

#### Scenario: Reading changes nothing
- **WHEN** a card is selected and its dialog is closed without a change
- **THEN** no request is made and the Save bar shows no unsaved change

## REMOVED Requirements

### Requirement: The read view and Edit mode each offer a Timeline that loads nothing until it is opened
**Reason**: The operator's decision of 2026-10-04: "remove the timeline viewer when NOT in edit mode. I only want it in
edit mode." The read view no longer has a Timeline section, an "Open timeline" button or a card inspector slot.
**Migration**: "The Timeline is shown only in Edit mode, open from the start" holds Edit mode's part of this requirement
unchanged (open on Edit, Prepare state, reads only, last-read order, the draft's cuts) and states that the read view has
no Timeline. To see an event on the Timeline, press Edit.

### Requirement: The Timeline pauses, and is paused, like every other player
**Reason**: This requirement governed the Timeline beside the read view's players (the Movie section's player and the
clip players opened from thumbnails). With the Timeline only in Edit mode, neither is on the page with it; there, "Edit
mode holds one video at a time" governs the Timeline and a clip preview.
**Migration**: None for the operator. The Timeline's video stays one of the page's videos under `web-app`'s "The event
page plays one video at a time", which covers every player without naming it.
