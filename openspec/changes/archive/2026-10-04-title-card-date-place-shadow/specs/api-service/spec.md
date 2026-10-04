## ADDED Requirements

### Requirement: The resolved card reports what it shows by default
Each chapter's resolved `card` in `GET /api/v1/events/{event_id}` SHALL carry `default_subtitle`, a string: what the
card's subtitle is when its `subtitle` key is absent. For the default chapter it is the engine's date-and-place text
(`title-card`, "The opening card's default subtitle is its date and place"), possibly empty; for any other chapter it
is the empty string. The card's `subtitle` SHALL be the effective one: the override when the key is present (an empty
string included), else `default_subtitle`. Both values SHALL be produced by the engine's own resolution, probe-free,
read-only, with no database read; neither the service nor a client composes them. An editorial `card` SHALL
keep an explicit `subtitle: ""` through `PUT` and `GET`, and the preview SHALL treat `""` as no subtitle and `null` or absent as
the default. The published OpenAPI schema SHALL carry `default_subtitle`, and the checked-in generated web types
SHALL match it. This requirement takes precedence over "else empty (a card shows no date or place unless the
author wrote it)" and the scenario "The opening card shows no date or place" of "The event detail reports each
chapter's resolved title card and the event's card style".

#### Scenario: The opening card reports the default
- **WHEN** the detail of an event dated 2024-08-20 with location `Tjörn` and no `subtitle` key is read
- **THEN** the default chapter's `card.subtitle` and `card.default_subtitle` are both `2024-08-20\nPlats: Tjörn`

#### Scenario: An explicit empty subtitle is reported empty, the default still shown
- **WHEN** the default chapter's card sets `subtitle: ""`
- **THEN** its `card.subtitle` is `""` and its `card.default_subtitle` is still `2024-08-20\nPlats: Tjörn`

#### Scenario: A chapter card has no default
- **WHEN** the detail of a chapter other than the default is read
- **THEN** its `card.default_subtitle` is `""`

#### Scenario: Empty is kept, null removes
- **WHEN** `PUT .../reel` writes the default chapter's `card: {subtitle: ""}` and later `card: {}` 
- **THEN** `reel.yaml` holds `subtitle: ""` after the first and no card entry after the second, and a `GET` after each reports it

#### Scenario: The preview follows the rule
- **WHEN** the preview is asked for the opening card with `card: {subtitle: ""}`, then with no subtitle
- **THEN** the first image has the title only and the second has the date and place lines
