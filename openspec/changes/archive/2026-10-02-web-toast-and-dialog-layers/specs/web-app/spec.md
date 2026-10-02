## ADDED Requirements

### Requirement: A full stack of notifications never loses an error to a lesser one

The page SHALL hold at most three notifications. When a fourth arrives:

- if a success or info notification is held, the oldest of those SHALL be removed to make room, whatever the
  tone of the new one;
- if all three held are errors and the new one is an error, the oldest error SHALL be removed;
- if all three held are errors and the new one is a success or info, the new one SHALL NOT be shown, and no
  held error SHALL be removed or change.

A notification that is not shown SHALL leave no trace: nothing is announced, and no later notification is
affected by it.

#### Scenario: Three unread errors and an info notification
- **WHEN** on the event list, three error notifications are shown (three Render presses on
  `2024-07-14 - kalas`, each answered with the output-collision error, or three failed re-reads), and then a
  queued render of another event is canceled, which raises the info notification “Render canceled”
- **THEN** the three errors are still shown, in the same order, the info notification is not shown, and
  nothing is announced for it

#### Scenario: An error replaces the oldest of three errors
- **WHEN** three error notifications are shown and a fourth error arrives
- **THEN** the oldest is removed and the other two and the new one are shown

#### Scenario: A success makes room before an error is touched
- **WHEN** two errors and one success notification are shown and an info notification arrives
- **THEN** the success notification is removed, and both errors and the info notification are shown

### Requirement: A notification raised under a dialog is shown above it

While a modal dialog is open, a notification that is shown SHALL be visible above the dialog and its
backdrop: an error notification SHALL be fully readable there at any window width from 320 CSS pixels up.
It MAY not take focus or clicks until the dialog closes. Opening a dialog while notifications are already
shown SHALL leave them visible above it.

While a modal dialog is open, the clock that dismisses a success or info notification by itself SHALL be
stopped, so that none disappears before the operator can see it. When the last open dialog closes, each such
clock SHALL continue with the time it had left. An error notification stays until it is dismissed, as always.

#### Scenario: A render ends while Render anyway is open
- **WHEN** on `2023-06-23 - Midsommar - Dalarna`, which is up to date, the operator presses Render anyway, and
  while the dialog "Render anyway?" is open a render of `2024-08-20 - Två kapitel - Tjörn` fails
- **THEN** the error notification naming "Två kapitel" is visible above the dialog and its backdrop, in
  windows 1280 and 390 pixels wide, in the light and the dark theme, and still shown after the dialog is
  closed with Escape

#### Scenario: A success notification does not run out under a dialog
- **WHEN** a render of another event ends while the "Render anyway?" dialog is open, which raises the success
  notification “Rendered …”, and the operator waits more than 5 seconds before pressing Cancel
- **THEN** the notification was visible above the dialog throughout, and it is still shown when the dialog
  closes
- **AND** it disappears by itself about 5 seconds after the dialog closed

#### Scenario: A notification already shown when the dialog opens
- **WHEN** an error notification is shown on the event page and the operator then opens the Move clips
  dialog
- **THEN** the error notification is still visible above the dialog

### Requirement: A closing dialog does not take focus from where the operator moved it

Closing a dialog SHALL return keyboard focus to the control that had it when the dialog opened, as long as
that control is still in the page and focus is still the dialog's: inside it, or on no control. When focus has
meanwhile moved to a control outside the dialog, closing the dialog SHALL leave it there.

#### Scenario: Escape returns focus to the opener
- **WHEN** the operator opens "Render anyway?" with the keyboard from the Render anyway button and presses
  Escape
- **THEN** the dialog is closed and keyboard focus is on Render anyway

#### Scenario: Cancel returns focus to the opener
- **WHEN** the operator opens "Render anyway?" with the keyboard and presses Cancel
- **THEN** the dialog is closed and keyboard focus is on Render anyway

#### Scenario: Focus moved before the dialog finished closing
- **WHEN** the operator closes the dialog with Escape and, in the same task as the dialog's close event (as
  a script listening to that event does), keyboard focus is moved to another control outside the dialog, such
  as Save
- **THEN** keyboard focus stays on that control and is not moved back to the control that opened the dialog

## MODIFIED Requirements

### Requirement: Notifications never cover the save bar

While the event page's save bar is shown, no notification SHALL overlap it, at any scroll position and at any
window width:

- While the bar is held at the bottom of the window, notifications SHALL sit above it.
- When the page is scrolled far enough that the bar rests in the page below the content, notifications SHALL
  sit either above the bar or in the room below it.

While the bar moves from the bottom of the window to its resting place, notifications that sit above it MAY
move with it. While the bar is held whenever the page is not scrolled to its resting place (see "Edit mode's
save bar rests in the page when it would hide the editor"), and while no save bar is shown, a control that
receives keyboard focus SHALL NOT be left under a notification at any scroll position, including while the bar
moves, while one notification is shown, or two in a window at least 844 pixels tall. While the bar rests in the
page because, held, it would hide the editor, the same SHALL hold for the controls just above the bar, such as
the last clip row's: while notifications sit above a resting bar, the page SHALL keep as much room between the
last chapter and the bar as the notifications take, so that they cover that room and no control. The room SHALL
follow the notifications as they come and go, and the bar and the notifications SHALL follow any change of the
page above the bar that moves the bar, such as content that grows or shrinks, without a scroll or a resize.
The room SHALL NOT be kept while the notifications sit below the bar or no notification is shown.

When a page is scrolled to its end, no notification SHALL cover any of the page's controls, with or without a
save bar. With no save bar shown, notifications keep their place at the bottom of the window.

#### Scenario: A notification above the held save bar
- **WHEN** an error notification is shown, and the operator, in Edit mode on
  `2024-06-27 - Grillning med grannar` with the page scrolled to its top, changes the title, in windows 1280
  and 390 pixels wide
- **THEN** the notification sits above the save bar, and covers neither Reset nor Save

#### Scenario: The end of the page
- **WHEN** in the same state, the operator scrolls step by step to the end of the page, or presses Tab until
  Save has focus
- **THEN** at no step does a notification overlap the save bar, and at the end Save is fully visible and
  can be clicked, and no control of the page is covered by a notification

#### Scenario: Tabbing through the last clips with two notifications
- **WHEN** two error notifications are shown, and the operator, in Edit mode on
  `2024-06-27 - Grillning med grannar` in a window 390 × 844 pixels, changes the title and then presses Tab
  from Title through every clip row's controls to Save
- **THEN** no notification covers any part of the control that has focus, at any step, and none overlaps the
  save bar

#### Scenario: A short page with a save bar
- **WHEN** an error notification is shown and the operator changes the title in the metadata form of
  `2024-02-30 - Omöjligt datum`, in windows 390 and 320 pixels wide
- **THEN** at no scroll position does a notification overlap the save bar, and Save can be clicked

#### Scenario: Tabbing to the last clip above a resting bar
- **WHEN** in a window 320 × 568, and again in a window 320 × 256, an error notification is shown, and the
  operator, in Edit mode on `2024-09-01 - Sommarlov`, moves its first clip down with the keyboard, saves, the
  save is answered with a conflict (the save bar now rests after the last chapter), and the operator presses
  Shift+Tab from Save through every control of the bar and every clip row's controls
- **THEN** every control that receives focus is fully visible and no part of it is covered by the
  notification, and at no step does the notification overlap the save bar

#### Scenario: The room follows the notification
- **WHEN** in the same state, with the page scrolled a little short of its end so that the notification sits
  above the bar, the operator dismisses it and scrolls to the end of the page
- **THEN** the room between the last chapter and the save bar is gone, and Save is fully visible and can be
  clicked
- **WHEN** a second error notification then arrives
- **THEN** the last clip row's controls are not covered, and, scrolled a little short of the end again so that
  the notification sits above the bar, the room is back

#### Scenario: Content above the bar changes without a scroll or a resize
- **WHEN** an error notification is shown above a resting save bar, and a change in the page above the bar
  (a chapter being added before it, or a clip list growing by one row) moves the bar down the page without
  the window being scrolled or resized
- **THEN** the notification is still directly above the bar, does not overlap it, and covers no control
