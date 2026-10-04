## ADDED Requirements

### Requirement: Edit mode edits the event's card style in one place

Edit mode SHALL offer, once for the event, a control named "Card style for this event" that edits the event-wide
title-card style, the `look.title_card` of `reel.yaml`. It SHALL offer these fields: font family, title size,
subtitle size, text color, position (center, top or bottom), default length, and default background (Black or
Video). The font family SHALL be chosen from the families the service lists (`GET /api/v1/fonts`), each shown
in its own face or with the service's preview image, never typed. A field the style leaves unset SHALL say that
it follows the project default, with the value in force when the page read it as a placeholder; when the
operator clears a value that the saved style set, the field SHALL say "Project default" without a number,
because the page does not know it, and SHALL NOT show a value it does not have. Every field SHALL be reachable
and operable with the keyboard, and have a label, and a tap area of at least 44 by 44 pixels while the
primary pointer is coarse. The control SHALL be closed until the operator opens it, SHALL NOT shift other
controls when it opens beyond its own height, and SHALL be disabled with Edit mode's other edit controls while
a save is in flight.

While the control is open it SHALL show a preview of the event's opening card drawn by the service from the
draft style (not the saved one), under the same rules as the card inspector's preview: debounced, a stale
request cancelled, the previous image kept while the next loads, and a failure told in words. When the
service cannot resolve the saved event style (the event detail's `title_card_error`), the control SHALL open
showing that error in words and the stored values as typed, so the operator can correct them.

#### Scenario: Setting a font and a colour for every card
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` in Edit mode, the operator opens "Card style for this event",
  picks the font `Playfair Display` and sets the text color `#FFD700`
- **THEN** the preview shows the opening card in that face and color before anything is saved, and the save
  bar says the card style changed

#### Scenario: An unset field follows the project default
- **WHEN** the event's `reel.yaml` sets no `look.title_card` and the operator opens the control
- **THEN** each field shows the project default value as a placeholder and none shows as set

#### Scenario: A cleared value does not invent a default
- **WHEN** the saved style sets a title size of 80 and the operator clears the field
- **THEN** the field says "Project default" with no number, the preview shows the card without the size, and
  the save bar counts the change

#### Scenario: A style the engine refuses is told and correctable
- **WHEN** the event's `look.title_card.position` is hand-written as `middle` and the operator enters Edit mode
- **THEN** the control opens on the service's refusal naming `position`, shows `middle` in the field, and
  choosing `center` clears the refusal

#### Scenario: The control is usable at a narrow width
- **WHEN** the window is 320 pixels wide and the operator opens the control
- **THEN** every field is fully visible without horizontal page scroll

### Requirement: A card says which fields it overrides and falls back to the event style

Each title card in Edit mode, in its row of the chapter list and in the card inspector, SHALL say which of its
fields it overrides: the names of the fields its draft sets ("Overrides font, color"), or "Uses the event
style" when it sets none. A field a card sets equal to the event style SHALL still count as an override. The
inspector's "Use event style" on a field SHALL remove that card's override of it, so the field then follows
the draft event style, not only the saved one, and the inspector's field and the card's preview SHALL show
the result without a save. A card's override of a field SHALL win over the event style, which SHALL win over
the project default.

#### Scenario: A card names its overrides
- **WHEN** the chapter `Kvällen` sets only `font_family` and `text_color` on its card
- **THEN** its row says "Overrides font, color" and the opening card's row says "Uses the event style"

#### Scenario: Use event style follows the draft style
- **WHEN** the event style's text color is edited to `#00FF00` and not saved, and the operator presses "Use event
  style" on the text color of `Kvällen`'s card
- **THEN** the inspector shows `#00FF00` as that card's color and its preview is drawn in it, and the card no
  longer lists color among its overrides

#### Scenario: A card's override beats a changed event style
- **WHEN** `Kvällen`'s card overrides the font and the operator changes the event style's font
- **THEN** `Kvällen`'s preview keeps its own font and every card without that override shows the new one

### Requirement: Saving the card style writes only look.title_card

A change to the event's card style SHALL be an edit of the same draft as every other, counted in the save bar
as "Card style changed", undone by Undo and Reset, and left in the draft by an edit that returns a field to
the value it was read with (no change to save). Saving SHALL write the editorial document as read with only
`look.title_card` changed: a field the operator set takes its value, a field the operator cleared is removed,
the keys of `look.title_card` the control does not edit and every other key of `look` go back as read, and
`look.title_card` is removed when the operator cleared its last field. A save that changes nothing in the
style SHALL send `look` as read. The same save SHALL carry the card overrides of the chapters by the card
inspector's rules. The service's refusal of a field, answered with a problem naming `look.title_card.<field>`,
SHALL be shown at that field and keep the operator's edits, like any failed save. No other control of this
change writes `reel.yaml`, and the page SHALL NOT keep any look editor from an earlier version of the page.

#### Scenario: Only the style changes
- **WHEN** on an event whose `reel.yaml` sets `look.title_card.fade_in: 0.5`, the operator sets the style's
  text color to `#FFFFFF` and saves
- **THEN** `reel.yaml` has `look.title_card` with `fade_in: 0.5` and `text_color: "#FFFFFF"`, and its metadata,
  chapters, per-clip properties and ignored clips are as before

#### Scenario: Clearing the last field removes the sub-map
- **WHEN** `look.title_card` holds only `font_family` and the operator clears it and saves
- **THEN** the saved `reel.yaml` has no `look.title_card`

#### Scenario: A style edited and put back is no change
- **WHEN** the operator changes the title size from 80 to 90 and back to 80
- **THEN** the save bar shows no changes and offers no Save

#### Scenario: The engine's refusal is shown at the field
- **WHEN** the operator enters a title size of `big` and saves, and the service answers 400 naming
  `look.title_card.title_font_size`
- **THEN** the message appears at the title size field, the operator's edits are kept, and `reel.yaml` is
  unchanged
