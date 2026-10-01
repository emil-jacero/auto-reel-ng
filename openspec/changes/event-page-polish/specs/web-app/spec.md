## MODIFIED Requirements

### Requirement: The event page shows the event's chapters and clips

An event's page SHALL show, from the event detail the service returns:

- the event's title, or its folder name when it has no title, with its date, location and description
  when present. When the heading shows a title that differs from the event's folder name, the page SHALL
  also show the folder name as secondary text, and SHALL give it to assistive technology as the heading's
  description, so that two events with the same title and date can be told apart.
- whether it needs a render, with every reason in words, or that it is up to date
- its latest job's status and time, when it has one
- counts of its clips, their total size, and its new, missing and ignored clips

The verdict and the latest job SHALL be shown together, in the one region that holds the page's render
controls, between the page's heading and its chapters. The clip counts SHALL be shown with the event's facts
under the heading, not between that region and the chapters.

Each chapter SHALL be shown as a table, in the order the service returns, with the default chapter's clips
under the label `Main` when the event also has named chapters. Each chapter SHALL first list the clips it
plays, in play order, each with its position in the chapter, numbered from 1. After them it SHALL list the
clips the event ignores, marked as ignored and with no position, because an ignored clip is not part of the
play order. A chapter's heading SHALL count the clips it plays, followed by the number of its ignored clips
when it has any. Every clip SHALL be listed with its name, its status in words, its size and its modification
time. A new, missing or ignored clip SHALL show its status as a status label. An included clip, the usual
case, SHALL show its status as quiet words with its icon, without a label's fill or edge, so that the other
statuses stand out. A clip the service reports without a size or time (a missing clip) SHALL show those as
absent, never as zero or a placeholder date. When `reel.yaml` lists clips that are missing from disk, the
page SHALL name them in a warning above the chapters.

A clip's name SHALL be its file name while every clip its chapter lists lies in the chapter's own folder
(the event folder, for the default chapter). A chapter that lists a clip from another folder SHALL name each
of its clips by its path inside the event folder, so that no two of its rows read alike.

The page SHALL read the event from the service when it opens and whenever the operator refreshes it. While
that read runs, the page SHALL show placeholders in the shape of what it will show: its heading, its facts
line, its render region, and clip rows laid out as the loaded rows are, each with its thumbnail box of the
loaded size. The heading SHALL show a placeholder, never a name that the read may replace, and SHALL still be
named by the event's folder name for assistive technology. The placeholders SHALL fit the window as the
loaded page does, without horizontal scroll from 320 CSS pixels up.

#### Scenario: Chapters and clips appear in play order
- **WHEN** an event has root clips and a `Kvällen` chapter
- **THEN** the page shows a `Main` table and a `Kvällen` table, each listing the clips it plays in the order
  the service returns, numbered from 1

#### Scenario: Every clip status is visible
- **WHEN** an event has an included clip, a NEW clip in a named chapter, a MISSING clip and an IGNORED clip
- **THEN** each is listed in its chapter with its status in words: the new, missing and ignored clips as
  status labels, and the included clip as the quiet word "Included" with its icon; and the counts line
  reports one new, one missing and one ignored clip

#### Scenario: An ignored clip has no position
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose `reel.yaml` ignores its root clip
  `s1710004.mp4`
- **THEN** `Main` lists `s1710001.mp4` at position 1 and then `s1710004.mp4`, marked as ignored and with no
  position, as Edit mode lists that chapter, and `Main`'s heading counts "1 clip" and "1 ignored"

#### Scenario: A new clip the service lists after an ignored one is numbered before it
- **WHEN** the root folder of `2024-08-20 - Två kapitel - Tjörn` also holds a NEW clip `s1710009.mp4`, which
  the service lists after the ignored `s1710004.mp4` because it sorts after it on disk
- **THEN** `Main` lists `s1710001.mp4` at position 1, `s1710009.mp4` as new at position 2, and then
  `s1710004.mp4`, marked as ignored and with no position, in the order Edit mode lists them

#### Scenario: A clip from another folder is named by its path
- **WHEN** `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its root
  chapter and ignores the root clip `s1710004.mp4`, as a hand edit or a render's adoption of that NEW clip
  leaves it
- **THEN** `Main` names its rows `s1710001.mp4`, `Kvällen/s1710004.mp4` and `s1710004.mp4`, and `Kvällen`
  still names its rows `s1710002.mp4` and `s1710003.mp4`

#### Scenario: Two events with the same title are told apart
- **WHEN** the operator opens `2024-07-14 - Kalas` and then `2024-07-14 - kalas`, both titled `Kalas`
- **THEN** each page's heading reads `Kalas` with the date `2024-07-14`, and each page also shows its own
  folder name, `2024-07-14 - Kalas` on the first and `2024-07-14 - kalas` on the second, which assistive
  technology reads as the heading's description

#### Scenario: A folder name that is the title is not repeated
- **WHEN** the operator opens `2024/Blandat`, whose title `Blandat` equals its folder name
- **THEN** the heading reads `Blandat`, and the page shows no separate folder name

#### Scenario: The render state reads as one region
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, which needs a render and whose latest
  job is rendered
- **THEN** "Needs render" with its reasons, the latest job "Rendered" with its time, and Render are shown
  in one region between the heading and the `Clips` table, and the line with its clip count and total size
  is shown under the heading

#### Scenario: A missing clip shows no invented facts
- **WHEN** `reel.yaml` lists `borttagen.mp4` and the file is not on disk
- **THEN** its row shows no size and no time, and a warning above the chapters names `borttagen.mp4`

#### Scenario: A stale event says why
- **WHEN** an event's `reel.yaml` was edited after its last render
- **THEN** the page shows that it needs a render, citing the edit in words

#### Scenario: A large event is fully listed
- **WHEN** an event holds 380 clips in one chapter
- **THEN** all 380 are listed, numbered 1 to 380

#### Scenario: A slow read keeps the page's shape
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide, and its read
  takes two seconds
- **THEN** during those seconds the heading shows a placeholder and no visible text, assistive technology
  names the heading `2024-06-27 - Grillning med grannar`, and each placeholder clip row is as tall as a
  loaded row; when the read answers, the heading reads `Grillkväll med grannarna` and the `Clips` table
  starts within 8 pixels of where the placeholder table started

### Requirement: Every clip row shows a frame from its clip

On an event's page, every clip row SHALL show a thumbnail of the clip beside its facts, after its position
number and ahead of its file name in the row's reading order. This applies to the chapter tables, to their
card layout in a narrow window, and to Edit mode's lists (the movable rows, the removed rows and the ignored
rows). The
thumbnail SHALL be the image the service returns for that clip from
`GET /api/v1/events/{event_id}/thumbnail?clip=<identity>`. The event id and the clip's full identity SHALL
be sent exactly as the event detail gives them, including a chapter folder and non-ASCII letters. The
request SHALL also carry the clip's modification time, exactly as the event detail gives it, as the `v`
parameter, so that a clip replaced on disk gets a new address. The client SHALL NOT choose, crop or compute
the frame itself.

The thumbnail SHALL be shown in a box of fixed 16:9 proportions, of the same size in every row. In the
chapter tables, the box SHALL be 128 × 72 CSS pixels where the chapter's panel is at least 1024 CSS
pixels wide, as in a window 1280 pixels wide, and 80 × 45 in narrower tables and in their card layout. The
whole image SHALL be visible inside the box, never cropped or stretched. A clip displayed in portrait, such
as a phone clip whose container rotates it, SHALL appear as a player shows it, whole, with empty bands at
its sides.

Each thumbnail image SHALL have the text alternative "Frame from <name>", where <name> is the clip's name as
its row shows it. The thumbnail SHALL NOT be focusable, and SHALL NOT start a drag of its own. In Edit mode
a clip moves only by its handle or its move buttons, and its thumbnail moves with its row.

A MISSING clip SHALL NOT request a thumbnail. Its row SHALL show an empty placeholder box of the same size,
and its status says why the box is empty. An IGNORED clip's thumbnail SHALL be dimmed, like the rest of its
row.

#### Scenario: Each clip of an event shows its frame
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`
- **THEN** each of its four clip rows shows an image whose text alternative is "Frame from <its file name>",
  with one thumbnail request per clip carrying that clip's identity, and as `v` that clip's modification time
  exactly as the event detail gives it

#### Scenario: Frames are larger in a wide window
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide, and again in
  a window 390 pixels wide
- **THEN** every thumbnail box is 128 × 72 CSS pixels in the first and 80 × 45 in the second, each shows its
  whole frame, and no row changes its size or position as the images arrive

#### Scenario: A frame is named as its row names the clip
- **WHEN** `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its root
  chapter and ignores the root clip `s1710004.mp4`
- **THEN** the `Main` table's thumbnails of those two clips have the text alternatives
  "Frame from Kvällen/s1710004.mp4" and "Frame from s1710004.mp4"

#### Scenario: Chapter clips are asked for by their full identity
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the `Kvällen` table's rows request their thumbnails with identities that start with `Kvällen/`,
  including the NEW `Kvällen/s1710004.mp4`, and each row shows the image for its own clip

#### Scenario: An ignored clip's frame is dimmed
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose root clip `s1710004.mp4` is IGNORED
- **THEN** that row shows its thumbnail dimmed together with the row's other facts, and the other rows'
  thumbnails are not dimmed

#### Scenario: A missing clip requests nothing
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, whose `reel.yaml` lists `borttagen.mp4` that is not
  on disk
- **THEN** no thumbnail request names `borttagen.mp4`, its row shows an empty placeholder box of the same size
  as the others, and every other clip's row shows its frame

#### Scenario: Edit mode keeps each frame with its clip
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, enters Edit mode, and moves its first clip
  down one place with the Move down button
- **THEN** every drag row shows the same frame its clip showed in the table, the moved clip's frame is now in
  the second row, and the service received no second thumbnail request for any of the four clips

#### Scenario: A clip rotated for display is shown whole
- **WHEN** an event holds a 1920×1080 clip whose container rotates it 90° for display, named with a space,
  a comma and a Swedish letter (`stående klipp, 1.mp4`)
- **THEN** its thumbnail is requested with that name as its `clip` value and arrives taller than wide, its
  box has the same size as a landscape clip's, and the whole frame is visible inside it, turned as a player
  shows it, with empty bands at its sides

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

In a window 390 CSS pixels wide, the thumbnail SHALL stay in the clip's row beside its facts, without
horizontal scroll, and no fact of a row SHALL overlap another.

#### Scenario: A clip whose frame cannot be read says "No preview"
- **WHEN** the operator opens `2024-10-05 - Trasig`, whose only clip `trasig.mp4` is an empty file
- **THEN** the row shows the "No preview" placeholder with its icon, its status and facts read as before, the
  page shows no alert or toast about it, and the service received exactly one thumbnail request for
  `trasig.mp4`

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
