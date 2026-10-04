## ADDED Requirements

### Requirement: A selected title card opens its inspector in Edit mode
Selecting a title card in Edit mode, from its block on the Timeline or its row at the head of a chapter, SHALL open
that card's inspector in the place `title-card-blocks` reserves for it, named "Title card for <chapter>" (the opening
card: "Opening title card"). The inspector SHALL show the card's title, subtitle, background, font, title size,
subtitle size, text colour and position, and a live preview. It SHALL NOT be a modal: the chapter list, the Timeline and
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
- **THEN** the inspector is below the Timeline, nothing scrolls horizontally, and the preview fits its width

### Requirement: A card's fields are overrides that follow the event style until set
Each of the inspector's fields SHALL be a per-card override. An unset field SHALL show the value it inherits as a
muted placeholder with the words "Event style" (the engine-resolved value the event detail reports), and a set field
SHALL offer **Use event style**, which clears it so the card inherits again. The title field SHALL, while empty, show
as its placeholder the chapter's current name in the draft, and for the opening card the event's current title in the
draft (the title read from the folder name when the draft's is blank), and SHALL say "Follows the chapter name"
(opening card: "Follows the event title"). Typing a title SHALL NOT change the chapter's name, the movie's chapter list
or the event's title. The subtitle SHALL be free text of any length that keeps its line breaks. The background SHALL be
a choice of Black or Video, with the words "Text on black, before the chapter" and "Text over the start of the
chapter's first clip" under them. The font SHALL be chosen from the service's font list (`GET /api/v1/fonts`) by its
display name, the default marked, and SHALL name no family the list does not hold (beside the families, one entry "Event style" clears the override). Title size and subtitle size SHALL be
numbers, the text colour a colour input with its hex value, the position a choice of Top, Center and Bottom. The page
SHALL apply none of the engine's value rules itself: it sends what was typed and shows the service's refusal. When the
event detail could not resolve a card (`card: null`), the inspector SHALL show the reported `card_error`, SHALL show
inherited values as unknown, and SHALL still let the operator set fields. The page SHALL NOT show a default of its own
for a value the service did not report.

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

### Requirement: The preview is drawn by the service while the operator edits
The inspector SHALL show a preview of the draft card by posting it to `POST /api/v1/events/{event_id}/title-card/preview`
and showing the PNG the service returns, so that what is previewed is what the renderer draws. The request SHALL carry
the draft: the chapter's name, the non-empty overrides, the draft event title for the opening card, and, for a chapter
other than the opening one with no title override, the draft chapter name as the title, so a renamed or added chapter
previews as it will render. The page SHALL wait for about 250 ms without an edit before sending, SHALL cancel the request
it has superseded, SHALL ignore a response to a request it has superseded, and SHALL keep showing the previous image
(marked as updating) until the new one is ready, never an empty box between two images. For a Black card the image is
shown as is. For a Video card the page SHALL show the returned text over a frame of the clip the card sits over, taken
from the clip's thumbnail, and SHALL say that the frame is from the clip and not its exact start; with no clip that
plays or no thumbnail it SHALL show the text over a neutral pattern and say there is no clip frame. A title over 200 or a
subtitle over 400 characters SHALL not be sent: the field says it is too long to preview, the text is kept, and it still
saves. A failure SHALL be said in words by its cause at the preview, with the previous image kept: the field the service
names (400), the bound (422), the cause (502), that the service is busy and a retry (503, once after `Retry-After`), and
that the service did not answer. The preview SHALL be a labelled image with a text alternative that gives the card's
title and subtitle, and a change of its state SHALL be announced politely, not on every image.

#### Scenario: Editing previews after a pause
- **WHEN** the operator types a subtitle one character at a time faster than 250 ms apart
- **THEN** one request is sent after the last keystroke, carrying the whole subtitle, and the earlier pending
  requests were never sent

#### Scenario: A superseded request is dropped
- **WHEN** a request is in flight and the operator changes the font
- **THEN** the first request is cancelled, its response is never shown, and the image shown is the one for the new font

#### Scenario: The previous image stays while loading
- **WHEN** a request is pending
- **THEN** the previous image is still visible and marked as updating, and when the new image arrives it replaces it

#### Scenario: A video card over a frame of its clip
- **WHEN** the operator sets Video for a chapter whose first clip plays
- **THEN** the preview shows the returned text over that clip's thumbnail frame with the words that the frame is from
  the clip and not its exact start, and no request for a video file is made

#### Scenario: No clip to show it over
- **WHEN** a Video card's chapter has no clip that plays
- **THEN** the text is shown over a neutral pattern with "No clip frame to show it over"

#### Scenario: An over-long text is kept but not previewed
- **WHEN** the operator pastes a 450-character subtitle
- **THEN** no request is sent for it, the subtitle field says it is too long to preview (limit 400), the text stays,
  and the card still saves with it

#### Scenario: A refusal is said at the field
- **WHEN** the service answers 400 naming `card.title_font_size`
- **THEN** the size field shows the service's message, the preview keeps its previous image, and editing the size
  retires the message

#### Scenario: A busy service
- **WHEN** the service answers 503 with `Retry-After: 2`
- **THEN** the preview says the service is busy, retries once after two seconds, and says so in words if that fails too

### Requirement: Title-card edits are edits of the same draft
A change to a card in the inspector SHALL change the editor's draft, the one every other Edit-mode change shares, and
SHALL be saved, counted, guarded and undone as any other edit. There SHALL be no second save path. A card SHALL count
as changed when its overrides differ from the ones read, so an edit set back to its read value counts as nothing.
Pressing Save SHALL send the same whole-document `PUT` under `If-Match` that every edit sends, with a `card` only for
chapters whose card changed (a card left with no override sent as `{}`, which removes it) and no `card` for the others,
so an unchanged card is never rewritten. The save bar SHALL say how many cards changed ("1 title card changed",
"2 title cards changed") beside its other counts. Undo for a card, and Reset, SHALL restore the overrides as read.
Leaving Edit mode with an unsaved card change SHALL ask first, as for any unsaved edit. A card SHALL follow its chapter:
renaming a chapter in the draft SHALL keep its card edits, deleting a chapter SHALL drop them with it, and undoing the
deletion SHALL bring them back. A refusal by the service (400) SHALL show in the save bar's problem list and at the
field of the card it names, and SHALL keep the draft.

#### Scenario: The save bar counts cards
- **WHEN** the operator changes the subtitle of one card and the font of another
- **THEN** the save bar says "2 title cards changed" and enables Save

#### Scenario: Editing back to the read value is no change
- **WHEN** the operator changes a card's position and then sets it back to the one read
- **THEN** the save bar counts no card and, with nothing else changed, Save is unavailable

#### Scenario: Only the changed card is written
- **WHEN** an event with three chapters is saved after the operator changed one card
- **THEN** the write is one `PUT` under `If-Match`, its `chapters` carry a `card` for the one changed chapter and none
  for the other two, and `reel.yaml` afterwards differs only in that card

#### Scenario: Clearing every override removes the card
- **WHEN** the operator presses **Use event style** on every field of a chapter that had a card, and saves
- **THEN** the write carries `card: {}` for it and `reel.yaml` has no card for that chapter

#### Scenario: A rename carries the card
- **WHEN** the operator edits a card's subtitle and renames its chapter, then saves
- **THEN** the persisted renamed chapter holds the new subtitle and the old name no longer exists

#### Scenario: Undo and Reset
- **WHEN** the operator changes a card's font and presses Reset
- **THEN** the card's overrides are as read and the inspector shows the read font

#### Scenario: Leaving with a card changed
- **WHEN** the operator has changed a card and follows a link out of Edit mode
- **THEN** the page asks before leaving, as for any unsaved edit

#### Scenario: A refusal at the field
- **WHEN** the service answers a save with 400 naming `card.font_family` of the chapter `Dag 2`
- **THEN** the problem list names the chapter and the field, the font control of that chapter's inspector shows the
  message, and the draft is kept

#### Scenario: The default is not rewritten
- **WHEN** the operator opens an inspector, changes nothing, and saves another edit
- **THEN** the opened card's chapter has no `card` in the write
