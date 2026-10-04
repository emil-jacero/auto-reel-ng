## MODIFIED Requirements

### Requirement: A selected title card opens its inspector in Edit mode
Selecting a title card in Edit mode, from its block on the Timeline or its row at the head of a chapter, SHALL open
that card's inspector below the Timeline's track (after it in the page, whatever the width), named "Title card for <chapter>" (the opening
card: "Opening title card"). The inspector SHALL show the card's title, subtitle, background, font, title size,
subtitle size, text colour and position, and a live preview. Opening it SHALL NOT move the track, the ruler, the playhead or the Timeline's video, and SHALL NOT scroll the page: the
track's position on the page is the same before and after a card is selected. It SHALL NOT be a modal: the chapter list, the Timeline and
the save bar stay usable, selecting another card switches it, and Escape closes it. The inspector SHALL show no field
for the card's length and SHALL leave the card's `duration` as the draft holds it. Every control SHALL have a visible
label and an accessible name, work with the keyboard alone, and be at least 44 × 44 CSS pixels where the primary
pointer is coarse. The inspector SHALL fit from 320 to 1280 CSS pixels wide without a horizontal page scroll, follow
the colour scheme, and add no motion when the operator prefers reduced motion.

#### Scenario: Selecting a card opens it
- **WHEN** the operator selects the title card of the chapter `Reception` on the Timeline
- **THEN** the inspector opens named "Title card for Reception", the card's row in the chapter list shows as selected,
  and the keyboard reaches every field in reading order

#### Scenario: Switching and closing
- **WHEN** the operator selects another card and then presses Escape
- **THEN** the inspector shows the other card, then closes, and the draft holds every edit made on both

#### Scenario: A narrow window
- **WHEN** the window is 320 CSS pixels wide and a card is selected
- **THEN** the inspector is below the track, nothing scrolls horizontally, and the preview fits its width

#### Scenario: Selecting never moves the track
- **WHEN** a card is selected from its block, from its row, and by pressing its duration handle, at 1280 and 390 px
- **THEN** the track's bounding box is the same before and after each, and the inspector is below it

### Requirement: A card's fields are overrides that follow the event style until set
Each of the inspector's fields SHALL be a per-card override. An unset field SHALL show the value it inherits as a
muted placeholder with the words "Event style" (the engine-resolved value the event detail reports), and a set field
SHALL offer **Use event style**, which clears it so the card inherits again. The title field SHALL, while empty, show
as its placeholder the chapter's current name in the draft, and for the opening card the event's current title in the
draft (the title read from the folder name when the draft's is blank), and SHALL say "Follows the chapter name"
(opening card: "Follows the event title"). Typing a title SHALL NOT change the chapter's name, the movie's chapter list
or the event's title. The subtitle SHALL be free text of any length that keeps its line breaks. The background SHALL be
a choice of Black or Video, with the words "Black: text on black, before the chapter" and "Video: text over the start of the
chapter's first clip" under them. The font SHALL be chosen from the service's font list (`GET /api/v1/fonts`) by its
display name, the default marked, and SHALL name no family the list does not hold (beside the families, one entry "Event style" clears the override). Title size and subtitle size SHALL be
numbers, the text colour a colour input with its hex value, the position a choice of Top, Center and Bottom. The page
SHALL apply none of the engine's value rules itself: it sends what was typed and shows the service's refusal. When the
event detail could not resolve a card (`card: null`), the inspector SHALL show the reported `card_error`, SHALL show
inherited values as unknown, and SHALL still let the operator set fields. The page SHALL NOT show a default of its own
for a value the service did not report.

#### Scenario: The background helper copy
- **WHEN** the inspector is open
- **THEN** the Background control's words are "Black: text on black, before the chapter" and "Video: text over the start of the chapter's first clip"

#### Scenario: Empty title follows the chapter name
- **WHEN** the chapter `Dag 2` has no title override and the operator renames it to `Dag två` in the draft
- **THEN** its inspector's title field is empty with the placeholder `Dag två` and "Follows the chapter name"

#### Scenario: A card title does not rename the chapter
- **WHEN** the operator types `Mottagningen` into the title of the chapter `Reception`'s card
- **THEN** the chapter is still `Reception` in the chapter list, in the Timeline's chapter band and in announcements,
  and the card's block shows `Mottagningen`

#### Scenario: Use event style clears an override
- **WHEN** the operator sets the text colour of a card and presses **Use event style** beside it
- **THEN** the colour input shows the inherited value muted with "Event style", and the draft holds no colour for the card

#### Scenario: The opening card is separate from the event title
- **WHEN** the operator types `Sommaren` into the opening card's title
- **THEN** the metadata form's Title field is unchanged, and clearing the opening card's title makes it follow the
  event's title again

#### Scenario: An unresolvable card is said so
- **WHEN** the detail reports `card_error: "look.title_card.position: …"` for a chapter
- **THEN** the inspector shows that message, its inherited values read "unknown", no default is shown in their place,
  and the operator can still set the position

#### Scenario: Fonts come from the list
- **WHEN** the inspector opens and the font list has nine entries
- **THEN** the font control offers those nine by display name, the default marked, and no other family (plus the "Event style" entry)

## ADDED Requirements

### Requirement: Edit mode switches the event's title cards On or Off

Edit mode SHALL offer, once for the event, a control named "Title cards" with the choices On and Off, showing the
state a render would have: the draft's choice, else the event detail's `title_cards.enabled`, with the words that say
where that came from ("Default", "Set in this event", "Set by the project's config.yaml"). Choosing Off SHALL make
the draft's `look.decorators` the event's own list without `title`, keeping the other names and their order, and the
empty list when the event has none; choosing On SHALL make it a list with `title` first and the other names kept. The
choice SHALL be an edit of the same draft as every other: counted in the save bar ("Title cards turned off", "Title
cards turned on"), undone by Undo and Reset, and no change when put back to the state read. A save SHALL write the
document as read with only `look.decorators` (and `look.title_card`, by its own rule) changed and every other key of
`look` as read, and SHALL NOT remove the key unless the draft is back to the state read. Turning cards Off SHALL
keep every card's edits in the draft. When the source is `project`, the control SHALL say that saving writes this
event's own list over the project's. When `title_cards` is null (`look.decorators` is not a list), the control SHALL
be disabled and show the service's `title_cards_error`. The control SHALL be disabled with the other edit controls while
a save is in flight, operable by keyboard, labelled, at least 44 by 44 CSS pixels where the primary pointer is coarse,
legible in both colour schemes from 320 to 1280 px wide without horizontal scroll, and SHALL make the Timeline, the card
rows and the movie's length follow the choice before any save.

#### Scenario: Turning cards off
- **WHEN** on an event with no `look.decorators` the operator chooses Off and saves
- **THEN** one `PUT` under `If-Match` writes `look.decorators: []` and nothing else changes, and the next read says `title_cards: {enabled: false, source: "event"}`

#### Scenario: Other decorators are kept
- **WHEN** the event's `look.decorators` is `[chapter, title]`, the operator chooses Off, and saves
- **THEN** the written list is `[chapter]`

#### Scenario: Back to the state read is no change
- **WHEN** the operator chooses Off and then On on an event that read `source: "default"`
- **THEN** the save bar shows no change and `look` goes back exactly as read

#### Scenario: Turning cards back on
- **WHEN** the event read `look.decorators: []`, the operator chooses On and saves
- **THEN** the written list is `[title]`

#### Scenario: Card edits survive Off
- **WHEN** the operator changes a card's subtitle, chooses Off, and then On
- **THEN** the subtitle edit is still in the draft

#### Scenario: A list that is not a list
- **WHEN** the detail has `title_cards: null` and `title_cards_error` naming `look.decorators`
- **THEN** the control is disabled and shows that text

### Requirement: A choice that follows an inherited value shows it pressed in a muted style

Every segmented choice of the card inspector (Background, Position) and of "Card style for this event" (Default
background, Position) that has no value of its own SHALL show the value it inherits as pressed, in a muted style
distinct from a chosen value and not by colour alone (a dashed outline), with the words "(event style)" for a
card's field and "(project default)" for the event style's, and SHALL expose it to assistive technology as the
inherited value, not as chosen. Pressing the inherited option SHALL set the field to that value as an override;
**Use event style** SHALL return it to the muted state. While the inherited value is unknown (`card: null`, or a
saved value the operator cleared) no option SHALL be shown pressed and the words SHALL say it is unknown.

#### Scenario: A card that follows the event style
- **WHEN** the event style's background is Video and a card sets none
- **THEN** Video is shown pressed in the muted style with "(event style)", Black is not, and the draft holds no background for the card

#### Scenario: Pressing the inherited option
- **WHEN** the operator presses the muted Video
- **THEN** the card sets Video as its own override (it is listed among its overrides) and the style is the chosen look

#### Scenario: The event style's own control
- **WHEN** the event's `look.title_card` sets no position and the project default is Center
- **THEN** the panel's Position shows Center muted with "(project default)"

#### Scenario: Unknown inherited value
- **WHEN** the operator cleared a saved size and the background of a card with `card: null`
- **THEN** no option is shown pressed and the words say the inherited value is unknown
