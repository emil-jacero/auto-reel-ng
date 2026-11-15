## ADDED Requirements

### Requirement: Edit mode is a full-window workspace

Pressing Edit SHALL replace the event page with a workspace that fills the window: no app header, no page width
limit. It SHALL have a top bar and four panes: the clip bin (left), the viewer (centre), the inspector (right) and the
Timeline (along the bottom). Done SHALL leave it through the same flow as leaving Edit mode today, unsaved guard
included, and the event page SHALL show again with the app header.

#### Scenario: Edit opens the workspace
- **WHEN** the operator presses Edit on `2024-08-20 - Två kapitel - Tjörn` in a 1440×900 window
- **THEN** the app header is gone, the top bar, bin, viewer, inspector and Timeline are all visible, and the page
  does not scroll

#### Scenario: Done with unsaved edits
- **WHEN** the operator has moved a clip and presses Done
- **THEN** the same unsaved-edits question as today is asked, and choosing to stay keeps the workspace and the draft

### Requirement: The workspace's top bar holds the event and the save controls

The top bar SHALL show a control back to the event list (which leaves Edit mode as Done does), the event's title with
its date and location, the unsaved summary in the save bar's words, Reset, Save and Done, and the theme switch. It
SHALL present one primary action as the save bar does today (Save, Reload latest or Back to the event list), and
Ctrl+S / Cmd+S SHALL save as today.

#### Scenario: The summary follows the draft
- **WHEN** the operator adds a cut and moves a clip
- **THEN** the top bar says "Unsaved" with "1 cut added · 1 clip moved", and Save is the primary action

#### Scenario: A conflict
- **WHEN** a save answers 412
- **THEN** the top bar's primary action is Reload latest, and the explanation opens under the top bar without covering
  the Timeline

### Requirement: The clip bin holds the chapters' clip lists

The bin SHALL list every chapter with its clips in compact rows (thumbnail, name, kept length, status) and SHALL keep
every action the chapter lists have: reorder and move between chapters by pointer and by keyboard, marks and Move
marked to…, Add/rename/delete chapter, and the New, Ignored and Missing clips with their actions.

#### Scenario: Keyboard reorder in the bin
- **WHEN** the operator focuses `s1710002.mp4`'s drag handle, presses Space, ArrowUp, Space
- **THEN** `s1710002.mp4` is first in its chapter, the move is announced, and the Timeline draws it first

#### Scenario: 400 clips
- **WHEN** the event has 400 clips
- **THEN** the bin scrolls on its own, the rest of the workspace does not move, and the drag-smoothness gate holds

### Requirement: The viewer holds the picture and the transport

The viewer SHALL show the Timeline's picture with play, previous clip, next clip, the time readout and Use as poster.

#### Scenario: Next clip
- **WHEN** the playhead is in `s1710002.mp4` and the operator presses Next clip
- **THEN** the playhead moves to the first kept frame of the next drawn clip

### Requirement: The inspector holds the event's fields and the selected cut

The inspector SHALL have an Event tab (Details form, Poster, and a button "All title cards in this event" that
opens the title card dialog on that tab, with whether title cards are on in words) and a Cut tab (the selected
cut's fields and the selected suggestion's decision). The tabs SHALL work by arrow keys. Choosing a cut or a
suggestion on the track SHALL show the Cut tab and leave focus on the track.

#### Scenario: Selecting a cut
- **WHEN** the operator presses a cut's handle on the track
- **THEN** the inspector shows the Cut tab with that cut's start and end fields

#### Scenario: The card style and the switch stay in the dialog
- **WHEN** title cards are on and the operator presses "All title cards in this event" in the Event tab
- **THEN** the Event tab said "Title cards are on for this event", and the dialog opens on its "All title cards in
  this event" tab, which holds the card style and the Title cards switch

### Requirement: The workspace follows the theme and fits narrower windows

The workspace SHALL follow the operator's light or dark theme and its switch SHALL change the same setting as the app
header's. At 1280×720 the page SHALL NOT scroll; the panes scroll within themselves. Below 960 CSS pixels wide the
panes SHALL stack in one column (viewer, Timeline, inspector, bin) with no horizontal page scroll.

#### Scenario: Theme switch
- **WHEN** the operator switches to light in the top bar and leaves Edit mode
- **THEN** the event page is light, and `auto-reel:theme` holds `light`

#### Scenario: Phone width
- **WHEN** the window is 390 CSS pixels wide
- **THEN** the panes are stacked, every control is reachable, and the page does not scroll sideways

### Requirement: The bin's chapter headings and lists say what they hold

A chapter's heading SHALL stay one line within the bin, naming the chapter and saying how many clips moved and how
many clips it plays. The lists of removed and of ignored clips SHALL each say how many clips they hold. No state of
the bin SHALL make it scroll sideways.

#### Scenario: A chapter with a removal and a move
- **WHEN** in Edit mode on `2024-09-01 - Sommarlov`, the operator removes `borttagen.mp4` and moves `s1710004.mp4` up
- **THEN** the chapter's heading is one line that reads "Clips", "1 clip moved" and "2 clips", and the list below
  says "1 clip removed from reel.yaml when you save"

### Requirement: An empty field in the inspector can be seen

In both color schemes, each Details field's edge SHALL have a contrast of at least 3:1 against the inspector around
it, so that an empty field is visible.

#### Scenario: Empty fields are visible in both schemes
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in the light and in the dark scheme
- **THEN** the edges of the empty Location and Description fields measure at least 3:1 against the inspector

### Requirement: Notifications never cover the workspace's top bar or a focused control

In the workspace, notifications SHALL sit at the top of the viewer pane, under the top bar, over the picture, and
SHALL NOT overlap the top bar, the transport, the bin, the inspector or the Timeline. Where the panes are stacked,
and outside Edit mode, notifications SHALL sit at the bottom of the window, and a control that receives keyboard
focus SHALL NOT be left under one at any scroll position.

#### Scenario: A notification in the workspace
- **WHEN** an error notification is shown and the operator, in Edit mode on `2024-06-27 - Grillning med grannar`
  in a window 1280 × 720, changes the title
- **THEN** the notification sits over the top of the picture and covers neither Reset, Save nor Done, nor any
  control of the bin, the inspector or the Timeline

#### Scenario: Tabbing with two notifications at phone width
- **WHEN** two error notifications are shown and the operator, in Edit mode in a window 390 × 844, presses Tab
  through every control of the workspace
- **THEN** no notification covers any part of the control that has focus, at any step

## MODIFIED Requirements

### Requirement: Every page shares one header and follows the operator's color scheme

Every page SHALL show the same header, except Edit mode's workspace, which hides it and shows its own top bar
("Edit mode is a full-window workspace"); the top bar holds the same color-scheme control. The header SHALL contain:

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

#### Scenario: The workspace hides the header and keeps the control
- **WHEN** the operator presses Edit on `2024-09-01 - Sommarlov`
- **THEN** the header is not shown, and the workspace's top bar offers System, Light and Dark

### Requirement: Edit mode's save bar stays compact and fits the window

Edit mode's save controls SHALL be in the workspace's top bar ("The workspace's top bar holds the event and the
save controls"), and the top bar SHALL fit the window at every width from 320 CSS pixels up. Nothing the top bar
shows SHALL make the page scroll horizontally, including a failed save's explanation and its choices, and every
word of it SHALL stay inside the window.

The top bar SHALL present exactly one primary action at a time: the way on from its current state.

- **Reload latest** while a conflict holds Save back
- **Back to the event list** when the event no longer exists
- **Save** in every other state

Every other control in the top bar SHALL be presented as secondary. A control that the state holds back SHALL
stay in its place, SHALL say that it is unavailable, and SHALL keep keyboard focus when it has it. Save
after a conflict, or after the event is found gone, is one such control.

A conflict's, a vanished event's and a failed save's explanation SHALL open as a panel directly under the top bar,
never over the Timeline, and SHALL take at most two fifths of the window's height, scrolling within itself when it
needs more. A failure to save SHALL show the service's detail in full.

The top bar SHALL NOT show the browser's own error text. When a save gets no answer at all, it SHALL say
that the service is not reachable and offer Retry, without the text the browser gave for the failed request.
An error in the page itself SHALL be shown as a failed save with Retry, and SHALL NOT be reported as an
unreachable service.

#### Scenario: A conflict at phone width
- **WHEN** in a window 390 × 844, the operator is editing the location of
  `2024-06-27 - Grillning med grannar`, its `reel.yaml` title is changed by hand, and the operator saves
- **THEN** the panel under the top bar says that the event changed since it was read and offers "Reload latest"
  and "Overwrite with mine", with "Reload latest" as the one primary action. Save is held back, presented as
  secondary, and still has keyboard focus. The panel takes at most two fifths of the window's height, and the
  page does not scroll horizontally.

#### Scenario: A conflict in the narrowest window
- **WHEN** the same conflict is answered in a window 320 pixels wide
- **THEN** the page does not scroll horizontally, and the alert's title, both choices and the note that the
  edits are kept are all inside the window

#### Scenario: No answer at phone width
- **WHEN** in a window 390 × 844, the operator saves a reorder of `2024-08-02 - Badutflykt - Varberg` and the
  request gets no answer
- **THEN** the top bar says that the service is not reachable, offers Retry, keeps the reorder and shows no
  browser error text such as "Failed to fetch". Save is the one primary action.

#### Scenario: A failed write at phone width
- **WHEN** in a window 390 × 844, the operator saves a reorder of `2024-09-01 - Sommarlov` while its folder
  cannot be written
- **THEN** the panel under the top bar says that `reel.yaml` could not be saved, shows the service's whole detail
  with the path it names, and offers Retry. Save is the one primary action, the panel takes at most two fifths of
  the window's height, and the page does not scroll horizontally.

### Requirement: Edit mode keeps keyboard focus in view and never drops it

After the operator drops, moves, removes or restores a clip in Edit mode, from the keyboard or with a
pointer, the control that holds keyboard focus SHALL be fully visible together with its whole row. No part
of either SHALL be covered by the bin's chapter heading or cut off by the edge of the bin; the bin scrolls,
the rest of the workspace does not. The one exception is a drop into another chapter (see "Edit mode drags
clips between chapters"): then the moved clip's handle and its row's first line SHALL be fully visible and
not covered.

Suppose Edit mode's read of the editorial document failed and the operator presses **Try again**. Then:

- the failure SHALL stay shown while the document is read again
- Try again SHALL keep keyboard focus, and SHALL show that it is busy until the read answers
- when the read fails again, focus SHALL stay on Try again, and the failure SHALL be announced again
- when the read succeeds, focus SHALL move to the heading of the event's fields
- when the event changed on disk in the meantime, focus SHALL move to the control that reads the event
  again

Focus SHALL never fall to the page's body.

When a save is answered, the control that then holds keyboard focus SHALL be fully inside the window.

#### Scenario: The first keyboard drop keeps the dropped clip in view
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with no other edit and in a window
  1280 × 720, the operator focuses the handle of its first clip, `s1710001.mp4`, in the bin, lifts the clip,
  moves it down one place and drops it
- **THEN** the top bar says "Unsaved", keyboard focus is on that handle, and the handle and its whole row are
  fully visible in the bin

#### Scenario: The first drop at phone width
- **WHEN** the operator does the same in a window 390 × 844 with the third clip, `s1710003.mp4`
- **THEN** its handle and its whole row are fully visible in the bin

#### Scenario: A tall row dropped into another chapter
- **WHEN** in a window 1280 × 720 on `2024-08-20 - Två kapitel - Tjörn`, the operator drags
  `Kvällen/s1710002.mp4` in the bin into `Main` after `s1710001.mp4`
- **THEN** keyboard focus is on its handle in `Main`, and its row's first line is fully visible below the
  chapter's heading in the bin

#### Scenario: A conflict in a short window scrolled to its top
- **WHEN** in a window 320 × 568, the operator has changed the location of
  `2024-06-27 - Grillning med grannar`, presses Save, and the save is answered with a conflict
- **THEN** Save keeps keyboard focus and is fully inside the window, and so is the explanation's panel

#### Scenario: A drop far down a long bin
- **WHEN** the operator moves the last clip of a 400-clip chapter up one place by keyboard
- **THEN** its handle and its whole row are fully visible in the bin, and the page has not scrolled

#### Scenario: Try again keeps focus while the document is still unreadable
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` became unparseable after its page was read,
  the operator enters Edit mode, and then presses Enter on Try again while the file is still unparseable
- **THEN** Try again shows that it is busy while the read runs, keyboard focus stays on Try again
  throughout and afterwards, and the unparseable-document failure is announced again

#### Scenario: Try again moves focus to the fields once the read succeeds
- **WHEN** after that, the file is repaired and the operator presses Enter on Try again
- **THEN** the event's fields and clip lists are shown, and keyboard focus is on the heading of the event's
  fields

### Requirement: Edit mode's save bar is in the page before the first edit

Once Edit mode has read the editorial document, the top bar's save controls (the unsaved summary, Reset and Save)
SHALL already be part of the page, hidden for as long as there is nothing to save and no vanished event to
explain. The first edit SHALL show them. It SHALL NOT have to build them.

While they are hidden:

- they SHALL draw nothing, and the top bar SHALL NOT change its height when they show
- neither the keyboard nor assistive technology SHALL reach them: Tab SHALL NOT stop on Reset or Save, and the
  page SHALL NOT list a region named "Unsaved changes"

They SHALL be hidden again whenever nothing is left to save: when every edit is undone, and after Reset.
Showing them SHALL change nothing else about them.

The first edit SHALL cost no more than the next one. In a chapter that plays 400 clips, in a Chromium window
1280 × 900, the time from pressing Move down on a clip to the next painted frame, for the first edit made in
Edit mode, SHALL be at most 50 ms longer than the same press on another clip as the second edit made. The time
is the median of five runs, each in a fresh Edit mode.

#### Scenario: No save bar before the first edit
- **WHEN** in a window 1280 × 720, the operator opens Edit mode on `2024-06-27 - Grillning med grannar`, makes
  no edit, and presses Tab through every control of the workspace
- **THEN** no stop is on a Reset or Save, and the page lists no region named "Unsaved changes"

#### Scenario: The first edit shows the bar
- **WHEN** the operator then changes the title
- **THEN** the top bar shows "Unsaved", Reset and Save (which is its one primary action), and its summary names
  the changed title, and no pane has moved

#### Scenario: An undone edit hides the bar again
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator moves `s1710001.mp4` down one
  place, and then moves it up one place
- **THEN** the save controls were shown after the first move and are hidden after the second, and the page shows
  no unsaved changes

#### Scenario: The first edit in a 400-clip chapter
- **WHEN** in a window 1280 × 900, Edit mode is open on an event whose one chapter plays 400 clips, the
  operator presses Move down on the first clip and then Move down on the second, and the five runs are timed
- **THEN** the median time to the next painted frame of the first press is at most 50 ms longer than the
  second's

### Requirement: Reset leaves keyboard focus on a heading that can be seen

Reset removes the save controls, with the control that was pressed, so keyboard focus SHALL move at once to the
workspace's level-one heading, the event's title in the top bar, never to the page's body. The top bar does not
scroll, so the heading is always in view and nothing SHALL scroll for it. Where the panes are stacked and the page
scrolls, the page SHALL scroll the least distance, instantly, that brings the heading fully into view.

#### Scenario: Reset from the bottom of a long page
- **WHEN** in a window 1280 × 720, in Edit mode on an event whose one chapter plays 400 clips, the operator moves
  its last clip up one place, with the bin scrolled to the clip, and presses Reset from the keyboard
- **THEN** keyboard focus is on the top bar's heading, and the clip is back in its place

#### Scenario: Reset with the heading already in view
- **WHEN** in a window 1280 × 720, the operator changes the title of `2024-06-27 - Grillning med grannar` and
  presses Reset
- **THEN** keyboard focus is on the top bar's heading, and nothing in the workspace has scrolled

#### Scenario: Reset with the bar resting
- **WHEN** in a window 320 × 568, where the panes are stacked, the operator changes the title of
  `2024-06-27 - Grillning med grannar`, scrolls the page to the bin, and presses Reset
- **THEN** keyboard focus is on the heading, and the heading is fully visible

### Requirement: Edit mode's clip list draws only the rows near the view, without moving the page

The bin SHALL let the browser skip drawing the clip rows that are far out of view (CSS `content-visibility: auto`
on each row), giving every row not yet drawn a block size close to a drawn row's and every row once drawn the size it
was drawn at, so that the bin's scroll height and the place of what is in view do not change as rows come into view.
The bin's compact rows fit its width, so they SHALL be skipped at every width the bin has. Every row SHALL stay in the
page while skipped: focusable by Tab, read by assistive technology, found by the browser's find in page, a drop target
for a drag, and reachable by keyboard reorder.

Rows coming into view SHALL NOT move the bin: while the operator scrolls it, the row at the top of the view SHALL
keep its place to within 1 px apart from the scroll itself. The bin's scroll height after the whole list has been
scrolled through once SHALL differ from its height on opening by at most 5 %.

Nothing a row draws outside its own box SHALL be cut off by the skipping: the row's focus ring, the drop indicator and
the dragged row SHALL look as they did before, in the light and the dark scheme. Dragging a clip (with the pointer and
by keyboard), marking clips and moving the marked ones, rotating a clip and the card dialog SHALL work as before; after
a drop, every row SHALL be drawn and take clicks where it now is, never where it was.

#### Scenario: Scrolling a 400-clip list moves nothing
- **WHEN** the bin shows an event of 400 clips in one chapter at 1280 × 720, and the bin is scrolled from the top to
  the bottom in steps of half a view, waiting two frames after each step
- **THEN** after each step the top row in view is where the step put it to within 1 px, the scroll height at the
  end differs from the scroll height on opening by at most 5 %, and the rest of the workspace has not moved

#### Scenario: A drag to the end of a long list lands where it was shown
- **WHEN** the operator drags the first clip of a 400-clip chapter to the last slot of the last chapter, the bin
  scrolling on its own across rows that were never drawn
- **THEN** the clip is dropped in the slot the drop indicator showed, and the draft's order says so

#### Scenario: Keyboard reorder far down the list
- **WHEN** the operator moves a clip down the bin by keyboard past rows that were never drawn
- **THEN** the moved row keeps keyboard focus, is in view with its focus ring whole, and the announcement names its new
  place

#### Scenario: Nothing is cut off
- **WHEN** a row has keyboard focus, a drag shows its drop indicator, or a clip is being dragged, in the light and the
  dark scheme
- **THEN** the focus ring, the indicator and the dragged row are drawn whole

#### Scenario: A skipped row is still found
- **WHEN** the operator tabs through the bin, or searches the page for the name of the 390th clip
- **THEN** each row is reached in order and the 390th clip's row is scrolled into view and shown

#### Scenario: A moved row takes its clicks where it is
- **WHEN** two marked clips are dragged to the top of another chapter in Chrome, so that the rows below them move down
- **THEN** a click on a moved row's mark box marks that row, and no other row's control takes the click

## REMOVED Requirements

### Requirement: Edit mode lines up with the event page and fits a phone
**Reason**: Edit mode no longer reuses the event page's table layout; it is a workspace.
**Migration**: "Edit mode is a full-window workspace" and "The workspace follows the theme and fits narrower windows".

### Requirement: Edit mode's save bar rests in the page when it would hide the editor
**Reason**: There is no bottom save bar; the save controls are in the top bar.
**Migration**: "The workspace's top bar holds the event and the save controls".

### Requirement: Notifications never cover the save bar
**Reason**: There is no bottom save bar to keep clear; notifications have a place in the workspace.
**Migration**: "Notifications never cover the workspace's top bar or a focused control".
