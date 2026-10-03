## Context

See proposal.md, "Why". Facts on main d4e2a0b (`timeline-view` merged, `timeline-trim` not):

- **The read exists and is unused.** `GET /api/v1/events/{id}/analysis` returns `AnalysisOut`
  `{analyzed: bool, segments: {clipIdentity: [{start, end, kind, confidence}]}}` (`api/events_read.py`
  `get_analysis`). It reads only the sidecar cache (`.auto-reel/cache/`), validated against each clip's size and
  mtime, never triggers analysis, never reads `reel.yaml`, answers 404 and 502 problem bodies and no 503. A clip
  with **no valid entry has no key** in `segments`; a clip analysed with nothing found has an **empty list**;
  `analyzed` is documented as true when at least one clip has an entry, **but the code sets it when
  `.auto-reel/cache/` exists**, and a render's manifest (`staleness/manifest.py`) creates that directory, so a rendered,
  never-analysed event reads `analyzed: true, segments: {}`. The page therefore decides "never analysed" from the entries
  (`segments` is empty), not from the flag. `kind` is typed `string` in `schema.d.ts`
  (`black`, `white`, `freeze` today; ML kinds later, HLD §4.5 stage 2). `confidence` is the same coarse constant
  on every v1 segment (D-AN5), so it carries no ranking.
- **Times are source seconds.** A segment's `start`/`end` and a cut's `in`/`out` are seconds in the original
  clip, and the proxy's time equals the source's (D-21, `-fps_mode passthrough`). So a suggestion needs no
  conversion to be a cut, and no conversion to be placed on the timeline.
- **The cut model in Edit mode.** `edit/draft.ts` holds `DraftCut {key, in, out, reason, removed}` per clip.
  `addCut(baseline, draft, identity, span, key)` inserts a cut with the reason hard-coded to `manual`;
  `removeCut` / `restoreCut` mark or drop; `settled` returns to the read state when an edit is undone, so an
  edit and its reverse leave nothing to save; `buildWriteBody` writes each changed clip's `trims` with
  `{in, out, reason}`. `EventEditor.tsx` reduces the action `cut-add {identity, span, key}` where `key` must be
  `a${nextCut + 1}` and is announced through the editor's one live region (`announce`); `CutHandlers.onAdd` is
  the stable object the rows use. `cuts/times.ts` `checkCut(listed, typedIn, typedOut, length?)` is the one
  check for a new cut (order, past the clip's end, overlap with a listed cut that is not removed) and
  `formatTime` writes a time to the millisecond.
- **`timeline-view`'s seams (read off main d4e2a0b).**
  - `events/EventDetail.tsx` owns `editing` and the read; it renders `ReadyView` (read view) or `EventEditor`
    (Edit mode). `ReadyView` renders `timeline/TimelineSection.tsx` with `{eventId, event, read, onFinished}`,
    where `read` is the page's one `useReadCuts` state `{cuts: ClipCuts | null, failure}` (`ClipCuts` = identity
    -> `Trim[]` in seconds). **Edit mode shows no Timeline** (spec `event-timeline`, "In Edit mode the page SHALL
    show no Timeline section"); `timeline-view`'s design leaves the Edit mount to `timeline-trim`, which plans
    `<Timeline mode="edit" .../>` with `cutsOf(identity)` from the draft, `onTrim`, `locked` and `announce`.
  - The section is **closed on every Refresh and after leaving Edit mode**, and while closed or in the Prepare
    state it renders no `Timeline` (no `<video>`, no request). `Timeline.tsx` mounts only when every shown clip
    has a ready proxy; it takes `clips: TrackClip[]`, `cuts: CutsRead`, `prepare`, and creates the `Playhead`
    store, `useTimelineVideo` (`video.seekTo(Position)`), the zoom state and the scroller.
  - `layout.ts` `TrackClip {identity, name, chapter, facts: {durationMs, fps}, version, cutCount, drawn, spans}`;
    `model.ts` `Layout {startsMs, totalMs}`, `timeToPx`, `pxToTime`, `visibleClips(l, view, overscan)`;
    `position.ts` `Position {clip, ms}`, `onGrid`, `positionAt`.
  - `Track.tsx` draws, inside `.tl-viewport > .tl-canvas`, the ruler, `.tl-chapters`, `.tl-lane` (the clips as
    `role="group"` `.tl-clip` boxes at `timeToPx(lay.startsMs[i], pps)`, only for the window `visibleClips(...)`
    with an overscan of one view) and the playhead slider. The canvas height is fixed in `timeline.css`
    (`--tl-ruler-h + --tl-band-h + --tl-clip-h + --s-3`). There is no per-clip slot and no model "scroll to
    time"; the playhead is kept in view by an effect in `Timeline` (`EDGE_PX` from the scroller's edge) whenever
    the playhead store moves and no drag is in progress.
  - Nothing on main reads the analysis (`grep -rn analysis web/src` finds only `cuts/times.ts`).

## Goals / Non-Goals

**Goals:**
- Dead-footage suggestions are reviewed where the footage is, one decision per suggestion, by pointer, touch,
  keyboard and assistive technology.
- Approval is an ordinary cut in the existing draft: one Save, one `If-Match` write, one undo model.
- The lane can never say "cut" for footage the movie still plays, or "pending" for footage it leaves out.

**Non-Goals:**
- A second editing model, a second save path, a bulk action, a persisted rejection, an analysis trigger,
  confidence display, trim handles (proposal, Non-goals).

## Research & Decisions

### The lane's data and its three states of "no suggestions"

**Context**: the lane must not conflate "never analysed", "analysed, found nothing" and "could not read".
**Explored**: `api/events_read.py` `get_analysis`; the api-service spec's "Analysis results are exposed
read-only"; `cuts/ReadCuts.tsx` `useReadCuts` (the failure note and the abort pattern); `TimelineSection`
(what mounts when). Reading on every event read, as `useReadCuts` does, was rejected: it would request while
the section is closed.
**Decision**: `api/analysis.ts` `fetchAnalysis(eventId, signal)` returns `ok | problem | unreachable |
unpublished`, as `fetchEvent` does (statuses 200, 404, 502). `useAnalysis(eventId)` reads **once when the track
mounts**, that is when the Timeline is open and every proxy is ready (never while the section is closed or
preparing: `event-timeline` promises a closed Timeline makes no request). A Refresh or leaving Edit mode closes
the section and unmounts the track, so the next opening reads again; the read in flight is aborted by leaving
the page or closing the section. There is no "last answer kept while the new one arrives": a remount starts
from "Reading the suggestions…". The lane's words: for the event, `analyzed === false` or no entry at all reads
"Not analyzed. Run `auto-reel analyze <root>`, then Refresh" (no clip has an entry: `analyzed === false` or an empty `segments`; the root is not known to the page, so the command
is written with the placeholder, as the page writes other commands today); `analyzed === true` with no
suggestions reads "Analyzed: nothing to suggest"; for one clip with no key in `segments` while the event is
analysed, the clip's row reads "Not analyzed" (its cache entry is missing or stale because the file changed),
and with an empty list it draws nothing and counts as analysed. A failed read is a note "Suggestions could not
be read" with the cause in the words the page uses (`unansweredFailure`, `FAILURE_LABEL`), not an alert; the
timeline stays usable.
**Rationale**: the endpoint already encodes the distinctions; collapsing them would invite the operator to
think a clean library was never checked, or the reverse.

### Suggestion state is derived from the cuts, never stored

**Context**: the prototype stored `state` on the suggestion and showed "approved" for footage no cut covered
(defects 1 and 2, proposal).
**Explored**: `proto/src/model.ts` `reduce` / `decide`; Edit mode's `settled` (the draft already derives
"dirty" from the difference to the read state, which is why Undo of an Undo is free).
**Decision**: a pure `suggestionState(cuts, segment, dismissed)` returns one of `pending`, `cut`, `partly-cut`
or `dismissed`. `cuts` are the clip's listed cuts that are not removed (in Edit mode the draft's list for the clip, `cutsOf(...)`
filtered with `keptCuts`; in the read view the `Trim[]` of the page's read cuts). The lane is given one function
for both, `cutsOf(identity)` in the `analysis` value (see "Gate seams"), so it does not know which mode it is in. Spans are compared at the millisecond as `cuts/times.ts`
does (`ms()`); the cuts are first joined as the render joins them (sorted, overlapping or touching spans
merged, the same union `cutOutSeconds` counts). Then: the union covers `[start, end]` entirely → `cut`; it
shares more than an instant with it → `partly-cut`; otherwise `dismissed` if the page visit dismissed it, else
`pending`. A cut wins over a dismissal: dismissing then cutting by hand is a cut. A segment of under one
millisecond once rounded is `pending` and cannot be approved (`checkCut` refuses it as `order`).
**Rationale**: the draft is the single source of truth. A trim handle (`timeline-trim`), the Cuts panel's
Remove, and a Reset all move a suggestion's state with no code in this change; a saved cut from an earlier
session (reason `black` in `reel.yaml`) already shows as cut on the first read.

### Approval is `cut-add`, checked by `checkCut`

**Context**: an approved suggestion must be an ordinary cut with the kind as its reason, and must never be
silently skipped (defect 1).
**Explored**: `addCut`'s hard-coded `'manual'`; the `cut-add` reducer's key check; `checkCut`'s refusals.
**Decision**: `addCut(baseline, draft, identity, span, key, reason = 'manual')`, `cut-add` carries an optional
`reason`, `CutHandlers.onAdd(identity, span, reason?)`. Approve calls
`checkCut(listed, formatTime(start), formatTime(end), length)` (`formatTime` rounds to the nearest millisecond;
`length` is the track clip's `facts.durationMs / 1000`, the proxy facts' ffprobe duration, never the `<video>`'s). On `ok` it dispatches `cut-add` with the
suggestion's `kind` as the reason, whatever string that is (`reasonWords` already writes an unknown reason in
quotes). On a refusal it adds nothing, announces the refusal in `refusalWords`' words ("Not approved: …") and
the detail strip shows them; the suggestion stays pending or partly cut. A **partly cut** suggestion is refused
for its overlap, as a typed cut is: the operator either removes the overlapping cut or trims it, not a silent
remainder. The press is ignored, as the Cuts panel's is, while a save or a Move clips is pending
(`cutHandlers.onAdd` already enforces that).
**Rationale**: reusing `checkCut` means one definition of a valid cut and the same words everywhere. Writing a
remainder or merging with the overlapped cut would change a span the operator did not see.

### Dismissal is for this page visit only

**Context**: "reject" must mean something, but `reel.yaml` has no field for it and the analysis cache is
derived, read-only state (Principle II: an editorial fact lives in `reel.yaml`, written first).
**Explored**: (a) a `reel.yaml` field, which is a schema change for a negative fact that never affects the
render; (b) `localStorage` per viewer (D-8/`web/README.md`: per-viewer conveniences only), which would hide
suggestions on this browser but not on the next device, and would go stale when the cache is rebuilt; (c) the
page's own state.
**Decision**: (c). Dismissed suggestions are a `Set` of `identity|start|end|kind` held in
`events/EventDetail.tsx` (a `useDismissals()` hook in `overlays/Dismissals.ts`), the one component above both
the read view and Edit mode. It cannot live in the Timeline or its section: both unmount on a Refresh and on
every switch between the read view and Edit mode. The set survives entering and leaving Edit mode, a Refresh and
a Save, and is gone on reload or leaving the page. The lane says so once in its note ("Dismissed suggestions come back when the page is
reloaded") and shows a **Restore** on a dismissed mark. A dismissal is not an edit: it does not dirty the draft,
enable Save, or raise the unsaved-changes guard.
**Rationale**: smallest honest behaviour that makes Reject useful in a session (a long review needs "I have
looked at this one"). It is stated, not hidden. (a) and (b) are one change each, and wait for a real library to
show whether re-seeing rejected suggestions is a nuisance.

### The lane: one toolbar per clip, a detail strip for the selected mark

**Context**: a short suggestion at low zoom is a few pixels wide (the prototype's chips truncated to "freez" and
"bla"), a clip may hold dozens of suggestions, and the timeline is windowed.
**Explored**: `timeline-library.md` §2.2 (chips, `aria_snapshot`, "a real implementation should replace [the
truncated label] with an icon"); the touch-size requirement ("Every control is large enough to touch", 44 px).
**Decision**:
- The lane is **its own row of the canvas, below the clips' row**, not inside a clip's box (a clip box is
  `overflow`-clipped and 54 px high). For each clip in the windowed range a `role="group"` named "Analysis
  suggestions of <clip name>" holds the marks, placed at `timeToPx(lay.startsMs[i] + ms, pps)` from the model's
  time-to-pixel mapping. A mark draws the span's width but has a hit area of at least 44 px
  (centred on the span); marks that would overlap stack into further rows rather than hide each other, stacked once over
  the marks of the whole track (the end of one clip and the start of the next reach into each other), so a mark's row
  never depends on which clips are drawn.
  A mark shows an **icon for the kind** (one each for black, white, freeze, and a neutral icon for an unknown
  kind) and a **glyph for the state** (`?` pending, `✓` cut, `◐` partly cut, `×` dismissed). Neither relies on
  colour; the words are in the accessible name and in the strip.
- **Roving tabindex**: the lane is one tab stop per clip; ArrowLeft/ArrowRight move to the previous or next
  suggestion, Home/End to the first or last. Moving to a suggestion outside the window moves the playhead to its start (`video.seekTo`, at
  `onGrid(facts, start)`); the Timeline's own playhead-follow effect then scrolls it into view, and the lane
  focuses the mark once it is rendered. (There is no model function that scrolls to a time; this reuses what
  exists.) Windowing renders only the marks of clips in the window plus the focused one.
- A mark's accessible name is "<Kind> <start> to <end> (<length>), <state word>" with times as `formatTime`,
  and `aria-keyshortcuts="A R"` when it can be decided.
- Selecting a mark (click, Enter, Space, or focus by arrow) opens one **detail strip** under the timeline:
  the clip's name, kind in words (`CUT_REASON_LABEL`), span, length, state in words, and the buttons
  **Approve as cut** and **Dismiss** (or **Restore**). Selecting also moves the playhead to the suggestion's
  start (the same `seekTo` the track's tap uses) so the operator sees the frame; the press does not start
  playback.
- In the read view (where `timeline-view` shows the Timeline) the lane and strip show state but have no
  Approve, Dismiss or Restore: reading a screen never changes state. A **legend** under the lane spells out the
  icons and glyphs in words, because a mark too narrow for words shows only an icon and a glyph.
**Rationale**: one tab stop per clip keeps a long event from adding hundreds of stops; the strip puts the
decision on a real, labelled, touch-sized button, so the keys are an accelerator and not the only route.

### A and R act only on a focused mark

**Context**: A and R are letters; Edit mode has text fields (title, location, typed cut times).
**Explored**: the prototype binds `keydown` on the suggestion button (`Timeline.tsx` lines 81-82); the v1
Ctrl+S shortcut is a document listener (web-save-shortcut) because Save must work from any focus.
**Decision**: `keydown` on the mark only (the Timeline's own key handlers sit on the playhead grip and on
`.tl-viewport` for `+ - 0` only, and the mark does not bubble `a`/`r` to them). `suggestionKey(event)` is pure: it returns `approve` for `a`/`A` and
`dismiss` for `r`/`R` and nothing when Ctrl, Meta or Alt is held (Shift is ignored, as the key is a letter),
when the key repeats, or during an IME composition. `preventDefault` only when it returns an action. On a
dismissed mark `r` restores; on a cut mark `a` and `r` say that the suggestion is already cut and change
nothing. After a decision, focus stays on the same mark (the mark remains, its state changed); after Dismiss
the strip's selection stays so Restore is one press away. Never a document listener: typing "a" in the title
field cannot approve anything.
**Rationale**: the only way to make a single letter safe in a page with text fields.

### Announcements and the unsaved-changes model

**Decision**: every decision is said through Edit mode's one polite live region (`announce`), e.g. "Approved
black frames, 0:03.203 to 0:05, of a.mp4 as a cut; 1 cut added" or "Not approved: this overlaps cut 2 (0:04 to
0:06)". Outside Edit mode the lane has no decisions to announce. The save bar's counts (`cutChanges`) and the
unsaved-changes guard work unchanged because an approval is a `DraftCut`. Save writes `trims` with the
suggestion's kind as `reason`; the render is untouched.

### Gate seams

**Context**: the Timeline on main has no slot for a lane, the canvas has a fixed height, and Edit mode has no
Timeline. `timeline-trim` (parallel) adds `mode`, `cutsOf`, `onTrim`, `locked`, `announce` to the same
`Timeline` and the Edit-mode mount.
**Decision**: all new code is in `web/src/timeline/overlays/`. `Timeline` gains **one optional prop**,
`analysis?: AnalysisControl`, and calls `useSuggestions(analysis, {clips, lay, pps, seekTo, announce})` which
returns `{rows, lane, strip}`. `Track` gains **one optional prop**, `lane?: {rows: number; render(view): ReactNode}`,
drawn as a row after `.tl-lane` with the canvas `block-size` extended by `--tl-lane-h` (set from `rows`); the
view it hands the lane is `{clips, lay, pps, shown, windowFrom, windowTo}`. `rows` is the rows the whole track's marks stack to at this zoom (a pure `placeMarks`), so the canvas height does not
change as the window scrolls.
`Timeline` renders `strip` after its summary line. `AnalysisControl` is
`{eventId, cutsOf(identity) -> readonly {in, out}[], dismissals, decide: null | {onApprove(identity, span, kind),
locked, announce}}`:
- the read view builds it in `TimelineSection` from `read.cuts` with `decide: null`;
- Edit mode builds it in `timeline-trim`'s mount from the draft with `decide` wired to `cutHandlers.onAdd` and the
  editor's `announce` and `locked` (a save or a Move clips pending). If that mount is not on main when the
  decision tasks are reached, the task stops and says so (proposal, "Gates"); this change adds no second one.
- Absent `analysis`, `Timeline` and `Track` behave exactly as on main.
`edit/draft.ts` and `EventEditor.tsx` change only by the optional `reason` parameter. `EventDetail.tsx` changes
by the dismissal hook and passing its value down. This keeps the merge surface with `timeline-trim` to optional
props and a trailing optional argument.
**Rationale**: the lane needs the track's scale and window, the strip needs space outside the scroller, and
neither can be done from outside `Timeline` without a context that `timeline-trim` would also have to know.

## Failure behaviour, idempotency

- **Read failure**: a note; no lane marks; the timeline, Edit mode and Save are unaffected. Closing and opening the
  Timeline retries.
- **Approve refused**: nothing added, nothing dirty; the words say why. Approving the same pending suggestion
  twice cannot add two cuts: after the first, the state is `cut` and the second press is a no-op with a
  statement; two quick presses before the render are one `cut-add` because the reducer checks the key against
  `nextCut` and `checkCut` finds the overlap with the cut just added.
- **Save conflict (412)** and a gone event are v1's (`Saving an edit …`, `A failed save keeps …`); an approved
  cut is in the draft like any cut and survives them.
- **Cache changed under the page** (a re-run of `auto-reel analyze`, or a clip replaced): closing and opening
  the Timeline (which a Refresh does) re-reads the analysis; a dismissal whose segment no longer exists is
  dropped silently, one that still exists stays.
- **Worker/render/restart**: not involved; nothing is written until Save.

## Risks / Trade-offs

- **The shared seams.** `timeline-trim` runs in parallel and edits the same `Timeline`, `Track`, `timeline.css`,
  `EventEditor` and `cut-add`. The optional props and the trailing-optional `reason` keep conflicts to a few
  lines; task 1.1 re-reads main before any edit.
- **The Edit-mode mount is `timeline-trim`'s.** Without it approval is unreachable (the draft exists only in Edit
  mode). The decision tasks are therefore last and stop on its absence; the rest stands on `timeline-view`.
- **Many suggestions.** A freeze detector on a static shot can report many spans. Stacked rows and windowing
  bound the DOM; if a real library shows hundreds per clip, an "approve all of this kind" is the next change, not
  this one.
- **Dismissal is forgotten on reload.** Accepted and stated ("Dismissal is for this page visit only").
- **Unknown kinds.** A future ML kind is shown with its own name and a neutral icon, and approved with that
  string as the reason; `reasonWords` quotes it. The engine accepts any reason text.
- **Screen readers and colour contrast of the lane were not measured in the prototype** (`timeline-library.md`
  §2.2, "Not measured"). Task 4.2 measures contrast with the page's tokens; a real screen-reader pass is out of
  reach here and is said so in the result, not claimed.

## Migration Plan

None. Additive client behaviour; no data, schema or API change. Reverting the change removes the lane and
leaves every saved cut valid (the reasons are existing values).

## Open Questions

None blocking. Deferred, each a later change if a real library asks for it: persisted dismissal, bulk
approve, launching an analysis from the page.

## Deferred to the change that mounts the Timeline on Edit mode's draft

`timeline-trim` has not merged, so no Timeline is mounted in Edit mode and this change delivers the **read half**: the
lane, its states, the legend, the notes and the keyboard. The decision code is written (`decideApprove`,
`decideDismiss`, the hook's `apply` and `AnalysisControl.decide`) and tested as pure functions, but it is inert while
`decide` is null, and **the `web-app` requirements below are not part of this change**: syncing them to the specs
before the product meets them would make the spec claim what the page does not do. They are kept here, as they were
proposed, for the change that mounts the Edit-mode Timeline (it passes `analysis` with `decide` wired to
`cutHandlers.onAdd`, the editor's `announce` and `locked`, and the `Dismissals` value from `EventDetail`, which
`EventEditor` does not take yet). The same change owns the "A and R work on a focused mark only" and "Modified keys
are left alone" scenarios and the A / R paragraph of "Suggestions are operable by keyboard…", which `event-timeline`
here no longer states.

### Requirement: A suggestion is approved as a cut through Edit mode's draft

In Edit mode, a suggestion that is pending SHALL offer **Approve as cut** (a button in the detail of the
selected mark, and the **A** key on a focused mark). Approving SHALL add a cut to the clip's draft cuts, the
same way a typed cut is added ("Edit mode lists, adds and removes a clip's cuts"): the cut's start and end are
the suggestion's, to the nearest millisecond, and **its reason is the suggestion's kind** (`black`, `white`,
`freeze`, or the unrecognised kind as written). The cut SHALL take the key the next cut added in Edit mode takes
and SHALL be listed, counted in the save bar ("added" cuts), covered by the unsaved-changes guard, and written
by Save with the version check, like any cut; nothing SHALL be written before Save. The suggestion's state
SHALL then read cut.

Approving SHALL be checked as a typed cut is, and SHALL add nothing when the check refuses: a span that
overlaps a cut the clip lists now (a partly cut suggestion) SHALL be refused, naming that cut; a span that ends
after the clip's length, where the page knows it, SHALL be refused, and a span of under a millisecond SHALL be
refused. A refusal SHALL be shown in the detail and said through Edit mode's live region ("Not approved: …"),
and the suggestion SHALL keep its state. Approving a suggestion that is already cut SHALL change nothing and say
so. An approval SHALL be ignored, as the Cuts panel's is, while a save or a Move clips is in progress.

Outside Edit mode the page SHALL offer no way to approve and SHALL say, once, that Edit mode is where
suggestions are approved. Approving is announced through the live region with the kind, the span, the clip's
name and the number of cuts added.

#### Scenario: Approving by button

- **WHEN** in Edit mode the operator selects the "Black frames 0:00 to 0:03.2" mark on `C0012.MP4` and presses
  Approve as cut
- **THEN** the clip lists a new cut from 0:00 to 0:03.2 with the reason "Black frames", the mark reads cut, the
  region says "Approved black frames, 0:00 to 0:03.2, of C0012.MP4 as a cut; 1 cut added", and the save bar
  counts one added cut

#### Scenario: Approving then saving writes the kind as the reason

- **WHEN** the operator approves a freeze suggestion from 58.1 to 60 s and saves
- **THEN** the write carries that clip's trims with `{in: 58.1, out: 60, reason: "freeze"}` and the existing
  trims unchanged, with the version check, and no other part of the document

#### Scenario: Approving what a cut overlaps is refused

- **WHEN** a clip lists a cut from 0 to 1 s and the operator presses Approve as cut on a black suggestion from
  0 to 3.2 s
- **THEN** no cut is added, the detail and the region say "Not approved: this overlaps cut 1 (0:00 to 0:01)",
  and the mark still reads partly cut

#### Scenario: A span past the clip's end is refused

- **WHEN** a freeze suggestion ends at 60.04 s and the clip's length is 60 s
- **THEN** the approval is refused with the past-the-end wording the Cuts panel uses, and no cut is added

#### Scenario: Pressing twice adds one cut

- **WHEN** the operator presses Approve as cut twice in quick succession on one pending suggestion
- **THEN** the clip gains one cut, and the second press says the suggestion is already cut

#### Scenario: Reading does not approve

- **WHEN** the event page shows the timeline outside Edit mode
- **THEN** no mark offers Approve as cut, a single note says to open Edit mode, and pressing A on a focused mark
  changes nothing

#### Scenario: A conflict keeps the approvals

- **WHEN** the operator approves two suggestions, then Save is refused because `reel.yaml` changed (412)
- **THEN** both approved cuts stay in the draft and the save bar offers the choices it always does

### Requirement: A suggestion is dismissed for the page visit, never saved

In Edit mode, a pending suggestion SHALL offer **Dismiss** (a button in the detail, and the **R**
key on a focused mark), and a dismissed one SHALL offer **Restore** (the button, and **R**). Dismissing SHALL
mark the suggestion dismissed (its glyph, its word and its accessible name), SHALL be said through the live
region, and SHALL write nothing: it is not an edit, so it SHALL NOT enable Save, count in the save bar, or raise
the unsaved-changes guard. Dismissals SHALL persist while the page is open, across entering and leaving Edit
mode, a Refresh, a Save and the Timeline being closed and opened, and SHALL be forgotten when the page is
reloaded or left. The lane SHALL say so,
once, in words. A dismissal of a suggestion that a later analysis read no longer lists SHALL be dropped; the
others SHALL stay.

#### Scenario: Dismissing is not an edit

- **WHEN** the operator dismisses a pending suggestion and nothing else has changed
- **THEN** the mark reads dismissed with a `×`, the region says it, Save stays unavailable ("Nothing to save"),
  and leaving Edit mode raises no unsaved-changes question

#### Scenario: Restoring

- **WHEN** the operator presses R on a dismissed mark
- **THEN** it reads pending again and the region says it was restored

#### Scenario: Dismissals last the visit and no longer

- **WHEN** the operator dismisses a suggestion, presses Refresh, leaves Edit mode, enters it again and opens
  the Timeline
- **THEN** the suggestion still reads dismissed
- **WHEN** the page is then reloaded
- **THEN** it reads pending, and the lane's note said that dismissed suggestions come back on reload

#### Scenario: A cut outranks a dismissal

- **WHEN** a dismissed suggestion's span is then cut by hand over the whole span
- **THEN** its mark reads cut
