## ADDED Requirements

### Requirement: A trim made on the timeline is an edit of the same draft as a cut made in the Cuts panel

A cut changed on the Edit-mode Timeline ("Edit mode's cuts are trim handles") SHALL change the cut in the editor's draft, the one the clip's Cuts panel lists, and SHALL be saved, counted, guarded and undone as any other cut edit. There SHALL be no second list of cuts and no save path of the Timeline's own.

- **The cut keeps what it is.** A trimmed cut keeps its place in the clip's list, its number and its reason (a cut an analysis made keeps its reason; a trim does not make it `manual`). Only its start or end changes. The Cuts panel SHALL list the new times at once, and a cut trimmed back to the times it was read with SHALL leave nothing to save, so that an edit and its reverse show no save bar. A cut typed in the Cuts panel and then trimmed stays an added cut.
- **The save bar counts it.** The save bar SHALL say how many cuts were trimmed ("1 cut trimmed"), beside the cuts added and removed, counting a read cut whose saved start or end differs from the one read, on a clip whose saved cuts differ. A trim that leaves the saved cuts as they were SHALL count as nothing. Pressing Save SHALL send the same whole-document write under `If-Match` that every other edit sends, with the clip's changed `trims`: the service edits the span that changed in place and leaves the other spans, their comments and their style as authored ("A changed cut list edits only the spans that differ").
- **Guards and reset.** A trimmed cut SHALL make the event count as having unsaved changes (leaving Edit mode, navigating away and closing the tab ask first, Ctrl+S and Cmd+S save). Reset SHALL put every trimmed cut back to the times it was read with, and the Timeline SHALL show them.
- **A conflict.** When the save is refused because the event was changed elsewhere (412), the page SHALL show the conflict as for any edit, keeping the trims. "Reload latest (discard my changes)" SHALL discard the trims as it discards every edit (it leaves Edit mode and shows the event as read again, whose Timeline is closed and draws the cuts as saved), and "Overwrite with mine" SHALL write the trims over the latest.
- **Removed neighbours.** A removed cut is not a neighbour: a handle can be moved over the span of a removed cut. An Undo of that cut that would then overlap a cut is refused, as for a cut added in this Edit mode, and names the cut to remove first.
- **Past the clip.** The Timeline's clip length is its proxy's duration. A trim SHALL NOT write a cut that ends after it (a typed time past it is refused), and a cut read from `reel.yaml` that already ends after it is saved as read until its end is moved.
- **Nothing else is written.** Selecting a cut, moving the playhead, scrubbing, and a drag that was cancelled or that ended where it began SHALL write nothing and SHALL NOT count as an edit.

#### Scenario: A trim is saved as a change of one span
- **WHEN** on `2024-06-27 - Grillning med grannar`, `s1710001.mp4` has `trims: [{in: 1, out: 2.5, reason: black}]` with a comment on that line in `reel.yaml`, and the operator drags the cut's end to 3.5 s on the Timeline in Edit mode and presses Save
- **THEN** the save bar before saving says "1 cut trimmed", the write is one `PUT` under `If-Match`, and `reel.yaml` afterwards holds the same span with `out: 3.5`, `reason: black` and the comment, and nothing else changed

#### Scenario: A trim and its reverse leave nothing to save
- **WHEN** the operator trims a read cut's start from 1.0 s to 1.04 s with Right on its handle and then presses Left once on the same handle
- **THEN** the cut is back at 1.0 s, the Cuts panel lists it as read, and no save bar is shown

#### Scenario: A trimmed analysis cut keeps its reason
- **WHEN** a cut with the reason `freeze` is trimmed on the Timeline and saved
- **THEN** the span is written with the new times and the reason `freeze`

#### Scenario: The Cuts panel follows the Timeline
- **WHEN** the operator drags the start of cut 1 of `s1710001.mp4` to 0.5 s and the Cuts panel of that clip is shown
- **THEN** the panel lists cut 1 as 0:00.5 to 0:02.5, the Cuts control of the clip reads the new summary, and the edit is announced

#### Scenario: Reset puts the trims back
- **WHEN** two cuts are trimmed and the operator presses Reset
- **THEN** the Timeline draws both cuts at the times they were read with, no save bar remains, and no handle is selected

#### Scenario: A conflict keeps the trims
- **WHEN** the event's `reel.yaml` was changed elsewhere after Edit mode read it and the operator saves a trim
- **THEN** the page says that the event was changed elsewhere since the operator started editing and offers "Reload latest (discard my changes)" and "Overwrite with mine", and the Timeline still draws the trim
- **WHEN** the operator presses "Reload latest (discard my changes)"
- **THEN** the page leaves Edit mode with no trim kept, no save bar remains, and opening the read view's Timeline draws the cuts of the reloaded document

#### Scenario: Undo of a removed cut over a trimmed one
- **WHEN** cut 1 (1.0 to 2.5 s) is removed, cut 2 is trimmed to start at 2.0 s, and the operator presses Undo on cut 1
- **THEN** the Undo is refused in cut 1's row, naming cut 2 as the one to remove first, and cut 1 stays removed

#### Scenario: A look at a cut is not an edit
- **WHEN** the operator tabs through every handle, selects a cut, scrubs the playhead and starts and cancels a drag
- **THEN** no save bar is shown and leaving Edit mode asks nothing
