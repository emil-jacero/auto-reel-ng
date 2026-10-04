## MODIFIED Requirements

### Requirement: Title card rendered to an image at the target resolution

The engine SHALL render a title card to an RGBA image sized to the target spec's resolution, using Cairo +
Pango for text layout (centering, wrapping within a column, kerning/interline) so the heading and the subtitle
are laid out without manual glyph positioning. The card text SHALL come from the chapter's card: the heading is
the card's `title` when it sets one, otherwise the chapter's name for a chapter other than the default, otherwise
the event title for the default chapter; the subtitle is the card's `subtitle` when it is not empty, and
otherwise the card has no subtitle line, except that the opening card's default applies as the requirement "The
opening card's default subtitle is its date and place" says. A card SHALL NOT show the event's description. The
heading SHALL be drawn at the card's title font size and the subtitle at its subtitle font size. A card whose
heading would be empty SHALL fail loud with a typed error naming the chapter, rather than be drawn empty. The
renderer SHALL honor the parsed config's outline, shadow, and background settings. The renderer SHALL be a
single reusable entry point so the same image is produced for a render and for a future GUI preview.

#### Scenario: Card image matches the target resolution
- **WHEN** the target spec is 1920×1080 and a title card is rendered
- **THEN** the produced image is a 1920×1080 RGBA image

#### Scenario: Card text composed from event metadata
- **WHEN** the default chapter's card is rendered for an event with a title, a date, a location and a description, and the chapter has no `card`
- **THEN** the card's text is the event title, the ISO date and the `Plats:` location, with no description

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
- **THEN** the card has the heading only, on the opening card too

#### Scenario: A card with no heading fails loud
- **WHEN** the default chapter's card sets no `title` and the plan has no event title
- **THEN** the engine raises a typed error naming the default chapter instead of drawing an empty card

## ADDED Requirements

### Requirement: The opening card's default subtitle is its date and place

When the default chapter's card has no `subtitle` key (no card, or a card without it), the card's subtitle SHALL be
the event's resolved date as ISO `YYYY-MM-DD` and, on the next line, `Plats: <location>`, each line only when the
resolved metadata has it. A date that comes from the event folder's name counts as the resolved date. The
description SHALL NOT be part of it. A `subtitle` of any text SHALL replace the default; a `subtitle` that is
the empty string SHALL mean no subtitle and SHALL NOT fall back to the default. A chapter other than the default
SHALL have no default subtitle. The engine SHALL expose the default text as a pure value so that a read of "what
would the card show" and a render cannot differ. This requirement takes precedence over the sentences "Absent or empty
means the card has no subtitle line" (`reel-document`, "A chapter may carry a title card") and "else empty (a card
shows no date or place unless the author wrote it)" (`api-service`) for the default chapter; the key stays optional
and an empty value stays valid.

#### Scenario: Date and place
- **WHEN** the default chapter has no `subtitle` key and the event's date is 2024-08-20 and its location is `Tjörn`
- **THEN** the subtitle is the two lines `2024-08-20` and `Plats: Tjörn`

#### Scenario: Only what is known
- **WHEN** the event has a date and no location, or a location and no date, and no `subtitle` key
- **THEN** the subtitle is the one line that exists; and with neither, the card has no subtitle line and does not fail

#### Scenario: The folder name supplies the date
- **WHEN** `reel.yaml` has no date and the folder is named `2024-08-20 - Midsommar - Tjörn`
- **THEN** the default subtitle is `2024-08-20` over `Plats: Tjörn`

#### Scenario: An explicit subtitle replaces it
- **WHEN** the default chapter sets `subtitle: Hos mormor`
- **THEN** the subtitle is `Hos mormor` alone, with no date or place

#### Scenario: An explicit empty subtitle means none
- **WHEN** the default chapter sets `subtitle: ""` and the event has a date and a location
- **THEN** the card has the heading only

#### Scenario: Chapter cards are unchanged
- **WHEN** a chapter other than the default has no `subtitle` key, in an event with a date and a location
- **THEN** its card has the heading only

#### Scenario: Description is never shown
- **WHEN** the event has a description and no `subtitle` key
- **THEN** the description appears nowhere on the card

### Requirement: A video-background card has a soft shadow under its text

A card whose background is `video` and whose shadow is enabled SHALL be drawn with a soft drop shadow under the
title and the subtitle: the shadow colour at about 60 % alpha, offset down and right by about 0.004 of the image
height, blurred by about 0.006 of the image height, drawn under the outline and the text, in place of the hard
offset shadow. The shadow SHALL stay inside the transparent canvas's rule: pixels away from the text and its shadow
remain fully transparent. The result SHALL be deterministic: the same configuration, content and size SHALL give
the same bytes on every run. A card whose background is `black` SHALL be pixel-identical to what was rendered before
this requirement. A shadow turned off (`shadow_offset` 0 or `shadow_opacity` 0) SHALL draw none. The in-memory and
the file entry points SHALL both draw it, so a preview shows it.

#### Scenario: Text over a bright frame is readable
- **WHEN** a `video` card with white text is composited over a white-to-light-grey frame
- **THEN** the pixels in a band just outside the glyphs are darker than the frame by a stated margin, and the same
  card without the shadow has no such band

#### Scenario: Softer than the old shadow
- **WHEN** a `video` card is rendered at 1920x1080
- **THEN** the shadow's alpha falls off over several pixels (not a hard edge), and its extent is about 0.006 of the height beyond the offset glyphs

#### Scenario: Black card unchanged
- **WHEN** a `black` card is rendered with any content
- **THEN** its bytes equal those the previous release produced for the same input

#### Scenario: Deterministic
- **WHEN** the same `video` card is rendered twice, in two processes
- **THEN** the two PNGs are byte-identical

#### Scenario: Shadow off
- **WHEN** a `video` card has `shadow_opacity` 0
- **THEN** no shadow pixel is drawn

#### Scenario: Preview matches
- **WHEN** the preview endpoint draws a `video` draft and the render draws the same card
- **THEN** the bytes are equal
