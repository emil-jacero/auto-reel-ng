## ADDED Requirements

### Requirement: In Edit mode a suggestion is approved as a cut of the draft

In Edit mode the analysis lane SHALL offer **Approve as cut** for a suggestion whose state is pending or partly cut, as a button in the detail of the selected mark (44 px high under a coarse pointer) and as the key **A** on the focused mark. Approving SHALL add the suggestion to the clip's cuts in the editor's **draft**, as the Cuts panel's "Add" does, through the same check: the span to the millisecond ("Times are written one way on every screen"), refused when it is empty or reversed, when it ends after the clip's length (the proxy's duration), or when it overlaps a cut of the clip that is not removed. The cut SHALL have the suggestion's kind as its reason (`black`, `white`, `freeze`, or an unrecognised kind as written) and not `manual`; the Cuts panel SHALL list it at once, with that reason in words, numbered as a cut added there, and the Timeline SHALL draw it with its trim handles. Approving SHALL change nothing else: no existing cut is merged, trimmed or removed, and a **partly cut** suggestion SHALL be refused as an overlap, never added as the part that is left.

Approving SHALL write nothing by itself. It is an edit of the draft: the save bar SHALL count one cut added, the unsaved-changes guard SHALL apply, and Save SHALL write the cut to `reel.yaml` as a trim with the kind as its `reason`, by the existing whole-document write ("Saving an edit writes only what the operator changed"). Removing the cut in the Cuts panel, and Reset, SHALL return the suggestion to pending with no other action, and an approval followed by its removal SHALL leave nothing to save. An approved cut, once saved, SHALL read as **cut** on the next read of the page, as a cut saved by hand over the same span does ("The timeline shows the event's analysis suggestions beside its clips").

Approving SHALL be said once, politely, through Edit mode's one live region ("Approved black frames, 0:00 to 0:03.2, of C0012.MP4 as a cut; 1 cut added."). A refusal SHALL add nothing, SHALL be said in the live region and shown in the detail, in the Cuts panel's words ("Not approved: …", an overlap naming the cut by its number in the panel and saying to remove it first), and the suggestion SHALL keep its state. Approving a suggestion that is already cut, or dismissed, SHALL change nothing and say so ("Already cut: …", "Dismissed: … Restore it first."). The read view SHALL offer no approval: reading a screen never changes state.

#### Scenario: Approving adds a cut with the kind as its reason
- **WHEN** in Edit mode a clip `C0012.MP4` of 25 s with no cuts has a pending black suggestion from 0 to 3.2033 s and the operator selects its mark and presses "Approve as cut"
- **THEN** the clip's Cuts panel lists one cut, 0:00 to 0:03.203, with the reason "black", the Timeline draws it with two handles, the mark reads cut, the save bar says that 1 cut was added, nothing has been written, and the live region said "Approved black frames, 0:00 to 0:03.203, of C0012.MP4 as a cut; 1 cut added."

#### Scenario: Save writes the reason
- **WHEN** the operator then presses Save
- **THEN** `reel.yaml` gives `C0012.MP4` a trim from 0 to 3.203 s with the reason `black`, the page reads that trim back, and the mark reads cut

#### Scenario: Removing the cut brings the mark back
- **WHEN** the operator removes that cut in the Cuts panel, or uses Reset
- **THEN** the mark reads pending, the save bar is gone if nothing else was edited, and the Cuts panel lists no cut

#### Scenario: An overlap is refused in words
- **WHEN** the clip lists a cut from 2 to 4 s (cut 1) and the operator approves a freeze suggestion from 3 to 5 s
- **THEN** no cut is added, the detail and the live region say "Not approved: this overlaps cut 1 (0:02 to 0:04). Remove that cut first.", the draft is as it was, and the mark still reads pending

#### Scenario: A partly cut suggestion is not completed for the operator
- **WHEN** the clip lists a cut from 0 to 1 s and the operator approves a black suggestion from 0 to 3.2 s
- **THEN** it is refused for the overlap with cut 1, and no cut from 1 to 3.2 s is added

#### Scenario: A suggestion past the clip's end is refused
- **WHEN** a suggestion ends at 6.2 s on a clip whose proxy is 6.08 s long and the operator approves it
- **THEN** it is refused in the Cuts panel's words for a cut that ends after the clip, and nothing is added

#### Scenario: Approving twice adds one cut
- **WHEN** the operator presses A on a pending mark and presses A again
- **THEN** the draft holds one cut, and the second press says "Already cut: …"

#### Scenario: The read view has no approval
- **WHEN** the Timeline is opened on the event page's read view
- **THEN** the detail of a selected mark has no Approve, Dismiss or Restore, the key A on a mark does nothing, and no request other than reads is made

### Requirement: A suggestion is dismissed for the page visit and restored, without an edit

In Edit mode the analysis lane SHALL offer **Dismiss** for a pending suggestion and **Restore** for a dismissed one, as buttons in the detail of the selected mark and as the key **R** on the focused mark (R on a pending mark dismisses it, R on a dismissed mark restores it). A dismissed suggestion SHALL read **dismissed**, with its glyph and word, unless a cut covers any of its span, in which case it reads by its cuts ("A cut outranks a dismissal"). Restoring SHALL return it to pending. Dismissing SHALL NOT be an edit: no cut is added, the draft SHALL stay as it was, the save bar SHALL NOT appear, Save SHALL stay unavailable if nothing else was edited, and the unsaved-changes guard SHALL NOT apply, because `reel.yaml` has no field for a rejection and nothing is written.

A dismissal SHALL last for the page visit: it SHALL survive opening and closing the Timeline, entering and leaving Edit mode, a Refresh and a Save, and SHALL be gone when the page is reloaded or left. A dismissal whose suggestion a new read of the analysis no longer lists SHALL be dropped silently. While any suggestion can be decided, the lane SHALL say once, as text, that dismissed suggestions come back when the page is reloaded. Dismissing and restoring SHALL each be said once through the live region ("Dismissed black frames, 0:00 to 0:03.2, of C0012.MP4.", "Restored …"). A suggestion that is cut or partly cut SHALL answer Dismiss with a statement ("Already cut: …", "Partly cut: … It is decided by the cut that overlaps it.") and change nothing.

#### Scenario: Dismiss and restore leave the draft alone
- **WHEN** in Edit mode, with nothing edited, the operator presses R on a pending mark, then R again
- **THEN** the mark reads dismissed with its `×` glyph and the word, then pending; no save bar appeared, Save was never enabled, and leaving Edit mode asked nothing

#### Scenario: A dismissal outlives Edit mode and a Refresh
- **WHEN** the operator dismisses a mark, leaves Edit mode, presses Refresh and opens the Timeline again
- **THEN** the mark still reads dismissed; after a reload of the page it reads pending

#### Scenario: A cut outranks a dismissal
- **WHEN** a dismissed suggestion's span is cut by hand in the Cuts panel
- **THEN** the mark reads cut; and when that cut is removed it reads dismissed again

#### Scenario: A dismissed suggestion is restored before it is approved
- **WHEN** the operator presses Approve on a dismissed mark
- **THEN** no cut is added and the live region says "Dismissed: … Restore it first."

#### Scenario: The note is said once
- **WHEN** Edit mode's Timeline shows marks that can be decided
- **THEN** one line under the lane says that dismissed suggestions come back when the page is reloaded; the read view shows no such line

### Requirement: A and R decide only the focused mark, and the buttons decide the same

The keys **A** (approve) and **R** (dismiss or restore) SHALL act only when the focused element is a suggestion's mark, never from the document: typing "a" or "r" in the title, the location or a typed cut time SHALL decide nothing. They SHALL ignore Ctrl, Meta and Alt chords, a key repeat and an input-method composition, SHALL ignore Shift (the key is a letter), and SHALL call `preventDefault` only when they acted; where they did not act (a Timeline without decisions, a pending save, a cut mark) the key SHALL be left to the browser. The detail's buttons SHALL make the same decisions in the same words, and are the route for touch and assistive technology; a mark SHALL advertise its keys (`aria-keyshortcuts="A R"`) only while it can be decided. After a decision keyboard focus SHALL stay on the same mark, and the detail SHALL stay on it, so that Restore is one press away.

#### Scenario: Typing in a field decides nothing
- **WHEN** the operator types "a" and "r" in the event's title field in Edit mode while the Timeline shows pending marks
- **THEN** the title holds the typed letters and no suggestion changed state

#### Scenario: A chord is the browser's
- **WHEN** a mark has focus and the operator presses Ctrl+R or Ctrl+A
- **THEN** nothing is decided and the browser's own action is not prevented

#### Scenario: The decision keeps focus
- **WHEN** the operator presses A on a focused pending mark
- **THEN** the mark now reads cut, keyboard focus is still on it, and the detail still shows it

#### Scenario: The button does what the key does
- **WHEN** the operator selects a pending mark by touch and presses "Dismiss", then "Restore", then "Approve as cut"
- **THEN** the mark reads dismissed, pending, then cut, each said once in the live region, with the draft changed only by the last

### Requirement: Decisions are unavailable while a save or a move is pending

While a save is in flight or a Move clips is pending, Approve, Dismiss and Restore SHALL say that they are unavailable (`aria-disabled` on the buttons, in words in the detail, as the trim handles do) and SHALL change nothing, whether pressed or keyed; selecting a mark, moving between marks and the playhead SHALL stay usable. A decision SHALL never be announced as done when no change was made.

#### Scenario: A pending save blocks the decision
- **WHEN** the operator presses Save and, before the service answers, presses Approve as cut on a pending mark and presses A on another
- **THEN** no cut is added, nothing is announced as approved, the buttons read as unavailable, and when the save has ended both marks are still pending

### Requirement: A press handed to a nearer handle selects and focuses the handle that took it

Where the press areas of two trim handles overlap and a press is handed to the nearer one ("Trim handles are large enough for a finger, and a swipe still scrolls"), the cut of the handle that took the press SHALL be the selected cut, and that handle SHALL hold keyboard focus when the press ends, whatever had focus before, for a mouse, a pen and a finger, in Chrome and in Firefox 155 or newer. A focus event on another handle of the same clip while that press is in force SHALL NOT change the selection; Tab, a key and a programmatic focus on a handle SHALL select its cut as before.

#### Scenario: A mouse press handed to a handle that already has focus
- **WHEN** the end of cut 1 and the start of cut 2 are 4 px apart, the end of cut 1 holds focus, and a mouse press lands 1 px right of cut 1's end, on cut 2's start, which lies on top
- **THEN** cut 1 is selected (the fields read "Cut 1 of g1.mp4"), "Cut 1 end of g1.mp4" holds focus, and nothing is edited, in Chrome and in Firefox

#### Scenario: A mouse press handed to a handle that does not have focus
- **WHEN** the same press lands while cut 2's start holds focus
- **THEN** the handle that took the press is selected and focused

#### Scenario: Tab still selects
- **WHEN** the operator tabs from cut 1's end to cut 2's start
- **THEN** cut 2 is selected
