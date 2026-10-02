## MODIFIED Requirements

### Requirement: State is never shown by color alone

Every render verdict, job status, clip status and event failure kind a screen shows SHALL be shown as its
words, paired with an icon, and never as a color alone. The same holds for warnings and failure messages:
each shows its words and an icon. Tones SHALL be consistent across screens: the same status has the same
tone and icon on every page.

In both color schemes, text SHALL meet WCAG 2.1 AA contrast: at least 4.5:1 for normal-size text, and at
least 3:1 for large text and for the focus indicator against its background. This includes the words inside
status labels and secondary ("muted") text. As in WCAG, the label of a control that is currently
unavailable (such as Refresh while it reads) is exempt.

A busy button SHALL show a loader before its label, in place of its icon, drawn in the button's own text
color. In the operating system's forced-colors mode, where the browser replaces the page's colors with the
system palette, that loader SHALL stay visible, in the same color as the button's label.

#### Scenario: Verdicts read in grayscale
- **WHEN** the event list for the dev library is viewed with all color removed
- **THEN** `2024-06-27 - Grillning med grannar` still reads "Needs render" with its reasons, and
  `2023-06-23 - Midsommar - Dalarna` still reads "Up to date"

#### Scenario: Status labels meet contrast in both schemes
- **WHEN** the contrast of every status label's text on its own background, and of the scan time's muted
  text on the page background, is measured in the light and in the dark scheme
- **THEN** every ratio is at least 4.5:1

#### Scenario: A failed job is marked by words and icon
- **WHEN** the list shows `2024-10-05 - Trasig`, whose latest job failed
- **THEN** its job status reads "Failed" beside an icon, and not only in a red color

#### Scenario: A busy button's loader survives forced colors
- **WHEN** the operator's system uses forced colors, and the operator presses Render on
  `2024-06-27 - Grillning med grannar` while the service takes two seconds to answer
- **THEN** during those seconds Render shows a loader in the same color as its label, in place of its icon,
  and the loader is not drawn in the button's background color

### Requirement: Every control is large enough to touch

When the browser's primary pointer is coarse, such as a finger on a phone, each of these controls SHALL
take a tap anywhere in an area of at least 44 × 44 CSS pixels around it:

- every button
- every option of a segmented choice, such as the list's All / Needs render filter and the color-scheme
  control
- the header's link to the event list, and the event page's link back to it
- a notification's link

No control's area SHALL reach into another control, including two controls stacked one above the other.
In a table row of the list, the area of a control SHALL NOT reach above the top of its own cell, so that
it never covers the line that separates the row from the one above; the area stays 44 pixels tall by
reaching further below the control instead.
Making room for these areas SHALL NOT push text out of the box that holds it, or anything out of the header.
The color-scheme options are the one exception to the width: in a window narrower than 416 pixels the header
has no room for them beside the connection's state in words, and there each option SHALL take a tap in an
area 44 pixels tall and as wide as the option.

When the primary pointer is fine, such as a mouse, every control SHALL keep the size and place it has without
this rule.

#### Scenario: The list on a phone
- **WHEN** the operator opens the dev library's event list on a touch screen 390 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area centred on the Render of
  `2024-06-27 - Grillning med grannar`, on Refresh, or on each filter option reaches that control, a tap
  anywhere in an area 44 pixels tall and as wide as each color-scheme option reaches that option, and the page
  does not scroll horizontally

#### Scenario: The header keeps the connection's state in words
- **WHEN** the jobs connection is connecting, reconnecting, or live with jobs rendering and queued, and the
  operator opens the event list on a touch screen 384, 390, 412, 430, 480 or 528 pixels wide
- **THEN** the connection's state is in words inside its pill, clear of the color-scheme control, the header's
  content stays inside the header, and from 416 pixels a tap anywhere in a 44 × 44 pixel area centred on each
  color-scheme option reaches that option

#### Scenario: A row's Render keeps out of the row above
- **WHEN** the operator opens the dev library's event list on a touch screen 1280 pixels wide, where the
  events are table rows, and taps on the line that separates the `2024-06-27 - Grillning med grannar` row
  from the row above it
- **THEN** the tap does not reach the Render of `2024-06-27 - Grillning med grannar`, and a tap anywhere in
  a 44 pixel tall area as wide as that Render, whose top is no higher than the top of its cell, reaches it

#### Scenario: Two stacked buttons keep their own areas
- **WHEN** the operator saves Edit mode on `2024-06-27 - Grillning med grannar` on a touch screen 390 pixels
  wide, and the save is refused because the event was changed elsewhere
- **THEN** "Reload latest (discard my changes)" and "Overwrite with mine" are stacked, and a tap anywhere in a
  44 × 44 pixel area centred on either reaches that button and never the other

#### Scenario: Moving a clip by touch
- **WHEN** the operator opens Edit mode on `2024-06-27 - Grillning med grannar` on a touch screen 390 pixels
  wide
- **THEN** each clip's Reorder, Move up and Move down take a tap anywhere in a 44 × 44 pixel area of their
  own, and no tap meant for Move up reaches Move down

#### Scenario: A mouse sees no change
- **WHEN** the operator opens the event list, the page of `2024-06-27 - Grillning med grannar` and its Edit
  mode with a mouse, in windows 1280, 390 and 320 pixels wide
- **THEN** every control has the size and place it had before this rule

### Requirement: The screens fit a phone-width window

In a window 390 CSS pixels wide, no page SHALL scroll horizontally. Every fact about an event, a clip or a
failure that a page shows in a wide window SHALL still be shown in the narrow one, rearranged and never
dropped. Long names and details SHALL wrap rather than overflow.

The header SHALL stay one bar tall at every window width from 320 pixels, in any font the browser falls
back to, narrower or wider than the design font. Its job counts SHALL NOT be broken over several lines.
When the words of the counts do not fit beside the header's other content, each count SHALL shrink to its
status icon and number, the words staying for assistive technology. Which of the two is shown SHALL depend
on the room the header leaves the counts, not on the window's width alone.

#### Scenario: The list at phone width
- **WHEN** the operator opens the dev library's event list in a window 390 pixels wide
- **THEN** the page does not scroll horizontally, and each event still shows its date, title, location, clip
  counts, verdict with reasons, and latest job

#### Scenario: An event page at phone width
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn` in a window 390 pixels wide
- **THEN** the page does not scroll horizontally, and every clip still shows its position, file name,
  status, size and modification time

#### Scenario: A failure detail wraps
- **WHEN** the operator opens the list at 390 pixels wide, and it shows `2024-02-30 - Omöjligt datum` under
  "Needs attention"
- **THEN** its folder name, failure words and detail wrap within the window

#### Scenario: The header's counts in a wider font
- **WHEN** the connection is live with 99 jobs rendering and 99 queued, the browser's sans-serif font is
  Liberation Sans or DejaVu Sans, and the operator opens the event list in windows 470, 480, 485 and 500
  pixels wide
- **THEN** the header's content stays inside its bar and the connection's pill and the counts do not overlap
  the navigation or the color-scheme control, and the counts are on one line, in words where they fit and as
  icons with numbers where they do not
