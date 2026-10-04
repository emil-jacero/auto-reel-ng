## 1. Pure model

- [x] 1.1 `model.ts`: add `keptExtent` (design D1, reusing `cutSpans` and `toEnd`), interior spans, a `layout()` that lays
  kept extents (zero length for an empty one, ties to the later clip in `clipAt`/`visibleClips`), and the
  `clipToLayout`/`layoutToClip` pair. Test in `model.test.ts`: every scenario of "Clips are laid out end to end from their
  durations and found by time" and the extent, trailing-slack and round-trip scenarios of "A clip's edge cuts set its
  kept extent" (leading + interior + trailing on one event, a wholly cut first/middle/last clip, the existing cases
  still pass).
- [ ] 1.2 `position.ts` (and `play.ts` `positionOnTrack`/`stepFramesOnTrack`/`stagesOf`): first and last kept frame,
  `positionAt`, `stepFrames`, `clampPosition`, `startPosition`/`endPosition`, `globalMs` through the extent; a clip with no
  kept frame is passed over. Test in `position.test.ts` and `play.test.ts`: the positions, steps, few-frames and
  no-kept-frame scenarios, a black card before a start-trimmed clip, and the existing cases unchanged.
- [ ] 1.3 `layout.ts` and `cards.ts`: `TrackClip` carries its extent and interior `drawn` spans; `trackLayout` uses the
  extent; a separate `footageMs` (full durations) for the movie line; `filmTiles` starts at `inMs`; `cardPlacements`/
  `firstKept` and `handOverMs` call the extent; `cardBlocks` puts a video card at the block's left edge; which listed
  cuts lie within an edge cut. Test in `layout.test.ts` and `cards.test.ts`: the filmstrip and card scenarios of "A clip's
  edge cuts set its kept extent", the "Edge cuts shorten the blocks" numbers, and the existing card scenarios.

## 2. The view

- [ ] 2.1 `Track.tsx`, `Filmstrip.tsx`, `TrimHandle.tsx`, `Playhead.tsx`, `CardLane`/chapter band: blocks, interior cut
  spans, handles (none for an edge cut), the playhead x and scrub, and chapter bands through the helpers; the block label
  shows the kept length; `labels.ts` `clipDescription` says the kept length of the full one. Test with `node:test` for the
  label and value-text strings (`labels.test.ts`, `readout.test.ts`: "Clip 0:05.00 of 0:10.00 · Event 0:03.00 of 0:19.00")
  and in task 3.1 for the drawing.
- [ ] 2.2 `overlays/useSuggestions.tsx` and `SuggestionLane.tsx`: marks and the "Not analyzed" note mapped through the
  extent, clipped, a mark wholly inside an edge cut not drawn. Test in `overlays/suggestions.test.ts` (or a new pure
  placement test): the "A suggestion inside a leading cut" scenario and the existing stacking cases.
- [ ] 2.3 `Timeline.tsx`: the clips-read-again effect clamps the playhead to the nearest kept frame; the selection ends
  when its cut becomes an edge cut; Fit, zoom anchoring and the playhead scroll use the rippled layout; the movie line
  uses `footageMs`. Test with `node:test` for any pure helper extracted, and verify by `grep -n "startsMs\[\|facts.durationMs"
  web/src/timeline --include=*.tsx` that no remaining use draws a width or an x without the extent (each left one is
  justified in a comment). `npm test`, `npx tsc --noEmit` and `npm run build` pass (node:22 in podman).

## 3. Browser verification

- [ ] 3.1 Playwright from `$SCRATCH` (never in the repo) in Chrome 154 (`localhost/playback-research:chrome`) and Firefox
  ≥ 155 (`localhost/pcm-audio-research:pw163`), Edit mode, on a dev library event with a start-trimmed and an
  end-trimmed clip (writes routed only as the brief says): blocks shortened with no gap (block rects abut within 1 px),
  no hatched span on the edge cuts, the filmstrip's first tile at each block edge is the tile of the kept start, a press
  into each trimmed clip gives the expected playhead and readout, Right/Left/Home/End land on kept frames, Play across
  the boundary never presents a frame of the trimmed part (sampled `currentTime` stays inside the extents), Fit fits the
  rippled length, an interior handle released at 0 shortens the block; light and dark at 1280 and 390; screenshots
  looked at. Fails if any of these is not seen.

## 4. Docs

- [ ] 4.1 Update the HLD: §4.10 (a `timeline-ripple-layout` note: edge cuts ripple, kept extent with Play's 0.1 s
  rule, clip time unchanged, the < 0.1 s total-vs-movie difference, edge handles until `clip-edge-trim`), §6 (phase-8
  status line), and D-20 (a bullet: the layout is by kept extent; "a trimmed clip is as wide as its proxy" no longer
  holds). Verify with a `grep` that no HLD text says a leading cut is drawn hatched on the Timeline, and that
  `openspec validate timeline-ripple-layout --strict` passes.
