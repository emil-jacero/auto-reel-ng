## Why

HLD §4.10 (v2) and §6 phase 9 say the full timeline editor ships with **analysis review built as overlays on that
timeline**, "approve black/white/freeze trims in place, not a separate screen". HLD §4.5 says detections are
**suggestions**: the operator approves or edits them, and approved ones become trims in `reel.yaml` with the
detection's kind as the reason (D-K: `black`, `white`, `freeze`; `manual` is a cut made by hand). Today nothing
in `web/` reads `GET /api/v1/events/{id}/analysis` at all (`grep -rn analysis web/src` finds only the reason
labels in `cuts/times.ts`), so an operator reviews dead footage only by running `auto-reel analyze` and typing
times into the Cuts panel (D-14).

This is the v2 sequence's row 12 (`research/v2/synthesis.md` §5). It builds on `timeline-view`, the read-only
timeline now on `main` (D-20: in-repo `web/src/timeline/`, React and plain CSS, no library), which lays out
clips from the proxy facts, windows its rendering and scrubs one `<video>`, and whose Timeline section loads
nothing until it is opened (spec `event-timeline`). The timeline research (`timeline-library.md` §2.2)
prototyped this lane and its accessibility result is the bar: suggestion marks as real buttons, A and R keys,
kind as text, state as a glyph and a word (`aria_snapshot`: suggestion `button`s inside `group "<clip>"`). Reading
the prototype's `reduce()` (`proto/src/model.ts`, action `decide`) found three defects this change must not
carry over:

1. **Approved without a cut.** `decide` with `approve: true` sets the suggestion's state to `approved` even when
   the span overlaps a cut and no cut was added, so the lane says "approved" for footage the movie still plays.
2. **A stored state that drifts.** The state is a flag on the suggestion; removing the cut it made (trim handle,
   Cuts panel, Undo) leaves the flag at `approved`.
3. **Colliding ids.** The new cut's id is `k${Date.now()}`; in v1 a cut's key comes from Edit mode's counter
   (`a${nextCut + 1}`, `EventEditor.tsx`), and this change uses it.

## What Changes

- **An Analysis lane on the timeline**, one row of suggestion marks under the clips' row, from the existing
  `GET …/analysis`. It is read **when the track is shown** (the section open and every proxy ready), never while
  the section is closed or preparing, because `timeline-view` guarantees a closed Timeline makes no request. A
  mark is placed from the timeline model's time-to-pixel mapping, windowed with the clips, and is a button named
  by kind, span and state.
- **State is derived, never stored.** A suggestion is **pending**, **cut** (the clip's listed cuts that are not
  removed cover its span to the millisecond, by one cut or by several joined) or **partly cut**, or **dismissed**
  (this page visit only). Removing the cut returns the suggestion to pending without any bookkeeping.
- **Approve** (button, or **A** on a focused mark) adds a cut through the existing Edit-mode draft: the
  `cut-add` action with the suggestion's span at the millisecond and the suggestion's **kind as the reason**.
  It is checked by the same `checkCut` the Cuts panel uses and is refused, in words, for an overlap with a
  listed cut or a span past the clip's end. Nothing is written until Save (`If-Match`, 412 handled as v1).
- **Where it works.** `timeline-view` mounts the Timeline in the read view only ("In Edit mode the page SHALL
  show no Timeline section"); the draft that approval needs exists only in Edit mode. The lane shows in both
  (state only in the read view, with one note that Edit mode is where suggestions are approved); deciding needs
  the Timeline in Edit mode, which is **`timeline-trim`'s mount** (its task 4.1, `mode="edit"`, cuts from the
  draft). This change does not mount it a second time (two mounts would conflict at archive); see "Gates".
- **Reject** (button, or **R**) dismisses the suggestion for this page visit; the set lives in the event page
  (`EventDetail`), above both the read view and Edit mode, because the Timeline section is closed again by a
  Refresh and by leaving Edit mode. Nothing is written: `reel.yaml`
  has no field for a rejection and the analysis cache stays read-only. It says so, and offers Restore.
- **State is never colour alone.** Kind is text plus an icon, state is a glyph and a word, in the mark's
  accessible name and in a detail strip that also carries the Approve and Reject buttons (the only route on
  touch and the one for assistive technology).
- **Honest empty states.** "Not analyzed" (no cache entry for the event or clip, with the `auto-reel analyze`
  command), "Analyzed, nothing found", and "Suggestions could not be read" (a note, the timeline stays usable).
- **Spec and docs**: ADDED requirements in `event-timeline` (the lane, keyboard and accessibility) and
  `web-app` (approval, dismissal); D-20 gains the analysis-overlay decisions; HLD §4.5
  and §4.10 notes; `web/README.md` file tree.

## Non-goals

- **No new endpoint, no write to the analysis cache, no analysis trigger.** `GET …/analysis` never runs
  analysis (api-service spec); starting one from the GUI is a later job kind, not this change.
- **No persisted rejection.** Dismissing is session-only (design, "Dismissal is for this page visit only"). A per-viewer `localStorage`
  memory or a `reel.yaml` field are later options, not built here.
- **No "approve all", no confidence display.** v1 stamps one coarse confidence on every segment (D-AN5), so
  there is nothing to rank by; no bulk action until a real library shows the need (Principle VII).
- **No trim handles, snapping or typed-time sync.** Those are `timeline-trim`'s, which runs in parallel;
  an approved suggestion is an ordinary cut that its handles edit.
- **No waveform lane, no reorder on the timeline, no proxy or API change.** No new runtime dependency.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `event-timeline` (added by `timeline-view`):
  - ADDED `Requirement: The Timeline shows the event's analysis suggestions beside its clips`
  - ADDED `Requirement: Suggestions are operable by keyboard and never shown by colour alone`
- `web-app`:
  - ADDED `Requirement: A suggestion is approved as a cut through Edit mode's draft`
  - ADDED `Requirement: A suggestion is dismissed for the page visit, never saved`

  All are additions (no existing requirement's text changes), so they cannot collide with `timeline-trim`'s
  MODIFIED blocks of "The event page offers a Timeline that loads nothing until it is opened" and "The track lays
  the clips out by their proxies' lengths, with the chapters and the cuts", nor with `clip-preview-proxy`'s
  edits of the preview requirements. "Edit mode lists, adds and removes a clip's cuts", "Saving an edit writes
  only what the operator changed" and "State is never shown by color alone" already say what a cut, a save and
  a status are, and the new text points at them.

## Impact

- **Packages (Principle VIII): `web/` only.**
  - `src/api/analysis.ts` (new) and `analysis.test.ts`: the read, as `api/event.ts` does it.
  - `src/timeline/overlays/` (new, own files so `timeline-trim` can run in parallel): `suggestions.ts` and
    `suggestions.test.ts` (pure: state, stacking, approval check, keys, roving order, words), `useAnalysis.ts`,
    `useSuggestions.ts` (the hook the Timeline calls: the lane, its height, the detail strip), `Dismissals.ts`
    (the page-level set), `SuggestionLane.tsx`, `SuggestionDetail.tsx`, `overlays.css`.
  - Small seams in files shared with `timeline-trim` and `clip-preview-proxy`, each additive and optional:
    `timeline/Timeline.tsx` (one optional `analysis` prop, the hook call, the strip under the track),
    `timeline/Track.tsx` (one optional `lane` prop drawn as a row of the canvas, plus the canvas height),
    `timeline/TimelineSection.tsx` (builds the read-view `analysis` value from the page's read cuts),
    `events/EventDetail.tsx` (holds the dismissal set above the read view and Edit mode),
    `edit/draft.ts` `addCut` (a trailing `reason`, default `manual`) with the `cut-add` action and
    `CutHandlers.onAdd` in `EventEditor.tsx` (an optional `reason`). Defaults keep every existing call unchanged.
- **CLI vs API (Principle V):** untouched. The behaviour is client-side and uses an existing read.
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump**; the staleness
  fingerprint inputs are unchanged (an approved cut is an edit to `reel.yaml`, which the fingerprint already
  covers, so saving one makes the event stale as any cut does).
- **Schemas:** no `reel.yaml` change (the `reason` field and values `black`, `white`, `freeze` exist), no
  `config.yaml` or API change, no Alembic migration, no rescan. `web/openapi.json` and `schema.d.ts` are
  untouched.
- **HLD:** D-20 (timeline) gets the overlay decisions; §4.5 and §4.10 notes (task 5.1). §6 phase 9 stays open
  (`timeline-trim` and the look editor remain).
- **Dependencies:** none new (Principle VII).
- **Gates:** `timeline-view` (merged: `web/src/timeline/`, spec `event-timeline`, archived
  `2026-10-03-timeline-view`), which itself needed `timeline-model`, `proxy-state-read`, `proxy-media-endpoints`
  and `proxy-enqueue-endpoint`. **Sequencing note for the supervisor:** approving and dismissing need the Timeline
  mounted on Edit mode's draft, which only `timeline-trim` (parallel, task 4.1) adds. This change is written so
  that everything except those decisions (the read, the lane, the strip, state in the read view) works on
  `timeline-view` alone, and so that the decisions are the last tasks; merging `timeline-trim` first lets the
  whole change be verified. Task 1.1 reads `main` and stops if the Edit-mode mount is missing when the
  decision tasks are reached, rather than adding a second mount.
- **Size:** two capability deltas (two ADDED requirements each), one package, 10 tasks.
