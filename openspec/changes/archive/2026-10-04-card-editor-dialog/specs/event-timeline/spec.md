## MODIFIED Requirements

### Requirement: A card is selected from the Timeline or the list, as one selection

The page SHALL hold one card selection, shared by the Timeline's blocks and Edit mode's rows, kept above both so
that a Refresh or leaving Edit mode, which close the Timeline section, do not end it. Pressing a block or a row
SHALL select that card, and the block and the row SHALL both show it selected, in more than colour. At most one
thing SHALL be selected on the Timeline: selecting a card SHALL end the selection of a cut, and selecting a cut
SHALL end the selection of a card. Pressing the selected card again SHALL leave it selected; Escape SHALL clear
it, unless the card's dialog is open, where Escape closes the dialog and the card stays selected. The selection SHALL end when its chapter is deleted or no longer in the event after a read. A block and a row
SHALL be buttons reached by Tab in document order, pressed by Enter or Space, with `aria-pressed`, named in words
as "Title card for <chapter>, 4.0 s, over video" (or "on black"; the default chapter: "Title card for the opening,
…"; a clamped video card: "…, 3.0 s of 7.0 s, over video"; the off look adds ", not enabled"). In the read view a selection SHALL open nothing but an inspector slot, a labelled region with the selected card's words; it SHALL write nothing, request nothing and be announced once through the polite status region. In Edit mode, pressing a block or a row SHALL also open that card's dialog (`web-app`, "A selected title card opens its inspector in Edit mode"), and there is no inspector slot in the page.

#### Scenario: One selection from either place
- **WHEN** the operator presses the block of "Dag 2" on the Timeline in Edit mode
- **THEN** the block is pressed, "Dag 2"'s row is shown selected, and the card's dialog opens (Edit mode) or the inspector slot names the card (read view)

#### Scenario: Selecting a cut ends a card selection
- **WHEN** a card is selected and the operator presses a cut's span
- **THEN** the cut is selected and the card is not

#### Scenario: Refresh keeps the selection
- **WHEN** a card is selected, the section is closed by a Refresh, and the read still lists the chapter
- **THEN** its row (Edit mode) is shown selected, and the block is pressed when the Timeline is opened again

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
fixed-width clock style ("Card 4.0 s") SHALL follow the pointer, and the rest of the editor SHALL NOT change: the
chapter list's card row, the save bar and the draft show nothing new until the pointer is released. The readout and
the snap to a whole second SHALL be given in words and by a line, not by colour alone. Releasing SHALL make one edit
of the draft, the card's duration, and announce the result once, politely, through Edit mode's one live region ("Title
card for Reception now 6.0 s. The movie is 2.0 s longer."). Escape, or the browser cancelling the pointer, SHALL end the
drag with the card as it was and no edit. A drag that ends where it began SHALL make no edit. Pressing the handle SHALL also select that card, as pressing its block does, but SHALL NOT open the card's dialog (a modal opening under the pointer would end the drag); activating the block's body opens it.

#### Scenario: A drag sets the length
- **WHEN** at 40 px per second the operator presses the end edge of the opening card (4.0 s, black) and moves the pointer 80 px right
- **THEN** the readout says "Card 6.0 s" while dragging, and the chapter list's card row still says 4.0 s until the pointer is released

#### Scenario: Releasing makes one edit
- **WHEN** the operator releases the pointer there
- **THEN** the card row says 6.0 s, the save bar counts one changed card, the live region says so once, and Save writes `card.duration: 6.0` for that chapter

#### Scenario: Snapping to a whole second
- **WHEN** the operator moves the edge to 4.96 s's worth of pixels at 40 px per second
- **THEN** the card is 5.0 s, a line shows the second, and the readout says it snapped

#### Scenario: The ends of the range
- **WHEN** the operator drags the edge far left, then far right, of a black card
- **THEN** it stops at 0.5 s, then at 60.0 s, and never takes a value between the pointer and a limit that the engine would refuse

#### Scenario: Escape cancels
- **WHEN** the operator presses Escape during a drag
- **THEN** the card is as it was, the draft is unchanged, and the chapter list is unchanged

#### Scenario: A drag that ends where it began
- **WHEN** the operator drags the edge away and back to 4.0 s and releases
- **THEN** the draft is unchanged and the save bar does not count a change

#### Scenario: A handle press selects the card
- **WHEN** the operator presses a card's end edge in Edit mode
- **THEN** the card is selected, no dialog opens, and the track has not moved

#### Scenario: Reset and Save are as for any edit
- **WHEN** the operator changes a card's length and presses Reset
- **THEN** the card is back at its saved length, and the save bar shows no change
