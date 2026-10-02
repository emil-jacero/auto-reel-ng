## Why

GUI v1 (HLD **§6 phase 8**, §4.10; **D-8** frontend stack, **D-10** visual system) is on main, and a review of
it found three CSS defects in the shared styles and the shell. They are all low severity, all visible to an
operator, and each was re-checked against the stylesheets on main `6a7fe16` for this change (design,
"Findings re-checked"). None needs a script or a new dependency:

- **Forced colors hide the busy loader on every button.** A busy button swaps its leading icon for a
  loader that `components.css` draws as `background: currentColor` through a mask. In the operating system's
  forced-colors mode the browser replaces that background with the system canvas color, so the masked box
  is invisible: the button shows a blank 1 rem gap where the loader should be, and the icon it replaced is
  hidden. The app's forced-colors rules (the segmented control, the job meter and live dot, the drag line, the
  preview) leave `.btn[aria-busy]` out. Busy is otherwise shown only by `aria-busy`, so a sighted
  forced-colors operator gets no sign that Render or Save was pressed.
- **A coarse pointer's 44 px Render hit area reaches into the row above.** Under `(pointer: coarse)` every
  `.btn` takes a tap in a 44 × 44 px area, grown evenly around its box. The list's `.btn-compact` Render is
  26 px tall, so its area grows 9 px upward. In the table layout the cell's top padding is 8 px, so the area
  covers the 1 px line that separates the row from the one above, and a tap there starts a render instead of
  opening the previous row (the whole row is a hit area, `openRow`). In the card layout the padding is
  12 px and nothing is reached.
- **The header's job counts stack on three lines near 480 px with a wider font.** The counts shrink to
  icons only below a fixed `30rem` viewport width, and the brand name hides at the same step. With a
  sans-serif wider than the design font (Liberation Sans, DejaVu Sans) the words need more room than the
  header leaves at 480-485 px, the two counts wrap onto separate lines beside the pill, and the header's
  48 px is not enough for three lines. The step is a guess about the font; the comment above it says "the
  last rem is for wider fonts".

## What Changes

- `web/src/styles/components.css`: a `@media (forced-colors: active)` rule that makes the busy loader keep
  the button's label color instead of the background the browser removes.
- `web/src/events/list.css`: under a coarse pointer and the table layout, the Render's hit area stops at the
  top of its cell's content and takes the rest of its 44 px below. The card layout is unchanged.
- `web/src/shell/shell.css`, `web/src/jobs/jobs.css`: the header's status slot becomes a size container, and
  the job counts' collapse to icons depends on the room that slot has, in the font's own units, instead of
  on the window's width. The counts no longer wrap among themselves.
- Specs (`web-app`): three MODIFIED requirements, one scenario each.

**Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump, and no staleness fingerprint input changes.
**Schema:** no `reel.yaml`, `config.yaml`, Alembic or rescan change. **Surfaces:** the GUI only; no CLI or
API change (Principle V), so nothing for the engine to also reach.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: "State is never shown by color alone" (a busy loader stays visible in forced colors), "Every
  control is large enough to touch" (a table row's control never reaches above its cell), and "The screens
  fit a phone-width window" (the header stays one bar tall with a wider font, its counts collapsing by the
  room they have).

## Impact

- **Package:** `web/` only. Four stylesheets, no TypeScript, no new dependency (Principle VII).
- **Gate:** `web-toast-and-dialog-layers` changes `shell.css` (the toast region's placement) and merges
  first. This change edits other rules of that file (`.shell-status` and the comment above the brand-name
  step); the implementation re-reads `shell.css` on the merged base before editing.
- **Verification** is ad hoc in a real browser (Playwright from the scratchpad, never committed; the web
  package has no test runner by design, D-8's dependency budget), plus `tsc --noEmit` and `npm run build`.

## Non-goals

- The brand name's own hide step (`30rem`, or `34rem` under a coarse pointer) and the pill's word hide
  below `23.5rem` stay viewport steps. Only the counts, which are the part that wraps, move to the room they
  have.
- Other `.btn-compact` placements (cards, Edit mode's rows, the cuts panel, the preview) are not reshaped;
  the findings measured only the list's table rows.
- No forced-colors audit of the rest of the app beyond the busy loader.
- No change to the theme control's widths or to any other header content.
