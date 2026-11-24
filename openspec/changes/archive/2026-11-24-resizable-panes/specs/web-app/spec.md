## ADDED Requirements

### Requirement: The workspace's pane borders can be dragged

From 960 CSS pixels wide, at any window height, three pane borders in Edit mode's workspace SHALL be draggable:
- the border between the bin and the viewer;
- the border between the viewer and the inspector;
- the border along the Timeline's top.

Dragging a border SHALL size its pane to follow the pointer. The other side pane and the Timeline SHALL keep their
sizes (but see a Timeline held short, below), and the viewer SHALL take up the difference. Sizes hold within
1 CSS pixel.

#### Scenario: Widening the bin
- **WHEN** Edit mode is open on `2024-08-20 - Två kapitel - Tjörn` in a 1440×900 window, nothing was resized before,
  and the operator drags the border between the bin and the viewer 100 CSS pixels to the right
- **THEN** the bin is 417 CSS pixels wide, the inspector is still 340, the Timeline is still 342 tall, the viewer is
  100 CSS pixels narrower, and the page does not scroll

#### Scenario: A taller Timeline and a save's explanation
- **WHEN** the operator drags the Timeline's top border 150 CSS pixels up in a 1440×900 window, and a save then
  answers 412
- **THEN** the Timeline is 492 CSS pixels tall, and the explanation's panel ends above the Timeline's new top

#### Scenario: The Timeline resizes in a short window
- **WHEN** Edit mode is open in a 960×600 window and the operator drags the Timeline's top border 20 CSS pixels down
- **THEN** the Timeline is 20 CSS pixels shorter and the page does not scroll

#### Scenario: Notifications follow the panes
- **WHEN** the operator has widened the bin and the inspector, and an error notification is shown
- **THEN** the notification sits over the top of the picture and overlaps neither the bin nor the inspector

### Requirement: Hiding or showing the bin moves a Timeline held short

A Timeline drawn shorter than its size because of the middle row's least height SHALL lengthen when the bin is hidden
and shorten again when the bin is shown, as that least height changes with the bin, once the bin's hide or show is
released. It is the one pane size another pane's border changes.

#### Scenario: Hiding the bin lengthens a Timeline held short
- **WHEN** the Timeline is kept 340 CSS pixels tall in a 1280×600 window with the bin shown, so that it is drawn
  the window's height minus the top bar minus 20rem tall (232 with a 48 px top bar, 231 with the 49 px bar drawn), and the operator drags the bin's border until the bin hides and releases it, and later drags the bin back
  out and releases it
- **THEN** the Timeline is the window's height minus the top bar minus 14rem tall (328 with a 48 px top bar, 327 with the 49 px bar drawn) while the bin is hidden, and as before once the bin is shown

### Requirement: A pane border shows itself under the pointer

From 960 CSS pixels wide, over a pane border the pointer SHALL show a resize cursor and the border SHALL be
highlighted. A border SHALL take the pointer within a few CSS pixels of its line without covering the centre of any
control in the panes beside it.

#### Scenario: Hovering a border
- **WHEN** Edit mode is open in a 1440×900 window and the pointer rests over the border between the bin and the
  viewer, and then over the Timeline's top border
- **THEN** the cursor is `col-resize` over the first and `row-resize` over the second, the line under the pointer is
  drawn highlighted, and no other control under the pointer reacts

### Requirement: A pane dragged past its least size hides

A border dragged so that its pane would be under its least size SHALL stop the pane at its least size. Dragged on
until the pane would be under half its least size, the pane SHALL be hidden and take no room, and the viewer (or, for
the Timeline, the row above it) SHALL take the room.

#### Scenario: The bin stops at its least width
- **WHEN** the operator drags the bin's border 150 CSS pixels to the left in a 1440×900 window with nothing resized
- **THEN** the bin is 240 CSS pixels wide and shown

#### Scenario: The bin hides
- **WHEN** the operator drags the bin's border 200 CSS pixels to the left in a 1440×900 window with nothing resized
  and releases it
- **THEN** the bin is hidden, the viewer is 317 CSS pixels wider, the inspector is still 340 wide and the Timeline
  still 342 tall, and a line stays at the window's left edge

### Requirement: A pane hides and comes back while the border is dragged

During a drag, the pane SHALL hide and come back as the pointer crosses half its least size, before the release. A
release SHALL keep what is shown. Escape before the release SHALL put the pane back as it was before the drag.

#### Scenario: A release just after the pane comes back
- **WHEN** the Timeline is 200 CSS pixels tall, and the operator drags its border down until the Timeline hides,
  moves straight back to near the start and releases it at once
- **THEN** the Timeline is shown 200 CSS pixels tall, its controls can be reached, and its border gives its size

#### Scenario: Escape after a drag that hid the pane
- **WHEN** the operator drags the inspector's border until the inspector hides and presses Escape before releasing it
- **THEN** the inspector is shown at its width before the drag and the selection is unchanged

### Requirement: A pane hidden only during a drag keeps focus

A drag that hides its pane on the way but ends with the pane shown, or is cancelled by Escape, SHALL leave keyboard
focus where it was before the drag.

#### Scenario: Focus survives a pane hidden only during the drag
- **WHEN** focus is in a field of the inspector, and the operator drags the inspector's border until the inspector
  hides, then drags back out until it shows and releases the border
- **THEN** the inspector is shown and the field still has focus; the same holds when the operator presses Escape
  instead of dragging back out

### Requirement: A hidden pane's border stays at the window's edge

A hidden pane's border SHALL stay at the window's edge the pane was hidden toward, drawn as a line, with the resize
cursor under the pointer. Dragging it out SHALL show the pane once the pointer is half the pane's least size from the
edge, at its least size, and then the pane SHALL follow the pointer.

#### Scenario: Dragging a hidden bin out
- **WHEN** the bin is hidden and the operator drags the line at the window's left edge 130 CSS pixels to the right,
  and then on to 300 CSS pixels from the edge, and releases it
- **THEN** the bin shows at 240 CSS pixels wide after the first part and is 300 CSS pixels wide after the release

### Requirement: A double-click or Enter shows a hidden pane

A double-click on a hidden pane's border, and Enter on it, SHALL show the pane at the size it had before it was hidden
(its default size if it was never resized), as far as the window allows. Enter on a shown pane's border SHALL hide
the pane.

#### Scenario: A double-click shows a hidden pane at its size
- **WHEN** the operator has made the bin 417 CSS pixels wide in a 1440×900 window, hidden it by dragging, and
  double-clicks the line at the window's left edge
- **THEN** the bin is shown 417 CSS pixels wide

#### Scenario: Enter hides and shows a pane
- **WHEN** the Timeline's border has focus in a 1440×900 window with nothing resized, and the operator presses Enter,
  and then Enter again
- **THEN** after the first Enter the Timeline is hidden and focus stays on its border; after the second the Timeline
  is shown 342 CSS pixels tall

### Requirement: A hidden pane is out of the way

A hidden pane SHALL NOT be drawn, SHALL NOT take the pointer, and nothing in it SHALL be reached by Tab or presented
to assistive technology. Its border SHALL stay in the Tab order. A pane left hidden while focus is inside it SHALL
leave focus on the page, where the workspace's keys act.

#### Scenario: Tab skips a hidden inspector
- **WHEN** the inspector is hidden, its border has focus, and the operator presses Tab
- **THEN** focus moves to the Timeline's border, and no control of the inspector was reached

#### Scenario: A hidden pane is not under the pointer
- **WHEN** the bin is hidden and the operator clicks 40 CSS pixels from the window's left edge, over the picture
- **THEN** no control of the bin reacts

### Requirement: A hidden Timeline keeps playing

Hiding the Timeline SHALL NOT stop playback or lose the Timeline's state. While it is hidden, the viewer's picture
and transport SHALL keep working, and so SHALL the workspace's keys.

#### Scenario: Playback survives a hidden Timeline
- **WHEN** the Timeline is playing in a 1280×720 window and the operator drags the Timeline's border 200 CSS pixels
  down and releases it
- **THEN** the Timeline is hidden, the picture keeps playing in the viewer without a pause or a restart, and Space
  then pauses it

### Requirement: A hidden inspector keeps up with the page

While the inspector is hidden, its tabs SHALL keep following the selection and keep what the Timeline puts in them. A
save refused at a field in a hidden inspector (the event's Details fields, a title card's field or a card style
field) SHALL show the inspector before it shows the refusal, whichever tab was shown.

#### Scenario: A hidden inspector keeps up with the selection
- **WHEN** the inspector is hidden, the operator clicks the clip block of `s1710002.mp4` on the track, and then shows
  the inspector
- **THEN** the inspector shows `s1710002.mp4`'s Clip tab with its trim fields

#### Scenario: A refusal in a hidden inspector
- **WHEN** the inspector is hidden with its Clip tab shown and a save is refused at the event's Details fields
- **THEN** the inspector is shown with its Event tab, and the refusal has focus

#### Scenario: A refusal in a hidden inspector already on its Event tab
- **WHEN** the inspector is hidden with its Event tab shown and a save is refused at the event's Details fields
- **THEN** the inspector is shown with its Event tab, and the refusal has focus

#### Scenario: A title card's refusal in a hidden inspector
- **WHEN** the inspector is hidden and a save is refused at a field of a title card
- **THEN** the inspector is shown with that card open, and the refusal is visible at its field

### Requirement: A hidden bin keeps its state, not its sound or its drops

Hiding the bin SHALL keep its lists and its player's shown clip, and SHALL close its player's open preview, as Hide
player does. A track drag SHALL NOT drop into a hidden bin.

#### Scenario: Hiding the bin closes its preview
- **WHEN** the bin's player is playing `s1710002.mp4` and the operator hides the bin, and later shows it
- **THEN** the preview stops when the bin hides, and the shown bin's player still shows `s1710002.mp4`

#### Scenario: No drop into a hidden bin
- **WHEN** the bin is hidden and the operator drags a clip block from the track to the window's left edge and
  releases it there
- **THEN** the clip is not ignored

### Requirement: A resized pane keeps the workspace usable

From 960 CSS pixels wide with a 16 CSS pixel root font, where there is room, shown panes SHALL keep these least
sizes: bin 240 and inspector 320 wide, Timeline 200 tall, viewer 20rem wide, middle row 20rem tall (bin shown) or
14rem (bin hidden). A resize SHALL stop at the viewer's or the middle row's least size and SHALL NOT push the other
side pane, except when a hidden side pane is shown ("Showing a hidden side pane may narrow the other").

#### Scenario: The viewer keeps its least width
- **WHEN** the operator drags the border between the viewer and the inspector as far left as it goes in a 1280×720
  window
- **THEN** the inspector stops where the viewer is 20rem wide, the bin keeps its width, and the page does not scroll

#### Scenario: The bin keeps its least width
- **WHEN** the bin's player is shown in a 1280×720 window and the operator presses Home on the bin's border
- **THEN** the bin is 240 CSS pixels wide and its player's controls are all visible

### Requirement: Showing a hidden side pane may narrow the other

When the window has no room for both side panes' kept sizes, showing a hidden side pane SHALL draw both in proportion,
each at or above its least size, so the other side pane MAY be drawn narrower than before. The narrower width SHALL NOT
be stored: the other pane's kept size is unchanged and returns when the window has room.

#### Scenario: Showing a hidden side pane in a window without room for both
- **WHEN** the bin is kept at 600 CSS pixels with the inspector hidden in an 1100×900 window (the bin is drawn at 600),
  and the operator shows the inspector by pressing Enter on its border
- **THEN** the inspector is shown at 331 CSS pixels (at least its 320 least size) and the bin is drawn narrower, at
  448 (at least its 240 least size), the viewer is at least 20rem wide, the stored bin size is still 600, and when the
  window is widened to 1440 the bin is 600 and the inspector 340 again

### Requirement: The side-by-side workspace never scrolls the page

From 960 CSS pixels wide the page SHALL NOT scroll, at any pane size, with any panes hidden, at any window height.

#### Scenario: Every pane hidden
- **WHEN** the operator hides the bin, the inspector and the Timeline in a 960×660 window
- **THEN** the viewer fills the window under the top bar, three lines stay at the window's edges, and the page does
  not scroll

### Requirement: The middle row at its least height stays usable

At its least height with the bin shown, a fine pointer and the information closed, the middle row SHALL show the
player whole (when shown), a list row and the viewer's transport whole. Otherwise the list SHALL keep its heading and
one row and the bin SHALL scroll rather than clip a control. Nothing in the bin SHALL be drawn over the Timeline. With the bin hidden, the transport SHALL be whole.

#### Scenario: The middle row at its least height
- **WHEN** the bin's player is shown and its information closed in a 1280×720 window with a mouse, and the operator
  presses End on the Timeline's border
- **THEN** the middle row is 20rem tall, the bin's player is whole, at least one row of the bin's list is visible,
  nothing in the bin is drawn over the Timeline, and the viewer's transport is whole

#### Scenario: The middle row at its least height with the information open
- **WHEN** the bin's player is shown and its information open in a 1280×720 window, and the operator presses End on
  the Timeline's border
- **THEN** the middle row is 20rem tall, nothing in the bin is drawn over the Timeline, and the information's toggle
  is inside the bin and can be pressed (the bin scrolls if its parts do not fit)

#### Scenario: The information's toggle in the untouched layout
- **WHEN** the bin's player is shown and its information open in a 1280×720 window with the panes untouched, with a
  mouse and, separately, with a coarse pointer
- **THEN** the information's toggle is inside the bin and can be pressed; with a mouse the bin has no scrollbar, and with a
  coarse pointer and the player shown the bin may scroll (the coarse player alone is about 383 px of the bin's 391), the
  toggle being reached by that scroll

#### Scenario: A taller Timeline with the bin hidden
- **WHEN** the bin is hidden in a 1280×720 window and the operator presses End on the Timeline's border
- **THEN** the middle row is 14rem tall and the viewer's transport is whole

### Requirement: A window too small for every least size shrinks panes, never hides them

Where the window cannot hold every least size of "A resized pane keeps the workspace usable" (a short window, or a
larger root font), the shown panes SHALL shrink to their least sizes and SHALL NOT be hidden; the viewer and the
middle row SHALL then give way; then content SHALL be cut or scrolled inside the panes (the bin's box scrolls rather than clipping a control). The
page SHALL NOT scroll, and nothing in the bin SHALL be drawn over the Timeline.

#### Scenario: A window too narrow for every least size
- **WHEN** the root font is 24 CSS pixels and the window is 960×900 with stored sizes for both side panes
- **THEN** the bin is 240 and the inspector 320 CSS pixels wide, neither is narrower or hidden, and the viewer takes
  the rest

#### Scenario: A window too short for every least size
- **WHEN** the bin's player is shown and the window is 960×500 with the Timeline kept 300 CSS pixels tall
- **THEN** the Timeline is 200 CSS pixels tall, no pane is hidden, nothing in the bin is drawn over the Timeline, and
  the page does not scroll

### Requirement: A pane border press changes only the pane

Pressing a pane border SHALL NOT move keyboard focus or change the selection. A press without movement SHALL change
nothing and store nothing. Escape during a drag SHALL put the pane back to the size it was drawn at before the drag.
A double-click on the border of a shown pane SHALL put it back to its default size. A drag SHALL NOT move either side
pane after the border is released.

#### Scenario: Escape during a drag
- **WHEN** a clip is selected and the operator drags the inspector's border and presses Escape before releasing it
- **THEN** the inspector is back to its width before the drag and the clip stays selected

#### Scenario: Escape in a window that shrinks the kept sizes
- **WHEN** the bin is kept at 600 and the inspector at 500 CSS pixels in an 1100×900 window, and the operator drags
  the bin's border and presses Escape before releasing it
- **THEN** the bin is back to the width it was drawn at before the drag, the viewer is at least 20rem wide and the
  page does not scroll sideways

#### Scenario: A drag in a window that shrinks the kept sizes
- **WHEN** the bin is kept at 600 and the inspector at 500 CSS pixels in an 1100×900 window, and the operator drags
  the bin's border to 380 CSS pixels and releases it
- **THEN** the bin stays 380 CSS pixels wide and the inspector keeps the width it had before the drag

#### Scenario: Hiding in a window that shrinks the kept sizes
- **WHEN** the bin is kept at 600 and the inspector at 500 CSS pixels in an 1100×900 window, and the operator hides
  the bin by dragging its border
- **THEN** the inspector is drawn at its kept 500 CSS pixels (the window no longer shrinks it), no kept size is
  rewritten, and showing the bin again, however often it is hidden and shown, draws the bin and the inspector at the
  widths they had before the first hide

#### Scenario: A double-click puts a pane back
- **WHEN** the operator has made the Timeline 400 CSS pixels tall in a 1440×900 window and double-clicks its border
- **THEN** the Timeline is 342 CSS pixels tall again and the stored size for the Timeline is gone

#### Scenario: A drag keeps the playhead keys
- **WHEN** the operator clicks a clip block on the track, drags the bin's border, releases it, and presses Right
- **THEN** the playhead moves one frame and the bin's width is unchanged by the key

### Requirement: Each pane border is a named separator in the Tab order

From 960 CSS pixels wide, each pane border SHALL be in the Tab order after the pane before it, whether its pane is
shown or hidden. It SHALL be presented as a separator named "Resize the clip bin", "Resize the inspector" or "Resize
the Timeline", with its pane's size in words, or that the pane is hidden.

#### Scenario: The border's name and value
- **WHEN** a screen reader reaches the bin's border in a 1280×720 window with nothing resized
- **THEN** it announces "Resize the clip bin", a separator, and "Clip bin 282 pixels wide"

#### Scenario: A hidden pane's border
- **WHEN** a screen reader reaches the inspector's border while the inspector is hidden
- **THEN** it announces "Resize the inspector", a separator, and "Inspector hidden"

### Requirement: Keys on a pane border move it

The keys on a focused pane border, with no Ctrl, Alt or Meta held:
- on the bin's and the inspector's border, Left and Right SHALL move the border 16 CSS pixels that way;
- on the Timeline's border, Up and Down SHALL do the same;
- Shift with any of them SHALL move it 64 CSS pixels;
- Home SHALL size the pane to its smallest shown size and End to its largest, showing a hidden pane.

These keys SHALL NOT also step the playhead or scroll.

#### Scenario: Right on the bin's border
- **WHEN** the bin's border has focus and the operator presses Right
- **THEN** the bin is 16 CSS pixels wider and the playhead has not moved

#### Scenario: End on the Timeline's border
- **WHEN** the Timeline's border has focus in a 1280×720 window with the bin shown and the operator presses End
- **THEN** the Timeline is as tall as it can be with the middle row 20rem tall, and the page does not scroll

### Requirement: Keys on a pane border hide and show it

On a focused pane border, with no Ctrl, Alt or Meta held, a key that moves the border into a pane already at its least
size SHALL hide the pane, and a key that moves it out of a hidden pane SHALL show the pane at its least size. Enter
SHALL hide a shown pane and show a hidden one at the size it had before it was hidden. A key held down SHALL NOT hide
or show a pane by its repeats: a held key stops at the least size, and a held Enter acts once.

#### Scenario: Past the least size by keys
- **WHEN** the bin is 240 CSS pixels wide, its border has focus, and the operator presses Left, and then Right
- **THEN** after Left the bin is hidden; after Right it is shown 240 CSS pixels wide

#### Scenario: A held key stops at the least size
- **WHEN** the bin is 300 CSS pixels wide, its border has focus, and the operator holds Left down for a second
- **THEN** the bin is 240 CSS pixels wide and shown; a further press of Left hides it

#### Scenario: A held Enter acts once
- **WHEN** the Timeline's border has focus with the Timeline shown and the operator holds Enter down for a second
- **THEN** the Timeline is hidden, and stays hidden until Enter is pressed again

### Requirement: Other keys on a pane border keep their meaning

With Ctrl, Alt or Meta held, an arrow on a focused pane border SHALL NOT resize the pane and SHALL be left to the
browser. With single-key shortcuts on, Space on a focused border SHALL be Play or Pause, whether the border was
reached by Tab or by a pointer; with them off, Space there SHALL do nothing.

#### Scenario: Alt+Right on the bin's border
- **WHEN** the bin's border has focus and the operator presses Alt+Right
- **THEN** the bin's width is unchanged and the playhead has not moved

#### Scenario: Space on a border reached by Tab
- **WHEN** single-key shortcuts are on, the operator tabs to the bin's border and presses Space
- **THEN** the Timeline plays and the bin's width is unchanged

### Requirement: Pane sizes and hidden panes are kept in the browser

A pane the operator resized SHALL keep its size, and a pane the operator hid SHALL stay hidden and keep its size for
when it is shown, for every event and on later visits in the same browser. When the browser keeps nothing, sizes and
hidden panes SHALL last for the page visit.

#### Scenario: The size is kept
- **WHEN** the operator widens the inspector to 420 CSS pixels, leaves Edit mode, reloads the page and opens Edit mode
  on another event
- **THEN** the inspector is 420 CSS pixels wide

#### Scenario: A hidden pane is kept hidden
- **WHEN** the operator hides the Timeline, reloads the page and opens Edit mode on another event
- **THEN** the Timeline is hidden, its border is at the window's bottom edge, and Enter on that border shows the
  Timeline at its size before it was hidden

### Requirement: A pane never resized follows its default size

A pane never resized, or put back, SHALL follow its default size, as far as the window allows:
- the bin, `clamp(240px, 22vw, 320px)`;
- the inspector, 340 CSS pixels;
- the Timeline, `minmax(280px, 38vh)`.

#### Scenario: Nothing resized looks as before
- **WHEN** Edit mode opens in a 1280×720 window in a browser that has no stored pane sizes
- **THEN** the bin is 282 CSS pixels wide, the inspector 340 and the Timeline 280 tall, as before this change, and no
  pane is hidden

#### Scenario: An untouched Timeline in a short window
- **WHEN** Edit mode opens in a 960×600 window with the bin shown and nothing stored
- **THEN** the Timeline is shorter than 280 CSS pixels so that the middle row is 20rem tall, and it is at least 200

### Requirement: Kept pane sizes fit the window

When the window is too small for the sizes the panes want, kept or default, the shown panes SHALL shrink toward their
least sizes so the limits hold, two shown side panes each giving up the same share of their width above their least
width. The kept sizes SHALL NOT be forgotten, and a window large enough again SHALL show them.

#### Scenario: A narrower window, then wider again
- **WHEN** the operator has made the bin 600 and the inspector 500 CSS pixels wide in a 1440×900 window, and the
  window is narrowed to 1100 and widened to 1440 again
- **THEN** at 1100 the bin is 386 and the inspector 393 CSS pixels wide (each within 1), the viewer is at least 20rem
  wide and the page does not scroll; at 1440 the bin is 600 and the inspector 500 again

#### Scenario: A shorter window, then taller again
- **WHEN** the operator has made the Timeline 340 CSS pixels tall in a 1280×720 window with the bin shown, and the
  window is made 600 tall and then 720 tall again
- **THEN** at 600 the Timeline is shorter so the middle row is 20rem tall, and it is at least 200; at 720 it is 340
  again

### Requirement: Stacked panes have no borders and no hidden panes

Below 960 CSS pixels wide no pane border SHALL be shown or reached by Tab, no pane SHALL be hidden whatever is stored,
and the panes SHALL stack as before.

#### Scenario: Stacked panes have no borders
- **WHEN** the window is 390 CSS pixels wide with stored pane sizes and the inspector stored as hidden
- **THEN** the panes are stacked as before, the inspector included, no pane border is shown or reached by Tab, and
  the page does not scroll sideways

#### Scenario: A bin stored hidden works when stacked
- **WHEN** the window is 390 CSS pixels wide with the bin stored as hidden
- **THEN** the bin's player is shown and plays its clip, and a clip block dragged from the track into the bin is
  ignored, as a drop into a shown bin is

## MODIFIED Requirements

### Requirement: Workspace shortcuts never act in fields, dialogs, a clip preview or a drag

A workspace shortcut SHALL NOT act, and SHALL leave the key to the browser, in any of these cases:
- focus is in a text field, a select or editable text;
- a dialog is open, or focus is inside an open clip preview or anywhere in the bin's player, open or not;
- a drag on the track or in the bin, or a drag of a pane border, is in progress, or an input-method composition is in
  progress;
- the focused control took the key itself;
- an arrow is pressed on a focused widget that takes arrows (a slider, a radio group, a tab list, a list box, a menu,
  a spin button or a pane border).

#### Scenario: Typing a title with a space
- **WHEN** focus is in Title and the operator types "Två kvällar"
- **THEN** the field reads "Två kvällar" and the Timeline does not play

#### Scenario: Arrows on the Zoom slider
- **WHEN** the Zoom slider has focus and the operator presses Right
- **THEN** the slider zooms one step and the playhead does not move

#### Scenario: Space during a trim drag
- **WHEN** the operator drags a trim handle and presses Space before releasing it
- **THEN** the Timeline does not start or stop playing

#### Scenario: Space on the player's Play after a click on a row's frame
- **WHEN** the operator presses the frame of `s1710002.mp4`'s row in the bin with the pointer, which moves keyboard
  focus to the player's Play, and presses Space
- **THEN** the player plays `s1710002.mp4`, and the Timeline does not play

#### Scenario: Arrows on a pane border
- **WHEN** the inspector's border has focus and the operator presses Left
- **THEN** the inspector is 16 CSS pixels wider and the playhead does not move

#### Scenario: Space during a pane border drag
- **WHEN** the operator drags the Timeline's border and presses Space before releasing it
- **THEN** the Timeline does not start or stop playing

### Requirement: The workspace lists its keyboard shortcuts

The top bar SHALL hold a "Keyboard shortcuts" button at its right, and `?` SHALL open the list wherever a workspace
shortcut acts. The list SHALL name, in words and grouped Playback, Zoom, Editing and Mouse, every key the workspace
layer answers and every key of the playhead, the track, the clip handles and the pane borders that shares one, built
from the keys the workspace handles, and the pane borders' keys, drag and double-click. It SHALL NOT be modal.
Escape, the button or a click outside SHALL close it, and Escape SHALL then leave the selection as it is.

#### Scenario: Opening the list
- **WHEN** the operator presses `?` with focus on the track
- **THEN** the list opens and shows "Space: Play or pause", "Q: Trim the clip's start to the playhead" and
  "Ctrl+wheel over the Timeline: zoom"

#### Scenario: The pane borders in the list
- **WHEN** the operator opens the list
- **THEN** Editing shows "On a pane border: move it (Shift: further), past its smallest size to hide it", "On a pane
  border: the pane's smallest or largest size" and "On a pane border: hide or show the pane", and Mouse shows "Drag a
  pane border: Resize the pane; past half its smallest size it hides" and "Double-click a pane border: Put the pane
  back to its first size, or show it again"

#### Scenario: Escape closes only the list
- **WHEN** a clip is selected, the list is open, and the operator presses Escape
- **THEN** the list closes and the clip stays selected

#### Scenario: Keys work with the list open
- **WHEN** the list is open and the operator presses Space with focus on the playhead
- **THEN** the Timeline plays and the list stays open
