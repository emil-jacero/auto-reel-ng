# Design

## Context

The workspace's clip bin (`editor-workspace-layout`, HLD D-28) draws, from the top:

1. `EventEditor`'s `bin` part: the new-clip line (`.edit-hint`, from `newClipsLine`) and the marks line (`.mark-line`:
   the Help row, `.mark-actions` with `.mark-rotate`, and the Move marked to… group).
2. One section per chapter (`ChapterDrag`):
   - a sticky one-line header bar (name, Edit Titlecard as `EditTitlecard.tsx`, count)
   - a tools row under it (`ChapterTools.tsx`: notes, Move up/down, Delete and Delete's refusal)
   - the clip rows in `ClipOrderList`'s `compact` variant

Measured and computed sizes, with a fine pointer:

- **Bin pane.** 240 px wide. About 391 px tall at 1280×720 (window 720, top bar 49, Timeline pane minimum 280) and
  about 509 px at 1440×900.
- **Marks line.** About 235 px. The bin is narrower than the line's one-row form, so the line wraps to its
  narrow-window form: Rotate on two rows, and the Move group on its own row with the label above.
- **New-clip line.** About 95 px when shown.
- **Chapter header and tools row.** About 60 + 50 px.
- **Compact row.** Three lines, `--clip-row-h: 6.3125rem` plus 16 px of padding, about 117 px. The two-line form
  starts only at `@container (width >= 22rem)`, which the bin never reaches.

The viewer's picture is 16:9 and limited by height: about 590 px wide in a 700 px column at 1280×720, and about
585 px in an 860 px column at 1440×900.

## Goals / Non-Goals

**Goals:**
- At 1280×720 the bin shows at least 3 whole clip rows on `Två kapitel - Tjörn`. At 1440×900 it shows all 4.
- Every control, name, description, reason and keyboard path stays. Only placement and visible words change.
- The stacked page (below 960 px, and the metadata fix editor) is untouched.

**Non-Goals:**
- The Timeline pane's height or chrome.
- Menus or overflow buttons.
- Moving tools to the inspector.
- Touch sizes: with a coarse pointer the 44 px rules stand, and the height limits apply only with a fine pointer.

## Decisions

### D1. The bin's width follows the window
`--ws-bin-w: clamp(240px, 22vw, 320px)` on `html[data-workspace]` (where the toast placement already reads it). This
gives 282 px at 1280 and 317 px at 1440. The viewer column loses 42–77 px of width it was not using. The picture
keeps its size, because its height limits it.

### D2. The marks line keeps its two rows, never more, in the bin
The line keeps the main spec's two-row structure:

- row 1: Help, the count and Clear marks
- row 2: Rotate left, Rotate right, then the Move group

In the bin it never wraps further. The changes, all in workspace CSS under `.event-editor-ws .mark-line` plus small
markup changes:

- **Rotate buttons.** Their words move into `.visually-hidden` spans inside the button, so the name is unchanged.
  `title` is set to the same words for the tooltip, and the icon stays.
- **Move group label.** The visible label "Move marked to…" becomes `.visually-hidden`. The group's `aria-labelledby`
  still points at it, and the picker keeps its own name.
- **Help toggle.** In the bin it is icon-only so row 1 fits at 282 px: the word "Help" is visually hidden, the button
  is 32 px square, and it gets `title="Help: Clips"` (its accessible name is unchanged). The toggle is one shared
  component, so its title is global: the stacked page's toggle shows the same tooltip. It is harmless there, and
  the spec asks only for the bin's tooltip.
- **Picker width.** The picker gets `flex: 1 1 auto; min-inline-size: 0`, and Move keeps its words.
  - About 282 − 24 px of padding = 258 px for 2×32 px Rotate buttons, about 64 px for Move and 3 gaps of 8 px.
  - That leaves the picker about 106 px, enough for "Choose a chapter" truncated by the native select.
- **Height and stickiness.** The line is `position: sticky; inset-block-start: 0` inside the bin pane, with the pane's
  surface as background and z-index above the rows. Both rows are always present, so its height is constant until the reason line or the Clips help opens; it then grows,
  and `--bin-toolbar-measured` (a ResizeObserver on the line) moves the chapter headings and the scroll padding with it.
  - Content: 2 × 32 + 8 = 72 px, plus 16 px of padding = 88 px. The border counts: the built line measured
    89 px with its 1 px border, so the spec's "at most 88" is met in code by taking 1 px off the padding
    (task 4.1), not by reading 88 without the border.
  - The bin's scroll padding grows by this height so focus-in-view clears it. `keepInView` already measures against
    `[data-ws-scroll]`, so only its padding value changes.

**Considered:** the one-row bar from the explore sketch, with the count, Rotate, picker, Move and Clear in one row.
It does not fit: 258 px leaves the picker under 60 px. It also changes how the main spec reads the line's rows, and
needs the count shown only as a number. Two fixed rows keep the spec's structure and still save about 150 px.

### D3. The chapter header bar holds its tools in the bin
`ChapterTools` renders its buttons, Move up, Move down and Delete, in two places. In the bin they go into the header
bar after the count, through a `placement: 'bar' | 'row'` prop. On the page they stay in their own row.

- **Notes and Delete's refusal** stay under the bar as lines. They show only when they apply, so they cost nothing in
  the common case.
- **Edit Titlecard** shows its icon only in the bin. Its accessible name, "Edit title card for <heading>", is
  unchanged, and `title` carries the visible words.
- **Icon buttons** are 28 px square with a fine pointer, so the bar is about 36 px.
- **Long names.** The name ellipsizes (it already does), and the full name is the buttons' and the bar's names.
- **Focus.** After Move up or Move down, focus stays on the pressed button, as today. The button is now in the sticky
  bar, so it can't scroll out of view.

### D4. Two-line rows from the bin's width
- **Breakpoint.** For a fine pointer the two-line grid moves from `@container (width >= 22rem)` to
  `@container (width >= 13.5rem)`, measured on the chapter container: the 240 px bin less its border and a
  scrollbar leaves 239 px, a 216 px content box, so 15rem would never apply.
  - A row has four tools (Move up, Move down, Rotate left, Rotate right), not two.
  - Line 1: handle, position, name, Move up and down (28 px icons), and from `@container (width >= 17rem)`
    (a bin of about 281 px, 1280x720) Rotate left and right too.
  - Line 2: thumbnail, length, status, Cuts, and in a bin under about 17rem (272 px, so the 240 px minimum
    to about 272 px) Rotate left and right after Cuts. The spec's two-line row wording says this.
  - The status is its icon alone on a fine pointer in the bin (its words stay as hidden text and a `title`), so
    line 2 is one line from 240 px. A fine pointer's rows are never taller than the limit.
  - `.clip-tools` is `display: contents`. In the bin Move comes before Rotate in the DOM, so tab order runs
    down the row (handle, name area, Move, Rotate, Cuts) with no step back. This DOM order also applies with a
    coarse pointer, where the 44 px areas stay (task 4.4 re-verifies them); the coarse layout has no `display:
    contents` tools, so the order only changes the tab sequence, not the picture.
- **Row height.**
  - `padding-block` goes from `--s-2` to `--s-1`; the column gap and inline padding to `--s-1`.
  - `--clip-row-h` becomes `3.7031rem`, measured once built, so `content-visibility` estimates stay right.
  - Target: at most 70 px per row with a fine pointer. Measured: 68 px at 240, 282 and 320 px bins, one estimate
    for every width.
- **Touch.** Under `pointer: coarse` the rows keep today's rules: three lines in the 240 px bin, two from 22rem, the
  16 px line gap and the 44 px touch rules. They are taller, and the height limits do not apply. A finger's tools
  (32 px, 28 px between pairs) would leave no name at 240 px.
- **Pass bar.** It counts the rows of clips a chapter plays. The ignored block is not a row (D6).
- **Width check.** Line 1 must fit its controls at 240 px:
  - 28 handle + 20 position + name + Move (56 px) + gaps of 4 px, and Rotate (56 px) from 17rem: the name is about
    100 px at 239 px (ellipsized) and keeps room for `s1710001.mp4` with Rotate from about 281 px.
    Longer names ellipsize as today.

### D5. No new-clip line in the bin
- **Bin.** In the workspace, `EventEditor` does not render `.edit-hint` in the bin.
- **Help.** `clipsHelpLines` gains the "joins `reel.yaml` once…" sentence while a new clip waits (the `waiting` case
  of `newClipsLine`).
- **Count.** The "Saving adds N new clips" count is already in the save summary (`EventEditor.tsx`, `adds N new clips
  to reel.yaml`), and so is in the top bar.
- **Stacked page.** Keeps the line as it is.

### D6. Ignored clips follow the chapters in the wide bin
Decision 2b (the user, round 2): the pass bar counts played rows only. On Tjörn (4 played clips, 1 ignored in
`Main`) the ignored block (caption 23.4 px + row 41.3 px = 64.7 px, about 106 px in the first measure) sits between
`Main`'s first clip and `Kvällen`, and costs rows.

- **Move, not collapse.** From 960 px the ignored clips leave their chapters and go into one block, always open,
  after the last chapter and before Add chapter, under an h2 "Ignored clips". Each chapter's ignored clips have a
  caption that names the chapter ("Main · 1 ignored clip, not played"). A pure helper, `ignoredGroups`, builds the
  groups (deleted chapters skipped, empty groups left out, names from the same inputs as the chapter's list, since
  Tjörn's ignored root `s1710004.mp4` and Kvällen's played `s1710004.mp4` share a visible name).
- **Why not a closed fold** per chapter: measured at 1280×720 it leaves 2 whole rows (shortfall -24.8 px; with a 4 px
  gap -8.8 px; only with a gap of 4 px and a 2 px row trim +3.2 px). A closed list also hides the clip that the
  delete refusal "Main still lists 1 ignored clip" points to, and needs a new control with normative words, state
  and target size.
- **Row budget** for 3 played rows at 1280×720 with the block moved out: 12 gap + 1 + 36 (Main header) + 68.3 +
  1 + 12 gap + 1 + 36 + 2 × 68.3 = 303.9 px against 303 px usable (137 to 440). The move alone gives +0.2 px, which is
  a knife edge.
- **Gap 12 → 8 px from 960 px.** The bin's grid gap drops, which gives about +8 px at 1280×720 (3 whole rows, the third
  ends at about 431.8 of 440) and about +59 px at 1440×900 (4 whole). A gap of 4 px (+16 px) is the documented
  fallback. The stacked layout keeps 12 px.
- **One DOM copy.** `compact` is true at every width in the workspace, and the stacked workspace still shows the bin
  (below 960 px), so the block's place follows `useWideBin()` (`matchMedia('(width >= 960px)')`, the pattern of
  `ChapterDrag.tsx`), not `compact`. Below 960 px each chapter lists its ignored clips as before.
- **Removed (missing) clips stay in their chapters.** Undo has to take focus under its chapter.
- **Counting.** The ignored clips still count as listed by their chapter, so "Main stays while it lists an ignored
  clip" and the delete refusal keep their words.
- **Risk.** The margin at 1280×720 is thin (about 8 px). The Playwright gate asks for at least 5 px to spare.
  A real 1280×720 browser window is shorter than the viewport the bar is defined on; that holds for every option.

## Research & Decisions

### Row budget at the target window
**Context**: The user's bar was "at least 4 clip rows at 1280×720".
**Explored**: Pane heights from the grid (`'tl' minmax(280px, 38vh)`, top bar 49 px), the compact row's
`--clip-row-h`, and screenshots from the `editor-workspace-layout` runs (`critic-dark-1440.png`).
**Decision**: The bar is 3 whole rows of played clips at 1280×720 on the two-chapter Tjörn event, and all 4 at
1440×900. The ignored clip is not a row of the bar.
**Rationale**: The first estimate, 391 − 88 − 36 − 70 − 36 = 161 px (2 more rows), left out the ignored block under
`Main` (about 65 px: a caption and a row) and the grid gaps. Round 1 measured 2 whole played rows at 1280×720 and 3
at 1440×900 with the block in place. D6 moves it out and trims the gap, giving 3 and 4. Four rows at 1280×720 need a
smaller Timeline pane, which is out of scope.

## Risks / Trade-offs

- **Icon-only tools rely on tooltips and names.** The user accepted icon-only buttons (explore, 2026-11-15). A new
  operator learns ↺/↻/✎/↑/↓/✕ from tooltips and the Clips help. Mitigation: the Help text names each icon.
- **A sticky toolbar covers a row's top as it scrolls under.** Scroll padding (D2) keeps a focused row clear. A
  dragged row auto-scrolls the pane, and dnd-kit's autoscroll threshold may need the toolbar height as an offset.
  Verify keyboard drag up past the toolbar.
- **The `content-visibility` estimate.** A wrong `--clip-row-h` makes the scrollbar jump. Measure after the build and
  set it.
- **Spec length.** The MODIFIED requirements are long already. The edits add one sentence or bullet each and no
  rewrites.
- **Status is icon-only in the bin rows (decision 1a).** The spec's "State is never shown by color alone" gets a
  carve-out for the bin's rows with a fine pointer: words stay as hidden text and a tooltip, and each status keeps its
  own icon. The words stay visible on the stacked page and with a coarse pointer.
- **Thin 1280×720 margin.** See D6.
