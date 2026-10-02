## Context

See proposal.md, "Why". The code this change edits, on main `6a7fe16` (the gate `web-toast-and-dialog-layers`
merges first and also edits `shell.css`; see "Files and the gate"):

- **`web/src/styles/components.css`, `@layer components`.**
  - `.btn[aria-busy='true']::before` (lines 78-86) is the busy loader: a 1 rem box,
    `background: currentColor`, cut to a spinner shape by `mask: url(svg) center / contain`. The button's own
    leading `svg` is hidden (`> svg:first-child { display: none }`). Busy buttons are `aria-disabled`, never
    natively `disabled` (`RenderControl.tsx`, `SaveBar.tsx`), and are excluded from the disabled opacity.
  - Its one forced-colors rule is for `.segmented` (lines 374-381). `jobs.css` already has the pattern this
    change follows: `.live-dot { forced-color-adjust: none; background: CanvasText }`.
  - Under `(pointer: coarse)` (lines 829-841) every `.btn`, `.segmented label` and `.toast-action` gets a
    `::after` hit area with `inset: min(-1px, calc(50% - 1.375rem))`. Insets count from the padding box; `50%`
    is half its size and `-1px` takes in the border.
  - `.data-table td` has `padding: var(--s-2) var(--s-3)` (8 px above) and a 1 px `border-bottom`, so the
    first pixel above a cell's top padding is the previous row's divider.
- **`web/src/events/list.css`, `@layer screens`** (after `components`, so its rules win without more
  specificity). The job cell (`td.cell-job`, `LiveJobCell.tsx`) holds the Render, a `.btn.btn-secondary.btn-compact`
  (`min-block-size: 1.625rem`, 26 px; padding box 24 px). A wide panel (`@container (width >= 50rem)`) is a
  table; a narrow one turns each row into a card (padding `--s-3` = 12 px).
- **`web/src/shell/shell.css`, `@layer screens`.** `.app-header-inner` is a flex row: brand (`flex: none`),
  nav, `.shell-status` (`display: flex; min-inline-size: 0; margin-inline-start: auto`, holding the
  `JobsIndicator`), the theme control. The brand name hides at `@media (width < 30rem), (pointer: coarse)
  and (width < 34rem)`; the comment there says "the last rem is for wider fonts".
- **`web/src/jobs/jobs.css`, `@layer components`.** `.jobs-indicator` is a wrapping flex (pill, then
  `.jobs-counts`); `.jobs-counts` is a wrapping flex of `.jobs-count` units (each `white-space: nowrap`,
  joined by a `·`). `@media (width < 30rem)` shrinks a count to its icon and number (the words become
  visually hidden) and drops the `·`. Only `JobsIndicator` renders these classes, only in the header.

### Findings re-checked

- **Busy loader.** Confirmed by reading: in forced colors the UA forces `background-color` to a system color
  (Canvas family) wherever `forced-color-adjust: auto` applies, so the masked box takes the canvas color
  and the loader vanishes, while the icon it replaced is `display: none`. `mask` and `color` are not
  overridden (`color` becomes `ButtonText`). Verified by Playwright `forcedColors: 'active'` (task 3.1);
  before the fix the loader's pixels equal the button's background.
- **Hit area.** Arithmetic confirmed on the current CSS: border box 26, padding box 24, area inset
  `min(-1px, 12px - 22px)` = `-10px` from the padding box, 9 px beyond the border box on each side. In the
  table the button's top is at or below its cell's content top, which is 8 px below the cell's top, so the
  area reaches 9 - 8 = 1 px above the cell, onto the previous row's `border-bottom`. In a card (`--s-3`
  padding, then a 4 px row gap) it stays inside the card's own padding. The row opens its event on click,
  so a tap on that pixel line starts a render instead.
- **Header counts.** The mechanism is confirmed by reading; the measurement is part of task 3.3. At 480 px
  with the brand name still shown, the status slot has roughly (480 − 2 × gutter − mark − name − nav −
  theme − gaps) of room, and the words form needs the pill plus "99 rendering · 99 queued" beside it. A
  font wider than the design font moves that need past the room, `.jobs-counts` wraps between the two
  counts, and pill + two lines no longer fit 48 px. The triage's own sketch ("`flex-wrap: nowrap` on
  `.shell-status`") is already true of that rule: the wrapping is in `.jobs-indicator` and `.jobs-counts`.

## Goals / Non-Goals

**Goals:**

- Each of the three defects is fixed in CSS, with no markup, script or dependency added.
- The counts' collapse follows the room the slot actually has, so a font change moves it by itself.
- Fine pointers, and every layout the findings did not name, are pixel-for-pixel what they were.

**Non-Goals:**

- A general font-fallback audit of the app. Only the header's status slot is made font-resilient.
- Touching the rest of the header's responsive steps (brand name, pill words, theme options).

## Decisions

### The busy loader keeps the button's text color in forced colors

**Context**: A masked `background: currentColor` box is a background, which forced colors replaces.

**Explored**: (a) drop the mask and draw the loader with `border` (borders are kept in forced colors, as
`.job-bar` does); (b) `forced-color-adjust: none` on the pseudo-element with an explicit system color;
(c) swap the icon for the existing `loader` icon element in markup.

**Decision**: (b), in `components.css` next to the segmented rule:

```css
@media (forced-colors: active) {
  .btn[aria-busy='true']::before {
    forced-color-adjust: none;
    background: ButtonText;
  }
}
```

**Rationale**: Same fix, same shape as `.live-dot` (`CanvasText`) and `.job-bar` in `jobs.css`; no markup
and no change in the normal-color look. `ButtonText` is the color forced colors gives every button label,
and busy buttons are never natively disabled, so no `GrayText` case exists. (a) redraws a working spinner
for one mode; (c) changes call sites for a CSS-only problem.

**Failure behavior**: A browser that does not know `forced-color-adjust` simply ignores the rule and
shows what it showed before.

### The table hit area stops at the cell's top

**Context**: The area is symmetric around the box. In a table the room above the button is the cell's 8 px
padding, so the symmetric growth of 9 px crosses it by 1 px. The room below is the same 8 px plus the
divider and the next row's padding, so a 44 px area can take its missing pixel there without reaching any
control.

**Explored**: (a) cap both sides at 8 px: the area becomes 42 px, under the spec's 44; (b) pad the cell
(moves the layout, which the findings say not to do); (c) cap the top, give the rest to the bottom.

**Decision**: (c), in `list.css`, in the same condition as the table layout and the coarse pointer:

```css
@container (width >= 50rem) {
  @media (pointer: coarse) {
    .event-table .cell-job .btn-compact::after {
      /* 8px above the border box = the cell's padding; the divider is not ours */
      inset-block-start: calc(-1px - var(--s-2));
      /* the rest of 44px below: 8 above + the 26px border box + 10 below */
      inset-block-end: min(-1px, calc(100% + var(--s-2) + 1px - 2.75rem));
    }
  }
}
```

(`100%` is the padding box height, 24 px; an inset counts from the padding box, so the 1 px border is added
to the reach: the top inset is `-9px` and the bottom `-11px`, and the area is 44 px, from 8 px above the
border box to 10 px below it. A first draft of this rule, `calc(1px - var(--s-2))`, subtracted the border
instead of adding it and gave `-7px`/`-13px`, an area from 6 px above to 12 px below; the browser check of
task 3.2 caught it by measuring the reach, and the measured values are the ones written here.) Inline
insets are the existing ones.

**Rationale**: Keeps 44 px, moves no box, and is scoped to the one selector the finding measured. Under a
fine pointer the rule does not apply.

**Known edge**: In a row whose job cell holds only the button, the cell is 8 + 26 + 8 px plus its 1 px divider,
so the area's 10 px below the button reaches 1 px into the next row's top padding (the pre-fix area, 9 px,
ended exactly at the divider). Rows with a job (a status line under the button's) have more room. Task 3.2
measures both edges with `elementFromPoint`. If the next row's padding pixel answers with this Render,
the fallback is decided here and not left to the implementer: the bottom stops at the divider
(`inset-block-end: calc(1px - var(--s-2) - 1px)`), the area is 43 px in that minimum row, and the spec's
"44 pixels tall" is read as "where the cell has the room". The spec states only the top rule, which is the
reported defect.

**Measured**: on every row the dev library has, the cell is 61 px or taller (the event cell's title and
location set the height), so the area's bottom ends inside the cell and no next-row pixel answers. Only a
synthetic row, stripped to the Render alone (43 px), reaches the next row's first pixel, by 1 px and only
where layout rounds that way. A row that short does not exist, so the fallback is not applied: it would
trade a pixel of the 44 px target in every real row for a case none has.

**Alternatives**: Applying the cap to every `.btn-compact` in a `.data-table` was rejected: only the
list's job cell was measured, and the attention table and other tables have no compact buttons.

### The header's counts collapse by the status slot's own width

**Context**: A viewport breakpoint can not know the font, and the font decides the words' width. The
container query is the only CSS tool that measures the room an element actually gets, and the slot's room
is what the siblings (brand, nav, theme control, all font-dependent) leave.

**Explored**: (a) raise the fine-pointer step to ~32 rem (the triage's alternative): still a guess about the
font, and costs every font the words between 30 and 32 rem; (b) a container query on the header: the header
is the window wide, so it measures the viewport again; (c) a script that measures and toggles a class:
flicker, a ResizeObserver for a CSS question; (d) make the slot itself the container.

**Decision**: (d). In `shell.css`, `.shell-status` takes the remaining room and is a size container; in
`jobs.css` the collapse rules move from `@media (width < 30rem)` to `@container shell-status (...)`:

```css
/* shell.css */
.shell-status {
  display: flex;
  flex: 1 1 0;               /* the room brand, nav and theme leave; replaces margin-inline-start: auto */
  justify-content: flex-end;
  align-items: center;
  gap: var(--s-2);
  min-inline-size: 0;
  container: shell-status / inline-size;
}

/* jobs.css */
.jobs-counts { flex-wrap: nowrap; }       /* the two counts never stack */
@container shell-status (inline-size < 22ch) { /* the former @media (width < 30rem) body */ }
```

`N` is measured, not guessed (task 3.3): the counts "99 rendering · 99 queued" on one line, in the status
text size, over the widest sans-serif in the check set, plus a margin. The pill is left out on purpose: the
indicator already wraps, so when the pill and the counts do not fit side by side the pill takes its own
line above the counts, two short lines that fit the header (the shape the stylesheet gave at those widths
before this change). Counting the pill too (26.7 ch) collapsed the words up to about 100 px of window
earlier than needed. The measured need is 19.2 ch in DejaVu Sans and 19.7 ch in Liberation Sans, so `N` is
22 ch. It is written in `ch`, which a container query resolves against the container's font, so the
threshold moves with the font along with the siblings that shrink the slot. `N` does not know how many jobs
there are: it is sized for the widest counts (99 and 99), so a short count such as "1 rendering" also
becomes icons below it, and counts wider than that would need a larger `N`. With `container-type:
inline-size` the slot's width no longer depends on its content, which is why `flex: 1 1 0` is needed: the
brand, nav and theme control keep their content widths and the slot takes what is left. No size cycle
exists, because none of the siblings depends on the slot.

**Rationale**: Fixes the cause (a font-dependent need against a font-dependent room) instead of moving the
guess. A phone at 390 px keeps today's icons-and-numbers form, because the slot is far below `N` there; the
form between 480 and 520 px now depends on the font. The existing `wrap` on `.jobs-indicator` stays: pill and
counts may be two short lines, as designed, but `.jobs-counts` cannot add a third.

**Failure behavior**: Where container queries are not supported, the words show everywhere and the counts
can overflow the slot at phone width. The app already depends on container queries for its tables
(`@container (width >= 50rem)`), so no browser that renders the app reaches that case.

### Files and the gate

`web-toast-and-dialog-layers` edits `shell.css` (the toast region's placement and `html`'s scroll padding),
`edit.css`, `toast.ts`, `ToastRegion.tsx` and `Dialog.tsx`. This change edits other rules in `shell.css`
(`.shell-status`, and the comment above the brand-name step) and no file the gate edits except that one.
Implementation starts from a base that already has the gate; task 1.1 re-reads `shell.css` there. If the
gate moved `.shell-status` or the brand-name step, the edits follow the rules, not the line numbers.

## Risks / Trade-offs

- [The `ch` threshold fits two fonts but not a third] → The verification sweep covers Liberation Sans and
  DejaVu Sans (the widest common fallbacks) at 320-560 px in 10 px steps with the widest counts, and the
  margin on `N` is stated in the task; the comment above the rule says what `N` was measured from.
- [Three-digit counts overflow the slot at 320-330 px] → Accepted, and not clipped. Measured on the build: with
  150 rendering and 150 queued the icons form is wider than the slot (about 65 px at 320 px, 74 px at 330 px)
  and spills over the navigation at 320 px (Liberation Sans fails there only, DejaVu Sans at both widths); every
  other width and font passes. Letting the counts shrink with `overflow: hidden` would cut digits and show a
  wrong number ("150" as "15"), which is worse than a visible overlap that needs a backlog of 100 or more
  jobs on the narrowest phones. The spec sizes the counts for 99, as `N` is. The baseline fails at the same
  widths, so this is not a regression.
- [`flex: 1 1 0` on the slot changes where a long pill sits] → `justify-content: flex-end` keeps it against
  the theme control as `margin-inline-start: auto` did; the sweep compares the rect of the pill before and
  after at 1280, 768 and 390 px and finds no difference at widths where the words fit.
- [The bottom of the table hit area passes the row's divider by 1 px in a minimum-height row] → Measured in
  task 3.2; the fallback is in "Known edge".
- [A coarse-pointer desktop (touch laptop) at 800+ px gets the table rule] → That is the case the rule is
  for.

## Migration Plan

None. Pure CSS in four files; reverting a file reverts its fix. No bundle, API or data change.
