## MODIFIED Requirements

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

The Timeline plays footage only: the playhead SHALL cross a black card's span without time passing, a press in
the span SHALL select the card and SHALL NOT move the playhead, and the lane SHALL say that the Timeline does not
play cards.

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
- **THEN** the card is selected and the playhead stays at 5.0 s

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
drag with the card as it was and no edit. A drag that ends where it began SHALL make no edit. Pressing the handle SHALL also select that card, as pressing its block does (the inspector opens below the track, so
selecting never moves the track out from under the pointer).

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
- **THEN** the card is selected, its inspector opens below the track, and the track has not moved

#### Scenario: Reset and Save are as for any edit
- **WHEN** the operator changes a card's length and presses Reset
- **THEN** the card is back at its saved length, and the save bar shows no change
