## Context

D-20 (the plan's number; the research calls it D-18, which the bug round took): the v2 timeline is built in
the repo, on React and plain CSS, in `web/src/timeline/`, generalising D-16's cut bar. This change is its first
slice and has no UI. It lands the pure model the later components call, so that the rules that carry the bugs
are unit-tested before a pointer event exists.

State of the client on main (8fb4d16): `npm test` runs `node --test --experimental-strip-types
"src/**/*.test.ts"`, `tsconfig.test.json` type-checks the tests, `npm run build` runs `tsc` on both first.
`src/cuts/times.ts` and `src/preview/playback.ts` already hold the cut rules in whole milliseconds
(`checkCut`, `skipSpans`, `toMs`). `playback.ts` has no test and imports `../cuts/times` without the `.ts`
extension, which Node's type stripping cannot resolve (`times.test.ts` writes the extension).

## Research & Decisions

### Build own, no library
**Context**: D-8 lets in only React, Vite, TypeScript and the dnd-kit trio, "each addition justified by the
slice that demonstrably needs it".
**Explored**: `research/v2/timeline-library.md` §2.1 (nine libraries: none models source-clip cuts; the three
run in a browser exposed no keyboard path; `@xzdarcy/react-timeline-editor` costs +68.5 KB gz), §2.2 (the
prototype: 780 TS lines, +5.6 KB gz JS, 22/22 functional checks in Chrome 154, Firefox and WebKit, 60 fps drag
and scrub to 400 clips at 4x CPU throttle), §4 (recommendation).
**Decision**: build in the repo; no timeline library; `@dnd-kit` stays for reorder only (it has no value
semantics and re-renders every consumer per move: 283 dropped frames at 400 clips, 4x).
**Rationale**: the pointer maths a library saves was about 110 lines; the keyboard and touch layer is the
costly half and no library has it. This change adds no dependency, so D-8's list is untouched.

### The model works in whole milliseconds, not float seconds
**Context**: the prototype used float seconds and `frameRound = Math.round(t * 25) / 25`. v1 writes cut times
to the millisecond (`parseTime` refuses a fourth decimal) and `playback.ts` documents that a frame at 0.96 s
plus a 0.04 s step falls short of a cut at 1 s in floating point.
**Decision**: every time the model takes or returns is an integer number of milliseconds (`Ms`); pixels and
pixels-per-second are plain floats. A frame time is `Math.round(n * 1000 / fps)`, so at 29.97 fps frame 1 is
33 ms, not 33.3667. Seconds appear only at the edge: `clipFacts(durationSeconds, fps)` converts once, and a
caller writes `ms / 1000` into a cut (`parseTime`'s documented nearest-double rule).
**Rationale**: whatever the model returns, the Cuts panel can print and read back unchanged ("Times are
written one way on every screen", D-14). A drag at 29.97 fps cannot produce a time the panel would refuse as
too precise.

### Facts are arguments, with no default
**Context**: the prototype has `FPS = 25`. The events read is probe-free (HLD §4.9), so the API has no
duration or fps (synthesis X6). They will come from a proxy's `facts.json` (D-21, the proxy changes), which
the timeline needs anyway: it opens only for an event whose proxies are prepared.
**Decision**: `ClipFacts = { durationMs, fps }`, built by `clipFacts(seconds, fps)`, which throws `ModelError`
for a duration or rate that is not a finite number above zero. No function has a default rate or duration.
**Rationale**: Principle I (never fabricate metadata). A guessed 25 fps would round every 29.97 or 50 fps
clip's cuts to frames the clip does not have. Variable frame rate is not modelled: a clip is rounded to its
nominal rate and the view decides what to do with the VFR flag (research risk 11, "not yet sized").

### Reuse how the render joins cuts
**Decision**: the model's cut spans are `skipSpans` from `preview/playback.ts` (clamp to the clip, drop empty,
sort, merge overlapping or touching), not a second implementation. `playback.ts` gets `.ts` on its two imports
so the model's tests can load it. A task test imports the module so a later edit that breaks the Node
resolution fails here.
**Rationale**: the render's merge (`kept_spans`) has one client-side twin already; a second would drift.
Individual cuts are still addressed by their position in the clip's list (`reel.yaml` cuts have no id), and
the spans are only for lengths and drawing joins.

## Decisions

### Public surface (all in `web/src/timeline/model.ts`)

```ts
export type Ms = number                                    // whole milliseconds
export type ClipFacts = { durationMs: Ms; fps: number }
export class ModelError extends Error {}
export function clipFacts(durationSeconds: number, fps: number): ClipFacts

// frames
export function frameMs(index: number, fps: number): Ms      // Math.round(index * 1000 / fps)
export function nearestFrame(ms: Ms, fps: number): Ms        // the frame time nearest ms
export function minCutMs(fps: number): Ms                    // frameMs(3, fps)

// layout and px
export const MIN_PPS = 4, MAX_PPS = 240, DEFAULT_PPS = 40, SNAP_PX = 8
export type Layout = { startsMs: readonly Ms[]; totalMs: Ms }
export function layout(clips: readonly ClipFacts[]): Layout
export function clipAt(l: Layout, t: Ms): number | null      // later clip at a boundary
export function timeToPx(ms: Ms, pps: number): number
export function pxToTime(px: number, pps: number): Ms        // rounded to the ms, not clamped

// zoom
export type View = { pps: number; scrollLeft: number; width: number }
export function clampPps(pps: number): number
export function zoomAt(v: View, factor: number, anchorX: number, totalMs: Ms): View
export function fitPps(totalMs: Ms, viewWidth: number): number
export function tickStepMs(pps: number): Ms

// windowing
export function visibleClips(l: Layout, v: View, overscanPx: number): [number, number] | null
export function visibleTicks(l: Layout, v: View, overscanPx: number): { stepMs: Ms; first: number; last: number }

// cuts
export function cutSpans(cuts: readonly ListedCut[], durationMs: Ms): Skip[]    // = skipSpans
export function movieLengthMs(clips: readonly (ClipFacts & { cuts: readonly ListedCut[] })[]): Ms
export function cutRects(cuts, durationMs, pps): { index: number; left: number; width: number }[]
export function cutOrdinals(cuts: readonly ListedCut[]): (number | null)[]       // null = removed

// trim and snap
export function trimLimits(cuts, index, edge: 'in' | 'out', f: ClipFacts): [Ms, Ms]
export function snapTo(ms: Ms, candidates: readonly Ms[], pps: number): { ms: Ms; target: Ms | null }
export function snapCandidates(cuts, index, f: ClipFacts, playheadMs: Ms | null, extra: readonly Ms[]): Ms[]
export function trimEdge(cuts, index, edge, wantedMs: Ms, f: ClipFacts, pps: number, candidates: readonly Ms[]):
  { ms: Ms; snappedTo: Ms | null }
```

`ListedCut` is `cuts/times.ts`'s `{ in, out, removed? }` in seconds, as every client screen holds cuts; the model
converts with `toMs` (`playback.ts`) on the way in, so a caller passes the panel's list as it is.

### Layout and lookup
`layout` lays clips end to end by `durationMs` (the proxy's own length, so a timeline's seconds are the
proxy's seconds). `clipAt` is a binary search over the starts (prototype: 8 lines): `t < 0` gives clip 0,
`t >= totalMs` the last clip, a boundary the later clip, no clips `null`. The Prepared-only rule means a
layout is never built from a guess.

### Zoom
`pps` is clamped to `[4, 240]` (the prototype's range, which held at 400 clips). `zoomAt` keeps the moment
under `anchorX` where it is (`t = (scrollLeft + x) / pps` before, the same `t` after) and clamps `scrollLeft`
to `[0, max(0, totalPx - width)]`. `fitPps` fits the whole length, clamped, and gives `DEFAULT_PPS` for a
zero length. `tickStepMs` is the first of `0.5, 1, 2, 5, 10, 30, 60, 300, 600` seconds whose spacing is at
least 70 px, else 600 s.

### Windowing
The prototype windowed with a filter over all clips: 112 DOM nodes at 80 or 400 clips versus 6,889 unwindowed
(§2.2). The model returns the index range instead, found by two binary searches, so the cost no longer grows
with the clip count. A range includes clips that touch `[scrollLeft - overscan, scrollLeft + width +
overscan]`; ticks are returned as an index range at the current step so the view renders only those.

### Trim limits
For a cut `i` and an edge, the *neighbours* are the other cuts, not removed, that do not overlap cut `i`
(touching is not overlap, as in `checkCut`). The range is:

| edge | lowest | highest |
|---|---|---|
| in | the largest `out` of a neighbour that ends at or before this cut's start, else 0 | `out - minCutMs`, but never below the current `in` |
| out | `in + minCutMs`, but never above the current `out` | the smallest `in` of a neighbour that starts at or after this cut's end, else `durationMs` |

The "never below the current" clause makes the range always contain the current value: a 50 ms cut that was
typed in v1 (shorter than three frames) is not pulled to 100 ms by looking at it, and a pair of overlapping
cuts read from disk (the render joins them) never gives an inverted range. A clip shorter than three frames
gives a collapsed range. Where the edge a minimum is measured from lies on a frame, the limit is itself a
frame time (`frameMs(k - 3)`, not `edge - 100`), so Home and End reach a time the clip can show. That is the
prototype's first bug.

### Snapping and `trimEdge`
`snapTo` takes the candidate nearest `ms` within `SNAP_PX / pps` seconds; two equally near candidates give
the earlier one (the result no longer depends on array order); none gives `target: null`. `snapCandidates`
returns the sorted, de-duplicated list of the clip's start and end, every other cut's edges, the playhead's
time inside this clip when it is inside, and the caller's extra points (analysis suggestions, later). `trimEdge`
runs: snap if a candidate is near, else `nearestFrame`; then clamp to `trimLimits`. `snappedTo` is set only
when the clamped result equals the candidate, so a snap line is never drawn at a place the handle did not
reach. A clamp returns the limit exactly (a neighbour's typed edge is a legal place to touch).

### Cut spans, rectangles, names
`cutRects` returns one rectangle per listed cut that is not removed, with its index in the caller's list, for
the cut's pixels clamped to `[0, durationMs]`: a cut that runs past the end is drawn up to the end (D-16's
bar); one wholly past it, or empty, has no rectangle. `cutOrdinals` numbers non-removed cuts 1..n by start
(ties by end, then position) and returns `null` for removed ones, so two cuts of one clip never share a name
"cut n start" (the prototype's second defect, found by `aria_snapshot`).

### What the prototype's third defect is not
The research lists a touch-swipe moving the playhead (a gesture decision in `Timeline.tsx`) as a second
"defect found by testing". It is pointer handling with no model content, so it is `timeline-view`'s to
reproduce and test in a browser; this change's second named case is the identical-names one.

### Failure behaviour
`clipFacts`, `layout` (through its inputs), and every function taking `fps`, `pps` or a view width throws
`ModelError` on a non-finite or non-positive value; there is no clamping to a default. `trimEdge` with an
index outside the list throws. Nothing here retries, logs or touches the DOM, the network or a file. The
model is a pure function of its arguments, so idempotency questions reduce to: the same arguments give the
same result, and `trimEdge(.., trimEdge(..).ms ..)` is a fixed point.

### Bundle and dependencies
No module imports the model, so `vite build` drops it: the production bundle delta is expected to be 0 bytes.
The task measures it (`dist/assets/*.js` gzip sizes before and after) rather than assuming. A test reads
`web/package.json` and asserts `dependencies` still lists exactly React, React DOM and the dnd-kit trio.

## Risks / Trade-offs

- Ms rounding costs up to 0.5 ms against the frame's true time. Chrome and Firefox read a clip's length up to
  60 ms apart (D-16), so a half millisecond is below what the browser resolves.
- Reusing `skipSpans` couples `timeline/` to `preview/`. Acceptable: `preview/playback.ts` is pure, the
  timeline generalises D-16, and one place decides how the render joins cuts.
- The model's rules are verified by node tests here and by a real browser only when `timeline-view` wires
  them. This change's own browser check is a regression smoke (the existing screens still load), since no
  new surface exists.
- Unsized, as the research says (§6 risk 11): undo, edge auto-scroll, VFR frame snapping, multi-select. None
  is in this model; each lands with the change that needs it.

## Migration Plan

Additive. No data, schema or API change; nothing to roll back beyond deleting the directory.

## Open Questions

None blocking. Whether the model grows `add`/`remove`/`decide` reducers is for the trim and overlay changes,
which know what the panel's list and `If-Match` write path need.
