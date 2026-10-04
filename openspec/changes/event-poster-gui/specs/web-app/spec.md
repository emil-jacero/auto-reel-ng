## ADDED Requirements

### Requirement: The event list and the event page show the event's poster
Each event of the event list SHALL show its poster as a cover image taken from `GET …/events/{id}/poster.jpg`,
and the event page's header SHALL show the same image larger. The image SHALL load lazily, SHALL sit in a box of
a fixed aspect ratio (16:9) that is reserved before it loads so that no row or header shifts when it arrives, and
SHALL have alternative text naming the event (and, on the page, whether the frame is the default or a chosen one).
An event the poster endpoint answers 404 for, or whose image fails to load, SHALL show a placeholder in the same
box that says there is no poster; a failure SHALL NOT hide the row, break the page or be shown by color alone.
Reading the images SHALL NOT change state, and a page of events SHALL NOT ask for more than the images in view
and near it. The cover SHALL keep its aspect at 390 px width and in both color schemes, the list's text SHALL stay
readable beside it, and the page SHALL announce nothing for a cover that loads.

#### Scenario: A list of events shows their covers
- **WHEN** the list shows events with and without a playable clip
- **THEN** the first show a cover image with alt text naming the event, the others a placeholder of the same
  size, and the rows do not move as the images load

#### Scenario: Images below the fold are not fetched
- **WHEN** the list is opened with more events than fit the window
- **THEN** only the covers in or near the viewport are requested until the page is scrolled

#### Scenario: A failed image does not break the row
- **WHEN** the poster endpoint answers 502 for one event
- **THEN** that row shows the placeholder, and the row's text and actions are all present

#### Scenario: The page header shows the poster
- **WHEN** an event with a chosen frame is opened
- **THEN** the header shows its image and the words "Chosen frame"; an event without one says "Default: first clip"

### Requirement: Edit mode chooses the event's poster on the Timeline
In Edit mode the Timeline SHALL offer **Use as poster**. Pressed, it SHALL set the draft's poster to the clip
under the playhead and the playhead's time in that clip, in seconds to the millisecond and before the clip's cuts
(a time inside a cut is allowed), and SHALL take the frame the Timeline's video shows as the draft picture of
the poster area. It SHALL be disabled, with the reason in words, when the playhead is on a title-card block or
outside every clip, when the video has no decoded frame at the playhead, and while a save or a Move clips is
pending; a snapshot that fails SHALL change nothing and say so. Keyboard focus SHALL stay on the button and the
change SHALL be announced once.

Edit mode's **poster area** (the event header's cover, which Edit mode keeps) SHALL say what the poster is:
**Default: first clip** when the draft has no poster, **Chosen frame** when it has one as saved, and **Chosen
frame, not saved** for a draft that differs from the saved one. **Use default** SHALL remove the draft's poster and
SHALL be unavailable when there is none. The poster is a part of the one draft: Save writes `poster` with the
existing editorial write (`poster: {clip, at}`, or `null` to remove, and nothing when the poster was not
changed), Undo of the poster and Reset restore the saved one, an unmodified draft writes nothing, the save bar
says "poster changed", and Unsaved edits are never discarded silently. After a save the poster area shows the
image from the poster endpoint, not the snapshot. A poster whose clip the draft removes, moves out of the event
or ignores SHALL be marked in the poster area ("this clip does not play, the default is used") and SHALL NOT be
rewritten silently. A chosen clip that the detail reports with a `poster_note` SHALL show that note. Clips whose
rotation the page shows turned (`rotate`) SHALL be snapshotted and shown turned.

#### Scenario: Use as poster sets the draft from the playhead
- **WHEN** the playhead is at 0:12.500 of `s1710002.mp4` in Edit mode and Use as poster is pressed
- **THEN** the draft's poster is that clip at 12.5 s, the poster area shows that frame as "Chosen frame, not
  saved", the save bar says "Poster changed", and focus is still on the button

#### Scenario: Saving writes the poster once
- **WHEN** the draft's poster is changed and Save is pressed
- **THEN** one `PUT …/reel` carries `poster: {clip, at}`, a save of an unchanged poster carries none, and the poster
  area then shows the served image as "Chosen frame"

#### Scenario: Use default removes the chosen frame
- **WHEN** an event with a saved poster is edited, Use default is pressed and Save is pressed
- **THEN** the write carries `poster: null`, the area says "Default: first clip", and Reset before Save restores
  the saved poster

#### Scenario: The button is off where there is no footage
- **WHEN** the playhead is on a title-card block, or a save is pending
- **THEN** Use as poster is disabled and says why

#### Scenario: A rotated clip is chosen turned
- **WHEN** the clip is shown turned and Use as poster is pressed on it
- **THEN** the draft picture is turned the same way

#### Scenario: The same behavior in Chrome and Firefox, in both schemes, at 1280 and 390 px
- **WHEN** the steps above are run in Chrome and in Firefox, light and dark, at 1280 and 390 px width
- **THEN** each has the same words and results, nothing overflows, and every control is large enough to touch

#### Scenario: Reading does not write
- **WHEN** the list, the page and Edit mode are opened and the Timeline's playhead is moved without pressing Use as
  poster
- **THEN** no request other than reads is sent
