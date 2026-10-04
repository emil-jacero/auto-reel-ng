## Why

The user asked (2026-10-04, verbatim): "Ability edit the clip length, like trimming away the begining or end of a
clip, in the timeline. I want to be able to do it graphically, by hovering over the left or right edge of the clip in
the timeline, a tool should show indicating that you are about to trim. Just like in Adobe Premiere." They chose
"Shorten + ripple": the trimmed start or end disappears, the block gets shorter and later clips slide left, and
dragging the edge back out restores it, up to the file's limit (red edge at the limit).

Today a clip's start or end can only be trimmed by typing a cut `0..x` or `x..end` in its Cuts panel, or by approving
a black/white/freeze suggestion and then dragging that cut's handle. A clip's own edge has no affordance at all
(research `trim/code-model.md` §2–§3: "Clip edges have NO affordance today"). The gate change
`timeline-ripple-layout` makes the Timeline lay each clip out over its kept extent only (leading and trailing removed
spans vanish, later clips slide left) and drops the handles of those spans; this change adds the tool that edits them.

## What Changes

- In **Edit mode**, the outer edge zones of every clip block on the Timeline become **Trim In** (left) and **Trim
  Out** (right) tools: a bracket-shaped trim cursor (CSS `cursor: url(data:…)` with the `ew-resize` fallback) and a
  visible bracket on the edge, so the affordance shows without a cursor (touch).
- **Dragging an edge is a ripple trim**: inward trims the clip's start or end, outward restores it, up to the file's
  limit. The block shortens/lengthens and everything after it slides **live during the drag**; a tooltip shows the
  signed change and the clip's new playing length; at the file's limit the edge turns red and says "Start of the
  file" / "End of the file". Snaps within 8 px to the playhead, the clip's interior cut edges and whole seconds; `S`
  switches edge snapping off/on (announced), Alt held bypasses it.
- The edit is the clip's **leading / trailing cut** in `trims` — no new field: created (reason `manual`) when none
  exists, extended or shortened when one does, removed when dragged back to the file's limit; **one draft edit per
  release**, saved by the existing Save, put back by Reset. A drag that reaches an interior cut **joins** it (the
  render's union rule) and says so; a clip always keeps at least three frames.
- **Keyboard and non-drag alternatives** (WCAG 2.5.7): each edge is a focusable slider (arrows 1 frame, Shift 1 s,
  Home/End the limits); `Q` trims the start of the clip under the playhead to the playhead and `W` its end
  (Premiere's keys), announced politely; a pressed edge selects its edge cut in the existing typed fields.
- Edge tools are inert while a save or a Move clips is pending, absent on clips drawn too narrow to show detail and
  absent outside Edit mode; windowing and the drag-smoothness gate hold.
- No engine, schema, API, fingerprint or `RENDER_GRAPH_VERSION` change: an edge trim is an ordinary `trims` entry
  that already renders (`render/segments.py kept_spans`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `timeline`: ADDED — the pure model of an edge trim: which cut is a clip's edge, its limits (file limit, cuts held
  by other cuts, three played frames), snapping and joining, and the one edit a release makes.
- `event-timeline`: ADDED — Edit mode's Trim In / Trim Out tools: hover cursor and bracket, ripple drag with live
  layout, tooltip and red limit, keyboard sliders, `Q`/`W`, snapping switch, typed alternative, locked/narrow/read-view
  rules, and the gates.

## Impact

- Web only (`web/`), one package. New `web/src/timeline/edgeTrim.ts` (pure, `node:test`), `EdgeHandles.tsx`,
  `timeline.css`; touched `Track.tsx`, `Timeline.tsx`, `TrimHandle.tsx` (press hand-over), `dragStore.ts`, `keys.ts`,
  `editing.ts` (`EditBinding`), `edit/draft.ts` + `edit/EventEditor.tsx` (one reducer action applying the edge edit).
- No new dependency (D-8, D-20); Playwright from the scratchpad in Chrome 154 and Firefox ≥ 155.
- Builds on `timeline-ripple-layout` (kept-extent layout); compatible with `timeline-zoom-slider` (which also removes
  the Timeline from the read view, so the "not in the read view" rule here is then trivially true) and
  `help-text-declutter` (key hints live behind its Help toggle).
- HLD: D-20 amendment and §4.10 / §6 notes.
