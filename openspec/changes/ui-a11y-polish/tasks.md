## 1. Gate

- [x] 1.1 Confirm the base, and re-check the names this change builds on (design, "Context"). Stop and report to the supervisor on any mismatch.
  - `git merge-base --is-ancestor bca64f2 HEAD` succeeds.
  - Record which parallel changes already landed, because they decide the current text of the call sites in tasks 2.2 and 3.1: `ls openspec/changes/archive/ | grep -E -- '-(edit-mode-polish|jobs-live-polish|event-page-polish)$'`.
  - `web/src/ui/ToastRegion.tsx` has the two `.toast-stack` containers (`role="alert"`, `role="status"`), `ToastItem`'s Dismiss calling `dismissToast`, and the region's `onFocus` and `onBlur`.
  - `web/src/ui/toast.ts` exports `dismissToast`, `pauseToasts` and `useToasts`.
  - `web/src/ui/Dialog.tsx` takes `open`, `title`, `onClose`, `initialFocus` and `children`, and sets only `aria-labelledby`.
  - `grep -rn "<Dialog" web/src --include=*.tsx | grep -v ui/Dialog.tsx` lists the call sites: four on `bca64f2` (two in `EventEditor.tsx`, two in `RenderControl.tsx`), each passing its consequence and then a `.dialog-actions` row. A dialog a landed change added is checked in 5.2 too.
  - `EventEditor.tsx` has the save bar's layout effect that publishes `--toast-inset-bottom`, or `edit-mode-polish`'s replacement for it. Write down its current shape, and whether it publishes the bar's height or a live band. If `.save-bar` is `position: fixed` on the base (design, "Also considered"), stop and report: 2.2's placement code and rise term are then not needed.
  - `shell.css` sets `html`'s `scroll-padding-bottom` to `calc(var(--toast-inset-bottom, 0px) + var(--toast-region-h, 0px) + var(--s-4))`, or a landed change's replacement that still adds those terms.
  - `EventDetail.tsx` renders the missing-clip `Alert` ("lists clips that are not on disk").
  - `theme.ts` has `applyThemeChoice`, and `index.html` has the two `media`-keyed `theme-color` metas and the pre-paint script.

  Re-base the MODIFIED block in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`: take the landed requirement text and carry over only this change's paragraph and its two scenarios.

  Verify: `openspec validate ui-a11y-polish --strict` passes.

## 2. web/ — toasts

- [x] 2.1 In `src/ui/ToastRegion.tsx`, make each announcement happen once and keep focus (design, "Announce once" and "Keyboard dismiss: where focus goes"):
  - `aria-atomic="false"` on both stacks
  - in `ToastItem`, a `useId` message id and `aria-describedby` on Dismiss
  - Dismiss calls the region's `dismiss(id, button)`. Its candidates are the next Dismiss, then the previous one, then `returnTo`, then `main:not([hidden]) h1`, each focused with `{ preventScroll: true }` and checked to take focus, and focus moves before `dismissToast`.
  - `returnTo` is set on each entry from outside the region (to `null` when `relatedTarget` is null). `lastFocused` is set in the region's `onFocus` and cleared only by a `focusin` or `pointerdown` outside the region, never by a `focusout` (Chromium fires one when the focused node is removed).
  - a `useLayoutEffect` on `toasts` handles a displaced focused toast, with the same candidates
  - the comment above the `updatePause` effect no longer says that no blur fires on removal
  - in `src/events/EventDetail.tsx`, `role="note"` on the missing-clip `Alert` (a one-attribute call site in P4's file)

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the node:22 container
  - `grep -c 'aria-atomic="false"' web/src/ui/ToastRegion.tsx` prints 2
  - `grep -n "\.focus(" web/src/ui/ToastRegion.tsx` shows only `focus({ preventScroll: true })`
  - `git diff --stat web/src/events/EventDetail.tsx` shows one line changed
  - `grep -rn ' disabled=\|autoFocus' web/src/ui` prints nothing
- [x] 2.2 Add the toast placement contract (design, "Where toasts sit relative to the save bar"):
  - in `src/ui/toast.ts`, `keepToastsClearOf(bar)` (a later call replaces an earlier one, and a release clears only its own registration) and `useToastClearance()`
  - in `src/ui/ToastRegion.tsx`, the placement `useLayoutEffect` keyed on the registered bar:
    - window `scroll` (passive) and `resize`, plus a `ResizeObserver` on the bar and on the region
    - `--toast-offset: 0px` applied first, then "below" or "above" by the rule, written only when the value changes
    - `--toast-rise-h` on `<html>`: the region's height plus the read-back gap while the region is not empty, removed when it is empty
    - both properties removed on cleanup
  - in `src/styles/components.css`, `.toast-region`'s `inset-block-end: calc(var(--toast-offset, var(--toast-inset-bottom, 0px)) + var(--s-4))`, with its comment updated
  - in `src/shell/shell.css`, one more term in `html`'s `scroll-padding-bottom`, `+ var(--toast-rise-h, 0px)`, and its comment (design, "Review: keyboard focus while the bar rises")
  - in `src/edit/EventEditor.tsx` (P1's file), two lines in the bar's layout effect: `const release = keepToastsClearOf(bar)` and `release()` in its cleanup. What it publishes stays unchanged.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff web/src/edit/EventEditor.tsx` adds at most 3 lines (the import and the two in the bar effect), and nothing else
  - `grep -rn "toast-inset-bottom" web/src` still hits `shell.css`, the publishing effect, and the fallback in `components.css`
  - `grep -rn "toast-rise-h" web/src` hits only `ToastRegion.tsx` and `shell.css`, and `git diff web/src/shell/shell.css` changes only the `scroll-padding-bottom` rule and its comment

## 3. web/ — dialogs

- [x] 3.1 In `src/ui/Dialog.tsx`, make the dialog describe itself (design, "Dialog description: the body describes the dialog"; supervisor decision, no new prop): render every child except the `.dialog-actions` row inside `<div id={bodyId} className="dialog-body">` after the title (`bodyId` from `useId`), then the actions row, and set `aria-describedby={bodyId}` on the `<dialog>` when the body is not empty. Update the doc comment. Leave every caller and the CSS unchanged.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff --stat web/src/jobs web/src/edit` shows no dialog line changed (EventEditor's only change is 2.2's)
  - `git diff web/src/styles` adds no dialog rule

## 4. web/ — the browser's UI color and docs

- [x] 4.1 In `src/shell/theme.ts`, add `THEME_COLOR` (`light: '#f9fafc'`, `dark: '#0b0d11'`, with a keep-in-step comment) and `applyThemeColor(choice)`, which sets both `theme-color` metas for Light or Dark and restores each meta's own color for System. `applyThemeChoice` calls it before storage. In `index.html`'s pre-paint script, when the stored choice is Light or Dark, read the two colors from the metas and set both to the chosen one (ES5, as the script is now). Keep the metas' markup unchanged (design, "Browser UI color").

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `grep -n "theme-color" web/dist/index.html` shows both metas and the script
- [x] 4.2 Update `web/README.md`, "Design system":
  - **Dialogs:** the body (every child but the `.dialog-actions` row) becomes the dialog's accessible description through `aria-describedby`, so a dialog's consequence paragraph is read when it opens; no prop, callers unchanged.
  - **Toasts:**
    - `keepToastsClearOf(bar)` replaces "sets `--toast-inset-bottom` so no toast covers it": above the bar while stuck, below it at the page end
    - `--toast-inset-bottom` remains the page's inset for scroll padding and the fallback, and the region adds `--toast-rise-h` to that padding while a bar is registered
    - the Dismiss focus hand-off
    - the stacks announce each toast once
  - **Theme:** the pre-paint script and the theme control also set `theme-color`

  - **Touch:** under a coarse pointer every button, segmented option, the header's Events link, the back link and a toast's link take a tap in at least 44 × 44 px

  Verify: `grep -n "keepToastsClearOf\|toast-rise-h\|aria-describedby\|theme-color\|pointer: coarse" web/README.md` hits all five, and `git diff --stat web/README.md` is confined to that section.

- [x] 4.3 Touch targets under a coarse pointer (design, "Touch targets under a coarse pointer"; supervisor decision):
  - in `src/styles/components.css`, one `@media (pointer: coarse)` block in `@layer components`: `.btn`, `.segmented label` and `.toast-action` get `position: relative` and an `::after` hit area, the border box grown evenly to 2.75rem each way where smaller (`inset: min(-1px, calc(50% - 1.375rem))`); a `.btn-icon` followed by a `.btn-icon` anchor their areas away from each other; `.segmented label` gets `min-inline-size: 2.75rem`
  - in `src/shell/shell.css`, under `(pointer: coarse)`: the same hit area for `.app-nav a`; and below 24rem the theme options keep `1.75rem` with an area as wide as the option
  - in `src/events/detail.css` (P4's file), one rule: `.back-link` gets `min-block-size: 2.75rem` under `(pointer: coarse)`

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `grep -n "pointer: coarse" web/src/styles/components.css web/src/shell/shell.css web/src/events/detail.css` hits each file, and `git diff --stat web/src/events/detail.css` adds one rule
  - the motion grep gate of 6.1 still passes (no animation or transition added)

## 5. Verification against the dev library

- [x] 5.1 Set up the agent's own environment per the dev-env runbook §9, with `SLUG=ui-a11y-polish` and port 8119:
  - database `arel_ui_a11y_polish`, library `../dev-ui-a11y-polish` made by `scripts/make_dev_library.py`
  - `auto-reel serve <library> --port 8119` over a fresh `npm run build`
  - no worker until a step starts one
  - never port 8080, 5173 or 8114, never `auto-reel-media/`, the default database `auto_reel_ng`, or another agent's library, database or port

  Drive `http://127.0.0.1:8119/` with a Playwright script kept in `<scratchpad>/verify/ui-a11y-polish/`, never committed:
  - container `mcr.microsoft.com/playwright/python:v1.49.0-noble`, with `--network host`
  - locators scoped to `main:not([hidden])`
  - AX facts read with CDP `Accessibility.getFullAXTree`

  Raise error toasts by pressing the list row's "Render 2024-07-14 - kalas". The service answers 409 `output_collision`, and no job is created. Check at 1280×900 and 390×844:
  - **Announce once:** with two error toasts, both stacks read `atomic: false` (`live` assertive or polite as before). Each Dismiss's AX description equals its toast's message.
  - **Next, then back:**
    - with two toasts, Tab from the last control of `main` into the region, and record that control
    - Enter on the first Dismiss: `activeElement` is the remaining Dismiss
    - Enter again: `activeElement` is the recorded control, never `BODY`
  - **Heading fallback:** with one toast, focus its Dismiss with `locator.focus()` from `<body>`, then press Enter. `activeElement` is the `h1` "Events".
  - **Displaced:**
    - with three error toasts and focus on the oldest Dismiss, raise a fourth with `element.click()` in `page.evaluate`, so focus does not move
    - `activeElement` is a `.toast-dismiss` of a toast still shown
  - **Pointer:** at 390×844 with one toast, focus the list's Refresh, scroll halfway down the list (not to its end, where the end padding shrinks with the toasts and clamps `scrollY`), then click Dismiss with the mouse. Focus ends on Refresh (Chromium focuses the clicked button, and the hand-off returns it), and `scrollY` is unchanged. The review's spike measured 705 → 705 with `preventScroll`, and 705 → 0 without it.
  - **Missing-clip warning:** a `MutationObserver` records `[role=alert]` insertions. Opening `2024-09-01 - Sommarlov` and pressing Refresh insert none. The warning naming `borttagen.mp4` is shown with `role="note"`, and the render status still names the missing clip.
- [x] 5.2 In the same environment, check placement, dialogs and color.

  **Save bar placement** (spec "Notifications never cover the save bar"):
  - Setup: one error toast, then two. Change the hash in-app, so the toasts survive, to `2024-06-27 - Grillning med grannar`, press Edit and type in Title.
  - Sizes: 1280×900, 768×1024, 390×844 and 320×700, in the light and the dark theme at 1280 and 390.
  - Scroll sweep: scroll from 0 to `maxY` in 16 px steps, including `maxY`. At every step, no `.toast` rect intersects `.save-bar-card`.
  - At `maxY`, no focusable control in `main:not([hidden])` intersects a toast.
  - Tab from Title to Save: `elementFromPoint` at Save's centre and four inset corners returns Save, and `click(trial=True)` on Save is actionable.
  - Repeat the sweep on `2024-02-30 - Omöjligt datum`'s form at 390×844 and 320×700.
  - After Stop editing (no bar):
    - the region has no inline `--toast-offset`, and its bottom is 16 px above the viewport edge
    - at `maxY`, no control is covered
  - While the bar shows with toasts, `getComputedStyle(documentElement).scrollPaddingBottom` equals the published inset plus `--toast-region-h` plus `--toast-rise-h` plus 16 px, and `--toast-rise-h` equals the region's height plus 16 px. After Stop editing, `--toast-rise-h` is absent.
  - **Tab walk** (spec scenario "Tabbing through the last clips with two notifications"): from Title, press Tab until Save has focus: with one toast at every size above and on the fix form at 390×844 and 320×700, and with two toasts at 1280×900, 768×1024 and 390×844 (Grillning and the fix form). After each Tab, no `.toast` rect intersects the focused element's rect by more than 1 px, and no `.toast` rect intersects `.save-bar-card`.
  - At 390 and 320, `scrollWidth <= clientWidth` throughout.

  **Dialogs** (spec "A confirmation dialog states its consequence"): the AX `description` of each open dialog equals its visible paragraph (no button name in it), and the focused element is the safe action.
  - "Render anyway?" on `2023-06-23 - Midsommar - Dalarna` (Cancel)
  - "Discard unsaved changes?" after an edit on Grillning and Back (Keep editing)
  - "Overwrite the other change?": in Edit mode on Grillning, change the title, change a typed field of that event's `reel.yaml` in the agent's library (`metadata.location`; a comment alone keeps the ETag, which is canonical over typed fields, D-R1), press Save (412), then "Overwrite with mine" (Cancel). Leave with Cancel and Reload, and write nothing; restore the file afterwards.
  - "Cancel this render?": start `auto-reel worker <library> --device cpu`, press Render on Grillning, then press Cancel while it runs (Keep rendering). Then stop the worker with SIGINT.

  **Browser UI color**, for OS light and dark × stored choice none, light and dark:
  - With `**/assets/*.js` aborted, so only the pre-paint script runs, the meta whose `media` matches carries `#f9fafc` for an effective light scheme and `#0b0d11` for dark.
  - With the app running, the same holds. Drawing `getComputedStyle(body).backgroundColor` to a canvas and reading the pixel matches that hex within ±1 per channel.
  - Switching System, Light and Dark with the theme control, without a reload, updates the matching meta each time.
  - With `localStorage` throwing (init script), the metas stay keyed on the OS, and choosing Dark sets `#0b0d11`.

  **Touch targets** (spec "Every control is large enough to touch"), in a context with `has_touch` and `is_mobile` (so `(pointer: coarse)` matches) at 390×844, 320×700 and 768×1024, on the list, Grillning's page and its Edit mode with the title changed:
  - for every button, segmented option, the header's Events link, the back link and a toast's link: `elementFromPoint` at a 7 × 7 grid of points across its designed area (the border box grown to 44 px each way; for a pair of icon buttons, anchored away from the other; for a control grown to 44 px without a hit area, the back link, the 44 × 44 square centred on it), each control scrolled to the window's centre first, returns that control or a descendant; the theme options below 384 px are checked across an area as wide as the option
  - no point in one control's box returns another control; Move up's box never returns Move down
  - `scrollWidth <= clientWidth` at 390 and 320
  - with a fine pointer, every control's rect at 1280, 390 and 320 on the list, Grillning's page and its Edit mode equals the rect measured on `bca64f2` before the change (`rects_fine_baseline.json`)

  **Screenshots:** save light and dark screenshots at 1280 and 390 to `<scratchpad>/verify/ui-a11y-polish/`, and look at every one:
  - Grillning in Edit mode with a toast, at the top and at the end
  - the fix form with a toast at the end
  - each dialog
  - the list and Grillning's Edit mode under a coarse pointer at 390 and 320

## 6. Validation

- [x] 6.1 Run the gates. Verify that all of them pass:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `web-design-system`'s motion grep gate, its three commands verbatim, over `web/src/ui`, `web/src/shell` and `web/src/styles`. This change adds no animation or transition.
  - `grep -rn 'autoFocus' web/src/ui web/src/edit web/src/jobs` prints nothing
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, then `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, with the web-mount and OpenAPI drift tests green
  - `git diff --stat main -- auto_reel_ng tests scripts web/openapi.json web/src/api/schema.d.ts web/package.json web/package-lock.json web/src/jobs` is empty
  - `openspec validate ui-a11y-polish --strict` passes
  - no Playwright script, screenshot or `.playwright` directory is in the worktree
