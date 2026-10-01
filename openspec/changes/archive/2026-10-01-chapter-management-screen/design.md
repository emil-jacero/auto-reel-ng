## Supervisor decisions (2026-10-01)

- A save that changes the chapter list adopts every NEW clip, as the next render writes them: **accepted**
  ("What a save writes").
- This change owns the small shared-UI edits, the `.dialog-fields` split in `ui/Dialog.tsx` and the two new
  icons in `ui/Icon.tsx`: **approved**.
- Renaming a chapter, or moving a clip into a new chapter, loses that chapter's `reel.yaml` comments, and
  reordering chapters can drop a comment between chapters: **accepted for now**. Follow-up: the engine
  matches a renamed chapter by its clip list (Risks).
- After implementation and review (2026-10-01): the six implementation deviations recorded below are
  **accepted**; the Move clips transition is **locked** rather than accepted as a window; and a **Pick all**
  box in Move clips is an **approved addition** ("The Move clips dialog"). The review's other minors are
  fixed as described in place: an emptied chapter that still lists ignored or removed clips says how clips
  get in; the own chapter's Delete refusal counts only the ignored clips that would stay under it; the
  notes name the own chapter by its heading (`Clips` when alone); a Delete refusal tells clips on disk from
  missing ones; Add chapter's announcement carries its notes.

## Context

See proposal.md, "Why". This change works on main at `d0bc1d5`. Its code is `web/src/edit/`, an early return in
`web/src/events/EventDetail.tsx`'s `ChapterPanel`, and two small additions to the shared UI (`ui/Icon.tsx`, `ui/Dialog.tsx`).

**Edit mode today** (all re-read on `d0bc1d5`):

- `edit/draft.ts` is the pure model. `EditableChapter` is `{ name, movable, ignored }` (17-24). `Orders` and
  `Removals` are keyed by the chapter's **name** (26-30). `buildWriteBody` (159-200) writes the document as
  read, except the chapters whose order changed (`reordered`, 125-129), and, when the document names no
  chapters, every chapter shown with a clip (`writtenFromView`, 136-142). `restoreClip` (254-271) puts a clip
  back after the last of its original predecessors. `movedSet` (329-337) counts the fewest moved clips; a
  clip absent from the original order has no rank, so it always counts as moved. Its Fenwick tree is
  sized by the **new** order's length while ranks come from the original, so a rank may never exceed the
  new order's length: both callers (`EventEditor.tsx` 609-614, `ClipOrderList.tsx` 460-468) pass the
  original **less the removed clips**, which keeps that true today. A clip moved **out** of a chapter
  breaks it: reviewed on `d0bc1d5` under Node, `movedSet(['K/s2','K/s3','K/s4'], ['K/s4'], null)` throws
  `TypeError: Cannot read properties of undefined (reading 'score')`. See "Counts, badges".
- `edit/EventEditor.tsx` holds the reducer (`reduce`, 140-240), the summary (`summarize`, 400-418), the
  chapter heading rule (`chapterHeading`, 424-426: `Main` while a named chapter exists, else `Clips`), and
  renders one `ClipOrderList` per chapter, keyed by name (1015-1035).
- `edit/ClipOrderList.tsx` is one chapter: its own `DndContext` (id `chapter-${index}`, 622-633) and the
  `withinChapter` modifier (77-84), so a drag can never leave the chapter. It names clips with
  `clipNames(chapter, [...original, ...ignored])` (475-478). Focus after a move is restored by a layout
  effect, and the row is scrolled by the passive effect after it (559-597).
- `ui/Dialog.tsx` describes the dialog by every child except a `.dialog-actions` row (5-11, 82-84).
- The panel header is sticky (`components.css` 168-185), one line (`edit.css` 366-369), and the page's
  `scroll-padding-top` counts on that height (`shell.css` 5).
- The read view (`EventDetail.tsx` 428-462, 532-588) renders an empty chapter as a table with a header and no
  rows.

**Engine and API facts** this design rests on. Each was checked in the code and, where marked, by a probe
against a scratch copy of the dev events (`engine_probe.py`, the engine directly) or by real `PUT`s against
a scratch `serve` on port 8190 with its own database (`put_probe.py`, `put_probe2.py`, `ignored_probe.py`;
all in the session scratchpad under `g-spec/chapter-management-screen/`, never committed; the database was
dropped afterwards).

| Fact | Where | Checked |
|---|---|---|
| `PUT …/reel` takes `EditorialDocumentBody` `{metadata, look, chapters: [{name, clips}], clips, ignore}`, `extra="forbid"` | `api/schemas.py` 157-216 | code |
| The route answers 400 for an invalid state, `failure: unusable_metadata` only for metadata; 412 on a stale `If-Match`; 502 for the disk | `api/routes/events.py` 422-488 | PUT: duplicate name → 400 with `failure: null`; old tag → 412 |
| Chapters are merged **by name**: a matched name keeps its node and its clips' comments, also for a clip moved in from another existing chapter; an unmatched name is a fresh node with no comments | `event/editorial.py` 169-233 | probe + PUT: a rename drops `# sunset`; a move between existing chapters keeps it |
| A chapter name must be a string; `''` is the default chapter; an exact duplicate is refused (a second `''` too); whitespace and case variants are accepted | `reel/schema.py` 101-132 | probe + PUT: `'  '` and `' '` saved |
| An identity is listed at most once; a `clips` entry needs a listing chapter; an ignored identity is never listed | `reel/schema.py` 245-282 | probe: one identity in two chapters → refused |
| The detail lists every authored chapter, an empty one included, then places each disk clip the document does not list (NEW or ignored) in the chapter named exactly after its folder, else the default chapter, appended last when the document does not name it | `api/events_read.py` 325-380, `cli/adoption.py` 86-129 | probe: empty `Morgon` listed; ignored `Kvällen/…` goes to the default chapter after a rename or delete, and under a re-added `Kvällen` |
| A document naming no chapters is placed as a seed: each folder its own chapter | `cli/adoption.py` 111-121 | PUT on `Blandat` |
| Folders are one level deep, root first, then subfolders by name; `original/` and `.reelignore` folders excluded | `event/discovery.py` 118-140 | code |
| A non-default chapter's title card uses its name as the heading; the default chapter's uses the event metadata | `render/title/content.py` 71-86 | code |
| A chapter with no clips has no title card and no chapter marker | `event/resolution.py` 76-90, `render/title/decorator.py` 86-122, `render/chapters.py` 16-33 | code |
| The detail is probe-free: a clip carries `identity`, `status`, `size`, `mtime`, no duration | `api/schemas.py` 30-50 | code |

Two engine facts shape the UI most. First, **D-12 is name-exact**: what attracts a folder's later clips,
and its ignored clips, is a chapter named exactly like the folder. Second, **a rename is a new chapter** to
the merge: it loses its clips' comments, and if Save sent the chapter's clips as `reel.yaml` lists them, its
NEW clips would move to the default chapter on the next read (probe: "rename Kvällen → Kväll, clips as
read").

## Goals / Non-Goals

**Goals:**

- Add, rename, reorder, delete and move-into chapters, all from the keyboard, at 320 px, by touch.
- A save shows after it what the page showed before it (clip by clip, chapter by chapter).
- G2 (`clip-cuts-screen`) can add per-clip properties to the draft without touching chapter structure.

**Non-Goals:**

- No engine, API, schema or dependency change. No change to how a drag or a row's Move up / Move down works.
- No new route, no chapter-level metadata (a chapter has only a name), no undo history beyond the per-item
  Undo and Reset that exist.

## Research & Decisions

### Delete only an empty chapter

**Context**: The brief asks to delete a chapter only when empty, or to move its clips to the default chapter,
and to justify the choice.

**Explored**: (a) Delete moves the clips to `Main`; (b) Delete only when the chapter plays no clip.

**Decision**: (b). The chapter's clips leave through **Move clips** (or a missing one through its Remove).
Delete on a chapter that still plays clips is `aria-disabled`, and pressing it explains why.

**Rationale**: (a) is a silent bulk move into a chapter the operator did not pick, and `Main` may itself
be deleted or absent (a document that does not name `''`). (b) needs no new rule for where clips go, and
every clip move stays one visible, undoable step that the save bar counts. The extra cost is one Move clips
before a Delete, which is also the step that makes the operator look at where the clips go.

The event's own chapter has one more condition: it can be deleted only when it lists no ignored clip that
would stay under it after the save. The detail lists an ignored clip under the chapter named exactly after
its folder, else under the default chapter whether or not `reel.yaml` names it (adoption.py 124-125). So an
ignored clip of the event folder, or of a folder no listed chapter is named after, would bring the deleted
chapter back on the next read, holding only ignored clips. One whose folder now has a chapter of its name
(say, one just added) moves there and does not hold the default chapter (`ignoredStaying`, chapterNames.ts,
the same rule as the notes' "listed here"). The
only chapter left cannot be deleted at all: a `chapters: []` save would turn the document seed-like and
re-chapter every clip by folder (adoption.py 111).

### The event's own chapter keeps no name

**Context**: The default chapter `''` is the event's own: its title card is the event's (D-E), and clips
with no chapter of their own join it (D-12).

**Decision**: It offers no Rename. It keeps the read view's heading rule (`Main` while another chapter is
listed, else `Clips`). While another chapter is listed, its tools row says: "The event's own chapter: its
title card shows the event's title, and clips without a chapter of their own join it."

**Rationale**: Renaming `''` to a name would make it an ordinary chapter: the event would lose its own title
card in the middle of the movie, and the folder's later clips would start a new default chapter at the end.
That is a real but rare want; it can be done in two steps (add a chapter, move the clips, delete `Main`).

### Name rules

**Context**: The engine accepts any string, refuses only an exact duplicate (reel/schema.py 119-120), and
uses the name verbatim as a title-card heading.

**Decision**: A name is trimmed, must not be empty, must differ **ignoring case** (`toLocaleLowerCase()`
both sides) from every other listed chapter's name, deleted ones included, and from `Main`, always. The
name sent is the trimmed one. No length limit (the heading wraps).

**Rationale**: A blank name is a blank title card. Two names differing only in case are two title cards
that read alike, and the operator cannot tell their D-12 effect apart. A deleted chapter still holds its
name until saved, because its Undo would bring a duplicate back. `Main` would read exactly like the
event's own chapter, and is refused even when the event has none: clips added to the event folder later
start a default chapter, headed `Main`, at the end (probe: a chapter literally named `Main` beside `''`
gives the page two `Main` headings). The engine stays as it is: the CLI and hand edits are unaffected (proposal,
"Non-goals").

### Moving clips: one dialog per chapter

**Context**: The brief asks for a keyboard-accessible way to move a clip to another chapter, cross-chapter
drag only if cheap.

**Explored**:
- **Drag across chapters.** One `DndContext` for all chapters, `onDragOver` moving items between
  `SortableContext`s, a custom keyboard coordinate getter that crosses lists, and new announcements. The
  `withinChapter` modifier and per-chapter announcements (ClipOrderList 77-84, 489-507) would be rewritten,
  and a 400-clip chapter would re-render on every pointer step across lists. Not cheap; it stays v3.
- **A per-row "Move to chapter…" control.** One more control on every row. The row's first line at 320 px
  already holds the handle, the position, the name and Move up / Move down (edit.css 498-516), and G2 needs
  that room for its per-row Cuts control. One clip per action, too.
- **A per-chapter "Move clips…" dialog.** Checkboxes for the chapter's clips, radios for the target.

**Decision**: The per-chapter dialog. It moves any number of clips in one step, needs no row space, and is
plain native form controls inside the existing `Dialog`.

**Rationale**: It is the cheapest fully keyboard-operable path, and the batch is the common case (split an
event into "day" and "evening"). Range selection (Shift-click) and "split at this clip" are follow-ups.

### Where moved clips land

**Decision**: The picked clips keep their relative order (their order in the source chapter now) and join
the end of the target's play order. A clip moving back to the chapter it was in when Edit mode opened is
placed as `restoreClip` places an undone removal: right after the last of its original predecessors that
the target now holds, else first. Returning clips are placed one by one in their original order, then the
others are appended.

**Rationale**: "Join the end" is predictable and the order is then one drag away. The return rule makes a
move and its reverse leave nothing to save, so `isDirty` needs no special case, and it is the rule
`restoreClip` already proved (missing-clips-screen).

### What a save writes

**Context**: A rename sends a name the merge cannot match; the probe shows the renamed chapter's NEW clip
then reads under the default chapter. A deleted chapter's NEW clips would do the same.

**Decision**: Two kinds of save. A **structural** save (a chapter added, renamed or deleted, or the
chapters' order changed), and any save that changes an order or a chapter while the document names no
chapters, write **every** listed, non-deleted chapter, in the order shown, under its current name, each
from the view: its order (missing and NEW clips in place), without its ignored and removed clips. Every
other save writes as today: the chapters whose order changed from the view (now including a clip moved in
or out), every other chapter exactly as read. A metadata-only save writes the chapters as read.

**Rationale**: Writing every chapter from the view adopts every NEW clip where the page shows it, so the
page shows the same placement after the save, and a chapter's name only decides where *later* clips go.
The save bar already says how many NEW clips a save adds (`adoptedNewCount`), so nothing is adopted
silently. Nor is anything adopted early in effect: the next render adopts every NEW clip anyway, into the
chapter the page shows it in, and writes `reel.yaml` (`cli/adoption.py` `prepare_event` + `persist`, called
by `cli/build.py` 53). Adopting at the save only fixes that placement before a name change could move it.
The narrower alternative (write untouched chapters as read) was rejected: after Add `Kvällen` (or a rename
to it), the folder's NEW clips shown in `Main` would move to the new chapter on the next read, which
contradicts the note the dialog shows. Unchanged chapters still keep their node and comments: the merge reuses a node by name and leaves
an unchanged list untouched (editorial.py 203-211, 414-416). For a document that names no chapters this also aligns
the code with the spec: `writtenFromView` today skips a seed chapter with no clip to play (one that holds
only ignored clips), which then moves those ignored clips to the default chapter after the save; the new
rule writes it, empty, where it was shown.

### The draft model

**Decision**: Chapters get a stable key for the session, and every map is keyed by it. `draft.ts` keeps no
runtime imports (scratch Node scripts run it as is).

```ts
/** `r0`, `r1`… for the chapters the page showed, in that order; `a1`, `a2`… for added ones. */
export type ChapterKey = string

export type DraftChapter = {
  key: ChapterKey
  /** The name it was read with; null for a chapter added in this session. */
  readName: string | null
  /** Its name now: trimmed, '' only for the event's own chapter. */
  name: string
  /** Deleted on save; still listed, in place, with Undo. An added chapter is never `deleted`: it is dropped. */
  deleted: boolean
}

export type EditableChapter = { key: ChapterKey; name: string; movable: string[]; ignored: string[] }
export type Orders = ReadonlyMap<ChapterKey, readonly string[]>
export type Removals = ReadonlyMap<string, ChapterKey>

/** What the operator changed. `clip-cuts-screen` adds its per-clip properties here. */
export type Draft = {
  chapters: readonly DraftChapter[]
  orders: Orders
  removed: Removals
  metadata: MetadataDraft
}

/** What Edit mode read: never changes during the session. */
export type Baseline = {
  read: ReelDocument
  chapters: readonly DraftChapter[]
  original: Orders
}

export type ChapterChanges = { added: number; renamed: number; deleted: number; reordered: boolean }

export function draftChapters(chapters: readonly EditableChapter[]): DraftChapter[]
export function chapterChanges(baseline: Baseline, chapters: readonly DraftChapter[]): ChapterChanges
export function isStructural(changes: ChapterChanges): boolean
export function isDirty(baseline: Baseline, draft: Draft): boolean
export function buildWriteBody(baseline: Baseline, draft: Draft): ReelWriteBody
export function adoptedNewCount(baseline: Baseline, draft: Draft, newClips: ReadonlySet<string>): number

export function addChapter(draft: Draft, key: ChapterKey, name: string): Draft            // appended, empty
export function renameChapter(draft: Draft, key: ChapterKey, name: string): Draft
export function moveChapter(draft: Draft, key: ChapterKey, delta: -1 | 1): Draft          // among all listed
export function deleteChapter(draft: Draft, key: ChapterKey): Draft                       // caller checked
export function restoreChapter(draft: Draft, key: ChapterKey): Draft
export function moveClips(
  draft: Draft, from: ChapterKey, to: ChapterKey, identities: readonly string[], original: Orders,
): Draft
/** The chapter each clip was in when Edit mode opened. */
export function originOf(original: Orders): ReadonlyMap<string, ChapterKey>
```

- `chapterChanges`: `added` counts listed chapters with `readName === null`; `renamed`, read chapters not
  deleted whose `name !== readName`; `deleted`, read chapters with `deleted`; `reordered`, whether the read
  chapters that are not deleted appear in another relative order than read. Moving an added chapter is part
  of "added", not a reorder.
- `isDirty` is true for a changed field, an order that differs from the original (a chapter key present in
  only one of the two maps counts), or any non-zero `chapterChanges`. An added chapter that is deleted again
  is dropped from `chapters` and from `orders`, so it leaves nothing.
- `deleteChapter` of an added chapter drops it; of a read chapter sets `deleted`. A deleted chapter keeps its
  `orders` entry (empty, since only an empty chapter is deleted) and its removals, so Undo restores both.
  The deleted placeholder lists no rows, so its removed clips have no Undo of their own; the reducer also
  refuses a `restore` whose chapter is deleted, so a deleted chapter never plays a clip.
- `moveChapter` swaps the chapter with its nearest **non-deleted** neighbour in that direction; a deleted
  placeholder keeps its index, so a press never only "passes" a placeholder (which would announce a move
  that changes nothing written). Positions ("chapter *k* of *n*") count the non-deleted chapters; Move up
  is unavailable on the first of them, Move down on the last.
- `moveClips` ignores an identity `from` does not hold, so a repeated submit is a no-op.
- `buildWriteBody` follows "What a save writes". The `clips` map is the read one less the removed
  identities (removed from a deleted chapter too). A moved clip's entry is kept: it is keyed by identity,
  not by chapter (probe: "per-clip properties follow a moved clip").
- `isDirty`, `adoptedNewCount` and `buildWriteBody` decide "written from the view" with one helper,
  `writtenFromView(baseline, draft): DraftChapter[]`, so the count and the body cannot disagree. Its
  triggers (structural, order changed, no chapters named) are collected in that one function, never inlined
  or re-derived by a caller: it is G2's extension point ("Files and the G2 seam").

**Rationale**: Name-keyed maps break the moment a chapter is renamed. A `Draft` value lets G2 add
`cuts: ReadonlyMap<string, readonly Trim[]>` (or similar), one merge step in `buildWriteBody` and one trigger
in `writtenFromView` without a new parameter on every call ("Files and the G2 seam"). The reducer keeps `Ready.read/original` and replaces `orders`, `removed`,
`metadata` with one `draft: Draft` plus `baseline: Baseline`.

### Name checks and D-12 notes: `chapterNames.ts`

**Decision**: A new pure module (type-only imports, like `draft.ts`):

```ts
export type NameRefusal = 'empty' | 'taken' | 'taken-deleted' | 'reserved'
export function checkName(
  chapters: readonly DraftChapter[], typed: string, self: ChapterKey | null,
): { ok: true; name: string } | { ok: false; refusal: NameRefusal; clash: string | null }

/** Folders holding a clip on disk ('' = the event folder): from the detail's identities, missing ones excluded. */
export function diskFolders(clips: Iterable<Clip>): ReadonlySet<string>

/** The later-clips notes of every chapter, in the order below. */
export function laterClipNotes(input: {
  chapters: readonly DraftChapter[]
  folders: ReadonlySet<string>
  ignored: ReadonlyMap<ChapterKey, readonly string[]>
}): ReadonlyMap<ChapterKey, readonly string[]>

/** The note the name dialog shows for `typed` on `self` (null for Add). */
export function nameDialogNote(input: …, self: ChapterKey | null, typed: string): readonly string[]
```

The notes, with `M` the event's own chapter's heading at that moment (`Main` while another chapter is
listed, `Clips` when it is the only one, the read view's rule): the operator must be able to find M on the
page, and after deleting the only other chapter no `Main` is shown anywhere:

| When (exact name comparison) | Note |
|---|---|
| A read chapter named after folder `F` is renamed away or deleted, and no other listed, non-deleted chapter is named `F` | No chapter will be named after the folder “F”, so clips added to it later will join M. |
| … and the event's own chapter is deleted too, or not listed | No chapter will be named after the folder “F”, so clips added to it later will start a new Main chapter at the end. |
| A chapter is added with, or renamed to, the name of a folder `F` that holds clips, and was not named `F` when read | Clips added to the folder “F” later will join this chapter. Clips from it that other chapters list stay where they are. |
| … and other chapters list ignored clips from `F` | Its *n* ignored clips will be listed here. |
| A renamed or deleted read chapter lists ignored clips | Its *n* ignored clip(s) will be listed under M. |
| … and the event's own chapter is deleted too, or not listed | Its *n* ignored clip(s) will be listed under a new Main chapter at the end. |
| The event's own chapter is deleted | Clips added to the event folder later will start a new Main chapter at the end. |

"Not listed" covers a document that never named the event's own chapter: its later clips start a new
`Main` at the end too, so the note says so rather than "join Main". An ignored clip's notes follow where the
page will list it after the save: under the chapter named exactly after its folder (that chapter's "listed
here" note), else under the event's own chapter (the renamed or deleted chapter's "listed under Main" note).

A case-only difference (`kvällen` for folder `Kvällen`) matches no folder, so the first row applies. The
name dialog shows the notes only while the typed name would be accepted (`checkName`): for a refused name
they would describe a change that cannot happen. The notes are shown in the name dialog as typed (below the field, in its description, not live) and in the
chapter's tools row (or its deleted placeholder) after the edit. They are part of the announcement of the
edit that caused them.

### The chapter tools row

**Context**: The sticky panel header must stay one line (edit.css 366-369; `scroll-padding-top` counts on
it) and already holds the heading, the moved badge and the clip count.

**Decision**: The tools go in a row of their own between the header and the column strip, not sticky.
Rendered only when it has something to show (a note or a control), so `Grillning` in Edit mode looks as it
does today.

```html
<section class="panel edit-chapter" aria-labelledby="h" data-chapter-key="r1">
  <header class="panel-header">
    <h2 id="h" tabindex="-1">Kvällen</h2>
    <span class="badge" data-tone="info">2 clips moved</span>
    <span class="panel-meta">3 clips</span>
  </header>
  <div class="chapter-tools" role="group" aria-labelledby="h">
    <div class="chapter-notes" id="n">
      <p>Renamed from “Kvällen”.</p>                    <!-- or "New chapter." for an added one -->
      <p>No chapter will be named after the folder “Kvällen”, so clips added to it later will join Main.</p>
    </div>
    <div class="chapter-actions">
      <button class="btn btn-ghost chapter-rename" aria-label="Rename chapter Kväll"><svg/>Rename…</button>
      <button class="btn btn-ghost chapter-move-clips" aria-label="Move clips from Kväll"><svg/>Move clips…</button>
      <span class="chapter-order">
        <button class="btn btn-ghost btn-icon chapter-up" aria-label="Move chapter Kväll up"><svg/></button>
        <button class="btn btn-ghost btn-icon chapter-down" aria-label="Move chapter Kväll down"><svg/></button>
      </span>
      <button class="btn btn-ghost chapter-delete" aria-label="Delete chapter Kväll"
              aria-disabled="true" aria-describedby="why"><svg/>Delete</button>
    </div>
    <p class="chapter-refusal" id="why" hidden>“Kväll” still plays 3 clips. Move them to another chapter first.</p>
  </div>
  <div class="clip-order-head">…</div> <ol class="clip-order">…</ol> …
</section>
```

- Icons: `pencil` (Rename), `arrow-right` (Move clips, new), `arrow-up` / `arrow-down`, `x` (Delete, as a
  missing clip's Remove: both take an entry out of `reel.yaml` on save).
- Which controls: Rename on every listed chapter but the event's own; Move up / Move down, Move clips and
  Delete while more than one chapter is listed (deleted ones aside). Move up is `aria-disabled` on the first,
  Move down on the last. Move clips is `aria-disabled` while the chapter plays no clip on disk, with the
  note "No clips to move." in its description. Delete is `aria-disabled` while the chapter plays a clip (or,
  for the event's own, lists an ignored clip that would stay under it), described by its refusal, which is
  `hidden` until pressed.
- Delete's refusal, shown (`hidden` removed) and announced on a press, focus staying on Delete. Clips on
  disk and missing clips are counted apart, since Move clips moves only the former:
  - only clips on disk: "“Kvällen” still plays 3 clips. Move them to another chapter first."
  - both: "“Main” still plays 3 clips. Move the 2 clips on disk to another chapter and remove the missing
    one first."
  - only missing clips: "“Main” still lists 1 missing clip. Remove it first."
  - the event's own chapter with ignored clips that would stay: "“Main” still lists 1 ignored clip that no
    other chapter will take, so it stays." (Not "from the event folder": a subfolder's ignored clip with no
    chapter of its own is listed there too.)
- The event's own chapter's note ("The event's own chapter: …") is shown while another chapter is listed.
- A listed chapter that plays no clip says so and how clips get in. With no removed or ignored clip either,
  it shows, instead of the column strip and the list: `<p class="chapter-empty">No clips. Move clips here
  with another chapter's Move clips. A chapter without clips is left out of the movie.</p>`. When it still
  lists removed or ignored clips, the column strip stays and `<p class="chapter-empty">It plays no clip.
  Move clips here with another chapter's Move clips. A chapter without clips is left out of the movie.</p>`
  comes before those lists.
- Deleted placeholder (`ChapterTools.tsx`, `DeletedChapter`), in the chapter's place:

```html
<section class="panel edit-chapter" data-deleted aria-labelledby="h">
  <header class="panel-header">
    <h2 id="h"><s>Kvällen</s></h2>
    <span class="badge" data-tone="warn"><svg x/>Deleted when you save</span>
  </header>
  <div class="chapter-tools">
    <div class="chapter-notes"><p>No chapter will be named after the folder “Kvällen”, …</p></div>
    <div class="chapter-actions">
      <button class="btn btn-secondary chapter-undo" aria-label="Undo deleting chapter Kvällen"><svg rotate-ccw/>Undo</button>
    </div>
  </div>
</section>
```

- **Add chapter** follows the last chapter: `<div class="chapter-add"><button class="btn btn-secondary"><svg
  plus/>Add chapter</button></div>`. Not offered in the needs-attention form (no detail).
- While a save is in flight every one of these is `aria-disabled` and ignores presses (never `disabled`,
  which drops focus).

**CSS** (`edit/chapters.css`, `@layer screens`, imported by `ChapterTools.tsx`):

```css
.chapter-tools {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3);
  padding: var(--s-2) var(--s-4); border-bottom: 1px solid var(--border);
}
.chapter-notes { flex: 1 1 16rem; min-inline-size: 0; color: var(--fg-muted);
  font-size: var(--text-sm); overflow-wrap: anywhere; }
.chapter-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-1);
  margin-inline-start: auto; }
.chapter-order { display: flex; gap: 0.125rem; }
.chapter-refusal { flex-basis: 100%; color: var(--err-fg); font-size: var(--text-sm); }
.chapter-empty { padding: var(--s-4); color: var(--fg-muted); font-size: var(--text-sm); }
.edit-chapter[data-deleted] > .panel-header { background: var(--surface); }
.edit-chapter[data-deleted] h2 { color: var(--fg-muted); }
.edit-chapter > .panel-header > h2:focus { outline: none; }   /* focused by script, as the page h1 */
.chapter-add { display: flex; }
@media (pointer: coarse) {
  /* 16 px both ways: see below. */
  .chapter-actions { gap: var(--s-4); }
}
```

The coarse-pointer gap is `--s-4` (16 px) both ways. Each 32 px button's area grows 6 px up and down. The
up/down pair's areas (`.btn-icon + .btn-icon`, components.css 842-848) meet at their shared edge and grow
outward by `100% + 1px - 2.75rem` from the 30 px padding box, which is 12 px beyond the border box; a text
button wider than 44 px grows none sideways. A gap equal to that growth makes the areas touch exactly, and
pixel rounding then hands the edge to the neighbour painted later: measured at 320 px with a 12 px column
gap, a tap on Move clips' right edge reached Move up, and one on Move down's right edge reached Delete
(42 of 49 grid points each). With 16 px the 4 px left over keeps every area its own (49 of 49), as the
design system already does for wrapped rows (components.css 851-862).

Under a coarse pointer the hit areas are the design system's `.btn::after` (components.css 829-848),
unchanged: each button's border box grown to 44 px each way, and for the up/down pair anchored away from
the other, as the clip rows' move pair already is. The tools row's `--s-2` vertical padding holds the
6 px each button's area grows into, so no area reaches the header or the column strip.

At 320 px the panel's content box is 254 px wide: the notes take the first line(s); Rename… and Move clips…
the next; the up/down pair and Delete the one after. Nothing is `nowrap` beyond a button's own label, so
nothing overflows. At 1280 px the row is one line: notes left, actions right. Every text is `--fg-muted`
or stronger (4.5:1, web-design-system's tokens); no new colour.

**Rationale**: Not in the sticky header (it would grow past one line and break the scroll padding), not in a
menu (no menu primitive; D-8). Text labels, because "Rename" and "Move clips" are clearer than icons, with
the chapter's name in the accessible name since every chapter has the same buttons.

### The name dialog

**Decision** (`ChapterDialogs.tsx`, `NameDialog`), one component for Add and Rename:

```html
<dialog class="dialog" aria-labelledby="t" aria-describedby="d">
  <h2 class="dialog-title" id="t">Add a chapter</h2>             <!-- Rename: Rename “Kvällen” -->
  <div class="dialog-body" id="d">
    <p>The name is the heading of the chapter's title card in the movie.</p>
  </div>
  <form class="dialog-fields" id="f" novalidate>
    <div class="field">
      <label class="field-label" for="i">Name</label>
      <input class="field-input" id="i" type="text" autocomplete="off" spellcheck="true"
             aria-invalid="true" aria-describedby="e notes" />
      <p class="field-error" id="e" role="alert">A chapter called “Kvällen” already exists.</p>
      <div class="field-hint" id="notes"><p>Clips added to the folder “Kvällen” later will join this chapter. …</p></div>
    </div>
  </form>
  <div class="dialog-actions">
    <button class="btn btn-secondary" type="button">Cancel</button>
    <button class="btn btn-primary" type="submit" form="f">Add chapter</button>  <!-- Rename: Rename -->
  </div>
</dialog>
```

- Opens with focus in the field (`initialFocus`), Rename with the current name selected. Enter submits
  (implicit submission); Escape or Cancel closes, changes nothing, focus returns to the opener (Dialog).
- Checked on submit only (`checkName`); once refused, re-checked as typed, so the error leaves when the name
  is good. Refusal copy:
  - `empty`: "Enter a name. A chapter's name is the heading of its title card."
  - `taken`: "A chapter called “Kvällen” already exists. Names are compared ignoring case."
  - `taken-deleted`: "“Kvällen” is deleted when you save. Undo that, or pick another name."
  - `reserved`: "“Main” is how the page names the event's own chapter. Pick another name."
- The error is `role="alert"` **inside** the dialog, keyed by a refusal counter so a repeated refusal is
  re-announced: while a modal is open, the editor's live region outside it is inert.
- A rename to the same name, or one differing only in spaces, closes and changes nothing.
- On success: Add appends the chapter, focus goes to its heading (scrolled into view), announcement "Chapter
  “Morgon” added, chapter 3 of 3. It has no clips." Rename returns focus to Rename (Dialog), announcement
  "“Kvällen” renamed to “Kväll”." followed by the chapter's later-clips notes.

### The Move clips dialog

**Decision** (`ChapterDialogs.tsx`, `MoveClipsDialog`):

```html
<dialog class="dialog" …>
  <h2 class="dialog-title">Move clips from “Kvällen”</h2>
  <div class="dialog-body"><p>The clips you pick join the end of the chapter you choose. Space picks a
    clip; Enter moves the picked clips.</p></div>
  <form class="dialog-fields move-clips" id="f" novalidate>
    <fieldset class="choice-group" aria-describedby="ce">
      <legend>Clips <span class="choice-count">1 of 3 picked</span></legend>
      <p class="field-error" id="ce" role="alert" hidden>Pick at least one clip.</p>
      <label class="choice choice-all"><input type="checkbox" /> Pick all</label>  <!-- mixed while some -->
      <ul class="choice-list">
        <li><label class="choice"><input type="checkbox" value="Kvällen/s1710002.mp4" />
          <span class="choice-pos">1</span> <span class="choice-name">s1710002.mp4</span></label></li>
        …
        <li><label class="choice">… s1710004.mp4 <span class="badge" data-tone="info">New</span></label></li>
      </ul>
    </fieldset>
    <fieldset class="choice-group" aria-describedby="te">
      <legend>Move to</legend>
      <p class="field-error" id="te" role="alert" hidden>Choose a chapter to move them to.</p>
      <ul class="choice-list"><li><label class="choice"><input type="radio" name="to" value="r0" checked /> Main</label></li></ul>
    </fieldset>
    <p class="field-hint">Not offered: 1 missing clip, which stays in its chapter until its file is restored
      or it is removed, and 1 ignored clip, which is not played.</p>
  </form>
  <div class="dialog-actions"><button …>Cancel</button><button type="submit" form="f" class="btn btn-primary">
    <svg arrow-right/>Move clips</button></div>
</dialog>
```

- Clips: the chapter's play order now, on-disk ones only (status `active` or `new`), named by the chapter's
  `nameOf`; NEW ones carry a "New" badge (label from `CLIP_STATUS_LABEL`, never the slug). Targets: every
  other listed, non-deleted chapter, by heading; checked already when it is the only one.
- **Pick all** (approved addition, after review): a native checkbox row above the clips, before the first
  box in tab order (Shift+Tab from it). Checked when every offered clip is picked, `indeterminate` (mixed)
  while only some are; a press picks all, or clears all when all are picked. Emptying or splitting a long
  chapter is then one press, not one per clip (400 on the scale fixture). Shift-click ranges stay a
  follow-up. It is a `.choice` row (44 px under a coarse pointer), framed like the list.
- Initial focus: the first clip's box. Space toggles. **Enter** on any box or radio submits (`onKeyDown` on
  the form calls `preventDefault()` then `requestSubmit()`, so a browser that also submits on Enter there
  does not submit twice), so a 400-clip list need not be tabbed through; the description says so.
  The radios are one tab stop, arrows choose (native).
- Submit with no clip: the clips' error shows and focus goes to the first box. With no target: the targets'
  error and focus on the first radio. Nothing moves.
- Success: the dialog closes, focus returns to Move clips (Dialog), announcement "2 clips moved to “Main”."
  The dialog closes at once and the move is applied in a React `startTransition`: on the 400-clip fixture
  one commit for both took 187–206 ms from Enter to the dialog's close (the long list re-renders every row),
  against the 200 ms target; split, the dialog closes in about 80–90 ms and the lists follow. Until the
  transition lands the page still shows the order from before the move, so nothing may act on it:
  `movingFrom` (set before the transition, cleared inside it) makes every chapter control, Add chapter,
  Undo and the clip rows `aria-disabled` (never `disabled`), the pressed Move clips also `aria-busy`, and
  every chapter handler and Save ignore a press meanwhile. Without this, a Delete pressed on the emptied
  chapter inside that window was refused as "still plays 3 clips".
- Size: `.dialog:has(.move-clips) { inline-size: min(32rem, calc(100vw - 2 * var(--s-4))); }`; the clips'
  `.choice-list` scrolls on its own (`max-block-size: min(45dvh, 22rem); overflow-y: auto`), so the
  targets and actions stay in view. `.choice` is a grid row (`1rem auto minmax(0,1fr)`: box, position, name;
  a target row `1rem minmax(0,1fr)`). A NEW clip's badge sits inside the name cell, a flex row that wraps it
  under the name with `white-space: normal`: its label (`CLIP_STATUS_LABEL.new`, "New, not yet in reel.yaml")
  is too long for a column of its own at 320 px. `min-block-size:
  2.25rem`, `2.75rem` under `pointer: coarse`, rows touching (no gap), so each tap area is its own row; the
  native boxes take `accent-color: var(--accent)`; names wrap (`overflow-wrap: anywhere`).

### Dialog descriptions: `.dialog-fields`

**Context**: `Dialog` makes every child except `.dialog-actions` its description (Dialog.tsx 82-91). A form
inside would make a 400-clip list the description, read out in full when the dialog opens.

**Decision**: A direct child with class `dialog-fields` is also left out of the description, and rendered
between the body and the actions. A three-line change in `ui/Dialog.tsx` (`isActionsRow` becomes
`isOutsideDescription`, and the parts are split in three). Existing dialogs have no such child and render
exactly as before.

**Rationale**: The "A confirmation dialog states its consequence" requirement wants the explanation as the
description, not the controls. The alternative, a `description` prop, would change every caller.

### Keyboard model and focus

All controls are native buttons, checkboxes and radios; no shortcut keys are added.

| Action | Focus after | Announcement |
|---|---|---|
| Add chapter → confirm | the new chapter's `h2` (`tabindex="-1"`), scrolled `nearest` (see below: a passive effect) | Chapter “X” added, chapter *k* of *n*. It has no clips. + notes |
| Rename → confirm | Rename (Dialog's opener) | “A” renamed to “B”. + notes |
| Move up / Move down | the same button, also once it is `aria-disabled` at an end | “A” moved to chapter *k* of *n*. |
| Delete, empty read chapter | its placeholder's Undo | “A” will be deleted when you save. + notes |
| Delete, added chapter | Add chapter | Chapter “A” removed. |
| Delete, refused | stays on Delete; refusal shown | the refusal |
| Undo (deleted chapter) | the restored chapter's Delete | “A” is back, chapter *k* of *n*. |
| Move clips → confirm | Move clips (Dialog's opener) | *n* clip(s) moved to “B”. |
| Cancel / Escape in a dialog | the opener | — |

A chapter move re-orders the sections, and moving a DOM node drops its focus, so the editor records
`focusAfter = { key, target }` and a layout effect focuses `[data-chapter-key="…"] .target` with
`preventScroll`, then the passive effect scrolls that chapter's tools row `nearest` (the clip lists' own
pattern, ClipOrderList 559-597).

**Add chapter is the one exception.** `Dialog` returns focus to its opener (Add chapter) from its effect's
cleanup (Dialog.tsx 71-79), a passive effect. React runs every layout effect of a commit, then every
passive cleanup, then every passive effect, so a layout-effect focus on the new heading would be undone by
that cleanup. The editor therefore focuses the new chapter's heading from a **passive** effect (it runs
after the cleanup of the same commit), dispatching the add and closing the dialog in one handler so both
land in that commit. Rename and Move clips want the opener back, which the cleanup already does.

The announcements go through the editor's one live region (`announce`, which sets its text a frame later,
after the dialog has closed). When the unsaved-changes question opens (`leaveQuestion`), an open chapter
dialog closes first, as a cancel.

### Counts, badges, the save bar and the hint

- **`movedSet`'s first argument is the chapter's original order less every clip it no longer holds**
  (`original.filter((id) => order.includes(id))`, through a `Set`), in both callers, replacing today's
  "less the removed clips". That covers removals as before, and also the clips moved out, which would
  otherwise crash `keptInPlace` (see "Context") and would count against the clips left behind. One helper,
  `keptOriginal(original, order)` in `draft.ts`, serves both callers so they cannot disagree. `movedSet`
  itself is unchanged.
- A clip moved in from another chapter: `movedSet` already counts it (no original rank). Its row shows
  `<span class="badge clip-was" data-tone="info">from Kvällen</span>` (the origin chapter's current
  heading, `originOf`) instead of "was *n*"; the badge truncates with an ellipsis past 12rem (its full text
  stays in the accessibility tree).
- Names: `clipNames(name now, [...original, ...order, ...ignored, ...removed])`. A clip from another folder
  moved in makes the chapter name by path; moved back out, it names by file again.
- `summarize` gains, after the field parts and before the moves: "1 chapter added", "1 chapter renamed",
  "1 chapter deleted", "chapter order changed" (each only when non-zero / true), then the moves, removals
  and "adds *n* new clips to reel.yaml" as today.
- The hint (`edit-hint`): "Drag a clip by its handle, or use its arrows. Clips stay in their chapter; use a
  chapter's Move clips to move them to another." The second clause only while more than one chapter is
  listed (no Move clips exists otherwise); a single-chapter event keeps "Clips stay in their chapter." The
  NEW-clip sentence becomes "A new clip joins reel.yaml
  once its chapter's order, or the list of chapters, is saved."; the bold one "Saving adds *n* new clips
  to reel.yaml."
- Headings: `Main`/`Clips` from the draft's listed, non-deleted chapters.

### The read view's empty chapter

**Decision**: `ChapterPanel` renders, for a chapter with no played and no ignored clip, its header (count
"0 clips") and `<p class="chapter-empty">No clips. This chapter is left out of the movie.</p>` instead of
the table (`detail.css`, same rule as Edit mode's). It is an early return at the top of `ChapterPanel`
(12 lines): wrapping the table in a ternary instead would re-indent the whole table, a far larger diff.

### Performance

`ClipOrderList` stays `memo`. Its new props are primitives (`chapterKey`, `heading`, `name`) plus one
`tools` object per chapter, built in one `useMemo` whose inputs are the draft's `chapters`, `orders`,
`removed`, `locked` and the notes, never `metadata`: typing in a field re-renders no list. Every handler is
one stable `dispatch`-based callback taking the chapter key. The Move clips dialog renders only while open,
and its move is applied in a transition (see "The Move clips dialog").
Checked on the 400-clip fixture (tasks 5.1).

### Files and the G2 seam

| File | Change |
|---|---|
| `edit/draft.ts` | keys, `Draft`/`Baseline`, chapter operations, `moveClips`, write rules, `keptOriginal` |
| `edit/chapterNames.ts` (new) | `checkName`, `diskFolders`, notes |
| `edit/ChapterTools.tsx` (new) | tools row, `DeletedChapter`, `AddChapter` |
| `edit/ChapterDialogs.tsx` (new) | `NameDialog`, `MoveClipsDialog` |
| `edit/chapters.css` (new) | the rules above |
| `edit/EventEditor.tsx` | reducer actions `chapter-add/-rename/-move/-delete/-restore`, `clips-move`; focus; summary; hint |
| `edit/ClipOrderList.tsx` | keyed by `chapterKey`; `DndContext id={`chapter-${chapterKey}`}`; tools slot; empty state; "from" badge; names |
| `ui/Icon.tsx` | `plus`, `arrow-right` |
| `ui/Dialog.tsx` | `.dialog-fields` |
| `events/EventDetail.tsx`, `events/detail.css` | empty chapter |
| `web/README.md`, `docs/high-level-design.md` | docs |

G2 (`clip-cuts-screen`, gated on this change) extends these, so this change keeps each one a single place:

- **`writtenFromView(baseline, draft)`** is the extension point for what a save writes from the view. G2
  adds a per-clip trigger: a chapter that plays a NEW clip whose properties changed, and any per-clip change
  when the document names no chapters. This change therefore collects every trigger in that one function;
  no caller inlines or specialises it (for example by testing "order or chapter changed" itself).
- `Draft` gains a field, and `buildWriteBody`'s `clips` section one merge step; `isDirty` gains one term.
- The editor's `afterEdit`, its `dirty`, and `submit`'s guard: G2 adds a typed-cut hold beside
  `dateIncomplete`, so each tests one flag, not a copy of the date rule.
- `summarize` and the hint: G2 adds save-bar parts and changes the NEW-clip sentence.
- Its per-row Cuts control goes in the row space this change leaves free.

G2 does not touch chapter keys, `chapterChanges` or the tools row.

### HLD

`docs/high-level-design.md` §7 gains:

> **D-13 — Chapters are edited in GUI v1** (2026-10-01, change `chapter-management-screen`). Edit mode adds,
> renames, reorders and deletes chapters, and moves clips between them with a per-chapter Move clips
> dialog, pulled forward from v3 at the operator's request. Dragging across chapters stays v3. A save that
> changes the chapter list writes every chapter as shown, so every NEW clip is adopted where the page shows
> it; a chapter's name then only decides where later clips go (D-12). The event's own chapter keeps no name,
> and a chapter is deleted only once empty. (§4.10)

§4.10's v1 bullet gains "**chapter edits and Move clips** (**D-13**)" after "drag-reorder clips (persist to
`reel.yaml`)", as D-11 named thumbnails there; its v3 line reads "drag across chapters" instead of "reorder
across chapters"; and slice row D gains one sentence naming this change.

### Verification fixtures

The implementing agent's own environment (dev-env runbook §9): `SLUG=chapter-management-screen`, `N=26`,
database `arel_chapter_management_screen`, library `../dev-chapter-management-screen`, `serve` on port
**8126**, no worker (nothing renders). In that library copy only:

- `2024/2024-09-15 - Stor dag`: the recipe of `archive/2026-09-30-event-edit-screen/design.md`
  ("Verification fixtures", ad hoc): 400 symlinks `c0001.mp4`…`c0400.mp4` at the event's root to one cut
  clip of the library's `clips/`, plus, for this change, 3 symlinks `Kväll/k001.mp4`, `Kväll/k002.mp4` and
  `Kväll/k003.mp4` to the same clip. **No `reel.yaml`**, so the page seeds two chapters: the event's own
  (400 clips) and `Kväll` (3).
- For the ignored-clip scenarios, append `- Kvällen/s1710004.mp4` to `Två kapitel`'s `ignore` by hand, and
  restore the saved copy afterwards.
- For "A moved clip keeps its cut", add `clips: {Kvällen/s1710002.mp4: {trims: [{in: 0, out: 1.5}]}}` to the
  same file, likewise restored.

**Normalise before copying.** `make_dev_library.py` re-dumps two files with ruamel's default indentation:
`2024-06-27 - Grillning med grannar` (`_edit_title`) and `2024-08-20 - Två kapitel - Tjörn` (`_ignore`). The
engine's writer (`reel/writer.py` 28-35, `indent(mapping=2, sequence=4, offset=2)`) re-indents every list
on its first real write, and every chapter-list save here is one. So before copying any `reel.yaml` a check
will `diff` (these two in particular), load it and dump it again with `YAML()` and `indent(mapping=2,
sequence=4, offset=2)`, then take the copy. A `diff` after a save then shows only the scenario's lines.

Each `reel.yaml` touched is copied first and compared after with `diff`.

## Failure behavior & idempotency

- Nothing renders, enqueues or probes. A save is the existing single `PUT` with `If-Match`; every failure
  path (400, 404, 412 with Reload / Overwrite, 502, no answer, an error in the page) keeps the draft,
  chapters included, and is shown by `SaveBar` as today. Overwrite sends the same body (structural rules
  included) under the fresh tag.
- The engine refuses what the GUI should never send (duplicate names, a clip in two chapters, properties
  for an unlisted clip): a 400 with the engine's detail, draft kept. The pure model makes these
  unreachable; the scratch tests in tasks 2.1 assert it.
- Re-running a save of the same draft is a no-op on disk (the merge leaves equal lists untouched). A save
  that only restores what was read is not offered (`isDirty` false).
- The detail is re-read after every save; a changed event between the page read and Edit mode still shows
  the "changed on disk" guard (`detailMatchesDocument`, unchanged: it compares the page with the document,
  before any edit).

## Risks / Trade-offs

- **A renamed chapter loses its clips' `reel.yaml` comments** (the merge matches by name). → Stated in the
  proposal's non-goals and here; an engine follow-up could match a renamed chapter by its clips. The UI does
  not warn per rename: the operator who comments `reel.yaml` by hand is also the one who sees the diff.
- **A structural save adopts every NEW clip of the event**, also in chapters the operator did not touch. →
  The save bar says how many before the save; it is what keeps the page and the movie in agreement.
- **Reordering chapters replaces the `chapters` sequence node**, so a comment line between two chapters can
  move or be dropped (editorial.py 217-224 keeps the node only when chapters keep their places). → Rare
  (comments sit on clips, not between chapters); accepted.
- **Enter submits from a checkbox**, which native forms do not do. → The description says so, and it is the
  only way a 400-clip list is usable from the keyboard without range selection.
- **Case-insensitive uniqueness uses `toLocaleLowerCase()`**, which differs from Unicode case folding for a
  few scripts. → Only a stricter-than-needed refusal at worst; the engine's exact check is the backstop.
- **The dialogs grow `ChapterDialogs.tsx`.** → Both are plain forms; no focus trap code (native modal).

## Migration Plan

None: no data, schema or API change. A `reel.yaml` written by this change is an ordinary v0 document; an
older client reads it. Rollback is reverting the web build.
