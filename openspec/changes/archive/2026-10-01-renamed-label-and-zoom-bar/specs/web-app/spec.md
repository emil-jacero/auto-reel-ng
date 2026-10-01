## MODIFIED Requirements

### Requirement: The event list shows every event with its render state

The client's first screen SHALL list every event the events list response returns. Events SHALL be grouped
by the year of their date, groups newest year first, and events within a group newest date first. Events
with no date SHALL form their own group after every dated group. Each event SHALL show:

- its date
- its title, or the event's folder name when it has no title
- its location when it has one
- its clip count
- its NEW and MISSING clip counts when either is non-zero
- whether it needs a render and, if so, every reason the verdict cites, in words
- its latest job's status, when it has one

When two or more events the list shows would read the same, because they have the same date, the same title
(or, for an event with no title, the same folder name in its place) and the same location, compared without
regard to letter case, each of them SHALL also show its folder's path under the project root, for example
`2024/2024-07-14 - Kalas`. No two events share that path, so rows that would otherwise read the same are
told apart, even when their folders have the same name in different parent folders.

The screen MUST NOT omit an event the response contains, invent a fact the response does not carry, or
present a missing fact (no date, no title, no job) as a value.

#### Scenario: A multi-year library is grouped newest first
- **WHEN** the list contains events dated in 2023 and 2024 and one event with no date
- **THEN** the 2024 group appears first, then 2023, then the undated group, and each dated group is ordered
  newest date first

#### Scenario: An untitled event is shown by its folder name
- **WHEN** an event has no title in its metadata
- **THEN** it is shown under its event folder's name, not as an empty row or "Untitled"

#### Scenario: A stale event names every reason
- **WHEN** the title of `2024-06-27 - Grillning med grannar` was changed after its last render, while its
  movie is still on disk under the old name, so its verdict cites the editorial change and the changed movie
  name
- **THEN** its row says it needs a render and names both reasons in words, "edited since last render" and
  "movie name changed", and does not say that the movie file is missing

#### Scenario: A movie deleted from disk is named missing
- **WHEN** the movie of `2024-06-21 - Midsommar - Dalarna` was deleted after its last render, and nothing
  else about the event changed
- **THEN** its row says it needs a render because the movie file is missing, and names no other reason

#### Scenario: NEW and MISSING clips are visible
- **WHEN** an event has one NEW clip, and another references one clip that is absent from disk
- **THEN** the first row shows one new clip and the second shows one missing clip

#### Scenario: The latest job's outcome is visible
- **WHEN** one event's latest job failed, another's is queued, and a third has no job
- **THEN** the first row shows the failure, the second shows that it is queued, and the third shows no job
  status at all

#### Scenario: Look-alike events are told apart
- **WHEN** the list shows `2024/2024-07-14 - Kalas` and `2024/2024-07-14 - kalas`, both titled "Kalas", dated
  2024-07-14 and with no location
- **THEN** the first row also shows `2024/2024-07-14 - Kalas`, and the second `2024/2024-07-14 - kalas`
- **AND** no other row of the dev library shows its folder's path beside its title

#### Scenario: Look-alike folders of the same name are told apart
- **WHEN** the list shows `2023/Blandat` and `2024/Blandat`, neither with a date, a title or a location
- **THEN** both rows read "Blandat" in the undated group, and the first also shows `2023/Blandat` and the
  second `2024/Blandat`

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
page because, held, it would hide the editor, a notification MAY cover a control just above the bar, such as
the last clip row's; it still SHALL NOT overlap the bar.

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

## ADDED Requirements

### Requirement: The event page says what a render does when the movie's name changed

The movie's file name is made from the event's date, title and location. Suppose one of these changed
after the event's last render, and the movie rendered under the old name is still on disk. The verdict then
cites that the movie's name changed. In that case:

- **The list** SHALL name this reason in short words, "movie name changed", in the same line as the
  verdict's other reasons.
- **The event's page** SHALL show the same words. Under the verdict's reasons, on a line of its own, it SHALL
  also say that the next render saves the movie under its new name, and that the movie under its old name
  stays on disk.

For every other reason, the page SHALL show the reason's words alone, as the list does. That includes a
movie file that is missing from disk.

The words the page adds for a reason SHALL come from a mapping defined over the generated types' union of
staleness reasons, in the same way as the reasons' own words. When a reason is added, the client's
type-check then fails until it is decided whether the page says more about it. Neither screen SHALL name a
movie file that the service's response does not carry.

#### Scenario: The page of a renamed event
- **WHEN** the title of `2024-06-27 - Grillning med grannar` was changed after its last render, its movie is
  still on disk under the old name, and the operator opens its page in a window 390 pixels wide
- **THEN** the page says it needs a render, "edited since last render, movie name changed", and, on a line
  of its own, "The next render saves the movie under its new name. The movie under its old name stays on
  disk."
- **AND** the page names no movie file, and does not scroll horizontally, in a window 390 or 320 pixels wide
  and in either color scheme

#### Scenario: The list keeps the short words
- **WHEN** the operator opens the event list in a window 1280 pixels wide
- **THEN** the row of `2024-06-27 - Grillning med grannar` reads "edited since last render, movie name
  changed", and shows no sentence about the next render

#### Scenario: A missing movie gets no note
- **WHEN** the movie of `2024-06-21 - Midsommar - Dalarna` was deleted after its last render, and the
  operator opens its page
- **THEN** the page says it needs a render because the movie file is missing, and adds no sentence about the
  next render

#### Scenario: A new staleness reason fails the build at the page's mapping
- **WHEN** a staleness reason is added to the engine, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the page's mapping until it is decided whether the page says more
  about the new reason

### Requirement: Edit mode's save bar rests in the page when it would hide the editor

Edit mode's save bar SHALL be held at the window's bottom edge only while both of these hold:

- it takes two fifths of the window's height or less;
- the window is at least 28rem tall (448 pixels at the default text size), so that a held bar, the sticky header
  and a chapter heading leave room for a whole clip row.

Otherwise it SHALL NOT be held there. It SHALL rest in the page after the editor's last chapter, and scroll with
the page. It SHALL be held again as soon as both hold again. Which of the two it is depends only on the bar's
height and the window's, never on where keyboard focus is.
The bar SHALL follow each change of its own height and of the window's, in both directions. Such changes
include:

- a save's answer
- an edit that changes what the bar says
- a window resized or zoomed

While the bar rests, it SHALL NOT cover any part of the editor. When the page then scrolls a focused control
into view, it SHALL leave no room for the bar at the window's bottom.

The control that holds keyboard focus SHALL NOT leave the window because the bar starts to rest:

- When a save's answer makes the bar rest, the control that then holds keyboard focus SHALL be scrolled fully
  into the window. When that control is in the bar, such as Save, the page scrolls to the bar.
- When a resized or zoomed window makes the bar rest while one of the bar's controls holds keyboard focus,
  that control SHALL be scrolled fully into the window.
- While the bar rests and one of its controls holds keyboard focus, every further resize or zoom of the window
  SHALL leave that control fully inside the window, step by step. A change of what the bar says, or of its own
  height, SHALL NOT scroll the page.

When keyboard focus moves to a control of the editor that is partly outside the window, such as the description
field, whose caret alone the browser would bring into view, that control SHALL be scrolled fully into the
window.

No notification SHALL overlap the bar while it is held or while it rests.

Everything else about the bar is unchanged: what it says, its one primary action, its compact layout, and the
share of a 390 × 844 window it may take while it is held.

#### Scenario: A conflict at 400 % zoom
- **WHEN** in a window 320 × 256 (a 1280 × 1024 screen at 400 % zoom), using only the keyboard, the operator
  enters Edit mode on `2024-09-01 - Sommarlov`, moves its first clip down, and saves, and the save is
  answered with a conflict
- **THEN** the save bar rests after the last chapter, Save keeps keyboard focus, and Save is fully inside the
  window
- **AND** as the operator presses Shift+Tab from Save through every control of the bar, every clip row's
  controls and the fields, and then Tab back to Save, every control that receives focus is fully visible.
  None is covered by the save bar.

#### Scenario: A failed write at 400 % zoom
- **WHEN** the same save in the same window is answered with a failure to write `reel.yaml`
- **THEN** the save bar rests after the last chapter with the failure's whole detail, and every focus stop
  of the same walk is fully visible

#### Scenario: The first edit at 400 % zoom
- **WHEN** in a window 320 × 256, the operator enters Edit mode on `2024-09-01 - Sommarlov` and moves its
  first clip down with the keyboard
- **THEN** the save bar, which says only that there are unsaved changes, rests after the last chapter, and the
  moved clip's focused control and its whole row are fully visible

#### Scenario: A conflict in a short phone window
- **WHEN** in a window 320 × 568, the operator moves the first clip of `2024-09-01 - Sommarlov` down, and the
  save bar is held at the window's bottom, and then saves, and the save is answered with a conflict
- **THEN** the save bar rests after the last chapter, Save keeps keyboard focus, and Save and the rest of the
  bar are fully inside the window

#### Scenario: Phone and desktop windows keep the held bar
- **WHEN** the same conflict, or the same failure to write, is answered in a window 390 × 844 or
  1280 × 900
- **THEN** the save bar stays held at the window's bottom edge, as before this change

#### Scenario: A taller window holds the bar again
- **WHEN** after the conflict at 320 × 256, the window becomes 390 × 844, and then 320 × 256 again
- **THEN** the save bar is held at the window's bottom edge while the window is 390 × 844, and rests after the
  last chapter again at 320 × 256
- **AND** at each size, Save keeps keyboard focus and is fully inside the window

#### Scenario: Zooming in after a failed save
- **WHEN** in a window 1280 × 1024 or 1920 × 968, using only the keyboard, the operator moves the first clip of
  `2024-09-01 - Sommarlov` down and saves, the save is answered with a conflict or with a failure to write
  `reel.yaml`, and the operator then zooms in one browser step at a time, through 110, 125, 150, 175, 200,
  250 and 300 % to 400 %
- **THEN** after every step Save keeps keyboard focus and is fully inside the window, and at 400 % the save bar
  rests after the last chapter

#### Scenario: The first edit in a short, wide window
- **WHEN** in a window 480 × 242 (a 1920 × 1080 screen at 400 % zoom), the operator enters Edit mode on
  `2024-09-01 - Sommarlov` and moves its first clip down with the keyboard, or lifts it with the keyboard and
  drops it one place down
- **THEN** the save bar, which says only that there are unsaved changes and takes less than two fifths of the
  window, rests after the last chapter, and the moved clip's focused control and its whole row are fully
  visible

#### Scenario: A notification and a resting bar
- **WHEN** an error notification is shown, and the operator answers a conflict on `2024-09-01 - Sommarlov`
  in a window 320 × 568 or 320 × 256, and then scrolls the page from its top to its end
- **THEN** at no scroll position does the notification overlap the save bar
