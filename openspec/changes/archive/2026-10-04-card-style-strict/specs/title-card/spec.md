## MODIFIED Requirements

### Requirement: Title-card config parsed from `look`

The engine SHALL parse a typed title-card configuration from the resolved `look.title_card` sub-map at render
time, without requiring `reel-document` to validate or model it. The config SHALL cover font family, font
sizes, text color, outline and shadow, background (color and opacity), fade-in/fade-out durations, total card
duration, and text position. Absent fields SHALL take documented defaults. The engine SHALL clamp the combined
fade durations to the total card duration so a card never fades for longer than it is shown. A malformed value
(wrong type/shape) SHALL fail loud with a typed error rather than be silently ignored. The parse SHALL be as
strict for the event-wide style as for a chapter's card: it SHALL refuse a key that is not a field of the
config, and it SHALL refuse a `title_font_size` or `subtitle_font_size` outside the card font-size bounds and a
`duration` outside the card duration bounds (the same constants the chapter card is checked against). Every
refusal SHALL be a typed error naming `look.title_card.<field>`.

#### Scenario: Defaults applied when `look.title_card` is silent
- **WHEN** a title decorator runs and `look.title_card` omits the fade and duration fields
- **THEN** the parsed config uses the documented default durations and the card still renders

#### Scenario: Fades clamped to card duration
- **WHEN** the configured fade-in plus fade-out exceeds the configured card duration
- **THEN** the parsed config reduces the fades so their sum does not exceed the duration

#### Scenario: Malformed config fails loud
- **WHEN** `look.title_card` carries a value of the wrong type for a known field
- **THEN** the engine raises a typed error naming the field rather than rendering with a guessed value

#### Scenario: An unknown key fails loud
- **WHEN** `look.title_card` carries `titel_font_size: 80`
- **THEN** the engine raises a typed error naming `look.title_card.titel_font_size` and the allowed fields, and renders nothing

#### Scenario: An out-of-range size or duration fails loud
- **WHEN** `look.title_card` sets `title_font_size: 4000`, or `subtitle_font_size: 2`, or `duration: 900`
- **THEN** the engine raises a typed error naming that field and its allowed range

#### Scenario: Values at the bounds are accepted
- **WHEN** `look.title_card` sets `duration: 0.5` and `title_font_size: 400`
- **THEN** the config parses with those values

#### Scenario: A refused event-wide style is a 400 over the API
- **WHEN** an editorial write sends `look: {title_card: {duration: 900}}`
- **THEN** the response is 400 naming `look.title_card.duration` and nothing is written, and the detail of an event already holding that value is 200 with `title_card_error` naming the field
