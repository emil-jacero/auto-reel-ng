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
- **Picker width.** The picker gets `flex: 1 1 auto; min-inline-size: 0`, and Move keeps its words.
  - About 282 − 24 px of padding = 258 px for 2×32 px Rotate buttons, about 64 px for Move and 3 gaps of 8 px.
  - That leaves the picker about 106 px, enough for "Choose a chapter" truncated by the native select.
- **Height and stickiness.** The line is `position: sticky; inset-block-start: 0` inside the bin pane, with the pane's
  surface as background and z-index above the rows. Both rows are always present, so its height is constant.
  - Content: 2 × 32 + 8 = 72 px, plus 16 px of padding = 88 px.
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
  - Line 1: handle, position, name, Move up and down (28 px icons), and from `@container (width >= 17rem)`
    (a bin of about 281 px, 1280x720) Rotate left and right too.
  - Line 2: thumbnail, length, status, Cuts, and below 17rem Rotate.
  - The status is its icon alone on a fine pointer in the bin (its words stay as hidden text and a `title`), so
    line 2 is one line from 240 px. A fine pointer's rows are never taller than the limit.
  - `.clip-tools` is `display: contents`. In the bin Move comes before Rotate in the DOM, so tab order runs
    down the row (handle, name area, Move, Rotate, Cuts) with no step back.
- **Row height.**
  - `padding-block` goes from `--s-2` to `--s-1`; the column gap and inline padding to `--s-1`.
  - `--clip-row-h` becomes `3.7031rem`, measured once built, so `content-visibility` estimates stay right.
  - Target: at most 70 px per row with a fine pointer. Measured: 68 px at 240, 282 and 320 px bins, one estimate
    for every width.
- **Touch.** Under `pointer: coarse` the rows keep today's rules: three lines in the 240 px bin, two from 22rem, the
  16 px line gap and the 44 px touch rules. They are taller, and the height limits do not apply. A finger's tools
  (32 px, 28 px between pairs) would leave no name at 240 px.
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

## Research & Decisions

### Row budget at the target window
**Context**: The user's bar was "at least 4 clip rows at 1280×720".
**Explored**: Pane heights from the grid (`'tl' minmax(280px, 38vh)`, top bar 49 px), the compact row's
`--clip-row-h`, and screenshots from the `editor-workspace-layout` runs (`critic-dark-1440.png`).
**Decision**: The bar is 3 whole rows at 1280×720 on the two-chapter Tjörn event, and all 4 at 1440×900.
**Rationale**: 391 − 88 (toolbar) − 36 (Main header) − 70 (row) − 36 (Kvällen header) = 161 px, which holds 2 more
whole rows, so 3 in all. Four rows need a smaller Timeline pane, which is out of scope.

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
