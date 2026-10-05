## Context

See proposal.md – Why. Evidence: `scratchpad/research/trim/code-model.md` (cited "CM §n"), `premiere-ux.md` ("UX
§n"), `zoom-perf.md`. Facts this design relies on:

- `trims` are removed spans; `[0, x]` is a start trim and `[x, ≥duration]` an end trim; overlapping or touching
  spans join into one removal; nothing in the engine, schema, writer, API or fingerprint needs to change (CM §1,
  §4 "Model choice").
- The Timeline's interior cut handles (`TrimHandle.tsx`, `handles.ts`, `model.ts trimLimits/snapTo/trimEdge`), the
  one-drag-at-a-time `dragStore`, the card edge drag with live re-layout (`CardHandles.tsx`, `ShiftFrom`) and the
  draft's `addCut`/`trimCut`/`removeCut` with `settled()` are the precedents (CM §2–§3).
- Gate `timeline-ripple-layout` (merged before implementation) lays each clip over its **kept extent** — from the
  end of a joined removed span that starts at 0 to the start of one that ends at the clip's end — with later clips
  sliding left, maps every time↔x path through it, and drops the handles of leading/trailing cuts. This change edits
  exactly those spans.
- Browsers: a custom cursor needs a keyword fallback, 32 px image, SVG with explicit width/height (UX §3 "Web
  mechanics", MDN `cursor`); touch has no cursor, so the edge needs a visible mark (UX §3).

## Goals / Non-Goals

**Goals:** a Premiere-looking edge tool whose result is an ordinary cut of the one draft; a pure, unit-tested model of
what an edge drag does; keyboard and typed alternatives; the existing gates (windowing, drag smoothness, schemes).

**Non-Goals:** rolling/slip/slide edits (UX §3: our boundaries are always shared, a roll is moot); a two-up trim
monitor or showing the new in/out frame in the video while dragging; snapping switch for interior cut handles or card
handles (stays as specified there; a follow-up may unify); a global undo stack; any engine/API change; the read view.

## Decisions

### D1 — An edge is the clip's leading or trailing cut, never a new field
A new `in`/`out` clip field would touch the document, schema, writer, editorial diff, API, segments, fingerprint and
the draft, and would be a second representation of a fact `trims` already holds (CM §4). The **edge cut** of a clip:
- leading: among cuts that are not removed and start at 0 ms, the one ending latest (first in list order on a tie);
- trailing: among cuts that are not removed and reach the clip's end (end at, past, or less than `END_SLACK_MS`,
  100 ms, before its duration: the gate's and Play's rule), the one starting earliest.
The edge's place is the clip's kept in-point (out-point): the end (start) of the joined leading (trailing) removed span,
the same value the gate lays the block out by. Reusing an approved `black` intro cut as the edge cut keeps its reason
(a trim never turns an analysis cut into `manual`, CM §2 "Draft edit").

### D2 — The edit is computed from the press-time cuts and the final place: add, trim, remove or nothing
Pure `edgeEdit(listed, edge, wantedMs, facts)` returns one of `{add span}`, `{trim key span}`, `{remove key}`,
`{none}`:
- place 0 (leading) or the duration (trailing) with an edge cut → **remove** it (an added cut drops out of the draft,
  a read cut is marked removed and its Cuts-panel Undo brings it back);
- otherwise, no edge cut → **add** `[0, x]` / `[x, duration]` with reason `manual`;
- otherwise → **trim** the edge cut to `[0, x]` / `[x, its own out]` (a cut read past the end keeps its out).
The editor applies it in **one reducer action** (`cut-edge`) through the existing `addCut`/`trimCut`/`removeCut`, so a
release is one edit, `settled()` still drops an edit that is reversed, Reset restores, and keys follow the existing
`a<n>` rule. Alternative rejected: `onAdd` then `onTrim` — two edits for one gesture, and a create-on-press would
write on a zero-move click.

### D3 — Joining follows the render's union, limits follow the played length
The block's in-point after a drag is the end of the union of `[0, x]` with every other live cut (touching joins), so
reaching an interior cut's start makes the edge **jump to that cut's end** ("Joined with cut 2"). The other cut stays
in the list unchanged (overlap is legal in the document, CM §1) — dragging back un-joins it, so nothing is lost and
the cut's reason survives. Limits: the lowest place is the end of the leading union formed by the other cuts alone
(0 in the normal case, the file's limit, drawn red); the highest is the last frame time at which the clip still
**plays at least three frames** (duration minus the union of all its cuts), the `minCutMs` rule turned around, and
still **has a kept extent** for the gate: `keptExtent` takes a span ending less than `END_SLACK_MS` (100 ms) before
the clip's end as a cut to the end (Play's rule), so a start trimmed into the last 100 ms would empty the block. On a
50 fps clip that is 5.92 s of 6.02 s, not the 5.96 s three frames allow (found when implementing; the scenarios say
5.92). A join that would break either rule stops the edge before the joined cut. An edge cut may be a single frame long (unlike
an interior cut's 3-frame minimum): trimming one frame off a start is the commonest edge edit.

### D4 — Leading drag anchors the block's left; trailing drag moves with the pointer
In a gapless track the block's left side sits on the previous clip's end. A leading drag keeps that side fixed: the
filmstrip slides so the first tile is the new in-point, the block narrows, and the block's end and everything after it
shift by the change (the gate's `ShiftFrom`-style transform, rendered on release). A trailing drag moves the block's
end with the pointer and shifts what follows the same way. The tooltip and bracket stay at the edge; the pointer's
distance moved is the change. Alternative rejected: let the left edge follow the pointer and close the gap on release —
the track would not show "the movie as it will play" during the drag, which is what the user chose.

### D5 — Hit zones live inside the block; nearest edge wins across all handles
Each edge's zone is inside its own block: 8 px on a fine pointer, 24 px on a coarse one, never more than a third of
the block's width, so the two zones at a boundary (Trim Out of the left clip, Trim In of the right) total 16 / 48 px
and a short block keeps a middle to scrub. The fine zone is below WCAG 2.5.8's 24 px; the "equivalent control"
exception applies (the focusable sliders and the typed fields). Presses where an edge zone and an interior handle's
area overlap go to the nearer edge (the existing `nearestHandle` rule extended with the clip edges); blocks under
`MIN_DETAIL_PX` (6 px) get no edge tool.

### D6 — Snapping: the existing 8 px rule, an edge-only switch
Candidates: the playhead (when in the clip), the clip's interior cut edges, and whole seconds of clip time
(`snapTo`, SNAP_PX 8, earlier on a tie). `S` toggles snapping for edge drags for the page visit and announces it; Alt
held bypasses it for that move. Kept edge-only so the interior handle and card handle specs stay as written.

### D7 — Cursor and colours
Two inline SVG brackets (Trim In `[` and Trim Out `]` with arrows), 32×32, hotspot on the bracket's stem,
`cursor: url("data:image/svg+xml,…") x y, ew-resize`. Bracket colour is a new token (amber/yellow, light and dark,
with an outline for contrast); the limit colour is the danger token. Shape and words carry the state, never colour
alone. During a drag the cursor is held on the track (class) so it does not flicker off the narrow zone.

### D8 — Save bar wording stays per cut
The save bar counts cut changes (`cutChanges`: added/trimmed/removed). An edge trim is a cut change and is counted as
such ("1 cut added" for a new start trim). The plan's "1 clip trimmed" wording was not adopted: classifying a trailing
cut needs the proxy duration, which the draft layer does not hold, and a second count for the same edit would make
the bar disagree with the Cuts panel. The release announcement carries the clip-level words ("s1710001.mp4 start
trimmed by 0.5 s, plays 0:03.02").

## Risks / Trade-offs

- [Gate lands with different names] → Task 1.1 reads the merged gate first and reuses its kept-extent function;
  `edgeTrim.ts` must not compute a second layout.
- [Edge zones crowd interior handles near a block edge] → one hit-test over edges and handles, nearest wins; tested
  in `handles.test.ts` and Playwright.
- [Live ripple drag on 80 clips is slow] → reuse the card drag's transform (no React re-layout per frame); measured by
  the existing ≤ 2 % frames over 25 ms gate at 4× throttle.
- [Firefox ignores the SVG cursor] → the `ew-resize` fallback plus the visible bracket; the Playwright check reads the
  computed style in both browsers.
- [A join hides an interior cut's handles while it is inside the leading span] → it is not drawn because it is not
  played; dragging back shows it again; the Cuts panel still lists it.

## Migration Plan

None: no stored data changes; `reel.yaml` files with leading/trailing cuts already render and display (gate).
