## MODIFIED Requirements

### Requirement: A read in progress is shown as a placeholder and announced

While a screen reads its own content from the service, it SHALL show placeholder rows shaped like its
content in place of the content. A screen's own content is what the screen is about: the event list's read
of the list, an event page's read of its event, and, where the event page has an editor, the editor's
first read of the event's document. It SHALL also show a status message naming the read ("Scanning
events…" on the list, "Reading event…" on an event page), which assistive technology announces.
Placeholders SHALL carry no event data, and SHALL NOT show an earlier state of the screen as current. Other
reads a screen makes, such as reading one job's state or re-reading a document only for its version, are
not reads of its content, and this requirement does not govern them.

The one exception is a re-read the client starts by itself because events changed, while the screen is
shown or when a hidden list is shown again (see "A shown screen re-reads in place when events change").
There, the screen keeps its current content, marked as updating, instead of showing placeholders.

The other exception is the player of an event page's "Movie" section. An operator's Refresh of an event page
that shows the section SHALL keep it, with its player as it is, while the page reads, as "The event page plays
the event's rendered movie" requires. The section SHALL show nothing of the earlier read that the read may
change while it runs: not its verdict, its file name, its size or its outdated sentence. Its heading and its
player SHALL remain, so that the page never shows an earlier state of the event as current.

#### Scenario: A slow list read
- **WHEN** the events list response takes two seconds
- **THEN** during those seconds the list shows placeholder rows and the announced message "Scanning events…",
  and no event from an earlier read

#### Scenario: A slow event read
- **WHEN** the operator opens `2024-09-01 - Sommarlov` and its read takes two seconds
- **THEN** during those seconds the page shows its heading, placeholder rows and the announced message
  "Reading event…"

#### Scenario: A Refresh keeps the movie player and nothing else
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and the operator presses Refresh, and the read takes
  two seconds
- **THEN** during those seconds the page shows its heading as a placeholder, placeholder rows and the announced
  message "Reading event…", and the "Movie" section shows its heading and its player, still playing, with no
  "Current" or "Outdated", no file name, no size and no outdated sentence

#### Scenario: A re-read after a finished render keeps the rows
- **WHEN** the list is shown, the render of `2024-06-27 - Grillning med grannar` completes, and the
  re-read takes two seconds
- **THEN** during those seconds the list keeps its rows, marked as updating, and shows no placeholder rows

#### Scenario: Reading a job shows no placeholders
- **WHEN** `2024-10-05 - Trasig`'s page is shown and reads its failed job's error text from the service
- **THEN** the page keeps its content while that read runs, and shows no placeholder rows

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

### Requirement: Thumbnails never hold up or break a page

Thumbnails SHALL NOT delay the event page. Its chapters and clip facts SHALL be shown as soon as the event
detail is read, whether or not any thumbnail has arrived. The page SHALL request a clip's thumbnail only when
its row is on or near the visible part of the page. A clip's thumbnail SHALL have the same address every time
it is shown while the clip is unchanged on disk, so that a row shown again (after a Refresh, or on entering or leaving Edit mode) is served from
the browser's cache while the service's caching headers allow it.

While a thumbnail loads, its box SHALL show a placeholder. That placeholder SHALL stand still when the
operating system asks for reduced motion. A row SHALL NOT change size or position when its thumbnail
arrives, or when it fails.

When the service cannot give a clip's thumbnail (it answers with a failure status, or the image cannot be
shown), the box SHALL show a neutral "No preview" placeholder with an icon, named "No preview for <name>"
for assistive technology, where <name> is the clip's name as its row shows it (see "Every clip row shows a
frame from its clip"). The failure SHALL NOT raise an alert or a toast, SHALL NOT change the
clip's status, and SHALL NOT be retried automatically while the row stays shown.

**When no preview can be made at all.** A failed image says nothing about why. For each thumbnail that fails to
show, the page SHALL therefore make one further request for the same address, only to read the service's answer,
and SHALL NOT show anything of that answer's body in the clip's row. The answer is the clip's own failure when
it is a 502 that carries the thumbnail failure kind `thumbnail_failed`. A 502 that carries no thumbnail failure
kind and no event `failure` (the service's thumbnail cache or its `config.yaml` is at fault, so that no clip
could have a preview) SHALL be counted as the service's. Any other answer is counted nowhere, as is none: a 502
whose `failure` says that the event itself could not be read is not a thumbnail fault. The further request SHALL
be made behind the page's own requests (low priority).

When at least three thumbnails shown on the page have failed as the service's, the page SHALL show
one note, once for the page and not per clip: "Previews are unavailable. The service could not make thumbnails;
run `auto-reel thumbs` on the server to see why." The note SHALL be shown in the read view and in Edit mode, in
the same place above the clips. It SHALL be part of the page's content: no alert, no toast and no announcement,
and with a name for assistive technology that does not need the colour of the warning. It SHALL leave when fewer
than three such failures are shown, such as after a Refresh that finds the service working. Failures that are
the clips' own SHALL never raise it, however many clips fail that way.

In a window 390 CSS pixels wide, the thumbnail SHALL stay in the clip's row beside its facts, without
horizontal scroll, and no fact of a row SHALL overlap another.

#### Scenario: A clip whose frame cannot be read says "No preview"
- **WHEN** the operator opens `2024-10-05 - Trasig`, whose only clip `trasig.mp4` is an empty file
- **THEN** the row shows the "No preview" placeholder with its icon, its status and facts read as before, the
  page shows no alert, toast or note about it, and the service received at most two thumbnail requests for
  `trasig.mp4`: the image's, and the one that reads why it failed

#### Scenario: A fault of the service's thumbnail cache is said once
- **WHEN** the service's thumbnail cache directory cannot be written, and the operator opens
  `2024-06-27 - Grillning med grannar`, whose four clips are on disk
- **THEN** each of the four rows shows the "No preview" placeholder, and the page shows one note, "Previews are
  unavailable…", above the clips; no alert or toast is raised
- **WHEN** the operator enters Edit mode
- **THEN** the note is shown in the same place, once

#### Scenario: Clips that cannot be decoded raise no note
- **WHEN** an event of four clips is opened and the service answers each thumbnail with a 502 that carries the
  thumbnail failure kind `thumbnail_failed`
- **THEN** each row shows the "No preview" placeholder, and the page shows no note

#### Scenario: An event that becomes unreadable raises no thumbnail note
- **WHEN** the operator has opened `2024-06-27 - Grillning med grannar`, its `reel.yaml` is then made unreadable,
  and the service answers the thumbnails of three of its clips with a 502 that carries an event `failure`
- **THEN** each of the three rows shows the "No preview" placeholder, and the page shows no note

#### Scenario: Two failures are not a pattern
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` and the service answers the thumbnails of two
  of its four clips with a 502 that carries no thumbnail failure kind, and the others with images
- **THEN** two rows show "No preview", and the page shows no note

#### Scenario: The note leaves with the fault
- **WHEN** the note is shown, the cache directory is made writable, and the operator presses Refresh
- **THEN** the four thumbnails are shown, and the page shows no note

#### Scenario: Only rows near the view are requested
- **WHEN** the operator opens an event of 60 clips in one chapter, in a window 1280 by 800 pixels, and then
  scrolls to its end
- **THEN** fewer than 60 thumbnails are requested before the scroll, and all 60 after it

#### Scenario: Arriving thumbnails move nothing
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn` and every thumbnail arrives after the clip
  facts are shown
- **THEN** no clip row changes its size or position as the images arrive

#### Scenario: A slow thumbnail does not hold up the page
- **WHEN** every thumbnail response of `2024-06-27 - Grillning med grannar` is held back for five seconds
- **THEN** the page shows its heading, verdict and all four clip rows with their facts before the images,
  and each box shows the loading placeholder until its image arrives

#### Scenario: Placeholders stand still under reduced motion
- **WHEN** the operator's system asks for reduced motion and thumbnails are loading
- **THEN** their placeholders are shown without any animation

#### Scenario: Thumbnails at phone width
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn` in a window 390 pixels wide, in the table
  view and in Edit mode
- **THEN** the page does not scroll horizontally, every clip still shows its thumbnail, position, file name,
  status, size and modification time in its row, and no two of them overlap

### Requirement: Edit mode lists, adds and removes a clip's cuts

A clip's cuts are the spans of it that the movie leaves out. Each has a start and an end, in seconds from the
clip's start, and may have a reason. In Edit mode, every included or new clip that `reel.yaml` does not exclude (a clip on disk that a chapter
lists, or will list once the edits are saved) SHALL offer a **Cuts** control. The control SHALL say how many
cuts the clip has and, when it has any, how much time they cut out. Pressing it SHALL show or hide a panel
under the clip's row and SHALL leave keyboard focus on the control. The control SHALL say to assistive
technology whether the panel is shown, and SHALL name the clip as its row names it. In the keyboard order, the
Cuts control SHALL come after the row's other controls, and the panel's controls straight after it.

The panel SHALL list the clip's cuts in their order, each with its number in the list, its start and end, its
length and its reason in words. A clip without cuts SHALL say that the whole clip plays. A missing clip that
`reel.yaml` does not exclude SHALL show, in its row, how many cuts it has, and SHALL offer no Cuts control: its file is not on disk to cut, and
removing it from `reel.yaml` takes its cuts with it. Once the operator removes it, its row SHALL NOT show its
cuts any more, since the save drops them. An ignored clip SHALL have no cuts and no Cuts control.
An excluded clip is not in the movie, so its cuts do not apply: its row SHALL show no cuts and SHALL offer no
Cuts control, whether the clip is on disk or missing. Its cuts stay in `reel.yaml`, and a save SHALL write
them back unchanged.

**Times.** A cut's times are places in the clip, not moments in a day, so the format for moments ("Times are
written one way on every screen") does not apply to them. The page SHALL write a time as minutes and seconds
(`1:02.35`), with hours in front from one hour on (`1:01:15.5`). It SHALL write up to three decimals and no
trailing zero. It SHALL write a length under a minute in seconds (`1.5 s`), and from a minute on as a time. The time a clip's cuts cut out SHALL count, once,
every span that one or more of its cuts covers, as the render does.

**Adding a cut.** The panel SHALL take a start and an end, typed, and add the cut on request. Spaces around a
time SHALL be ignored. A time SHALL be accepted in each of these forms, with an optional decimal part of one
to three digits after `.` or `,`:

- seconds (`75.5`)
- minutes and seconds, the seconds as two digits below 60 (`1:15.5`)
- hours, minutes and seconds, the minutes and seconds each as two digits below 60 (`1:01:15.5`)

The cut SHALL be refused, and nothing added, when either time is empty or in no accepted form, or has more
than three decimals. It SHALL also be refused when its end is not after its start, when it shares more
than an instant with another cut of the clip that is not removed, or when it ends after the clip's length
once the page knows that length (below). A refusal SHALL be shown at the field it concerns, which SHALL
receive keyboard focus. It SHALL be announced, and it SHALL say what to type, which cut the new one overlaps,
or the clip's length. A cut that only touches another, the end of one being the start of the other, SHALL
be accepted. Times SHALL be compared to the millisecond, as they are typed and written, so a cut that starts
where another is shown to end touches it.

An added cut SHALL take its place in the list by its start, after every cut that starts at the same time or
earlier. It SHALL be saved with the reason `manual`. After an addition:

- both fields SHALL be empty again, with keyboard focus on the start field
- the addition SHALL be announced with the cut's times, the clip's name and its new cut count

**The clip's length.** The page knows a clip's length from one of two places, and the first it has wins: the
length the clip's preview has read from the clip's file in this Edit mode ("Edit mode previews a clip on
request"), else the duration the event detail gives the clip when it is not null (a thumbnail of the clip was
made before). The preview's length wins because it is the one Set From and Set To write times from, so a cut
set at the end of the clip is never refused. A null duration is unknown, never zero. When the page knows the
length from neither, the panel SHALL say that the page does not know the clip's length, that a cut that runs
past the clip's end stops there, and that a cut over the whole clip leaves the clip out of the movie, and it
SHALL NOT refuse a cut for its length. Once the page knows the length, from either place, the panel SHALL
state it beside its fields, SHALL refuse a cut that ends after it, and SHALL mark each listed cut that ends
after it ("A clip's preview sets cut times at the playhead and plays the clip as the movie will"), and
it SHALL still say that a cut over the whole clip leaves the clip out of the movie. The
duration of a clip the event detail gives SHALL NOT be sent anywhere, and neither length SHALL be saved.

**What a whole-clip cut does to a title card.** Wherever the panel says that a cut over the whole clip leaves
the clip out of the movie, it SHALL add that when the clip is its chapter's title clip, the chapter's title card
moves to the next clip of the chapter that plays. The render places a chapter's title card before the first
clip it plays when the title clip is cut away, and adds none to a chapter in which every clip is cut away. The
page does not know which clip is a chapter's title clip, so the sentence is conditional and the same for every
clip.

**Removing a cut.** Each cut SHALL offer **Remove**, which names the clip and the cut. A cut read from
`reel.yaml` SHALL then stay listed in its place, marked as removed when the edits are saved, with an **Undo**
that puts it back. Keyboard focus SHALL move to that Undo, and after an Undo to the cut's Remove. An Undo that
would make the cut share more than an instant with a cut added in this Edit mode SHALL be refused, as adding
that cut would be: the cut stays removed, keyboard focus stays on its Undo, and the refusal is shown in the
cut's row, announced, and names the cut to remove first. Two cuts read from `reel.yaml` that overlap there
SHALL NOT refuse each other's Undo: an Undo only goes back to what was read. A cut added in this Edit mode SHALL simply be gone.
Keyboard focus SHALL then move to the Remove of the cut that took its place, or of the cut before it, or to
the start field when no cut is left. Each removal and each Undo SHALL be
announced. After any addition, removal or Undo, the control holding keyboard focus SHALL be fully visible,
not covered by the page header, the chapter's heading or the save bar.

**Typed but not added.** While a panel's fields hold a typed time that was not added, the event SHALL count as
having unsaved changes. The save bar SHALL say that a cut was typed but not added, naming the clip as its row
names it when only one clip holds one, also after an edit that changes that name. Save, and Overwrite with mine after a conflict, SHALL say that they are unavailable until
the cut is added or its fields are cleared. Hiding the panel SHALL keep what was typed, and so SHALL moving the
clip to another chapter. The Cuts control of each clip whose panel holds such a time SHALL say so in words, at
every width and to assistive technology, also while its panel is hidden, so that the clip holding Save back
is found on its row. Reset SHALL empty every panel's fields.

While a save is in flight, the panel's fields, Add cut, Remove and Undo SHALL say that they are unavailable
and change nothing when used. The Cuts control SHALL still show and hide its panel, since that changes nothing
to save.

The Cuts control and every control in the panel SHALL take a tap anywhere in an area of at least 44 × 44 CSS
pixels around it when the primary pointer is coarse, reaching no other control, as every button does ("Every
control is large enough to touch"). With every panel hidden, the Cuts control SHALL NOT make a row taller in a
window 320 or 390 pixels wide. No panel SHALL make the page scroll horizontally from 320 pixels up.

#### Scenario: Opening a clip's cuts
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator presses the Cuts control of
  `s1710001.mp4`
- **THEN** a panel under its row says that the whole clip plays and offers a start and an end field and Add
  cut. Keyboard focus is still on the Cuts control, which says that its panel is shown.

#### Scenario: Adding a cut with typed times
- **WHEN** in that panel the operator types `0` as the start and `1,5` as the end and presses Enter
- **THEN**
  - the panel lists one cut, from `0:00` to `0:01.5`, 1.5 s long, its reason "Cut by hand"
  - the Cuts control reads "1 cut · −1.5 s"
  - both fields are empty, with keyboard focus on the start field
  - the addition is announced
  - the save bar says that 1 cut was added

#### Scenario: Every accepted form of a time
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from ` 0:00:01.25 `
  to `0:02.5`, and then one from `4` to `0:06`
- **THEN** the panel lists the cuts from `0:01.25` to `0:02.5` and from `0:04` to `0:06`, in that order, and the
  Cuts control reads "2 cuts · −3.25 s"

#### Scenario: A time the page cannot read
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `1:5` as the start and
  `2` as the end and asks to add the cut, then types `-1` as the start, then `0.1234`
- **THEN** each is refused at the start field, which keeps keyboard focus. The first two are refused as no time
  the page can read, naming the three forms. The last is refused for its four decimals. No cut is added.

#### Scenario: A cut that does not end after it starts
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `3` as the start and
  `2` as the end and asks to add the cut
- **THEN** the cut is refused at the end field, which receives keyboard focus, saying that a cut must end after
  it starts, and no cut is added

#### Scenario: A clip never previewed is not checked for length
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose detail gives a duration of `null`
  and whose preview was not opened in this Edit mode, the operator adds a cut from `5` to `7`
- **THEN** the cut is accepted and listed, and the panel says that the page does not know the clip's length and
  that a cut that runs past the clip's end stops there

#### Scenario: A clip whose duration the service gives is checked before any preview
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, whose detail gives a duration of `6.02`
  and whose preview was not opened in this Edit mode, the operator adds a cut from `5` to `7`
- **THEN** the panel says that the clip ends at `0:06.02`, the cut is refused at the end field, which receives
  keyboard focus, saying that `0:07` is after the clip's end at `0:06.02`, and no cut is added
- **WHEN** the operator types `0:06.02` as the end and adds the cut
- **THEN** the cut from `0:05` to `0:06.02` is listed

#### Scenario: The panel says where a whole-clip cut sends the title card
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator opens the Cuts panel of
  `s1710001.mp4`, the first clip of its chapter, before and after opening its preview
- **THEN** both times the panel says that a cut over the whole clip leaves the clip out of the movie and that,
  when it is the chapter's title clip, the chapter's title card moves to the next clip of the chapter that plays

#### Scenario: A cut that overlaps another
- **WHEN** `s1710001.mp4` of `2024-06-27 - Grillning med grannar` has a cut from `0:00` to `0:01.5`, and the
  operator adds one from `1` to `2`
- **THEN** it is refused, saying that it overlaps cut 1 (`0:00` to `0:01.5`)
- **WHEN** the operator then adds one from `1.5` to `2`
- **THEN** it is accepted and listed second

#### Scenario: Removing a cut read from reel.yaml, and undoing it
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds with the reason `black`, and in Edit mode the operator presses that cut's Remove
- **THEN** the cut stays listed, marked as removed when the edits are saved, with an Undo that has keyboard
  focus, and the save bar says that 1 cut is removed
- **WHEN** the operator presses that Undo
- **THEN** the cut is listed as before, its reason "Black frames", keyboard focus is on its Remove, and the page
  shows no unsaved changes

#### Scenario: An Undo that would overlap is refused
- **WHEN** with that same `reel.yaml`, the operator removes the cut from 0 to 1.2 seconds of `s1710003.mp4`, adds
  one from `1` to `2`, and presses the removed cut's Undo
- **THEN** the Undo is refused, saying that cut 1 overlaps cut 2 (`0:01` to `0:02`) and that cut 2 must be
  removed first. Cut 1 stays removed, keyboard focus stays on its Undo, and the save bar still says that 1 cut
  was added and 1 removed.

#### Scenario: Read cuts that overlap do not refuse each other's Undo
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` cuts from 0 to 3 seconds
  and from 2 to 4 seconds, and the operator removes both and presses each one's Undo
- **THEN** both are listed as before, and the page shows no unsaved changes

#### Scenario: A cut starts where another is shown to end
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 3.2033333
  seconds, listed as ending at `0:03.203`, and the operator adds one from `3.203` to `4`
- **THEN** it is accepted and listed second

#### Scenario: Removing a cut added in this Edit mode
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from `0` to `1.5`
  and presses its Remove
- **THEN** the panel says that the whole clip plays again, keyboard focus is on the start field, and the page
  shows no unsaved changes

#### Scenario: A missing clip's cuts are shown, not edited
- **WHEN** the `reel.yaml` of `2024-09-01 - Sommarlov` gives the missing `borttagen.mp4` a cut from 0 to 2
  seconds, and the operator opens Edit mode
- **THEN** the row of `borttagen.mp4` says that it has 1 cut and offers Remove but no Cuts control, while
  `s1710002.mp4` and `s1710004.mp4` offer theirs
- **WHEN** the operator presses Remove on `borttagen.mp4`
- **THEN** its row is listed as removed when the edits are saved and no longer says that it has a cut

#### Scenario: An excluded clip offers no cuts
- **WHEN** the operator enters Edit mode on an event whose `reel.yaml` excludes `s1710002.mp4`, which is on
  disk and has a cut from `0` to `1.5`
- **THEN** its row offers no Cuts control and shows no cut count, the other clips of the chapter still offer
  theirs, and saving another edit writes the cut back unchanged

#### Scenario: An ignored clip has no cuts
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the ignored `s1710004.mp4` offers no Cuts control, and every clip `Main` and `Kvällen` play offers one,
  the new `Kvällen/s1710004.mp4` included

#### Scenario: A cut typed but not added holds Save back
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `2` as the start, adds
  nothing, and hides the panel
- **THEN** the save bar says that a cut was typed on `s1710001.mp4` but not added, and Save says that it is
  unavailable. Opening the panel again shows `2` in the start field.
- **WHEN** the operator then presses the browser's Back
- **THEN** the page stays and asks "Discard unsaved changes?"

#### Scenario: A typed cut moves with its clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `2` as the start of a cut on
  `Kvällen/s1710002.mp4`, which `Kvällen` names `s1710002.mp4`, adds nothing, and moves that clip to `Main`
  with Move clips
- **THEN** the save bar now says that a cut was typed on `Kvällen/s1710002.mp4` but not added, Save says that
  it is unavailable, and the clip's Cuts panel, now in `Main`, is still shown with `2` in the start field

#### Scenario: Hidden panels holding typed text are marked on their rows
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator types `5` in the start field of `s1710002.mp4`
  and hides its panel, then types `1:00` in the start field of `s1710004.mp4` and hides that panel
- **THEN** the save bar says that cuts were typed on 2 clips but not added, and the Cuts controls of those two
  clips, and of no other, say "typed" and that a cut was typed but not added
- **WHEN** the operator clears the field of `s1710002.mp4`
- **THEN** its Cuts control no longer says so, and the save bar names `s1710004.mp4`

#### Scenario: Cut controls wait for a save
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its panel shown, the
  operator presses Save and the service has not answered yet
- **THEN** the start and end fields, Add cut and the cut's Remove say that they are unavailable, typing and
  pressing them change nothing, and the Cuts control still hides and shows the panel

#### Scenario: Cuts on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** each clip row is as tall as on the page before this change, and a tap anywhere in a 44 × 44 pixel area
  around the Cuts control of `Kvällen/s1710002.mp4` reaches that control and no other
- **WHEN** the operator opens that panel and adds a cut from `0` to `1`
- **THEN** the page does not scroll horizontally, and a tap anywhere in a 44 × 44 pixel area around each of the
  panel's fields, Add cut and the cut's Remove reaches that control and no other
