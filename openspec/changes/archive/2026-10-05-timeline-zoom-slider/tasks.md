All tasks are in `web/` (plus the HLD). Node runs only in podman (`docker.io/library/node:22`); Playwright runs from the
scratchpad only, in Chrome 154 (`localhost/playback-research:chrome`) and Firefox ≥ 155, light and dark, at 1280 and
390 px, scoped to `main:not([hidden])`, with write routes intercepted; every screenshot is looked at.

## 1. Specs in step with main

- [x] 1.1 Before any code, re-read `origin/main`: if `help-text-declutter`, `timeline-ripple-layout` or `clip-edge-trim`
  has landed, re-copy the current text of every requirement this change MODIFIES that they changed too ("The track lays
  the clips out…", "A card is selected…", any zoom or toolbar text), keeping their behaviour and this change's edits.
  Test: `openspec validate timeline-zoom-slider --strict` passes.

## 2. web/ — Fit and the zoom model

- [x] 2.1 Bug (a), Fit never scrolls (design D5): first measure in Playwright `scrollWidth − clientWidth` of
  `.tl-viewport` at Fit (playhead at start and end; fine and coarse pointer; a 3.0 s black card at its 24 px minimum;
  1280 and 390) and record the numbers in the PR; then add the end gutter (`--tl-end-gutter`, Fit against
  `clientWidth − gutter`, canvas `floor(totalPx) + gutter`) and keep anything else found overflowing inside the canvas.
  Tests: `node:test` for the fitted width never exceeding the view (several lengths and widths, incl. the 4 px/s floor);
  Playwright asserts `scrollWidth == clientWidth` in all of the measured cases, Chrome and Firefox.
- [x] 2.2 Pure zoom helpers in `model.ts` / `labels.ts` (design D1–D3): `SLIDER_STEPS`, `ppsToSlider`, `sliderToPps`,
  `anchorFor(playheadX, width, pointerX?)`, `wheelFactor(deltaY, deltaMode, viewHeight)`, `zoomValueText(pps, fitted)`.
  Tests (`node:test`): round-trip pps → position → pps within one step; position 0 is exactly Fit and `SLIDER_STEPS`
  exactly 240; clamps outside the range; `fit ≥ max` → 0; anchor = playhead when in view, centre when not, pointer
  when given; wheel factor clamped to [1/1.5, 1.5] and normalised for line and page modes; value text "Fit" /
  "40 px per second"; `MAX_PPS` still 240.

## 3. web/ — The zoom controls

- [ ] 3.1 `zoomTo(target, anchorX?)` replaces the body of `zoomBy` (requested scale kept in a ref updated at request time);
  the **Zoom** range input between Zoom out and Zoom in, `aria-valuetext`, disabled when Fit ≥ 240, coalesced to one
  zoom per animation frame; −/+ keep 1.5x and move the slider; reaching position 0 sets Fit (`fitted: true`).
  Tests: Playwright — dragging the slider end to end keeps the playhead within 1 px of its view x and ends at
  "240 px per second"; Zoom in three times moves the slider right; a 3 s event's slider is disabled; with 4x CPU
  throttling on the 400-clip fixture a slider drag keeps ≤ 2 % of frames over 25 ms (Chrome and Firefox), and the scrub
  gates (≥ 30 fps median, frame-step p90 ≤ 60 ms) still hold.
  Status (2026-10-05, after the review): everything above passes in Chrome 154 and Firefox 155 except the Chrome
  4x-throttled drag gate, which stays open for a decision. The review made each zoom frame cheaper (one render per
  zoom, a quarter-view margin while dragging, memoised readout and card layer; design D2). Measured on a quiet host
  (load 2-5), same script, same 180-move drag, 4x: idle 0-0.6 %; the slider thumb alone (zoom switched off in a
  scratch build) 1.4-2.1 %; the zoom before the review 35-41 % (p95 74-96 ms), after it 30-34 % (p95 55-66 ms),
  46-56 % in the full gate script at load 5-7. With the Edit page's 400-row clip list given `content-visibility: auto`
  (injected CSS, not in this change) the same drag is 7.4-7.9 % (p95 30 ms): most of a zoom frame's cost is that
  page's paint and layerize, not the Timeline. Firefox (no throttle) 0 %. Scrub gates hold (Chrome 55.6 fps / step
  p90 25.3 ms; Firefox 47.6 fps / p90 33.5 ms).
- [x] 3.2 Keys and pointer (D3): `\` in the viewport key list and `onTrackKey` (Fit, and back to the zoom before it);
  `keys.ts` returns null for `\` and `=`; `TRACK_KEYS` names `\`; a non-passive `wheel` listener on `.tl-viewport` zooms
  on Ctrl/Meta (and pinch) about the pointer, `preventDefault` only then. Tests: `keys.test.ts`, `labels.test.ts`;
  Playwright — `=`, `-`, `0`, `\` twice (Fit, then back to the earlier scale); Ctrl+wheel keeps the time under the
  pointer within 1 px and leaves `visualViewport.scale` at 1; a plain wheel scrolls without zooming. Review: a pure
  `trackZoomKey` takes `\` typed with AltGr (Ctrl+Alt on Windows, AltGraph on Linux) or Option (macOS), never Ctrl
  alone or Cmd (`keys.test.ts`; Playwright Ctrl+Alt+`\`, Alt+`\`, Ctrl+`-` left to the browser).
- [x] 3.3 Session memory (D4): a `zoomMemory.ts` module (key per event, `{fitted, pps}`, parse/validate, injected
  storage, in-memory mirror, every access in try/catch), restored on mount and re-bounded once the view is measured.
  Tests (`node:test`): corrupt, missing, non-finite and throwing storage → Fit; a stored scale above the max or below
  Fit is clamped; Playwright — zoom to 60 px/s, Save and Refresh keep it, a new browser context opens at Fit.

## 4. web/ — Toolbar and read view

- [x] 4.1 Bug (b), the toolbar holds still (D6): `.tl-controls` as a grid of fixed slots (one row from 64rem,
  two from 31rem, three below, plus the movie stat's row); the clip name ellipsized with its `title`; the inline `.tl-poster-why` removed; Use as poster's reason as
  `title` + `aria-describedby` (visually hidden), shown in an absolutely positioned tip and said once in the Timeline's
  live region when the disabled button is pressed. Tests: Playwright — the bounding boxes of Play, the readout parts,
  every zoom control and Use as poster are equal within 1 px across idle, a seek whose frame is loading (throttled proxy
  route), playing, and the playhead in a black card, at 1280 and 390, light and dark; pressing the button while loading
  shows "The picture is still loading." in the tip and the live region once; no horizontal page scroll at 320.
- [x] 4.2 The read view loses the Timeline (D7): remove `TimelineSection` from `EventDetail.tsx` `ReadyView` (and the
  props only it used); make `editing` / `cardEditing` required in `TimelineSection`, `Timeline`, `Track` and
  `overlays/control.ts` and delete every `editing === null` branch, the Open/Close toggle, `sectionOpen`, the card
  inspector slot (keep its status region), `.tl-toggle` / `.tl-inspector*` CSS and the strings; delete or rewrite the
  tests that covered only the read view (`sectionOpen` in `layout.test.ts`, the read branch of `analysisOf`). Tests:
  `npm test` and `npx tsc --noEmit` pass; Playwright — the read view of an event with ready proxies has no "Timeline"
  heading, no Open timeline button, no title card line, no Timeline `<video>`, and no request to a proxy, filmstrip,
  analysis or proxy-job address; the clip ▶ overlays, Movie section and poster still work; Edit shows the Timeline open,
  leaving Edit mode shows none.

## 5. Docs and gates

- [x] 5.1 HLD (`docs/high-level-design.md`): amend D-20 (the zoom slider, `\`, Ctrl/Cmd+wheel and pinch at the pointer,
  the per-tab session memory, MAX_PPS kept at 240 with the numbers from design.md, Fit's end gutter, the Timeline only in
  Edit mode — superseding "the read view keeps its button"); a §4.10 bullet and a §6 phase-8 note naming
  `timeline-zoom-slider`. Test: a `docs.test.ts` case asserting `timeline-zoom-slider` is named in D-20, §4.10 and §6.
- [ ] 5.2 Gates: `npm test`, `npx tsc --noEmit` and `npm run build` in podman; the full Playwright run of 2.1, 3.1–3.3,
  4.1 and 4.2 in Chrome 154 and Firefox ≥ 155, light and dark, at 1280 and 390 px, screenshots looked at; no request
  other than reads during any zoom.
  Status (2026-10-05): all of it passes except 3.1's Chrome 4x slider-drag frame gate; this stays open with 3.1.
