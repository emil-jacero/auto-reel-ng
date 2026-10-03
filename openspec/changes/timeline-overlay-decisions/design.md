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
page does not act on (locked, read view, a cut mark) is left to the browser (`preventDefault` only when acted on).
Never a document listener. This is `timeline-overlays`' design, now a requirement.

### The press rule: the winner's selection is final for the press

**Context**: two focus-related effects of one mouse press can disagree: the press handler selects the winner, and
the browser's own focus handling after a press may focus the element the pointer landed on (cut 2's start), whose
`onFocus` selects *its* cut. Chrome and a touch tap do not do the second thing here; Firefox's mouse press does,
after the pointer handlers have run.
**Explored**: (a) `preventDefault` on `mousedown` as well as `pointerdown` (a mouse-only guess that leaves other
paths open and cannot be tested without a browser); (b) re-select the winner on `pointerup` (a flicker: the wrong cut
is selected for the length of the press, and the Cuts fields are rebuilt twice); (c) one rule: a press that is handed
to a handle records the winner for the clip's layer; a `focus` event on **another** handle of that layer, arriving
while that press is still the latest (until the winner's pointer is released or cancelled, and one task after it),
does not select, and returns focus to the winner. Everything else is as before: Tab, a key and a programmatic focus
select the focused handle.
**Decision**: (c), after reproducing. The first task of the component work captures the order of `pointerdown`,
`mousedown`, `focusin`, `pointerup` and `click` with their targets in Firefox 155 and Chrome 154 on the `ft3.py` case
and writes it in the task result; the rule below is the one that is true whatever that order, and if the capture
shows a different cause (for example the capture target changing the compat events' target) the fix is made at that
cause, the requirement and the scenarios stand, and the rule is rewritten to match. The rule is pure:
`pressFocus(taken: string | null, focused: string): 'select' | 'winner'` in `timeline/handles.ts` (`taken` = the id of
the handle that took a press that is still in force, `null` otherwise; `'winner'` means the focus is not the press's
and goes back to the winner without selecting). `ClipHandles` holds `taken` in a ref set in `press` and cleared by the
winner's release, cancel or lost capture; `TrimHandle.onFocus` asks `pressFocus` before `onSelect`.
**Rationale**: the invariant is about the operator's intent (the handle that took the press is the one they hold) and
it is testable as a function of two ids; the browser order is not, and is checked by the Playwright case that failed.

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
- **The Firefox cause is inferred.** The mouse-only failure with a pointer-capture hand-over points at the browser's
  post-press focus; the first task proves it before the rule is written. The rule is cheap and safe if the cause
  turns out different, because it only suppresses selection by a focus event the press itself did not take.
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
