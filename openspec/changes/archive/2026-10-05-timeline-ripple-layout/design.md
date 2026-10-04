## Context

See proposal.md for the why. The Timeline (D-20, `web/src/timeline/`) has three time scales today:

- **clip time**: a `Position {clip, ms}` in the clip's own (proxy = source) time; cuts, handles, marks, the seek
  coalescer and `follow.ts` all use it;
- **layout time**: `model.layout()` puts clip *i* at `startsMs[i]`, each `facts.durationMs` long, so
  `globalMs = startsMs[clip] + ms` (`position.ts:70`);
- **track time**: `cards.ts` `trackX`/`clipTimeAt`/`trackLayout` add the black cards' spans to layout time.

Every consumer reads `lay.startsMs[i]` and `clip.facts.durationMs` directly (research `trim/code-model.md` §3, and
`grep startsMs\[ | facts.durationMs` in `web/src/timeline/`: `Track.tsx` blocks, chapter band and handles,
`overlays/useSuggestions.tsx:126`, `SuggestionLane.tsx:102`, `Filmstrip.tsx:51` via `filmTiles`, `cards.ts:264,372`,
`play.ts:51`, `position.ts`, `readout.ts`, `Playhead.tsx`, `Timeline.tsx:317,349,462-489`). The leading/trailing rule
already exists three times: `cards.ts firstKept` and `play.ts handOverMs` (a span with `from <= 0`), and
`preview/playback.ts toEnd` (a span ending less than `END_SLACK_MS` = 100 ms before the length) used by
`follow.ts` to end a clip while playing. Play therefore already never shows a leading or trailing cut; only the
drawing and the playhead's reachable places disagree with it.

## Goals / Non-Goals

**Goals:** one place that defines a clip's kept extent and the clip ↔ layout map; every drawer and every playhead
rule using it; tests of the pure functions with `node:test`; the same visible behaviour in Chrome and Firefox.

**Non-Goals:** any new interaction (the edge hover/drag tool, Q/W keys, a red limit edge: `clip-edge-trim`); the
zoom slider and the toolbar/Fit-scrollbar bugs, and removing the read-view Timeline (`timeline-zoom-slider`); live
re-layout during an interior handle's drag (the layout changes on release, as today); any engine, schema or API
change.

## Decisions

### D1. The kept extent is derived from the joined spans, with Play's rules
**Decision**: a pure `keptExtent(spans, durationMs) → {inMs, outMs}` in `model.ts`, from `cutSpans` (the client twin of
`kept_spans`): `inMs` = `spans[0].to` when `spans[0].from <= 0`, else 0; `outMs` = the last span's `from` when
`toEnd(last, durationMs)`, else `durationMs`; `inMs >= outMs` is empty. Interior spans are the rest.
**Why**: the three existing copies of the rule (`firstKept`, `handOverMs`, `toEnd`) already decide where Play starts
and stops a clip; using them makes the drawing, the playhead and Play agree by construction. `cards.ts firstKept` and
`play.ts handOverMs` become callers of the extent (one rule, not four).
**Alternative**: a strict `to >= durationMs` for the trailing cut, matching the render byte for byte. Rejected: Play
already ends the clip at such a span (`toEnd`, D-16: a browser's reported length can differ from the proxy's by
tens of ms), so the Timeline would draw up to 99 ms the playhead could sit in but Play never shows. The cost is that
the Timeline's total can be up to 0.1 s per clip shorter than the movie stat's Movie (which keeps the render's arithmetic);
see Risks.

### D2. Layout time becomes rippled; clip time stays the one time of the model
**Decision**: `Layout` keeps `startsMs`/`totalMs` and gains the per-clip `inMs` (and `outMs`); `layout()` takes each
clip's extent and lays `outMs - inMs`. Two helpers, `clipToLayout(l, clip, ms) = startsMs[clip] + ms - inMs[clip]` and
its inverse, replace every `startsMs[i] + ms` and every `facts.durationMs` used as a width. `Position` is unchanged
(clip time), so cuts, handles, `trimLimits`, the coalescer, `follow.ts`, suggestions' state and the poster rule do
not change. The card map keeps working on layout time, so `trackX`/`clipTimeAt` need no change; `cardMap` takes the
layout's start (already the block's left edge) and `cardBlocks` places a video card at the block's left edge
(`atMs - inMs` = 0).
**Alternative**: shift clip time itself so that a clip's kept start is 0 (a "rippled clip time"). Rejected: cuts,
`reel.yaml`, the Cuts panel, the trim handles and the suggestions are in source time; a second clip time would need
a conversion at every one of them and is the representation the research warns against (`code-model.md` §4: two
representations of one fact).

### D3. The playhead lives on kept frames
**Decision**: `position.ts` gets `firstKeptFrame`/`lastKeptFrame` (frame grid of the clip's own rate, `frameAtOrAbove(in)`
and the last frame below `out`); `positionAt`, `stepFrames`, `clampPosition`, `startPosition`/`endPosition` and
`stepFramesOnTrack` use them; a clip with no kept frame is skipped (zero width, or an extent that falls between two
frames). The "clips read again" effect in `Timeline.tsx` (today `at.ms > durationMs`) and the selection effect both
clamp to the extent, so a cut added in a Cuts panel, an Approve, a typed time or a handle released at the edge moves
the playhead to the nearest kept frame and ends a selection whose cut became an edge cut.
**Why**: "the Timeline shows the movie as it will play" (user decision) means no reachable place the movie lacks.

### D4. Edge cuts are not drawn and have no handle — until `clip-edge-trim`
**Decision**: `TrackClip.drawn` and `spans` split into interior spans (drawn, relative to `inMs`) and the extent. A
listed cut lying within a leading or trailing joined span gets no `ClipHandles` entry (`cutRects` filters by the
extent). An interior handle may still reach 0 or the clip end (its limits are unchanged, `trimLimits`): on release the
cut becomes an edge cut and the block shortens. This is the documented, temporary loss of an on-Timeline handle for an
edge cut; the Cuts panel (Edit mode's clip rows) keeps it editable by typed times, and `clip-edge-trim` gives every
block edge a handle next.
**Alternative**: keep drawing a slim marker for a hidden edge cut. Rejected: the user asked for the trimmed part to
"disappear", and the next change replaces it with the edge tool.

### D5. Filmstrip, marks and labels
**Decision**: `filmTiles(film, extent, pps, window)`: the place at `x` shows tile `floor((inMs/1000 + x/pps)/interval)`,
held to the sprite's last tile, the clip width being the extent's. `useSuggestions` maps a mark's start/end through
`clipToLayout` and clips it to the extent (dropping a mark wholly outside); the 44 px minimum and stacking are
unchanged. The block label shows the kept length; `clipDescription` says "0:08.00 of 0:10.00 kept, 1 cut" when the
extent is shorter than the clip (unchanged otherwise). The readout and the slider's value text keep "clip <time> of
<full duration>" (the clip's own time, as the cuts are written) and use the rippled track for the event pair. The movie
line's "of footage" uses the sum of full durations (a new `footageMs`), not the rippled `totalMs`.

### D6. Tests
Pure functions get `node:test` cases mirroring the spec scenarios (`model.test.ts`, `layout.test.ts`,
`position.test.ts`, `cards.test.ts`, `play.test.ts`, `readout.test.ts`, `labels.test.ts`, `overlays/suggestions.test.ts`).
The browser check uses Playwright from the scratchpad in Chrome 154 (`localhost/playback-research:chrome`) and Firefox
≥ 155 (`localhost/pcm-audio-research:pw163`) on a dev library with a start-trimmed and an end-trimmed clip.

## Risks / Trade-offs

- [Every drawer must switch to the helpers; one missed `startsMs[i] + ms` draws a mark or handle offset by `inMs`] →
  the helpers are the only exported mapping, a `grep` in task 2.3 for `startsMs\[` and `facts.durationMs` used as a
  width outside `model.ts`/`position.ts` must come back empty or justified, and the Playwright check measures handle,
  mark and card x against the block edge.
- [The track total and the movie stat can differ by < 0.1 s per clip with a trailing cut ending just short of the
  end (D1)] → accepted, the movie stat stays the render's arithmetic; documented in the HLD note.
- [Zero-width clips in the binary searches] → `clipAt`/`visibleClips` resolve ties to the later clip (they do today);
  tests cover a wholly cut first, middle and last clip.
- [`help-text-declutter` was in flight on the Timeline toolbar] → it landed first (2026-10-04): this change was
  re-applied onto it by a new branch and cherry-picks (never `git rebase`), keeps its compact movie stat and passes the
  stat the full footage (`footageMs`) rather than the rippled track total, so an edge cut counts in its `cuts` term.
- [`timeline-zoom-slider` and `clip-edge-trim` edit the same files] → `clip-edge-trim` is gated on this change;
  `timeline-zoom-slider`'s `zoomTo`/Fit read `lay.totalMs`, which is the rippled total after this change, as wanted.

## Migration Plan

None: no stored data changes; a saved event with edge cuts simply draws shorter blocks.
