## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Each chapter's title card is a block on the Timeline

The Timeline SHALL show a lane of title cards directly above the clips, from the event detail's resolved cards
(`chapters[].card`) and the event's `look.decorators`, with one block per chapter whose card the render draws: a
chapter with a shown clip that has footage left after the cuts, when `look.decorators` includes `title`. The block
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
wholly cut, SHALL have no block. When the event's `reel.yaml` lists `look.decorators` without `title`, every chapter
with footage SHALL have its block drawn in an off look (a dashed outline and the word "not enabled", no time added) and
the lane SHALL say once that the render draws no title cards for the event. When `reel.yaml` has no
`look.decorators` at all, the effective look may still come from the project's `config.yaml`, which the web cannot
read: the blocks SHALL be drawn in the same look, the lane SHALL say that the cards are not enabled in this event's
`reel.yaml` and that a project default may still enable them, and the movie's length SHALL say that title cards are
not counted instead of presenting itself as final. When the event's card style or a chapter's card could not
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
- **WHEN** the event's `reel.yaml` lists `look.decorators: [chapter]`
- **THEN** the blocks are drawn in the off look with no time added, and the lane says the render draws no title cards

#### Scenario: The decorators are not set in reel.yaml
- **WHEN** the event's `reel.yaml` has no `look.decorators`
- **THEN** the blocks are drawn in the off look, the lane says the cards are not enabled in this event's `reel.yaml` and a project default may still enable them, and the movie's length says that title cards are not counted

#### Scenario: A card that cannot be resolved
- **WHEN** the detail has `title_card_error: "look.title_card.font_family"` and every chapter's `card` is null
- **THEN** the lane shows that text in a note and no block, and the clips, cuts and playhead are unaffected

#### Scenario: A press in a black card's span
- **WHEN** the operator presses inside a black card's block with the playhead at 5.0 s of a clip
- **THEN** the card is selected and the playhead stays at 5.0 s

### Requirement: Edit mode's chapter list shows each chapter's card as a row

Edit mode's chapter list SHALL show, at the head of each chapter, a row for that chapter's card from the event
detail's resolved card: its title, its subtitle ("No subtitle" when empty), its duration, "Black" or "Video" and
its font name, in words. The default chapter's row SHALL be the opening card and SHALL keep the press-to-edit
event-title control the main title card has, which edits the draft's title as before. The row SHALL be matched to
its chapter by the chapter's key. A chapter added in the draft has no saved card: its row SHALL say that its card
is drawn after Save, and SHALL NOT be selectable. A chapter whose draft name differs from the saved name SHALL show
the saved card and say the saved name. A card that could not be resolved SHALL say so in words in its row and
SHALL NOT show values. The row SHALL write nothing and request nothing.

#### Scenario: A row for each chapter
- **WHEN** Edit mode opens on an event with the chapters "" and "Dag 2", the latter with a 4.0 s video card in
  "Sofia Sans" titled "Dag två" with subtitle "Stranden"
- **THEN** each chapter's header is followed by its card row, and "Dag 2"'s says "Dag två", "Stranden", "4.0 s",
  "Video" and "Sofia Sans"

#### Scenario: Main's row is the opening card
- **WHEN** the operator opens the default chapter in Edit mode
- **THEN** its row is named for the opening card, shows the event title, and the title control still edits
  `metadata.title` in the draft and follows the metadata form

#### Scenario: A chapter added in the draft
- **WHEN** the operator adds a chapter "Dag 3" and has not saved
- **THEN** its row says its card is drawn after Save and offers no selection

### Requirement: A card is selected from the Timeline or the list, as one selection

The page SHALL hold one card selection, shared by the Timeline's blocks and Edit mode's rows, kept above both so
that a Refresh or leaving Edit mode, which close the Timeline section, do not end it. Pressing a block or a row
SHALL select that card, and the block and the row SHALL both show it selected, in more than colour. At most one
thing SHALL be selected on the Timeline: selecting a card SHALL end the selection of a cut, and selecting a cut
SHALL end the selection of a card. Pressing the selected card again SHALL leave it selected; Escape SHALL clear
it. The selection SHALL end when its chapter is deleted or no longer in the event after a read. A block and a row
SHALL be buttons reached by Tab in document order, pressed by Enter or Space, with `aria-pressed`, named in words
as "Title card for <chapter>, 4.0 s, over video" (or "on black"; the default chapter: "Title card for the opening,
…"; a clamped video card: "…, 3.0 s of 7.0 s, over video"; the off look adds ", not enabled"). A selection SHALL open
nothing but an inspector slot, a labelled region saying "Card editing comes next" with the selected card's words;
it SHALL write nothing, request nothing and be announced once through the polite status region.

#### Scenario: One selection from either place
- **WHEN** the operator presses the block of "Dag 2" on the Timeline in Edit mode
- **THEN** the block is pressed, "Dag 2"'s row is shown selected, and the inspector slot names the card

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
