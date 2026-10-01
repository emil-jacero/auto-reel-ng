## Supervisor decisions (2026-10-01)

- An overlapping cut is **refused, not merged**, consistent with the `reel-document` spec's
  "non-overlapping" ("What a cut must satisfy"). Merging remains the alternative the user may still choose.
  Aligning the engine (which merges at render) and the spec on overlaps is a follow-up.
- A GUI cut is saved with `reason: manual`, shown as "Cut by hand": **accepted**.
- The read view uses a second `GET …/reel` (web-only), with no `ClipOut` change: **accepted**.
- No probe-free clip duration exists, so a cut past the clip's end is not refused in the GUI (the render
  clamps it). A duration field on `ClipOut` is a follow-up API decision (Open Questions).
- A cut over a chapter's whole title clip drops that chapter's title card at render: an **engine
  follow-up**; the panel copy stays as designed (Risks).
- `exclude: true` is not shown in the GUI: pre-existing, **follow-up** (Risks).
- `make_dev_library.py`'s indentation: normalised in the tasks (as now); aligning the script with
  `reel/writer.py` is a **follow-up**.
- Re-based on main `d631b7c` (G1 archived, with its review fixes): the MODIFIED requirement's text differs
  from the landed one only by this change's cut edits; every G1 name this design uses landed unchanged
  (task 1.1); the line numbers below were refreshed.

## Context

See proposal.md, "Why". This change starts from main **after** `chapter-management-screen` (G1) is archived.
It builds on G1's draft model as G1's design states it: `Draft`, `Baseline`, `writtenFromView(baseline,
draft)`, `buildWriteBody(baseline, draft)`, chapter keys, `keptOriginal`, and the `.dialog-fields` split. Line
numbers below are from main at `d631b7c` (G1 and its review fixes landed). The gate task (1.1) re-checked every
name G1 landed.

**Engine and API facts** this design rests on. Each was checked in the code. Where marked, it was also checked
by real `PUT`s against a scratch `serve` on port 8191 with its own database `arel_spec_clip_cuts_screen`
(`put_probe.py`), by calling the engine directly, or by measuring main's build with Playwright
(`measure.py`, `measure2.py`). All of these live in the session scratchpad under
`g-spec/clip-cuts-screen/`, are never committed, and the database was dropped afterwards.

| Fact | Where | Checked |
|---|---|---|
| `PUT …/reel` takes `clips: {identity: {trims: [{in, out, reason?}], title?, rotate?, exclude}}`. `TrimBody` is `{in, out, reason}`, `extra="forbid"`. The generated `TrimBody` type is `{in: number; out: number; reason?: string \| null}` | `api/schemas.py` 157-216, `web/src/api/schema.d.ts` 811-818 | code |
| An unmodified round trip writes nothing | `event/editorial.py` 273-302 | PUT: bytes equal |
| A span is refused when `out <= in`, a time is negative or not a number. Overlapping, unsorted and arbitrarily long spans are accepted | `reel/schema.py` 160-180, 345-358 | PUT: `out == in`, `out < in`, `in: -1` → 400 (`failure: null`); overlap, unsorted, `out: 99999` → 200 |
| Properties for a clip no chapter lists are refused ("dangling clip properties") | `reel/schema.py` 245-282 | PUT: a cut on Badutflykt's NEW `s1710004.mp4` → 400 with chapters as read, 200 once its chapter lists it |
| A clip's `trims` list is rewritten whole when its content changes: its other spans keep their values but lose flow style and end-of-line comments, and `in: 0` reads back as `0.0` | `event/editorial.py` 273-302 | PUT: `{in: 0, out: 1.5, reason: black}  # dark start` became block style without its comment |
| `trims: []` on an entry with nothing else leaves `identity: {}` in `reel.yaml`, and an entry left out of the body is removed | `event/editorial.py` 235-271 | PUT |
| `title` and `rotate` survive a trims change, and so do values like `62.35` and `3723.5` exactly | `event/editorial.py` 256-271 | PUT |
| A cut is removed footage. The render sorts the spans, clamps each to `[0, duration]`, merges overlapping or touching ones, and keeps the rest. A cut past the end is cut short silently, a cut wholly past the end removes nothing, and a cut over the whole clip leaves the clip with no segment | `render/segments.py` 131-158, D-D | engine: `kept_spans` on `[5,100]`, `[7,9]`, `[0,6]`, `[0,3]+[2,4]`, `[0,2]+[2,4]` over 6 s |
| The detail is probe-free: a clip carries `identity`, `status`, `size`, `mtime`. No read gives a duration (`/analysis` gives detected segments only, and the thumbnail route probes internally and returns a JPEG) | `api/schemas.py` 30-50, 231-249, `api/routes/events.py` 308-378 | code |
| `trims.reason` is an open string, and `black`, `white`, `freeze` and `manual` are its documented values | D-K (`archive/2026-06-02-reel-yaml-editorial-model/design.md` 116-118), `reel/document.py` 39-55 | code |
| The dev library's clips are 6 s long | `scripts/make_dev_library.py` 46 | code |
| The dev library writes `reel.yaml` with ruamel's default indentation (`_edit_title`, `_ignore`). The engine's writer (2/4/2) re-indents the whole chapter list on its first real write, a cut included. Task 4.1 normalises the copies first | `scripts/make_dev_library.py` 142-157, `reel/writer.py` 28-35 | engine: a Grillning-style file, one cut added |

Three facts shape the design most. First, **the engine never sees a clip's length when it saves a cut**: a cut
past the end is cut short at render time, never refused. So "let the engine fail loud" is not available. The
page can only validate what it knows, and must say what it cannot check. Second, **a cut on a NEW clip needs
its chapter written**, or the save is refused. Third, **a changed clip's other cuts lose their formatting**,
which is an engine trait this change states but does not fix.

**Edit mode's rows today:**

- `ClipOrderList.tsx`. `ClipRow` (240-344) renders, in order, the handle, `RowBody` (position, thumbnail,
  file with its badge, `ClipFacts` with the row's action) and `MoveButtons`. `IgnoredRow` and `RemovedRow`
  have no controls. `nameOf` names every clip as the read view's table does.
- `edit.css` 203-212, 287-302 and 454-505. Wide rows (from 58rem) are one grid line, two when the row has an action:
  a missing clip's Remove in area `action`, under the name. Narrow rows are `'handle pos thumb file moves' /
  '. . thumb facts facts'`, or `'handle pos file file moves' / '. . thumb facts facts'` below 30rem. The two
  cells under the handle and the position are **empty** on the second line.
- `EventEditor.tsx` holds `dateIncomplete`. A date typed only in part counts as unsaved, is named in the
  save bar ("date incomplete") and holds Save back (`SaveBar.tsx` 84-91, `EventEditor.tsx` 134, 1378-1389, 1652).

**The read view** (`EventDetail.tsx` 429-615) reads only the event detail, which carries no cuts.

## Goals / Non-Goals

**Goals:**

- List, add and remove a clip's cuts with typed times, from the keyboard, at 320 px, by touch, in Edit mode.
- Show each clip's cuts on the event page.
- Validate everything the client can know, say plainly what it cannot, and never send a body the engine
  refuses.
- No row grows on a phone while every panel is closed. Typing in a cut field re-renders no list.

**Non-Goals:**

- No engine, API, schema or dependency change. No change to chapter structure: G1 owns chapter keys,
  `chapterChanges` and the tools row, and this change touches none of them.
- No editing of a cut in place, no reason field, and no per-cut history beyond Undo and Reset.

## Research & Decisions

### Where the Cuts control sits

**Context**: G1 kept the row's first line free of a per-row control so that this change could have one (G1
design, "Moving clips: one dialog per chapter"). Every row is in a 400-clip-capable list, and the existing
spec bounds a missing clip's row at 390 px to "at most 8 pixels taller" than an included one's.

**Explored**: `measure.py` and `measure2.py` opened Edit mode on main's build (two events, 320 / 390 / 768 /
1280 px) and injected a compact button in two candidate places, measuring each row's height before and after:

| Place | 320 | 390 | 768 | 1280 |
|---|---|---|---|---|
| In the row's action slot (`ClipFacts`, after the time) | +30 px every row | +5 (included), +30 (new) | +4 | 0 |
| Grid row 2, columns 1-2 (the empty cells under the handle and position) | **0** | **0** | +4 | n/a (wide) |

In the wide layout, area `action` under the name adds 0 px at 1280. A 72 px thumbnail already sets the row's
height there. At 58-64rem, with a 45 px thumbnail, it adds a few pixels.

**Decision**: One `button.cuts-toggle`, a direct child of `li.clip-item` after `MoveButtons`, followed by the
panel (when mounted). Both are placed by grid area, so their DOM order does not move them:

- **Wide (container ≥ 58rem)**: in grid area `action`, under the name. It shows the scissors icon, the words
  ("Cuts", or "2 cuts · −4.5 s") and a chevron. A missing clip, the only row whose action is Remove, has no
  toggle, so the two never share the area.
- **Narrow (< 58rem)**: at `grid-row: 2; grid-column: 1 / 3`, under the handle. It shows the scissors icon and
  the count when there is one ("✂ 2"). It is at most 64 px wide (2rem + gap + 1.5rem); "✂ 123" measures about
  60 px.

**Rationale**: The narrow cells are empty space today. The wide line gives the words room. Tab order is
handle → Move up → Move down → Cuts → the panel (when shown). In both layouts that is the row's first line,
then its second, and the disclosure's content comes straight after its button. With the toggle before the
move buttons, a narrow row's Tab would go down to the toggle and back up to the moves.

### A disclosure under the row, not a dialog

**Explored**: (a) a Cuts dialog per clip, like G1's Move clips. (b) A panel under the row.

**Decision**: (b). `aria-expanded` on the toggle, and `aria-controls` once the panel is mounted (never an id
that is not in the page). The panel sits in the same `li` on a grid row of its own (`grid-row: -1 / span 1`,
after the explicit lines). It spans the whole row when narrow, and runs from `file-start` to the end when
wide. The panel is mounted on first open, and then only hidden (`hidden`) when collapsed. Rows never opened
mount nothing.

**The panel's state lives in the editor, not in the row.** G1's Move clips moves a row into another chapter's
`ClipOrderList`, which React mounts anew, so `useState` in `ClipRow` or `CutsPanel` would be lost on a move,
and a typed cut with it, while the editor's `typed` still held Save back with no visible text to clear. The
editor therefore owns `panels: useRef(new Map<string, PanelState>())`, keyed by identity:

```ts
type PanelState = { open: boolean; start: string; end: string }
/** Stable for the editor's life; reads and writes never re-render anything. */
type CutPanels = { get(identity: string): PanelState | undefined; set(identity: string, next: PanelState): void }
```

`ClipRow` takes its initial `open` from it and writes it on each toggle. `CutsPanel` takes its initial fields
from it, keeps them as local state for rendering, and writes them back on each change. A panel is mounted when
`open` is true or the store has an entry. Reset clears the map before it bumps `resets`. Leaving Edit mode
unmounts the editor, and the map goes with it.

**Rationale**: Cuts are about one clip. The panel keeps its name, thumbnail and position in view, and needs
no focus trap. A dialog would hide the row it edits, and would make "typed but not added" a dialog-close
question. The panel moves with its row on a reorder, since it is part of the sortable `li`, and dnd-kit's
activator is the handle only (`ClipOrderList.tsx` 314-323), so typing Space in a field never lifts a row.

### Times: forms, parsing, writing

**Decision** (`cuts/times.ts`, pure, type-only imports):

```ts
export type Trim = components['schemas']['TrimBody']          // { in: number; out: number; reason?: string | null }
export type TimeRefusal = 'empty' | 'unreadable' | 'too-precise'
/** A typed time, in whole milliseconds. */
export function parseTime(typed: string): { ok: true; ms: number } | { ok: false; refusal: TimeRefusal }
export function formatTime(seconds: number): string           // 0:00 · 0:01.5 · 1:02.35 · 1:01:15.5
export function formatLength(seconds: number): string         // 1.5 s · 59.999 s · 1:00 · 1:02.5
export function spokenLength(seconds: number): string         // 1 second · 1.5 seconds · 1:02.5
/** The time cut out: the union of the spans, merged as the render merges them. */
export function cutOutSeconds(cuts: readonly Trim[]): number
```

- Accepted (after `trim()`): `^(?:(\d+):([0-5]\d):([0-5]\d)|(\d+):([0-5]\d)|(\d+))(?:[.,](\d+))?$`. A
  fraction of more than three digits is `too-precise`. Anything else is `unreadable`, including a sign,
  `1:5`, `1:60` and `1.2.3`. Hours and minutes of any size are accepted in their leading place (`90:00` is
  5400 s).
- **Parsing to whole milliseconds**, then `ms / 1000`. `0:58.1` → 58100 → 58.1, the nearest double to 58.1.
  Adding 58 and 0.1 as floats could land one ulp off, and the body would then carry `58.099999999999994`. All
  comparisons of typed times use these values. Read values are kept exactly as read (an analysis cut may hold
  `3.2033333`), and written back unchanged.
- **Writing**: round to whole milliseconds, `m:ss` below an hour and `h:mm:ss` from one, then `.` and the
  fraction with its trailing zeros removed. A length under 60 s is `1.5 s`. The two writers never disagree:
  both go through one `parts(ms)` helper.

**Rationale**: These are the forms a person reads off a player. The comma is there because the operator's
locale writes `1,5`. `type="text"` with no `inputmode`: `inputmode="decimal"` hides the colon on iOS
keyboards, and every accepted form but plain seconds needs it.

### What a cut must satisfy

**Context**: The engine refuses `out <= in` and negative times, and nothing else. The render clamps to the
clip's length, which no read gives (Context).

**Decision**: `checkCut(listed, typedIn, typedOut)` refuses, in this order:

1. the start, then the end, when it is `empty`, `unreadable` or `too-precise` (focus to that field)
2. an end not after the start (`order`, at the end field)
3. a span sharing more than an instant with a listed, not-removed cut of the clip: `newIn < c.out && c.in <
   newOut` (`overlap`, at the start field, naming the first such cut by its number and times)

Touching spans (`[0, 1.5]` then `[1.5, 2]`) are accepted. A cut past the clip's end is accepted, and the panel
states the render's rule (copy below).

`checkRestore(listed, key)` applies rule 3 to an Undo: the removed cut's span against every other listed,
not-removed cut. Without it, removing a read cut, adding one inside its span and pressing Undo would build
an overlap that the page refuses everywhere else. A refused Undo keeps the cut removed and focus on Undo. Its
words are shown in a `p.cut-refusal` in that cut's row (the Undo's `aria-describedby`) and announced once, and
they go at the clip's next cut edit or Reset.

**Rationale**: (1) and (2) are exactly the engine's refusals, so the GUI never sends a body that is refused for
a cut. (3) follows the `reel-document` spec ("A clip MAY have multiple non-overlapping spans"). The parser does
not enforce it, but merging silently would rewrite a cut the operator did not touch and drop its reason (for
example an analysis `black` cut). Refusing names the cut to remove first. Overlaps already in `reel.yaml` are
shown as read, and the total counts their union. The **length check** waits for a duration source (Open
Questions). Refusing nothing about length while saying what the render does is the honest option.
Fabricating a limit from the dev library's 6 s, or from a guess, is not.

### The reason of a cut made here

**Decision**: An added cut is sent with `reason: 'manual'`. Reasons are shown in words through
`CUT_REASON_LABEL: Record<KnownReason, string>` over D-K's four documented values: `black` "Black frames",
`white` "White frames", `freeze` "Frozen picture", `manual` "Cut by hand". Any other string is shown as written
in quotes (“sunset noise”). An absent reason shows "—".

**Rationale**: `manual` is the documented value for a hand-made cut. Writing it keeps a GUI cut apart from an
analysis one when v2's review lands. The reason is an open string (D-K), so the map covers the documented set
and falls back to the operator's own text. That text is free text, not a slug, so the "never render a slug"
rule does not apply to it. The name is `CUT_REASON_LABEL`, not `REASON_LABEL`, which `events/labels.ts`
already exports for the staleness reasons.

### Removing a cut

**Decision**: A cut read from `reel.yaml` stays listed, struck through, with a "Removed when you save" badge
and **Undo**. A cut added in this Edit mode is dropped. This is the pattern G1 uses for chapters (read ones
stay with Undo, added ones go) and `missing-clips-screen` uses for clips.

**Rationale**: Re-typing a removed read cut would give it the reason `manual` instead of `black`, so an Undo is
the only exact way back, and with it a remove and an Undo leave nothing to save.

### The draft model

**Decision** (`edit/draft.ts`, still type-only imports):

```ts
/** `r0`, `r1`… a cut read (its index in reel.yaml's list); `a1`, `a2`… one added in this session. */
export type CutKey = string
export type DraftCut = { key: CutKey; in: number; out: number; reason: string | null; removed: boolean }
/** Identity → its cuts as listed now, in order; only the clips whose cuts the operator changed. */
export type Cuts = ReadonlyMap<string, readonly DraftCut[]>

export type Draft = { /* G1's chapters, orders, removed, metadata */ cuts: Cuts }
export type Baseline = { /* G1's read, chapters, original */ cuts: ReadonlyMap<string, readonly DraftCut[]> }

export function readCuts(read: ReelDocument): ReadonlyMap<string, readonly DraftCut[]>   // Baseline.cuts, built once
/** Takes the two maps, not `Draft`, so a list's props never change on a metadata edit ("Performance"). */
export function cutsOf(
  base: ReadonlyMap<string, readonly DraftCut[]>, changed: Cuts, identity: string,
): readonly DraftCut[]
export function addCut(baseline: Baseline, draft: Draft, identity: string, span: { in: number; out: number }, key: CutKey): Draft
export function removeCut(baseline: Baseline, draft: Draft, identity: string, key: CutKey): Draft
export function restoreCut(baseline: Baseline, draft: Draft, identity: string, key: CutKey): Draft
/** The clips whose saved cuts would differ from the read ones; removed clips excluded. */
export function changedCuts(baseline: Baseline, draft: Draft): ReadonlySet<string>
export function cutChanges(baseline: Baseline, draft: Draft): { added: number; removed: number }
```

- `cutsOf` returns the draft's list, or else the baseline's. Both are stable references, which keeps the
  memoised rows still.
- `addCut` inserts `{reason: 'manual', removed: false}` after the last listed cut whose `in` is `<=` the new
  `in` (removed ones count, so a struck cut keeps its place). It does not re-check. `checkCut` ran in the
  panel against the same `cutsOf`. `restoreCut` likewise trusts `checkRestore`, run in the panel first.
- After every operation, a clip whose list equals its baseline list (same keys, none removed) leaves
  `draft.cuts`. So `isDirty` needs no special case for "added then removed" or "removed then Undo".
- **`isDirty`** adds `changedCuts(…).size > 0`. "Equal" compares `in`, `out` and `reason ?? null` of the
  not-removed cuts, in order, against the read `trims`.
- **`writtenFromView`** (G1's one helper for `isDirty`, `adoptedNewCount` and `buildWriteBody`) gains one
  predicate. A chapter is also written from the view when it plays a clip in `changedCuts` that **no chapter of
  the read document lists** (a NEW clip). When the document names no chapters, G1's rule writes every chapter
  on any change of order or chapter, and now on any cut change too. The count and the body therefore keep
  coming from one function.
- **`buildWriteBody`**'s `clips`: G1's map (the read one, less removed identities, moved clips' entries kept),
  then, for each identity in `changedCuts`:

  ```ts
  const trims = cutsOf(baseline.cuts, draft.cuts, id).filter((c) => !c.removed)
    .map(({ in: start, out, reason }) => ({ in: start, out, reason }))
  const entry = baseline.read.clips[id]
  if (entry !== undefined) {
    if (trims.length === 0 && entry.title == null && entry.rotate == null && !entry.exclude) delete clips[id]
    else clips[id] = { ...entry, trims }
  } else if (trims.length > 0) {
    clips[id] = { trims, exclude: false }
  }
  ```

  So no empty `{}` entry is written (Context), and `title`, `rotate` and `exclude` go back as read.
  Every key is listed by a written chapter. Read keys were listed and stay listed, since G1 never drops a
  played clip. A NEW clip's key is listed because its chapter is now written from the view.

**Rationale**: Identity-keyed, as `clips` is. A clip moved by G1's Move clips keeps its draft cuts, and a
missing clip's removal drops its entry whatever its cuts (G1's rule). One `Cuts` field, one merge step and one
trigger in `writtenFromView`, the extension points G1's design names (G1 design, "Files and the G2 seam").

### A cut typed but not added

**Decision**: The editor keeps `typed: ReadonlySet<string>` in `Ready`: the identities of the clips whose
panel fields hold any non-space text. It holds **no name**. It is not part of `Draft`: it is never saved. A
panel dispatches `cut-typed {identity, typed}` when "has text" flips. A row that Move clips remounts keeps its
entry, since unmounting dispatches nothing and the panel store still holds its text.

The clip's name is resolved **when `summarize` runs**, from the draft as it is then: the chapter that now
holds the identity, its current name, and the same `clipNames` inputs `ClipOrderList`'s `nameOf` uses (G1
design, "Counts, badges": name now, original, order, ignored, removed). So the bar names the clip as its row
does whatever renamed it: a move to `Main` (`Kvällen/s1710002.mp4`), a chapter rename (`Kvällen` → `Kväll`
makes every row of that chapter a path, without remounting anything, since lists are keyed by `chapterKey`),
or a clip from another folder moved in. It is only computed while `typed.size === 1`, over one chapter.
While `typed` is non-empty:

- the event is dirty: `afterEdit`'s and the editor's `dirty` both add `typed.size > 0`, so the unsaved
  guard holds and a past failure is not retired
- `summarize` adds "cut typed on s1710001.mp4, not added" (the name resolved as above), or "cuts typed on 2
  clips, not added", in the order of "Copy"
- Save is unsendable. `SaveBar`'s prop `dateIncomplete` is renamed `unfinished` and passed
  `dateIncomplete || typed.size > 0`, with no other change to `SaveBar`. It already describes an unsendable
  Save by the summary, and passes the same flag to the conflict's Overwrite with mine and to Retry (`blocked`).
- `submit` refuses on the same flag (today `ready.dateIncomplete`), so no path sends a body without the typed
  cut

Reset clears the panel store, then bumps `resets`, which already keys the fields. The panels are keyed by it
too, so their text empties, and `typed` empties with it.

**Rationale**: The operator who types `0` and `1.5` and then presses Save expects a cut. Losing it silently is
the classic form bug. This is the rule the date field already follows.

### The Edit-mode toggle and panel

`cuts/CutsPanel.tsx` exports `CutsToggle` and `CutsPanel`, both `memo`. `ClipRow` keeps `open`
(`useState`, seeded from and written to the editor's panel store), and passes the stable `cuts` array, the
store and the editor's stable handlers.

```html
<li class="clip-item" data-identity="s1710001.mp4" data-status="active">
  <button class="btn btn-ghost btn-icon drag-handle" aria-label="Reorder s1710001.mp4">…</button>
  <!-- RowBody: pos, thumb, file, facts -->
  <span class="clip-moves">…</span>
  <button type="button" class="btn btn-ghost btn-compact cuts-toggle" data-cut
          aria-expanded="true" aria-controls="cuts-:r3:"
          aria-label="1 cut of s1710001.mp4, 1.5 seconds cut out">
    <svg scissors/>
    <span class="cuts-toggle-count">1</span>               <!-- narrow only; absent with no cut -->
    <span class="cuts-toggle-words">1 cut · −1.5 s</span>  <!-- wide only; "Cuts" with no cut -->
    <svg chevron-down class="cuts-toggle-chevron"/>        <!-- wide only -->
  </button>
  <div class="clip-cuts" id="cuts-:r3:" role="group" aria-label="Cuts of s1710001.mp4">
    <ol class="cut-list">
      <li class="cut" data-key="a1">
        <span class="cut-n">1</span>
        <span class="cut-span"><span class="cut-at">0:00</span><span aria-hidden="true"> → </span><span
          class="visually-hidden"> to </span><span class="cut-at">0:01.5</span></span>
        <span class="cut-length">1.5 s</span>
        <span class="cut-reason">Cut by hand</span>
        <button type="button" class="btn btn-ghost btn-compact cut-remove"
                aria-label="Remove cut 1 of s1710001.mp4, 0:00 to 0:01.5"><svg x/>Remove</button>
      </li>
      <li class="cut" data-key="r0" data-removed>
        <span class="cut-n">2</span> <span class="cut-span">…</span> …
        <span class="badge" data-tone="warn"><svg x/>Removed when you save</span>
        <button type="button" class="btn btn-secondary btn-compact cut-undo"
                aria-label="Undo removing cut 2 of s1710001.mp4" aria-describedby="u"><svg rotate-ccw/>Undo</button>
        <p class="cut-refusal field-error" id="u"><svg alert-triangle/>Cut 2 overlaps cut 1 …</p>  <!-- only after a refused Undo -->
      </li>
    </ol>
    <p class="cuts-none">No cuts: the whole clip plays.</p>          <!-- instead of the list -->
    <form class="cut-form" novalidate aria-label="Add a cut to s1710001.mp4">
      <div class="field cut-field">
        <label class="field-label" for="f">From</label>
        <input class="field-input cut-time" id="f" type="text" autocomplete="off" spellcheck="false"
               enterkeyhint="done" aria-invalid="true" aria-describedby="e h" />
      </div>
      <div class="field cut-field">
        <label class="field-label" for="t">To</label>
        <input class="field-input cut-time" id="t" … aria-describedby="h" />
      </div>
      <button type="submit" class="btn btn-secondary cut-add"><svg plus/>Add cut</button>
      <p class="field-error" id="e"><svg alert-triangle/>“1:5” is not a time the page can read. …</p>
      <p class="field-hint" id="h">Seconds (75.5), m:ss (1:15.5) or h:mm:ss (1:01:15.5). The page does not
        know the clip's length: a cut that runs past its end stops there, and a cut over the whole clip
        leaves the clip out of the movie.</p>
    </form>
  </div>
</li>
```

- `data-cut` (the clip has a not-removed cut) gives the toggle `--info-fg`. The count and the words say it
  too, so the state is never colour alone. With no cut the toggle is quiet but legible: its words in
  `--fg-muted`, its icons in `--fg-subtle` until the row is hovered or the panel shown. The move buttons'
  `--fg-subtle` is fine for an icon (3:1), but measures about 3.6:1 (light) and 3.9:1 (dark) on `--surface`,
  under the 4.5:1 that the words "Cuts" need.
- Accessible names. With no cut: "Cuts of s1710001.mp4". With cuts: "*n* cut(s) of *name*, *spoken* cut
  out". The name starts with the visible words in both layouts ("Cuts", "1 cut", or the count "1").
- The error is not a live region. Its words are announced once through the editor's `announce`, and the field
  that has focus is described by it. That avoids a second announcement ("The screens announce each change
  once") and the editor's one-live-region rule.
- **A missing clip's row** shows, after its name, `<span class="badge clip-cuts-badge" data-tone="idle"><svg
  scissors/>1 cut</span>` when it has cuts, and has no toggle. The badge is rendered by `ClipRow` only, for
  `status === 'missing'` (through a `RowBody` prop that only `ClipRow` passes). **`RemovedRow` shows no
  badge**: a removed clip's cuts leave `reel.yaml` with it, so counting them there would state cuts that the
  save drops. At 390 px the row keeps the existing bound of at most 8 px taller than an included row (task
  4.2 measures it with the Sommarlov fixture).
- **Locked** (save in flight): the inputs get `aria-disabled` and `readOnly`, as the metadata fields do. Add
  cut, Remove and Undo get `aria-disabled` and ignore presses. None gets `disabled`. The toggle stays live.

### Copy

| Where | Words |
|---|---|
| no cut | No cuts: the whole clip plays. |
| empty start / end | Type where the cut starts. / Type where the cut ends. |
| unreadable | “1:5” is not a time the page can read. Type seconds (75.5), m:ss (1:15.5) or h:mm:ss (1:01:15.5). |
| too precise | “0.1234” has more than three decimals. Times go to the millisecond. |
| order | A cut must end after it starts: 0:02 is not after 0:03. |
| overlap | This cut overlaps cut 1 (0:00 to 0:01.5). Change the times, or remove cut 1 first. |
| added (announced) | Cut 0:00 to 0:01.5 added to s1710001.mp4. 1 cut, 1.5 seconds cut out. |
| read cut removed | Cut 1 of s1710003.mp4, 0:00 to 0:01.2, will be removed when you save. |
| added cut removed | Cut 0:00 to 0:01.5 removed from s1710001.mp4. No cuts left. (or "2 cuts left.") |
| undo | Cut 1 of s1710003.mp4 is back. |
| undo refused (shown in the row and announced) | Cut 1 overlaps cut 2 (0:01 to 0:02). Remove cut 2 first. |
| save bar parts (G2's) | cut typed on s1710001.mp4, not added · cuts typed on 2 clips, not added · 1 cut added · 2 cuts removed |
| save bar order (all parts) | fields · date incomplete · cut(s) typed …, not added · chapter parts (G1) · moves · removals · cuts added · cuts removed · adds *n* new clips. The first part shown is capitalised, as today ("Cut typed on s1710001.mp4, not added") |
| hint (G1's sentence, changed) | A new clip joins reel.yaml once its chapter's order, one of its cuts, or the list of chapters is saved. |

### Keyboard model and focus

All controls are native. No shortcut keys are added. Enter in either field submits (implicit submission).

| Action | Focus after | Announcement |
|---|---|---|
| Cuts (toggle) | stays on the toggle | none (`aria-expanded` changes) |
| Add cut, accepted | start field (both fields emptied) | "Cut … added to …" |
| Add cut, refused | the refusal's field | the refusal |
| Remove, read cut | its Undo | "Cut *n* of … will be removed when you save." |
| Remove, added cut | the Remove of the cut now at its index, else of the one before, else the start field | "Cut … removed from … ." |
| Undo | its Remove | "Cut *n* of … is back." |
| Undo, refused (overlap) | stays on Undo | the refusal |
| Reset | as today (G1, C4) | as today |

The panel records `focusAfter = { key, target }`. A layout effect focuses the target with `preventScroll` (the
list re-rendered, and a dropped cut's node is gone). The passive effect after it calls `scrollIntoView({block:
'nearest'})` on the focused control's cut row, or on the form. The page's scroll padding keeps it clear of the
header, a chapter heading and the save bar. This is ClipOrderList's own pattern (597-642). The first edit
brings the save bar in, and the editor publishes its height in a layout effect before this passive scroll
runs.

### The read view

**Decision**: `cuts/ReadCuts.tsx` exports `useReadCuts(eventId, event)` and `ReadCuts`.

- `useReadCuts` runs `fetchReel(eventId, signal)` in an effect keyed on the `event` object. Every finished event
  read gives a new object, a quiet re-read included. It aborts on change and unmount. It returns `{ cuts:
  ReadonlyMap<string, readonly Trim[]> | null; failure: { cause: string; detail: string | null } | null }`, and
  keeps the last map while a new read runs. Failure words come from `labels.ts`. `unansweredFailure` covers no
  answer and an unpublished answer. A 502 gives `FAILURE_LABEL[failure]` and its detail. A 404 gives "The event
  is no longer there; refresh the page".
- `ReadyView` calls it once and passes `cuts.get(identity)` to each `ChapterPanel` row. A failure shows
  `<Alert tone="warn" role="note" title="Cuts could not be read" detail={…} />` after the missing-clip
  warning. It is not an alert role, as the content-warning rule requires.
- In the row's `td.cell-file`, under the name, only when the clip has cuts:

```html
<details class="read-cuts">
  <summary class="read-cuts-summary"><svg scissors/>1 cut · <span aria-hidden="true">−</span>1.5 s<span
    class="visually-hidden"> cut out</span><svg chevron-down class="read-cuts-chevron"/></summary>
  <ol class="cut-list" aria-label="Cuts of s1710001.mp4">
    <li class="cut"><span class="cut-n">1</span><span class="cut-span">…as in the panel (CutSpan)…</span>
      <span class="cut-length">1.5 s</span><span class="cut-reason">Cut by hand</span></li>
  </ol>
</details>
```

`<details>`/`<summary>` is native, operable by keyboard, and exposes expanded or collapsed state. It needs no
state of its own, and survives a quiet re-read. The list markup and `CutSpan` are shared with the panel.

**Explored**: Adding `trims` to the detail's `ClipOut` would be one atomic read with no second request, but it
is an API change. The brief allows that only when truly required, and `GET …/reel` already serves the cuts.
Reading them in `EventDetail.load()` itself would change the page's load, failure and quiet-re-read logic,
which C5's seam rules (brief round 2, rule 7) keep stable. The separate hook touches none of it.

**Rationale**: Web-only, one extra read per event read, never on a timer. The detail and the document are read
at two instants, but cuts are keyed by identity, so a clip the document no longer lists simply shows none
(Risks).

### CSS

`cuts/cuts.css`, `@layer screens`, imported by `CutsPanel.tsx` and `ReadCuts.tsx`. The edit layout lives in
`edit/edit.css`, since it places a child of the row's grid:

```css
/* edit.css, inside the existing `@container (width >= 58rem)` block: the two-line rule's
   selector gains the toggle; its grid-template-areas and row-gap are unchanged */
.clip-item:has(.clip-action, > .cuts-toggle) { /* unchanged two lines */ }
.clip-item > .cuts-toggle { grid-area: action; align-self: start; justify-self: start;
  margin-inline: var(--s-3); }
/* edit.css, inside the existing `@container (width < 58rem)` block: row 2, under handle and position */
.clip-item > .cuts-toggle { grid-area: 2 / 1 / 3 / 3; align-self: start; justify-self: start; }
@media (pointer: coarse) {
  /* Under the handle: its area reaches 6 px down, a 26 px compact toggle's 9 px up; 2 px row gap + 14 = 16. */
  @container (width < 58rem) { .clip-item > .cuts-toggle { margin-block-start: 0.875rem; } }
}

/* cuts.css: words never below --fg-muted (4.5:1); only the quiet toggle's icons use --fg-subtle (3:1) */
.cuts-toggle { --_fg: var(--fg-muted); }
.cuts-toggle:not([data-cut], [aria-expanded='true']) > svg { color: var(--fg-subtle); }
.clip-item:hover .cuts-toggle > svg { color: inherit; }
.cuts-toggle[data-cut] { --_fg: var(--info-fg); }
.cuts-toggle[aria-expanded='true'] .cuts-toggle-chevron { rotate: 180deg; }
.cuts-toggle-count { display: none; font-variant-numeric: tabular-nums; }
@container (width < 58rem) {
  .cuts-toggle-words, .cuts-toggle-chevron { display: none; }
  .cuts-toggle-count { display: inline; }
}
.clip-cuts { grid-row: -1 / span 1; grid-column: 1 / -1; display: grid; gap: var(--s-3);
  margin-block-start: var(--s-2); padding: var(--s-3); border-radius: var(--r-md); background: var(--surface-2); }
@container (width >= 58rem) { .clip-cuts { grid-column: file-start / -1; margin-inline-end: var(--s-4); } }
.cut-list { list-style: none; }
.cut { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-1) var(--s-3); min-block-size: 2rem;
  border-bottom: 1px solid var(--border); font-size: var(--text-sm); }
.cut-n { min-inline-size: 1.25rem; color: var(--fg-muted); font-variant-numeric: tabular-nums; text-align: end; }
.cut-span { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.cut-at { white-space: nowrap; }                       /* a time never breaks; the span may wrap at the arrow */
.cut-length, .cut-reason { color: var(--fg-muted); font-variant-numeric: tabular-nums; }
.cut-reason { overflow-wrap: anywhere; min-inline-size: 0; }
.cut > .btn, .cut > .badge { margin-inline-start: auto; }
.cut > .badge + .btn { margin-inline-start: 0; }
.cut > .cut-refusal { flex-basis: 100%; }
.cut[data-removed] :is(.cut-span, .cut-length, .cut-reason) { color: var(--fg-muted); text-decoration: line-through; }
.cuts-none { color: var(--fg-muted); font-size: var(--text-sm); }
.cut-form { display: flex; flex-wrap: wrap; align-items: end; gap: var(--s-2) var(--s-3); }
.cut-field { flex: 1 1 7rem; max-inline-size: 10rem; }
.cut-time { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.cut-form > :is(.field-error, .field-hint) { flex-basis: 100%; }
.read-cuts { margin-block-start: var(--s-1); font-family: var(--font-sans); }
.read-cuts-summary { display: inline-flex; align-items: center; gap: var(--s-1); padding: 0.125rem var(--s-1);
  margin-inline-start: calc(-1 * var(--s-1)); border-radius: var(--r-sm); color: var(--info-fg);
  font-size: var(--text-sm); cursor: pointer; list-style: none;
  &::-webkit-details-marker { display: none; } &:hover { background: var(--surface-hover); } }
.read-cuts[open] .read-cuts-chevron { rotate: 180deg; }
.read-cuts > .cut-list { margin-block-start: var(--s-1); }
@media (pointer: coarse) {
  .cut { min-block-size: 2.75rem; }                     /* each row holds its button's 44 px area */
  .cut-time { min-block-size: 2.75rem; }
  .cut-form { row-gap: var(--s-4); }                    /* the 32 px Add cut grows 6 px each way */
  .read-cuts-summary { min-block-size: 2.75rem; min-inline-size: 2.75rem; }
}
```

- The `.btn::after` hit areas (components.css 829-848) are unchanged. At narrow width the toggle's area grows
  9 px up and 9 px down. The 14 px margin under a coarse pointer clears the handle's area. Below it, the row's
  8 px padding and the next row's 8 px leave 16 px against the next handle's 6 px plus this 9 px. Rows stay
  the same height, because line 2 is set by the facts (about 44 px) or the thumbnail (45 px), and 14 + 26 = 40
  px is under that. At 768 px the toggle costs 4 px (measured), and up to 18 px more under a coarse pointer.
  Both are stated in Risks.
- At 320 px the panel is the row's width less its padding, about 248 px. Two 7rem fields share a line, and
  Add cut wraps under them. The read view's file cell is narrower: about 150 px at 320 (`detail.css`, the
  `< 22rem` grid), where a whole span such as `10:00:00.125 → 10:00:01.5` (about 200 px in 14 px mono) would
  overflow. So only each time is `nowrap` (`.cut-at`, about 100 px at its widest), and a span wraps after its
  arrow. Every other text wraps. Nothing overflows in either view.
- Every text is `--fg-muted` or stronger (the quiet toggle's words included), and the toggle's and summary's `--info-fg` sits on `--surface`,
  `--surface-2` or `--surface-hover` (contrast measured in 4.2). No new colour, and no animation (the chevron
  turns without a transition).

### Performance

`ClipOrderList` receives **`draft.cuts` and `baseline.cuts`** as two props, never `draft` and never a
`cutsOf` closure over it, and resolves `cutsOf(baseCuts, cuts, identity)` per row. Both are identity maps:
`baseline.cuts` never changes, and `draft.cuts` gets a new reference only on a cut edit. So G1's rule holds
(no list prop derives from `metadata`): typing in Title re-renders no list.

`ClipRow` stays `memo`. Its new props are `cuts` (a stable array per clip: the baseline's, or the draft's for a
changed clip), `locked` (already a prop), the stable panel store and stable `dispatch`-based handlers. A cut
edit therefore re-renders each list's body (memo checks only) and that row alone. Typing in a cut field is
local state in `CutsPanel`, mirrored into the store (a ref: no render). The `cut-typed` dispatch fires only
when "has text" flips, not per keystroke. Rows never opened mount no panel. Task 4.1 checks this on G1's
400-clip `Stor dag`, both typing in a cut field and typing in Title.

### Files and the G1 seam

| File | Change |
|---|---|
| `cuts/times.ts` (new) | parse, write, `checkCut`, `checkRestore`, `cutOutSeconds`, `CUT_REASON_LABEL`, copy constants |
| `cuts/CutsPanel.tsx` (new) | `CutsToggle`, `CutsPanel`, `CutList`, `CutSpan` |
| `cuts/ReadCuts.tsx` (new) | `useReadCuts`, `ReadCuts` |
| `cuts/cuts.css` (new) | the rules above |
| `edit/draft.ts` | `Draft.cuts`, `Baseline.cuts`, cut operations, `changedCuts`, `cutChanges`, `writtenFromView` predicate, `clips` merge |
| `edit/EventEditor.tsx` | actions `cut-add`, `cut-remove`, `cut-restore`, `cut-typed`; `typed` (identities); the typed clip's name at summary time; `nextCut` counter; the panel store; `submit`'s and `dirty`'s typed check; summary; hint sentence; `unfinished`; passes `draft.cuts` and `baseline.cuts` to each list |
| `edit/ClipOrderList.tsx` | props `cuts`, `baseCuts`; toggle and panel in `ClipRow`, after `MoveButtons`; the missing clip's badge from `ClipRow` only (not `RemovedRow`) |
| `edit/SaveBar.tsx` | `dateIncomplete` → `unfinished` |
| `edit/edit.css` | the toggle's placement (above) |
| `events/EventDetail.tsx` | `ReadyView` calls `useReadCuts`; `ChapterPanel` renders `ReadCuts` in the file cell |
| `ui/Icon.tsx` | `scissors`, `chevron-down` (Lucide, ISC, as the others) |
| `web/README.md`, `docs/high-level-design.md` | docs |

The change touches no chapter key, no `chapterChanges`, no tools row and no dialog of G1's.

### HLD

`docs/high-level-design.md` §7 gains:

> **D-14 — Cuts are edited by typed times in GUI v1** (2026-10-01, change `clip-cuts-screen`). Edit mode
> lists, adds and removes a clip's cuts (D-D), with times typed as seconds, m:ss or h:mm:ss, pulled forward
> from v3 at the operator's request. Scrubbing, previews and drag-trim stay v3. The page refuses what the
> engine refuses (`out <= in`, negative), and refuses an overlap with another cut. It cannot refuse a cut past
> the clip's end, because no probe-free read gives a duration, so it states the render's rule instead (cut
> short at the end; a whole-clip cut leaves the clip out). A cut made in the GUI has the reason `manual`. The
> event page shows each clip's cuts. (§4.10)

§4.10's v1 bullet gains "**typed cuts** (**D-14**)" beside G1's "chapter edits and Move clips (**D-13**)";
the line is re-read after G1 lands, and its "No timeline, no per-frame editing" stays true (typed times are
neither). Slice row D gains one sentence naming this change.

### Verification fixtures

The implementing agent's own environment (dev-env runbook §9): `SLUG=clip-cuts-screen`, `N=27`, database
`arel_clip_cuts_screen`, library `../dev-clip-cuts-screen`, `serve` on port **8127**, no worker. In that
library copy only, each `reel.yaml` copied before it is touched and compared after with `diff`. Each fixture is
applied only for the scenarios that state it, and the copy is restored before the next scenario: the read
view's "nothing beside its other clips", for one, holds only without the Grillning fixture.

- `2024-06-27 - Grillning med grannar`: `clips: {s1710003.mp4: {trims: [{in: 0, out: 1.2, reason: black}]}}`
  for the removal, Undo and refused-Undo scenarios.
- `2024-06-27 - Grillning med grannar`, layout checks only (task 4.2): `s1710002.mp4` given
  `[{in: 3723.125, out: 3725.5}]`, the widest times a list shows, at 320 px in both views.
- `2024-09-01 - Sommarlov`: `clips: {borttagen.mp4: {trims: [{in: 0, out: 2}]}}` for the missing-clip
  scenario.
- `2024-08-20 - Två kapitel - Tjörn`: G1's hand fixture `clips: {Kvällen/s1710002.mp4: {trims: [{in: 0, out:
  1.5}]}}`, for "A moved clip keeps its cut" as written.
- `2024-09-15 - Stor dag`, for scale: G1's fixture (`openspec/changes/archive/*-chapter-management-screen/design.md`,
  "Verification fixtures"), itself the recipe of `archive/2026-09-30-event-edit-screen/design.md`: 400
  symlinks `c0001.mp4`…`c0400.mp4` at the root to one cut clip of the library's `clips/`, plus
  `Kväll/k001.mp4`…`Kväll/k003.mp4` to the same clip, and no `reel.yaml`.

## Failure behavior & idempotency

- Nothing renders, enqueues or probes. A save is G1's single `PUT` with `If-Match`. Every failure path keeps
  the draft, cuts and typed text included, and `SaveBar` shows it as today: 400, 404, 412 (Reload / Overwrite),
  502, no answer, or an error in the page. Overwrite sends the same body under the fresh tag.
- The engine would refuse a span with `out <= in`, a negative time, or a cut on an unlisted clip. The model
  makes all three unreachable: `checkCut`, and the NEW-clip predicate in `writtenFromView`. Task 2.2's
  scratch script asserts that every body it builds passes those rules. If one slipped through, the 400
  carries the engine's detail and the draft is kept.
- Re-saving the same draft is a no-op on disk (`_trims_equal`). A draft equal to the read is not offered
  (`isDirty` false).
- The read view's cut read writes nothing. A failure leaves the clips shown, with a note. An aborted read (a
  newer event read, leaving the page) is dropped silently, as the event read's own abort is.

## Risks / Trade-offs

- **[A cut past the clip's end is cut short silently at render; a whole-clip cut drops the clip.]** → The
  panel says so beside the fields. A duration source is an API decision (Open Questions). Note an engine
  wrinkle found here: the title card is inserted before the chapter's title clip's first segment
  (`render/title/decorator.py` 83-122). A whole-clip cut on that clip therefore leaves the chapter without a
  title card. Reported to the supervisor as an engine follow-up, not handled here.
- **[Changing a clip's cuts reformats its other cuts]** (flow style and comments lost; `in: 0` → `0.0`). →
  Stated in the proposal's non-goals. Only the changed clip's `trims` node is rewritten, and every other line
  stays (the scenario "A cut writes only its clip's cuts").
- **[The read view's cuts arrive after the rows]**, and the two reads are not atomic. → Rows show no indicator
  for the moment the second read runs. A document changed in between can only add or drop an indicator, never
  misplace one, since cuts are keyed by identity, and Refresh re-reads both. The API alternative is recorded.
- **[An excluded clip offers Cuts.]** A clip with `exclude: true` in `reel.yaml` is listed and on disk, so the
  page shows it as included (the GUI has never shown `exclude`), and its cuts change nothing while it is
  excluded. → Its cuts still save as written, `exclude` is kept as read, and showing exclusion is out of scope.
- **[Every on-disk row gains a control]**, 400 more tab stops in a large chapter. → One stop per row, after the
  move buttons, as each of them is. Wide rows from 58 to 64rem grow by a few pixels, and narrow rows
  by 4 px at 768 (18 px more under a coarse pointer). Rows at 320 and 390 do not grow (measured).
- **[`manual` is written without the operator typing it.]** → D-K documents it for exactly this, and the
  panel shows it as "Cut by hand" before the save.
- **[Overlaps are refused, while the render would merge them.]** → Stricter than the engine. The refusal names
  the cut to remove, and overlaps already in `reel.yaml` are still shown and counted correctly.

## Migration Plan

None: no data, schema or API change. A `reel.yaml` written by this change is an ordinary v0 document, and an
older client reads it. Rollback is reverting the web build.

## Open Questions

- **A probe-free clip duration** (for refusing a cut past the end): the thumbnail route already probes each
  clip it extracts from. Caching that duration and adding it to `ClipOut` would let a later change refuse such
  cuts. That is a separate API decision, and it changes nothing here.
