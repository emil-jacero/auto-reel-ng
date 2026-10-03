## Context

State of `origin/main` (775f772, with `timeline-model`, `timeline-view`, `timeline-overlays`, `timeline-trim` merged and
archived), read from the code:

- **The lane already decides, given a `decide`.** `timeline/overlays/control.ts` defines
  `DecideControl {onApprove(identity, span, kind), locked, announce}` and `AnalysisControl {eventId, cutsState,
  cutsOf, dismissals, decide: DecideControl | null}`. `useSuggestions.tsx` applies `decideApprove` / `decideDismiss`
  (pure, in `suggestions.ts`, tested): `approve` calls `decide.onApprove`, `dismiss`/`restore` call
  `dismissals.dismiss/restore`, every outcome calls `decide.announce(words)`, a refusal is shown in the detail strip;
  `SuggestionDetail` draws **Approve as cut**, **Dismiss**, **Restore** only when `decide !== null`; `onMarkKey`
  handles **A**/**R** on the focused mark only (`suggestionKey`); `Notes` shows `DISMISSAL_NOTE` ("Dismissed
  suggestions come back when the page is reloaded.") only when `decide !== null`. All of this is dead on `main`.
- **The only place `decide` is built is `timeline/TimelineSection.tsx`**, and it sets `decide: null` for both modes
  (comment: "a later change decides"). In Edit mode it already builds `cutsOf` from `editing.listed(identity)`
  (the draft's cuts as the Cuts panel lists them, removed ones in place) and `cutsState: 'ok'`.
- **`EditBinding`** (`timeline/editing.ts`, built in `EventEditor.tsx` ~l.1358) carries `cuts`, `listed`, `onTrim`,
  `locked` (= `listsLocked` = a save pressed **or** a Move clips pending), `announce` (the editor's one polite live
  region), `orderChanged`, `previews`, `epoch`. It has **no way to add a cut**.
- **The editor's add path is complete.** `cutHandlers.onAdd(identity, span, reason?)` is stable (`useMemo`, dep
  `announce`), ignores a call while `pressed !== null` or `moving.current !== null`, and dispatches `cut-add` with
  `key = a${nextCut + 1}`; the reducer refuses a stale key. `addCut(baseline, draft, identity, span, key, reason =
  'manual')` stores the reason; `buildWriteBody` writes `trims` with `{in, out, reason}`; `cutChanges` counts it as an
  added cut; `settled` makes an added-then-removed cut leave nothing to save. `cutReason.test.ts` covers the draft
  half ("lists the kind it is given", "is written by the save as the clip's trim", "leaves nothing to save once the
  added cut is removed again").
- **Dismissals** live in `events/EventDetail.tsx` (`useDismissals()`, `overlays/Dismissals.ts`), above the read view
  and Edit mode, and reach the section as `dismissals`. Not an edit: nothing dirty, no Save, no unsaved guard.
- **The Firefox defect.** `TrimHandle.tsx` `ClipHandles.press` collects the handles whose area holds the pointer, picks
  `nearestHandle(pressPx, contenders, reach) ?? id`, and calls that handle's registered `begin(event)`, which does
  `setPointerCapture`, `target.focus({preventScroll})`, `onSelect(identity, cut.key)` for the **winner**. Every handle's
  `onFocus` also calls `onSelect` for **itself**. In `ft3.py` (`two_neighbours`) cut 1's end (winner) and cut 2's start
  are 4 px apart; with the winner already focused, the press lands on cut 2's start (on top), is handed to cut 1's end,
  and in Firefox cut 2 ends up selected (the Cuts-fields group reads "Cut 2 of g1.mp4"), whereas Chrome and the
  *touch* variants of the same test (a tap hands over, winner focused or not) leave cut 1 selected.

Research relied on (`research/v2/`): `timeline-library.md` §2.2, the prototype's `reduce`/`decide` and what its 22
checks in three engines proved for A/R on a button and for the touch size, and its defects 1 and 2 (state stored,
"approved" for footage a cut did not cover) which `suggestionState` already avoids; `synthesis.md` §3 (D-20: no
timeline library, plain CSS, `node:test`) and §6 (risks). No new measurement is needed: nothing here changes how
many elements the Timeline creates or how it scrubs, so the gates are re-run once, not re-derived.

## Goals / Non-Goals

**Goals**
- In Edit mode: Approve, Dismiss and Restore on the analysis lane, by button and by A and R, on the draft, with the
  editor's live region, lock and Save/Undo/Reset, and written requirements for them.
- The Timeline's press hand-over selects the handle that took the press in every supported browser.

**Non-goals**: see the proposal. Notably no second code path for adding a cut, no change to `suggestionState`, and
no decision in the read view.

## Decisions

### `decide` is built from the Edit-mode binding, in one pure function

**Context**: `TimelineSection` has the `editing` binding and builds the `analysis` value in a `useMemo`.
**Explored**: (a) build the object inline in the memo; (b) give the binding a `decide` ready-made from the editor;
(c) add `onAdd` to the binding and build `DecideControl` in a pure `decideControl(editing)`.
**Decision**: (c). `EditBinding` gains `onAdd(identity, span, reason?)`, filled with `cutHandlers.onAdd` (stable). In
`overlays/control.ts`: `decideControl(editing: Pick<EditBinding, 'onAdd' | 'locked' | 'announce'> | null):
DecideControl | null` returns `null` for `null` (the read view) and otherwise `{onApprove: editing.onAdd, locked:
editing.locked, announce: editing.announce}`. `TimelineSection` sets `decide: decideControl(editing)` and keeps
`editing` in the memo's dependencies as today.
**Rationale**: the editor stays the only owner of the draft (Principle II: `reel.yaml` is written by Save from the
draft; nothing here writes); the form `Pick<…>` keeps the function testable under `node:test` without importing a
component (`editing.ts` and `control.ts` are types only, `node --experimental-strip-types` reads them); the read view
cannot acquire a decision by accident because its binding is `null`. (b) would put Timeline-specific vocabulary in
the editor; (a) is untestable.

### Approval is the Cuts panel's add, nothing new

**Decision**: unchanged from `timeline-overlays` and now specified: `decideApprove` runs `checkCut(listed,
formatTime(start), formatTime(end), clipLength)` on the draft's listed cuts (removed ones counted, so the number named
in a refusal is the panel's), where `clipLength` is the proxy facts' `durationMs / 1000`; on `ok` the span, to the
millisecond as `formatTime` writes it, becomes `cutHandlers.onAdd(identity, {in, out}, kind)`. Nothing else is added or
changed: no merge, no remainder for a partly cut suggestion (refused: "Remove that cut first."). The reason is the
suggestion's `kind` verbatim (`black`, `white`, `freeze`, or a future kind), shown in the Cuts panel as the panel's
`reasonWords` writes it and saved as the trim's `reason`.
**Why no new guard against a double press**: `locked` covers a pending save and Move clips (the same two conditions
`onAdd` guards on, `pressed` and `moving`); a second discrete key or click re-renders first, so the mark reads `cut`
and `decideApprove` answers "Already cut"; `repeat` is ignored by `suggestionKey`; and the reducer refuses a second
`cut-add` carrying a stale key. There is no path on which "Approved" is announced and no cut is added; if one is found
while implementing, the task says so and stops rather than patching around it.

### Dismissal stays the page's set, and Restore is its undo

**Decision**: unchanged and now specified. Dismiss adds `identity|start|end|kind` to the set in `EventDetail`;
Restore removes it; a cut over any part of the span outranks a dismissal; a dismissal of a segment a new read of
the analysis no longer lists is dropped (`dropGone`). It survives entering/leaving Edit mode, Refresh and Save; reload
forgets it, and the lane says so once. It is not an edit: no dirty draft, no Save enabled, no unsaved-changes guard
(verified by the save bar staying hidden). While a save or a Move clips is pending it does nothing (`locked`), to match
the handles; this is a choice for consistency, and costs nothing as both pend for a moment.

### The keys and the buttons are one decision

**Decision**: `A`/`R` on a focused mark (Shift ignored; none with Ctrl, Meta or Alt, on a repeat or in an IME
composition) and the detail strip's buttons call the same `approve`/`dismiss`; focus stays on the mark; a key the
page does not act on (locked, read view) is left to the browser; one that says why nothing was done ("Already cut") has acted (`preventDefault` only when acted on).
Never a document listener. This is `timeline-overlays`' design, now a requirement.

### A mouse press without pointer events is handed over by position too

**Context**: the reproduction (task 2.2, Firefox 155.0 and Chrome 154.0.8037.92, the `ft3.py` `two_neighbours` case) showed
the original hypothesis, a browser focus *after* the pointer handlers, was not the cause. With a normal context Firefox
fires `pointerdown` (on cut 2's start, which lies on top), the press is handed to cut 1's end, `gotpointercapture` lands
on it, and cut 1 is selected: the same as Chrome. The failing case is the one `ft3.py` runs in a context with touch
emulation on (`has_touch`, `is_mobile`): there Firefox delivers a mouse press as `mousedown`, `mouseup` and `click` only
(no `pointerdown`, no `pointerup`, no capture), so `ClipHandles.press` never runs; the browser's own `mousedown` default
focuses the handle under the pointer (cut 2's start), and its `onFocus` selects its cut. Touch taps in the same context
do fire pointer events, which is why only the mouse step failed.
**Explored**: (a) guard `onFocus` against a focus the press did not take (the earlier design: a `taken` ref and a pure
`pressFocus`): useless here, as no press is ever taken; (b) fix the test harness only (use a non-touch context for the
mouse case): leaves a pointer-less mouse press, which a browser or an automation can deliver, handled differently from
every other; (c) hand a bare `mousedown` over by position as a pointer press is.
**Decision**: (c). `ClipHandles` records whether a pointer sequence is in progress (`pointerdown` captured on the layer
sets it, `pointerup` and `pointercancel` clear it). A `mousedown` on a handle when none is in progress and the button is
the main one (pure `bareMousePress(pointerSeen, button)` in `timeline/handles.ts`) is prevented (so the browser moves no
focus), and the handle that `nearestHandle` picks, the same way as for a pointer press, is focused and selected
(`Registered.choose`). No drag starts: nothing would move it. Locked, it is prevented and does nothing, as a pointer
press is. A secondary button, and a `mousedown` that follows a `pointerdown` still in progress, are the browser's.
Where pointer events exist the path is not strictly dead: a touch tap fires `pointerdown`, `pointerup` and only then the
compatibility `mousedown`, by when the sequence is over, so the path also runs there. It hands over to the handle that
the pointer press already took (`nearestHandle` gives the same winner), so it is idempotent; it is not relied on.
**Rationale**: the invariant is the operator's intent (the handle that took the press is the one they hold), and the
fix follows the cause the log shows; the position rule (`nearestHandle`) is reused, not copied. The pure part is what
can be tested under `node:test`; the browser order is checked by the Playwright case that failed.

## Failure behaviour, idempotency

- **Approve refused**: nothing added, nothing dirty; the words (the Cuts panel's own, "Not approved: …") in the
  strip and the live region. **Already cut / restore first / partly cut**: nothing changes; stated.
- **Locked**: the buttons are `aria-disabled`, a key is left to the browser, nothing is announced as done.
- **Save conflict (412), failed save, gone event**: the editor's; an approved cut is in the draft and survives them.
  After "Reload latest" the draft is rebuilt from disk: an approved cut already saved reads as `cut`, an unsaved one
  is gone and its suggestion is pending again, by derivation.
- **Reset**: the editor's; every approval since the last Save leaves with the draft, and dismissals stay (the set is
  the page's, not the draft's).
- **Leaving Edit mode**: the draft is the editor's, so the unsaved-changes guard applies as for any cut.
- **Worker, render, restart**: not involved; nothing is written until Save, which is the existing `PUT …/reel`.

## Risks / Trade-offs

- **A mark's key is a letter.** The only safe place is the mark itself; `A` in the title field decides nothing. A scenario
  and a Playwright check pin it.
- **Dismissal is forgotten on reload.** Accepted (stated in the lane, said once in the requirement); a persistent
  dismissal is a later change.
- **The Firefox cause is a pointer-less mouse press, found by reproducing.** The earlier guess (focus after the pointer
  handlers) was wrong and was dropped before any code was written. The fallback acts only on a `mousedown` that no
  pointer sequence is in progress, so for the real mouse in Chrome and Firefox it does not run. It does run, idempotently,
  on the compatibility `mousedown` that follows a touch tap (after its `pointerup`); it is a small defence against a
  delivery path, with a flag that is cleared by `pointerup`/`pointercancel`.
- **Some wiring is covered only by the browser run.** The repo has no component test runner (`node:test` only; vitest is
  out of scope). `analysisOf` (the binding to the lane's control) and `standingRefusal` are pure and tested;
  `ClipHandles.bareMouseDown`, `EventEditor` filling `onAdd` from `cutHandlers.onAdd`, and the Timeline passing the
  control on are checked only by the Playwright scripts, which live in `$SCRATCH`, not in the repo.
- **Two controls decide the same thing** (button and key). Both go through `approve`/`dismiss`; there is no second
  implementation to drift.
- **Screen readers and colour contrast of the lane** were not measured by `timeline-overlays` for the *decision*
  buttons; contrast of the buttons with the page's tokens is measured here in light and dark. A real screen-reader
  pass is out of reach and is said so in the result, not claimed.

## Migration Plan

None: no schema, API or stored data changes. A `reel.yaml` trim with reason `black`, `white` or `freeze` is already
valid, is already shown as "cut" by the lane, and renders as any trim.

## Open Questions

None. (Whether a future kind needs its own icon is the lane's existing neutral-icon rule.)
