## Why

GUI v2 builds a timeline editor in the repo (HLD §4.10, §6 phase 9; the plan's D-20, which the research
calls D-18). Its logic (where a clip sits at a zoom, what a drag may do to a cut, what a snap lands on, which
clips are on screen) is the part that carries bugs: the build-own prototype found two by testing
(`research/v2/timeline-library.md` §2.2: `MIN_CUT = 0.1` was not frame-aligned, so Home on a cut handle
returned 0.12 and the limit was unreachable by keyboard; two cuts of one clip got the same accessible name).
The research also showed the prototype's `model.ts` is pure and 146 lines, and that the expensive half of the
feature is the keyboard and WCAG layer built on top of it (§4). D-8 reserves a test runner for "logic worth
unit-testing"; the repo already has one (`npm test`, Node's built-in `node:test`, 16 test files), so this
change adds no runner.

This is the first, UI-free slice: land the model, with its tests, before any component depends on it. Later
changes (`timeline-view`, trim, overlays) only call it.

Three things in the prototype's model cannot be carried over as they are, each a consequence of a v1 or v2
rule:

- It hard-codes 25 fps (`FPS = 25`) and takes durations from a fixture. The API has no clip duration or fps
  (synthesis X6); the facts will come from a proxy's `facts.json`. The model takes both as arguments and
  throws when they are missing (Principle I: never fabricate metadata).
- It works in floating-point seconds. v1 already hit that trap (`web/src/preview/playback.ts`: "a frame at
  0.96 s plus a 0.04 s step falls short of a cut at 1 s") and writes cut times to the millisecond (D-14,
  D-16). The model works in whole milliseconds, so a value it returns is one the Cuts panel reads back.
- It assumes cuts do not overlap. `reel.yaml` may hold overlapping cuts (the render joins them), so its
  neighbour limits could invert on a file read from disk.

## What Changes

- New `web/src/timeline/model.ts`: pure TypeScript, no DOM, no React, no import beyond the repo's own pure
  modules. It covers time and pixel conversion, frame rounding at a clip's own rate, clip layout end to end
  from durations, zoom, windowing, a clip's cut spans, trim limits, snapping.
- New `web/src/timeline/model.test.ts` (and, if it grows, a second `*.test.ts` beside it), run by the existing
  `npm test`: every function, both prototype bugs as named cases, and the overlapping-cuts, short-cut and
  missing-facts cases the prototype did not have.
- `web/src/preview/playback.ts`: its two imports from `../cuts/times` gain the `.ts` extension, as
  `times.test.ts` already writes them, so Node can load the module the model reuses for how the render joins
  cuts (`skipSpans`). No behaviour change.
- HLD: a D-20 entry (the timeline is built in the repo; no library; the model's rules), a §4.10 and §6 note.
  The plan's D-21 (proxy contract) is recorded by the proxy changes, not here.
- Nothing is wired: no component imports the model, so the production bundle does not change. The measured
  delta (expected 0 bytes, tree-shaken) is recorded in D-20.

## Capabilities

### New Capabilities

- `timeline`: the pure model behind the v2 timeline: units and frame alignment, layout, zoom, windowing,
  cut spans, trim limits, snapping, and its failure behaviour.

### Modified Capabilities

None. `web-app`'s "The type-check is the frontend's gate" says the project does not *require* a test runner
for GUI v1 and that adding one needs its own proposal; the runner is already in the repo (`npm test`), this
change adds none, and this proposal is the justification that clause asks for. The requirement is left
unedited so that parallel v2 changes do not conflict on it at archive.

## Impact

- Packages: `web/` only (one new directory, one two-line edit in `preview/playback.ts`).
- Dependencies: none added, none changed (a test asserts `package.json`'s `dependencies` stay as they are).
- Rendered output: unchanged; `RENDER_GRAPH_VERSION` is not bumped; the staleness fingerprint inputs are
  unchanged.
- `reel.yaml` and project `config.yaml` schema: unchanged. No Alembic migration, no rescan. No CLI or API
  change (Principle V: the model is client-side presentation logic; every fact it uses is an argument).
- HLD phase: §6 phase 9 (GUI v2), the "timeline editor" slice. It depends on no unresolved §8 item: §8.11
  (proxies and scrubbing) is what the research resolved, and this slice touches neither proxies nor media.
- Evidence relied on: `research/v2/timeline-library.md` §2.2 (prototype size, bugs, 60 fps drag to 400 clips,
  windowing table) and §4 (build-own); `research/v2/synthesis.md` §3 (D-18 as the plan's D-20), §5 row 3, §6
  risk 11 (variable frame rate unsized) and X6 (the API has no duration or fps).

## Non-goals

- No component, no CSS, no route, no `<video>` wiring, no keyboard handling, no pointer handling: that is
  `timeline-view` and the trim and overlay changes after it.
- No waveform lane, no reorder or cross-chapter move on the timeline (list-based, locked), no undo, no
  suggestion approve/reject logic (the overlays change), no multi-select.
- No variable-frame-rate frame snapping: a clip is rounded to its nominal rate (risk 11); the VFR flag in
  `facts.json` is the view's concern.
- No new dependency and no timeline library (D-20); `@dnd-kit` is not used here.
- No change to the Cuts panel's rules (`checkCut`, `skipAt`): the model agrees with them and does not
  replace them.
