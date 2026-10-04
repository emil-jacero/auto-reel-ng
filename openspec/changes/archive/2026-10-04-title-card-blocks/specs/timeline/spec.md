## ADDED Requirements

### Requirement: The model places each chapter's card as the render does

The model SHALL compute, for each chapter, whether and where its title card is drawn, from the chapter's shown
clips, their cut spans, the resolved card and whether `look.decorators` includes `title`. A chapter SHALL be
`anchored` when it has a shown clip with footage left after the cuts, the anchor being the chapter's first shown
clip, or the next shown clip with footage when every part of the first is cut; the anchor's start SHALL be the
end of a cut span that begins at zero of the anchor clip, else zero. Otherwise it SHALL be `no-footage`. When the
decorator is not `title`, anchored chapters SHALL be `off`. A card's duration SHALL be taken in whole
milliseconds from seconds, and a value that is not a finite number above zero SHALL be refused with a
`ModelError` naming the card, never replaced. A **video** card's width SHALL be the lesser of its duration and
the anchor's first kept span, and the model SHALL report that it was clamped; a **black** card's width SHALL be
its duration. The model SHALL read no media and use no frame rate.

#### Scenario: Plain chapters
- **WHEN** two chapters each have one 20 s clip without cuts and `look.decorators` is `["title"]`
- **THEN** both are anchored at their first clip with a start of 0

#### Scenario: A wholly cut first clip moves the anchor
- **WHEN** a chapter's first clip is cut from 0 to its end and its second clip is 8 s
- **THEN** the anchor is the second clip

#### Scenario: A leading cut
- **WHEN** the anchor clip has a cut from 0 to 3,000 ms
- **THEN** the anchor's start is 3,000 ms and a video card of 7,000 ms on a first kept span of 3,000 ms is
  3,000 ms wide and clamped

#### Scenario: No footage, and off
- **WHEN** every clip of a chapter is wholly cut, and in another event the decorators are absent
- **THEN** the first chapter is `no-footage`, and the second event's anchored chapters are `off`

#### Scenario: A bad duration is refused
- **WHEN** a card has duration 0, -1 or `NaN`
- **THEN** the model throws a `ModelError` naming the card's duration and places nothing for it

### Requirement: Black cards shift the track by a map that keeps clip time

The model SHALL map a clip time to a track time by adding the lengths of every black card anchored at or before
it, and SHALL map a track time back to a clip time, or to the black card whose span holds it, with no clip time.
A black card at a clip's start SHALL come before the clip's time zero, and video and `off` cards SHALL add
nothing. Positions inside a black card SHALL not map to a clip time. The two maps SHALL be inverses on every
clip time. The movie's length SHALL be the footage less the cut spans plus the black cards' lengths, each once.
Windowing SHALL find the cards in range as it finds clips, without visiting every card.

#### Scenario: Two black cards
- **WHEN** black cards of 3,000 and 4,000 ms anchor at the starts of clips of 20,000 and 20,000 ms
- **THEN** the first clip starts on the track at 3,000 ms, the second at 27,000 ms (20,000 + 3,000 + 4,000), and the total is 47,000 ms

#### Scenario: Inside a card
- **WHEN** a track time of 1,500 ms is mapped back with a 3,000 ms black card first
- **THEN** the result is "in card 0" with no clip time

#### Scenario: Round trip
- **WHEN** every clip time of the 40 s above is mapped to the track and back
- **THEN** each returns itself

#### Scenario: A video card moves nothing
- **WHEN** a video card of 4,000 ms is anchored on the first clip
- **THEN** the track times equal the clip times

#### Scenario: A long event
- **WHEN** 2,000 chapters each have a black card and the view shows a few
- **THEN** the cards in range are found without visiting the rest

### Requirement: The model words a card and holds one card selection

The model SHALL word a card as "Title card for <chapter>, <length>, over video" or "on black" (with "off" when the
decorator is off and "<kept> of <duration>" when clamped), the default chapter being "the opening", with the
length in seconds to one decimal. It SHALL hold the card selection as a pure reducer over `select(chapter)`,
`clear`, `chapters(list)` (ends a selection whose chapter is absent) and `selectCut` (ends a card selection),
returning the same object when nothing changes. The model SHALL import no DOM, React, network or file module and
add no dependency.

#### Scenario: Words
- **WHEN** a 4,000 ms video card on "Dag 2" and the default chapter's 3,000 ms black card are worded
- **THEN** they read "Title card for Dag 2, 4.0 s, over video" and "Title card for the opening, 3.0 s, on black"

#### Scenario: The selection ends with its chapter
- **WHEN** "Dag 2" is selected and the chapter list no longer holds it
- **THEN** the reducer returns no selection, and returns the same state when it still does

#### Scenario: Cut and card exclude each other
- **WHEN** a card is selected and `selectCut` is applied
- **THEN** no card is selected
