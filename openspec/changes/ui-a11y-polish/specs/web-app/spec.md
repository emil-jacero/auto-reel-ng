## ADDED Requirements

### Requirement: The screens announce each change once

A notification (a toast) SHALL be announced once, when it appears: an error assertively, and any other
notification politely. Adding a notification SHALL NOT announce again any notification still shown, and
removing one SHALL NOT be announced.

A warning that is part of a page's content, as opposed to a failure that replaces the content, SHALL NOT be
announced as an alert. The event page's warning that `reel.yaml` lists clips that are not on disk is one such
warning. Opening the page or reading it again SHALL NOT announce the warning. It is read where it stands in
the page, and the page's render status, which is announced when it changes, already states the missing clip.

#### Scenario: A second notification is announced alone
- **WHEN** on the dev library's event list, the operator presses the Render of the `2024-07-14 - kalas` row
  twice, and each time the service answers that the movie file is shared with `2024-07-14 - Kalas`
- **THEN** two error notifications are shown, and the second answer is announced by the second notification
  alone, not by both notifications again

#### Scenario: The missing-clip warning is not re-announced
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, whose `reel.yaml` lists `borttagen.mp4`, and then
  presses Refresh
- **THEN** the page shows the warning that `reel.yaml` lists clips that are not on disk, naming
  `borttagen.mp4`, and neither opening the page nor the refresh announces the warning as an alert

### Requirement: Dismissing a notification keeps keyboard focus

Every notification SHALL offer a dismiss control that is reachable with the keyboard. The control SHALL be
named "Dismiss" and SHALL be described to assistive technology by the notification's message.

When a notification is dismissed while focus is within the notifications, focus SHALL move to the next target
in this order:

1. the dismiss control of the next notification shown
2. the dismiss control of the previous notification shown
3. the control that had focus before focus moved into the notifications, when it is still shown
4. the page's level-one heading

The same order SHALL apply when a notification that holds focus is removed because a newer notification took
its place. In either case, focus SHALL NOT fall to the document body, and moving it SHALL NOT scroll the page.
A dismissal made while focus is outside the notifications, for example a pointer click in a browser that does
not focus buttons on click, SHALL NOT move focus.

#### Scenario: Dismissing moves to the next notification, then back
- **WHEN** two error notifications are shown on the event list, and the operator moves focus into them with
  Tab and presses Enter on the first notification's Dismiss
- **THEN** that notification is gone, and focus is on the remaining notification's Dismiss, described by its
  message
- **WHEN** the operator presses Enter again
- **THEN** no notification is shown, and focus is back on the control that had focus just before focus moved
  into the notifications, not on the document body

#### Scenario: With no earlier control, focus goes to the heading
- **WHEN** focus reached the only notification's Dismiss without passing through another control of the page,
  and the operator presses Enter
- **THEN** focus is on the list's level-one heading "Events"

#### Scenario: A displaced notification hands focus on
- **WHEN** three error notifications are shown, keyboard focus is on the oldest notification's Dismiss, and a
  fourth notification arrives
- **THEN** the oldest notification is removed, and focus is on the Dismiss of a notification still shown,
  not on the document body

#### Scenario: A pointer dismissal leaves the page where it is
- **WHEN** one error notification is shown on the dev library's event list in a window 390 pixels wide, the
  operator focuses the list's Refresh, scrolls halfway down the list so that Refresh is out of view, and
  clicks the notification's Dismiss with the mouse
- **THEN** the notification is gone, the page has not scrolled, and focus is on Refresh, not on the document
  body

### Requirement: Notifications never cover the save bar

While the event page's save bar is shown, no notification SHALL overlap it, at any scroll position and at any
window width:

- While the bar is held at the bottom of the window, notifications SHALL sit above it.
- When the page is scrolled far enough that the bar rests in the page below the content, notifications SHALL
  sit either above the bar or in the room below it.

While the bar moves from the bottom of the window to its resting place, notifications that sit above it MAY
move with it. A control that receives keyboard focus SHALL NOT be left under a notification at any scroll
position, including there, while one notification is shown, or two in a window at least 844 pixels tall.

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

### Requirement: A confirmation dialog states its consequence

Every dialog that asks the operator to confirm an action SHALL have a title that asks the question and a
text that states the consequence. The dialog SHALL expose both to assistive technology: the title as the
dialog's name, and the consequence as its description. Opening the dialog therefore SHALL make the question
and its consequence available to assistive technology, although focus moves straight to the choice that
changes nothing.

#### Scenario: Render anyway states that the movie is replaced
- **WHEN** on `2023-06-23 - Midsommar - Dalarna`, which is up to date, the operator presses Render anyway
- **THEN** a dialog named "Render anyway?" opens, described as "The event is up to date. The existing movie
  is replaced when the new render finishes.", with focus on Cancel

#### Scenario: Overwriting states what else is replaced
- **WHEN** after a conflicting save on `2024-06-27 - Grillning med grannar`, the operator chooses
  "Overwrite with mine"
- **THEN** a dialog named "Overwrite the other change?" opens. Its description says that the operator's
  version replaces everything saved since editing started, including changes to chapters the operator did not
  touch, and focus is on Cancel.

## MODIFIED Requirements

### Requirement: Every page shares one header and follows the operator's color scheme

Every page SHALL show the same header. The header SHALL contain:

- the product's mark and name
- a link to the event list, marked as the current page while the list is shown
- a control for choosing the color scheme: System, Light or Dark

The header SHALL stay visible while the page scrolls.

The screens SHALL render in a light and a dark color scheme drawn from one set of design tokens. Tokens SHALL
exist for colors, spacing, radii, type and motion. The screens SHALL follow the operating system's color
preference until the operator chooses Light or Dark. The choice SHALL persist in that browser across reloads
and new tabs, and SHALL apply before the first paint, so a reload never flashes the other scheme. Choosing
System SHALL return to following the operating system.

The color the page declares for the browser's own interface, such as a mobile browser's address bar, SHALL be
the page background of the scheme in effect. That is the chosen scheme when the operator chose Light or Dark,
and the operating system's otherwise. It SHALL be in effect from the first paint, and SHALL follow a new choice
without a reload.

When the browser refuses storage, the screens SHALL follow the operating system and render without error.
The control SHALL still switch the scheme for the current page.

#### Scenario: The operating system's preference is followed by default
- **WHEN** the operator's system prefers dark and no choice was made in this browser
- **THEN** the event list for the dev library renders in the dark scheme, and the control shows System

#### Scenario: A chosen scheme survives a reload
- **WHEN** the operator's system prefers dark, the operator chooses Light on the page of
  `2024-08-20 - Två kapitel - Tjörn`, and then reloads
- **THEN** the page renders in the light scheme from the first paint, and the control shows Light

#### Scenario: System returns to the operating system's preference
- **WHEN** the operator chose Dark earlier and now chooses System on a system that prefers light
- **THEN** the page renders in the light scheme

#### Scenario: The browser's interface color follows the choice
- **WHEN** the operator's system prefers dark, the operator chose Light, and the event list is reloaded
- **THEN** from the first paint the page declares the light scheme's page background as the browser's
  interface color, and choosing Dark then declares the dark scheme's page background, without a reload

#### Scenario: System hands the browser's interface color back
- **WHEN** the operator chose Light earlier and now chooses System on a system that prefers dark
- **THEN** the page declares the dark scheme's page background as the browser's interface color

#### Scenario: Storage is blocked
- **WHEN** the browser throws on every storage access and the operator opens the event list
- **THEN** the list renders in the operating system's scheme with no error shown, and choosing Dark switches
  the current page to the dark scheme

#### Scenario: The header marks where the operator is
- **WHEN** the event list is shown
- **THEN** the header's Events link is marked as the current page, and it is not marked on the page of
  `2024-09-01 - Sommarlov`
