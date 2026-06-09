# title-card Specification

## Purpose

Give auto-reel its title cards: parse a typed title-card configuration from the resolved `look.title_card`
sub-map at render time, render an event's title card to an RGBA image at the target resolution via Cairo +
Pango (real typography with fail-loud fontconfig font resolution, outline/shadow/background/fades), and
register a `title` decorator that inserts a synthetic title segment before each chapter's title clip with text
composed from event metadata and the chapter name. The renderer is a single reusable seam so a render and a
future GUI preview produce the same image.

## Requirements

### Requirement: Title-card config parsed from `look`

The engine SHALL parse a typed title-card configuration from the resolved `look.title_card` sub-map at render
time, without requiring `reel-document` to validate or model it. The config SHALL cover font family, font
sizes, text color, outline and shadow, background (color and opacity), fade-in/fade-out durations, total card
duration, and text position. Absent fields SHALL take documented defaults. The engine SHALL clamp the combined
fade durations to the total card duration so a card never fades for longer than it is shown. A malformed value
(wrong type/shape) SHALL fail loud with a typed error rather than be silently ignored.

#### Scenario: Defaults applied when `look.title_card` is silent
- **WHEN** a title decorator runs and `look.title_card` omits the fade and duration fields
- **THEN** the parsed config uses the documented default durations and the card still renders

#### Scenario: Fades clamped to card duration
- **WHEN** the configured fade-in plus fade-out exceeds the configured card duration
- **THEN** the parsed config reduces the fades so their sum does not exceed the duration

#### Scenario: Malformed config fails loud
- **WHEN** `look.title_card` carries a value of the wrong type for a known field
- **THEN** the engine raises a typed error naming the field rather than rendering with a guessed value

### Requirement: Title card rendered to an image at the target resolution

The engine SHALL render a title card to an RGBA image sized to the target spec's resolution, using Cairo +
Pango for text layout (centering, wrapping within a column, kerning/interline) so titles, dates, locations,
and descriptions are laid out without manual glyph positioning. The card text SHALL be composed from the event
`metadata` (title, date, location, description) for the movie's first/default card, and SHALL use the chapter
name as the heading for a non-default chapter's card. The renderer SHALL honor the parsed config's outline,
shadow, and background settings. The renderer SHALL be a single reusable entry point so the same image is
produced for a render and for a future GUI preview.

#### Scenario: Card image matches the target resolution
- **WHEN** the target spec is 1920×1080 and a title card is rendered
- **THEN** the produced image is a 1920×1080 RGBA image

#### Scenario: Card text composed from event metadata
- **WHEN** the default chapter's card is rendered for an event with a title, date, and location
- **THEN** the rendered card contains the event title and the formatted date/location text

#### Scenario: Non-default chapter card uses the chapter name
- **WHEN** a card is rendered for a chapter other than the default
- **THEN** the card's heading is that chapter's name

### Requirement: Fail-loud font resolution

The engine SHALL resolve the configured font family through fontconfig before rendering and SHALL raise a
typed error if the family does not resolve, naming the requested family and the bundled default. It SHALL NOT
allow a silent font substitution to produce a card in an unintended typeface. A bundled default font family
SHALL be available so rendering succeeds without any per-event font configuration.

#### Scenario: Unresolved font family fails loud
- **WHEN** the configured font family is not installed/resolvable on the host
- **THEN** the engine raises a typed error naming the family rather than rendering in a substituted font

#### Scenario: Bundled default renders without configuration
- **WHEN** no font family is configured in `look.title_card`
- **THEN** the card renders using the bundled default font family

### Requirement: Title decorator inserts a synthetic title segment

The engine SHALL register a `title` decorator (an inserter) selectable via `look.decorators`. When applied, it
SHALL insert one synthetic title segment immediately before each chapter's title clip (the clip resolved as
`is_title`), carrying the producer reference, the resolved card duration, the look-derived card config, and the
chapter membership of the clip it precedes. When `look.decorators` does not include `title` (or is absent), no
title segment SHALL be produced and behavior SHALL be unchanged.

#### Scenario: Title segment inserted before a chapter's title clip
- **WHEN** the `title` decorator is applied to a plan whose default chapter has a title clip
- **THEN** the segment list contains a synthetic title segment immediately before that chapter's title clip, carrying that chapter's name

#### Scenario: Per-chapter title segments
- **WHEN** the `title` decorator is applied to a plan with two chapters that each have a title clip
- **THEN** a synthetic title segment is inserted before each chapter's title clip

#### Scenario: No title decorator means no card
- **WHEN** `look.decorators` does not include `title`
- **THEN** the segment list contains no synthetic title segment
