## MODIFIED Requirements

### Requirement: A selected title card opens its inspector in Edit mode
Activating a title card in Edit mode, from its block on the Timeline or its row at the head of a chapter (a press, Enter or
Space), SHALL open that card's inspector in a modal dialog, over the page wherever the operator has scrolled to, named "Title card
for <chapter>" (the opening card: "Opening title card"). There SHALL be one card editor and one place for it: the inspector SHALL NOT
also be rendered in the page below the Timeline's track. The app's existing dialog component (`ui/Dialog`, the native `<dialog>`
with `showModal()`) SHALL be reused. The dialog SHALL show the card's title, subtitle, background, font, title size, subtitle
size, text colour and position, and a live preview; the preview SHALL sit above the fields where the dialog is 600 CSS pixels
wide or narrower and beside them where it is wider. Opening it SHALL NOT scroll the page, SHALL NOT move the track, the ruler,
the playhead or the Timeline's video, and the page behind it SHALL NOT scroll while it is open. Focus SHALL move to the dialog's first
field when it opens and SHALL return to the row or block that opened it when it closes, unless the operator has already moved it to
a control outside the dialog. Escape and a Close button SHALL close it, as SHALL a "Done" button; none of them SHALL discard an
edit. Edits SHALL go into the page's one draft, as every other Edit-mode change does: the dialog has no Save or Cancel of its
own, and the save bar counts a changed card ("1 title card changed") while the dialog is open and after it is closed. The
card's selection highlight, on its row and on its block, SHALL stay while the dialog is open and after it closes. Activating
a card that is already selected SHALL open the dialog again. At 600 CSS pixels wide or narrower the dialog SHALL be a full-screen
sheet. The inspector SHALL show no field for the card's length and SHALL leave the card's `duration` as the draft holds it. Every
control SHALL have a visible label and an accessible name, work with the keyboard alone, and be at least 44 × 44 CSS pixels where
the primary pointer is coarse. The dialog SHALL fit from 320 to 1280 CSS pixels wide without a horizontal page scroll, follow the
colour scheme, and add no motion when the operator prefers reduced motion. In the read view nothing changes: selecting a card
there opens no dialog and writes nothing.

#### Scenario: Opening from a row far down the page
- **WHEN** the page is scrolled to a chapter far below the Timeline and the operator presses that chapter's title card row
- **THEN** the dialog opens named "Title card for <chapter>" with focus in its first field, the page has not scrolled, and the
  card's row shows as selected

#### Scenario: Selecting a card opens it
- **WHEN** the operator presses the title card block of the chapter `Reception` on the Timeline
- **THEN** the dialog opens named "Title card for Reception", the block and the card's row show as selected, and the keyboard reaches
  every field in reading order

#### Scenario: Editing and finishing
- **WHEN** the operator changes the title, sees the preview update, and presses Done
- **THEN** the dialog is closed, focus is back on the row that opened it, the card's row and the save bar show the change
  ("1 title card changed"), and Save writes `reel.yaml`

#### Scenario: Escape closes and keeps the edit
- **WHEN** the operator has typed a title and presses Escape
- **THEN** the dialog closes, focus returns to the row or block that opened it, the draft holds the edit, and the card stays selected

#### Scenario: Reopening the selected card
- **WHEN** the dialog has been closed and the operator presses the still-selected card again
- **THEN** the dialog opens again with the draft's values

#### Scenario: A narrow window
- **WHEN** the window is 390 CSS pixels wide, and again 320, and a card is open
- **THEN** the dialog is a full-screen sheet with the preview above the fields, nothing scrolls horizontally, and the page behind
  it does not scroll

#### Scenario: Selecting never moves the track
- **WHEN** a card is opened from its block and from its row, at 1280 and 390 px
- **THEN** the track's bounding box is the same before and after each and no inspector is in the page below it

#### Scenario: Switching and closing
- **WHEN** the dialog is open and the operator closes it, then presses another card
- **THEN** the other card's dialog opens, and the draft holds every edit made on both
