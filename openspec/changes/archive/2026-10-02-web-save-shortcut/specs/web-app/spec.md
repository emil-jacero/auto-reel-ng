## ADDED Requirements

### Requirement: Edit mode saves with Ctrl+S or Cmd+S

While Edit mode has read the event's editorial document, pressing **S** with Ctrl (or Cmd on a Mac), without
Shift or Alt, SHALL act as the Save control does, from wherever keyboard focus is on the page, including a
text field, a clip row's control, the header and the page's body. Reaching Save SHALL NOT take a Tab stop
for every control before it.

The key press SHALL NOT open the browser's own "Save page" dialog, whether or not anything is saved. Before
the document has been read, and while its read has failed, the press SHALL be left to the browser. A press
with Shift or Alt, a held key's repeats, and a press during an IME composition SHALL NOT save, and Shift or
Alt SHALL leave the browser's own meaning of the key alone.

When Save is available, the press SHALL send the same write the Save control sends (the same changes, the
same version check), SHALL announce "Saving…", and SHALL show the same outcomes: the "Saved" notification and
the event page when it is written, and the save bar's failure with its choices when it is not. The press
SHALL NOT move keyboard focus. Save is available under the rules of "Saving an edit writes only what the
operator changed" and "Edit mode's save bar stays compact and fits the window": the shortcut SHALL NOT
save in any state where the Save control is held back.

When Save is held back, the press SHALL send nothing and SHALL announce why:

- with nothing to save: "Nothing to save."
- with a date typed in part, or a cut typed and not added: "Not saved:" and what is unfinished
- after a conflict: that Reload latest or Overwrite with mine comes first
- after the event is found gone: that the event no longer exists
- while a clip is lifted by the drag and not yet dropped or cancelled: that the lifted clip comes first
  ("Not saved: drop or cancel the lifted clip first."), because the order shown is not yet the order that
  a write would carry

While a save is in flight, while a Move clips is still being applied, or while a dialog is open (including
the question "Discard unsaved changes?" and the confirmation of Overwrite with mine), the press SHALL send
nothing and say nothing. It SHALL NOT answer a dialog's question.

The Save control SHALL name the shortcut to assistive technology and in its tooltip, and the bar SHALL NOT
show more text for it.

#### Scenario: Saving from the first field
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location in the
  location field and, with keyboard focus still in that field, presses Ctrl+S
- **THEN** exactly one write is sent with the changed location, the live region says "Saving…", the browser's
  Save page dialog does not open, and the event page shows with a "Saved" notification

#### Scenario: Saving after a keyboard reorder without tabbing
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator lifts its first clip by its
  handle from the keyboard, moves it down one place, drops it, and with focus still on that handle presses
  Cmd+S (the meta key)
- **THEN** one write is sent with the new clip order, and no Tab was pressed between the drop and the save

#### Scenario: Nothing has changed
- **WHEN** in Edit mode on `2024-08-02 - Badutflykt - Varberg`, with no edit made, the operator presses Ctrl+S
- **THEN** no request is sent, the live region says "Nothing to save.", and the browser's Save page dialog
  does not open

#### Scenario: A date typed in part
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, clears
  the date's year and presses Ctrl+S
- **THEN** no request is sent, the live region says that the date is incomplete and that nothing was saved,
  and the Save control is still unavailable

#### Scenario: After a conflict the shortcut waits like Save
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, the
  event's `reel.yaml` is changed by hand, the operator saves and the save bar shows the conflict, and then
  the operator presses Ctrl+S
- **THEN** no request is sent, the live region says that Reload latest or Overwrite with mine comes first,
  and the confirmation of Overwrite with mine does not open

#### Scenario: A failed shortcut save keeps the field and the edits
- **WHEN** in Edit mode on `2024-08-02 - Badutflykt - Varberg`, the operator edits the title, presses Ctrl+S
  in the title field, and the request gets no answer
- **THEN** the save bar says that the service is not reachable and offers Retry, the edit is kept, and
  keyboard focus is still in the title field

#### Scenario: A second press during the save does nothing
- **WHEN** the operator presses Ctrl+S, and presses it again, and again as a held key repeats, before the
  service has answered the first
- **THEN** exactly one write is sent, and "Saving…" is announced once

#### Scenario: A dialog's question is not answered
- **WHEN** in Edit mode with unsaved changes, the operator presses Refresh so that "Discard unsaved
  changes?" opens, and presses Ctrl+S
- **THEN** no request is sent, nothing is announced, the dialog stays open with focus on Keep editing, and
  the edits are kept

#### Scenario: A lifted clip is not saved at its old place
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, lifts
  its first clip with Space, moves it down one place with ArrowDown and, before dropping it, presses Ctrl+S
- **THEN** no request is sent, the live region says that the lifted clip must be dropped or cancelled first,
  and the clip is still lifted; after the drop, Ctrl+S sends one write with the location and the new order

#### Scenario: Other chords keep their meaning
- **WHEN** in Edit mode with unsaved changes, the operator presses Ctrl+Shift+S
- **THEN** the page does not save, and does not cancel the browser's own handling of the key

#### Scenario: The shortcut is named
- **WHEN** an unsaved change brings in the save bar
- **THEN** its Save control has the keyboard shortcut Control+S (Meta+S) declared to assistive technology,
  its tooltip reads "Save (Ctrl+S, or ⌘S on a Mac)", and the bar is not taller or wider than before at
  390 × 844
