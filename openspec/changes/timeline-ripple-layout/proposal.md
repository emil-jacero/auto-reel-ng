## Why

The operator asked for Premiere-style trimming of a clip's start and end on the Timeline, and chose **Shorten +
ripple** (AskUserQuestion, 2026-10-04): "the trimmed start/end disappears, the clip block gets shorter and later
clips slide left, so the Timeline shows the movie as it will play". Today every clip is laid out at its full proxy
duration and a cut at its start or end is a hatched span over the block (`web/src/timeline/model.ts` `layout()`,
`layout.ts` `trackClips`/`drawnCuts`, research `trim/code-model.md` §3), so a trimmed start still takes room and the
Timeline shows footage the movie does not play. This change is the first of the trim swarm: it makes the layout
ripple for **edge** cuts; `clip-edge-trim` adds the hover/drag edge tool on top of it, and `timeline-zoom-slider` the
slider and the toolbar fixes.

No engine, schema or API change is needed: a start trim is already a cut `[0, x]` and an end trim a cut `[x, duration]`
in `ClipProperties.trims`, and the render's `kept_spans` already drops them (`render/segments.py:157-185`, research
`trim/code-model.md` §1).

## What Changes

- The pure model derives each clip's **kept extent** `[in, out)` from its joined cut spans: `in` is the end of a
  leading cut (a joined span from 0), `out` the start of a trailing cut (a joined span that runs to the clip's end or
  within 0.1 s of it, the rule Play already uses, `preview/playback.ts` `toEnd`). Only the spans between are interior
  cuts.
- Clips are laid out end to end by their kept extents (no gaps); a wholly cut clip takes no length and has no
  block. Leading and trailing cuts are no longer drawn, and their trim handles disappear (the cut stays in the
  clip's Cuts panel; the edge tool in `clip-edge-trim` gives them a handle back). Interior cuts stay hatched with
  their handles, as today.
- Every time-to-x mapping goes through the extent: ruler and ticks, the playhead (press, scrub, grip), Home/End and
  frame steps (they land on kept frames only and pass over a clip with none), the filmstrip (tiles start at the kept
  in-point), interior cut spans and their handles, the analysis marks (clipped to the extent), the title-card blocks
  (a black card sits right before the block, a video card at its left edge), the chapter band, Fit and windowing.
- The readout keeps the clip's own time and full length ("Clip 0:05.00 of 0:25.00"); the Event time is the
  rippled track time. The block's label says the kept length. The movie line's "of footage" stays the full source
  length.
- When cuts change under the playhead so its time is no longer kept, it moves to the nearest kept frame of the same
  clip.
- Play is unchanged in rule (D-16, `follow.ts`): it starts a clip at its first kept frame and ends it at a trailing
  cut, now consistent with what the track draws. Use as poster is unchanged.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `timeline`: clips are laid out by their kept extents; a new requirement for the kept extent and the mapping of
  clip time, positions, frame steps, filmstrip tiles and card anchors through it.
- `event-timeline`: the track draws blocks by kept extent and no leading/trailing cut spans; leading and trailing
  cuts have no trim handle; a title card sits at the first kept frame; a new requirement for the rippled Timeline
  (playhead, readouts, keys, Play, filmstrip, marks, Fit).

## Impact

- Web only (`packages: web`): `web/src/timeline/` (`model.ts`, `layout.ts`, `position.ts`, `cards.ts`, `play.ts`,
  `readout.ts`, `labels.ts`, `Track.tsx`, `Filmstrip.tsx`, `TrimHandle.tsx`, `Playhead.tsx`, `Timeline.tsx`,
  `overlays/useSuggestions.tsx`, `overlays/SuggestionLane.tsx`) and their `node:test` files. No new dependency.
- No engine, `reel.yaml` schema, API, staleness or `RENDER_GRAPH_VERSION` change; nothing written differs.
- HLD: §4.10 note, §6 phase-8 status, D-20 bullet.
- Interplay: `clip-edge-trim` gates on this change. `timeline-zoom-slider` removes the read-view Timeline (user,
  2026-10-04) and touches the toolbar; this change adds no read-view-only behaviour and no toolbar control.
