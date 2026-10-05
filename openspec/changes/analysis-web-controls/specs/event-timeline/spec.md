## MODIFIED Requirements

### Requirement: The timeline shows the event's analysis suggestions beside its clips

When the Timeline shows its track (the section open and every shown clip's proxy ready), it SHALL draw each
suggestion of the event's cached analysis (a black, white or frozen span that analysis found) as a **mark** in an
analysis lane, a row below the clips' row, under the clip it belongs to, placed by its start and end in the clip,
at the timeline's zoom. The Timeline SHALL NOT read the analysis itself: it SHALL show the event page's one read of
it (`GET …/analysis`, capability `web-app`, "The event page shows the event's analysis state"), so the lane, its
badge and the page header always show the same read. When that read is replaced (a Refresh, the end of the event's
analysis job), the lane SHALL show the new read without the Timeline being closed or the page reloaded, keeping its
zoom, scroll position and playhead. A Timeline that is closed or still preparing proxies SHALL draw no lane. The
read SHALL NOT change anything; an analysis is started only by the operator's Re-analyze (below) or by the
service's own background analysis, never by showing the lane.

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

The lane's control row SHALL show the event's analysis badge, in the same words, glyph and tone as the page
header shows it ("The event page shows the event's analysis state"): **Not analyzed** (never), **Analysis out of
date** (stale), **Analyzing…** with the job's live progress (analyzing), **Analysis failed for N clips** (failed),
and no badge when the analysis is current. The badge state SHALL be the service's published analysis state, never
inferred from the `analyzed` flag or from which clips have segments. An event whose analysis is current with
nothing found SHALL say nothing was found. Each clip's row SHALL carry its own clip's state when it is not
current: "Not analyzed", "Analysis out of date", "Analyzing…" or "Analysis failed", in words and with a glyph; a
clip analysed with nothing found SHALL show no marks and no note. In Edit mode, beside the badge, the control row
SHALL offer **Re-analyze** ("Analyze" while the event was never analysed), the same action as the page header's
(capability `web-app`, "The operator re-analyzes an event from its page"). A read that fails SHALL leave the
timeline usable and show a note, not an alert, that says the suggestions could not be read and why, in the words
the page uses for its other reads.

The Timeline help SHALL say what Re-analyze does: the suggestions are found again from the clips, cuts already
approved stay in the event's cuts, and dismissed suggestions come back. It SHALL list, while the analysis failed
for any clip, each such clip's name with the service's failure text. The terminal command (`auto-reel analyze
<root>`) SHALL appear only there, as an aside that the same runs from a terminal; no sentence outside the help
SHALL name it.

#### Scenario: A closed or preparing timeline reads no analysis

- **WHEN** the operator opens the page of an analysed event and does not open Edit mode, or opens it while a
  clip's proxy is not ready
- **THEN** no analysis lane is drawn, the Timeline itself has made no request to `…/analysis`, and the page has
  made exactly one (the header's), whose answer the lane shows once the track is shown

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

- **WHEN** an event has been rendered (its cache directory holds only the render manifest), was never analysed,
  and the service reports its analysis state as never
- **THEN** the lane's control row shows the badge "Not analyzed" and an Analyze button, no clip row says that
  nothing was found, and no text outside the Timeline help names `auto-reel analyze`

#### Scenario: Never analysed, analysed clean, and a stale clip

- **WHEN** one event's analysis state is never, a second's is current with nothing found, and in a third the
  file `C0003.MP4` was replaced after analysis, so the service reports the event and that clip as stale
- **THEN** the first shows the badge "Not analyzed", the second shows no badge and says nothing was found, and
  the third shows the badge "Analysis out of date" and marks only `C0003.MP4`'s row "Analysis out of date"

#### Scenario: The lane follows an analysis that finishes

- **WHEN** the Timeline of an event shows its track in Edit mode, the operator presses Re-analyze, and the
  analysis job ends done
- **THEN** the badge reads "Analyzing…" with the job's progress while it runs, and when it ends the lane shows
  the new suggestions without a Refresh, a reload or the Timeline being closed, with the same zoom and playhead

#### Scenario: Reopening reads again

- **WHEN** the operator re-runs `auto-reel analyze` from a terminal and presses Refresh
- **THEN** the page reads the analysis again, and the lane shows the new suggestions once the Timeline shows its
  track

#### Scenario: A failed clip is named in the help

- **WHEN** the service reports the event's analysis as failed for `C0007.MP4` with the text "ffmpeg exited 1:
  Invalid data found when processing input"
- **THEN** the badge reads "Analysis failed for 1 clip", `C0007.MP4`'s row reads "Analysis failed", and the
  Timeline help lists `C0007.MP4` with that text

#### Scenario: A failed read leaves the timeline

- **WHEN** `GET …/analysis` answers 502 for an unreadable disk, or does not answer
- **THEN** the timeline still shows, no marks are drawn, and a note says the suggestions could not be read and
  gives the cause

#### Scenario: Reading the analysis changes nothing

- **WHEN** the page shows the timeline of an analysed event and the operator makes no edit and does not press
  Re-analyze
- **THEN** no request other than reads is made, and no analysis is started
