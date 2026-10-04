## ADDED Requirements

### Requirement: The event detail reports whether title cards are enabled and where that was decided
`GET /api/v1/events/{event_id}` SHALL report `title_cards`, an object with `enabled` (boolean) and `source` (one
of `event`, `project`, `default`). `enabled` is whether the effective decorators of the merged look include
`title`, that is whether a render draws the chapters' cards at all. `source` is `event` when the event's
`reel.yaml` sets `look.decorators`, else `project` when the project `config.yaml` sets it, else `default`, where
the effective decorators are `[title]`. The value SHALL be produced by the engine's own function, the one the
render resolves its decorators with, from the document's `look` and the project's `look` defaults, and not by the
service or the client. It SHALL be probe-free, read-only and add no database read, and it SHALL always be present as a key;
it is an object unless `look.decorators` is not a list, when it is null (see below). It describes what a render would do; like a chapter's `card`, it does not claim that a chapter with no
title clip, or whose clips are all cut away, gets a card. The published OpenAPI schema SHALL carry `title_cards`
with `source` as a closed enumeration, and the checked-in generated web types SHALL match it.

When `look.decorators` holds a value that is not a list, the detail SHALL still answer 200 so the author can open
the event and correct it: `title_cards` is then `null` and a `title_cards_error` names `look.decorators` and the
reason; nothing is guessed in its place. Absence of an error is
`title_cards_error: null`.

#### Scenario: Event null decorators override a project opt-out
- **WHEN** the event `look.decorators` is present but null and the project sets `decorators: []`
- **THEN** the null counts as the event's own (empty) value in the shallow merge, so the cards are on with `source` `default`

#### Scenario: Nothing sets decorators
- **WHEN** neither the event's `reel.yaml` nor the project `config.yaml` sets `look.decorators`
- **THEN** the detail's `title_cards` is `{enabled: true, source: "default"}`

#### Scenario: The event opts out
- **WHEN** the event's `reel.yaml` sets `look.decorators: []`
- **THEN** `title_cards` is `{enabled: false, source: "event"}`

#### Scenario: The project opts out
- **WHEN** the project `config.yaml` sets `look.decorators: []` and the event's `reel.yaml` does not set it
- **THEN** `title_cards` is `{enabled: false, source: "project"}`

#### Scenario: The event overrides the project
- **WHEN** the project `config.yaml` sets `look.decorators: []` and the event's `reel.yaml` sets `[title]`
- **THEN** `title_cards` is `{enabled: true, source: "event"}`

#### Scenario: A list without title is disabled
- **WHEN** the event sets `look.decorators` to a list that does not include `title`
- **THEN** `title_cards.enabled` is `false` and `source` is `event`

#### Scenario: A bad value does not lock the event
- **WHEN** the event's `look.decorators` is the string `title`
- **THEN** the detail is 200, `title_cards` is `null` and `title_cards_error` names `look.decorators`, while the clips, chapters and staleness are reported as usual

#### Scenario: The read is read-only and probe-free
- **WHEN** the detail is read
- **THEN** no file is written under the event, no subprocess is started, and no database read is added

#### Scenario: The schema is published and the types match
- **WHEN** the OpenAPI document is generated
- **THEN** it carries `title_cards` on the event detail with `source` restricted to `event`, `project` and `default`, and the drift test finds `schema.d.ts` unchanged after regeneration
