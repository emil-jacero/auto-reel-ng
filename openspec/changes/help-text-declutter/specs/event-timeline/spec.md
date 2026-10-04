## MODIFIED Requirements

### Requirement: The track lays the clips out by their proxies' lengths, with the chapters and the cuts

With every shown clip ready, the Timeline SHALL show, in one horizontally scrolling track:

- a **ruler** with time labels in the page's time format (`m:ss`, with fractions only when zoomed in far enough that labels would repeat)
- the **clips end to end** in play order (a black title card's span, when the event draws one before a chapter, is between them, see "Each chapter's title card is a block on the Timeline"), each as wide as its proxy's duration at the current zoom, labelled with its name as the page names it. A proxy has the source's timestamps, so a time in a proxy is the same time in the source clip. A clip's length SHALL come from its proxy's facts, never from the browser's reading of a file and never defaulted; a clip shorter than a pixel at the current zoom SHALL still be drawn, one pixel wide at least, and the playhead SHALL be able to be put in it by keyboard.
- a **chapter band** above the clips: one segment per chapter spanning its shown clips, labelled with the chapter's name, or as the page headings an unnamed chapter ("Main" beside named chapters, "Clips" when none is named). The band's labels stay in view while their chapter scrolls past.
- each clip's **cuts**, as the event page lists them from `reel.yaml` (in Edit mode: as the Cuts panels list them now, the draft's, with the ones marked removed left out), drawn over the clip as spans with a hatch pattern and named by their reason in words ("manual", "black", "white", "freeze") in the span's text alternative; overlapping or touching cuts SHALL be drawn as the render joins them, one span; a cut that runs past the proxy's duration SHALL be drawn to the end of the clip only. In the read view the spans SHALL be read-only: no handle, no drag, no edit. In Edit mode each cut SHALL have the two trim handles of "Edit mode's cuts are trim handles", drawn over the joined span.
- the **movie stat**, one muted line in the Timeline's control row (beside Play and the zoom), not a paragraph of its own: the movie's length (the sum of the shown clips' lengths minus the time the cuts remove, plus the lengths of the black title cards the track draws), then the source length, the time the cuts remove and the cards' time, each named, separated by " · " ("Movie 3:12 · footage 3:45 · cuts −0:33"; with black cards, "Movie 3:20 · footage 3:45 · cuts −0:33 · cards +0:08"). The cuts term SHALL be left out when no cut removes time, and the cards term when no black card adds time. The line SHALL wrap by whole terms, never scroll the page, and be written by the clock ("Running times are written to a fixed width and say what they are")

If the cuts cannot be read (the same read the page's cut summaries use), the Timeline SHALL show the track without cut spans and SHALL say in a note that the cuts could not be read, and SHALL NOT show the movie's length as if there were no cuts.

#### Scenario: Clip widths follow the facts
- **WHEN** an event has clips whose proxies report 24.96 s, 3.2 s and 0.48 s at 40 px per second
- **THEN** the clips are drawn about 998, 128 and 19 px wide, in play order, each labelled with its name, with the 0.48 s clip still focusable

#### Scenario: A rotated phone clip keeps its source time
- **WHEN** a clip's source is a rotated phone clip of 12.0 s and its proxy reports a duration of 12.0 s
- **THEN** the clip is drawn 12.0 s long, and a cut at 3.0 to 4.5 s in `reel.yaml` is drawn from 3.0 to 4.5 s of that clip

#### Scenario: Chapters are bands, not guesses
- **WHEN** an event has the chapters "Dag 1" with two clips and "Kvällen" with one
- **THEN** the band shows "Dag 1" over the first two clips and "Kvällen" over the third, and an event with a single unnamed chapter shows "Clips" over all of them

#### Scenario: Overlapping cuts are one span
- **WHEN** a clip lists cuts 2.0 to 4.0 s and 3.5 to 5.0 s
- **THEN** the track draws one hatched span from 2.0 to 5.0 s, and the movie's length is shorter by 3.0 s for that clip

#### Scenario: A cut that cannot be read
- **WHEN** reading `reel.yaml`'s cuts fails while the proxies are ready
- **THEN** the track is shown without cut spans, a note says that the cuts could not be read, and no movie length is shown

#### Scenario: The same cut in the read view and in Edit mode
- **WHEN** a clip lists a cut from 2.0 to 4.0 s, and the operator opens the Timeline in the read view and then in Edit mode
- **THEN** the read view draws the hatched span from 2.0 to 4.0 s with no handle, and Edit mode draws the same span with a start and an end handle

#### Scenario: Black cards count in the movie's length
- **WHEN** an event of 3:45 of footage with 33 s of cuts draws two black cards of 4.0 s each
- **THEN** the stat reads "Movie 3:20 · footage 3:45 · cuts −0:33 · cards +0:08", and a video card adds nothing to it

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
rendered event has a cache directory) SHALL show a small muted badge "Not analyzed" and no sentence (the command that runs it, `auto-reel analyze <root>` and then Refresh, is in the Timeline help); an analysed event with nothing found SHALL say nothing was
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
- **THEN** the lane shows the badge "Not analyzed" and the Timeline help names `auto-reel analyze`, and no clip row says "Not analyzed" or that
  nothing was found

#### Scenario: Never analysed, analysed clean, and a stale clip

- **WHEN** one event has no analysis cache, a second was analysed and nothing was found, and in a third the
  file `C0003.MP4` was replaced after analysis while its siblings have entries
- **THEN** the first shows the badge "Not analyzed" and the Timeline help names `auto-reel analyze`, the second says nothing was found, and
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

### Requirement: The selected cut's times can be typed, and stay in step with the handles

Under the track the Timeline SHALL show the **selected cut** in a group named "Cut <n> of <name>" with two text fields, "Start of cut <n> of <name>" and "End of cut <n> of <name>", showing the cut's times in the Cuts panel's time format. A cut SHALL be selected when one of its handles gets keyboard focus or is pressed, or its span is pressed; the selection SHALL stay until another cut is selected or the cut is removed. With no selected cut the group SHALL NOT be shown: no line says that nothing is selected, no field is drawn and no room is kept for it. The fields' hint (the time forms, Enter and Escape) SHALL be in the Timeline help, and the fields SHALL name it as their `aria-describedby`.

A time typed in a field SHALL be taken on Enter or when the field loses focus, in the forms the Cuts panel accepts (seconds, `m:ss`, `h:mm:ss`, up to three decimals), and SHALL make one edit of the draft. It SHALL be refused, and nothing changed, for the reasons the Cuts panel refuses a typed cut and in its words: unreadable, too precise, an end not after the start, an overlap with another cut of the clip that is not removed (the cut itself excepted), an end after the clip's length (the proxy's duration). A refusal SHALL be shown at the field the Cuts panel's rule names for it and announced; when the time was taken with Enter that field receives keyboard focus, and when it was taken because the field lost focus the refusal stands in the same words and focus stays where the operator put it. Escape in a field SHALL put the cut's current time back. A typed time need not be a frame time: it is taken to the millisecond, as a typed cut is.

The fields, the handles, the span drawn and the Cuts panel's list SHALL show the same times at all times: a drag or a key updates the fields on every change, and a typed time moves the handle. A field being typed in (it has focus and its text differs from the cut's time) SHALL NOT be overwritten by a handle moving, but SHALL NOT be taken either until Enter or blur.

#### Scenario: A drag updates the fields
- **WHEN** cut 1 is selected and the operator drags its end from 2.5 s to 3.5 s
- **THEN** the "End of cut 1" field reads 0:03.5 while the pointer is still down and when it is released, and the Cuts panel lists 0:01 to 0:03.5

#### Scenario: A typed time moves the handle
- **WHEN** the operator types `0:00.5` in the "Start of cut 1" field and presses Enter
- **THEN** the start handle reads 0.5, the span is drawn from 0:00.5, the Cuts panel lists 0:00.5 to 0:02.5, and the save bar says that 1 cut was trimmed

#### Scenario: A refused typed time
- **WHEN** the operator types `3` in the "Start of cut 1" field and presses Enter
- **THEN** it is refused at the End field, which receives keyboard focus, saying that a cut must end after it starts (0:02.5 is not after 0:03), announced, and the cut is unchanged
- **WHEN** the operator types `4.5` in the "End of cut 1" field
- **THEN** it is refused, saying that it overlaps cut 2 (0:04 to 0:05)

#### Scenario: A time past the clip's end
- **WHEN** the operator types `7` in the "End of cut 2" field of `s1710001.mp4` (6.02 s)
- **THEN** it is refused, saying that 0:07 is after the clip's end at 0:06.02

#### Scenario: A field being typed in is left alone
- **WHEN** the operator has typed `0:0` in the start field without pressing Enter and presses Shift+Right on the cut's end handle, then returns to the field
- **THEN** the field still reads `0:0`, and Enter takes what is in it

#### Scenario: Nothing is selected, nothing is shown
- **WHEN** the Timeline opens and no cut has been selected
- **THEN** no "Selected cut" group and no sentence about a selection is in the document
- **WHEN** a cut's handle gets focus
- **THEN** the group "Cut 1 of <name>" appears under the track with its two fields
