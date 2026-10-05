## ADDED Requirements

### Requirement: Edit mode's clip list draws only the rows near the view, without moving the page

Edit mode SHALL let the browser skip drawing the clip rows that are far out of view (CSS `content-visibility: auto`
on each row), giving every row not yet drawn a block size close to a drawn row's and every row once drawn the size it
was drawn at, so that the page's scroll height and the place of what is in view do not change as rows come into view.
Every row SHALL stay in the page while skipped: focusable by Tab, read by assistive technology, found by the browser's
find in page, a drop target for a drag, and reachable by keyboard reorder.

Rows coming into view SHALL NOT move the page: while the operator scrolls the list, the row at the top of the view SHALL
keep its place to within 1 px apart from the scroll itself. The page's scroll height after the whole list has been
scrolled through once SHALL differ from its height on opening by at most 5 %.

Nothing a row draws outside its own box SHALL be cut off by the skipping: the row's focus ring, the drop indicator and
the dragged row SHALL look as they did before, in the light and the dark scheme, at 1280 and at 390 px. Dragging a clip
(with the pointer and by keyboard), marking clips and moving the marked ones, Move up and Move down, rotating a clip, the
card dialog and the save bar SHALL work as before.

#### Scenario: Scrolling a 400-clip list moves nothing
- **WHEN** Edit mode shows an event of 400 clips in one chapter at 1280 and at 390 px, and the page is scrolled from
  the top to the bottom in steps of half a view, waiting two frames after each step
- **THEN** after each step the top row in view is where the step put it to within 1 px, and the scroll height at the
  end differs from the scroll height on opening by at most 5 %

#### Scenario: A drag to the end of a long list lands where it was shown
- **WHEN** the operator drags the first clip of a 400-clip chapter to the last slot of the last chapter, the page
  scrolling on its own across rows that were never drawn
- **THEN** the clip is dropped in the slot the drop indicator showed, and the draft's order says so

#### Scenario: Keyboard reorder far down the list
- **WHEN** the operator moves a clip down the list by keyboard past rows that were never drawn
- **THEN** the moved row keeps keyboard focus, is in view with its focus ring whole, and the announcement names its new
  place

#### Scenario: A skipped row is still found
- **WHEN** the operator tabs through the list, or searches the page for the name of the 390th clip
- **THEN** each row is reached in order and the 390th clip's row is scrolled into view and shown

#### Scenario: Nothing is cut off
- **WHEN** a row has keyboard focus, a drag shows its drop indicator, or a clip is being dragged, in the light and the
  dark scheme at 1280 and at 390 px
- **THEN** the focus ring, the indicator and the dragged row are drawn whole, as on the page before this change
