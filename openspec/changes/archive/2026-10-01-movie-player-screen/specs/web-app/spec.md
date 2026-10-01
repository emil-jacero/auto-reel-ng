## ADDED Requirements

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
keyboard focus, the new one SHALL receive it. The old address SHALL never be used for the new file. A Refresh, like
opening the page or leaving Edit mode, replaces the page's content with placeholders while it reads (see "The event
page shows the event's chapters and clips"). It therefore stops playback, and the section returns with a new
player, paused at its start, at the address of the entity-tag that read finds.

**Nothing loads before Play.** Opening, refreshing or returning to the page SHALL NOT request any byte of the movie
other than the one-byte answer above, and SHALL NOT start playback. Playback SHALL start only from the operator's
action on the player. The player SHALL NOT loop and SHALL NOT be muted by the page. Its poster SHALL be the thumbnail
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

**The player.**
- It SHALL be the browser's own media player with its native controls. It SHALL be named by the section's heading.
- The page SHALL add no keyboard shortcut of its own. The player SHALL be reachable with Tab, and SHALL show a
  visible focus indicator in both color schemes that nothing clips, on the player itself and on every Tab stop of
  its native controls.
- The page SHALL show no captions control and no chapter list. No chapter times reach the client: the service
  gives none, and the browser exposes none of the movie's chapters.
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

#### Scenario: Refresh starts the player over
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and the operator presses Refresh
- **THEN** the page shows its placeholders while it reads, and then a "Movie" section whose player is paused at its
  start, at an address that carries the same entity-tag as before

### Requirement: The movie player says what it cannot play

The movie section SHALL say, in words, why it cannot offer or play a movie, by cause. It SHALL never leave the
operator with a silent or black player and nothing said. It SHALL never show a fact it did not receive.

**When the movie cannot be fetched.** These answers to the one-byte request SHALL replace the player:
- **404:** the service has no movie file for the event (for example, something other than a file now lies where
  the movie belongs), with the service's detail.
- **502:** the movie could not be read, with the service's detail and the failure kind in words when the answer
  carries one. A movie file that cannot be read is named by its file name, never a server path.
- **416:** the movie file is empty.
- **No answer, or an answer the route does not publish:** the same words the event page uses for its own read.

These notes are part of the page's content and SHALL NOT be announced as alerts. The same holds when a re-read the
page starts by itself gets one of these answers. Focus is never dropped:
- Whenever a note replaces a player that had keyboard focus, the note SHALL receive it.
- Whenever a player replaces a note that had keyboard focus, the new player SHALL receive it.
- When a re-read finds that the event no longer has a rendered movie, and the section that disappears held keyboard
  focus, the page's heading SHALL receive it.

**When playback fails.** After the operator starts playback:
- **No picture.** When the browser has loaded the movie but reports no picture size, it plays the sound of a
  movie whose picture it cannot show, such as a legacy MPEG-4 movie adopted with `auto-reel adopt-renders`, and it
  raises no error. The section SHALL say that this browser cannot show the movie's picture and plays its sound
  only. It SHALL offer to download the movie, and the player SHALL stay.
- **A playback error.** The page SHALL ask the service for the first byte of the movie again, and answer by cause:
  - The entity-tag differs from the one the player loaded: the section SHALL say that the movie file changed while
    it played, and offer "Load the new movie". That control SHALL replace the player with one at the new address,
    without starting playback, and SHALL give it keyboard focus.
  - The entity-tag is the same: the section SHALL say that this browser could not play the movie, with the
    browser's error in words. When the browser reports a network error, it SHALL say instead that the movie could
    not be loaded, with that error in words, never that the browser cannot play it. Either way it SHALL offer to
    download the movie, and "Try again", which SHALL replace the player with a new one at the same address,
    without starting playback, and SHALL give it keyboard focus.
  - Any other answer: the note for that answer, as when the movie cannot be fetched, in place of the player.

These notes follow the operator's action, so each SHALL be announced once, when it appears: a failure assertively,
and the no-picture warning politely, through a region that exists before its words. Downloading SHALL
save the file under its own name. A control in these notes SHALL be reachable from the keyboard, and under a
coarse pointer SHALL take a tap anywhere in an area of at least 44 × 44 CSS pixels around it.

#### Scenario: Something other than a file where the movie belongs
- **WHEN** `2024-07-14 - Kalas`'s movie file is replaced on disk by a folder of the same name, so its staleness still
  cites no reason, and the operator opens its page
- **THEN** the "Movie" section says that the service has no movie file for this event, with the service's detail,
  shows no player, and no alert is announced

#### Scenario: A movie the service cannot read
- **WHEN** `2024-07-14 - Kalas`'s movie file cannot be read for lack of permission, and the operator opens its page
- **THEN** the "Movie" section says the movie could not be read, with a detail that names
  `2024-07-14 - Kalas.mp4` and the reason, contains no absolute path, and shows no player

#### Scenario: The service does not answer
- **WHEN** the one-byte request for `2024-07-14 - Kalas`'s movie gets no answer
- **THEN** the "Movie" section says the service is not reachable, with what to do, and shows no player

#### Scenario: A legacy movie plays its sound only
- **WHEN** an event's movie is a legacy MPEG-4 Part 2 file adopted with `auto-reel adopt-renders`, and the operator
  plays it in Chrome
- **THEN** the section says that this browser cannot show the movie's picture and plays its sound only, the player
  stays, and the offered download saves the file under its own name

#### Scenario: The movie file changes while it plays
- **WHEN** the operator plays a movie in Chrome, its file is replaced on disk by another movie, and the operator
  seeks past what was loaded, so the browser reports a playback error
- **THEN** the section says that the movie file changed while it played and offers "Load the new movie"
- **AND** activating it from the keyboard shows a paused player at the new file's address, with keyboard focus, and
  that player plays the new file

#### Scenario: Try again after a playback error
- **WHEN** the operator plays the movie of `2024-07-14 - Kalas` and the browser's requests for the movie fail while
  the one-byte request still answers with the same entity-tag
- **THEN** the section says that this browser could not play the movie, with the browser's error, and offers
  "Try again" and "Download the movie"
- **AND** once the requests answer again, activating "Try again" from the keyboard shows a paused player at the same
  address, with keyboard focus, and that player plays the movie

#### Scenario: A player that replaces a focused note takes the focus
- **WHEN** the movie file of `2024-06-27 - Grillning med grannar` cannot be read when the operator plays it from
  the keyboard, so a note replaces the player and receives keyboard focus, and the file is readable again when a
  forced render of the event, queued from elsewhere and cancelled, makes the page read the event again
- **THEN** a player replaces the note, and keyboard focus is on the new player

#### Scenario: Notes stay inside a phone-width window
- **WHEN** the section shows any of these notes in a window 320 pixels wide
- **THEN** the page does not scroll horizontally, and the note's words and detail wrap inside the section

## MODIFIED Requirements

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
movie file that the service's response does not carry. The verdict and the render region SHALL name no movie
file. The one place the event's page names its movie file is its "Movie" section, which takes the name from the
movie route's own answer (see "The event page plays the event's rendered movie"). In this case that is the old
name.

#### Scenario: The page of a renamed event
- **WHEN** the title of `2024-06-27 - Grillning med grannar` was changed after its last render, its movie is
  still on disk under the old name, and the operator opens its page in a window 390 pixels wide
- **THEN** the page says it needs a render, "edited since last render, movie name changed", and, on a line
  of its own, "The next render saves the movie under its new name. The movie under its old name stays on
  disk."
- **AND** the render region names no movie file, the "Movie" section names the movie under its old name
  `2024-06-27 - Grillning med Grannar.mp4`, and the page does not scroll horizontally, in a window 390 or 320
  pixels wide and in either color scheme

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
