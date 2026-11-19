## ADDED Requirements

### Requirement: The Clip tab acts on several selected clips

With two or more clips selected, the Clip tab SHALL say how many and name them (five at most, then "and N more"), and
SHALL offer Rotate left, Rotate right, Move to… and Ignore clips, each one draft edit and one Undo step over every
selected clip it applies to. A rotate SHALL turn each clip a quarter from its own turn. Move to… SHALL put the clips at
the end of the chosen chapter, in play order; while it is applied it is the pending move of several clips.

#### Scenario: Three clips turned right
- **WHEN** on `2024-06-27 - Grillning med grannar` the clips `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4`, with
  turns 0, 90 and 270, are selected and the operator presses Rotate right in the Clip tab
- **THEN** their turns are 90, 180 and 0, "3 clips rotated right." is announced once, the three stay selected, and
  Undo says "Undo rotation of 3 clips"

#### Scenario: Moving two clips from two chapters
- **WHEN** on an event whose chapters are `Main`, `Kvällen` and `Test`, the operator selects `Main/a.mp4` and
  Ctrl+clicks `Kvällen/c.mp4`, chooses `Test` in the Clip tab's picker and presses Move
- **THEN**
  - `Test` plays what it played before and then `a.mp4` and `c.mp4`, last, in that play order
  - "2 clips moved to “Test”." is announced once, and keyboard focus stays on Move
  - the top bar says "2 clips moved", and both clips are still selected
- **WHEN** the operator saves
- **THEN** `reel.yaml` lists `a.mp4` and `c.mp4` last in `Test`'s clips and nothing else changed

#### Scenario: The clips already are last
- **WHEN** the two clips just moved are still selected and the operator presses Move with `Test` chosen again
- **THEN** "Nothing moved." is announced and the draft and the top bar are unchanged

#### Scenario: Ignoring several clips
- **WHEN** `s1710001.mp4` and `s1710003.mp4` are selected and the operator presses Ignore clips
- **THEN** neither is drawn, the bin lists both as ignored, the top bar says "2 clips ignored", nothing is selected,
  and one Undo brings both back

#### Scenario: Move says why it is unavailable
- **WHEN** two clips are selected and no chapter is chosen
- **THEN** Move is `aria-disabled`, not `disabled`, its description and tooltip say "Choose a chapter.", and pressing
  it changes nothing
- **WHEN** a save is pending
- **THEN** Rotate left, Rotate right, Move and Ignore clips say "Unavailable while saving." and change nothing
- **WHEN** only the Clip tab's Move of several clips is pending
- **THEN** Rotate left, Rotate right, Move and Ignore clips say "Unavailable while the clips move." and change
  nothing, the bin's Move marked to… says the same instead of "Unavailable while saving." and does not show as busy

#### Scenario: The selection is its own set of clips
- **WHEN** `s1710002.mp4` is marked in the bin, `s1710001.mp4` and `s1710003.mp4` are selected, and the operator
  moves the selection to `Kvällen` with the Clip tab's Move
- **THEN** only `s1710001.mp4` and `s1710003.mp4` moved, and `s1710002.mp4` is still marked where it was

## MODIFIED Requirements

### Requirement: The inspector follows the selection

The inspector SHALL show the tab for what is selected: Clip for one or more clips or a cut, Title card for a card,
Suggestion for a suggestion, and Event when nothing is selected. The operator MAY still pick another tab by hand; the
next selection SHALL pick the tab again. Each tab's controls SHALL edit the one draft, as every Edit-mode change does.

#### Scenario: Clip selected
- **WHEN** the operator presses the body of `s1710003.mp4`'s block on the track
- **THEN** the inspector shows the Clip tab with `s1710003.mp4`, "Kvällen · clip 2 of 3", its Trim In/Out fields,
  rotate buttons and its cuts

#### Scenario: Several clips selected
- **WHEN** the operator presses `s1710001.mp4` and Ctrl+clicks `s1710003.mp4`
- **THEN** the inspector shows the Clip tab saying "2 clips selected" with both names, Rotate left, Rotate right,
  Move to… and Ignore clips, and no Trim In/Out fields

#### Scenario: Nothing selected
- **WHEN** the operator presses Escape with a clip selected
- **THEN** nothing is selected and the inspector shows the Event tab with the Details form

### Requirement: The Clip tab edits the selected clip

With one clip selected, the Clip tab SHALL show the clip's name, chapter and position, and its length in the movie,
and SHALL offer Trim In and Trim Out as typed times, Rotate left and right, **Move to…**, the clip's cuts with remove
and "+ Cut at playhead", Use frame as poster. A typed trim SHALL be the same draft edit as the track's edge tools.
Move to… SHALL be a chapter picker named "Chapter to move <name> to", listing every chapter the draft lists but the
clip's own, and a Move button that puts the clip at the end of the chosen chapter, the edit a drop on that chapter's
band makes. While no chapter is chosen, or a save or a move of several clips is pending, Move SHALL be `aria-disabled`
and say why. An event with one chapter SHALL offer no Move to….

#### Scenario: Typed Trim In
- **WHEN** the operator types 0:01.50 into Trim In for `s1710001.mp4`
- **THEN** the clip's leading cut is 0 to 1.5 s in the draft, the block shortens and the clips after it move left

#### Scenario: Moving one clip to another chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` `Kvällen/s1710003.mp4` is selected and the operator chooses `Main` in
  the Clip tab's picker and presses Move
- **THEN** `s1710003.mp4` is drawn last in `Main`, the move is announced, keyboard focus stays on Move, and Undo says
  "Undo move of s1710003.mp4"

#### Scenario: One chapter, no Move to
- **WHEN** a clip of `2024-06-27 - Grillning med grannar`, whose clips are all in one chapter, is selected
- **THEN** the Clip tab offers no Move to…

### Requirement: Edit mode offers a clip's edits in a menu

In Edit mode a clip's menu SHALL be headed by the clip's name and list four groups: Rotate left and Rotate right;
Cut at playhead and Use frame as poster; Move to «chapter» for each other chapter the Timeline draws; Ignore clip.
Each item SHALL make the draft edit its Clip tab control makes (Move to: a drop on that chapter's band, at its end),
announced as there and undone in one step. The Clip tab SHALL keep all of these controls.

Opened on a clip that is one of two or more selected clips, the menu SHALL act on every selected clip it applies to:
it SHALL be headed by their count ("3 clips"), list Move to «chapter» for every chapter the Timeline draws, and name
the count in Ignore ("Ignore 3 clips"). Each item SHALL then make the edit the Clip tab makes for several clips ("The
Clip tab acts on several selected clips"), in one Undo step. Cut at playhead and Use frame as poster SHALL be
unavailable, with the reasons "Select one clip to cut at the playhead." and "Select one clip to use a frame as
poster.".

#### Scenario: The menu of a clip in Kvällen
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator opens the menu of `s1710002.mp4`, drawn in `Kvällen`
- **THEN** it is headed "s1710002.mp4" and lists Rotate left, Rotate right, Cut at playhead, Use frame as poster,
  Move to Main and Ignore clip, in that order, with a separator between the groups

#### Scenario: Rotate right from the menu
- **WHEN** the operator chooses Rotate right in the menu of `s1710002.mp4`
- **THEN** the clip is turned a quarter right on the track and in the picture, the turn is announced once, nothing
  is written, and Undo says "Undo rotation of s1710002.mp4"

#### Scenario: Move to another chapter
- **WHEN** the operator chooses Move to Main in the menu of `s1710003.mp4`
- **THEN** `s1710003.mp4` is drawn as the last clip of Main, after `s1710001.mp4`, "Moved s1710003.mp4. At the end of
  Main." is announced, the top bar says "1 clip moved", and Undo says "Undo move of s1710003.mp4"

#### Scenario: Cut at the playhead
- **WHEN** the playhead is at 0:02.00 of `s1710002.mp4`, which has no cuts, and the operator chooses Cut at playhead
  in its menu
- **THEN** the draft has a cut of that clip from 2.0 to 3.0 s, the cut "+ Cut at playhead" in the Clip tab makes,
  and the top bar says "1 cut added"

#### Scenario: Ignore from the menu
- **WHEN** the operator chooses Ignore clip in the menu of `s1710002.mp4`
- **THEN** it is no longer drawn, the bin lists it as ignored, and the top bar says "1 clip ignored"

#### Scenario: One chapter, no Move to
- **WHEN** the Timeline draws a single chapter and the operator opens a clip's menu
- **THEN** the menu has no Move to item

#### Scenario: The menu of three selected clips
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the clips `s1710001.mp4`, `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4` are selected and the operator right-clicks `s1710002.mp4` and chooses Rotate right
- **THEN** the menu was headed "3 clips", listed Move to Main and Move to Kvällen and "Ignore 3 clips", and showed
  Cut at playhead unavailable under "Select one clip to cut at the playhead."; all three clips are turned a quarter
  right, and one Undo turns them back

#### Scenario: Several clips moved from the menu
- **WHEN** the same three clips are selected and the operator chooses Move to Main in the menu
- **THEN** `Main` draws `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4` in that order, and "3 clips moved to
  “Main”." is announced

### Requirement: An unavailable item in the clip menu says why

An item that cannot act SHALL stay listed, shown as unavailable in more than colour and to assistive technology, with
its reason in words under it, as the Clip tab words it. While a save or a move of several clips (Move marked… or Move
to…) is pending, every item SHALL be unavailable under one line that says so. Choosing an unavailable item SHALL say
its reason once through the polite status, change nothing, and keep the menu open.

#### Scenario: The playhead is in another clip
- **WHEN** the playhead is in `s1710001.mp4` and the operator opens the menu of `s1710002.mp4`
- **THEN** Cut at playhead is unavailable under "Move the playhead into s1710002.mp4 to cut there.", Use frame as
  poster is unavailable under "Move the playhead into s1710002.mp4 to use a frame as poster.", and the other items
  are available

#### Scenario: During a save
- **WHEN** a save is pending, the operator opens a clip's menu and presses Enter on Rotate right
- **THEN** every item is unavailable under "Clip edits wait for the save or the move of several clips to finish.",
  those words are announced, the clip is not turned, and the menu stays open
