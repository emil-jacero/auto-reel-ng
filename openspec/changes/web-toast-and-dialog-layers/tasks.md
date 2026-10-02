## 1. web/ - a runner for the pure rules, and the store's eviction rule

- [x] 1.1 Add the runner. In `web/package.json` add `"test": "node --test --experimental-strip-types src/**/*.test.ts"`;
  in `web/tsconfig.json` add `"exclude": ["src/**/*.test.ts"]` (`node:test` has no types here; no `@types/node`).
  Create `web/src/ui/toast.test.ts` (imports `node:test` and `node:assert/strict`; sets
  `globalThis.window = globalThis`, then `await import('./toast.ts')`; each case starts from an empty store by
  dismissing every held toast; `mock.timers.enable({ apis: ['setTimeout', 'Date'] })` for clocks) with the
  eviction cases below, written red first against the unchanged `show()`.
  Verify: `podman run --rm -v $WT/web:/app:Z -w /app docker.io/library/node:22 sh -c "npm ci && npm test"` runs
  the file and, before 1.2, the "three errors then info" case fails with `error:e2, error:e3, info:i4`.
- [x] 1.2 Fix `show()` in `web/src/ui/toast.ts`: when `held.length >= MAX_HELD`, drop the oldest non-error
  toast; if there is none, a new `error` drops `held[0]` and any other tone returns before consuming an id,
  creating a clock or emitting. Rewrite the header comment (and the matching sentence in the `ToastRegion`
  doc comment). Cases in `toast.test.ts`: e1 e2 e3 + info i4 leaves `e1 e2 e3` and an unchanged snapshot
  identity (no emit); e1 e2 e3 + error e4 leaves `e2 e3 e4`; e1 e2 + success s3 + info i4 leaves `e1 e2 i4`;
  the dropped toast's clock is cleared (advancing 5 s fires nothing for it). Verify: `npm test` passes.

## 2. web/ - clocks wait while a modal dialog is open

- [x] 2.1 In `toast.ts` add `enterModal(): () => void` (module counter `modalDepth`; the returned release is
  idempotent) and `onModalOpened(listener): () => void`, notified synchronously by `enterModal`. Make the
  effective pause `isPaused || modalDepth > 0` in `startClock` and in one `syncClocks()` that stops or starts
  every running clock when that value changes (`pauseToasts` only sets `isPaused`, then calls it). Cases in
  `toast.test.ts`: a success shown, 2 s elapsed, `enterModal()`, 10 s elapsed - still held; release - gone
  after the 3 s left; a toast raised while a modal is open keeps its full 5 s after release; two nested
  `enterModal`s keep the pause until both are released; a double release of one does not release the other;
  hover pause (`pauseToasts(true)`) and a modal together resume only when both end; errors never get a clock.
  Verify: `npm test` passes.

## 3. web/ - a dialog gives focus back only when it still owns it

- [x] 3.1 Create `web/src/ui/returnFocus.ts` exporting `mayReturnFocus(active, dialog, body)` (true when `active` is
  null, is `body`, or is inside `dialog`) and `returnFocus.test.ts` with structural stand-ins for the nodes:
  null, body, the dialog itself, a descendant, an outside button (false), the opener itself (false: it already
  has focus). Verify: `npm test` passes.
- [x] 3.2 In `web/src/ui/Dialog.tsx`: call `enterModal()` right after `showModal()` in the open effect and
  release it in the cleanup after `dialog.close()`; read `document.activeElement` at the top of the cleanup,
  before `dialog.close()`, and refocus `opener` only when it is connected and `mayReturnFocus(active, dialog,
  document.body)`. Update the component's doc comment ("closing returns focus there when ... focus is still the
  dialog's"). Verify: `npx tsc --noEmit` in the node container is clean, and, in the Playwright pass (6.1),
  Escape and Cancel return focus to the opener while a `close`-listener that focuses Save leaves focus on Save.

## 4. web/ - the toast region sits in the top layer

- [x] 4.1 In `ToastRegion.tsx` render the region with `popover="manual"`, show it in a mount effect
  (`typeof region.showPopover === 'function'` and not already `:popover-open`; `hidePopover()` in the cleanup,
  both in try/catch) and re-promote it (`hidePopover(); showPopover()`) from `onModalOpened`. In
  `styles/components.css` reset the user-agent popover box on `.toast-region[popover]` as the design lists
  (keep `position: fixed`, the bottom/inline offsets, the width, `pointer-events: none`; drop `z-index`).
  Update the component doc comment. Verify: `npx tsc --noEmit` clean; in the Playwright pass (6.1) the region is
  `:popover-open`, looks the same as before in light/dark at 1280 and 390 (toast width, offset, shadow), and
  `elementFromPoint` at an error toast's centre returns the toast with "Render anyway?" open (screenshot).

## 5. web/ - room above a resting save bar

- [x] 5.1 In `ToastRegion.tsx` `place()` also publish `--toast-room-h` on `<html>` (the value of
  `--toast-rise-h`, only while `offset > 0`; removed otherwise and in the cleanup), and observe
  `document.documentElement` and `bar.parentElement` with the existing `ResizeObserver` so `place()` reruns when the
  page above the bar moves it. In `edit/edit.css` give `.save-bar[data-rests]`
  `margin-block-start: var(--toast-room-h, 0px)` and update the save-bar comment; update the `shell.css`
  `scroll-padding-bottom` comment and the `ToastRegion` doc comment (the "known gap" and the
  "except, while the bar rests" sentences go). Verify: `npx tsc --noEmit` and `npm run build` clean; in the
  Playwright pass (6.1) the focus-stop sweep (Shift+Tab from Save through every control of `Sommarlov` after a
  conflict) at 320 x 256 and 320 x 568 with one error toast, and at 320 x 568 with two, finds no focus stop
  covered by a toast, and `--toast-room-h` is absent with no toast or with the toast below the bar.

## 6. Verification

- [x] 6.1 Playwright from the session scratchpad (never committed; `localhost/playback-research:chrome` or
  `mcr.microsoft.com/playwright/python:v1.49.0-noble`, `--network host`) against the built client served by
  `auto-reel serve` on the change's own port, DB and a scratch copy of the dev library; locators scoped to
  `main:not([hidden])`; light and dark at 1280 and 390; look at every screenshot. Route only
  `**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel`, `**/reel?*` to make toasts (errors: a 409 on POST jobs;
  info: "Already up to date" on an up-to-date row; success: an intercepted save), never a catch-all. Verify each
  scenario of the delta spec:
  - three errors, then an info: the three errors stay, no live-region text for the info
  - an error shown, then "Render anyway?" opened: the error is visible above the backdrop (screenshot,
    `elementFromPoint`); an error raised while it is open is too; record whether Chromium treats the region as
    inert and whether it is in the accessibility tree (report in the final summary, per design Risks)
  - a success raised under the dialog survives 6 s, then disappears about 5 s after Cancel
  - Escape and Cancel return focus to the opener; a `close` listener that focuses Save leaves focus on Save
  - the resting-bar sweeps of 5.1, the room collapsing on dismiss and returning with a second toast, and a
    chapter added while a toast is above the resting bar (the toast stays directly above it)
- [x] 6.2 Gates: `npx tsc --noEmit`, `npm run build` and `npm test` in the `node:22` container (all clean); no
  Python file changed, so `git status` shows only `web/` and `openspec/` paths and `web/openapi.json` is
  untouched (`git diff --stat` shows it absent). Update `web/README.md`: the Toasts paragraph (drops the
  "known gap ... follow-up in `ui/`" sentence; adds the three-toast rule, the top-layer popover and the
  `--toast-room-h` property) and the `ui/` file list (`returnFocus.ts`, `toast.test.ts`, `returnFocus.test.ts`),
  and the build/test commands. Then `openspec validate web-toast-and-dialog-layers --strict`. Verify: all
  clean, and no Playwright script, screenshot or `.playwright` directory is in the worktree.
