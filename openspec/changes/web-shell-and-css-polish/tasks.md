## 1. Base

- [ ] 1.1 Confirm the base and re-read the rules this change edits (design, "Context" and "Files and the gate"). Stop and report on any mismatch.
  - `git merge-base --is-ancestor 6a7fe16 HEAD` succeeds, and `ls openspec/changes/archive/ | grep web-toast-and-dialog-layers` shows the gate is archived (or `git log --oneline -- web/src/ui/toast.ts` shows its commit).
  - `web/src/styles/components.css` still has `.btn[aria-busy='true']::before` with `background: currentColor` and a `mask`, and no `forced-colors` rule that names `.btn`.
  - `web/src/events/list.css` has the `@container (width >= 50rem)` block and `web/src/jobs/LiveJobCell.tsx` renders the Render as `btn btn-secondary btn-compact` in `td.cell-job`.
  - `web/src/shell/shell.css` has `.shell-status` (find it by name: the gate edits other rules of this file) and the brand-name `@media (width < 30rem), (pointer: coarse) and (width < 34rem)` step; `web/src/jobs/jobs.css` has `@media (width < 30rem)` shrinking `.jobs-count` and `.jobs-counts`.
  - Write down, in the task's notes, the current text of `.shell-status` and of that `jobs.css` block, as merged.

  Verify: `openspec validate web-shell-and-css-polish --strict` passes. If the gate changed the two `shell.css` rules named here, re-base the MODIFIED blocks in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md` first.

## 2. web/ — styles

- [ ] 2.1 In `src/styles/components.css`, next to the segmented forced-colors rule, add `@media (forced-colors: active) { .btn[aria-busy='true']::before { forced-color-adjust: none; background: ButtonText; } }` (design, "The busy loader keeps the button's text color in forced colors"). No other rule changes; the normal-color loader stays `currentColor`.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the `node:22` container (`podman run --rm -v $WT/web:/app:Z -w /app docker.io/library/node:22 ...`)
  - `grep -n "forced-colors" web/src/styles/components.css` shows two blocks (segmented, busy loader)
  - the browser check of 3.1 passes
- [ ] 2.2 In `src/events/list.css`, add the table-layout cap (design, "The table hit area stops at the cell's top"): inside `@container (width >= 50rem)` and `@media (pointer: coarse)`, `.event-table .cell-job .btn-compact::after` gets `inset-block-start: calc(1px - var(--s-2))` and `inset-block-end: min(-1px, calc(100% + var(--s-2) - 1px - 2.75rem))`, with a comment saying why the top stops at the cell. The card layout and every fine-pointer rule stay as they are.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff --stat web/src/events/list.css web/src/styles/components.css` shows `list.css` with one added rule and no change to the `components.css` coarse-pointer block
  - the browser check of 3.2 passes
- [ ] 2.3 Make the header's counts follow their room (design, "The header's counts collapse by the status slot's own width"):
  - `src/shell/shell.css`: `.shell-status` becomes `flex: 1 1 0; justify-content: flex-end; container: shell-status / inline-size`, replacing `margin-inline-start: auto`; update the comment above the brand-name step so it no longer says the last rem is for wider fonts (the counts no longer need it).
  - `src/jobs/jobs.css`: `.jobs-counts` gets `flex-wrap: nowrap`; the body of `@media (width < 30rem)` moves to `@container shell-status (inline-size < Nch)`, with `N` measured in 3.3 and a comment naming what it was measured from (the pill "Live" plus "99 rendering · 99 queued", over the widest font of the sweep, plus the margin). The comment on the block no longer says "phone".
  - `web/README.md`, "Design system": the `shell-status` line says the slot is a size container, and the Touch bullet says a table row's Render area stops at its cell's top.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `grep -n "width < 30rem" web/src/jobs/jobs.css` prints nothing, and `grep -n "container: shell-status" web/src/shell/shell.css` hits once
  - `git diff --stat` for the change touches only `components.css`, `list.css`, `shell.css`, `jobs.css` and `web/README.md` under `web/`
  - the sweep of 3.3 passes

## 3. Verification in a real browser

- [ ] 3.1 Before editing any CSS in 2.x, build the unchanged base once and keep that `web/dist` copy in the scratchpad as the baseline every "unfixed build" below refers to. Set up the agent's own environment per the dev-env runbook with `SLUG=web-shell-and-css-polish` and port 8227: database `arel_web_shell_and_css_polish`, library `../dev-web-shell-and-css-polish` from `scripts/make_dev_library.py`, `auto-reel serve` over a fresh `npm run build`, no worker. Drive it with a Playwright script kept in the scratchpad (never committed; container `localhost/playback-research:chrome` or `mcr.microsoft.com/playwright/python:v1.49.0-noble`, `--network host`; locators scoped to `main:not([hidden])`; route only `**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel` and `**/reel?*`; `page.wait_for_timeout`, not `time.sleep`). **Forced colors**, `forced_colors='active'`, at 1280 × 900 and 390 × 844, light and dark:
  - hold the answer of `POST /api/v1/jobs` for 2 s and press Render on `2024-06-27 - Grillning med grannar`; while it is busy, read the loader's pixels from a clip screenshot of the button: they differ from the button's background and equal the label's color
  - the same script on the baseline build shows the loader pixels equal the background, so the check is able to fail
  - without forced colors the loader looks as before (compare with a screenshot of the unfixed build)
  - LOOK at the screenshots in both schemes.
- [ ] 3.2 **Hit area**, with `has_touch` and `is_mobile` so `(pointer: coarse)` matches, at 1280 × 900 and 1024 × 768 (table), 390 × 844 (cards), and a mouse context at 1280:
  - for every row of the list that has a Render, call `document.elementFromPoint` at the divider line above the row, across the button's width and at the pixel centres 1 px either side of it: none answers the Render
  - the same at the button's border-box top minus 8 px: answers the Render; and at the button's box bottom plus 9 and plus 10 px, for a row with no job and one with a job, recording the answer for the next row's first padding pixel (design, "Known edge"; apply its fallback if that pixel answers this row's Render)
  - the area's rect from `getBoundingClientRect` of the `::after` is not readable, so measure it by sweeping `elementFromPoint` in 1 px steps up and down from the button's centre
  - at 390 the sweep reaches 9 px above and below as before (cards unchanged); under the mouse context every control's rect is identical to the unfixed build's.
- [ ] 3.3 **Header sweep**: with the jobs WebSocket route replaced by a page-side stub that reports 99 rendering and 99 queued (the real `/api/v1/ws/jobs` snapshot shape; the stub is the script's, no job is created), for Liberation Sans and DejaVu Sans (set through `font-family` on `:root` in an injected style) and the design font, at every width 320-560 px in 10 px steps plus 470, 480, 485, 500, fine and coarse pointer, light and dark at 1280 and 390:
  - `.app-header` is 48 px tall and `scrollWidth <= clientWidth`
  - the rects of `.jobs-indicator` content, `.app-nav` and `.theme-control` do not intersect, and `.jobs-counts` is one line (its height equals one line's height)
  - the counts show words where `.jobs-count-word` is visible and icons otherwise; record the width at which each font collapses, and take `N` from the widest uncollapsed need plus a 10% margin
  - at 1280, 768 and 390 the pill's rect equals the unfixed build's wherever the words fit
  - LOOK at the screenshots at 470, 480, 485 and 500 for both fonts.

## 4. Gates

- [ ] 4.1 Run the gates and confirm nothing else changed: `npx tsc --noEmit` and `npm run build` in the `node:22` container; `.venv/bin/python -m pytest tests/test_api_web_mount.py` (serves the build); `git diff --stat` lists only the four stylesheets and `web/README.md`; the motion grep gate of the design system still passes (no `animation` or `transition` added); `openspec validate web-shell-and-css-polish --strict` passes. The Python gates (black, isort, mypy, pylint) are unaffected because no `.py` file changes; `git diff --stat -- '*.py'` prints nothing.
