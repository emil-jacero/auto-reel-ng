## REMOVED Requirements

### Requirement: The Timeline is shown only in Edit mode, open from the start
**Reason**: Its rule that the Timeline draws the saved order (scenario "A reorder is not drawn") is reversed.
**Migration**: Replaced, with every other obligation kept word for word (checked against the main spec on
2026-11-15), by the first six requirements below ("…shown
only in Edit mode and draws the draft", "The read view has no Timeline", "The read view keeps everything else it
shows", "Showing the Timeline only reads…", "The Edit-mode Timeline draws the draft's order and chapters", "The
Edit-mode Timeline's cuts are the draft's").

## ADDED Requirements

### Requirement: The Timeline is shown only in Edit mode and draws the draft

The event page SHALL show a section headed "Timeline" (a level-two heading) only in Edit mode, after the metadata form
and the Poster panel and before the chapters' lists; it is the Timeline on which the operator trims cuts ("Edit mode's
cuts are trim handles"). The section SHALL be open whenever Edit mode shows: pressing Edit opens Edit mode with the
Timeline open, and a Refresh or a save keeps it open. It SHALL have no button that opens or closes it.

#### Scenario: Edit opens the Timeline, leaving closes it
- **WHEN** the operator presses Edit on `2024-06-27 - Grillning med grannar` and later leaves Edit mode
- **THEN** Edit mode shows a Timeline section after the metadata form, open and showing its track, with no "Open
  timeline" or "Close timeline" button; after leaving, the read view shows no Timeline section and its clip list,
  Movie section and poster as before


### Requirement: The read view has no Timeline

The read view SHALL show no Timeline: no section, no heading, no "Open timeline" or "Close timeline" button, no line
or region naming a selected title card, and SHALL create no `<video>` for a Timeline and make no request for a proxy, a
filmstrip, the analysis or a proxy job on its behalf, whatever the number of clips.

#### Scenario: The read view has no Timeline
- **WHEN** the operator opens the page of an event of 400 clips whose proxies are all ready
- **THEN** the read view has no heading "Timeline", no "Open timeline" button and no title card line, the page holds no
  `<video>` for a Timeline, and no request was made to a proxy, filmstrip, analysis or proxy-job address


### Requirement: The read view keeps everything else it shows

The read view SHALL keep everything else it shows: the event's chapters and clips with their play controls, cut
summaries and turns, the Movie section and the poster. While the event page is loading, or shows a failure, it SHALL
show no Timeline section.

#### Scenario: Leaving Edit mode keeps the read view
- **WHEN** the operator leaves Edit mode on `2024-06-27 - Grillning med grannar`
- **THEN** the read view shows the event's chapters and clips with their play controls, cut summaries and turns, the
  Movie section and the poster, and no Timeline section


### Requirement: Showing the Timeline only reads, and shows Prepare without proxies

An open Timeline of an event whose proxies are not all ready SHALL show its Prepare state and nothing else. Showing
the Timeline SHALL change no state the service holds: it only reads. Starting a proxy job is a separate, explicit
control (see "The Timeline asks for the clips' proxies when they are missing"). A proxy job that ends while Edit mode
is open SHALL read the event again, quietly, and the Timeline follows it; the editor's draft is not touched by that
read.

#### Scenario: Edit mode without proxies shows Prepare
- **WHEN** the operator presses Edit on an event none of whose proxies is prepared
- **THEN** the open Timeline shows its Prepare state with "Prepare proxies", the chapters' Edit Titlecard buttons and the
  Details form work, and the page holds no `<video>` for the Timeline

#### Scenario: Showing is a read
- **WHEN** the operator presses Edit on an event whose proxies are all ready
- **THEN** every request the client made for the Timeline was a read, no file under the library changed, and the jobs
  the service lists are the same as before

#### Scenario: Proxies prepared while editing
- **WHEN** in Edit mode the Timeline shows its Prepare state, the operator presses "Prepare proxies", and the job ends
- **THEN** the page reads the event again, the Timeline shows the track with the draft's order and cuts, and the draft,
  the save bar and the Cuts panels are as they were


### Requirement: The Edit-mode Timeline draws the draft's order and chapters

The Timeline SHALL draw the draft's chapters in the draft's order and names, a deleted chapter drawing nothing, and in
each chapter its clips in the draft's order, at once and before Save; Reset SHALL draw the saved order again. Each
clip's facts SHALL be those of the last read; a clip that read no longer has SHALL NOT be drawn. No note about the
order last saved SHALL be shown. Play on the Timeline SHALL follow the drawn order.

#### Scenario: A reorder is drawn before Save
- **WHEN** in Edit mode the operator moves `s1710002.mp4` above `s1710001.mp4` in its chapter's list
- **THEN** the Timeline draws `s1710002.mp4` first at once, no note about the order last saved is shown, nothing has
  been written, and Play from 0 plays `s1710002.mp4` before `s1710001.mp4`

#### Scenario: Reset draws the saved order again
- **WHEN** the operator has moved `s1710003.mp4` from "Kvällen" to "Main" and presses Reset
- **THEN** the Timeline draws `s1710003.mp4` in "Kvällen" where it was saved

#### Scenario: A deleted chapter draws nothing
- **WHEN** the operator deletes the chapter "Kvällen" (listed with Undo until Save) whose clips moved to "Main"
- **THEN** the Timeline draws no band named "Kvällen" and no card for it, and draws the moved clips in "Main"

#### Scenario: A clip gone from disk mid-edit
- **WHEN** in Edit mode a proxy job ends, the page reads the event again, and `s1710004.mp4` is no longer in the read
- **THEN** the Timeline no longer draws `s1710004.mp4`, and the draft and its lists are as they were


### Requirement: The Edit-mode Timeline's cuts are the draft's

The Timeline SHALL draw its cuts as the draft lists them, and the cuts of every clip stay editable. Play on the
Timeline SHALL skip the draft's cuts as they are now, so that a trim is heard and seen before it is saved. The cuts are
never "being read" and never "unreadable": the draft holds them.

#### Scenario: Play skips a trim that is not saved
- **WHEN** in Edit mode the operator trims the cut of `s1710001.mp4` to 1.0 to 3.5 s and plays the Timeline from 0.5 s
- **THEN** no frame between 1.0 and 3.5 s is shown, and nothing has been written


### Requirement: Title cards of renamed chapters keep their card on the Timeline

While title cards are on, a chapter renamed in the draft SHALL keep, on the card lane, the card the service resolved
for its saved name, titled with the draft's name where the card's title is the chapter's name. A deleted chapter's card
SHALL NOT be drawn.

#### Scenario: Renamed chapter keeps its card
- **WHEN** the operator renames "Kvällen" to "Kväll vid havet"; its saved card is 4.0 s over video
- **THEN** the card lane draws a 4.0 s video card titled "Kväll vid havet" over the chapter's first clip

#### Scenario: Title cards off
- **WHEN** the draft's Title cards switch is Off and the operator adds a chapter
- **THEN** no card adds time, and each chapter's card, the added one's included, is drawn only in the off look
  ("not enabled")

### Requirement: A chapter added while editing gets the event's card on the Timeline

While title cards are on, a chapter added in this Edit session SHALL get a card built from the event's resolved cards
(the opening card, else the first) with the draft's card style applied and the chapter's name as its title. Its length
and background SHALL place it as any card is placed. With no resolved card to build from, it SHALL be a block of the
event style's length named "Title card for <chapter>, shown after save". After a save the service's cards replace it.

#### Scenario: Added chapter gets the event's card
- **WHEN** the event's cards are black, 3.0 s, and the operator adds a chapter "Morgon" and moves `s1710004.mp4` into it
- **THEN** a 3.0 s black card titled "Morgon" is drawn before `s1710004.mp4`, and the clips after it start 3.0 s later

#### Scenario: Nothing to build from
- **WHEN** no chapter of the event has a resolved card and the operator adds a chapter "Morgon"
- **THEN** a block named "Title card for Morgon, shown after save" of the event style's length is drawn
