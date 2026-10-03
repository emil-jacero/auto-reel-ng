## 1. Gate

- [x] 1.1 Re-check, on `main` at implementation time, the seams this change builds on (design, "Context" and "Gate seams"; they were read off main d4e2a0b with `timeline-view` merged and `timeline-trim` not). Stop and report to the supervisor on any mismatch that changes scope, and re-base the delta if a landed requirement now says something about suggestions or analysis. Write down in the result where each of these sits now:
  - `git log origin/main --oneline | grep -E "timeline-view|timeline-model|timeline-trim"`; `ls web/src/timeline`; `grep -rn "analysis" web/src --include=*.ts --include=*.tsx | grep -v schema.d.ts` still finds only `cuts/times.ts`.
  - `Timeline.tsx` (props, `video.seekTo`, the playhead-follow effect), `Track.tsx` (the canvas rows and `visibleClips` window), `TimelineSection.tsx` (what mounts when), `timeline.css` canvas height; `events/EventDetail.tsx` (`ReadyView` and `EventEditor` mounts).
  - Whether `timeline-trim` has merged: if `Timeline` takes `mode="edit"` and `edit/EventEditor.tsx` mounts it, note its `cutsOf`, `locked` and `announce`; if not, tasks 3.1 and the read-view half of 3.2 and 4.1 proceed and the decision wiring of 3.2 stops there with a report (this change mounts no Timeline in Edit mode).
  - `edit/draft.ts` `addCut`, the `cut-add` action and `CutHandlers.onAdd` in `edit/EventEditor.tsx` (whether `timeline-trim` changed them), and `cuts/times.ts` `checkCut`, `refusalWords`, `reasonWords`, `formatTime`.
  - `docs/high-level-design.md` has a D-20 entry; if it does not, stop (task 5.1 appends to it).

  Verify: `openspec validate timeline-overlays --strict` passes on the re-based artifacts.
  - Done on main d4e2a0b: nothing had landed since the spec was written. `timeline-trim` has NOT merged (`Timeline` has no
    `mode`, `edit/EventEditor.tsx` mounts no Timeline), so the Edit-mode mount is absent; see the note under 3.2.

## 2. web/ — the read, the rules and the reason

- [x] 2.1 In a new `src/api/analysis.ts`, export `AnalysisResult` and `fetchAnalysis(eventId, signal)` shaped as `fetchEvent` is (`ok | problem | Unanswered`; statuses 200, 404 and 502 are published; rethrows `AbortError`), with type aliases into the generated schema (`AnalysisOut`, `SegmentOut`) and no re-declared shape. Add `src/api/analysis.test.ts` (`npm test`, as `thumbnail.test.ts` stubs `fetch`).
  - Cases: 200 with segments, 200 `analyzed: false`, 200 analysed with an empty list for one clip, 404 and 502 problem bodies, a 500 as `unpublished` (message names the request), a rejected `fetch` as `unreachable`, and an aborted request rethrown. The event id's segments are encoded one by one (an id with a space and a non-ASCII letter).

  Verify: `npm test` runs the new cases green; `git diff --stat -- web/src/api/schema.d.ts web/openapi.json` is empty.
- [x] 2.2 In a new pure `src/timeline/overlays/suggestions.ts` (type-only imports, runs under Node as it is), export: `suggestionState(cuts, segment, dismissed)` (design, "Suggestion state is derived"), `approval(listed, segment, length)` (calls `checkCut` with `formatTime(start)`, `formatTime(end)` and returns the cut or the refusal), `suggestionKey(event)` (`approve | dismiss | null`, design, "A and R act only on a focused mark"), `stackMarks(marks, pps, minPx)` (rows so that marks of at least `minPx` do not overlap; the row count for the lane's height), `neighbour(order, from, key)` for the roving order (previous, next, first, last; no wrap), `dismissalKey(identity, segment)`, `dropGone(dismissed, segments)`, and the words: `markName`, `stateWord`, `eventNote` (never analysed, analysed clean, per-clip "Not analyzed"), `approvedWords`, `dismissedWords`, `restoredWords`, `alreadyCutWords`. Add `suggestions.test.ts`.
  - State cases: no cuts → pending; one cut covering; two touching cuts covering the 0 to 3.2033333 span against cuts 0 to 1.5 and 1.5 to 3.203 → cut; a cut over part → partly cut; a removed cut ignored; overlapping cuts joined; dismissed with no cut → dismissed; dismissed then fully cut → cut; dismissed then partly cut → partly cut; a sub-millisecond segment → pending.
  - Approval cases: ok on a free span; overlap refused naming the cut's number; past the clip's end refused when the length is known and passed when it is not; a span of under a millisecond refused as `order`; an unknown kind passes through unchanged.
  - Key cases: `a`, `A`, `r`, `R` act; Ctrl, Meta or Alt held, a repeat and an IME composition do not; Shift alone does.
  - Stacking cases: marks 10 px apart at 44 px reach go to two rows; marks far apart share row 0; the row count is the maximum over clips.
  - Roving cases: Home, End, previous and next at both ends; and `dropGone` keeps a dismissal whose segment is still listed and drops the one that is not.

  Verify: `npm test` and `npx tsc --noEmit -p tsconfig.test.json` pass in the node:22 container.
- [x] 2.3 Give `addCut` in `src/edit/draft.ts` a trailing `reason: string = 'manual'` (the existing `'manual' satisfies KnownReason` becomes the default), let the `cut-add` action in `src/edit/EventEditor.tsx` carry an optional `reason`, and let `CutHandlers.onAdd(identity, span, reason?)` pass it on. No existing call changes. Add `src/edit/cutReason.test.ts`.
  - Cases: `addCut` with no reason still lists `manual`; with `'freeze'` lists `freeze`; `buildWriteBody` for that draft writes the clip's `trims` with `{in, out, reason: 'freeze'}` and the read trims unchanged; removing the added cut returns the draft to the read state (`settled`), so nothing is left to save.

  Verify: `npm test` green; `git diff -- web/src/edit/draft.ts web/src/edit/EventEditor.tsx` changes no existing call site and no class name.

## 3. web/ — the lane and its decisions

- [x] 3.1 In new `src/timeline/overlays/`, add `useAnalysis.ts` (reads once when the track mounts, never while the section is closed or preparing; the read in flight is aborted on unmount; a failure is a value), `useSuggestions.ts` (the hook `Timeline` calls: returns `{rows, lane, strip}`; `rows` from the pure `stackMarks` over all clips at the current `pps`), `SuggestionLane.tsx` (the group per windowed clip in its own canvas row, one roving tab stop, marks placed by `timeToPx(lay.startsMs[i] + ms, pps)`, 44 px hit area, stacked rows, kind icon and state glyph, the focused mark always rendered, ArrowLeft/Right/Home/End with an off-window mark reached by `seekTo` and the Timeline's own playhead-follow) and `overlays.css` (tokens only, no new colour literals, `prefers-reduced-motion` honoured, forced-colors outlines). Add the two optional seams: `Timeline` gets `analysis?: AnalysisControl` and renders `strip` under its summary, `Track` gets `lane?: {rows, render}` drawn as a canvas row with `--tl-lane-h` added to the canvas height; `TimelineSection` builds the read-view `analysis` (`decide: null`) from `read.cuts`, and `EventDetail` holds the dismissal set (`Dismissals.ts`). The lane's notes (never analysed, clean, per-clip "Not analyzed", reading, read failure as a `role="note"` `Alert`) go with it.

  Verify: `npx tsc --noEmit` and `npm run build` pass in the node:22 container; with `analysis` absent the Timeline renders exactly as on main (`git diff` of `Timeline.tsx` and `Track.tsx` shows only optional additions); the production bundle size before and after is recorded in the result (no new dependency: `git diff -- web/package.json web/package-lock.json` is empty).
- [x] 3.2 Add `SuggestionDetail.tsx` (the selected mark's strip: clip name, kind in words, span, length, state in words, Approve as cut, Dismiss or Restore, the refusal text) and wire it: selecting a mark moves the playhead to `onGrid(facts, start)` without playing; Dismiss and Restore change only the page-level set; in the read view no decision controls and one "Open Edit mode to approve" note. Then the decisions, in the Edit-mode mount found in task 1.1: Approve runs `approval(...)` with the clip's `facts.durationMs / 1000` as the length, then `decide.onApprove(identity, span, kind)` (the editor's `cutHandlers.onAdd(identity, span, kind)`), or shows and announces the refusal; `A` and `R` on a mark through `suggestionKey`; announcements through the editor's `announce`; presses ignored while `locked`.

  Verify: `npx tsc --noEmit`, `npx tsc --noEmit -p tsconfig.test.json`, `npm test` and `npm run build` pass; `grep -rn "addEventListener('keydown'" web/src/timeline/overlays` prints nothing (A and R are never a document listener); if the Edit-mode mount is absent the decision half is not written and the result says so.
  - Note (deviation, said in the result): `timeline-trim`'s Edit-mode mount is absent on main, so this change mounts no Timeline in
    Edit mode. The decision code itself (Approve through `approval`, A and R, announcements, the lock) is written against
    `AnalysisControl.decide` in `useSuggestions.tsx` and is inert while `decide` is null, which is what the read view passes; it was
    exercised in Chrome 154 and Firefox 155 through a throwaway harness (a local draft in place of Edit mode's, never committed).
    Whoever mounts the Timeline in Edit mode passes `analysis` with `decide` wired to `cutHandlers.onAdd`, the editor's `announce`
    and `locked`, and `useDismissals()`'s value from `EventDetail` (a prop `EventEditor` does not take yet).

## 4. Playwright in real browsers (scratchpad only, never in the repo)

- [x] 4.1 Functional run on `PORT` against a scratch dev library (`make_dev_library.py`; proxies prepared by `auto-reel proxies`; `auto-reel analyze` run on a scratch copy of events with a black start, a freeze and one clip left unanalysed), Chrome (`localhost/playback-research:chrome`) and Firefox ≥ 155 (check the image's version first and say which), with writes intercepted by routes on `**/reel` and `**/reel?*` only (record the body, fulfil with the real answer for the saves that should land). Assert:
  - a closed Timeline and a Prepare state make no `…/analysis` request (request log); the lane under each clip once the track is shown, the mark names from the proposal's scenarios, the three "no suggestions" wordings, and a fault-injected 502 on `**/analysis*` giving the note while the timeline works;
  - Approve by button then Save: one `PUT` whose clip `trims` hold the span with `reason: "black"` and the read trims unchanged, `If-Match` set; then a reload shows the suggestion as cut;
  - A and R on a focused mark; "a" typed in the title field approves nothing; Ctrl+A does nothing; a held A adds one cut;
  - overlap refused with the words and no cut added; removing the cut in the Cuts panel returns the mark to pending; a 412 on Save keeps both approvals;
  - dismiss, Refresh, leave and enter Edit mode, open the Timeline again: still dismissed; reload: pending; Save stays unavailable after a dismissal only;
  - in the read view: state shown, no decision controls, one note;
  - the Edit-mode half needs `timeline-trim`'s mount (task 1.1); without it that half is not run and the result says so.
    Done: the read-view half ran against the real build; the decision half ran against the throwaway harness (see 3.2), not against
    Edit mode (Save, `If-Match`, the 412 and the title field were not exercised; the write body is covered by `cutReason.test.ts`).

  Verify: the script exits 0 in both browsers; each assertion is in its output; no request other than reads and the intercepted writes reached the service (a log of method and path).
- [x] 4.2 Look at the result: light and dark at 1280 and 390, plus 320, with an event of about 10 suggestions on one clip; screenshots to `$SCRATCH`, each opened and described. Measure: `scrollWidth === clientWidth` for the page at 390 and 320; hit area of the narrowest mark ≥ 44 px; contrast of mark text, glyphs and the focus ring against their background in both schemes (≥ 4.5:1 text, ≥ 3:1 focus), computed from the page's tokens; `aria_snapshot` of one clip's lane (a `group` of `button`s with the names above); the same page with `prefers-reduced-motion: reduce` (computed `transition-duration` of the marks is `0s`); a grayscale screenshot (`filter: grayscale(1)`) showing kind and state still readable. Say that no screen-reader pass was run.

  Verify: the numbers and the opened screenshots are in the result; every threshold above holds, or the failing one is named and fixed before the task is ticked.

## 5. Docs and gates

- [x] 5.1 In `docs/high-level-design.md`, add to D-20 (timeline) a paragraph "Analysis overlays": the lane, state derived from cuts, approval as `cut-add` with the kind as reason through `checkCut`, dismissal for the page visit only and why, A and R only on a focused mark; one sentence in §4.5 that the GUI writes an approved suggestion as a trim whose reason is its kind; the §4.10 v2 bullet notes the analysis overlays landed (`timeline-overlays`) and what is left; §6 phase 9 stays open. In `web/README.md` add the new files to the tree and one sentence on the lane and its keys.

  Verify: `git diff --stat docs web/README.md` shows only those edits; the decision text matches the web-app delta (names, keys, the page-visit scope).
- [x] 5.2 Final gates in the node:22 container: `npm ci`, `npx tsc --noEmit`, `npx tsc --noEmit -p tsconfig.test.json`, `npm test` and `npm run build` pass; the rest of the checks: `git diff --stat -- auto_reel_ng tests web/openapi.json web/src/api/schema.d.ts web/package.json web/package-lock.json` is empty (no Python, API, schema or dependency change, so black, isort, mypy, pylint and pytest are unaffected, and `RENDER_GRAPH_VERSION` stays); `openspec validate timeline-overlays --strict` passes.

  Verify: all commands exit 0 and the diff stat prints nothing.
