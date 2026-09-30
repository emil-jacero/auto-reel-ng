## 1. Gate

- [ ] 1.1 Confirm that **both** gates are archived on main: `openspec/changes/archive/*-web-design-system` and `openspec/changes/archive/*-editorial-chapter-roundtrip`; stop and report if either is missing. Then confirm the names this change builds on (design, "Context"). Verify:
  - `ls -d openspec/changes/archive/*-web-design-system openspec/changes/archive/*-editorial-chapter-roundtrip` prints two directories
  - `web/src/ui/Icon.tsx` names `grip-vertical`, `arrow-up`, `arrow-down`, `pencil`, `check`, `rotate-ccw`, `x`, `alert-triangle` and `loader` in its `IconName` union
  - `web/src/ui/Dialog.tsx`, `web/src/ui/Pill.tsx`, `web/src/ui/Alert.tsx`, `web/src/ui/Skeleton.tsx` (`SkeletonRows`), `web/src/ui/toast.ts`, `web/src/events/tones.ts` (`CLIP_STATUS_LOOK`) and `web/src/events/changes.ts` (`markEventsChanged`) exist
  - `web/src/styles/index.css` declares `@layer reset, tokens, base, components, screens`
  - `grep -n "initialFocus" web/src/ui/Dialog.tsx` shows the optional `initialFocus?: RefObject<HTMLElement | null>` prop
  - `grep -rn "toast-inset-bottom" web/src/ui web/src/styles` shows the toast region's bottom offset read as `var(--toast-inset-bottom, 0px)` (or with its default on `:root`), not a default declared on the region element itself (design, "The save bar's height")
  - `grep -rn 'aria-busy' web/src/styles` shows the `.btn[aria-busy="true"]` style (the busy-control rule)
  - the event page's `h1` has `tabIndex={-1}`, and chapter keys are chapter names (`grep -n "tabIndex\|key={chapter.name}" web/src/events/EventDetail.tsx`)
  - `openspec/specs/web-app/spec.md` contains `Requirement: Reading a screen never changes state` and no longer contains `SHALL be read-only`

  If a name differs, for example an icon called `save` rather than `check`, use the landed name and list the difference in the change's final report. Do not add the missing piece to `ui/`.

## 2. web/ — dependency, editorial client and edit model

- [ ] 2.1 Add the drag-and-drop library and `src/api/reel.ts` (design, "The drag-and-drop library", "Reading and writing the document").
  - `npm install @dnd-kit/core@^6.3.1 @dnd-kit/sortable@^10.0.0 @dnd-kit/utilities@^3.2.2` in the node:22 container
  - `src/api/reel.ts`: `fetchReel` and `saveReel`, their result unions, and the aliases `ReelDocument`, `ReelWriteBody` and `ReelWriteResult`
  - the read uses `cache: 'no-store'` and an `AbortSignal`; a 200 without an `ETag` is `unreachable`
  - the write sends `Content-Type: application/json` and `If-Match` verbatim
  - 404/502 are problems on the read, and 400/404/412/502 on the write
  - 422 or any other status is `unreachable` with `"<METHOD> <url> answered <status> …"`

  Verify:
  - `git diff web/package.json` adds exactly those three `dependencies`
  - `npm ls @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities` reports 6.3.1, 10.0.0 and 3.2.2
  - `grep -c '"node_modules/@dnd-kit/\(react\|modifiers\)"' web/package-lock.json` prints 0
  - `grep -n "no-store\|If-Match" web/src/api/reel.ts` shows both
  - the three body and response types are aliases of `components['schemas'][…]`; only the two result unions are declared locally, as in `api/event.ts`
  - `npx tsc --noEmit` and `npm run build` pass
- [ ] 2.2 Add `src/edit/draft.ts` with no runtime imports and only `import type` imports: `editableChapters`, `detailMatchesDocument`, `buildWriteBody`, `movedSet` (subsequence-based, with the `lastMoved` tie-break), `adoptedNewCount` and `isDirty` (design, "The editable order", "The detail and the document must agree"). Verify:
  - `tsc --noEmit` passes
  - a scratch script (in the session scratchpad, never committed) runs under `node --experimental-strip-types` in the node:22 container, imports `draft.ts`, and asserts the following over hand-copied detail and document JSON of the dev-library events (design, "Verification fixtures"):
    - **Två kapitel:** moving `Kvällen/s1710004.mp4` to the front gives `Kvällen = [Kvällen/s1710004.mp4, Kvällen/s1710002.mp4, Kvällen/s1710003.mp4]`, `""` is unchanged, and `ignore` is unchanged
    - **Badutflykt:** moving `s1710001.mp4` below `s1710003.mp4` gives `adoptedNewCount = 1` and the order `[s1710003, s1710001, s1710004]`
    - **Sommarlov:** a swap keeps `borttagen.mp4` last, and `movedSet` after a Move down of `s1710002.mp4` is `{s1710002.mp4}`
    - **Blandat:** a title-only edit gives `chapters: []`
    - **no `reel.yaml`, two folders:** a reorder writes both chapters, and a title-only edit writes `chapters: []`
    - **`movedSet`:** moving index 0 to 4 of 5 has size 1; moving it back has size 0, with `isDirty` false
    - **metadata:** a draft of `''` over a read `null` keeps `null` without being dirty; `'  '` over a read title is sent as `null`
    - **`detailMatchesDocument`:** false after a clip is appended to the document's chapter, and false after a NEW identity is added to the document's `ignore`
    - **untouched sections:** `look`, `clips` and `ignore` are deep-equal to the input in every case

## 3. web/ — editor components

- [ ] 3.1 Add the navigation guard to `src/route.ts` (`setNavigationGuard`, `acceptedHash`, restore with `replaceState`, the `setRoute` bail-out on an equal route), and add `src/edit/unsaved.ts` (`useUnsavedGuard`, `requestLeave`, the pending-leave store, a guard slot cleared only by its owner) (design, "Unsaved-changes guard"). Verify:
  - `tsc --noEmit` passes
  - `git diff --stat web/src/route.ts` shows 30 lines or fewer
  - with no guard set, `#/event/…` ⇄ `#/` navigation behaves exactly as before (checked in 5.1)
- [ ] 3.2 Add `src/edit/ClipOrderList.tsx` and `src/edit/MetadataForm.tsx`, plus their rules in `src/edit/edit.css` under `@layer screens` (design, "Row list and keyboard access", "Metadata form"). This covers:
  - one `DndContext` per chapter, with the hand-written modifier: vertical axis, clamped to the chapter's `<ol>`
  - Pointer (distance 6) and Keyboard sensors on the handle
  - custom announcements and instructions
  - per chapter, a panel with its `h2`, an `<ol>` of memoised `<li>` rows as direct children, and the ignored tail as a separate `<ul>`
  - each row with its position, file name, status `Pill`, size, time, "was N" badge, and Move up and Move down, with focus retention
  - `transition: null` under reduced motion, every CSS transition inside `@media (prefers-reduced-motion: no-preference)` with a `--dur-*` token, and no `animation` outside that media query (none is needed)
  - the two-line row layout below 40rem, and `:root:has(.save-bar) { scroll-padding-bottom: var(--toast-inset-bottom, 0px); }`
  - the four fields, with the value hint, the "Left empty" hint, the `badInput` message and the group message slot for `unusable_metadata`

  Verify:
  - `tsc --noEmit` passes, including the `accessibility={{ announcements, screenReaderInstructions }}` prop against the installed `@dnd-kit/core` types
  - `grep -n "touch-action: none" web/src/edit/edit.css` matches `.drag-handle`
  - `grep -n "scroll-padding-bottom" web/src/edit/edit.css` shows `var(--toast-inset-bottom, 0px)`
- [ ] 3.3 Add `src/edit/EventEditor.tsx`, without the conflict path (design, "Edit mode, saving and the save bar"). It covers:
  - the reel read (aborted on unmount), `SkeletonRows`, and its failure `Alert`s
  - the `detailMatchesDocument` guard with "Read again", and the detail captured once at mount: the reducer is never re-initialised from props, and the reel read's effect depends on `eventId` only, so a new `event` object does not reset the draft
  - the reducer, the hint, and the adoption notice
  - the sticky `.save-bar` with its summary, Reset and Save, and Save disabled while the date is incomplete; while the bar shows, a `ResizeObserver` writes its height as `--toast-inset-bottom` on `<html>`, removed by the effect's cleanup
  - the locked editor while saving: the pressed Save or Retry gets `aria-disabled="true"` + `aria-busy="true"` and a ref guard, never `disabled`; the lists, handles, move buttons, fields and Reset get `disabled`
  - the outcome table except 412: toast, `markEventsChanged()` and `onSaved` on a 200, run even after unmount; the 400, 404, 502 and unreachable alerts; Retry
  - the one live region for the button path

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - `grep -n 'aria-busy\|aria-disabled\|toast-inset-bottom' web/src/edit/EventEditor.tsx` shows the busy Save and Retry and the inset effect
- [ ] 3.4 Add the conflict path and the discard question to `EventEditor.tsx` (design, "Edit mode, saving and the save bar" step 6, "Unsaved-changes guard"):
  - the 412 `Alert` with **Reload latest (discard my changes)** (`onReload`, no question) and **Overwrite with mine**
  - the Overwrite `Dialog` with `initialFocus={cancelRef}`; confirming closes it (focus returns to **Overwrite with mine**, which is then `aria-disabled` + `aria-busy`, never `disabled`), then a re-read for the ETag only, then a PUT of the original-based body, all in the locked phase, with its own failure alerts
  - the "Discard unsaved changes?" `Dialog` wired to `useUnsavedGuard` and `requestLeave`, with `initialFocus={keepEditingRef}` and Escape meaning Keep editing

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - `grep -n "initialFocus" web/src/edit/EventEditor.tsx` shows two, and `grep -rn "autoFocus" web/src/edit` prints nothing

## 4. web/ — wiring into the page and the list, and docs

- [ ] 4.1 Edit `src/events/EventDetail.tsx` and `src/events/EventList.tsx` (design, "Where it mounts, and 'Needs attention'"), then the docs:
  - EventDetail:
    - an `editing` state, with one toggle button (**Edit** / **Stop editing**, the latter through `requestLeave`)
    - `<EventEditor>` in place of the facts, description and chapter tables while editing
    - the seam's part (a): `load()` never touches `editing`; one `leaveEditMode()` sets `editing` to false, calls `load()` and moves focus to the page's `h1`; every exit uses it: Stop editing and Refresh (both through `requestLeave`), `onSaved` and `onReload`
    - the "Fix the date or title" section with `<EventEditor event={null}>` under an `unusable_metadata` failure
  - EventList: the attention row's folder name links to `eventHref(event_id)`.
  - `web/README.md`: the screens paragraph (the event page's Edit mode, the "Needs attention" links and form, and the unsaved guard, including the rewritten history entry after a guarded Back); the file tree (`api/reel.ts`, and `edit/` with its six files); the dependency budget (the three `@dnd-kit` packages as the one drag-and-drop library)
  - `docs/high-level-design.md`: in §4.10, the slice table's row D only: append that it landed in `event-edit-screen` (no status column; the "no further api/ prerequisite" sentence and row E are `render-progress-screen`'s). In §4.10's Decision D-8 block, extend the dependency-budget bullet to name the chosen library, and the condition for moving to `@dnd-kit/react`: 1.0, or #2116 fixed.

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - `grep -n "setEditing\|load()" web/src/events/EventDetail.tsx`: no `setEditing` inside `load`'s body, and every `setEditing(false)` sits in `leaveEditMode`, followed by `load()`
  - `git diff --stat` shows no change to `App.tsx`, `labels.ts`, `common.tsx`, `src/styles/`, `src/ui/`, `src/jobs/` or `src/api/jobs.ts`
  - the `EventList.tsx` diff touches only the attention row's folder cell (`eventHref` is already imported)
  - `grep -n "@dnd-kit" web/README.md docs/high-level-design.md` shows the README budget and the D-8 bullet
  - `git diff docs/high-level-design.md` touches only §4.10's row D and the D-8 dependency-budget bullet, and `grep -n "event-edit-screen" docs/high-level-design.md` shows the row D status

## 5. Verification against the dev library

- [ ] 5.1 Set up the agent's own environment per the dev-env runbook §9:
  - database `arel_event_edit_screen`, library `…/dev-event-edit-screen`, `auto-reel serve $DEV/library --port 8104`, and **no worker**
  - in that library copy only, add the fixtures from design, "Verification fixtures": `2024/2024-09-15 - Stor dag` (400 symlinked clips), `2024/2024-09-16 - Två mappar`, and `2024/2024-09-17 - Bruten fil` (unparseable `reel.yaml`)

  Drive the built client at `http://127.0.0.1:8104/` with a Playwright script kept in `<scratchpad>/verify/event-edit-screen/`, never committed:
  - container `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `--network host`
  - locators scoped to `main:not([hidden])`
  - every PUT request body captured
  - host-side file checks done with `cat`

  Check each item, in this order where one check changes a file another reads:
  - **List:** the "Needs attention" folder names `2024-02-30 - Omöjligt datum` and `2024-09-17 - Bruten fil` are links to their pages.
  - **Grillning** (`2024-06-27 - Grillning med grannar`):
    - Edit keeps focus on the toggle, now **Stop editing**. The title field holds `Grillkväll med grannarna`, the date `2024-06-27`, and location and description are empty.
    - Escape during a keyboard move of `s1710001.mp4` restores position 1 and is announced
    - Move down then Move up on `s1710002.mp4` leaves no save bar
    - dragging `s1710004.mp4` above `s1710001.mp4` badges only `s1710004.mp4` "was 4", and the save bar says "1 clip moved"; Reset restores the order with no question
    - dragging again and saving gives a PUT body whose `look`, `clips`, `ignore` and `metadata` equal the GET `/reel` body, and whose only chapter lists `s1710004, s1710001, s1710002, s1710003`. `reel.yaml` on disk matches. The page shows "Saved", leaves Edit mode with focus on the `h1`, and shows "Needs render" with the edit reason.
    - **busy Save keeps focus:** with a reorder pending and `page.route('**/api/v1/events/**/reel', …)` holding the PUT, press Enter on Save: `document.activeElement` is still Save, Save has `aria-busy="true"` and `aria-disabled="true"` and no `disabled` attribute, a second Enter sends no second PUT, and the handles are `disabled`; then release the route
    - setting only the location to `Hönö` and saving leaves the chapter lines of `reel.yaml` byte-identical (`diff` of the chapter section before and after)
    - **conflict:** while editing, change the `reel.yaml` title on the host with `sed`, then press Save. The conflict alert shows, and the edits are kept. **Reload latest** asks nothing and shows the hand-made title. Repeat the conflict, choose **Overwrite with mine**: a `Dialog` opens with Cancel focused; confirming with the PUT held by `page.route` leaves `document.activeElement` on **Overwrite with mine** (`aria-busy`, not `disabled`); after release it saves, and the operator's version is on disk.
    - emptying the title shows "Left empty: inherits from the folder name when saved", and no hint presents the title just cleared as the folder name's; saving leaves `reel.yaml` with no title, and the page shows `Grillning med Grannar`
  - **Två kapitel** (`2024-08-20 - Två kapitel - Tjörn`), keyboard and structure:
    - Space, ArrowDown and Space on the `Kvällen/s1710002.mp4` handle give the order `s1710003, s1710002, s1710004`, and the dnd-kit live region reads "s1710002.mp4 moved to position 2 of 3"; then Reset
    - `s1710004.mp4` in `Main` is listed after `s1710001.mp4` in a separate list, marked "Ignored", with no handle or buttons
    - dragging `Kvällen/s1710003.mp4` upward past the top of `Kvällen` stops the row at `Kvällen`'s edge; after release it is first in `Kvällen` and `Main` is unchanged; then Reset
    - moving `Kvällen/s1710004.mp4` to the front and saving writes the `Kvällen` order from the spec, leaves `Main` as `[s1710001.mp4]`, and keeps `ignore: [s1710004.mp4]` on disk
  - **Badutflykt** (`2024-08-02 - Badutflykt - Varberg`): the hint and the save bar say saving adds 1 new clip. Stop `serve`, press Save: the page shows "not reachable" plus Retry, and the draft is kept. Restart `serve`, hold the PUT with `page.route` and press Enter on Retry: focus stays on Retry (`aria-busy`, not `disabled`); after release, `reel.yaml` lists `s1710003, s1710001, s1710004`.
  - **Sommarlov** (`2024-09-01 - Sommarlov`):
    - **Move down** on `s1710002.mp4` keeps `document.activeElement` inside that row, badges `s1710002.mp4` "was 1", and the editor's status region announces the move
    - `borttagen.mp4` stays listed at position 3; after saving the swap it is still last on disk, and its line still ends with `# MISSING` (the gate `editorial-chapter-roundtrip`). If the comment is gone, stop and report: the gate did not hold; do not work around it in `web/`.
    - **stale view:** with the page read, append `extra.mp4` to its chapter on disk, then press Edit. The page shows "changed on disk" plus "Read again", and no Save.
    - **read-only folder:** after Read again, `chmod a-w` the event folder, then save a reorder. The alert names the permission error and offers Retry, and the draft is kept. After `chmod u+w`, Retry saves.
  - **2024-07-14 - kalas:** all fields are empty, and the hints read "From the folder name: Kalas" and "From the folder name: 2024-07-14".
  - **Blandat:** a title-only save leaves `reel.yaml` with no `chapters` key.
  - **Två mappar:** reordering the root chapter and saving creates a `reel.yaml` that lists both chapters with all four clips.
  - **Midsommar 2024** (`2024-06-21 - Midsommar - Dalarna`):
    - clearing only the day of the date shows the incomplete-date message and no Save; `reel.yaml` still sets `2024-06-21`
    - a date after today shows the service's "is in the future" message at the date-and-title group, and `reel.yaml` is unchanged
    - a new title then saves; `GET /api/v1/jobs` returns the same set as before (no job enqueued)
    - pressing Back shows the list re-read (a new `GET /api/v1/events` request) with the new title
  - **Unsaved guard** (on Grillning, with a reorder pending):
    - Back keeps `page.url` on the event page and opens "Discard unsaved changes?" with Keep editing focused
    - Escape keeps the edits
    - Back then Discard shows the list, and `reel.yaml` is unchanged
    - with edits pending, `page.close({ run_before_unload: True })` raises a `beforeunload` dialog (`page.on('dialog')`)
    - Refresh and **Stop editing** ask too
    - entering Edit mode with no change and pressing **Stop editing** asks nothing, sends one `GET /api/v1/events/…` (every exit re-reads), and moves focus to the `h1`
    - entering Edit mode with no change and pressing Back shows the list with no dialog
  - **Omöjligt datum:**
    - the page shows the failure plus "Fix the date or title"
    - a future date shows the message, and the failure stays
    - `2024-02-29` saves, and the page then shows the event (1 clip, title `Omöjligt Datum`)
    - Back shows the list re-read: `Omöjligt datum` is listed among the 2024 events, and only `Bruten fil` remains under "Needs attention"
  - **Bruten fil:** its attention row opens a page with the failure and no form.
  - **Unparseable after load:** open `Stor dag`, write an unparseable `reel.yaml` into it on the host, press Edit: the unparseable failure words show and there is no editor. Delete that file afterwards.
  - **Scale, Stor dag (400 clips):**
    - all 400 rows are listed
    - over 10 keyboard steps of a lifted clip, and over 10 **Move down** clicks, the median time from input to the row's new position is under 100 ms (`performance.now()` plus `waitForFunction`). Record the numbers in the report.
    - if the budget is exceeded, stop and report; do not add virtualisation
  - **Keyboard only:** on Badutflykt, a reorder with the handle and a title save are completed with Tab, Space, the arrows and Enter only; every focused control shows a focus ring
  - **StrictMode (dev server):** run Vite on port 5104 in the node:22 container with `AUTO_REEL_API=http://127.0.0.1:8104` and `--network host`, and repeat the Grillning drag, the Två kapitel keyboard move and the guarded Back there, without saving. Effects replay only in dev, so this is where a StrictMode fault would show (a drag that never starts, a doubled guard dialog, a duplicated reel read left un-aborted).
  - **Screenshots and layout:**
    - light and dark screenshots at 1280 px and 390 px width of: Grillning in Edit mode with the save bar, the conflict alert, the Omöjligt datum fix form, and the discard dialog. Save them to `<scratchpad>/verify/event-edit-screen/`.
    - at 390 px, `document.documentElement.scrollWidth <= clientWidth`, every row still shows its position, file name, status, size and time, and the save bar's Reset and Save are visible
    - **toast above the save bar:** at 390 px with the save bar shown, `getComputedStyle(document.documentElement).getPropertyValue('--toast-inset-bottom')` equals the bar's `offsetHeight` in px, and so does `scroll-padding-bottom`; in the dev-server pass, `page.evaluate(() => import('/src/ui/toast.ts').then(m => m.toast.error('probe')))` shows a toast whose bounding box ends above the bar's top, with Reset and Save still hit-testable (`elementFromPoint`); after Reset hides the bar, the property is gone
    - under `reducedMotion: 'reduce'`, the rows have no transform transition and no element under the editor has a running animation (`document.getAnimations()` is empty)
    - an ad hoc axe-core run in Edit mode reports no serious or critical violations

## 6. The Edit-mode seam with `render-progress-screen` (at the pre-archive rebase)

- [ ] 6.1 Evaluate this task only at the pre-archive rebase, never during implementation: the supervisor says which case applies after merging the first of `event-edit-screen` and `render-progress-screen`. During implementation, leave the box unchecked, go on to 7.1, and have the final report say "seam pending until the pre-archive rebase". At the pre-archive rebase, confirm the case on the rebased branch with `ls openspec/changes/archive/ | grep -- '-render-progress-screen$'`:
  - **It prints nothing:** write "not applicable: `render-progress-screen` wires the seam when it archives second" on this task and check the box.
  - **It prints the directory:** wire the seam in `EventDetail.tsx` (design, "Where it mounts", parts b to d), then run the combined check below:
    - deferred self-started re-reads while editing: while `editing`, every re-read EventDetail would start by itself (`reread()`: the render-finished re-read, and the "fresh" / 404 enqueue answers) only sets a pending ref; the `load()` in `leaveEditMode()` is that deferred re-read and clears the ref; entering Edit mode aborts a quiet re-read already in flight and sets the same pending ref (verify: start a quiet re-read held by `page.route`, press Edit, release it with an abort — the editor and its draft stay)
    - `blockedReason` on `RenderControl` while editing: `blockedReason={editing ? 'Save or leave Edit mode to render' : undefined}`
    - the draft is not reset on a quiet re-read: confirm that `load({ quiet })` never touches `editing` and that the editor keeps its draft when a quiet re-read hands it a new `event` object; report a difference, and do not rewrite `render-progress-screen`'s code
    - re-base the text of any MODIFIED block on the current `openspec/specs` (this change has none; confirm)

  Verify, in the second case only:
  - `tsc --noEmit` and `npm run build` pass after `npm ci` on the rebased branch, and the `EventDetail.tsx` diff for the seam is 15 lines or fewer
  - the combined Playwright check, with 5.1's setup and conventions, `serve` restarted on the rebased branch, and no worker running. First add `2024/2024-12-01 - Lång` to this change's library copy only: 40 symlinks (`a01.mp4`…`a40.mp4`) that cycle through `clips/s1710001.mp4`…`clips/s1710004.mp4`, never the zero-byte `clips/trasig.mp4` (`render-progress-screen`'s recipe). Then:
    - `2024-06-27 - Grillning med grannar`, with no active job (it offers Render): entering Edit mode removes Render and shows "Save or leave Edit mode to render"; leaving Edit mode brings Render back
    - `2024-12-01 - Lång`: press Render (the job waits), enter Edit mode, move one clip and change the title
    - install `page.route('**/api/v1/events/**', r => r.abort())` and record the time; only then start `auto-reel worker $DEV/library --device cpu` (it may run jobs queued earlier first)
    - while Lång's job is queued or running, at 1280 px and 390 px, light and dark: `document.documentElement.scrollWidth <= document.documentElement.clientWidth`; Save and Reset are visible, with bounding boxes inside the viewport; Render and Render anyway are absent and "Save or leave Edit mode to render" shows; the progress and Cancel stay
    - once the render finishes: the WebSocket delta carrying Lång's job as terminal (`page.on("websocket")`, `framereceived`) arrived after the recorded route time; `page.on("request")` recorded no events request while Edit mode was open; the editor stays, with the moved clip, the changed title and the save bar, and no failure view replaces the page
    - remove the route, then **Stop editing** → Discard: exactly one `GET /api/v1/events/…` is sent, and the page shows Up to date with the job Rendered; stop the worker (SIGINT)
    - screenshots to `<scratchpad>/verify/event-edit-screen/combined-*`

## 7. Validation

- [ ] 7.1 Run the gates. Verify all pass:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `web-design-system`'s motion grep gate (its design, "The motion grep gate"), its three commands verbatim over this change's directory:
    - `grep -rnE 'transition[^;]*[0-9.]+m?s\b' web/src/edit` prints nothing (no literal transition duration)
    - `grep -rn 'animation[^;]*--dur-' web/src/edit` prints nothing (no token-timed loop)
    - every hit of `grep -rnE '(^|[^-])animation(-name)?:|@keyframes' web/src/edit` lies inside a `prefers-reduced-motion: no-preference` block (read the hits)
  - `grep -rn 'autoFocus' web/src/edit` prints nothing
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, then `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`; the OpenAPI drift and web-mount tests stay green
  - `git diff --stat main -- auto_reel_ng tests scripts web/openapi.json web/src/api/schema.d.ts` is empty
