## ADDED Requirements

### Requirement: A suggestion is approved as a cut through Edit mode's draft

In Edit mode, a suggestion that is pending SHALL offer **Approve as cut** (a button in the detail of the
selected mark, and the **A** key on a focused mark). Approving SHALL add a cut to the clip's draft cuts, the
same way a typed cut is added ("Edit mode lists, adds and removes a clip's cuts"): the cut's start and end are
the suggestion's, to the nearest millisecond, and **its reason is the suggestion's kind** (`black`, `white`,
`freeze`, or the unrecognised kind as written). The cut SHALL take the key the next cut added in Edit mode takes
and SHALL be listed, counted in the save bar ("added" cuts), covered by the unsaved-changes guard, and written
by Save with the version check, like any cut; nothing SHALL be written before Save. The suggestion's state
SHALL then read cut.

Approving SHALL be checked as a typed cut is, and SHALL add nothing when the check refuses: a span that
overlaps a cut the clip lists now (a partly cut suggestion) SHALL be refused, naming that cut; a span that ends
after the clip's length, where the page knows it, SHALL be refused, and a span of under a millisecond SHALL be
refused. A refusal SHALL be shown in the detail and said through Edit mode's live region ("Not approved: …"),
and the suggestion SHALL keep its state. Approving a suggestion that is already cut SHALL change nothing and say
so. An approval SHALL be ignored, as the Cuts panel's is, while a save or a Move clips is in progress.

Outside Edit mode the page SHALL offer no way to approve and SHALL say, once, that Edit mode is where
suggestions are approved. Approving is announced through the live region with the kind, the span, the clip's
name and the number of cuts added.

#### Scenario: Approving by button

- **WHEN** in Edit mode the operator selects the "Black frames 0:00 to 0:03.2" mark on `C0012.MP4` and presses
  Approve as cut
- **THEN** the clip lists a new cut from 0:00 to 0:03.2 with the reason "Black frames", the mark reads cut, the
  region says "Approved black frames, 0:00 to 0:03.2, of C0012.MP4 as a cut; 1 cut added", and the save bar
  counts one added cut

#### Scenario: Approving then saving writes the kind as the reason

- **WHEN** the operator approves a freeze suggestion from 58.1 to 60 s and saves
- **THEN** the write carries that clip's trims with `{in: 58.1, out: 60, reason: "freeze"}` and the existing
  trims unchanged, with the version check, and no other part of the document

#### Scenario: Approving what a cut overlaps is refused

- **WHEN** a clip lists a cut from 0 to 1 s and the operator presses Approve as cut on a black suggestion from
  0 to 3.2 s
- **THEN** no cut is added, the detail and the region say "Not approved: this overlaps cut 1 (0:00 to 0:01)",
  and the mark still reads partly cut

#### Scenario: A span past the clip's end is refused

- **WHEN** a freeze suggestion ends at 60.04 s and the clip's length is 60 s
- **THEN** the approval is refused with the past-the-end wording the Cuts panel uses, and no cut is added

#### Scenario: Pressing twice adds one cut

- **WHEN** the operator presses Approve as cut twice in quick succession on one pending suggestion
- **THEN** the clip gains one cut, and the second press says the suggestion is already cut

#### Scenario: Reading does not approve

- **WHEN** the event page shows the timeline outside Edit mode
- **THEN** no mark offers Approve as cut, a single note says to open Edit mode, and pressing A on a focused mark
  changes nothing

#### Scenario: A conflict keeps the approvals

- **WHEN** the operator approves two suggestions, then Save is refused because `reel.yaml` changed (412)
- **THEN** both approved cuts stay in the draft and the save bar offers the choices it always does

### Requirement: A suggestion is dismissed for the page visit, never saved

In Edit mode, a pending suggestion SHALL offer **Dismiss** (a button in the detail, and the **R**
key on a focused mark), and a dismissed one SHALL offer **Restore** (the button, and **R**). Dismissing SHALL
mark the suggestion dismissed (its glyph, its word and its accessible name), SHALL be said through the live
region, and SHALL write nothing: it is not an edit, so it SHALL NOT enable Save, count in the save bar, or raise
the unsaved-changes guard. Dismissals SHALL persist while the page is open, across entering and leaving Edit
mode, a Refresh, a Save and the Timeline being closed and opened, and SHALL be forgotten when the page is
reloaded or left. The lane SHALL say so,
once, in words. A dismissal of a suggestion that a later analysis read no longer lists SHALL be dropped; the
others SHALL stay.

#### Scenario: Dismissing is not an edit

- **WHEN** the operator dismisses a pending suggestion and nothing else has changed
- **THEN** the mark reads dismissed with a `×`, the region says it, Save stays unavailable ("Nothing to save"),
  and leaving Edit mode raises no unsaved-changes question

#### Scenario: Restoring

- **WHEN** the operator presses R on a dismissed mark
- **THEN** it reads pending again and the region says it was restored

#### Scenario: Dismissals last the visit and no longer

- **WHEN** the operator dismisses a suggestion, presses Refresh, leaves Edit mode, enters it again and opens
  the Timeline
- **THEN** the suggestion still reads dismissed
- **WHEN** the page is then reloaded
- **THEN** it reads pending, and the lane's note said that dismissed suggestions come back on reload

#### Scenario: A cut outranks a dismissal

- **WHEN** a dismissed suggestion's span is then cut by hand over the whole span
- **THEN** its mark reads cut
