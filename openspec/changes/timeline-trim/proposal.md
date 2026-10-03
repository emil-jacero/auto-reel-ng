## Why

GUI v1 edits a clip's cuts by typed times, with a one-clip preview that sets a time at the playhead (D-14, D-16).
HLD §4.10 moved the full timeline editor into v2, and its stated shape is "drag-trim in/out" on a per-clip track.
The ground under that is built and merged: the pure model (`web/src/timeline/model.ts`, `timeline-model`: trim
limits, snapping, frame grid, all in whole milliseconds) and the read-only Timeline (`timeline-view`:
`TimelineSection`, ruler, clips laid out from proxy facts, cut spans, one scrubbing `<video>`). What is missing is
the editing: the cuts are drawn, and nothing on them can be moved.

The research settled how this must be built (`research/v2/timeline-library.md` §2.2, §4; `synthesis.md` §5 row 11):

- **A trim handle is a slider, not a draggable.** `@dnd-kit` as the handle driver rendered `role=button`, had no
  `aria-valuenow`, lifted and nudged in pixel steps, and cost 283 dropped frames at 400 clips under a 4x CPU
  throttle; a hand-built handle held 60 fps. D-20 keeps `@dnd-kit` for reordering only.
- **The prototype's trim handle ran 22 checks in three engines** (snapping at 8 px, frame, 1 s and 5 s keys, Home and
  End to the limits, Enter at the playhead, 44 px touch handles, a snap line). Its two defects by testing, a
  limit that was not a frame time and two cuts with one name, are already fixed in the model.
- **Dragging needs an alternative** (WCAG 2.5.7), which the prototype met with the keys and v1's typed-time fields;
  the brief asks that the typed-time fields stay in step with the handles.

This change is the trim half of HLD **§6 phase 9** (GUI v2). It is also where the Timeline meets the editor: Edit
mode owns the draft, the Save bar, the `If-Match` write and the 412 conflict, and the read view's Timeline
deliberately writes nothing. Reading the code showed that the draft has no operation that **edits** a cut, only
add, remove and restore, and that its "back to what was read" test would silently drop a trimmed cut (it compares
keys, not times). Those are the first things this change must get right.

## What Changes

- **The Timeline in Edit mode.** Edit mode shows the same Timeline section (closed until opened, nothing loaded
  before), after the metadata form. Its cuts are the draft's, so a cut added, removed or restored in a Cuts panel is
  on the track at once, and Play skips a trim before it is saved. Its clips and proxies are the page's live event
  (a Prepare job that ends while editing is followed, the draft untouched) in the **saved order**: reorders stay
  list-based, and a note says so while the draft's order or chapters differ.
- **Two trim handles on each cut** of a clip that has a ready proxy, each a slider named "Cut n start|end of
  <clip>" (n = the cut's number in the Cuts panel), with value, range and value text in the panel's time format.
  - **Drag** (mouse, pen, finger): the edge moves by the distance moved, snaps to the clip's ends, other cuts' edges
    and the playhead within 8 px, shows a snap line and says what it snapped to, stays within the model's limits, and
    makes **one** draft edit on release; Escape cancels.
  - **Keyboard**: Left/Right one frame, Shift one second, Page Up/Down five seconds, Home/End to the limits, Enter
    sets the edge at the playhead.
  - **Typed times**: the selected cut's Start and End fields, in the Cuts panel's forms and with its refusals, stay in
    step with the handles, the drawn span and the Cuts panel's list.
  - **Touch**: 44 px handles under a coarse pointer, a nearest-edge rule where two overlap, a swipe still scrolls.
- **A draft operation that edits a cut** (`trimCut` in `edit/draft.ts`): same key, position and reason; new start or
  end. The draft's "back to what was read" test now compares times as well, `cutChanges` counts trimmed cuts so the
  save bar says "1 cut trimmed", and `checkRestore` stops treating a trimmed read cut as unchanged.
- **Save is the existing Save.** One whole-document `PUT` under `If-Match`, 412 handled by the existing conflict bar;
  the service already edits only the span that differs (`editorial-write`). No API change.
- **One video in Edit mode.** A clip preview and the Timeline's video release each other (the editor's preview
  store is the broker; `playback/exclusive.ts` keeps the movie and the Timeline apart as before); the clip-preview
  requirements are not touched.
- **HLD**: D-20 gains the trim record; §4.10, §6 phase 9, D-14 and D-16 ("scrubbing and drag-trim are the v2
  timeline editor's") are updated.

### Non-goals

- The analysis lane and approve/reject (`timeline-overlays`, in parallel; own component files); the draft operation
  for approval is theirs.
- Adding, removing or splitting a cut on the timeline ("cut at playhead"): the Cuts panel does that. Handles trim
  existing cuts only.
- Reordering and cross-chapter moves on the timeline (list-based, locked); undo and redo beyond what the draft
  already has (Reset; Undo of a removed cut); multi-select; ripple edit.
- Edge auto-scroll while dragging (research §4 lists it as unsized): a long drag is done by zooming, by the keys, or
  by typing.
- Variable-frame-rate frame accuracy (research risk 11): a clip is rounded to its nominal rate; typed times keep
  their millisecond.
- Changing the model's rules, the proxy contract, the API, `reel.yaml`, or the clip preview's requirements.
- A touch long-press gesture, a modifier key to switch snapping off, and a waveform.

## Capabilities

### New Capabilities

None. `event-timeline` was added by `timeline-view` (merged); this change extends it.

### Modified Capabilities

- `event-timeline`: **REMOVED** "The event page offers a Timeline that loads nothing until it is opened" and
  **ADDED** "The read view and Edit mode each offer a Timeline that loads nothing until it is opened" in its place
  (the old text, and its scenario "Edit mode has no timeline", say the opposite of this change, and a MODIFIED block
  cannot drop a scenario: the precedent is `api-excluded-clips-read-model`); **MODIFIED** "The track lays the clips
  out by their proxies' lengths, with the chapters and the cuts" (read-only spans in the read view, handles in Edit
  mode; the MODIFIED text is `main`'s as of d4e2a0b, copied whole); **ADDED** the trim handles, drag and snap,
  keyboard, typed times, touch, inert states, one video, and the gates with handles.
- `web-app`: **ADDED** "A trim made on the timeline is an edit of the same draft as a cut made in the Cuts panel"
  (counting, save, guards, Reset, 412, Undo). No existing `web-app` requirement is edited: "Edit mode previews a
  clip on request" and "A clip's preview sets cut times" (as `clip-preview-proxy` left them) stay as they are; the
  one-video rule is kept by the Timeline releasing its video instead.

## Impact

- **Packages**: `web/` only, plus `docs/high-level-design.md`. New under `web/src/timeline/`: `handles.ts` (pure; `trim.ts`
  would sit beside the model's `trim.test.ts`), `TrimHandle.tsx`, `CutFields.tsx`. Edited: `web/src/edit/draft.ts`, `web/src/edit/EventEditor.tsx`
  (a reducer action, one handler, the mount), `web/src/cuts/times.ts` (words, one check), `web/src/cuts/CutsPanel.tsx`
  (one `checkRestore` call site if its signature moves), and the merged Timeline files (`TimelineSection`, `Timeline`, `Track`, `useTimelineVideo`, `timeline.css`: the optional
  `editing` binding), plus `web/src/events/EventDetail.tsx` (two props to the editor).
- **API / CLI**: untouched (Principle V). The write is the existing `PUT …/reel`; `openapi.json`/`schema.d.ts`
  unchanged.
- **Rendered output**: unchanged by this change; `RENDER_GRAPH_VERSION` is not bumped; the staleness fingerprint's
  inputs are unchanged. (A *saved* trim changes the event's cuts, an editorial input, so the movie is outdated
  after a save exactly as after any cut edit.)
- **`reel.yaml` / `config.yaml`**: schema unchanged (`trims` entries as today). **Alembic / rescan**: none.
- **Dependencies**: none added (no timeline library, no test runner beyond the existing `node:test`, no `@dnd-kit`
  use). The bundle delta is measured and recorded (research: +5.6 KB gz JS, +2.6 KB gz CSS for the whole interaction
  layer; trim is part of that).
- **Depends on** (merged): `timeline-view`, and through it `timeline-model`, `proxy-state-read`,
  `proxy-media-endpoints`, `proxy-enqueue-endpoint`; `clip-preview-proxy` (the preview's requirements, untouched).
  Parallel: `timeline-overlays` (also edits the draft through `addCut` and mounts in the same Timeline; keep the
  editor wiring small and conflict-light).
- **Principle VIII**: one package, one interaction (trim), one draft operation. The draft fix is a prerequisite of
  it, not a separate feature.
