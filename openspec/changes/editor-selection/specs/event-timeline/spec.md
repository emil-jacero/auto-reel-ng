## ADDED Requirements

### Requirement: One selection in the workspace

The workspace SHALL hold one selection: nothing, a clip, a cut, a title card or a suggestion. Selecting one SHALL end
any other. Escape SHALL clear it. It SHALL survive a Refresh and a save while its target is still in the event, and
end when its target is gone. The selected thing SHALL be shown selected in more than colour.

#### Scenario: Card ends clip
- **WHEN** `s1710003.mp4` is selected and the operator presses the "Kvällen" card block
- **THEN** the card is selected, the clip is no longer outlined, and the inspector shows the Title card tab

#### Scenario: Target deleted
- **WHEN** the selected card's chapter is deleted
- **THEN** nothing is selected and the inspector shows the Event tab

### Requirement: The selection is shown and announced once

A selected clip or title card SHALL be shown as pressed (`aria-pressed`) wherever it is selected from; a cut and a suggestion by their own marks; none by colour alone.

The selection SHALL be announced once, through the polite status region, when it changes to something, and the page SHALL have no visible line naming it besides the selected thing's own name. Pressing the selected thing again SHALL leave it selected. Reading a selection SHALL make no request and SHALL NOT mark the page changed.

#### Scenario: Cut and suggestion shown
- **WHEN** a cut or a suggestion is selected
- **THEN** the cut is shown by its group and handles and the suggestion by its selected mark, neither by colour alone

#### Scenario: Selection announced once
- **WHEN** the operator selects the "Kvällen" card block, then a clip, a cut and a suggestion
- **THEN** each selection is said once by the polite status and no visible line names the selection

### Requirement: A card block is a button with a name in words

A title card's block and its chapter's Edit Titlecard button SHALL both show a selected card, as pressed. A card block SHALL be a button reached by Tab in document order, pressed by Enter or Space, named in words as "Title card for <chapter>, 4.0 s, over video" (or "on black"; the default chapter: "Title card for the opening, …"; a clamped video card: "…, 3.0 s of 7.0 s, over video"; the off look adds ", not enabled").

#### Scenario: Keyboard and names
- **WHEN** a keyboard user tabs to the "Dag 2" block and presses Space
- **THEN** it is selected, a screen reader says "Title card for Dag 2, 4.0 s, over video, pressed", and the polite status says it once

#### Scenario: A card block's name
- **WHEN** the "Dag 2" card, 4.0 s over video, is selected
- **THEN** its block's name is "Title card for Dag 2, 4.0 s, over video" and it is pressed

### Requirement: A clip is selected on the track or in the bin

A press on a clip block's body (not its edge tools or handles) and a press on its bin row SHALL select the clip. The
block SHALL be outlined with trim handles and the row highlighted; each SHALL be scrolled into view in its pane
without moving keyboard focus there. A press on empty track SHALL select nothing.

#### Scenario: Bin to track
- **WHEN** the track shows 0–20 s and the operator presses the bin row of a clip drawn at 31 s
- **THEN** the clip is selected, the track scrolls so the clip is in view, and focus stays on the bin row

#### Scenario: Bin press again
- **WHEN** a clip is selected, the track is scrolled away from it, and the operator presses its bin row again
- **THEN** the track scrolls back to the clip

#### Scenario: Empty track
- **WHEN** the operator presses the track below the last lane
- **THEN** nothing is selected and the inspector shows the Event tab

## MODIFIED Requirements

### Requirement: Each chapter's title card is a block on the Timeline

The Timeline SHALL show a lane of title cards directly above the clips, from the event detail's resolved cards
(`chapters[].card`) and the detail's `title_cards.enabled` (the draft's Title cards switch while it differs), with one block per chapter whose card the render draws: a
chapter with a shown clip that has footage left after the cuts, when title cards are enabled. The block
SHALL show the card's title text (its resolved `title`), its length, and its look in words and shape, never by
colour alone:

- a **black** card SHALL be a block of its own, as long as the card's `duration`, **before** the chapter's first
  footage, and SHALL add its length to the track: the clips after it start that much later. A cut at the start of
  the chapter's first clip does not move it: the card opens the chapter, directly before the clip's block, which starts at the first kept frame (a leading cut is not drawn).
- a **video** card SHALL be a block over the **start** of the chapter's first footage, aligned with the footage it
  covers, joined to the clip by an edge marker, as long as the card's `duration` or the first kept span if that
  is shorter, and SHALL add no time. It SHALL start where the first kept span starts, so a clip whose first 3 s
  are cut puts the block at the left edge of the clip's block, over 3 s of the clip.
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
what activating the block does ("One selection in the workspace": it selects the card, whose
editor is then docked in the inspector) and SHALL also put the playhead there.

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
- **THEN** the black card is drawn directly before the clip's block, the video card begins at the left edge of the
  clip's block (3.0 s of the clip), and no gap and no hatched span lies between either card and its footage

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
- **THEN** the card is selected, its editor shows in the inspector's Title card tab, and the playhead is in the card at the press, showing its image

#### Scenario: A zoomed-out card stays pressable
- **WHEN** a 3.0 s black card is drawn at 4 px per second (12 px wide)
- **THEN** its block is 24 px wide, the clips after it start where they did, and a press on it selects the card

#### Scenario: A block shows its card
- **WHEN** a black card's image has been fetched and the Timeline is in the dark scheme
- **THEN** the block's background is that image, its title is written on a solid strip over it when it fits, its accessible name
  carries the title, and a light ring marks its edge

### Requirement: A card block's end edge is dragged to set the card's length

In Edit mode, the end edge of every title-card block on the Timeline SHALL be a handle that sets that card's
`duration` in the draft. Pressing it with a mouse, a pen or a finger, and moving, SHALL move the edge by the distance
the pointer moves from where the edge was, in whole tenths of a second, snapping to a whole second within 8 screen
pixels, and staying between the card's limits (0.5 s to 60 s, and for a card over video no more than the first span of the
chapter's anchor clip that the draft's cuts keep). While dragging, the block, the handle and a readout in the Timeline's
fixed-width clock style ("Card 4.0 s") SHALL follow the pointer, and the rest of the editor SHALL NOT change: the save bar and the draft show nothing new until the pointer is released. The readout and
the snap to a whole second SHALL be given in words and by a line, not by colour alone. Releasing SHALL make one edit
of the draft, the card's duration, and announce the result once, politely, through Edit mode's one live region ("Title
card for Reception now 6.0 s. The movie is 2.0 s longer."). Escape, or the browser cancelling the pointer, SHALL end the
drag with the card as it was and no edit. A drag that ends where it began SHALL make no edit. Pressing the handle SHALL also select that card, as pressing its block does, and the inspector SHALL show its editor in the Title card tab; that panel is docked, so the drag and the track are not disturbed.

#### Scenario: A drag sets the length
- **WHEN** at 40 px per second the operator presses the end edge of the opening card (4.0 s, black) and moves the pointer 80 px right
- **THEN** the readout says "Card 6.0 s" while dragging, and the save bar counts no changed card until the pointer is released

#### Scenario: Releasing makes one edit
- **WHEN** the operator releases the pointer there
- **THEN** the save bar counts one changed card, the live region says so once, the card's editor in the inspector holds 6.0 s in its Length field,
  and Save writes `card.duration: 6.0` for that chapter

#### Scenario: Snapping to a whole second
- **WHEN** the operator moves the edge to 4.96 s's worth of pixels at 40 px per second
- **THEN** the card is 5.0 s, a line shows the second, and the readout says it snapped

#### Scenario: The ends of the range
- **WHEN** the operator drags the edge far left, then far right, of a black card
- **THEN** it stops at 0.5 s, then at 60.0 s, and never takes a value between the pointer and a limit that the engine would refuse

#### Scenario: Escape cancels
- **WHEN** the operator presses Escape during a drag
- **THEN** the card is as it was and the draft is unchanged

#### Scenario: A drag that ends where it began
- **WHEN** the operator drags the edge away and back to 4.0 s and releases
- **THEN** the draft is unchanged and the save bar does not count a change

#### Scenario: A handle press selects the card
- **WHEN** the operator presses a card's end edge in Edit mode
- **THEN** the card is selected, no dialog opens, the inspector shows its Title card tab, and the track has not moved

#### Scenario: Reset and Save are as for any edit
- **WHEN** the operator changes a card's length and presses Reset
- **THEN** the card is back at its saved length, and the save bar shows no change

### Requirement: The playhead scrubs one video

The Timeline SHALL hold exactly one `<video>`, created when the track opens, showing the proxy of the clip the playhead is in, at the playhead's time in that clip. The playhead SHALL be a slider over the whole timeline: it SHALL have the role `slider`, a name ("Playhead"), `aria-valuemin`, `aria-valuemax` and `aria-valuenow` in the timeline's seconds, and a value text that names the clip, the time in it and the time in the whole timeline, each said by its noun ("Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12", the times in the Cuts panel's time format, not padded). Dragging on the ruler SHALL move the playhead; so SHALL dragging on the track body with a mouse or a pen, and so SHALL dragging the playhead's own grip. With touch, the ruler SHALL scrub and a swipe on the track body SHALL scroll it. A press on the ruler SHALL move the playhead there, and so SHALL a press on the track's empty lane. A single press on a clip's block (its body, not its edge tools or handles) SHALL select the clip and SHALL NOT move the playhead; a double press on it SHALL place the playhead there ("A clip is selected on the track or in the bin"). A press in a black card's span still puts the playhead in the card.

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

#### Scenario: A clip press does not move the playhead
- **WHEN** the playhead is at 5.0 s and the operator presses once on the body of a clip's block elsewhere
- **THEN** the clip is selected and the playhead is still at 5.0 s

#### Scenario: A double press places the playhead
- **WHEN** the operator presses twice on the body of a clip's block
- **THEN** the clip is selected and the playhead is at the press

### Requirement: The Timeline is accessible, fits every width and respects the color scheme

The Timeline SHALL expose its structure to assistive technology: the section is a region named "Timeline"; the chapter band is a list of chapters; each clip is a button named as the page names it (pressed while selected), with its length and the number of its cuts in its description, and its block's other content is not announced a second time; the title cards are buttons named as "A card block is a button with a name in words" says; the playhead is a slider; each cut span inside a clip's block keeps its text alternative ("Cut 2.0 to 4.0 s, black") and is exposed, so the block's picture is hidden from assistive technology but its cuts are not. The state of a clip's proxy, of a cut's reason and of the Play button SHALL never be shown by color alone: it SHALL be words, a pattern or an icon with a name. Text and controls SHALL meet the contrast the rest of the page meets, in the light and in the dark scheme, which SHALL follow the page's scheme choice. Every width from 320 to 1280 px SHALL fit without a horizontal scroll bar on the page. With `prefers-reduced-motion: reduce` the Timeline SHALL not animate: no smooth scrolling, no transitions on the playhead or the zoom, and the progress of a job SHALL change without easing. Touch targets under a coarse pointer SHALL be 44 px.

#### Scenario: The structure reads in order
- **WHEN** a screen reader walks the open Timeline of an event with two chapters and three clips
- **THEN** it finds the region "Timeline", a list of two chapters, three named clip buttons with their lengths, the slider "Playhead", and the Play button

#### Scenario: A cut is told in words
- **WHEN** a clip's cut with the reason black is hatched on the track
- **THEN** its text alternative says the cut's start, end and reason, and the span is also distinguished by its pattern, not by its color

#### Scenario: Dark scheme and reduced motion
- **WHEN** the operator's scheme is dark and the system asks for reduced motion
- **THEN** the Timeline is drawn with the dark tokens, the filmstrip and cuts stay legible, and zooming, scrolling and the playhead move without animation

#### Scenario: Touch
- **WHEN** the page is used on a phone-sized window with a coarse pointer
- **THEN** every Timeline button and the playhead's grip are at least 44 px high, and a swipe on the track scrolls it without moving the playhead

#### Scenario: A clip is a button and its cuts are still told
- **WHEN** a screen reader walks a clip with a cut from 2.0 to 4.0 s
- **THEN** it finds one button with the clip's name, and the image "Cut 0:02 to 0:04" in the block, and the clip's name is not said twice

## REMOVED Requirements

### Requirement: A card is selected from the Timeline or the list, as one selection
**Reason**: The card selection is now part of the workspace's one selection.
**Migration**: "One selection in the workspace" now holds the one-selection rule; "The selection is shown and announced once" holds the pressed state and the once-only announcement; "A card block is a button with a name in words" holds the card block's accessible name and keyboard behaviour.
