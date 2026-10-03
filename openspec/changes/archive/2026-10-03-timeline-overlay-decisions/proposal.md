## Why

`timeline-overlays` (merged) drew the analysis lane and wrote the decision rules, and `timeline-trim` (merged) mounted
the Timeline on Edit mode's draft. The two were designed to meet and have not: the lane takes an
`AnalysisControl` whose `decide` is **null in both modes**, so on `main` an operator sees black, white and frozen spans
in Edit mode and cannot approve or dismiss one. The pure rules exist and are tested (`decideApprove`, `decideDismiss`,
`suggestionKey`, `approval`, `addCut(..., reason)`, the `cut-add` action's `reason`, the page-level `useDismissals()`), and
the lane already renders Approve, Dismiss and Restore buttons and the A and R keys for a Timeline that is given a
`decide`. What is missing is the one wire, and the **requirements**: `timeline-overlays` deferred the approval and
dismissal requirements to the change that mounts them (its `design.md`, "Approval is `cut-add`, checked by
`checkCut`", "Dismissal is for this page visit only", "A and R act only on a focused mark", "Announcements and the
unsaved-changes model"; its spec says only "The lane SHALL offer no decision outside a Timeline that is given one").

The same review of `timeline-trim` left one known defect: in Firefox, with two cut handles whose press areas overlap,
a mouse press that is handed to the nearer handle, when that handle already holds focus, leaves the *other* cut
selected ("a mouse press handed to the focused winner selects the winner (Cut 2 of g1.mp4)", the only failure of
`ft3.py` in Firefox, 39/40, 44/44 in Chrome; the same failure before the multi-touch review fix, so not caused by it).
The same change that lets the operator approve with a click on a mark is the one that should leave the Timeline's
own selection sound in the browser the research made a first-class target (D-21: Firefox ≥ 155).

## What Changes

- **Approve and dismiss work in Edit mode.** `TimelineSection` builds `AnalysisControl.decide` from the Edit-mode
  binding instead of `null`: Approve (the detail's button, or **A** on a focused mark) adds the suggestion as a cut
  to the **draft** through the editor's `cutHandlers.onAdd`, with the suggestion's kind as the reason; Dismiss (button
  or **R**) records the dismissal in the page's set; Restore (button, or **R** on a dismissed mark) removes it.
  Save, Undo and Reset are the editor's, unchanged: an approval is a `DraftCut`, so it is one cut added in the save
  bar, `reel.yaml` gets a trim `{in, out, reason: black|white|freeze}`, and removing it, or Reset, returns the
  suggestion to pending. Announcements go through the editor's one live region; a pending save or Move clips locks
  the decisions as it locks the handles.
- **`EditBinding` gains `onAdd`** (the editor's `cutHandlers.onAdd`, which already takes a `reason`), and a pure
  `decideControl(editing)` in `timeline/overlays/control.ts` builds the `decide` value. The read view still passes
  `null`: reading a screen never changes state.
- **The requirements** `timeline-overlays` deferred are written into `event-timeline` (ADDED: approval, dismissal,
  the keys and buttons, the pending-state lock). The archived `design.md` is history and stays as it is.
- **The Firefox press-handover defect is fixed.** A press that a handle hands to a nearer handle selects, and leaves
  keyboard focus on, the handle that took it, in Chrome and Firefox, whichever handle held focus before. The cause,
  found by reproducing it, is a mouse press that Firefox delivers without pointer events under touch emulation: the
  press is now handed over by position as a pointer press is (a small pure rule with a test), and the case that failed
  in `ft3.py` passes in Firefox.
- **HLD** (D-20 "Analysis overlays", §4.10, §6 phase 9) and `web/README.md` stop saying that deciding is "to
  mount"; no D-21 change.

### Non-goals

- "Approve all of this kind", batch decisions, and a persistent dismissal (a `reel.yaml` field or `localStorage`):
  `timeline-overlays` listed them as the next change if a real library shows a need; nothing here changes that.
- Any change to what the lane draws or how a state is derived (`suggestionState`), to the model, to Save, to the
  write API, or to the engine. A cut approved here renders like any cut (no `RENDER_GRAPH_VERSION` bump: the reason
  is not a render input).
- Approving a **partly cut** suggestion as a remainder or merging with the overlapped cut (refused as a typed cut is).
- Ctrl+click or lasso selection of several marks.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `event-timeline`: ADDED requirements for approving, dismissing and restoring a suggestion in Edit mode (what each
  does to the draft, the page and the live region; the keys; the lock) and for a press that a handle hands over.

## Impact

- `web/src/timeline/TimelineSection.tsx`, `timeline/editing.ts` (type), `timeline/overlays/control.ts`
  (`decideControl`), `timeline/TrimHandle.tsx` and `timeline/handles.ts` (the press rule), `edit/EventEditor.tsx`
  (one field on the binding), with `node:test` files beside them. No dependency, no API, no schema, no Python.
- Docs: `docs/high-level-design.md`, `web/README.md`.
- Research relied on: `research/v2/timeline-library.md` §2.2 (the prototype's `decide`/`reduce` and its two defects:
  a stored state that read "approved" for footage still played, and truncated chips; the keys on the suggestion
  button, 22/22 checks in three engines), `synthesis.md` §5 (sequence), §6 (risks: a short flash at clip
  boundaries is accepted; nothing here touches it). Evidence for the Firefox defect: the `timeline-trim` verification
  logs (`verify/v2/timeline-trim/final-ft3-firefox.log`, 39/40) and its PR body, "Follow-ups".
