## 1. Pure model (timeline)

- [x] 1.1 Rebase on the merged gate `timeline-ripple-layout`: read its `model.ts`/`layout.ts` kept-extent functions
  and its spec deltas, then add `web/src/timeline/edgeTrim.ts` (pure, no DOM/React): edge places and edge cuts
  reusing the gate's kept-extent function (no second layout), `edgeLimits` (other-cut lowest place, three played
  frames, range holds the current place), `edgeAt` (snap to playhead / interior cut edges / whole seconds within
  8 px or nearest frame, snapping-off flag, join reporting, change and played length) and `edgeEdit` (add / trim /
  remove / none, reasons and keys kept). Verify with `web/src/timeline/edgeTrim.test.ts` under `npm test` covering
  every scenario of the `timeline` delta (start/end, cut past the end, two cuts at the start, join and un-join,
  6.5 s → 5.92 s (the gate's 100 ms end rule; three frames would be 5.96 s), black reason kept, back to 0 removes, bad duration → `ModelError`).
- [x] 1.2 Add the key logic: `edgeKey` (Left/Right frame, Shift 1 s, Home/End limits) and `trimToPlayhead` for `Q`/`W`
  (clip under the playhead, card refusal, no-op words, playhead place after), and make `keys.ts` `playheadKey` and the
  track key handler return null for `q`, `w`, `s`. Verify with new cases in `edgeTrim.test.ts` and `keys.test.ts`.

## 2. Draft and drag state (web/edit, web/timeline)

- [x] 2.1 Add one reducer action `cut-edge` in `edit/EventEditor.tsx` applying an `edgeEdit` through `addCut` /
  `trimCut` / `removeCut` (key `a<nextCut+1>`, reason `manual`), and `EditBinding.onEdge(identity, edit, note)` in
  `timeline/editing.ts`, ignored while `locked`. Verify with `edit/edgeEdit.test.ts` (node:test): one release = one
  draft change, reverse edit leaves no dirty draft (`settled`), read cut removed then restored by the Cuts panel Undo,
  `cutChanges` counts, approved `black` cut keeps its reason.
- [x] 2.2 Extend `dragStore.ts` with an edge drag (`EdgeDragging`: identity, edge, place, change, joined, snappedTo,
  words) sharing the one-drag `claim`, and drive the live ripple through the existing `ShiftFrom` transform (ticks,
  chapter band, card lane follow). Verify with `dragStore.test.ts` cases (claim exclusivity against trim and card
  drags, cancel restores, subscribers notified per move).

## 3. Components (web/timeline)

- [x] 3.1 Add `EdgeHandles.tsx` + `timeline.css`: zones inside the block (8 / 24 px, ≤ a third of the block),
  bracket SVG cursors (32×32 data URI, hotspot, `ew-resize` fallback), visible bracket, slider semantics (names,
  values, value text, `aria-describedby`), pointer lifecycle (capture, 3 px slop, Escape/cancel/lost capture, Alt,
  `touch-action: none`), tip, limit colour and words, snap line, `locked` state, reduced motion, light/dark tokens;
  mount only in Edit mode on detailed, windowed blocks; extend `nearestHandle`/`winnerAt` so edges and interior
  handles share one nearest-wins hit test; a pressed/focused edge selects its edge cut in `CutFields`. Verify with
  `handles.test.ts` cases for the shared hit test, `npx tsc --noEmit` and `npm run build` in the node:22 container.
- [x] 3.2 Wire `Q`, `W` and `S` in `Timeline.tsx`/`Track.tsx` (focus rules, never in fields), the release and key
  announcements through Edit mode's live region, and Tab order (Trim In, cut handles, Trim Out per clip). Verify with
  `npm test`, `tsc` and the Playwright keyboard checks of 4.1.

## 4. Browser verification (scratchpad only)

- [ ] 4.1 Playwright from `$SCRATCH` in Chrome (`localhost/playback-research:chrome`) and Firefox ≥ 155
  (`localhost/pcm-audio-research:pw163`) against the dev service on port 8441 (DB `arel_clip_edge_trim`, library
  `dev-clip-edge-trim`): hover cursor (computed style has `url(` and `ew-resize`) and bracket, boundary hand-over,
  start and end drags with live ripple and tip, join/un-join, red limit + words, restore removes the cut, Escape and
  zero move, Alt and `S`, keyboard sliders, `Q`/`W`, locked during save, no tools outside Edit mode, Save writes the
  expected `trims` to `reel.yaml` (route only the write globs); light/dark at 1280 and 390; screenshots looked at.
- [ ] 4.2 Gates: 400-clip windowing count of edge tools, scripted edge drag on an 80-clip event under 4x throttle in
  Chrome (≤ 2 % frames over 25 ms, median vs idle page recorded), no horizontal page scroll 320–1280 px; record the
  numbers and the gzip bundle size before/after (`npm run build`) in the PR body.

## 5. Docs

- [x] 5.1 Update `docs/high-level-design.md`: amend D-20 (edge tools edit leading/trailing cuts, no new field; one
  edit per release; join by the render's union; three played frames; `Q`/`W`/`S`), add the §4.10 v2 note and the §6
  roadmap note for `clip-edge-trim`. Verify `openspec validate clip-edge-trim --strict` passes and the HLD mentions
  `clip-edge-trim` under D-20, §4.10 and §6.
