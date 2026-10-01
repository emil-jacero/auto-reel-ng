## 1. Gate

- [x] 1.1 Confirm that `openspec/changes/archive/*-media-endpoints` **and** `openspec/changes/archive/*-cross-chapter-drag` exist on main, and that neither `openspec/changes/media-endpoints` nor `openspec/changes/cross-chapter-drag` does. Stop and report to the supervisor if either is missing. Then re-check the names this change builds on (design, "Context", "Files and the seams"), and stop and report on any mismatch:
  - `web/src/api/schema.d.ts` has the path `"/api/v1/events/{event_id}/media"` with a required `clip` and an optional `v` query parameter, and `web/src/api/thumbnail.ts` still exports `thumbnailUrl(eventId, clip)`
  - `web/src/cuts/CutsPanel.tsx` exports `CutPanels` (`get`, `set`), `PanelState` and `CutHandlers`, and `CutsPanel` (`memo`) has the props `id`, `identity`, `name`, `cuts`, `open`, `locked`, `panels`, `handlers`, the local `setFields`, the `focusAfter` layout effect, the passive scroll effect, and `hidden={!open}`
  - `web/src/cuts/times.ts` exports `checkCut(listed, typedIn, typedOut)`, `CutRefusal`, `refusalWords`, `CUT_HINT`, `formatTime`, `parseTime` and `ListedCut`, and imports only with `import type`
  - `web/src/edit/ClipOrderList.tsx`'s `ClipRow` mounts `CutsPanel` with the props above and has `eventId` and `clip`, and `RowBody` (`memo`) renders `ClipThumb eventId clip name`; the one `DndContext` lives in `web/src/edit/ChapterDrag.tsx`, the drag's activator is the handle only (`setActivatorNodeRef`), and its cross-chapter drop scrolls the handle (the row's first line) into view, as its amended rule says ("the handle and the row's first line … fully visible")
  - `web/src/edit/EventEditor.tsx` creates `cutPanels` (`{ panels, clear }`) once, and its `onReset` calls `cutPanels.clear()` before `dispatch({ type: 'reset' })`
  - `web/src/ui/Icon.tsx`'s `IconName` has `play` and `x`. Note which of `pause`, `skip-forward` and `download` exist already (`movie-player-screen` may have added some). Only the missing ones are added in 3.1.
  - `ls openspec/changes/ openspec/changes/archive/ | grep movie-player-screen` tells whether D-15 has landed (task 5.1). If it has:
    - note whether `web/src/styles/tokens.css` has `--media-bg` exactly as design "Layout, look and motion" gives it (task 3.1 adds it only if absent)
    - `api/movie.ts` and `api/headers.ts` exist: reuse their status mapping (and `contentRangeSize`) in `checkClipMedia` rather than restating it; the response-to-kind table must stay identical
  - `ls ../auto-reel-media/samples/` lists the ten samples, `sony-xavc-1080p25-pcm.mp4` … `legacy-render-mpeg4-mp3.mp4`
  - `ls openspec/changes/` shows no other change touching `web/src/cuts/` or `web/src/edit/`

  Re-base both MODIFIED blocks in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`. For "Every clip row shows a frame from its clip", carry the Edit-mode Watch exception and the scenario "In Edit mode a clip's frame is a Watch button" onto the landed text. For "Edit mode lists, adds and removes a clip's cuts", carry these edits:
  - the refusal sentence ("…, or when it ends after the clip's length once the page knows that length (below)", "…, or the clip's length")
  - the "The clip's length" paragraph that replaces "The page does not know a clip's length…"
  - the scenario "A clip never previewed is not checked for length"

  Verify: `openspec validate clip-preview-screen --strict` passes, and a `diff` of each requirement's main text against the change's text shows only those edits.

## 2. web/ — the model (pure)

- [x] 2.1 Change `src/cuts/times.ts` and add `src/preview/playback.ts` (design, "The playhead slider", "Set From / Set To", "Skip cuts: one frame ahead, the render's merge", "The clip's length", "Copy").
  - `times.ts`:
    - `checkCut` takes an optional `length` (seconds) and refuses `past-end` after `order` and before `overlap`
    - `CutRefusal` gains `{ kind: 'past-end'; field: CutField; at: number; length: number }`
    - `refusalWords` handles it, and add `lengthHint`, `pastEnd` and `PAST_END`
  - `playback.ts`, with type-only imports: `Skip`, `END_SLACK_MS`, `toEnd`, `skipSpans`, `skipAt`, `playFrom`, `seekKey`, `along`, `playheadWords` and the preview's copy constants (`typedSpan` was removed in the review fixes: the bar's typed span is `checkCut`'s; `playback.ts` imports `formatTime` at runtime, accepted).

  Verify: a scratch script in `<scratchpad>/verify/clip-preview-screen/`, never committed, runs under `node --experimental-strip-types` in `docker.io/library/node:22`, imports both files, and asserts:
  - `checkCut`:
    - with no `length`, every case of `clip-cuts-screen` task 2.1 gives the same answer as before. Run that task's assertions unchanged.
    - with `length` 6.02 and no cuts:
      - `5`/`7` → `past-end` at `end`, `at` 7
      - `7`/`8` → `past-end` at `start`
      - `0:06.02`/`7` → `past-end` at `start` (a start at the end: no end could fix it)
      - `5`/`0:06.02` → ok
      - `5`/`6.021` → `past-end`
      - `3`/`2` → `order` (order comes first)
    - with `length` 6.0065, `5` / `formatTime(6.0065)` → ok
    - with `[{in: 0, out: 1.5}]` and `length` 6.02, `1`/`7` → `past-end` (before `overlap`)
  - `refusalWords` for both past-end refusals equals the design's "Copy" rows, and `lengthHint(6.02)` equals its row, which contains `This clip ends at 0:06.02, as this browser reads it` (never `0:06.02 long`)
  - `pastEnd({in: 3723.125, out: 3725.5}, 6.02)` is true, and `pastEnd({in: 0, out: 6.02}, 6.02)` is false
  - `skipSpans` over 6020 ms:
    - `[1,2]` → `[{1000,2000}]`
    - `[0,3]+[2,4]` → `[{0,4000}]`
    - `[0,2]+[2,4]` → `[{0,4000}]` (touching joined, as `kept_spans`)
    - `[5,99]` → `[{5000,6020}]`
    - `[7,8]` → `[]`
    - a removed cut is left out
    - `[4,5]+[0,1]` → sorted
  - `skipAt([{1000,2000}], …, 6020)`:
    - at 960 with step 40 → `{seek: 2000}` (one frame ahead)
    - at 940 with step 40 → null
    - at 1500 with step 0 → `{seek: 2000}` (the first frame itself), and with step 20 → `{seek: 2000}`
    - at 2000 → null
    - at 1980 with step 20 → null (the next frame starts at the cut's end)
  - a cut that ends between two frames is never sought again: `skipAt([{1000,2010}], 2000, 20, 6020)` → null (the frame Chrome shows after the seek to 2010), while at 980 with step 20 → `{seek: 2010}`
  - the end slack:
    - `skipAt([{5000,6020}], 4980, 20, 6020)` → `{stop: 5000}`
    - `skipAt([{5000,6020}], 4980, 20, 6080)` → `{stop: 5000}` (Firefox's length; 60 ms left)
    - `skipAt([{5000,6020}], 4980, 20, 6040)` → `{stop: 5000}` (Chrome after a `durationchange`)
    - `skipAt([{5000,5900}], 4980, 20, 6020)` → `{seek: 5900}` (120 ms left)
    - `toEnd({from: 5000, to: 5921}, 6020)` is true, and `toEnd({from: 5000, to: 5920}, 6020)` is false
  - `playFrom`:
    - `([{1000,2000}], 1500, 6020)` → 2000
    - `([{1000,2000}], 500, 6020)` → 500
    - `([{5000,6020}], 5000, 6020)` → 0
    - `([{0,1000},{5000,6020}], 5500, 6020)` → 1000
    - `([{5000,6020}], 5000, 6080)` → 0 (runs to the end within the slack)
    - `([{0,1000}], 6020, 6020)` → 1000, and `([], 6020, 6020)` → 0 (Play at the clip's end starts over)
    - `([{0,6020}], 0, 6020)` → null
  - `seekKey`:
    - `ArrowRight` at 5990 of 6020 → 6020
    - `ArrowLeft` at 50 → 0
    - `PageDown` at 6020 → 5020
    - `Home` → 0, and `End` → 6020
    - `ArrowUp` and `ArrowRight` agree
    - `Enter` → null
  - `playheadWords(1234, 6020, [{in: 1, out: 2}])` → `0:01.234 of 0:06.02, in cut 1`, and at 300 → `0:00.3 of 0:06.02`
  - (review fixes) the bar's typed span is `checkCut`'s: `checkCut([], '0:01.2', '2.5', 6.02)` accepts 1.2–2.5, and an overlapping or past-end span is refused (so not drawn); `readyWords('a.mp4', 6.02)` → `a.mp4 is ready to play, 0:06.02.`
  - `formatTime(1.2) === '0:01.2'`, and `parseTime(formatTime(2.6074729)).ms === 2607`
- [x] 2.2 Add `src/preview/previews.ts` (`ClipPreviews`, `createClipPreviews`; no runtime import) and `src/api/clipMedia.ts` (`clipMediaUrl`, `MediaCheck`, `checkClipMedia`, `changedSince`) (design, "One preview at a time", "What the browser cannot do: by cause, with one byte"). `clipMediaUrl` checks its path and query against the generated `paths` with `satisfies`, as `thumbnail.ts` does.

  Verify:
  - `npx tsc --noEmit` passes in the node:22 container
  - the scratch script of 2.1 imports `previews.ts` and asserts:
    - `show('a', 'toggle')` then `show('b', 'thumb')` leaves `open() === 'b'` and `opener('b') === 'thumb'`, and calls each listener once per change
    - `takeFocus('b')` is true once and then false; a second `show('b', 'thumb')` makes it true once more and changes `showCount()`; `takeFocus('a')` is false
    - `hide('a')` then changes nothing, and `hide('b')` gives `null`
    - `hideAll()` gives `null` and keeps `length(src)`
    - `keepPlayhead('b', 2.5)` then `playhead('b') === 2.5`, and `keepPlayhead('b', undefined)` forgets it
    - `show('b', 'toggle')`, `keepPlayhead('b', 2.5)`, `hide('b')` → `playhead('b') === undefined` and `opener('b') === null`, and the same with `hideAll()` (a panel hidden or a Reset reopens at the start)
    - `setLength(src, 6.02)` notifies, and `setLength` with the same value does not
  - `clipMediaUrl('2024/2024-08-20 - Två kapitel - Tjörn', {identity: 'Kvällen/s1710002.mp4', mtime: '2024-06-27T14:03:11.123456Z'})` equals `/api/v1/events/2024/2024-08-20%20-%20Tv%C3%A5%20kapitel%20-%20Tj%C3%B6rn/media?clip=Kv%C3%A4llen%2Fs1710002.mp4&v=2024-06-27T14%3A03%3A11.123456Z`, and with `mtime: null` it has no `v`
  - `changedSince('2024-06-27T14:03:11.123456Z', 'Thu, 27 Jun 2024 14:03:11 GMT')` is false, with `… 14:03:12 GMT` it is true, and with either argument `null` it is false
  - `checkClipMedia` is checked against task 4.1's served library: 206 → `served` with the response's `Last-Modified`, 416 → `empty`, 404 and 502 → `problem`

## 3. web/ — the preview

- [x] 3.1 Add `src/preview/ClipPreview.tsx` (`ClipPreview`, `CutBar`, `usePreviewOpen`, `useClipLength`) and `src/preview/preview.css` (with `.clip-thumb-watch`), add the missing ones of `pause`, `skip-forward` and `download` to `src/ui/Icon.tsx`, and add `--media-bg` to `src/styles/tokens.css` if task 1.1 found it absent, with exactly the value and comment design "Layout, look and motion" gives (design, "The element", "Custom controls, native elements", "The playhead slider", "Skip cuts", "The clip's length", "What the browser cannot do", "Locks, moves and Reset", "Layout, look and motion", "Copy").
  - The element's source is set and removed in a layout effect, never as a JSX `src`.
  - The skip loop is `requestVideoFrameCallback` only.
  - Notes and failures use `Alert` with `role="note"`.
  - The stage's background is `var(--media-bg)`, with no fallback.
  - Play's focus comes from the store's `takeFocus` in a layout effect keyed on `showCount()`.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the node:22 container
  - `preview.css` declares only `@layer screens`, and `grep -n "transition\|animation" web/src/preview/preview.css` prints nothing
  - `grep -rn ' disabled=\|autoFocus\|autoPlay\|role="alert"\|controls=' web/src/preview` prints nothing
  - `grep -n "src=" web/src/preview/ClipPreview.tsx` shows no `<video src=`
  - `grep -rn "timeupdate" web/src/preview` prints nothing
  - `grep -rn "var(--media-bg," web/src/preview` prints nothing, and `grep -n -- "--media-bg" web/src/styles/tokens.css` prints the one `light-dark()` line
  - `grep -rn "Preview\b" web/src/preview web/src/cuts | grep -v "ClipPreview\|usePreviewOpen"` shows no visible word or name "Preview" (the control is "Watch")
- [x] 3.2 Wire the preview into Edit mode (design, "Where the preview lives", "One preview at a time", "Set From / Set To", "Opening, closing and focus", "Performance"):
  - `CutsPanel.tsx`:
    - `CutPanels` gains `previews`, and `CutsPanel` gains the props `eventId` and `mtime`
    - the Watch toggle comes first, and `ClipPreview` mounts while open and the panel is shown; hiding the panel closes it in a layout effect
    - `onSet` goes through `setFields`
    - the length feeds `checkCut`, the hint and the `Past the clip’s end` badge
    - `focusAfter` gains `preview-toggle`; Close and Escape return focus to the opener (`previews.opener`): that target, or the row's `.clip-thumb-watch`
  - `ClipOrderList.tsx`: `ClipRow` passes `eventId={eventId}` and `mtime={clip.mtime}` to `CutsPanel`, and, for a cuttable clip, a stable `onWatch` (`useCallback` over `identity` and `panels`: show the panel if hidden, then `panels.previews.show(identity, 'thumb')`) to `RowBody`, which wraps `ClipThumb` in the Watch button (design, "The thumbnail opens the player")
  - `EventEditor.tsx`: the panel store gets `previews: createClipPreviews()`, and its `clear` calls `previews.hideAll()`

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff main -- web/src/edit/ClipOrderList.tsx` adds only the two `CutsPanel` props, `onWatch`, and the button around `ClipThumb`
  - `git diff main -- web/src/events/ClipThumb.tsx web/src/events/thumbs.css` is empty
  - `git diff main -- web/src/edit/EventEditor.tsx` touches only the store's creation, and the import
  - `git diff main -- web/src/edit/draft.ts web/src/edit/SaveBar.tsx web/src/edit/ChapterDrag.tsx web/src/edit/dragSlots.ts web/src/events` is empty
  - `grep -rn ' disabled=' web/src/edit web/src/cuts web/src/preview` prints nothing

## 4. Verification against the dev library

- [x] 4.1 Set up the agent's own environment per the dev-env runbook §9 and design, "Verification fixtures". Never use port 8080 or 5173, `../auto-reel-dev`, the default database, or another agent's database, library or port. Never stop or remove a `test-pg` container.
  - **Environment:**
    - `SLUG=clip-preview-screen`, database `arel_clip_preview_screen`, library `../dev-clip-preview-screen`
    - `auto-reel serve <library> --port 8131` over a fresh `npm run build`, with no worker
  - **Fixtures:**
    - Add `Provklipp`: symbolic links only. `auto-reel-media/` stays untouched, which `find ../auto-reel-media -newer <scratch>/marker` printing nothing confirms at the end.
    - Add `Stor dag`, and normalise and copy every `reel.yaml` a check will `diff`.
  - **Playwright:** drive `http://127.0.0.1:8131/` with a script in `<scratchpad>/verify/clip-preview-screen/`.
    - The container is the Chrome-channel image `localhost/playback-research:chrome`, with `--network host` and `channel="chrome"`, or its Firefox. If `podman image exists localhost/playback-research:chrome` fails, build it from the two-line Containerfile in `docs/research/browser-playback.md` (`FROM mcr.microsoft.com/playwright/python:v1.49.0-noble`, `RUN pip install -q playwright==1.49.0 && python -m playwright install chrome`). Never Playwright's stock Chromium for playback: it cannot decode H.264 (R0).
    - Scope locators to `main:not([hidden])`.
    - Record every request whose path ends in `/media` and every `PUT …/reel` body.
    - Record every text of the editor's `role="status"`.
    - Use the **keyboard only** (Tab, Shift+Tab, Enter, Space, Escape, arrows, Page Up/Down, Home/End, typing) except where an item says pointer, and after each step assert `document.activeElement`.
    - Count frames shown with a `requestVideoFrameCallback` observer the script attaches to the page's `video`, recording `mediaTime`.

  Check:
  - **Every scenario of the two ADDED requirements and of the MODIFIED one, in order, on the named events, in Chrome**, with these specifics:
    - "Nothing loads until a preview is opened": no `/media` request, and `document.querySelectorAll('video').length === 0`, before Watch. After it, every `/media` request's `clip` is `c0400.mp4` and its `v` is that clip's `mtime` from `GET /api/v1/events/…`.
    - "Opening another preview closes the first": after the second Watch, no `/media` request for `s1710001.mp4` starts within 2 s, and exactly one `video` exists
    - "Closing gives focus back": play to about 2 s before each way of closing. After each reopening, `currentTime` is 0 and `paused` is true, also after the closing by the Cuts control.
    - "Watching from the row in one press": the thumbnail is a `button` named "Watch s1710002.mp4" and no thumbnail is focusable in the read view; every row's `getBoundingClientRect()` before and after the press equals, within 1 px, except the pressed row's height; after Escape, `document.activeElement` is that thumbnail button. The pointer press on `s1710001.mp4`'s thumbnail fires no `dragstart` and announces no lift, and the clips' order in the DOM is unchanged.
    - Each scenario starts from a fresh load of the event page, so that no length a browser revised during an earlier scenario (Chrome raises 6.02 to 6.04 while playing) carries over.
    - "Skipping cuts while playing":
      - with Skip cuts on, no recorded `mediaTime` lies in [1, 2) and some lie in [2, 2.5]
      - with it off, some lie in [1, 2)
      - repeat once at 390 × 844
    - "A cut that ends between two frames is jumped over once": count `seeking` events while playing. Exactly one, `currentTime` passes 2.5 within 1.5 s of reaching 1, and every recorded `mediaTime` in [1, 2.01) is ≥ 1.99 (only the straddling frame at 2.00). Run it in Chrome and in Firefox.
    - "A cut to the clip's end ends playback", in Chrome and in Firefox: `paused` is true, `currentTime` is within 0.05 s of 5, no `mediaTime` is over 5.0, and `ended` is false
    - "A cut past the clip's end is refused once its length is known": `document.querySelector('video').duration` is 6.02 in Chrome. The refusal's words equal the design's "Copy".
    - "The preview follows its clip": run once by a pointer drag (`cross-chapter-drag` task 4.1's method) and once by Move clips. Each time, `currentTime` is 2.5 and `paused` is true after the move.
      - At 1280 × 900 and at 390 × 844, after the pointer drop: the handle is `document.activeElement`, and its rect, and the rect of the row's first line (handle, name, Cuts control), lie between the bottom of the page header or the chapter heading, whichever is lower, and the top of the save bar.
      - After Move clips, `document.activeElement` is the Move clips control (G1), not a control of the preview.
    - "A pending save leaves playback alone": hold the `PUT` with `page.route` and press Enter on Save, then:
      - `document.activeElement` stays on Save
      - Set From and Set To are `aria-disabled` with no `disabled` attribute, and pressing them changes no field
      - Play toggles `paused`
      - abort the route afterwards: the draft is kept
    - "A clip removed from disk since the page was read": delete only the library's own symlink, and restore it after. The note's words say to stop editing, never "Refresh".
    - (review fixes) "Try again opens the preview anew": abort `**/media?*` so the check finds no answer (focus on Close), unroute, press Enter on Try again: `document.activeElement` is Play once ready, readiness is announced, and Escape closes the preview. Space on the playhead plays and pauses with `scrollY` unchanged. A press on Play while the media request is held plays the clip once it is released. The Watch toggle reads "Hide player" while open. The bar draws no typed span for an overlapping or past-end typed cut, and the legend names no kind the bar does not draw. Move clips with the preview at 2.5 s keeps 2.5 in a StrictMode dev build (vite dev server proxied to the serve) as in the production build.
  - **Saving a cut set at the playhead:** after "Setting a cut at the playhead", Save. The captured body gives `s1710001.mp4` `trims: [{in: 1.2, out: 2.5, reason: manual}]`, and the Grillning `reel.yaml` `diff` against its normalised copy shows only that cut's lines.
  - "A clip changed on disk since the page was read": after Edit mode opened, type a title change and `2` in the start field of `s1710001.mp4`, replace the library's `s1710002.mp4` symlink of Grillning by a regular file of 1 MiB of random bytes, then open its preview. The note says to stop editing (save first), never "Refresh", and the title field, the typed `2`, the save bar and the editor are untouched until the operator acts; no `PUT` and no read of the event is sent. Afterwards, restore the symlink and confirm with `ls -l`.
  - **Firefox** (the same image's bundled Firefox 132, keyboard only):
    - "No sound for a Sony clip in Firefox" and the Firefox half of "A picture this browser cannot show"
    - "A cut past the clip's end is refused once its length is known", with `0:07` refused and the length Firefox reads named
  - Restore every touched `reel.yaml` and symlink afterwards, and `diff` to confirm.
- [x] 4.2 Layout, touch, theme, motion and accessibility. States, on `2024-06-27 - Grillning med grannar` unless named:
  - (a) Edit mode with every panel hidden
  - (b) the preview of `s1710003.mp4` open and paused at `0:01.5`, with G2's fixture cut removed (its Undo shown), a cut `3`–`4` added and `5`/`5.5` typed, so the bar and the legend show all three kinds
  - (c) Skip cuts pressed, playing
  - (d) the Trasig failure note
  - (e) the no-picture note on Provklipp's `hevc-mov-rotate90-aac.mov` in Chrome
  - (f) Provklipp's `h264-720p-rotate90-aac.mp4` playing
  - **Sizes**: 320×700, 390×844, 768×1024 and 1280×900, each in the light and the dark theme (the theme control), in each state. Save the screenshots to `<scratchpad>/verify/clip-preview-screen/` and look at every one.
    - `document.documentElement.scrollWidth <= clientWidth`
    - `.preview-stage`'s box is 16:9 within 1 px, at most 640 × 360, and its size equals its size before `loadedmetadata` within 0.5 px
    - in (f), the picture's drawn frame is taller than wide inside the stage
    - in (a), every row's height equals a run on main's build taken first, within 1 px
  - **Coarse pointer**: a context with `has_touch` and `is_mobile` at 320×700 and 390×844.
    - Run `ui-a11y-polish`'s touch probe, with `elementFromPoint` on a 7 × 7 grid across the designed 44 × 44 area, each control scrolled to the window's centre first. Probe the thumbnail's Watch, the panel's Watch, Close, Play, Skip cuts, Set From, Set To and Download.
    - For the playhead, probe 7 points across its width at its centre line and at ±20 px from it: each returns the slider.
    - A tap at 25 % of the slider's width moves `currentTime` to within 0.1 s of 25 % of the length. A 200 px vertical swipe that starts on it changes `scrollY` and not `currentTime`.
  - **Fine pointer**: at 1280 and 390 with a mouse, the bounding boxes of Edit, Save, the handles, the thumbnails (now Watch buttons), the move buttons, the Cuts controls, the cut fields and Add cut keep their size and inline place against a run on main's build taken first, with every preview closed; what lies under the open panel moves down by exactly the Watch row the panel gained.
  - **Reduced motion** (`reduced_motion='reduce'`): in (b) and (c), `document.querySelector('.clip-preview').getAnimations({subtree: true})` is empty, and Set From's `scrollIntoView` lands at once.
  - **Contrast**, in both themes:
    - at least 3:1 against the track (`--surface`), and against `--surface-2` where they overlap the panel: `[data-kind=cut]`, the dashed border of `[data-kind=removed]`, the border of `[data-kind=typed]`, and the head
    - at least 4.5:1 on `--surface-2`: the time, the legend's words, the `Past the clip’s end` badge and Skip cuts' pressed words
    - the stage's computed background is `--media-bg` (black) in both themes, the `Loading…` words reach 4.5:1 on their badge, and the badge 3:1 against the black stage
    - the thumbnail's Watch shows a 2px focus ring, unclipped, in both themes
  - **forced-colors**: a context with `forced_colors='active'` in (b). The cut, typed and removed spans remain visible (non-transparent `background-color` or `border-color`).
  - **axe-core**, injected ad hoc from cdnjs: no serious or critical violation in (a) to (f) in both themes. Run it in Firefox too for the no-sound note.
  - no Playwright script, screenshot or `.playwright` directory is in the worktree
- [x] 4.3 Scale and render budget on `2024/2024-09-15 - Stor dag` at 1280 × 900 (design, "Performance"). Use the production build, with `cross-chapter-drag`'s commit hook installed by `page.add_init_script` before the first navigation and its host-child table extended by `section.clip-preview` (ClipPreview) and `div.clip-cuts` (CutsPanel). It is never committed. Record every number in the report.
  - **No media before asked:**
    - Open Edit mode, scroll to `c0400.mp4` and back to the top, show and hide the Cuts panels of `c0001.mp4`, `c0200.mp4` and `c0400.mp4`, and drag `Kväll/k001.mp4` into the 400 and back (pointer).
    - Then: 0 `/media` requests and 0 `video` elements.
  - **Opening:** from Enter on Watch of `c0200.mp4`, and from Enter on its thumbnail, to Play focused, under 200 ms each.
  - **Playing:** over 5 s of playback with Skip cuts on and a cut `1`–`2` added:
    - 0 `ClipRow`, 0 `ClipOrderList` and 0 `EventEditor` commits, and no more `CutsPanel` commits than the video's `durationchange` events (the panel follows the latest length)
    - `ClipPreview` commits recorded (expected about one per shown frame)
    - no `longtask` of 100 ms or more
  - **Typing while playing:** 10 characters in Title, under 50 ms per keystroke, with 0 `ClipOrderList` commits.
  - **Set From:** from Enter to its announcement, under 100 ms; with text already in the field, 0 `ClipOrderList` commits (into an empty field, the typed mark's own row and list commits, G2).
  - **A drag while a preview plays:** a keyboard step of `c0199.mp4`, median under 100 ms over 10 steps (`cross-chapter-drag`'s budget), each step's commit rendering `RowBody` only for the rows it renumbers; the same 10 steps with the clip paused render `ClipPreview` and `CutsPanel` 0 times (while it plays, a pending frame update may share a step's commit).
  - **Closing:** after Close, 0 `video` elements, and no `/media` request starts in the next 2 s.
  - When a budget fails, stop and report the numbers. Do not add a dependency or virtualisation.

## 5. Docs and validation

- [x] 5.1 Update `web/README.md` and `docs/high-level-design.md`:
  - `web/README.md`:
    - the Edit-mode paragraph: Watch in the Cuts panel and on the clip's thumbnail, one video at a time, the controls and keys, Set From / Set To, Skip cuts, the length check, the notes by cause, nothing loaded before Watch, and Chrome (`localhost/playback-research:chrome`) / Firefox as the verified browsers
    - "Design system": `--media-bg`, if this change added it
    - the file tree: `api/clipMedia.ts` and `preview/` with its four files
  - `docs/high-level-design.md` (design, "HLD"), each place re-read on main first:
    - D-16 after D-15 (or after D-14 if `movie-player-screen` has not landed)
    - D-14's length sentence and its previews wording
    - §4.10's v1 bullet and slice row D

  Then run the gates:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `web-design-system`'s motion grep gate, its three commands verbatim, over `web/src/preview`, `web/src/cuts` and `web/src/edit`
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full `.venv/bin/python -m pytest` (the web-mount and OpenAPI drift tests green)
  - `git diff --stat main -- auto_reel_ng tests scripts web/openapi.json web/src/api/schema.d.ts web/package.json web/package-lock.json` is empty
  - `openspec validate clip-preview-screen --strict` passes

  Verify that all of the above pass, and that each of these hits:
  - `grep -n "D-16" docs/high-level-design.md` (§7, D-14 and §4.10)
  - `grep -n "preview/" web/README.md`
  - `grep -n "clip-preview-screen" docs/high-level-design.md`
