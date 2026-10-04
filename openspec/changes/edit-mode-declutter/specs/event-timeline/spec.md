## MODIFIED Requirements

### Requirement: The read view and Edit mode each offer a Timeline that loads nothing until it is opened

The event page SHALL show, in its read view and in Edit mode, a section headed "Timeline" (a level-two heading). In the read view it comes after the Movie section (when the page shows one) and before the event's chapters; in Edit mode it comes after the metadata form and before the chapters' lists, and it is the Timeline on which the operator trims cuts ("Edit mode's cuts are trim handles"). In the read view the section SHALL have a button, "Open timeline", that opens it; once open, the same button SHALL read "Close timeline". The button SHALL state whether the section is open (`aria-expanded`) and SHALL name the content it controls. In Edit mode the section SHALL have no such button and no way to close it: Edit mode's Timeline is where the cuts are trimmed, and it is open whenever Edit mode shows.

The read view's section SHALL be closed when the page opens, after a Refresh and after leaving Edit mode. Edit mode's section SHALL be open from the moment Edit mode shows: pressing Edit opens Edit mode with the Timeline open (a Timeline open in the read view is replaced by Edit mode's, open), and a Refresh or a save keeps it open. While the read view's section is closed the page SHALL create no `<video>` for it and SHALL make no request for a proxy, a filmstrip or a proxy job, whatever the number of clips. An open Edit-mode Timeline of an event whose proxies are not all ready shows its Prepare state and nothing else, as the open read view does. While the event page is loading, or shows a failure, it SHALL show no Timeline section.

Opening the Timeline SHALL change no state the service holds: it only reads. Starting a proxy job is a separate, explicit control (see "The Timeline asks for the clips' proxies when they are missing").

In Edit mode the Timeline SHALL draw its clips, chapters and proxies as the event was last read (a proxy job that ends while Edit mode is open reads the event again, quietly, and the Timeline follows it; the editor's draft is not touched by that read), and its cuts as the draft lists them. It SHALL NOT draw the draft's unsaved order or chapters: when the draft has moved a clip, reordered or renamed a chapter, or added or deleted one, the Timeline SHALL say in a note that it shows the order last saved, and the cuts of every clip stay editable. Play on the Timeline SHALL skip the draft's cuts as they are now, so that a trim is heard and seen before it is saved. In Edit mode the cuts are never "being read" and never "unreadable": the draft holds them.

#### Scenario: A closed timeline costs nothing
- **WHEN** the operator opens the page of an event of 400 clips and does not press "Open timeline"
- **THEN** the page holds no `<video>` for the Timeline and has made no request to a proxy or filmstrip address, and the Timeline section shows its heading and the "Open timeline" button, not expanded

#### Scenario: Edit mode has its own, closed timeline
- **WHEN** the operator opens the Timeline of `2024-06-27 - Grillning med grannar` and then presses Edit
- **THEN** the read view's closed Timeline is not carried over: the page shows Edit mode with a Timeline section after the metadata form, open and showing its track, with no "Open timeline"
  or "Close timeline" button anywhere in Edit mode; and leaving Edit mode shows the read view's Timeline section closed

#### Scenario: Edit mode without proxies shows Prepare
- **WHEN** the operator presses Edit on an event none of whose proxies is prepared
- **THEN** the open Timeline shows its Prepare state with "Prepare proxies", the chapters' Edit Titlecard buttons and the
  Details form work, and the page holds no `<video>` for the Timeline

#### Scenario: Opening is a read
- **WHEN** the operator opens the Timeline of an event whose proxies are all ready
- **THEN** every request the client made for it was a read, no file under the library changed, and the jobs the service lists are the same as before

#### Scenario: The movie and the timeline do not play together
- **WHEN** the event's movie is playing and the operator presses Play on the Timeline
- **THEN** the movie pauses and the Timeline plays; pressing the movie's Play while the Timeline plays pauses the Timeline

#### Scenario: A reorder is not drawn
- **WHEN** in Edit mode the operator moves `s1710002.mp4` above `s1710001.mp4` in its chapter's list and opens the Timeline
- **THEN** the Timeline draws `s1710001.mp4` first, as last saved, and a note says that it shows the order last saved; after Save the Timeline draws the new order

#### Scenario: Play skips a trim that is not saved
- **WHEN** in Edit mode the operator trims the cut of `s1710001.mp4` to 1.0 to 3.5 s and plays the Timeline from 0.5 s
- **THEN** no frame between 1.0 and 3.5 s is shown, and nothing has been written

#### Scenario: Proxies prepared while editing
- **WHEN** in Edit mode the Timeline shows its Prepare state, the operator presses "Prepare proxies", and the job ends
- **THEN** the page reads the event again, the Timeline shows the track with the draft's cuts, and the draft, the save bar and the Cuts panels are as they were

### Requirement: A card is selected from the Timeline or the list, as one selection

The page SHALL hold one card selection, shared by the Timeline's blocks and Edit mode's chapter header bars, kept above both so
that a Refresh or leaving Edit mode, which close the Timeline section, do not end it. Pressing a block, or a chapter's Edit Titlecard button, SHALL select that card, and the block and the button SHALL both show it selected, in more than colour (the button as pressed, with `aria-pressed`). At most one
thing SHALL be selected on the Timeline: selecting a card SHALL end the selection of a cut, and selecting a cut
SHALL end the selection of a card. Pressing the selected card again SHALL leave it selected; Escape SHALL clear
it, unless the card's dialog is open, where Escape closes the dialog and the card stays selected. The selection SHALL end when its chapter is deleted or no longer in the event after a read. A block and the button SHALL be buttons reached by Tab in document order, pressed by Enter or Space, with `aria-pressed`, named in words
as "Title card for <chapter>, 4.0 s, over video" (or "on black"; the default chapter: "Title card for the opening,
…"; a clamped video card: "…, 3.0 s of 7.0 s, over video"; the off look adds ", not enabled"). In the read view a selection SHALL open nothing but an inspector slot, a labelled region with the selected card's words; it SHALL write nothing, request nothing and be announced once through the polite status region. In Edit mode, pressing a block or the button SHALL also open that card's dialog (`web-app`, "A selected title card opens its inspector in Edit mode"), and there is no inspector slot in the page.

#### Scenario: One selection from either place
- **WHEN** the operator presses the block of "Dag 2" on the Timeline in Edit mode
- **THEN** the block is pressed, "Dag 2"'s Edit Titlecard button is shown pressed, and the card's dialog opens (Edit mode) or the inspector slot names the card (read view)

#### Scenario: Selecting a cut ends a card selection
- **WHEN** a card is selected and the operator presses a cut's span
- **THEN** the cut is selected and the card is not

#### Scenario: Refresh keeps the selection
- **WHEN** a card is selected, the section is closed by a Refresh, and the read still lists the chapter
- **THEN** its Edit Titlecard button (Edit mode) is shown pressed, and the block is pressed when the Timeline is opened again

#### Scenario: A deleted chapter ends the selection
- **WHEN** the selected card's chapter is deleted in the draft
- **THEN** nothing is selected and the slot is gone

#### Scenario: Keyboard and names
- **WHEN** a keyboard user tabs to the "Dag 2" block and presses Space
- **THEN** it is selected, a screen reader says "Title card for Dag 2, 4.0 s, over video, pressed", and the polite
  status says it once

#### Scenario: Reading changes nothing
- **WHEN** a card is selected in the read view or in Edit mode
- **THEN** no request is made and the Save bar shows no unsaved change

### Requirement: A card block's end edge is dragged to set the card's length

In Edit mode, the end edge of every title-card block on the Timeline SHALL be a handle that sets that card's
`duration` in the draft. Pressing it with a mouse, a pen or a finger, and moving, SHALL move the edge by the distance
the pointer moves from where the edge was, in whole tenths of a second, snapping to a whole second within 8 screen
pixels, and staying between the card's limits (0.5 s to 60 s, and for a card over video no more than the first span of the
chapter's anchor clip that the draft's cuts keep). While dragging, the block, the handle and a readout in the Timeline's
fixed-width clock style ("Card 4.0 s") SHALL follow the pointer, and the rest of the editor SHALL NOT change: the save bar and the draft show nothing new until the pointer is released. The readout and
the snap to a whole second SHALL be given in words and by a line, not by colour alone. Releasing SHALL make one edit
of the draft, the card's duration, and announce the result once, politely, through Edit mode's one live region ("Title
card for Reception now 6.0 s. The movie is 2.0 s longer."). Escape, or the browser cancelling the pointer, SHALL end the
drag with the card as it was and no edit. A drag that ends where it began SHALL make no edit. Pressing the handle SHALL also select that card, as pressing its block does, but SHALL NOT open the card's dialog (a modal opening under the pointer would end the drag); activating the block's body opens it.

#### Scenario: A drag sets the length
- **WHEN** at 40 px per second the operator presses the end edge of the opening card (4.0 s, black) and moves the pointer 80 px right
- **THEN** the readout says "Card 6.0 s" while dragging, and the save bar counts no changed card until the pointer is released

#### Scenario: Releasing makes one edit
- **WHEN** the operator releases the pointer there
- **THEN** the save bar counts one changed card, the live region says so once, the card's dialog, opened afterwards, holds 6.0 s in its Length field,
  and Save writes `card.duration: 6.0` for that chapter

#### Scenario: Snapping to a whole second
- **WHEN** the operator moves the edge to 4.96 s's worth of pixels at 40 px per second
- **THEN** the card is 5.0 s, a line shows the second, and the readout says it snapped

#### Scenario: The ends of the range
- **WHEN** the operator drags the edge far left, then far right, of a black card
- **THEN** it stops at 0.5 s, then at 60.0 s, and never takes a value between the pointer and a limit that the engine would refuse

#### Scenario: Escape cancels
- **WHEN** the operator presses Escape during a drag
- **THEN** the card is as it was and the draft is unchanged

#### Scenario: A drag that ends where it began
- **WHEN** the operator drags the edge away and back to 4.0 s and releases
- **THEN** the draft is unchanged and the save bar does not count a change

#### Scenario: A handle press selects the card
- **WHEN** the operator presses a card's end edge in Edit mode
- **THEN** the card is selected, no dialog opens, and the track has not moved

#### Scenario: Reset and Save are as for any edit
- **WHEN** the operator changes a card's length and presses Reset
- **THEN** the card is back at its saved length, and the save bar shows no change

## REMOVED Requirements

### Requirement: Edit mode's chapter list shows each chapter's card as a row
**Reason**: The row repeated what the Timeline's card block and the card dialog already show, and it cluttered every chapter (operator feedback of 2026-10-04: "Remove the
card style for this event section completely, I want all title card related settings in the popup only", and the section "below" the header). The card is reached by the header bar's
"Edit Titlecard" button and by its block on the Timeline.
**Migration**: The card's words (title, subtitle, length, background, font) are in the dialog and on the Timeline's block and readout; "Not enabled" is said by the dialog ("Title cards are off for this event");
a chapter added in the draft keeps its Edit Titlecard button, and its dialog says that its card is drawn after Save. The "Main title card" line and the rename pencils are removed with the row ("Edit mode adds, renames,
reorders and deletes chapters").
