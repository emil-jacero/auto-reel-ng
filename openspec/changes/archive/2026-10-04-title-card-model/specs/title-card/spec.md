## MODIFIED Requirements

### Requirement: Title card rendered to an image at the target resolution

The engine SHALL render a title card to an RGBA image sized to the target spec's resolution, using Cairo +
Pango for text layout (centering, wrapping within a column, kerning/interline) so the heading and the subtitle
are laid out without manual glyph positioning. The card text SHALL come from the chapter's card: the heading is
the card's `title` when it sets one, otherwise the chapter's name for a chapter other than the default, otherwise
the event title for the default chapter; the subtitle is the card's `subtitle` when it is not empty, and
otherwise the card has no subtitle line. A card SHALL NOT show the event's date, location or description. The
heading SHALL be drawn at the card's title font size and the subtitle at its subtitle font size. A card whose
heading would be empty SHALL fail loud with a typed error naming the chapter, rather than be drawn empty. The
renderer SHALL honor the parsed config's outline, shadow, and background settings. The renderer SHALL be a
single reusable entry point so the same image is produced for a render and for a future GUI preview.

#### Scenario: Card image matches the target resolution
- **WHEN** the target spec is 1920×1080 and a title card is rendered
- **THEN** the produced image is a 1920×1080 RGBA image

#### Scenario: Card text composed from event metadata
- **WHEN** the default chapter's card is rendered for an event with a title, a date, a location and a description, and the chapter has no `card`
- **THEN** the card's only text is the event title, with no date, no `Plats:` location and no description

#### Scenario: The opening card carries a free-text subtitle
- **WHEN** the default chapter's `card` sets `subtitle: Hos mormor`
- **THEN** the card has the event title as its heading and `Hos mormor` as its subtitle, drawn at the subtitle font size

#### Scenario: Non-default chapter card uses the chapter name
- **WHEN** a card is rendered for a chapter other than the default whose card sets no `title`
- **THEN** the card's heading is that chapter's name and it has no subtitle

#### Scenario: A card title overrides the heading without renaming the chapter
- **WHEN** a chapter named `Reception` has `card: {title: Mottagningen}`
- **THEN** the card's heading is `Mottagningen`, and the chapter keeps the name `Reception` in the movie's chapter list

#### Scenario: An empty subtitle draws no line
- **WHEN** a card sets `subtitle: ""`
- **THEN** the card has the heading only

#### Scenario: A card with no heading fails loud
- **WHEN** the default chapter's card sets no `title` and the plan has no event title
- **THEN** the engine raises a typed error naming the default chapter instead of drawing an empty card

### Requirement: Title decorator inserts a synthetic title segment

The engine SHALL register a `title` decorator (an inserter) selectable via `look.decorators`. When applied, it
SHALL insert one synthetic title segment for each chapter that resolved a title clip (the clip resolved as
`is_title`), carrying the producer reference, the chapter's own card duration, the chapter's effective card
config (the event-wide style with the chapter's `card` overrides applied) and text, and the chapter membership of
the segment it precedes. The card SHALL be placed immediately before the title clip's
first surviving segment (for a clip with partial cuts, its first kept span). When cuts remove the title clip
entirely, so that it contributes no segment, the card SHALL instead be placed immediately before the first
surviving source segment of the same chapter, so the chapter still opens with its card. When every clip of the
chapter is cut away, so that the chapter has no source segment, no card SHALL be inserted for it. A chapter
that resolved no title clip SHALL get no card. A card whose effective background is `video` SHALL make the engine
fail loud with a typed error naming the chapter before any segment is encoded, because it is not rendered by
this engine; it SHALL NOT be drawn as a black card. When `look.decorators` does not include `title` (or is absent),
no title segment SHALL be produced and behavior SHALL be unchanged.

#### Scenario: Title segment inserted before a chapter's title clip
- **WHEN** the `title` decorator is applied to a plan whose default chapter has a title clip
- **THEN** the segment list contains a synthetic title segment immediately before that chapter's title clip, carrying that chapter's name

#### Scenario: Per-chapter title segments
- **WHEN** the `title` decorator is applied to a plan with two chapters that each have a title clip
- **THEN** a synthetic title segment is inserted before each chapter's title clip

#### Scenario: No title decorator means no card
- **WHEN** `look.decorators` does not include `title`
- **THEN** the segment list contains no synthetic title segment

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

#### Scenario: A video background fails the render loud
- **WHEN** a chapter's card sets `background: video`, or `look.title_card.background` is `video`
- **THEN** the render of that event fails with a typed error naming the chapter and no title segment is drawn as black

## ADDED Requirements

### Requirement: A card's effective style layers the chapter's overrides over `look.title_card`

The engine SHALL compute each card's effective config from three layers, later layers winning key by key: the
documented defaults, the resolved `look.title_card` sub-map (the event-wide style), and the chapter's `card`
overrides (`duration`, `background`, `font_family`, `title_font_size`, `subtitle_font_size`, `text_color`,
`position`). The result SHALL be parsed once, so every rule of the config parser applies to it, and the combined
fades SHALL be clamped to the final duration, not to the duration of an earlier layer. `look.title_card` SHALL
accept a `background` of `black` or `video`, defaulting to `black`, and SHALL fail loud with a typed error naming
the field on any other value. The engine SHALL expose the effective config and text of a chapter's card through
one function of the plan and the chapter, which the title decorator uses, so that a render and any later read of
"what this card will look like" cannot disagree. Computing it SHALL NOT probe media, render an image or touch the
database.

#### Scenario: Defaults, event-wide style and card compose in order
- **WHEN** `look.title_card` sets `title_font_size: 80` and `text_color: "#CCCCCC"`, and a chapter's card sets `text_color: "#FFD700"`
- **THEN** that chapter's effective config has `title_font_size` 80 and `text_color` `#FFD700`, and a chapter without a card has `title_font_size` 80 and `text_color` `#CCCCCC`

#### Scenario: A short card clamps the default fades once
- **WHEN** a chapter's card sets `duration: 1` and no fades are configured anywhere
- **THEN** the effective fade-in and fade-out are 0.5 s each, and their sum does not exceed 1 s

#### Scenario: A longer card is not left with fades shrunk for a shorter event-wide duration
- **WHEN** `look.title_card` sets `duration: 3` and the default 2 s fades, and a chapter's card sets `duration: 10`
- **THEN** that chapter's effective fades are the full 2 s each

#### Scenario: An unknown background value fails loud
- **WHEN** `look.title_card` sets `background: transparent`
- **THEN** the engine raises a typed error naming `look.title_card.background` and the allowed values

#### Scenario: An unregistered or unresolvable font in a card fails that render loud
- **WHEN** a chapter's card sets `font_family` to a family the renderer cannot resolve
- **THEN** the render of that event fails with the typed font-resolution error naming the family, and no card in a substituted face is drawn

#### Scenario: The resolution reads no media
- **WHEN** the effective config and text of a chapter's card are computed for a plan
- **THEN** no ffprobe or ffmpeg process starts and no image is written
