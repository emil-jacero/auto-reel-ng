## ADDED Requirements

### Requirement: The timeline shows the event's analysis suggestions beside its clips

When the Timeline shows its track (the section open and every shown clip's proxy ready), it SHALL read the
event's cached analysis (`GET …/analysis`) and draw each suggestion (a black, white or frozen span that analysis
found) as a **mark** in an analysis lane, a row below the clips' row, under the clip it belongs to, placed by its
start and end in the clip, at the timeline's zoom. The read SHALL be made only then: a closed Timeline, and one
that is still preparing proxies, SHALL make no request for the analysis ("The event page offers a Timeline that
loads nothing until it is opened"). Closing and opening the Timeline, which a Refresh does, SHALL read it
again; a read that closing the Timeline or leaving the page has made pointless SHALL be abandoned. The page
SHALL NOT start an analysis, and the read SHALL NOT change anything.

A mark SHALL have, as text, its kind in words (Black frames, White frames, Frozen picture, or an unrecognised
kind as written), its start, its end and its length, written as times in a clip are everywhere ("Times are
written one way on every screen"), and, as a glyph and a word, its state. A mark SHALL be at least 44 CSS
pixels wide to press, whatever width its span has at the current zoom, and marks that would overlap SHALL stack
and never hide each other, including the last mark of one clip and the first of the next; the lane's height SHALL NOT change as the track scrolls. Only the marks of the clips in view SHALL be drawn, plus the one that has keyboard
focus.

A suggestion's state SHALL be derived from the clip's cuts, never remembered: **cut** when the cuts the clip
lists now (not removed ones) cover its whole span, counting spans to the millisecond and joining overlapping
or touching cuts as the render does; **partly cut** when they cover some of it; **dismissed** when the operator
dismissed it during this page visit and no cut covers any of it; otherwise **pending**. Removing or undoing the
cut that covered a suggestion SHALL return it to pending with no other action, and a cut saved in an earlier
session SHALL show its suggestion as cut on the first read.

The lane SHALL tell the three kinds of "no suggestions" apart: an event whose analysis was never run (no clip has a cached entry, whatever the service's `analyzed` flag says: a
rendered event has a cache directory) SHALL say "Not analyzed" and name the command that runs it; an analysed event with nothing found SHALL say nothing was
found; and in an analysed event a clip with no cached analysis (its file changed since) SHALL be marked "Not
analyzed" in its own row, while a clip analysed with nothing found SHALL show no marks. A read that fails SHALL
leave the timeline usable and show a note, not an alert, that says the suggestions could not be read and why,
in the words the page uses for its other reads.

#### Scenario: A closed or preparing timeline reads no analysis

- **WHEN** the operator opens the page of an analysed event and does not open the Timeline, or opens it while a
  clip's proxy is not ready
- **THEN** no request to `…/analysis` has been made, and the first one is made when the track is shown

#### Scenario: Suggestions are drawn under their clip

- **WHEN** an analysed event's clip `C0012.MP4` has a black span from 0 to 3.2 s and a freeze span from 58.1 to
  60 s, and the timeline is shown
- **THEN** the clip's row has two marks, in time order, named "Black frames 0:00 to 0:03.2 (3.2 s), pending" and
  "Frozen picture 0:58.1 to 1:00 (1.9 s), pending", each with its icon and a `?` glyph

#### Scenario: A narrow span is still pressable

- **WHEN** the timeline is zoomed out so that a 0.4 s freeze span is 3 px wide
- **THEN** its mark is at least 44 px wide to press, and two such marks 10 px apart sit on two rows, both
  fully visible

#### Scenario: A cut covers the suggestion, however it was made

- **WHEN** a clip's black suggestion spans 0 to 3.2033333 s and its draft lists a cut from 0 to 1.5 s and another
  from 1.5 to 3.203 s
- **THEN** the suggestion's state is cut, because the two cuts touch and together cover the span to the
  millisecond

#### Scenario: Removing the cut brings the suggestion back

- **WHEN** a suggestion is cut by a cut the operator then removes in the Cuts panel
- **THEN** its mark reads pending again, without any press on the mark

#### Scenario: A saved approval shows on the first read

- **WHEN** `reel.yaml` holds a trim from 0 to 3.2 s with the reason `black` and analysis lists a black span from 0
  to 3.2 s on that clip
- **THEN** on opening the event page the suggestion reads cut

#### Scenario: A cut over part of the span

- **WHEN** a clip lists a cut from 0 to 1 s and a black suggestion spans 0 to 3.2 s
- **THEN** the suggestion reads partly cut

#### Scenario: Marks of adjacent clips never hide each other

- **WHEN** a clip ends with a black span and the next clip starts with one, so that their 44 px marks reach into
  each other at the current zoom
- **THEN** the two marks sit on two rows and each is fully visible and pressable

#### Scenario: A rendered but never analysed event

- **WHEN** an event has been rendered (its cache directory holds only the render manifest) and was never analysed
- **THEN** the lane says "Not analyzed" and names `auto-reel analyze`, and no clip row says "Not analyzed" or that
  nothing was found

#### Scenario: Never analysed, analysed clean, and a stale clip

- **WHEN** one event has no analysis cache, a second was analysed and nothing was found, and in a third the
  file `C0003.MP4` was replaced after analysis while its siblings have entries
- **THEN** the first says "Not analyzed" and names `auto-reel analyze`, the second says nothing was found, and
  the third marks only `C0003.MP4`'s row "Not analyzed"

#### Scenario: Reopening reads again

- **WHEN** the operator re-runs `auto-reel analyze`, presses Refresh (which closes the Timeline) and opens the
  Timeline again
- **THEN** the lane shows the new suggestions

#### Scenario: A failed read leaves the timeline

- **WHEN** `GET …/analysis` answers 502 for an unreadable disk, or does not answer
- **THEN** the timeline still shows, no marks are drawn, and a note says the suggestions could not be read and
  gives the cause

#### Scenario: Reading the analysis changes nothing

- **WHEN** the page shows the timeline of an analysed event and the operator makes no edit
- **THEN** no request other than reads is made, and no analysis is started

### Requirement: Suggestions are operable by keyboard and never shown by colour alone

The analysis lane of each visible clip SHALL be one group, named "Analysis suggestions of" and the clip's name
as the clip's row names it, and SHALL be one stop in the keyboard order: ArrowLeft and ArrowRight SHALL move
focus to the previous and next suggestion of the clip, and Home and End to its first and last. Moving to a
suggestion outside the part of the timeline in view SHALL bring it into view and focus it. Selecting a
mark (press, Enter, Space or arriving by arrow) SHALL show its detail (the clip, the kind in words, the span, the
length and the state in words) and SHALL move the timeline's playhead to the suggestion's start without starting
playback. The lane SHALL offer no decision outside a Timeline that is given one.

A suggestion's kind and state SHALL each be shown as words and as an icon or glyph, and a legend under the lane
SHALL spell the icons and glyphs out in words, never by colour alone
("State is never shown by color alone"), with text contrast of at least 4.5:1 and a visible focus indicator in
both colour schemes. When the system asks for reduced motion, the lane SHALL NOT animate. In a window 390 CSS
pixels wide, and down to 320, the lane and its detail SHALL NOT make the page scroll horizontally.

#### Scenario: Arrow keys walk the suggestions

- **WHEN** focus is on the first of three marks on a clip and the operator presses ArrowRight twice, then Home
- **THEN** focus is on the third mark, then the first, and each move leaves one mark in the tab order

#### Scenario: A mark out of view is reached

- **WHEN** the timeline is zoomed in and the next suggestion lies beyond the right edge
- **THEN** ArrowRight scrolls it into view and focuses it

#### Scenario: The lane reads in grayscale

- **WHEN** the timeline is viewed with all colour removed
- **THEN** each mark still shows its kind icon and its state glyph, and the detail reads the kind and state in
  words

#### Scenario: The lane fits a phone

- **WHEN** the event page with its timeline is viewed 390 and 320 CSS pixels wide
- **THEN** the page does not scroll horizontally, the lane scrolls with the timeline inside it, and the detail's
  buttons wrap and stay fully visible

#### Scenario: Reduced motion

- **WHEN** the system asks for reduced motion and a mark is selected
- **THEN** nothing in the lane or its detail animates
