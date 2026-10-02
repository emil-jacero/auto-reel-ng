## Context

See proposal.md for the problem. The code this change edits, on `6a7fe16`:

- **`auto_reel_ng/api/schemas.py`.** `ClipOut(identity, status, size, mtime)`, `EventSummaryOut` (with
  `clip_count`, `new_count`, `missing_count`), `EventDetailOut` (with `chapters`, `missing`).
- **`auto_reel_ng/api/events_read.py`.**
  - `_load_for_reconcile` returns `(document, listing, result)`; `document` is `None` when no `reel.yaml`
    exists. `ReconcileResult.classification` maps every identity to NEW / MISSING / ACTIVE / IGNORED.
  - `_event_summary` (line ~267) sets `clip_count=len(result.classification)`, `new_count=len(result.new)`,
    `missing_count=len(result.missing)`.
  - `_clip_out(event_dir, identity, status)` builds a `ClipOut`; `_build_chapters` calls it for the
    document's listed clips and for the disk clips the document does not list.
  - `get_event` (line ~430) returns `missing=list(result.missing)`.
- **The engine's meaning of exclude.** `ClipProperties.exclude` (`reel/document.py`); `_resolve_chapter`
  (`event/resolution.py:50-56`) skips an excluded clip before the probed-facts check; `cli/build.py:37`
  does not probe it. `reel/schema.py:_validate_cross_references` rejects `clips` properties for an identity no
  chapter references, so only a clip a chapter lists can be excluded: a NEW or IGNORED clip never is.
- **The web.**
  - `EventDetail.tsx:425` passes `missingClipsReason(event.missing)` to `RenderControl`; `:439-448` renders the
    warning from `event.missing`; `Counts` (`:480`) and `ChapterTable` (`:554`) treat every non-ignored clip as
    played; each row's status cell is `CLIP_STATUS_LOOK`/`CLIP_STATUS_LABEL` over `ClipStatus`.
  - `EventList.tsx:159` shows `plural(event.clip_count, …)`; `:167` shows the missing badge; `:186` passes
    `blockedReason` when `event.missing_count > 0`.
  - `edit/ClipOrderList.tsx`: `ClipFacts` shows the same status pill; `cuttable = status === 'active' ||
    status === 'new'`; a missing clip shows a cut-count badge. `cuts/ReadCuts.tsx` builds
    `ClipCuts` from `GET …/reel` for every clip with trims.
  - `events/labels.ts` and `events/tones.ts` hold `Record<ClipStatus, …>` vocabularies, exhaustive over the
    generated union.

### Findings re-checked

- `list-clip-count-counts-ignored-clips-page-does-not`: confirmed in the code above (`len(result.classification)`
  vs `status !== 'ignored'`). `classification` also holds MISSING and NEW, which the page counts as played, so
  the page's number is `len(classification) - len(ignored)`.
- `excluded-missing-clip-blocks-render-no-api-field`: confirmed for the client. The server half (POST /jobs
  accepting such events) is not this change's: supervisor decision, `api-jobs-missing-clips-refusal`.
- `exclude-not-shown-in-gui`: confirmed; `grep -rn exclude web/src` hits only the generated schema and
  `draft.ts`'s round trip.
- The triage's open check, "should an excluded MISSING clip drop out of staleness `clip_set`", is answered
  **no change needed**: `_hash_clip_set` (`staleness/fingerprint.py`) hashes `scan_event(event_dir).identities`,
  the clips on disk. A missing clip is not in it, excluded or not. `exclude` is in `editorial_hash`
  (`document.to_dict()`), so toggling it already marks the event stale. An excluded clip that is on disk still
  counts in the clip set; that is existing behaviour and a non-goal.

## Goals / Non-Goals

**Goals**

- The service says, per clip, whether it is excluded, and, per event, which missing clips a render needs.
- Both screens, and Edit mode, use those two facts and nothing else to decide what is marked and what blocks.
- The list and the page agree on how many clips an event has.

**Non-Goals**

See proposal.md, "Non-goals". At design level: no new module, no new `ClipStatus`, no change to `missing`'s
meaning, no probe, and no client-side recomputation of exclusion from the editorial document.

## Decisions

### `excluded` is a flag on `ClipOut`, not a `ClipStatus`

**Context**: An excluded clip is still ACTIVE (on disk) or MISSING (absent): reconcile's status is about disk
against document. Exclusion is about the plan.
**Explored**: A fifth status `excluded`. It would hide whether an excluded clip is on disk, so an excluded
missing clip could not report both; it would change a closed, published vocabulary (api-service, "Clip status
is a closed, published vocabulary") and every `Record<ClipStatus, …>`; and `reconcile` would have to know about
properties.
**Decision**: `ClipOut.excluded: bool = False`, filled from `document.clips[identity].exclude`. `_clip_out`
takes the flag; `_build_chapters` passes it for the document's listed clips and `False` for the disk-only
clips (NEW/IGNORED), which cannot be excluded (schema validation). The no-document branch is all `False`.
**Rationale**: Status vocabulary untouched; an excluded missing clip reports `missing` and `excluded: true`;
the generated union stays exhaustive over a smaller set.

### `blocking_missing` is computed once, in `events_read`, and is the shared definition

**Context**: "Missing and not excluded" must be the same set for the page, the list and (next) POST /jobs.
**Decision**: A module-level function in `events_read.py`,
`blocking_missing(document: Optional[ReelDocument], result: ReconcileResult) -> tuple[str, ...]`: the
identities in `result.missing` for which `document.clips.get(identity)` is not an excluded
`ClipProperties`; empty when `document` is `None` (nothing is listed, nothing is missing). `get_event` returns
`list(...)`, `_event_summary` returns its length, and `api-jobs-missing-clips-refusal` imports it.
**Alternatives**: A property on `ReconcileResult` (reconcile would take the document's properties, widening a
pure disk-versus-structure diff). A field on the engine's plan (`resolution.py`): the plan is built from probed
facts and is not available to a read. Both are a third package; the API function is a read-model projection of
two engine facts (`result.missing`, `ClipProperties.exclude`), which Principle V allows, and the CLI reaches
the same outcome through the probe skip.
**Rationale**: One definition, one place, no probe. `missing` stays untouched so the warning can list all.

### `clip_count` is the page's number; `ignored_count` is added

**Decision**: `clip_count = len(result.classification) - len(result.ignored)`; `ignored_count =
len(result.ignored)`. `new_count` and `missing_count` are unchanged (both inside `clip_count`, as on the page).
`EventList.tsx` shows `plural(clip_count)` and, when `ignored_count > 0`, `· k ignored`, as the page's chapter
heading writes it.
**Alternatives**: Change the page to count ignored clips (rejected: the page's definition is the established
one, "the clips the event plays", and Edit mode counts the same); leave the list terse and only fix the number
(rejected: the ignored clips would vanish from the list silently; one extra number is cheap).

### Excluded clips stay in place and numbered; they are counted as a subset

**Context**: The triage sketch drops excluded clips from "N clips". But positions are the unit of Edit mode:
`ClipOrderList` numbers every movable row by index, and drag announcements, `order.length`, `dragSlots` and the
move buttons all work on that list. An excluded clip is in the document's chapter list, and moving it changes
`reel.yaml`'s order.
**Explored**: Listing excluded clips after the played ones, unnumbered, as ignored ones are. In the read view
that is a sort; in Edit mode the excluded clip would have to leave the movable list, and `writtenFromView` and
the drag slots would have to put it back in its chapter position on Save: a rewrite of the editor's model for
a display flag.
**Decision**: Both screens keep the document's order and numbering. "Excluded" is a count of a subset of the
listed clips, like "missing" ("`N clips · size · k new · m missing · i ignored`" gains `· e excluded`, zero
counts omitted). The row says Excluded in words and an icon; the position number stays so the two screens
number the same rows.
**Rationale**: The marking is honest (the row says it is not in the movie) with no model change. The cost is
that a numbered row can be an excluded one, and the facts line's total size sums every listed clip, which is
today's definition. Both are visible in the label.

### The Excluded label replaces "Included"; Missing keeps its label and gains Excluded

`CLIP_STATUS_LABEL`/`LOOK` stay keyed by `ClipStatus`. Next to them, `EXCLUDED_LABEL = 'Excluded'` and
`EXCLUDED_LOOK = { tone, icon }` (tone `idle`, with an icon of its own: the closed `IconName` set in
`ui/Icon.tsx` gains one drawing, since `x` is the Ignored icon and `square`/`check` mean other things).
A shared helper `clipLabels(clip)` returns the pills for a clip, so the page's table and Edit mode's
`ClipFacts` cannot disagree: ACTIVE and excluded gives `[Excluded]`; MISSING and excluded gives
`[Missing, Excluded]`; otherwise today's single pill. The Excluded pill is a status label (fill and edge) like
New and Missing, so state is not shown by color alone.

### The page's warning lists every missing clip; Render uses the blocking ones

`missingClipsReason(blocking_missing)`; the warning keeps `event.missing` and appends ` (excluded)` to each
identity that is not in `blocking_missing`. The warning stays `role="note"` (ui-a11y-polish). When every
missing clip is excluded, the warning stays shown (the files are gone) and Render is offered. The list row
keeps its missing badge from `missing_count` and blocks only on `blocking_missing_count > 0`.

### Cuts for an excluded clip: hidden, preserved

`cuttable` in `ClipOrderList` also requires `!clip.excluded`; the missing clip's cut-count badge is likewise
not shown. `ReadCuts` receives `undefined` for an excluded clip (the page passes `cuts?.get(identity)` only
when not excluded). Without a Cuts panel the row's thumbnail is a plain image (RowBody's `onWatch` is
`undefined` when no panel exists), so the Watch preview follows the Cuts rule in its own requirement.
Nothing is deleted: `draft.ts` `withCuts` writes the stored trims back for every clip the operator did not
edit, so Save leaves an excluded clip's cuts as they were. This is verified in the Playwright run by
inspecting the write body (the write is intercepted).

### Gates

- `api-jobs-create-validation` replaces an `exists()` call in `events_read.py` with `reel_exists`. The lines
  this change edits (`_clip_out`, `_build_chapters`, `_event_summary`, `get_event`) are elsewhere; a
  textual conflict is trivial. Task 1.1 re-greps the names this change builds on.
- `api-ws-heartbeat` adds a `WsMessageType` member to `schemas.py` and regenerates `openapi.json` and
  `schema.d.ts`. These two generated files are never hand-merged: task 1.3 regenerates them from the
  merged tree.
- The sibling `api-jobs-missing-clips-refusal` depends on this change (`blocking_missing`) and on its own
  gate; this change does not touch `routes/jobs.py`.

## Risks / Trade-offs

- **A numbered row can be excluded; the total size includes it** → The row says Excluded in words; the
  decision above records why.
- **Hiding cuts hides stored data** → Nothing is removed; Save writes them back unchanged (spec scenario,
  verified on the write body). An operator who wants them sees them in `reel.yaml`.
- **A client built against the old schema** reads `clip_count` as before: the field keeps its name and type;
  only its value changes to the page's number. New fields are additive.
- **A stale page offers Render for an event whose clip went missing** → Unchanged behaviour; the POST refusal
  is the sibling change's.
- **The list shows "1 missing" beside an enabled Render** (the only missing clip is excluded) → Intended and
  specified: the badge counts files that are gone, the Render guard counts files a render needs.

## Idempotency and failure

The change is read-only: a repeated request gives the same answer for the same disk and document, nothing is
written, no job is created, and nothing leaves a partial file. An unreadable event keeps its error row or 502
(unchanged); the new fields exist only on a readable event. A `reel.yaml` with no `clips` map, or no `exclude`,
gives `excluded: false` and `blocking_missing == missing`.

## Open Questions

None that change the specs or tasks. Whether the icon for Excluded is a new drawing or an existing one is a
choice for the implementer within the "icon of its own" rule.
