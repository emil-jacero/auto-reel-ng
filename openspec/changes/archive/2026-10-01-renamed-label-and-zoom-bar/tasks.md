## 1. Gate

- [x] 1.1 Confirm the gate, and the names the design cites. Stop and report to the supervisor on any mismatch.

  **The gate.** `output-renamed-reason` (Z2) must be archived on main:
  - `ls openspec/changes/archive/ | grep -- '-output-renamed-reason$'` prints one directory.
  - `grep -n 'StalenessReason:' web/src/api/schema.d.ts` lists `"output" | "output_renamed"`. That is Z2's
    member. If Z2 landed another name, use it wherever this change writes `output_renamed`.
  - `grep -n 'output_renamed' web/src/events/labels.ts` shows Z2's provisional entry (Z2 task 4.1:
    `'renamed — renders under the new name; the old movie stays'`). Record what is there.
  - `npx tsc --noEmit` in the `node:22` container. If it fails at `labels.ts` with TS2741, Z2 left no entry.
    Report it, and task 2.1 fixes it.

  **The names this change edits:**
  - `web/src/events/common.tsx`: `StalenessCell({ staleness })`
  - `web/src/events/EventDetail.tsx`: `RenderPanel`'s `<StalenessCell staleness={event.staleness} />`
  - `web/src/events/detail.css`: `.render-panel {`
  - `web/src/edit/EventEditor.tsx`:
    - the `[showBar]` layout effect that writes `bar.offsetHeight` to `--toast-inset-bottom`, registers
      `keepToastsClearOf(bar)` and observes the bar with a `ResizeObserver`
    - the `answers` effect with `scrollIntoView({ block: 'nearest' })`
  - `web/src/edit/edit.css`: `.save-bar { position: sticky; inset-block-end: 0;`

  **The spec.** Re-base this change's MODIFIED requirement, "The event list shows every event with its
  render state", on the text now in `openspec/specs/web-app/spec.md`. Keep only this change's edit to
  "A stale event names every reason" and its added scenario "A movie deleted from disk is named missing".
  Likewise re-base "Notifications never cover the save bar" (supervisor decision, option (a)) and keep only
  this change's edit to its focus sentence.

  Verify: `openspec validate renamed-label-and-zoom-bar --strict` passes.

## 2. web/ — the renamed reason in words

- [x] 2.1 Give the reason its words, and add the page's note map (design, "The reason's words", "Where the
  note lives"). In `src/events/labels.ts`:
  - set `REASON_LABEL.output_renamed` to `'movie name changed'`, replacing Z2's provisional words
  - add `REASON_NOTE: Record<StalenessReason, string | null>`, with the design's sentence for
    `output_renamed` and `null` for every other reason

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the `node:22` container.
  - `grep -n "'movie name changed'\|REASON_NOTE" web/src/events/labels.ts` shows both, and
    `grep -n 'renders under the new name' web/src/events/labels.ts` shows only the note.
  - Make a throwaway copy of the worktree's `web/` under the scratchpad
    (`rsync -a --exclude node_modules --exclude dist web/ <scratch>/web-probe/`, then `npm ci` there). Add a
    member `"probe"` to `StalenessReason` in the copy's `schema.d.ts`. `npx tsc --noEmit` then reports TS2741
    at both `REASON_LABEL` and `REASON_NOTE`.
- [x] 2.2 Show the note on the event page only (design, "Where the note lives"):
  - `src/events/common.tsx`: `StalenessCell` takes `explain?: boolean` (default `false`). When it is set and
    the verdict is stale, each non-null `REASON_NOTE` of a cited reason renders after `.reasons` as
    `<span className="reason-note">`.
  - `src/events/EventDetail.tsx`: `RenderPanel` passes `explain`. This is the only changed line.
  - `src/events/detail.css` (`@layer screens`): `.render-panel .reason-note { flex-basis: 100%; color:
    var(--fg-muted); font-size: var(--text-sm); }`

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass.
  - `git diff main -- web/src/events/EventDetail.tsx` shows one changed line.
  - `git diff main -- web/src/events/EventList.tsx` is empty.

  Then run Playwright against this change's own `serve` on :8124 (design, "Verification fixtures"). Allow
  GETs only, and abort every other request.

  On the page of `2024-06-27 - Grillning med grannar`, at 1280, 390 and 320, in light and dark:
  - the render panel's `.verdict` reads "Needs render" and "edited since last render, movie name changed"
  - exactly one `.reason-note` reads "The next render saves the movie under its new name. The movie under its
    old name stays on disk."
  - `scrollWidth <= clientWidth`
  - no `.mp4` text appears in `.render-panel`

  On the list, at 1280 and 390, Grillning's row reads "edited since last render, movie name changed" and has
  no `.reason-note`. With the Noto `fonts.conf`, its `.verdict` is at most 61 px tall at 1280 and 42 px at
  390. Those are 93721b3's heights with "movie file missing". Z2's provisional words measured 81 px and
  61 px.

  Move `library-output/2024/2024-06-21 - Midsommar - Dalarna.mp4` aside in the agent's own library. Then
  the list row and the page of `2024-06-21 - Midsommar - Dalarna` read "movie file missing", and neither shows
  a `.reason-note`. Put the movie back afterwards. The page of the up-to-date
  `2023-06-23 - Midsommar - Dalarna` shows "Up to date" and no `.reason-note`.

## 3. web/ — the save bar rests above two fifths of the window

- [x] 3.1 Make the bar rest in the page when it is taller than two fifths of the window (design, "The bar
  rests above two fifths of the window", "When the bar decides").

  In `src/edit/EventEditor.tsx`:
  - module scope: `HELD_BAR_MAX_SHARE = 0.4` and `placeBar(bar)`, as in the design, including the scroll that
    follows a focused control of the bar when the bar goes from held to resting (design, "A focused control
    follows a bar that starts to rest")
  - the `[showBar]` layout effect: calls `placeBar(bar)` where it called `publish`, from its
    `ResizeObserver`, and from a new `window` `resize` listener, which the cleanup removes. The registration,
    its release and the property's removal stay as they are. Its comment says the property is the held bar's
    height and is absent while the bar rests.
  - right after it, a layout effect with no dependency list:
    `if (showBar && barRef.current !== null) placeBar(barRef.current)`

  In `src/edit/edit.css`, after `.save-bar`: `.save-bar[data-rests] { position: static; }`. Bring the bar's
  comment there, and `SaveBar.tsx`'s header comment, in line with "held while it takes at most two fifths;
  taller, it rests after the editor".

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass.
  - `grep -n "data-rests\|HELD_BAR_MAX_SHARE\|'resize'" web/src/edit/EventEditor.tsx web/src/edit/edit.css`
    shows all three.
  - `grep -rn ' disabled=' web/src/edit` prints nothing.

  Then run Playwright on `2024-09-01 - Sommarlov`, by keyboard only, with no click and no `.focus()`:
  1. From the page's `h1`, Tab to Edit and press Enter.
  2. Tab to the first clip's Move down and press Enter.
  3. Tab to Save and press Enter.

  In the browser, `PUT …/reel` is answered 412 for a conflict and 502 with a real-length detail for a write
  failure. At 320 × 256, do one run each with the real 412 (a hand edit of the `reel.yaml` title after the
  page read) and the real failure (`chmod a-w` on the folder, restored afterwards).

  Run windows 320 × 256, 320 × 568, 390 × 844 and 1280 × 900 in light and dark. Also run 320 × 230 and
  844 × 340 to record their results.

  "Fully visible" means: the control's rectangle lies inside the window, and `elementFromPoint` at its centre
  and at the middle of each of its four edges, 2 px in, returns the control or an element inside it. Edge
  midpoints, not corners, because some controls have pill-shaped corners that hit-testing skips.

  Expected results:
  - **After the move**: `.save-bar[data-rests]` exists at 320 × 256 and 320 × 230 only. The focused Move
    down and its whole `li` are fully visible.
  - **After the answer**:
    - `data-rests` is present at 320 × 256, 320 × 230, 320 × 568 and 844 × 340, and absent at 390 × 844 and
      1280 × 900. The computed `position` is `static` or `sticky` to match.
    - `document.activeElement` is Save, and it is fully visible.
    - At 320 × 568, the `.save-bar-card` rectangle is inside the window and below `.app-header`.
  - **The Shift+Tab walk**: press Shift+Tab 18 times from Save, then Tab back to Save. At every stop the
    focused control is fully visible: every sample hits the control itself, never `.save-bar-card` (for a
    control outside the bar), `.app-header` or `.panel-header`. On main, 15 to 16 stops at 320 × 256 were
    fully hidden.
  - **No horizontal scroll** in any window.
  - **Resize**: after the conflict at 320 × 256, `set_viewport_size(390 × 844)` makes `data-rests` absent and
    `position` sticky, with `--toast-inset-bottom` equal to `.save-bar`'s `offsetHeight`. Back at 320 × 256,
    `data-rests` is present again. At each size, Save keeps focus and is fully visible.
  - **Zoom in**: answer the conflict, and separately the failure, at 1280 × 1024 and at 390 × 844 (the bar
    held, Save focused). Then `set_viewport_size` to 320 × 256, and from 390 × 844 also to 320 × 568.
    `data-rests` is present, `document.activeElement` is still Save, and Save is fully visible. The first
    prototype left Save 0 % visible in all of these (design, "A focused control follows a bar that starts to
    rest").
  - **edit-mode-polish's checks still pass**:
    - task 2.1's bounds at 390 × 844 (the bar held, conflict ≤ 281 px, failure ≤ 337 px)
    - its short window held at its top (320 × 568, 320 × 700, 340 × 700, 375 × 667: after the answer, Save
      and the card are inside the window)
    - task 3.1's first keyboard drop on Grillning at 1280 × 900 and 390 × 844
- [x] 3.2 Check the toast contract in both states (design, "The toast contract in both states"). This task
  adds no code beyond 3.1.

  Verify, with Playwright:
  - **Held** (1280 × 900 and 390 × 844, plain, conflict and failure): `--toast-inset-bottom` equals
    `.save-bar`'s `offsetHeight`. After Reset it is absent.
  - **Resting** (320 × 256 and 320 × 568 after a conflict, no toast): `--toast-inset-bottom` is absent, and
    `html`'s computed `scroll-padding-bottom` is `16px`.
  - **With an error toast held**: use the row Render of `2024-07-14 - kalas` (the real 409), then answer a
    Sommarlov conflict at 320 × 256, 320 × 568 and 390 × 844. Scroll from the top to the end in 16 px steps.
    At no step does a `.toast` rectangle intersect `.save-bar-card`. In the prototype the count was 0 at every
    size.
  - **Record and report**: the Shift+Tab stops that a toast covers in part at 320 × 568 and 320 × 256. The
    prototype found 4 and 5 there, with `Remove borttagen.mp4` fully covered in both; main found 15 at
    320 × 568. The bar rests there, so they are the case the narrowed focus sentence of "Notifications never
    cover the save bar" leaves out (supervisor decision, option (a)). Report them with their visible shares,
    as that case and as the evidence for the follow-up (option (b)), never as a pass of the old sentence.
  - **The narrowed sentence still holds where it applies**: with one error toast held, a Shift+Tab walk from
    Save at 390 × 844 and 1280 × 900 (the bar held) leaves no focus stop under the toast; and at 320 × 568 and
    320 × 256, scrolled to the page's end, no toast covers any control of the page.
  - **ui-a11y-polish's own toast checks** at 1280 and 390 on Grillning, with a title edit and an error toast
    held: the toast sits above the held bar, and Tab to Save never lands under a toast.

## 4. Docs

- [x] 4.1 Update `web/README.md`:
  - **The Edit-mode paragraph.** "A sticky save bar says what changed…" now says the bar is held at the
    window's bottom while it takes at most two fifths of the window. A taller bar rests in the page after the
    last chapter, and a save's answer, or a zoom that makes it rest, scrolls to its focused control. Examples
    of a taller bar: a failed save in a short window, any bar at 400 % zoom. The file tree's `SaveBar.tsx`
    line drops "sticky".
  - **The Toasts bullet.** The page sets `--toast-inset-bottom` to the bar's height while the bar is held, and
    removes it while the bar rests.
  - **Reasons.** The event page adds a sentence for a changed movie name: the next render saves under the new
    name, and the old movie stays on disk.
  - **The dev-library bullet** "stale for `editorial`, `output`, `clip_set` and `no_manifest`" names
    `output_renamed` (Grillning) in place of `output`. After the gate, no dev-library event is stale for
    `output` until its movie is removed by hand.

  Verify:
  - `grep -n "two fifths" web/README.md` hits the Edit-mode paragraph.
  - `grep -n "toast-inset-bottom" web/README.md` shows the held-or-removed sentence.
  - `grep -n "movie name changed\|old name" web/README.md` hits.
  - `git diff --stat main -- docs` is empty.

## 5. Verification against the dev library

- [x] 5.1 Run the whole pass in the agent's own environment (design, "Verification fixtures"):
  - `SLUG=renamed-label-and-zoom-bar`
  - port 8124
  - database `arel_renamed_label_and_zoom_bar`
  - library `../dev-renamed-label-and-zoom-bar`
  - no worker

  Never use port 8080 or 5173, the default database, `../auto-reel-dev`, `auto-reel-media/`, or another
  agent's database, library or port. Never stop an `auto-reel-ng-test-pg-*` container.

  The scripts and screenshots live in `<scratchpad>/verify/renamed-label-and-zoom-bar/`, and are never
  committed. Run them in `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `--network host` and the
  Noto `fonts.conf`.

  - **Screenshots**, light and dark. Look at every one.
    - Grillning's list row, and its page, at 1280, 390 and 320
    - Midsommar 2024's page with its movie moved aside
    - Sommarlov in Edit mode:
      - the plain bar at 320 × 256
      - a conflict at 320 × 256, 320 × 568, 390 × 844 and 1280 × 900
      - a write failure at the same four sizes
      - the resting bar at 320 × 256 with an error toast
  - **axe-core**, injected ad hoc, in both schemes: no serious or critical violation on Grillning's page, or
    on Sommarlov's conflict at 320 × 256 and at 390 × 844.
  - **The tasks' checks**: run 2.2, 3.1 and 3.2 once more on the final build.

  Verify:
  - the screenshots and logs exist under that directory
  - `git status --porcelain` in the worktree lists only this change's files: no script, screenshot or
    `.playwright` directory

## 6. Validation

- [x] 6.1 Run the gates, and verify that all of them pass:
  - `npx tsc --noEmit` and `npm run build` in the `node:22` container
  - the motion gate (web/README.md, "Motion") over `web/src/edit` and `web/src/events`. This change adds no
    animation.
  - `grep -rn 'autoFocus' web/src/edit web/src/events` prints nothing
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then
    `.venv/bin/python -m mypy auto_reel_ng`, then `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, with the web-mount and OpenAPI drift tests green
  - `git diff --stat main -- auto_reel_ng tests scripts docs web/openapi.json web/src/api web/package.json
    web/package-lock.json web/src/jobs web/src/ui web/src/shell web/src/styles` is empty
  - `openspec validate renamed-label-and-zoom-bar --strict` passes
