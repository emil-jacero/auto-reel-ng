## 1. Gate

- [x] 1.1 Re-check, on main after `proxy-state-read` and `proxy-media-endpoints` have merged, every name this change builds on (design, "The gates, as planned"), and write down the real ones in the PR body. Stop and report to the supervisor on any mismatch that changes the specs, and follow the generated names where only a field name differs.
  - `git log origin/main --oneline | grep -E "proxy-state-read|proxy-media-endpoints"` finds both.
  - `web/src/api/schema.d.ts`: `ClipOut` has the proxy object (its state values `absent | ready | stale | failed`; where the facts' duration sits and its unit, seconds expected) and `paths` has `/api/v1/events/{event_id}/proxy` with `clip` and `v` query parameters, an `ETag` response header on 200/206 and the 404 problem body.
  - `grep -n "def .*proxy" auto_reel_ng/api/*.py` shows the route behind the clip route's path guard and auth, and that a 200 without an entity tag cannot happen.
  - `grep -rn "proxy" web/src --include=*.ts --include=*.tsx -l` shows whether another landed change already reads the proxy state in the web (reuse its type, do not add a second one).

  Verify: the written list names, for each of the three rows of the design's table, the real field or route; `openspec validate clip-preview-proxy --strict` passes on the re-based delta.

## 2. web/ — the copy's address and probe

- [x] 2.1 In `web/src/api/headers.ts` add `entityVersion(etag)`, moved unchanged from the private `versionOf` in `movie.ts` (which imports it); in `web/src/api/clipMedia.ts` add `proxyUrl(eventId, clip, version)` and `probeProxy(eventId, identity, signal)` (design, Decision 2). The route and query are `satisfies keyof paths` / the generated query type, as `MEDIA_PATH` is. `probeProxy` is `probeFirstByte` on the unversioned address with a reader that requires the `ETag`, and answers `ok` with the tag, `empty`, `problem` or the unanswered kinds. New `web/src/api/clipMedia.test.ts` (`npm test`), with a `fetch` stand-in as `thumbnail.test.ts` does.
  - Cases: the address for an event id with `/` in it and an identity with a space and `#` (each encoded, `v` appended only when given); `W/"abc"` and `"abc"` both give `abc`; a 206 with no `ETag` reads as unpublished; a 404 problem body, a 416 and a rejected fetch map to `problem`, `empty` and `unreachable`; the request is `Range: bytes=0-0` with `cache: 'no-store'`; an aborted request rethrows.
  - `movie.ts` behaves as before: `git diff web/src/api/movie.ts` shows the function removed and the import added, nothing else.

  Verify: `npm test` runs the new file green and the others unchanged; `npx tsc --noEmit` passes in the node:22 container (renaming the route in `schema.d.ts` would fail it).

## 3. web/ — the choice and its words, pure

- [x] 3.1 New pure `web/src/preview/source.ts` (type-only imports): `previewSource(proxy)` (design, Decision 1), the words of the line under the picture (`Playing the preview copy`, `Playing the original`, and the three reasons), `playOriginalName(name)` / `playCopyName(name)` and the announcements, the copy's failure titles (gone, unreadable, empty, cannot play, no answer, each naming the preview copy), the sentence the no-sound note adds when a copy is ready, and `copyLengthMs(facts)` (whole milliseconds, null when unusable). New `source.test.ts` (`npm test`).
  - `previewSource`: ready with a duration of 6.02 gives the copy and 6020; ready with `null`, `0`, a negative, `NaN`, no facts, or no proxy object gives the original with `unusable` or `absent` as the table says; stale and failed give their reasons; an unknown state string gives the original and never the copy; the same input twice gives equal output.
  - The words: every title names `<name>` or "preview copy", the stale / failed / unusable lines match the spec's three reasons, `absent` adds none.

  Verify: `npm test` runs the new file green; `npx tsc --noEmit` passes.
- [x] 3.2 In `web/src/preview/previews.ts` add the operator's override (design, Decision 3): `original(identity)` and `setOriginal(identity, on)`, notified like the other store changes, forgotten by `hide(identity)`, by `hideAll()` and when another clip's preview is shown (as the kept playhead is), and kept across a remount. New `previews.test.ts` (`npm test`; the module has no imports).
  - Cases: default false; set then read; `hide` of that clip clears it, `hide` of another does not; `show` of another clip clears it; `hideAll` clears all; subscribers are called once per real change and not for setting the same value.

  Verify: `npm test` runs the new file green; the doc comment on `ClipPreviews` names the override.

## 4. web/ — the preview

- [x] 4.1 In `web/src/preview/ClipPreview.tsx` choose the file and play the copy (design, Decisions 1 to 6). `CutsPanel.tsx` passes the clip's proxy state in the `clip` prop. The component derives `choice` from `previewSource` and the store's override; for a copy it runs `probeProxy` (keyed on the attempt, aborted by the effect's cleanup) before the source effect sets `video.src`, with the poster and "Loading…" until then. Length is stored under `clipMediaUrl` (the original's address) in both cases: `copyLengthMs` on the copy's `loadedmetadata`, `video.duration` for the original, and `onDurationChange` ignores the copy's. The no-sound note is computed only for the original (with the copy-ready sentence); the copy's failures use `source.ts`'s titles, `changedSince` is applied to the original only, the Download href stays `clipMediaUrl`, and every copy failure gets a Play original action beside Try again that sets the override and reopens the original with focus on its Play.
  - Layout-effect cleanup and `keepPlayhead` stay as they are; a clip with no ready copy takes exactly the v1 path (`git diff` shows its branch unchanged).

  Verify: `npx tsc --noEmit` and `npm run build` pass in the node:22 container; with a copy built by `auto-reel proxies` for the dev library on `PORT`, a Chrome Playwright script in `$SCRATCH` opens the preview of a ready clip and records exactly one `Range: bytes=0-0` request to `…/proxy` then the element's range requests to `…/proxy?…&v=<tag>`, and none to `…/media`; for a clip with no copy it records none to `…/proxy`.
- [x] 4.2 The control and the line, in `ClipPreview.tsx` and `preview.css`: the `<p class="preview-source">` under the transport, and the Play original / Play preview copy button as the last control after Set To (design, Decision 7), `btn btn-ghost btn-compact`, with the same 44 × 44 touch area as its neighbours on a coarse pointer. A press sets the override, sets `pendingPlay` when playing, resets `phase` and the notes, announces through `onAnnounce`, and keeps focus on the button (the element is not remounted). No new colour: the house tokens, in both schemes, nothing animated.

  Verify: `npx tsc --noEmit` and `npm run build` pass; `grep -n "preview-source" web/src/preview/preview.css` finds the rule and the stylesheet has no new custom property; the Chrome script of 4.1 presses the control twice and sees the source flip both ways with the playhead kept.

## 5. Playwright in a real browser (scratchpad only, never in the repo)

- [x] 5.1 Function, against a dev library built from copies of the `auto-reel-media` samples (never symlinks for the clips that are made stale or failed; `XDG_CACHE_HOME` under `$SCRATCH`; copies built with `auto-reel proxies`; the service on `PORT` and `DB`), in Chrome 154 (`localhost/playback-research:chrome`) and Firefox ≥ 155 (`localhost/pcm-audio-research:pw163`: print `browser.version` first and stop if it is below 155). Routes only on `**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel`, `**/reel?*`; sound is measured by tapping the element with WebAudio into an analyser on a pulse null sink, as the PCM research did (peak over 3 s of playback).
  - **Sound.** `sony-xavc-1080p25-pcm.mp4` and `sony-xavc-4k25-pcm.mp4` with a ready copy: decoded peak above 0 in both browsers, "Playing the preview copy", no no-sound note. After Play original: Chrome peak above 0; Firefox peak 0 and the note, which names Play preview copy.
  - **Time.** Seek the copy to 2.5 s, Set From writes `0:02.5`; Play original, seek to 2.5 s, Set From writes `0:02.5`. Press Play original while playing and while paused at 2.5 s: the playhead after the swap is within one frame of 2.5 s, playing stays playing, paused stays paused, focus stays on the control, the live region says what plays. Repeat on `h264-1080p50-aac.mp4` and on the rotated `h264-720p-rotate90-aac.mp4`; a difference beyond one frame fails the task (design, Risks).
  - **Length.** With a clip whose copy's browser length is shorter than its facts' duration (measure the dev library's copies; the Sony clip's is enough if none is), a cut ending at the facts' duration is accepted and "This clip ends at" shows the facts' value.
  - **Not ready.** A clip with no copy, one made stale by editing its scratch copy after the build, and one whose build failed (a truncated copy of a sample): the original plays, the line says why, no Play original control, no request to `…/proxy`.
  - **Gone.** Delete a built copy from the cache after the page read the event, then open its preview: the note says the preview copy is no longer there, offers Play original, the page makes no request to `…/media` until it is pressed, and then the original is ready with focus on Play.
  - **Edit-mode rules.** No video element and no media or proxy request before a preview opens; one video at a time; Escape closes and returns focus; moving a clip with Play original chosen keeps it paused at the same time with the override kept, and closing then reopening plays the copy; the keyboard order ends with the new control.
  - **Speed.** Time from the Watch press to the first presented frame of the copy (probe included), 5 runs per browser, reported. Above 250 ms local is reported to the supervisor with the probe's share (design, Risks).

  Verify: the script exits 0 for each browser; each assertion above is in its output; the results are saved to `$SCRATCH`.
- [x] 5.2 Look at the result: light and dark at 1280 and 390 wide with a ready copy and with none: the line, the control, the note and the failure note. Screenshots to `$SCRATCH`, each opened and looked at. At 320 and 390 the page does not scroll horizontally (`scrollWidth <= innerWidth`); with a coarse pointer the control's tap area is at least 44 × 44 and reaches no other control; the stage's box is the same size before and after the copy loads.

  Verify: eight screenshots opened and described in the result; the three measurements are printed.

## 6. Docs and gates

- [x] 6.1 Docs. `web/README.md`: in the Edit-mode paragraph that describes the preview, say that it plays the preview copy when one is ready (with sound in Firefox) and the original otherwise, name Play original, and state the support matrix (sound from Sony PCM clips: the copy everywhere; the original in Chrome and WebKit, silent in Firefox); add `source.ts`, `source.test.ts`, `previews.test.ts` and `clipMedia.test.ts` to the file tree. `docs/high-level-design.md`: amend **D-16** with a dated paragraph (2026-10-03, change `clip-preview-proxy`) covering what plays, the length rule (Decision 4), Play original, and that "What stays v2" no longer lists Firefox's silent preview for a clip with a copy; in §4.10 v2 add that the clip preview plays the copy (first user-visible Firefox fix); in §6 phase 9 note the change. Refer to the proxy contract as **D-21** and the timeline as **D-20**; do not create either entry (`proxy-encode` and `timeline-model` record them): if the HLD has no D-21 when this lands, write "the proxy contract (change `proxy-encode`)" and add the number later.
  - No other decision is edited; D-15 (entity tag as `v`) is cited, not changed.

  Verify: `git diff --stat` for this task shows only `web/README.md` and `docs/high-level-design.md`; `grep -n "clip-preview-proxy" docs/high-level-design.md` finds the D-16 paragraph, §4.10 and §6.
- [x] 6.2 Final gates: in the node:22 container `npm ci`, `npx tsc --noEmit`, `npm test` and `npm run build` pass; `git diff --stat -- auto_reel_ng tests web/openapi.json web/src/api/schema.d.ts` is empty (no Python, no API, no schema change, so black, isort, mypy, pylint and pytest are unaffected, `RENDER_GRAPH_VERSION` stays and no fingerprint input is added); `openspec validate clip-preview-proxy --strict` passes.

  Verify: the four npm commands and the validate exit 0 and the diff stat prints nothing.
