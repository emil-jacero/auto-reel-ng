## ADDED Requirements

### Requirement: The opening card's subtitle shows its default and can be set to none
The inspector's Subtitle field for the opening card SHALL, while the draft's subtitle is unset, show the resolved
card's `default_subtitle` as its placeholder with the words "Default" (lines joined by " / ", for example
`Default: 2024-08-20 / Plats: Tjörn`), and when that is empty `No subtitle`. The page SHALL NOT compose the default. The
field SHALL offer **No subtitle**, which sets the subtitle to the empty string, and **Use default**, which unsets it
(the key is removed on Save); the field SHALL keep the empty string and unset apart in the draft, in the dirty state
and in what Save and the preview send, so an explicit `""` is written as `""` and an unset subtitle is not written. A
subtitle typed into the field SHALL replace the default. For a chapter other than the opening one the field keeps its
"Event style: no subtitle" behaviour and offers neither button, since it has no default. The chapter list's card
rows and the Timeline's card readout SHALL show the effective subtitle (`card.subtitle` of the detail, or the draft's
value when edited) and "No subtitle" only when it is empty. This requirement takes precedence over the sentence "The
subtitle SHALL be free text of any length that keeps its line breaks" only in adding the default; that sentence still holds.

#### Scenario: The default is the placeholder
- **WHEN** the opening card is selected for an event dated 2024-08-20 at `Tjörn` with no subtitle key
- **THEN** the Subtitle field is empty with the placeholder `Default: 2024-08-20 / Plats: Tjörn`, and **Use default** is not offered

#### Scenario: No subtitle writes the empty string
- **WHEN** the operator presses **No subtitle** and Saves
- **THEN** the request carries `subtitle: ""` for the default chapter, the field shows the placeholder `No subtitle` with **Use default** offered, and the row says "No subtitle"

#### Scenario: Use default removes the key
- **WHEN** the card's saved subtitle is `""` and the operator presses **Use default** and Saves
- **THEN** the request carries no subtitle for that card, and the row shows the date and place again

#### Scenario: Typing replaces the default
- **WHEN** the operator types `Hos mormor`
- **THEN** the preview and the row show `Hos mormor` and no date or place

#### Scenario: A chapter card has no default controls
- **WHEN** a chapter other than the opening one is selected
- **THEN** the Subtitle field shows its existing placeholder and neither **No subtitle** nor **Use default** is offered

#### Scenario: The preview sends the empty string
- **WHEN** the draft's subtitle is `""`
- **THEN** the preview request carries `subtitle: ""`, and the image has no subtitle line
