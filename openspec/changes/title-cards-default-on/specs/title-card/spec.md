## MODIFIED Requirements

### Requirement: Title decorator places each chapter's card

The engine SHALL register a `title` decorator (an inserter) selectable via `look.decorators`. When
`look.decorators` is absent (or null) from the resolved look, that is from both the event's `reel.yaml` and the
project `config.yaml`, the effective decorators SHALL be `[title]`. An explicit list SHALL keep its meaning: `[]`,
`[none]` and any list that does not include `title` SHALL produce no title segment. A non-list value SHALL fail
loud. When applied, the `title` decorator
SHALL insert one synthetic title segment for each chapter that resolved a title clip (the clip resolved as
`is_title`), carrying the producer reference, the chapter's own card duration, the chapter's effective card
config (the event-wide style with the chapter's `card` overrides applied) and text, and the chapter membership of
the segment it precedes. The card SHALL be placed immediately before the title clip's
first surviving segment (for a clip with partial cuts, its first kept span). When cuts remove the title clip
entirely, so that it contributes no segment, the card SHALL instead be placed immediately before the first
surviving source segment of the same chapter, so the chapter still opens with its card. When every clip of the
chapter is cut away, so that the chapter has no source segment, no card SHALL be inserted for it. A chapter
that resolved no title clip SHALL get no card. A card whose effective background is `video` SHALL NOT be inserted as a segment; it SHALL be attached to the
anchor segment instead, and never drawn as a black card (see "A video-background card is attached over the
chapter's first segment"). When the effective decorators do not include `title`,
no title segment SHALL be produced and behavior SHALL be unchanged.

#### Scenario: Title segment inserted before a chapter's title clip
- **WHEN** the `title` decorator is applied to a plan whose default chapter has a title clip
- **THEN** the segment list contains a synthetic title segment immediately before that chapter's title clip, carrying that chapter's name

#### Scenario: Per-chapter title segments
- **WHEN** the `title` decorator is applied to a plan with two chapters that each have a title clip
- **THEN** a synthetic title segment is inserted before each chapter's title clip

#### Scenario: Absent decorators render the cards
- **WHEN** neither the event's `reel.yaml` nor the project `config.yaml` sets `look.decorators`, and the plan has
  a default chapter and one named chapter, each with a title clip
- **THEN** the render's segment list has an opening card and a card for the named chapter, each before its title clip

#### Scenario: No title decorator means no card
- **WHEN** `look.decorators` is an explicit list that does not include `title`
- **THEN** the segment list contains no synthetic title segment

#### Scenario: An explicit empty list means no cards
- **WHEN** the event's `reel.yaml` sets `look.decorators: []`
- **THEN** the segment list contains no synthetic title segment

#### Scenario: The none decorator means no cards
- **WHEN** `look.decorators` is `[none]`
- **THEN** the segment list contains no synthetic title segment

#### Scenario: A list without title means no cards
- **WHEN** `look.decorators` lists another decorator and not `title`
- **THEN** the segment list contains no synthetic title segment

#### Scenario: The project's explicit list wins over the default
- **WHEN** the project `config.yaml` sets `look.decorators: []` and the event's `reel.yaml` does not set it
- **THEN** the segment list contains no synthetic title segment

#### Scenario: The event's list wins over the project's
- **WHEN** the project `config.yaml` sets `look.decorators: []` and the event's `reel.yaml` sets `[title]`
- **THEN** the render draws the cards

#### Scenario: A non-list value fails loud
- **WHEN** `look.decorators` is the string `title`
- **THEN** the render fails with an error naming `look.decorators`

#### Scenario: Previously rendered events become stale once
- **WHEN** an event rendered by the previous engine version, with no decorators, is checked for staleness
- **THEN** it is stale with reason `engine`

#### Scenario: Partially cut title clip keeps its anchor
- **WHEN** the chapter's title clip has a cut span over its first seconds and a kept span after it
- **THEN** the synthetic title segment is placed immediately before that clip's first kept span, exactly as for an uncut clip

#### Scenario: Fully cut title clip moves the card to the next clip
- **WHEN** a chapter is `[a.mp4 (title, 10 s), b.mp4]` and a cut span covers all of `a.mp4`
- **THEN** the chapter's synthetic title segment is placed immediately before `b.mp4`'s first segment, carrying that chapter's name and heading, and the chapter has exactly one card

#### Scenario: Fully cut title clip with later surviving clips in several chapters
- **WHEN** two chapters each have a title clip, the first chapter's title clip is wholly cut, and the second chapter is untouched
- **THEN** the first chapter's card moves to its next surviving segment, the second chapter's card stays before its title clip, and each card still carries its own chapter's name

#### Scenario: Chapter cut away entirely gets no card
- **WHEN** every clip of a chapter, including its title clip, is wholly cut
- **THEN** no synthetic title segment is produced for that chapter and the chapter is absent from the segment list, as it is without the decorator

#### Scenario: Chapter without a title clip gets no card
- **WHEN** no clip of a chapter resolved as the title clip
- **THEN** no synthetic title segment is produced for that chapter, whether or not its clips are cut

#### Scenario: Each chapter's card has its own length
- **WHEN** the default chapter's card sets `duration: 3`, a second chapter's card sets `duration: 10`, and the third chapter has no card
- **THEN** the three synthetic title segments last 3 s, 10 s and the event-wide duration

#### Scenario: A chapter's card overrides apply to that chapter only
- **WHEN** one chapter's card sets `font_family` and `text_color` and another chapter sets nothing
- **THEN** only the first chapter's title segment carries those values in its config

#### Scenario: A video background is attached, not failed
- **WHEN** a chapter's card sets `background: video`, or `look.title_card.background` is `video`
- **THEN** the render succeeds, no title segment is drawn as black for that chapter, and the card is attached over
  the chapter's first segment
