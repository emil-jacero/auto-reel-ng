## 1. Gate

- [ ] 1.1 Re-check, on main after `clip-preview-proxy` has merged, every name this change builds on (design, "What the gate adds"), and write the real ones down in the PR body. Stop and report to the supervisor on any mismatch that changes the specs; follow the real names where only a name differs.
  - `git log origin/main --oneline | grep clip-preview-proxy` finds it.
  - `web/src/preview/ClipPreview.tsx`: the props of the component (does `clip` carry the proxy state? are `onSet`, `locked`, `typed` still the props they were?), where Play original sits in the controls, and `previews.ts`' override.
  - `grep -rn "STOP_EDITING\|stop editing\|Stop editing" web/src` lists every place that gives the "stop editing" advice, the gate's copy-failure titles included: each is routed through `staleAdvice` in 2.3.
  - `grep -rn "Edit mode's live region" web/src` and the announce calls: nothing assumes the editor's region beyond the `onAnnounce` prop.

  Verify: the written list names, for each row of the design's table, the real function or field; `openspec validate clip-play-read-view --strict` passes on the re-based delta.

## 2. web/ — the pure parts

- [ ] 2.1 New pure `web/src/events/watch.ts` (type-only imports): `canWatch(clip)` (`status !== 'missing'`) and `watchedAfterRead(open, clips)` (the open identity when the new read still lists that clip on disk, else `null`; `null` in, `null` out). New `watch.test.ts` (`npm test`).
  - Cases: active, new, ignored and excluded clips can be watched, a missing one cannot; `watchedAfterRead` keeps an identity that is listed active, new or ignored, drops one that became missing, drops one no chapter lists, answers `null` for `null`, and finds the clip in a later chapter of several; the same input twice gives equal output.

  Verify: `npm test` runs the new file green; `npx tsc --noEmit` passes in the node:22 container.
- [ ] 2.2 New `web/src/events/onePlayer.ts`: `pauseOthers(started, videos)` (pauses each video that is not paused and is not `started`) and `keepOneVideoPlaying(root)` (a capturing `play` listener on `root`, for `video` elements only; returns its remover). New `onePlayer.test.ts` (`npm test`), with stand-ins for the root and the videos (an `EventTarget`; no DOM).
  - Cases: a started video pauses the one that plays and not the paused ones; it does not pause itself; a `play` from a non-video target pauses nothing; nothing is closed or replaced (only `pause()` is called); the remover stops the listener; two starts in a row leave only the latest playing.

  Verify: `npm test` runs the new file green; `npx tsc --noEmit` passes.
- [ ] 2.3 In `web/src/preview/playback.ts` add `staleAdvice(readOnly)` (Edit mode: `STOP_EDITING`, unchanged; read-only: "Press Refresh to read the event again, then watch the clip anew."), `offersSkip(readOnly, cuts)` (Edit mode: always; read-only: at least one cut that is not removed), and give `goneWords` and `changedWords` a `readOnly` argument that defaults to false. New `playback.test.ts` (`npm test`; the module imports only `../cuts/times.ts`).
  - Cases: the Edit-mode words are byte-for-byte what they were (copy the old strings into the test); the read-only advice names Refresh and contains none of "edit", "save", "Edit mode"; `offersSkip` for no cuts, one cut, only removed cuts, in both modes.

  Verify: `npm test` runs the new file green; `git diff web/src/cuts` is empty.

## 3. web/ — the player and the row

- [ ] 3.1 In `web/src/preview/ClipPreview.tsx` make the player read-only when it is given no `onSet` (design, "One component"): `onSet`, `locked` and `typed` become optional; Set From and Set To are not rendered read-only; Skip cuts is rendered by `offersSkip`; `failureOf` and the gate's copy failures take their advice from `staleAdvice(readOnly)`. A read-only player's `cuts` are the clip's cuts as listed.
  - `CutsPanel.tsx` is not edited and passes `onSet`: `git diff web/src/cuts/CutsPanel.tsx` is empty and Edit mode's JSX for the preview is the same.

  Verify: `npx tsc --noEmit` and `npm run build` pass in the node:22 container; `git diff web/src/preview/ClipPreview.tsx` shows only the conditions above; the Chrome script of 4.1 finds, in Edit mode, "Set From at the playhead of <name>" and "Set To …" in the player of a clip and, in the read view, neither.
- [ ] 3.2 The read view's Watch and player row. New `web/src/events/ClipWatch.tsx` with `WatchButton` and `PlayerRow` (design, "The player opens in a row of its own", "The store…", "Focus and ids"), wired in `ChapterPanel` (a `Fragment` per clip: the `tr`, then `PlayerRow`; the button in the file cell between `ClipName` and `ReadCuts`; row ids from `headingId` and the index; `tr` gets `tabIndex={-1}`) and `ReadyView` (the store and its `hideAll` on unmount, the live region with `announce`, the `watchedAfterRead` layout effect with the focus rule, the cuts expression of design "Which clips…"). `EventDetailBody` installs `keepOneVideoPlaying(document)` in an effect and passes `focusHeading` down. CSS in `events/detail.css`: the button's place in the cell, `.clip-preview-row` and its cell at every container width (block in the `< 50rem` grids), the coarse-pointer 44 × 44 area, the forced-colors rule beside the others.
  - No state by colour alone (the words change, `aria-expanded` follows), no animation, no new custom property.

  Verify: `npx tsc --noEmit` and `npm run build` pass; `grep -n "clip-preview-row" web/src/events/detail.css` finds the rule at each container query; with the dev library on `PORT`, a Chrome Playwright script in `$SCRATCH` presses "Watch s1710001.mp4", sees one video, the region "Player for s1710001.mp4" directly after that clip's row, no request to `…/media` before the press and exactly the clip's after, and presses "Hide player of s1710001.mp4" to close it.

## 4. Playwright in a real browser (scratchpad only, never in the repo)

- [ ] 4.1 Function, against a dev library built from copies of the `auto-reel-media` samples (copies, never symlinks, for the clips that are made missing, changed or failed; `XDG_CACHE_HOME` under `$SCRATCH`; copies built with `auto-reel proxies`; the service on `PORT` and `DB`), in Chrome 154 (`localhost/playback-research:chrome`) and Firefox >= 155 (`localhost/pcm-audio-research:pw163`: print `browser.version` first and stop if it is below 155). Routes only on `**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel`, `**/reel?*`; sound is measured by tapping the element with WebAudio into an analyser, as the PCM research did (peak over 3 s of playback).
  - **Sound.** `sony-xavc-1080p25-pcm.mp4` and `sony-xavc-4k25-pcm.mp4` with a ready copy, in the read view: decoded peak above 0 in both browsers, "Playing the preview copy", no no-sound note. After Play original: Chrome peak above 0; Firefox peak 0 and the note, which names Play preview copy.
  - **Rows.** A Watch control on every clip on disk, none on a missing clip (a deleted copy of a sample); ignored and excluded clips have one; Tab order from the control into the player: Close, Play, playhead, Skip cuts (only on a clip with cuts), Play original last (a ready copy only); no Set From or Set To in the DOM.
  - **Cuts.** A clip with a cut from 0 to 1.5: the bar draws it, the legend reads "Cut", the playhead says "in cut 1" inside it, Skip cuts on starts playback at or after 1.5 s and shows no frame inside the cut, the page's cut list is unchanged. Route `**/reel` to fail: the note stays, no Skip cuts, an empty bar. An excluded clip with cuts: none on its bar.
  - **Load.** A scratch event of 400 symlinked copies of one small sample: on opening, scrolling to the end, Refresh, entering and leaving Edit mode, no `<video>` for a clip and no `/media` or `/proxy` request; after Watch on the last clip, one video and requests for that clip only.
  - **Focus and one at a time.** Enter on Watch lands focus on Play; Escape and Close land it on Watch; Watch pressed while open closes; Watch on a second clip, in another chapter, closes the first. Refresh and Edit close the player; the Movie section's player survives a Refresh as before.
  - **One video playing.** With a rendered movie in the event: play the movie, then a clip: the movie is paused at its position; play the movie again: the clip pauses and stays open; Skip cuts' jump is not interrupted.
  - **Failures.** A clip removed from the scratch library after the page read it: the note says it is no longer on disk and to press Refresh, says nothing of editing, and the page has not refreshed. A copy removed from the cache after the read: the gate's note with Play original, and the original plays with focus on Play.
  - **Re-reads**, with a worker on the scratch library and `DB`: rendering the event while a player plays leaves it playing; touching the clip and rendering again leaves the player paused at the same time on the new address, and no request for the old one; a proxy job finishing under a player that plays the original does not change its file. If no worker can run here, say so, and the unit tests of 2.1 are the evidence for the pure part.

  Verify: the script exits 0 for each browser; each assertion above is in its output; the results are saved to `$SCRATCH`.
- [ ] 4.2 Look at the result: the read view with a Watch control, a closed row, an open player with a ready copy, with the original and its Firefox note, and with a failure note, in light and dark at 1280, 800 (the grid layouts begin below 50rem of the table's own width), 390 and 320. Screenshots to `$SCRATCH`, each opened and looked at. At 320 and 390 the page does not scroll horizontally (`scrollWidth <= innerWidth`) with a 40-character clip name; with a coarse pointer the Watch control's tap area is at least 44 × 44 and reaches no other control; with `prefers-reduced-motion` nothing moves; the player's box is the same size before and after the file loads. Measure and report: a row's height with and without the Watch control (1280, no cuts), and the time from the press to the first presented frame on the 400-clip event.

  Verify: at least eight screenshots (each width in each scheme, with the states above spread over them) opened and described in the result; the measurements are printed.

## 5. Docs and gates

- [ ] 5.1 Docs. `web/README.md`: describe Watch on the event page's read view (what it opens, that it is read-only, Skip cuts as a view option, one player at a time, the Movie player pausing and being paused), and add `watch.ts`, `watch.test.ts`, `ClipWatch.tsx`, `onePlayer.ts`, `onePlayer.test.ts` and `playback.test.ts` to the file tree. `docs/high-level-design.md`: amend **D-16** with a dated paragraph (2026-10-03, change `clip-play-read-view`: the read view plays a clip in the same component, read-only, with Watch, one at a time, nothing loaded before a press, and that a started video pauses another because the read view, unlike Edit mode, shows the Movie player too); in §4.10 v2 add one sentence that the clip's player works outside Edit mode; in §6 phase 9 note the change. Refer to the proxy contract as **D-21** and the timeline as **D-20**; edit neither, and do not create either entry.
  - No other decision is edited; D-15 is cited, not changed.

  Verify: `git diff --stat` for this task shows only `web/README.md` and `docs/high-level-design.md`; `grep -n "clip-play-read-view" docs/high-level-design.md` finds the D-16 paragraph, §4.10 and §6.
- [ ] 5.2 Final gates: in the node:22 container `npm ci`, `npx tsc --noEmit`, `npm test` and `npm run build` pass; `git diff --stat -- auto_reel_ng tests web/openapi.json web/src/api/schema.d.ts web/src/cuts/CutsPanel.tsx` is empty (no Python, API or schema change, so black, isort, mypy, pylint and pytest are unaffected, `RENDER_GRAPH_VERSION` stays and no fingerprint input is added); `openspec validate clip-play-read-view --strict` passes.

  Verify: the four npm commands and the validate exit 0 and the diff stat prints nothing.
