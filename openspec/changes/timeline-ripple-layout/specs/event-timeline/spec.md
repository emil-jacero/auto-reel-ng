## MODIFIED Requirements

### Requirement: The track lays the clips out by their proxies' lengths, with the chapters and the cuts

With every shown clip ready, the Timeline SHALL show, in one horizontally scrolling track:

- a **ruler** with time labels in the page's time format (`m:ss`, with fractions only when zoomed in far enough that labels would repeat)
- the **clips end to end** in play order (a black title card's span, when the event draws one before a chapter, is between them, see "Each chapter's title card is a block on the Timeline"), each as wide as its **kept extent** at the current zoom (its proxy's duration less a cut span that starts at the clip's beginning and a cut span that runs to its end, see "Edge cuts shorten a clip on the Timeline and the clips after it close up"), with no gap between one clip's block and the next, labelled with its name as the page names it and with the kept extent's length. A proxy has the source's timestamps, so a time in a proxy is the same time in the source clip. A clip's length SHALL come from its proxy's facts, never from the browser's reading of a file and never defaulted; a clip shorter than a pixel at the current zoom SHALL still be drawn, one pixel wide at least, and the playhead SHALL be able to be put in it by keyboard.
- a **chapter band** above the clips: one segment per chapter spanning its shown clips, labelled with the chapter's name, or as the page headings an unnamed chapter ("Main" beside named chapters, "Clips" when none is named). The band's labels stay in view while their chapter scrolls past.
- each clip's **cuts**, as the event page lists them from `reel.yaml` (in Edit mode: as the Cuts panels list them now, the draft's, with the ones marked removed left out), drawn over the clip as spans with a hatch pattern and named by their reason in words ("manual", "black", "white", "freeze") in the span's text alternative; overlapping or touching cuts SHALL be drawn as the render joins them, one span. A joined span that starts at the clip's beginning (a **leading cut**) or runs to the clip's end or within 0.1 s of it (a **trailing cut**; a cut that runs past the proxy's duration is one) SHALL NOT be drawn: the clip's block starts after a leading cut and ends at a trailing cut's start. Only the spans between the two (**interior cuts**) are drawn, hatched, inside the block. In the read view the spans SHALL be read-only: no handle, no drag, no edit. In Edit mode each drawn cut SHALL have the two trim handles of "Edit mode's cuts are trim handles", drawn over the joined span; a leading or trailing cut has none.
- the **movie stat**, one muted line in the Timeline's control row (beside Play and the zoom), not a paragraph of its own: the movie's length (the sum of the shown clips' lengths minus the time the cuts remove, plus the lengths of the black title cards the track draws), then the source length (the sum of the shown clips' full proxy durations, which edge cuts do not shorten, so the time a leading or trailing cut removes is in the cuts term), the time the cuts remove and the cards' time, each named, separated by " · " ("Movie 3:12 · footage 3:45 · cuts −0:33"; with black cards, "Movie 3:20 · footage 3:45 · cuts −0:33 · cards +0:08"). The cuts term SHALL be left out when no cut removes time, and the cards term when no black card adds time. The line SHALL wrap by whole terms, never scroll the page, and be written by the clock ("Running times are written to a fixed width and say what they are")

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
- **THEN** the stat reads "Movie 3:28.00 · footage 3:45.00 · cuts −0:25.00 · cards +0:08.00", and a video card adds nothing to it

#### Scenario: Edge cuts shorten the blocks and close the gap
- **WHEN** an event's clips are A (10.00 s, a cut from 0 to 2.00 s), B (8.00 s, a cut from 6.00 to 8.00 s) and C (5.00 s, a cut from 1.00 to 2.00 s), drawn at 40 px per second with no title card
- **THEN** A's block is 320 px wide from 0, B's 240 px wide from 320 px and C's 200 px wide from 560 px, with no gap between them; no hatched span is drawn on A or B, C shows one hatched span from 600 to 640 px, the blocks are labelled 0:08, 0:06 and 0:05, and the stat reads "Movie 0:18.00 · footage 0:23.00 · cuts −0:05.00"

#### Scenario: A cut past the end is a trailing cut
- **WHEN** a 6.02 s clip lists a cut from 5.0 to 7.0 s
- **THEN** its block is 5.0 s wide, no hatched span is drawn for that cut, and the next clip starts where the block ends

### Requirement: Edit mode's cuts are trim handles

In Edit mode, each cut the Timeline draws on a clip that offers a Cuts panel (an included or new clip on disk whose proxy is ready) SHALL have two **trim handles**, one on its start and one on its end. The handles belong to the cut as the clip's Cuts panel lists it: the cut keeps its place in the list, its number, its reason and its identity while a handle moves, and a cut marked removed has no handle. A handle SHALL be a slider (`role="slider"`, horizontal), reachable by Tab, in the order of time: the clips in play order, and in each clip the cuts by start, a cut's start handle before its end handle, after the playhead. It SHALL be named "Cut <n> start of <name>" or "Cut <n> end of <name>", where <name> is the clip as its row names it and <n> the cut's number in that clip's Cuts panel (the panel's own numbering, removed cuts counted), so no two handles of a clip share a name. It SHALL expose `aria-valuenow` as its time in the clip in seconds, and `aria-valuemin` and `aria-valuemax` as the least and greatest time it can take now, and a value text that gives its time in the Cuts panel's time format followed by the cut's span in words ("0:01.5, the cut runs 0:01.5 to 0:03"). A visible description, referenced by `aria-describedby`, SHALL list the keys of "A trim handle is moved by keyboard".

A handle SHALL take only places the cut can legally take, and its range SHALL always hold the value it has:

- the **start** can go no earlier than the clip's start or the end of the nearest cut before it that it does not overlap, and no later than three frames of the clip before its own end
- the **end** can go no later than the clip's length (the proxy's duration) or the start of the nearest cut after it that it does not overlap, and no earlier than three frames of the clip after its own start
- a cut already shorter than three frames, a cut that runs past the clip's end, and cuts that overlap each other in `reel.yaml` SHALL keep a range that holds their current times; looking at a cut SHALL NOT change it
- the limits are frame times of the clip's own frame rate (taken from the proxy's facts), so that Home and End reach a time the clip can show
- a cut touching another, one's end at the other's start, is a legal place

A leading or trailing cut ("The track lays the clips out") is not drawn and SHALL have no handle; it stays listed and editable in its Cuts panel, and a cut that runs past the clip's end is such a trailing cut. A handle MAY be dragged or stepped to the clip's start or end, or to touch a leading or trailing cut, within its limits: on release the cut becomes part of the leading or trailing cut, its block shortens, its handles are gone and, if it was the selected cut, nothing is selected.

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
- **THEN** the cut runs from 0 to 2.5 s in the draft, the Timeline draws no span and no handle for it, the clip's block starts at 2.5 s of the clip and is 2.5 s shorter, the clips after it start 2.5 s earlier on the track, and no cut is selected

#### Scenario: A clip too narrow to show its cuts
- **WHEN** at the lowest zoom of a 400-clip event a clip is drawn as a block with no cut spans
- **THEN** it has no handle, its cuts are still listed and editable in its Cuts panel, and zooming in until its cuts are drawn gives it its handles

#### Scenario: Overlapping cuts from disk
- **WHEN** a clip lists cuts 2.0 to 4.0 s and 3.5 to 5.0 s
- **THEN** the track draws one joined span with four handles, each with a range that holds its current time, and no range is inverted


### Requirement: Each chapter's title card is a block on the Timeline

The Timeline SHALL show a lane of title cards directly above the clips, from the event detail's resolved cards
(`chapters[].card`) and the detail's `title_cards.enabled` (the draft's Title cards switch while it differs, in Edit mode), with one block per chapter whose card the render draws: a
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
- **THEN** the card is selected (in Edit mode its dialog opens) and the playhead is in the card at the press, showing its image

#### Scenario: A zoomed-out card stays pressable
- **WHEN** a 3.0 s black card is drawn at 4 px per second (12 px wide)
- **THEN** its block is 24 px wide, the clips after it start where they did, and a press on it selects the card

#### Scenario: A block shows its card
- **WHEN** a black card's image has been fetched and the Timeline is in the dark scheme
- **THEN** the block's background is that image, its title is written on a solid strip over it when it fits, its accessible name
  carries the title, and a light ring marks its edge


## ADDED Requirements

### Requirement: Edge cuts shorten a clip on the Timeline and the clips after it close up

The Timeline SHALL show the movie as it will play at a clip's edges: a clip's block spans its kept extent only
("The track lays the clips out"), and every place that maps between the track and a time in a clip SHALL go through
it, the block's left edge being the clip's first kept time (the end of its leading cut, else 0): the ruler, the
playhead and its grip, a scrub or press on the ruler or the track, the filmstrip, the interior cut spans and their
handles, the analysis marks, the title-card blocks, the chapter band, Fit and the windowing. The ruler and the
Event time SHALL count the track's time, in which edge cuts take no time (and black cards do, as before).

A time in a clip SHALL stay the clip's own time: the readout SHALL say the playhead's time in the clip and the
clip's full proxy duration ("Clip 0:05.00 of 0:10.00 · Event 0:03.00 of 0:19.00"), and so SHALL the playhead's value
text, while the block's label says the kept length.

The playhead SHALL never be inside a leading or a trailing cut. The **first kept frame** of a clip is its first
frame at or after its first kept time, and its **last kept frame** its last frame before the start of its trailing
cut (before its end when it has none). A scrub, a press, a key step, Home and End SHALL land on a kept frame: a
frame step across a boundary SHALL land on the next clip's first kept frame or the previous clip's last kept frame,
skipping none, and Home and End on the timeline's first and last kept frame (or the opening black card, as before).
A clip that its cuts cover wholly, or whose kept extent holds no frame, SHALL have no block and no playhead position:
the clips around it meet, and a step passes over it. When the clips or their cuts change under the playhead (an
edit in a Cuts panel, an approved suggestion, a trim, the page reading the event again) so that its time is no longer
kept, the playhead SHALL go to the nearest kept frame of the same clip.

The filmstrip of a clip SHALL start at its first kept time: the tile drawn at a place `x` pixels into the block SHALL
be the sprite's tile for the clip's second `first kept time + x / scale`. An analysis mark SHALL be placed by its
times in the clip through the same map; the part of a mark inside a leading or trailing cut SHALL NOT be drawn, and
a mark wholly inside one SHALL NOT be drawn (its state is cut). Play SHALL start a clip at its first kept frame and
end it at its trailing cut's start, showing no frame of a leading or trailing cut, by the rules of "Play follows the
playhead through the clips, skipping cuts". Use as poster SHALL take the playhead's clip and time as before, so it
takes a kept frame or a frame inside an interior cut.

#### Scenario: A press in a start-trimmed clip
- **WHEN** clip A (10.00 s, 25 fps, a cut from 0 to 2.00 s) is first, followed by B (8.00 s, 25 fps, a cut from
  6.00 to 8.00 s) and C (5.00 s, 25 fps), at 40 px per second with no title card, and the operator presses the track
  at 0 px and then at 120 px
- **THEN** the playhead is at A 2.00 s and the video shows A's frame at 2.00 s, reading "Clip 0:02.00 of 0:10.00 ·
  Event 0:00.00 of 0:19.00", and then at A 5.00 s, reading "Clip 0:05.00 of 0:10.00 · Event 0:03.00 of 0:19.00"

#### Scenario: A press at the end of an end-trimmed clip
- **WHEN** the operator presses the same track at 559 px
- **THEN** the playhead is at B 5.96 s, B's last kept frame, and never at a time of B from 6.00 s on

#### Scenario: Keys cross the edges onto kept frames
- **WHEN** the playhead is at B 5.96 s and the operator presses Right, then Left twice, then Home, then End
- **THEN** it goes to C 0.00 s, back to B 5.96 s, to B 5.92 s, to A 2.00 s and to C 4.96 s

#### Scenario: Play crosses the trimmed edges without showing them
- **WHEN** the operator plays from A 9.00 s
- **THEN** A plays to its end, B plays from 0 to its frame at 5.96 s, C plays from 0, the playhead moves on the track
  without a jump back, and no frame of B from 6.00 s on is shown

#### Scenario: The filmstrip starts at the kept start
- **WHEN** A's sprite has one 96 px tile a second and A is drawn at 40 px per second
- **THEN** the tile at A's block's left edge is the sprite's tile for second 2, and the tile 96 px into the block is
  the one for second 4

#### Scenario: A clip trimmed to a few frames
- **WHEN** a 10.00 s, 25 fps clip has cuts from 0 to 4.00 s and from 4.12 s to 10.00 s
- **THEN** its block is 0.12 s long, and frame steps take the playhead through 4.00, 4.04 and 4.08 s of it and on
  into the next clip

#### Scenario: A clip cut away entirely leaves no trace on the track
- **WHEN** the middle one of three clips has a cut from 0 to its end
- **THEN** it has no block, the third clip starts where the first ends, and Right on the first clip's last kept frame
  lands on the third clip's first kept frame

#### Scenario: A new leading cut moves the playhead
- **WHEN** in Edit mode the playhead is at A 1.00 s of an event whose clip A has no cut, at 40 px per second, and the operator adds a cut
  from 0 to 2.00 s to A in its Cuts panel
- **THEN** A's block is 80 px shorter, the clips after it start 80 px earlier, and the playhead is at A 2.00 s

#### Scenario: A suggestion inside a leading cut
- **WHEN** A has a black-frames suggestion from 0 to 1.50 s and another from 1.00 to 3.00 s, and its leading cut runs from 0 to 2.00 s
- **THEN** the analysis lane draws no mark for the first, and draws the second from A's block's left edge as partly cut

#### Scenario: Fit fits what plays
- **WHEN** the operator presses Fit on the event of A, B and C in a track 950 px wide
- **THEN** the scale is 50 px per second, the 19 s of the track fill it, and C's block ends at 950 px
