## Context

State of `main` (d4e2a0b, with `timeline-model` and `timeline-view` merged and archived; read from the code, not
from their plans):

- `web/src/timeline/model.ts` (`timeline-model`): whole-millisecond `Ms`, `ClipFacts {durationMs, fps}`, `frameMs`,
  `nearestFrame`, `minCutMs` (three frames), `layout`, `clipAt`, `timeToPx`, `pxToTime`, `cutSpans`, `cutRects`,
  `Edge`, `trimLimits(cuts, index, edge, facts)`, `snapTo`, `snapCandidates(cuts, index, facts, playheadMs, extra)`,
  `trimEdge(cuts, index, edge, wantedMs, facts, pps, candidates)` returning `{ms, snappedTo}`, `SNAP_PX = 8`. Its limits
  always hold the current value; it takes `ListedCut` (`{in, out, removed?}` in seconds). It has no reducer.
  `timeline/trim.test.ts` already exists: it tests **the model's** trim functions, so this change's new pure module
  is named `handles.ts` (test: `handles.test.ts`), not `trim.ts`.
- The Timeline (`timeline-view`), read view only: `TimelineSection({eventId, event, read, onFinished})` (the toggle,
  `usePrepare`, `shownClips(event)`, `trackClips(shown.clips, read.cuts)`) is mounted by `ReadyView` in
  `events/EventDetail.tsx`, which owns `useReadCuts` (`GET …/reel`, after each event read). `Timeline({eventId, clips,
  chapterNames, cuts: CutsRead, prepare})` holds the playhead store (`playhead.ts`, `useSyncExternalStore`), the
  `useTimelineVideo` controller and zoom; `Track` windows the clips (`visibleClips`) and draws a clip's cut spans
  (`clip.drawn`, the joined spans) only when the clip is wide enough to be `detailed`. A `TrackClip` is
  `{identity, name, chapter, facts, vfr, film, version, cutCount, drawn, spans}`, so cuts enter as a
  `ClipCuts` (`ReadonlyMap<identity, Trim[]>`) and nothing in the Timeline knows a cut's key, reason or removed flag.
  Its one `<video>` is rendered for as long as the track is open. `playback/exclusive.ts` makes the movie and the
  Timeline's video pause each other; the clip preview is not in it.
- v1 Edit mode (`web/src/edit/`): `EventEditor.tsx` holds a reducer over `{baseline, draft, pressed, nextCut, typed,
  ...}`; `draft.ts` is pure (type-only imports) and holds `Draft.cuts`, a map from a clip's identity to the
  `DraftCut[]` the operator changed; `CutsPanel.tsx` lists them and calls `CutHandlers` (`onAdd`, `onRemove`,
  `onRestore`). Save is one `PUT …/reel` under `If-Match`; 412 shows the conflict bar (`Reload latest`, `Overwrite
  with mine`). `editorial-write` edits "only the spans that differ", matching an edited span to the old one by
  value, then by `in`, then by `out`, so a trimmed span is an in-place edit that keeps its comment and style.
  **`EventEditor` reads its `event` prop once** (`const [detail] = useState(event)`), while `EventDetail` goes on
  passing it the page's live `state.event`, which a quiet re-read replaces.

Three facts found by reading the code shaped this design, and the spec states each as observable behavior:

1. **The draft cannot edit a cut.** It has `addCut`, `removeCut`, `restoreCut`. And `settled()` decides a clip's list
   is "as read" when it has the same keys, none removed: it never compares times. A `trimCut` built on it as it is
   would be dropped as "unchanged" and the save bar would never appear.
2. **`cutChanges` counts only added and removed cuts**, and `checkRestore` exempts two cuts that both carry read keys
   (`r0`, `r1`) from the overlap refusal because "an overlap between them was already in the file". After a trim
   that is no longer true.
3. **The Timeline's clip list and the editor's draft are two views of different moments.** The Timeline lays out
   `shownClips(event)` (chapters from the event read) and takes its cuts as a map of `Trim[]`; the editor's draft
   holds the cuts (keyed, with a removed flag) and, separately, the operator's unsaved order and chapters. Drawing the
   draft's order would need the editor's `Orders`/`DraftChapter` mapped back onto proxy facts for every move; trimming
   needs none of it (a cut belongs to a clip's identity, not to its place).

## Research & Decisions

### Handles are sliders built in the repo; dnd-kit stays for reorder
**Context**: D-20 (the plan's number; the research calls it D-18) builds the timeline in the repo and keeps
`@dnd-kit` for reordering. The trim handle needs value semantics.
**Explored**: `research/v2/timeline-library.md` §2.2 (prototype `Handle.tsx`, 114 lines: pointer + keyboard + snap;
22/22 checks in Chrome 154, Firefox, WebKit; 60 fps drag to 400 clips at 4x CPU with windowing) and the dnd-kit
measurement (`role=button`, no `aria-valuenow`, 283 dropped frames and 20 long tasks at 400 clips, 4x; keyboard =
lift, nudge in pixels, drop), §2.3 (v1's `CutBar` is already a hand-built slider).
**Decision**: a `TrimHandle` with `role="slider"`, pointer capture and its own key handler, driven by the model's
`trimEdge`. No new dependency.
**Rationale**: the WAI-ARIA slider pattern is the right abstraction for a continuous value; the measured cost is lower
and the semantics are the ones the brief asks for ("slider semantics").

### Where the Timeline mounts: Edit mode, on the draft
**Context**: `timeline-view` left this open: "Edit mode entry or its own toggle" (HLD D-20: "`timeline-trim` decides how
the same component mounts there").
**Explored**: (a) a second draft and a Save in the read view's Timeline: a second write path, its own conflict and
unsaved-change handling; (b) trim handles in the read view writing straight to `reel.yaml`: every drag a write,
no undo, no review; (c) the Timeline inside Edit mode on the editor's draft.
**Decision**: (c). `EventEditor` mounts the same `TimelineSection`, closed until opened, after `MetadataForm`.
`TimelineSection` gains one optional prop, `editing: EditBinding | null` (null = the read view, unchanged):

```ts
type EditBinding = {
  cuts: ClipCuts                                  // the draft's cuts, removed ones left out (drives drawn/spans/play)
  listed(identity: string): readonly DraftCut[]   // cutsOf(baseline.cuts, draft.cuts, identity): keys, reasons, removed
  onTrim(identity: string, key: CutKey, span: { in: number; out: number }): void
  locked: boolean                                 // a save in flight, or Move clips pending
  announce(words: string): void                   // Edit mode's one live region
  orderChanged: boolean                           // the draft's order or chapters differ from the saved ones
}
```

and takes `read = {cuts: editing.cuts, failure: null}` in its place, so `trackClips`, `movieMs`, Play's skip spans and
the "cuts are being read" wait all work on the draft with no second code path. The **layout** (clips, chapters,
facts, `version`) comes from the page's live event: `EventDetail` passes its `state.event` to `EventEditor` as a
second prop, `liveEvent`, and `reread` as `onProxiesFinished` (the editor's own `event` prop stays the once-read
snapshot the draft is built from). A quiet re-read therefore changes the Timeline's proxies and nothing in the
draft. Reorders and cross-chapter moves stay list-based (locked): the Timeline shows the **saved order** and a note
says so while `orderChanged` (task 1.1 adds `layoutChanged(baseline, draft)` to `draft.ts` from `chapterChanges`/
`isStructural` and the existing `reordered`).
**Rationale**: Edit mode already owns Save, `If-Match`, 412, Reset, the unsaved guard, Ctrl+S and the live region;
the brief says edits go "through the existing draft/cuts model and Save". The read view's Timeline stays read-only.
**Cost**: `event-timeline` states the new mount in a REMOVED + ADDED pair (the old requirement said "In Edit mode the
page SHALL show no Timeline section", and its scenario of that name cannot be kept by a MODIFIED block; the repo's
precedent is `api-excluded-clips-read-model`), and one MODIFIED block for the track (spans read-only only in the read
view). Clips whose cuts change are re-derived through `trackClips` once per draft edit (one edit per gesture), reusing
the previous `TrackClip` of every clip whose cut list is the same reference so memoised clip elements keep their props.

### A draft operation that edits a cut, and a corrected "as read" test
**Context**: see Context, facts 1 and 2.
**Decision**: in `edit/draft.ts`:

```ts
export type DraftCut = { key; in; out; reason; removed;
  /** True while a cut read from reel.yaml has other times than it was read with. */
  edited?: true }
export function trimCut(baseline: Baseline, draft: Draft, identity: string, key: CutKey,
                        span: { in: number; out: number }): Draft
export function cutChanges(baseline, draft): { added: number; removed: number; trimmed: number }
```

- `trimCut` finds the cut by key in `cutsOf(...)`, ignores an unknown or removed key (returns `draft`), returns
  `draft` itself when the times are unchanged, throws `RangeError` for a non-finite time or `out <= in` (the
  handles only produce legal values, so this is a bug, and Principle I says fail loud), and otherwise replaces the
  cut **in place** (same key, position, reason) with the new times, setting `edited` when the cut has a read
  twin whose times differ and clearing it when they match. It then goes through `settled`.
- `settled`'s first "as read" clause also compares each cut's `in` and `out` to the read cut of that position;
  the second clause (`sameTrims`) already compares times and reason. An edit and its reverse leave `draft.cuts`
  without the entry, as add then remove does today.
- `cutChanges.trimmed` counts, on the clips `changedCuts` names, the cuts not removed whose key is a read key and
  whose times differ from the read cut with that key. A trimmed read cut that is then removed counts as removed, not
  trimmed.
- `checkRestore` exempts the pair only when the other cut is a read cut that is **not** `edited`.

A position-based address (`r0`, `a1`) is the identity, because `reel.yaml` cuts have no id; the model addresses cuts
by their index in the clip's list too, and a trim never reorders the list (the limits keep a cut between its
neighbours, which do not overlap it).
**Rationale**: smallest change that makes the existing machinery true for a new kind of edit. The save body already
comes from `savedTrims`, so no write-side change is needed.

### One draft edit per gesture; the drag itself is local
**Context**: G1's rule from v1: a gesture must not re-render the chapter lists at pointer rate; the research
measured 60 fps with windowing, and 283 dropped frames when every consumer re-rendered per move (dnd-kit).
**Decision**: during a drag the dragged edge, the cut's rectangle, the snap line and the fields are driven by a
small external store (the prototype's `playhead.ts` pattern, 17 lines) that only those parts subscribe to; the
draft is untouched until `pointerup`, which calls `onTrim` once with the final value. `Escape`, `pointercancel` and
a save starting restore the edge. A key press is its own gesture: one `onTrim` per key.
**Rationale**: the Cuts panel and the save bar cannot flicker through intermediate values, and the pointer path
costs one reducer step.

### What a drag computes, from the model
`wanted = edgeAtPress + (pointerX - pressX) / pps` in ms; `trimEdge(cuts, index, edge, wanted, facts, pps,
snapCandidates(cuts, index, facts, playheadMs | null, []))` gives `{ms, snappedTo}`. `listedCuts` passed to the
model are the clip's draft cuts as listed (removed ones included; the model skips them). `handles.ts` adds the pure
parts the model does not have:

```ts
export function stepEdge(key: string, shift: boolean, nowMs: Ms, range: [Ms, Ms], fps: number): Ms | null
export function atPlayhead(playheadMs: Ms | null, clipDurationMs: Ms, range: [Ms, Ms], fps: number):
  { ms: Ms } | { refused: 'not-in-clip' }
export function nearestHandle(pressPx: number, handles: readonly { id: string; px: number }[], reachPx: number):
  string | null
export function snapWords(target: Ms, ctx: SnapContext): string
export function describeEdit(...)   // value text for a handle: time, then the cut's span in words
```

- `stepEdge` returns null for a key it does not handle. Arrow: the frame time `n` frames away in that direction,
  where an off-grid time moves to the next grid frame in that direction first (typed `1.234` + Right goes to the
  first frame after it, not 1.234 + 1 frame). Shift+Arrow: ±1000 ms; PageUp/PageDown: ±5000 ms, each result
  `nearestFrame`d. Home/End: the range ends. The result is clamped into `range`; the range comes from
  `trimLimits`, so Home/End land on frame times (the prototype's bug 1).
- `atPlayhead` is Enter: the playhead's time in this clip (the playhead's end of the clip counts as inside it),
  `nearestFrame`d and clamped into the range; null playhead or outside the clip gives `not-in-clip`.
- `nearestHandle` is the touch rule: among the handles whose edge is within `reachPx` (22 for a 44 px area) of the
  press, the nearest; a tie goes to the earlier time. Called from a handle's `pointerdown`, which hands the press
  to the winner when it is not itself.
- `snapWords` names the snap target: the playhead first, then the clip's start or end, then "cut n start|end" by
  the Cuts panel's number.
- All times are `Ms`; seconds appear only when calling `trimCut` (`ms / 1000`, the nearest double, as
  `parseTime` does).

### Handle names use the Cuts panel's numbers, not the model's ordinals
`cutOrdinals` numbers non-removed cuts by start so that names never collide. The Cuts panel numbers cuts by
**position in the list**, removed ones counted, and its refusals ("This cut overlaps cut 2") use that number. A
handle called "Cut 1" that the panel calls "cut 3" would make the two surfaces disagree. The list position is
also unique per clip, so the collision the ordinal guards against cannot occur. The handle uses `index + 1`; the
model's `cutOrdinals` is not needed by trim.

### Typed times: reuse `checkCut`, with the cut itself taken out of the list
**Context**: "typed-time fields stay in sync" and WCAG 2.5.7 (a non-dragging alternative).
**Decision**: `CutFields` shows, for the selected cut, two text fields. A commit (Enter or blur) calls `checkCut(
listed.map(c => c is this ? {...c, removed: true} : c), startText, endText, lengthSeconds)`; the cut is marked
removed in the copy rather than filtered out, so the overlap refusal's number is still the panel's. The length is the
proxy's duration. An accepted result goes to `onTrim`; a refusal is written with `refusalWords` at the field the
refusal names, which takes focus; Escape puts the cut's time back. While a field has focus and unsent text it is
not overwritten by the store; otherwise it shows `formatTime` of the live value, so a drag updates it on every
frame.
**Rationale**: one rule set for "what time is acceptable" on every screen (D-14: "times are written one way on every
screen"); no second validator to drift. A typed time is millisecond-precise, not frame-aligned, as in v1; the model's
range still holds it.

### One video in Edit mode, without touching the clip-preview requirements
**Context**: "Edit mode previews a clip on request" (`web-app`, as `clip-preview-proxy` left it) says Edit mode never
holds more than one video element. The Timeline has its own, rendered by `Timeline` for as long as its track is open,
and `playback/exclusive.ts` pauses one *playing* video when another starts, which only the movie and the Timeline use
(the clip preview is not in it, and the movie is absent from Edit mode). A MODIFIED of the preview requirements
would be a second edit of the same blocks for the sake of a cross-reference.
**Decision**: keep the rule by construction, with the editor's preview store as the broker. `Timeline` gets
`videoHeld: boolean` (from `useSyncExternalStore(previews.subscribe, () => previews.open() === null)`, passed down in
`EditBinding`): when false it renders no `<video>` and `useTimelineVideo` pauses, drops `src`, calls
`releasePlayback` and keeps the playhead's position in the store; the Timeline stays open and handles work (they need
no video). A playhead move or Play while the video is not held calls `previews.hide(previews.open())` first, which
re-renders `videoHeld`, then loads the proxy of the clip the playhead is in and seeks. No new state in `ClipPreviews`.
**Alternatives**: allow two videos and pause one (changes the preview requirement's "one at a time"); close the
Timeline when a preview opens (loses zoom and scroll for a Watch).

### Quality bar
**Context**: the brief and `timeline-view` set: no horizontal page scroll 320–1280, reduced motion, light/dark, 44 px
touch, scrub gate (median ≥ 30 fps, step p90 ≤ 60 ms) in Chrome and Firefox ≥ 155.
**Decision**: the gates are re-measured with handles on the track in Edit mode (task 8), plus the research's drag
measure (rAF deltas, 180 moves, 80 clips, 4x CPU) with the pass line at most 2 % of frames over 25 ms; the
prototype showed 0. Handles are windowed with their clip (they exist only for clips in `visibleClips`). The only
transition on a handle reads the `--dur-fast` token that `tokens.css` zeroes under reduced motion. State is words
and shape: focus ring, the snap line plus "Snapped to …", a "unavailable" word in the fields group.

## Decisions

### Components and files (`web/src/timeline/`)
- `handles.ts`: the pure functions above (the name `trim.ts` would sit beside the model's `trim.test.ts`). No imports beyond `model.ts` and `../cuts/times.ts`; node-tested in `handles.test.ts`.
- `TrimHandle.tsx`: one handle: slider ARIA, key handler (`stepEdge`, `atPlayhead`), pointer capture, the drag store,
  the 44 px / 24 px areas by `(pointer: coarse)`, `touch-action: none` on the handle only.
- `CutFields.tsx`: the selected cut's group and fields; selection is a `useState` in the Timeline keyed by
  `(identity, key)` and cleared when the cut is removed or the draft is reset.
- `timeline.css` additions (the file `timeline-view` adds): handle, snap line, readout, fields group.
- `Timeline` (timeline-view's component) gains the optional `editing: EditBinding | null` (above), passed down by
  `TimelineSection`; `Track` draws a `TrimHandle` pair per listed cut inside the clip element wherever it draws the
  cut spans (`detailed`), so handles are windowed with their clip. With `editing === null` nothing changes.

### Editor wiring (`edit/EventEditor.tsx`, small)
- Reducer action `{type: 'cut-trim', identity, key, span}` → `withDraft(state, trimCut(...))`.
- `CutHandlers.onTrim(identity, key, span)` with the same guard as `onAdd`: `current.pressed === null &&
  moving.current === null`; it dispatches and announces `trimmedWords(...)`.
- `summarize` gains `trimmed`: `"1 cut trimmed"` after "added" and "removed".
- The mount: `<TimelineSection editing={…}/>` after `MetadataForm`, before the chapters, with `liveEvent` and
  `onProxiesFinished` from `EventDetail`; Reset replaces `baseline`/`draft` in place (Reload latest leaves Edit mode, so the whole editor and its Timeline go), and the handles' layer is
  keyed on the baseline so a selection and a drag do not survive them (the section stays open; zoom and scroll stay).

### Words (`cuts/times.ts`, with tests in `times.test.ts`)
`TRIM_KEYS` (description of the keys), `handleName(edge, n, name)`, `handleValueText(ms, cut)`,
`selectedName(n, name)`, `fieldName(field, n, name)`, `trimmedWords(n, name, cut, after, snap?)`, `NOT_IN_CLIP(name)`,
and `UNAVAILABLE` (the fields group while locked). Existing helpers are reused: `formatTime`, `spanWords`,
`spokenSummary`, `refusalWords`.

### Failure behavior
- A clip without ready proxy has no timeline presence, so no handle; its Cuts panel is unchanged. The model throws
  `ModelError` on missing facts; the view never calls it without them (Principle I: no default fps or duration).
- `trimCut` throws `RangeError` on a non-finite time or `out <= in`; an unknown or removed key is a no-op.
- A refused typed time changes nothing and says why at the field. An Enter with the playhead outside the clip
  changes nothing and says so.
- A 412 on Save is the existing conflict bar; the trims stay in the draft. `Overwrite with mine` re-reads only the
  tag, then writes the same body.
- Nothing here writes a file or retries.

### Idempotency
Trimming to the time an edge already has returns the same `draft` object (no state change, no announcement). An
edit and its reverse leave no entry in `draft.cuts` (the corrected `settled`). Save is the existing whole-document
`PUT`: repeating it with the same body changes nothing on disk (`editorial-write`: "a list that is unchanged by
value SHALL be persisted exactly as it was"). A worker restart or a render is not involved; the staleness verdict
changes only after a Save, like any cut edit.

### Bundle and dependencies
No dependency changes (a test from `timeline-model` asserts the list). The bundle delta (gzip JS and CSS, before and
after) is measured by the verification task and recorded in D-20.

## Risks / Trade-offs

- **Proxy length versus source length.** The Timeline's clip end is the proxy's duration (D-21: within 50 ms of the
  source). An End/Home-to-limit trim that ends a cut "at the clip's end" writes the proxy's end; if the source is a
  few ms longer, up to one frame of footage can remain. The render clamps a cut past the end, so too long is safe;
  too short is the sliver. Task 4.1 records the proxy-versus-ffprobe difference on the samples. Not mitigated
  here; if the measured difference is a frame or more on real clips, a later change can let End use the
  length the clip's preview read from the original.
- **A trim cannot be undone one step at a time**, only Reset (everything) or trimming back by hand/keys; v1 has no
  undo stack and this change does not add one (non-goal). A cancelled drag and a keyboard step back are cheap.
- **`EventEditor.tsx` is 2,067 lines and `timeline-overlays` edits the same file** (approval becomes `addCut`). The
  wiring here is one action, one handler, one summary part, one mount; the two changes touch different lines, and
  the supervisor merges one first.
- **Touch precision.** A finger drags frame-rounded edges at the current zoom; at 4 px/s a pixel is 250 ms. The
  keys, the fields and zoom are the precision tools; the spec does not promise frame accuracy by drag at low zoom.
- **Firefox's `pointer` events on a captured slider** were exercised in the prototype (22/22 in Firefox); task 4.1
  repeats the functional script on the real implementation in Chrome and Firefox ≥ 155 (image
  `localhost/pcm-audio-research:pw163`; confirm its version).
- **The editor keeps a snapshot, the Timeline follows the page.** `EventEditor` builds its draft from the event it
  was opened with and never again; the Timeline reads the page's live event for proxies. A clip that appears or
  vanishes on disk while editing changes the Timeline's clips but not the editor's panels: a handle is drawn only for
  a clip whose cut list the editor can give (`listed(identity)`), and a clip the editor has no panel for is shown
  without handles. Not mitigated further: the editor's own staleness handling (412) is the safety net.
- **Keyboard reach is by window.** Handles exist only for clips in or near the view, so Tab reaches the handles
  around the playhead, not every cut of a 400-clip event; Home/End and the keys on the playhead move the view. A
  user who wants "the third cut of clip 212" scrubs there or types in that clip's Cuts panel (always complete).
- **Order is the saved order.** A reorder made in the same Edit session is not drawn until Save (a note says so).
  Drawing the draft's order is a larger change (the draft's maps onto proxy facts) and is left to a later one.

## Migration Plan

Additive. No data, schema or API change. A rollback is reverting the web change: no stored state carries a trim
beyond the `trims` that `reel.yaml` already holds.

## Open Questions

None blocking. Recorded for the next changes: whether `timeline-overlays` approval should reuse `trimCut` for
"approve and adjust" (it reads the same draft); edge auto-scroll while dragging; a snapping-off modifier.
