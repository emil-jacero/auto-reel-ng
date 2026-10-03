## MODIFIED Requirements

### Requirement: The event page plays the event's rendered movie

When the event has a rendered movie, its page SHALL show a section headed "Movie" (a level-two heading) in the read
view, between the region that holds the verdict and the render controls and the event's chapters. The event has a
rendered movie exactly when its staleness verdict cites neither `no_manifest` nor `output`. The page SHALL decide
this from the event detail alone. An event without one SHALL show no movie section and SHALL make no request for a
movie. In Edit mode the page SHALL show no movie section. Leaving Edit mode reads the event again, and the section
returns with that read.

**Which file, and its version.** On each read of the event that shows the section, the page SHALL ask the service
for the first byte of the event's movie (`GET /api/v1/events/{event_id}/movie` with `Range: bytes=0-0`, never
served from or stored in the browser's cache). It SHALL take from that answer only what the service sent:
- the movie's entity-tag
- its size in bytes, from `Content-Range`
- its file name, from `Content-Disposition`

The player SHALL load the movie from the same route with that entity-tag, without its quotes, as the `v` query
parameter. The event id SHALL be encoded segment by segment, as on every events route. When a re-read the page
starts by itself (when the job it shows reaches a finished state, see "A shown screen re-reads in place when events
change") finds the same entity-tag, the player SHALL stay as it is, playing or paused, at its position. When it
finds a different one, the page SHALL replace the player with a new one at the new address. If the old player had
keyboard focus, the new one SHALL receive it. The old address SHALL never be used for the new file. Opening the page
and leaving Edit mode replace the page's content with placeholders while it reads (see "The event page shows the
event's chapters and clips"), and the section returns with a new player, paused at its start, at the address of
the entity-tag that read finds.

**A Refresh keeps the player.** An operator's Refresh of a page that shows the section SHALL replace the rest of
the page's content with placeholders, as every read of the event does, but SHALL keep the section and its
player while it reads, playing or paused, at its position. The player SHALL be the same one, not a new element at
the same address, and the Refresh SHALL NOT start, stop or seek it. When the read finds the same entity-tag, the
player SHALL stay as it is after it. When it finds a different one, the page SHALL replace the player with a new
one at the new address, with keyboard focus as above. When it finds that the event has no movie, or it fails, the
section SHALL go as it does for any read. While the read runs, the section SHALL show its heading and its player
and nothing that the read may change ("A read in progress is shown as a placeholder and announced"), and SHALL be
marked as busy; the verdict, the facts and the sentence return with the read's answer. A Refresh SHALL NOT request
any byte of the movie while the read runs.

**Nothing loads before Play.** Opening, refreshing or returning to the page SHALL NOT request any byte of the movie
other than the one-byte answer above, and SHALL NOT start playback. Playback SHALL start only from the operator's
action on the player, or on a chapter of the list under it. The player SHALL NOT loop and SHALL NOT be muted by the page. Its poster SHALL be the thumbnail
of the event's first played clip that is on disk, in the order the event page lists them, at the same address its
row uses. The page SHALL show no poster when there is no such clip, or when that thumbnail cannot be loaded.

**What the section says.**
- Whether the movie is **Current**, when the event is up to date, or **Outdated**, when it needs a render. Each is
  shown in words with an icon, never by color alone.
- For an outdated movie, a sentence that it was rendered before the event's latest changes and that a render
  brings it up to date.
- The movie's file name, as the service names it, and its size in the units the event page uses for clips. In the
  `output_renamed` case this is the movie under its old name. A fact the answer did not carry SHALL be left out,
  never guessed.
- When the event detail carries the movie's version (`movie.recorded_at`, when the render record was written, and
  `movie.fingerprint`, the short identity of the inputs it was made from), written as "Recorded" with that time in
  the one way the client writes times, then "version" and the fingerprint, in the same facts as the file's name
  and size. The time SHALL be kept exact in `<time dateTime>`. It is when the render finished for a rendered
  movie and when it was adopted for an adopted one, which the detail does not tell apart, so the page says
  "Recorded", not "Rendered". A version the detail did not carry (`movie` null) SHALL be left out, never
  guessed or replaced by the file's modification time.

**The player.**
- It SHALL be the browser's own media player with its native controls. It SHALL be named by the section's heading.
- The page SHALL add no keyboard shortcut of its own. The player SHALL be reachable with Tab, and SHALL show a
  visible focus indicator in both color schemes that nothing clips, on the player itself and on every Tab stop of
  its native controls.
- The page SHALL show no captions control. The player's own controls show no chapters: the movie's chapters are
  listed under the player when the event detail gives their times ("The movie player lists the rendered movie's
  chapters").
- It SHALL show the movie in a frame of 16:9 proportions that has its final size before any byte arrives. The
  frame SHALL be at most 768 CSS pixels wide, and no taller than the window leaves below the shared header, which
  stays in place while the page scrolls, and the section heading. A picture of other proportions SHALL be shown
  whole inside it, on a dark surround in both schemes.
- In a window from 320 to 1280 CSS pixels wide, the page SHALL NOT scroll horizontally, and the file name SHALL wrap
  rather than overflow.
- The section SHALL NOT animate, and its heading SHALL scroll with the page rather than stay in place over the
  player.

#### Scenario: A current movie
- **WHEN** the operator opens `2024-07-14 - Kalas`, which is up to date
- **THEN** the page shows a "Movie" section above its chapters that says "Current", names
  `2024-07-14 - Kalas.mp4` with its size, and shows a player whose poster is the thumbnail of `s1710002.mp4`
- **AND** the only request for the movie is one `Range: bytes=0-0` request, the player's address carries that
  answer's entity-tag as `v`, and after five seconds the player is paused at its start

#### Scenario: Playing from the keyboard
- **WHEN** the operator tabs from the page's Edit button to the player of `2024-07-14 - Kalas` and presses Space,
  waits two seconds, and presses Space again
- **THEN** the movie plays for those two seconds and then pauses, and the player shows a visible focus indicator
  throughout

#### Scenario: An outdated movie under its old name
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, whose title changed after its render, so its
  staleness cites `editorial` and `output_renamed`
- **THEN** the "Movie" section says "Outdated" with the sentence on what a render does, names the file under the
  old name `2024-06-27 - Grillning med Grannar.mp4`, and plays that file

#### Scenario: No movie, no section, no request
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, `2024-10-05 - Trasig`, `2024/Blandat` and
  `2024-07-14 - kalas` (which has no render record, although `2024-07-14 - Kalas`'s movie lies at its expected path)
- **THEN** none of these pages shows a "Movie" section, and none of them requests a movie

#### Scenario: A finished render replaces the player
- **WHEN** the operator plays the movie of `2024-06-21 - Midsommar - Dalarna` from the keyboard and pauses it,
  keyboard focus stays on the player, and a forced render of the event, started from elsewhere (another tab, or `POST
  /api/v1/jobs`), finishes while the page is shown
- **THEN** after the page's read the player loads from an address with the new file's entity-tag, keyboard focus is
  on the new player, and it plays the new movie

#### Scenario: A read that finds the same movie keeps playing
- **WHEN** the movie of `2024-06-27 - Grillning med grannar` is playing, and a forced render of the event is
  queued from elsewhere and cancelled before it starts, so the page reads the event again
- **THEN** the player is the same one, still playing, and its position did not jump back

#### Scenario: Edit mode shows no movie
- **WHEN** the operator opens Edit mode on `2024-06-27 - Grillning med grannar` and then leaves it
- **THEN** the "Movie" section is absent while Edit mode is open, and is shown again, paused at its start, after it
  closes

#### Scenario: The player at phone width
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in windows 320 and 390 pixels wide, in both
  color schemes
- **THEN** the page does not scroll horizontally, the frame spans the section's width at 16:9, and the file name
  and the outdated sentence wrap inside it

#### Scenario: The player in a wide window
- **WHEN** the operator opens `2024-07-14 - Kalas` in a window 1280 × 800 pixels and scrolls the frame into view
- **THEN** the frame is 768 × 432 pixels and lies whole between the bottom of the shared header, which stays in
  place while the page scrolls, and the bottom of the window

#### Scenario: Refresh keeps the movie playing
- **WHEN** the movie of `2024-07-14 - Kalas` is playing, 3 seconds in, and the operator presses Refresh
- **THEN** the page shows placeholders for the rest of its content while it reads, and the player is the same
  element, still playing, whose position never went back; after the read the "Movie" section says "Current" again
  and its player's address carries the same entity-tag as before
- **AND** the only request for the movie during and after the Refresh is one `Range: bytes=0-0` request, made when
  the read answered

#### Scenario: Refresh starts the player over
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and a forced render of the event, started from elsewhere,
  replaces its file, and then the operator presses Refresh
- **THEN** after the read the page shows a new player, paused at its start, at an address that carries the new
  entity-tag, and the old address is not used again

#### Scenario: Refresh finds no movie
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and its render record is removed from disk before the
  operator presses Refresh
- **THEN** after the read the page shows no "Movie" section, and keyboard focus stays on the Refresh button

#### Scenario: Refresh that fails takes the movie with the rest
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and the service is stopped before the operator presses Refresh
- **THEN** the page shows its failure as for any read, and no "Movie" section

#### Scenario: The movie's version is shown
- **WHEN** the operator opens `2024-07-14 - Kalas`, whose detail carries the version of its latest render
  (`recorded_at` 2026-10-03 14:02, fingerprint `a1b2c3d4e5f6`)
- **THEN** the "Movie" section's facts say `2024-07-14 - Kalas.mp4`, its size, and "Recorded Oct 3, 2:02 PM ·
  version a1b2c3d4e5f6", with the exact instant in the `<time>` element's `dateTime`

#### Scenario: A movie whose version is not recorded
- **WHEN** the operator opens an event whose staleness shows a movie but whose detail's `movie` is `null` (the
  service could not tell a version, for instance a record without a usable time)
- **THEN** the facts name the file and its size and say nothing of a time or a version

## ADDED Requirements

### Requirement: The movie player lists the rendered movie's chapters

When the event page shows the "Movie" section's player and the event detail gives the movie's chapters, the section
SHALL list them under the player, in a list headed "Chapters" (a level-three heading), in the order of their start
times. The page SHALL take the chapters only from the event detail: each chapter's name and its start in the
rendered movie, in seconds. It SHALL NOT compute, estimate or look up a start time anywhere else (not from the
current chapters and clips of the event, not from clip durations, not from the player's metadata). When the detail
gives no chapters, or gives them in a form the page cannot rely on, the section SHALL show no list, no heading and no
placeholder for one, and SHALL say nothing about it. The chapters are relied on only when there is at least one,
every start is a finite number of seconds of at least 0, the starts strictly increase, and every name is
text that is either empty or not only spaces. The empty name is the event's default chapter as the render
recorded it; the list writes it as the event page does ("Main" when another chapter is named, otherwise
"Clips"), and never invents any other name. A movie of one chapter has nothing to jump between: the section SHALL show no
list for it, as for no chapters (the usual event is one default chapter). The list is the movie's chapters as rendered: an outdated movie lists the chapters it has,
and the section SHALL say so in words with the list ("As rendered"), not by color alone.

**One row per chapter.** Each chapter SHALL be a row with a button as its only control. The row shows the chapter's
number, its name, and its start written as the client writes a place in a clip (`m:ss`, `h:mm:ss` from an hour,
with the fraction of a second only when there is one). The
button's accessible name SHALL be "Jump to chapter N, name, at start". A long name SHALL wrap inside the row.

**Jumping.** Activating a chapter's button SHALL move the player to that chapter's start, to the millisecond, and
start playback, whether or not the movie had been played before, and whether it was playing, paused or at its
start. A jump before the first Play SHALL NOT need the operator to press Play first. Keyboard focus SHALL stay on
the button. A movie that cannot play after a jump SHALL be said as for any playback failure ("The movie player says
what it cannot play"). The page SHALL add no keyboard shortcut for the list: its buttons are reached with Tab and
activated with Enter or Space, in the order of the chapters.

**The current chapter.** The list SHALL mark the chapter the player's position is in: the last chapter whose start is
at or before the position, where a position up to 60 milliseconds before a start counts as at it, because a
browser's seek may land a frame short. A position before that, ahead of the first chapter, marks none. The mark SHALL be words with an
icon ("Current chapter"), never color alone, and the row's button SHALL carry `aria-current="true"` while it is
marked. The mark SHALL follow the position whether the movie is playing, paused or moved with the player's own
controls, and SHALL stay on the right row within half a second of the position. Exactly one row, or none,
SHALL carry it. The page SHALL NOT announce the mark's moves: they happen while the movie plays.

**What the list stays with.** The list SHALL belong to the player it was shown under. When the movie's file is
replaced and the page shows a new player, the list SHALL show the chapters of the detail that read found. While the
page reads the event again the list SHALL stay as it is, with its buttons usable. When a re-read leaves the player
without a list while keyboard focus is in the list, focus SHALL go to the player; when it removes the whole section,
to the page's heading, as for the section. When the section shows a note in the player's place, it SHALL show no
list.

**Motion and size.** The list SHALL NOT animate: the mark moves without a transition, with or without a
preference for reduced motion, and a jump does not scroll the page. In a window from 320 to 1280 CSS pixels wide the
page SHALL NOT scroll horizontally. Under a coarse pointer each button SHALL take a tap anywhere in an area of at
least 44 × 44 CSS pixels around it. Each button SHALL show a visible focus indicator in both color schemes that
nothing clips.

#### Scenario: A list from the detail's chapter times
- **WHEN** the operator opens `2024-06-21 - Midsommar - Dalarna`, whose detail gives the chapters "Förberedelser"
  at 0 s, "Majstången" at 74 s and "Dans" at 301 s
- **THEN** under the player a "Chapters" list shows three rows, "1 Förberedelser 0:00", "2 Majstången 1:14" and
  "3 Dans 5:01", and the first row is marked "Current chapter"
- **AND** the buttons are named "Jump to chapter 2, Majstången, at 1:14" and so on

#### Scenario: Jumping before the first Play
- **WHEN** the operator opens that page and, without pressing Play, activates "Dans"
- **THEN** the movie starts playing from 301 s (within one frame), the "Dans" row is marked "Current chapter" and no
  other row is, and keyboard focus is still on the "Dans" button

#### Scenario: Jumping from the keyboard
- **WHEN** the operator tabs from the player to the list, tabs to the second button and presses Enter
- **THEN** the movie plays from 74 s, and the second row is marked; pressing Tab moves focus to the third button

#### Scenario: The mark follows the player's own controls
- **WHEN** the movie is paused, and the operator drags the player's own timeline to 310 s
- **THEN** within half a second "Dans" is the only marked row, and the page announced nothing

#### Scenario: The mark is words, not colour
- **WHEN** the operator views the list in both color schemes, and with forced colors
- **THEN** the marked row says "Current chapter" with an icon, its button has `aria-current="true"`, and the other
  rows have neither

#### Scenario: The default chapter is written as the event page writes it
- **WHEN** the operator opens an event whose detail gives the chapters "" at 0 s and "Dans" at 80 s
- **THEN** the list shows "1 Main 0:00" and "2 Dans 1:20", and the first button is named "Jump to chapter 1, Main,
  at 0:00"

#### Scenario: One chapter, nothing to jump to
- **WHEN** the operator opens an event whose detail gives the one chapter "" at 0 s
- **THEN** the section shows its player and facts and no "Chapters" heading or list

#### Scenario: No chapter data, no list
- **WHEN** the operator opens `2024-07-14 - Kalas`, whose movie was rendered before chapter times were recorded, so
  its detail gives no chapters
- **THEN** the "Movie" section shows its player and facts and no "Chapters" heading or list, and no chapter start
  is derived from the event's clips

#### Scenario: Chapters that cannot be relied on
- **WHEN** a detail gives chapters whose starts do not increase, or one whose name is only spaces, or a start that is not a
  number
- **THEN** the section shows no list at all, rather than the part that seems right

#### Scenario: An outdated movie lists what it has
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, whose chapters changed after its render
- **THEN** the "Chapters" list holds the chapters of the movie as rendered and says "As rendered"

#### Scenario: A new render replaces the list with its player
- **WHEN** a forced render of `2024-06-21 - Midsommar - Dalarna` finishes while its page is shown, and the read finds
  a new entity-tag and a fourth chapter
- **THEN** the page shows the new player and a list of four chapters, and the old player's position is not carried
  over to the marks

#### Scenario: The list at phone width
- **WHEN** the operator opens that page in windows 320 and 390 pixels wide, in both color schemes
- **THEN** the page does not scroll horizontally, a long chapter name wraps inside its row, and under a coarse
  pointer each button takes a tap anywhere in 44 × 44 pixels around it

#### Scenario: Reduced motion
- **WHEN** the operator has asked for reduced motion and activates "Dans"
- **THEN** the mark moves to its row at once, no transition or animation runs, and the page does not scroll

#### Scenario: A re-read removes the list while it has focus
- **WHEN** keyboard focus is on a chapter button and a re-read the page started by itself finds a movie with no
  chapters
- **THEN** the list is gone and keyboard focus is on the player
