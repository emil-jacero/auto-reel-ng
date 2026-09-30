## Context

See proposal.md, "Why". The code this change starts from is `main` at `541c44c`, plus its two gates:
`web-design-system`, which lands the shared UI named below, and `editorial-chapter-roundtrip`, which makes a
PUT keep the comments on clip entries (see "The editorial API").

**The page and the route** (line numbers at `541c44c`; `web-design-system` rewrites the markup but keeps the
structure, the `LoadState` pattern and the hash routing)
- **`web/src/events/EventDetail.tsx`** holds a `LoadState` (`loading | ready | failed`) and a
  `load()` that aborts the previous read and sets `loading` (`EventDetail.tsx:62-100`). `ReadyView` renders
  the facts, the status line, the counts and one `ChapterTable` per chapter (`:144-187`). Chapters are keyed
  by index (`:182`; `web-design-system` keys them by name, unique per event) and clip rows by `identity`
  (`:232`). A failed read renders one `role="alert"` block (`:122-137`).
- **`web/src/route.ts`**: `useRoute()` sets its state from `parseRoute(location.hash)` on every
  `hashchange` (`route.ts:49-56`). `hashchange` cannot be cancelled. `App.tsx:42-49` runs a layout effect
  keyed on the `route` object, so a new but equal route object scrolls an event page to the top;
  `web-design-system` adds `focusPageHeading()` to the same route-change path, so it would also move focus.
- **`web/src/main.tsx:12`** renders under `<StrictMode>`. Effects run twice in the dev server only; the
  production build `serve` mounts does not replay them.
- **`web/src/api/http.ts`** has `isProblem` and `readJson`. No module sends a method, a header or a body
  yet. No module reads a response header.
- **`web/src/events/EventList.tsx`** already imports `eventHref` (`:5`); the attention row's folder cell is
  plain text (`:82`).

**What `web-design-system` gives this change** (fixed names; checked by task 1.1):
- `Icon` (`grip-vertical`, `arrow-up`, `arrow-down`, `pencil`, `check`, `rotate-ccw`, `x`,
  `alert-triangle`, `loader`)
- `Dialog` (native `<dialog>`; the native `close` event, including Escape, calls `onClose` while `open` is
  true; focus returns to the opener; an optional `initialFocus?: RefObject<HTMLElement | null>` is focused right
  after `showModal()`, else the first focusable child)
- `toast.success` / `toast.error`, and a `ToastRegion` whose bottom offset is the custom property
  `--toast-inset-bottom` (default 0)
- `Pill` (`ui/Pill.tsx`), `Alert` (`ui/Alert.tsx`, `role="alert"` by default), `SkeletonRows`
  (`ui/Skeleton.tsx`), and `CLIP_STATUS_LOOK` (`events/tones.ts`, tone and icon per clip status)
- the `btn` classes, and the busy-control rule: the control the operator just pressed gets
  `aria-disabled="true"` + `aria-busy="true"` and ignores clicks while in flight, never the `disabled`
  attribute (which drops focus to `<body>`)
- `markEventsChanged()` in `events/changes.ts`
- the `@layer reset, tokens, base, components, screens` order, `scroll-padding-top` for the sticky header,
  and the motion rule: every `animation` is declared inside `@media (prefers-reduced-motion:
  no-preference)` with a literal loop duration, and the `--dur-*` tokens are for transitions only

**The editorial API** (`auto_reel_ng/api/routes/events.py`)
- `GET …/reel` (`:158-189`) returns `EditorialDocumentBody` and sets `ETag` to `"<editorial_hash>"`
  (`:76-83`, `:188`). The tag is strong and quoted, and a comment-only edit does not change it.
- An event with no `reel.yaml` reads as the empty document (`events_read.py:396-409`). This includes the
  unusable-metadata events: the reel read never checks processability, only the detail read does
  (`events_read.py:121-122`).
- A malformed file is a 502 with `failure` (`events.py:185-186`).
- `PUT …/reel` (`:222-302`) takes the complete desired state. `extra="forbid"` applies to every body model
  (`api/schemas.py:150-209`). An omitted section is cleared (`event/editorial.py:84-195`).
  - The write merges onto the file's own round-trip structure (`editorial.py:63-73`,
    `reel/writer.py:39-51`), so keys the body does not model, such as the event's `sort`, survive.
  - `_apply_chapters` reuses chapter nodes by name (`editorial.py:157-195`). At `541c44c` it always empties
    and refills each chapter's `clips` sequence (`:188-191`), so end-of-line comments on clip entries are
    lost on **every** save, even a body sent back unmodified (checked on a scratch copy of the dev
    library's `Sommarlov` `reel.yaml`, `- borttagen.mp4  # MISSING`). The gate `editorial-chapter-roundtrip`
    fixes this in the engine: an unchanged chapter's clips node is left untouched, a reordered chapter moves
    its existing items with their comments, a removed item drops only its own comment, and an added item
    gets none. This editor resends every chapter on each save, so it relies on that fix; task 5.1 checks it
    in the browser (the Sommarlov swap keeps `# MISSING`).
- PUT outcomes:
  - 400 with `failure: unusable_metadata` for a missing, impossible or future date or a missing title
    (`events.py:285-288`). The explanation is in `detail` only; the body carries no field pointer.
  - 400 for any other invalid state (`:289-290`)
  - 404 (`:264-268`)
  - 412 on an `If-Match` mismatch, carrying no `ETag` (`:276-280`)
  - 502 for an unreadable existing file (`:274-275`) or a refused save, naming the OS error (`:291-293`)
  - 422 for a structurally invalid body (FastAPI)
- A failed write leaves the file untouched. The save is atomic (`reel/writer.py:59-82`).

**The detail's chapters are the reconcile view, not the document** (`events_read.py:260-311`):
- the document's chapters, in document order, each with its referenced clips in document order, including
  MISSING clips
- then the disk-only clips (NEW, and IGNORED: `event/reconcile.py:86-95`) appended to their disk chapter in
  sort order, NEW and IGNORED interleaved
- then disk chapters the document does not name, appended as new chapters
- With no document, it is the disk listing, and every clip is NEW.

Identities are unique within a document (`reel/schema.py:245-282`). A referenced clip cannot also be
ignored.

## Goals / Non-Goals

**Goals:**

- Edit the order and metadata with a body built from the document read, never from the detail. The detail
  only supplies the order the operator sees, plus the display facts.
- Pointer, touch and keyboard reordering that a screen reader can follow, and a non-drag path.
- No edit is lost silently, and no save overwrites a concurrent change unasked.
- Keep edits to shared files small, so `render-progress-screen` (built in parallel) merges cleanly.

**Non-Goals:**

- Cross-chapter moves, chapter structure, ignore/un-ignore, trims and `look` (proposal, "Non-goals").
- Rebasing edits onto a concurrent change (a merge).
- Any API change. Where the API's shape limits the UI (the 400 has no field pointer), the UI works within it
  and the gap is recorded.

## Research & Decisions

### The drag-and-drop library

**Context**: D-8 budgets exactly one drag-and-drop library for this slice. The app runs under
`<StrictMode>` (`main.tsx:12`). The requirement covers pointer, touch and keyboard sorting with
announcements, within one vertical list per chapter, at up to about 400 rows.

**Explored**: Session research on 2026-09-30 (`npm view` data, upstream issue #2116, the legacy
accessibility guide at `dndkit.com/legacy/guides/accessibility`). The note itself is not committed; its
findings are summarised here. The published `@dnd-kit/core@6.3.1` tarball was read to confirm the
`accessibility` prop (`announcements`, `screenReaderInstructions`, `restoreFocus`) and that a modifier's
`containerNodeRect` is the rect of the dragged node's parent element. Candidates:

| Option | Why not chosen |
|---|---|
| `@dnd-kit/react` 0.5 | 0.x, with open issue #2116: the manager is destroyed during the StrictMode replay, so dragging fails in dev |
| `@atlaskit/pragmatic-drag-and-drop` | No keyboard dragging in core. Its accessibility add-on pulls `@emotion/react` and Atlaskit tokens, which a CSS-framework rule forbids. |
| `@hello-pangea/dnd` | 1.26 MB, with redux and react-redux inside |
| `react-aria-components` | A component library (D-8 forbids one) |
| `sortablejs` | No keyboard support, and a stale React wrapper |
| Native HTML5 drag-and-drop | No touch support |

**Decision**: The legacy `@dnd-kit` line, pinned by caret and the lockfile:
- `@dnd-kit/core@^6.3.1`, `@dnd-kit/sortable@^10.0.0` and `@dnd-kit/utilities@^3.2.2`
- MIT licensed, peer `react >=16.8`
- transitive packages: `@dnd-kit/accessibility` and `tslib`

`@dnd-kit/modifiers` is not added. The one modifier this change needs is written by hand (about 10 lines,
passed to `DndContext`): `x = 0`, and `y` clamped so that the dragged row stays inside its chapter's `<ol>`
(`containerNodeRect`, which is the `<li>`'s parent element). Without the clamp, `closestCenter` would pick
the chapter's nearest clip while the pointer is over another chapter, and a release there would silently
move the clip to the end of its own chapter.

**Rationale**:
- It is the only candidate with keyboard sorting and customizable announcements built in.
- It works under StrictMode (the sortable StrictMode fix shipped in v7.0.2) and adds no styling system.
- It has had no release since 2024-12, which is acceptable for a small, stable surface. The migration to
  `@dnd-kit/react` is mechanical once it reaches 1.0 or #2116 is fixed (recorded in D-8, task 4.1).
- StrictMode only replays effects in the dev server, so the choice is checked there as well as on the built
  client (task 5.1).

### The editable order: shown from the detail, written from the document

**Context**: The operator must see the order the page shows, including NEW, MISSING and IGNORED clips. But
the write body must be the document as read, because the detail and the document are different models
(the `api-service` requirement "The events detail response is not an editorial write body").

**Explored**: Two options.
- Reorder the document's own chapter lists. This hides NEW clips, which the operator sees on the page and
  expects to place.
- Reorder the detail's lists and map them back onto the document. The session's API survey recommended the
  first option. The plan chose the second, because the page already shows NEW clips in their chapter.

**Decision**: `src/edit/draft.ts` holds pure functions with no runtime imports. Its type imports are written
as `import type …`, so Node's type stripping erases them and the scratch check in task 2.2 can import the file
directly:
- **The view:** `editableChapters(detail)` gives, per detail chapter, the movable identities in shown order.
  Those are every clip except IGNORED, including MISSING and NEW. The IGNORED identities form a fixed tail.
  With no detail (the needs-attention form), there are no chapters.
- **The body:** `buildWriteBody(read, original, next, metadataDraft)` returns
  `EditorialDocumentBody-Input`:
  - `look`, `clips` and `ignore` are copied from `read` unchanged.
  - Metadata: a field whose draft equals what was read (with `null` read as `''`) keeps the read value. An
    edited field is sent as typed, or as `null` when empty or whitespace-only (inherit).
  - Chapters:
    - No chapter order changed: `read.chapters`, verbatim.
    - `read.chapters` is empty and some order changed: every view chapter with at least one movable
      clip, in view order, as `{name, clips: next order}`. For an event with no `reel.yaml`, these are the
      chapters seeding would persist, in the operator's order.
    - Otherwise: `read.chapters` mapped in place. A chapter whose order changed gets its next order, and
      every other chapter is kept verbatim. A reordered view chapter that the document does not name is
      appended as a new chapter, in view order.
- **The summary:**
  - `movedSet(original, next, lastMoved)` returns the identities outside a longest increasing subsequence
    of the original positions, so moving one clip from 1 to 5 moves 1 clip, not 5. Its size is the chapter's
    "clips moved" count, and its members get the moved mark and a badge.
  - Ties: among equally long runs, `movedSet` keeps the one with the most clips at their original index,
    then the one without the clip the operator moved last, so a Move down on `s1710002.mp4` badges
    `s1710002.mp4`. It is a maximum-weight increasing run (a Fenwick tree over original positions,
    O(n log n)) whose weight has the three preferences as digits. (Review decision: the plain `lastMoved`
    tie-break could count a clip that never left its place, as in `[A,B,C]` → `[C,B,A]`, marking it with no
    old position while the bar counted it.)
  - A clip counted as moved can still sit at its original index when no longest run can keep it
    (`[A..E]` → `[D,E,C,A,B]` moves three, `C` among them). Its badge then says "moved" rather than
    "was N" at position N, so the count, the marks and the badges always agree.
  - `adoptedNewCount` counts the NEW clips in chapters that will be written from the view.
- **Dirty** (`isDirty`) is computed, never a flag: any metadata draft that differs from the read, or any
  order that differs from the original.

**Rationale**:
- Untouched sections are sent exactly as read, so their content survives every save. With the gate
  `editorial-chapter-roundtrip` in place, their bytes survive too, including end-of-line comments on clip
  entries (Context).
- A reordered chapter never drops a MISSING clip.
- The ignore list and per-clip properties are never touched, so cross-reference validation
  (`reel/schema.py:245-282`) cannot newly fail: no orphaned property and no ignore/structure conflict can
  appear.
- Pure functions can be checked from a scratch script without a committed test runner (task 2.2).

### The detail and the document must agree before editing

**Context**: The page reads the detail when it opens. Edit mode reads the document later. If `reel.yaml`
changed in between, the order the operator sees is not the order the document holds. `If-Match` protects
only against changes made after the document read.

**Explored**: Three options: re-read both on entering Edit mode, trust the timing, or compare the two.

**Decision**: On entering Edit mode, `detailMatchesDocument(detail, read)` checks that the first
`read.chapters.length` detail chapters have the document's names in the same order. For each of those
chapters, the detail's ACTIVE and MISSING identities must equal the document's list and must precede its
NEW and IGNORED ones. Every later detail chapter must hold only NEW or IGNORED clips. Every IGNORED identity
must be in `read.ignore`, and no NEW identity may be; otherwise a reorder could adopt a clip that was ignored
by hand in between, and the save would fail validation. When the check fails, Edit mode shows "This event
changed on disk since the page was read" with a "Read again" action (leave Edit mode, then the page's
`load`), and no Save.

The editor keeps the detail it was opened with. A later re-read of the page (a Refresh asks first, see the
guard) never changes the order shown or the draft of an open editor.

**Rationale**: The check is about 25 lines and fails loud (Principle I) instead of saving an order built on a
view that no longer exists. Re-reading both would still leave a window, and would double the reads. A change
on disk alone (a clip added or deleted between the two reads) passes the check: the document is the same,
and a clip deleted in between is written as a reference to a missing clip, which the engine allows (D-E4).

### Reading and writing the document (`src/api/reel.ts`)

**Context**: No client module sends a body or reads a header yet. The ETag is needed verbatim for
`If-Match`.

**Explored**: The existing read modules return discriminated results (`event.ts:18-55`), and the session's
React-patterns research covers ETag handling (verbatim echo, `no-store` on the read).

**Decision**:

```ts
export type ReelDocument = components['schemas']['EditorialDocumentBody-Output']
export type ReelWriteBody = components['schemas']['EditorialDocumentBody-Input']
export type ReelWriteResult = components['schemas']['EditorialWriteResult']

export type ReelReadResult =
  | { kind: 'ok'; document: ReelDocument; etag: string }
  | { kind: 'problem'; problem: Problem }         // 404, 502
  | { kind: 'unreachable'; message: string }       // rejected fetch, other status, bad body, no ETag
export async function fetchReel(eventId: string, signal: AbortSignal): Promise<ReelReadResult>

export type ReelSaveResult =
  | { kind: 'saved'; result: ReelWriteResult }
  | { kind: 'problem'; problem: Problem }         // 400, 404, 412, 502
  | { kind: 'unreachable'; message: string }       // rejected fetch, 422, other status, bad body
export async function saveReel(eventId: string, body: ReelWriteBody, ifMatch: string): Promise<ReelSaveResult>
```

- The read uses `cache: 'no-store'`. A 200 without an `ETag` is `unreachable` ("GET … answered 200 without
  an ETag"). Fail loud: never save unconditionally by accident.
- The write sends `Content-Type: application/json` and the `If-Match` verbatim. It is not abortable: a
  sent write cannot be recalled.
- Both reuse `readJson`, `isProblem` and `encodeEventId`.

**Rationale**: The module matches the house pattern, where expected failures are values. A successful
save's `ETag` is not used: a successful save leaves Edit mode and the page re-reads, so no chained write
exists in v1.

### Metadata form

**Context**: `reel.yaml` metadata overrides the folder name (D-2). A field left unset inherits.
Detail values are already resolved. The 400 names no field.

**Explored**: Three options for the displayed value:
- fill the fields with resolved values, which would persist folder values on the first save
- use placeholders, which do not render in `<input type="date">` in Chromium or Firefox
- show authored values plus a visible hint

**Decision**: `src/edit/MetadataForm.tsx` has four labelled controls: title (`<input>`), date
(`<input type="date">`), location (`<input>`) and description (`<textarea>`).
- **Values:** the read document's metadata, with `null` shown as `''`.
- **Inherited hint:** the detail's title, date and location are resolved per field: the authored value when
  it is set and not blank, else the folder name's (`event/metadata.py:38-45`). The detail therefore shows the
  folder name's value **only** for a field the read document leaves unset. So:
  - read field unset (null, or blank for title and location), detail value non-null, draft empty: a hint
    below the field reads "From the folder name: <detail value>"
  - read field set, draft emptied by the operator: the hint reads "Left empty: inherits from the folder name
    when saved", with no value. The detail's value here is the authored one, so naming it as the folder
    name's would be false.
  - Hints are linked with `aria-describedby`. Description has no folder source, so it has no hint. There are
    no value hints without a detail (the needs-attention form).
- **One client-side rule, the date input's own:** when the date input reports `validity.badInput` (a date
  typed only in part), its `value` is `''`. That must not be read as "inherit". The field shows "Enter a
  complete date, or clear the field", and Save is disabled until then.
- **No other client-side rules.** A 400 with `failure: unusable_metadata` renders its `detail` once, in a
  message at the top of the "Date and title" group. Both inputs get `aria-invalid="true"` and
  `aria-describedby` pointing at it, and focus moves to the message. Any other 400 goes to the editor's
  alert.
- The fields are not inside a submitting `<form>`, so Enter in a field never saves. Save is the save bar's
  button.
- The form is a section with the heading "Details" (`h2`), as the keyboard requirement asks of every section.
  Its panel heading scrolls with it, unlike the chapter panels' sticky headings: a sticky heading would sit
  over the fields it heads.

**Rationale**:
- The file keeps holding only what the operator authored (Principle II).
- The service stays the single judge of usability. The `badInput` rule is not a usability judgement: it stops
  a half-typed date from silently clearing an authored one.
- Reading which field failed out of the prose would break the "distinction from the problem body" rule.
  The gap is recorded as a risk.

### Row list and keyboard access (`src/edit/ClipOrderList.tsx`)

**Context**: The spec requires three ways to move a clip, announcements, and focus retention. The page must
stay responsive at about 400 rows.

**Explored**: dnd-kit's legacy accessibility guide (`KeyboardSensor`, `sortableKeyboardCoordinates`, the
`accessibility.announcements` and `screenReaderInstructions` props, and `setActivatorNodeRef` for handles),
and the session's reorder-UX research.

**Decision**:

**Structure**
- There is one `DndContext` per chapter (`id="chapter-<index>"` for stable `aria-describedby` ids). A clip
  therefore cannot be dropped into another chapter by construction.
- It holds a `SortableContext` over the movable identities, with `verticalListSortingStrategy`,
  `closestCenter`, and the hand-written modifier (vertical axis, clamped to the chapter's `<ol>`; see "The
  drag-and-drop library"). A dragged row stops at its chapter's edge, so it never hovers over another
  chapter.
- Each chapter is a panel with its `h2` (the same heading the read view uses: `Main` or the chapter's name,
  or "Clips" for an event with only the default chapter). Its movable clips are an `<ol>` whose direct
  children are memoised `<li>`s keyed by identity. The clamp relies on the `<li>` being a direct child.
- The ignored tail is a separate, dimmed `<ul aria-label="Ignored, not played">` after the `<ol>`, so it
  is neither numbered nor counted in "position N of M", nor inside the clamp. Its rows carry the "Ignored"
  pill and no controls.

**Sensors**
- `PointerSensor` with `activationConstraint: { distance: 6 }`, and `KeyboardSensor` with
  `sortableKeyboardCoordinates` and `scrollBehavior: 'auto'` under reduced motion (`'smooth'` otherwise).
  The listeners go on the handle only.
- The handle is a `<button className="btn btn-ghost btn-icon drag-handle">` with
  `<Icon name="grip-vertical" />` and `aria-label="Reorder <file>"`. `.drag-handle` has
  `touch-action: none`: a touch that starts on the handle drags, and one that starts elsewhere scrolls.
- Under `prefers-reduced-motion: reduce`, `useSortable({ transition: null })`, read from
  `matchMedia('(prefers-reduced-motion: reduce)')` and kept current. Every CSS transition in `edit.css` sits
  inside `@media (prefers-reduced-motion: no-preference)`, per `web-design-system`'s rule, and uses a
  `--dur-*` token. Any `animation` under `web/src/edit` MUST be declared inside that same media query, with a
  literal loop duration (for example `1.2s`), never a `--dur-*` token. The editor needs none of its own: the
  busy Save's spinner is `web-design-system`'s `.btn[aria-busy]` rule. Task 7.1 greps `web/src/edit` for
  both rules.

**A row shows** the same facts as the read view's table, plus the controls:
- its position among the movable clips
- the file name (the identity's last segment)
- its status as a `Pill` (`CLIP_STATUS_LABEL` words, `CLIP_STATUS_LOOK` tone and icon)
- its size and modification time, or "—" when absent (a MISSING clip). The time is the only ordering cue v1
  has, because there are no thumbnails.
- a badge when it is in the moved set: "was N", or "moved" for a moved clip at its original index
- **Move up** and **Move down** icon buttons (`arrow-up`, `arrow-down`, `aria-label="Move <file> up"`),
  unavailable at the ends: `aria-disabled`, not `disabled`, so they keep their place in the tab order

**Narrow windows**: below 54rem (a container query on the chapter panel, as `web-design-system` does for
tables), a row wraps onto two lines. (Implementation: planned as 40rem; an edit row has two more columns
than the read table, the handle and the move buttons, and the read table itself switches at 50rem, so
below 54rem the file column would collapse.) The first holds the handle, position, file name and move buttons, and
the second the status, badge, size and time. No fact is dropped. The handle and move buttons are at least
24×24 CSS px. `web-design-system` already pads the top for the sticky header.

**The save bar's height, one value for two consumers.** While the save bar is shown, `EventEditor` measures
its border-box height with a `ResizeObserver` (it wraps at narrow widths, so the height is not a constant)
and writes it, in px, as `--toast-inset-bottom` in the inline style of `<html>`. The effect's cleanup
removes the property when the bar hides or the editor unmounts; the StrictMode replay sets it again.
- The bar is a floating card: `.save-bar` is the transparent sticky wrapper (`bottom: 0`, 16px of bottom
  padding, clicks passing through), and its card floats that gap above the viewport's edge. The height
  published is the wrapper's, card and gap, so a toast sits a gap above the card.
- `web-design-system` already sets `html`'s `scroll-padding-bottom` to
  `calc(var(--toast-inset-bottom, 0px) + var(--toast-region-h, 0px) + var(--s-4))` (`shell.css`), so a
  focused or dragged row is never hidden under the bar or a toast: the padding is at least the bar's
  height. (Implementation: the planned `:root:has(.save-bar) { scroll-padding-bottom:
  var(--toast-inset-bottom, 0px); }` in `edit.css` was dropped; it would override that rule with a
  smaller padding.)
- `web-design-system`'s `ToastRegion` offsets its bottom by the same property, so a toast (a
  `render-progress-screen` toast can arrive while editing) sits above the bar and never covers Reset or
  Save at 390px.

The inline style on `<html>` wins over any layered default, and the region inherits it. Task 1.1 confirms
that `web-design-system` reads the property with a fallback (`var(--toast-inset-bottom, 0px)`) or declares
its default on `:root`, not on the region element itself, which would block the inheritance.

**Announcements** (legacy `accessibility` prop):
- start: "Picked up <file>, position 2 of 12."
- over: "<file> is over position 5 of 12."
- end: "<file> moved to position 5 of 12." (or "…dropped at position 2 of 12, unchanged.")
- cancel: "Move cancelled. <file> is back at position 2 of 12."
- Instructions: "Press Space or Enter to pick up a clip, the Up and Down arrows to move it, Space or Enter
  to drop it, Escape to cancel."

**The button path**
- A button move, like a drop, dispatches `move(chapter, from, to)`, which also records the clip as
  `lastMoved` for the badge tie-break.
- It announces "<file> moved to position N of M." through the editor's single visually hidden
  `role="status"` region, which sits outside the lists.
- A layout effect then re-focuses the same button of the moved row; at an end that button is
  `aria-disabled`, so it still takes focus. It also scrolls that button into view (`block: 'nearest'`,
  which honours the page's scroll padding) after every move, since focus alone does not scroll a button
  that already had it: repeated Move downs never slide it under the save bar. dnd-kit restores focus to the
  handle after a keyboard drop.

**Scale**
- No virtualisation.
- Rows are `memo`, with stable callbacks. Order state is a `Map<chapterName, string[]>` in a reducer.
- Responsiveness at 400 rows is measured, not assumed (task 5.1).

**Rationale**:
- A drag path and a non-drag path mean touch, pointer and keyboard users can all reorder.
- A live region of its own for the button path avoids double announcements with dnd-kit's own region.
  dnd-kit's region carries only the drag path.
- Alt+Arrow shortcuts are left out (YAGNI). The visible buttons already give a keyboard path without a
  hidden convention.

### Edit mode, saving and the save bar (`src/edit/EventEditor.tsx`)

**Context**: The spec requires an explicit save, complete-state fidelity, failures by cause, and a locked
editor while saving.

**Explored**: The session's React-patterns research (reducer over the draft, 412 UX, explicit save rather than
autosave). React 19 form actions were considered and rejected: they reset uncontrolled fields, and
`useOptimistic` would show a save that can still 412.

**Decision**: `EventEditor({ eventId, event, onSaved, onReload })`. `event` is `null` in the needs-attention
form, which then renders only the metadata form and the save bar. `event` is read once, at mount (a
`useState` initializer; see "The detail and the document must agree"). The draft is **not** reset when the
`event` prop changes identity: the reducer is never re-initialised from props, and the reel read's effect
depends on `eventId` only, so a new detail object from a re-read (once `render-progress-screen` lands, see
"Where it mounts") neither clears the draft nor re-reads the document. `onSaved` and `onReload` both mean
"leave Edit mode, then re-read".
The flow:

1. **Read.** On mount, `fetchReel` with an `AbortController` that the unmount aborts (so the StrictMode
   replay leaves one live read). While loading: `SkeletonRows` with the status "Reading reel.yaml…". A
   failure shows an `Alert` in the page's own words for a failed event read, as the spec asks: 404 is "No
   event “<folder>” under the project root." with a list link, 502 shows the cause, the `FAILURE_LABEL`
   words and `detail`, and unreachable shows `UNREACHABLE_CAUSE`. Each has "Try again". (Implementation:
   planned as "no longer exists", which the 404 on a save uses.)
2. **Check.** Run `detailMatchesDocument` when `event` is non-null (see above).
3. **Edit.** A `useReducer` holds `{ read, etag, original, orders, lastMoved, metadata, phase, problem }`.
   - A hint above the lists: "Drag a clip by its handle, or use its arrows. Clips stay in their chapter.
     Ignored clips are not played and cannot be moved."
   - When `adoptedNewCount > 0`, the hint adds "Saving this order adds N new clip(s) to reel.yaml."
4. **Save bar** (`src/edit/SaveBar.tsx`, with the failure alert). It is `.save-bar`,
   `position: sticky; bottom: 0`, a `role="region"` with
   `aria-label="Unsaved changes"`, shown while there are edits, and for a vanished event (its alert stays,
   Save unavailable). An edit that brings the draft back to what was read also retires a save's failure:
   nothing is left to save, so the bar goes and Save, Retry and Overwrite never send a no-op. Its height feeds
   `--toast-inset-bottom` and `scroll-padding-bottom` (see "Row list and keyboard access"). It contains:
   - the summary: the changed field names, "N clips moved", and "adds N new clip(s) to reel.yaml"
   - **Reset** (`btn-secondary`, `rotate-ccw`): back to the read state, with no question asked
   - **Save** (`btn-primary`, `check`)
5. **Save.** Set `phase: 'saving'`, then call `saveReel(eventId, buildWriteBody(…), etag)`. Retry and
   Overwrite run in the same phase. While saving:
   - **The pressed control** (Save, Retry, or **Overwrite with mine**, see step 6) gets
     `aria-disabled="true"` and `aria-busy="true"`, and its click handler returns early (a ref guard, so a
     second press or Enter never sends a second PUT). It MUST NOT get the `disabled` attribute: that would
     drop keyboard focus to `<body>` and take it out of the tab order (`web-design-system`'s busy-control
     rule). For the same reason the alert holding a pressed Retry or Overwrite stays rendered until the
     answer arrives: `problem` is replaced by the outcome, never cleared when the request starts.
   - **The rest of the locked editor** (the handles, move buttons, fields, Reset, and the unpressed
     buttons) is `aria-disabled` too, with the fields `readOnly`: no control in the editor ever gets the
     `disabled` attribute, so each keeps its place in the tab order and focus never drops to `<body>`.
   - **Save when nothing can be saved** (an incomplete date, a conflict, a vanished event) is
     `aria-disabled`, not `disabled`, and its `aria-describedby` points at the failure's alert (or, for
     the date, at the bar's summary).
   - After a failed answer focus stays on the pressed control, which the alert now describes; a 400
     `unusable_metadata` moves it to the message at the date and title group.
   - The alert is keyed by the failure's kind, so another kind of failure is a new alert: its buttons are
     never the old ones reused. When the pressed control went with the old alert (Retry answered by a 412,
     a 404 or a 400; Overwrite with mine answered by an unreachable service), focus moves on purpose to the
     new alert (`tabIndex=-1`), which a screen reader then reads, never to `<body>` and never onto
     **Reload latest (discard my changes)**, where a second Enter would throw the edits away. (Review
     decision: unkeyed, React reused the old buttons across kinds.)
   - Task 5.1 checks it: with `page.route` holding the PUT, Enter on Save leaves `document.activeElement` on
     Save until the answer.

   The outcomes:

| Answer | Shown | Draft |
|---|---|---|
| 200 | `toast.success('Saved')`, `markEventsChanged()`, `onSaved()` (the page leaves Edit mode and re-reads) | cleared |
| 400 `unusable_metadata` | message at the date and title group | kept |
| 400 other | alert: "The change was refused." plus `detail` | kept |
| 404 | alert: "This event no longer exists.", link to the list, Save unavailable | kept |
| 412 | conflict alert (below) | kept |
| 502 | alert: "reel.yaml could not be saved." plus the `FAILURE_LABEL` pill when `failure` is present, plus `detail`, plus **Retry** | kept |
| rejected, 422, other | alert: `UNREACHABLE_CAUSE` or "The service gave an unexpected answer" plus the message, plus **Retry** | kept |

   **Retry** builds the body again from the current draft and sends it with the same `If-Match`, the
   same as Save would; the draft only changes by the operator's own edits after the failure. Retry and
   **Overwrite with mine** are unavailable, as Save is, while the date is typed only in part or nothing is
   left to save, and the save itself refuses both, so a half-typed date is never sent as unset. (Review
   decision: this replaces "re-sends the same body"; only Save had checked the date.) The 200 handling
   (toast and `markEventsChanged()`) runs even if the editor unmounted meanwhile, so the list learns of the
   save, and the page reads the event again if it is still shown.
6. **Conflict (412).** An alert with the `warn` tone: "This event was changed elsewhere since you started
   editing." It offers two actions:
   - **Reload latest (discard my changes)** (`btn-primary`) calls `onReload()`, so the page leaves Edit
     mode and re-reads. It is a named discard and asks nothing.
   - **Overwrite with mine** (`btn-danger`) opens a `Dialog`, "Overwrite the other change?". The dialog
     says: "Your version replaces everything saved since you started editing, including changes to
     chapters you did not touch." Its actions are Cancel and Overwrite. The editor passes
     `initialFocus={cancelRef}` (the safe action) to `Dialog`; no React `autoFocus`, which would call
     `focus()` while the `<dialog>` is still closed.
     - Confirming closes the dialog, so focus returns to its opener, **Overwrite with mine**. That button
       is then the pressed control of step 5 (`aria-disabled` + `aria-busy`, never `disabled`) while the
       editor re-reads the document for its `ETag` only and then saves the same body built from the
       original read, with the new tag.
     - A failure of that re-read shows its own alert. Another 412 shows the conflict again.

**Rationale**:
- One whole-document PUT per explicit save gives one conflict window and one clear outcome.
- Locking during the save removes the "draft changed while in flight" case entirely, instead of reconciling
  it.
- The overwrite writes the operator's own version rather than rebasing it. Rebasing onto a document whose
  chapter lists changed could produce an order the operator never saw.

### Unsaved-changes guard (`src/edit/unsaved.ts` and a hook in `route.ts`)

**Context**: `hashchange` fires after the address changed and cannot be cancelled. `useRoute` would unmount
the page, and the draft with it, before any dialog could ask. App's layout effect scrolls on any new route
object (`App.tsx:42-49`).

**Explored**: The Navigation API's `navigate` event is cancellable, but support is not universal.
Intercepting links alone misses Back, Forward and typed addresses (session React-patterns research).

**Decision**:

**In `route.ts`** (about 50 lines):
- `setNavigationGuard(guard: ((proceed: () => void) => boolean) | null)`, plus module-level
  `acceptedHash` and `acceptedIndex`.
- Every accepted history entry carries its place in the session history, an index kept in
  `history.state` (stamped with `replaceState`, which changes no address): the entry shown when the
  module loads keeps its index or gets 0, and a new entry gets the accepted index plus one.
- In `useRoute`'s listener: if the hash differs from `acceptedHash` and a guard returns `false`, the move
  is undone. Back or Forward lands on an entry with an index, `delta` entries away, and is undone with
  `history.go(-delta)`; a link or typed address pushes a new entry without one and is undone with one step
  back. The undo's own `hashchange` lands on `acceptedHash` again and changes nothing. The guard receives
  `proceed`, which redoes the move: `history.go(delta)`, or assigning the target hash again. Otherwise
  `acceptedHash` and `acceptedIndex` are updated.
- This replaces restoring the address with `history.replaceState`, which overwrote the history entry Back
  had landed on, so a second Back left the app.
- `setRoute` bails out (returns `prev`) when the parsed route equals the current one. An undone move
  therefore neither remounts, scrolls nor moves focus.
- `acceptedHash` starts as `location.hash` when the module loads.

**In `unsaved.ts`** (the module store):
- `useUnsavedGuard(dirty)` is used once, by the mounted editor. While `dirty`, it registers `beforeunload`
  (`preventDefault()` plus `returnValue = ''`), and a navigation guard that stores the route's `proceed`
  and asks.
  Its cleanup clears the guard slot only if the slot still holds its own guard, so the StrictMode replay
  (register, clean up, register) leaves exactly one guard.
- `requestLeave(proceed)` runs `proceed` at once when nothing is dirty. Otherwise it asks first.
  `EventDetail` calls it for Refresh and for leaving Edit mode.
- **While a save is in flight nothing leaves, and nothing asks.** The editor publishes `saving`
  (`setSaving`, `useSaving`). The page makes Refresh and Stop editing unavailable (`aria-disabled`), and
  the navigation guard undoes a Back, Forward, link or typed address without a question, while a polite
  toast says the save is still running. (Review decision: a Discard during the PUT unmounted the editor
  and re-read the event before the save landed, and the later "Saved" left the page stale.) As a second
  line, a save that succeeds after the editor unmounted still has the page, if it is shown, read the event
  again.
- The question is one `Dialog`, "Discard unsaved changes?", rendered by the editor and keyed by the
  question's number, so a question asked again before React renders (Escape, then Back at once) still
  opens the dialog afresh.
  - **Keep editing** is focused first: the editor passes `initialFocus={keepEditingRef}` to `Dialog` (no
    React `autoFocus`). Escape or closing the dialog means the same as Keep editing.
  - **Discard** (`btn-danger`) clears dirty, drops the guard, then proceeds. For a navigation, proceeding
    redoes the move the route undid.

**Rationale**:
- One place asks for every way of leaving.
- The undone move keeps the page, the draft and the history intact: after Keep editing, Back asks again;
  after Discard, the list is where Back had led.

### Where it mounts, and "Needs attention"

**Context**: The plan assigns the Edit toggle, the editor mount point and the error-row link to this change.
`render-progress-screen` edits the same page's header region in parallel, and adds re-reads the page starts
by itself (`load({ quiet: true })` after a render finishes, and after a "fresh" or 404 enqueue answer). A
failed re-read replaces the ready view, so one that ran while editing would unmount the editor and lose a
dirty draft; and its Render control, left usable next to an open editor, would render the saved
`reel.yaml`, not the draft. The two changes archive in an order not known in advance, so the seam is fixed
here and mirrored in `render-progress-screen` (supervisor rule 7).

**Explored**: A separate route (`#/event/…/edit`) was rejected: it would need `App.tsx` and `parseRoute`
changes and a second mount of the page, and the plan asks for an in-page toggle.

**Decision**:
- **`EventDetail.tsx`** gets an `editing` state:
  - one header toggle button, next to Refresh: **Edit** (`btn-secondary`, `pencil`) when not editing, and
    **Stop editing** (`btn-ghost`, `x`, via `requestLeave`) while editing. It is the same `<button>` element
    in the same place, so React keeps the DOM node and focus stays on it when Edit mode starts. It is shown
    while the page is `ready`.
  - `ready` renders `<EventEditor …/>` instead of the facts, description and chapter tables while editing.
    The verdict and the latest job in the header stay.
  - **The `load()` contract (the seam, part a).** `load()` never touches `editing`. **Every** Edit-mode
    exit sets `editing` to false and then calls `load()`: Stop editing and Refresh (both through
    `requestLeave`), `onSaved`, and `onReload` (Reload latest, Read again). This change never calls `load()`
    while `editing` is true. One helper, `leaveEditMode()`, does the two steps and the focus move below, so
    no exit can skip one.
  - **The rest of the seam** is wired by whichever of the two changes is archived second (task 6.1 here,
    mirrored in `render-progress-screen`; both are evaluated only at the pre-archive rebase):
    - (b) while `editing` is true, EventDetail defers every re-read it would start by itself
      (`render-progress-screen`'s render-finished re-read, and its "fresh" / 404 enqueue answers). A ref
      records that one is pending, and the `load()` of the next Edit-mode exit satisfies it (and clears
      the ref), so no timer and no second read are needed.
    - (c) `render-progress-screen`'s `RenderControl` takes `blockedReason?: string`. While `editing`,
      EventDetail passes "Save or leave Edit mode to render": Render and Render anyway are hidden, and the
      progress and Cancel stay.
    - (d) one combined browser check (task 6.1).
  - Whenever Edit mode ends, focus moves to the page's `h1` (EventDetail's own element; `web-design-system`
    makes it focusable with `tabIndex={-1}`). The `h1` stays rendered while the page reads, so focus is
    never dropped to `<body>`.
  - A `failed` state whose `failure === 'unusable_metadata'` renders the failure, then
    `<section aria-labelledby=…><h2>Fix the date or title</h2><EventEditor event={null} …/></section>`.
- **`EventList.tsx`**: the attention row's folder name becomes `<a href={eventHref(error.event_id)}>`.
  This applies to every failure kind, because the page is the event's address either way. `eventHref` is
  already imported there.

**Rationale**:
- The page's own `load` is the one re-read path after every Edit-mode exit: a save, a conflict reload, a
  "Read again", Refresh and Stop editing. One exit path means a deferred re-read needs no path of its own.
- Keeping `editing` out of `load()`, deferring self-started re-reads, and keeping the draft across a new
  `event` object mean nothing but the operator's own action ends Edit mode or changes its draft, whichever
  change lands first.
- Stop editing re-reads even when nothing changed. It costs one GET, and a re-read deferred during editing
  is never lost.
- A form offered only for `unusable_metadata` matches what the write can fix. An unparseable file's
  detail tells the operator to repair it by hand.

### File ownership (parallel with `render-progress-screen`)

**Context**: `render-progress-screen` is built at the same time in another worktree, also on
`web-design-system`. Its design claims `src/jobs/**`, `src/api/jobs.ts`, the render region in the page
header and the job cell in list rows, and leaves `route.ts`, `src/edit/**`, `src/api/reel.ts` and
`package.json` alone.

**Decision**:
- **Owned by this change:** `web/src/edit/**`, `web/src/api/reel.ts`, `web/package.json` and
  `web/package-lock.json`.
- **Shared, and kept small and local:**
  - `EventDetail.tsx`: the Edit button next to Refresh, the `editing` branch in the ready view, the
    unusable-metadata branch in the failed view, `leaveEditMode()`, and Refresh through `requestLeave`.
    If `render-progress-screen` is already on main at the rebase, also the seam's (b) and (c) (task 6.1):
    a pending-re-read ref and one `blockedReason` prop.
  - `EventList.tsx`: one cell
  - `route.ts`: the guard. `render-progress-screen` does not touch it.
  - `web/README.md`: the screens paragraph, two tree entries, and the budget line
  - `docs/high-level-design.md`: in §4.10, the slice-table row D only (the sentence "no further api/
    prerequisite is known for v1" is `render-progress-screen`'s to update), and one D-8 bullet.
    `render-progress-screen` edits the adjacent row E, so git may report a conflict on the rebase. It is
    resolved by keeping both edits.
- **Not touched:** `App.tsx`, `labels.ts`, `common.tsx`, `styles/*`, `ui/*`, `jobs/*` and `api/jobs.ts`.
- **CSS:** `edit/edit.css` holds its rules in `@layer screens` and uses only the tokens and component
  classes from `web-design-system`.
- **Specs:** only ADDED requirements, so the archive order against `render-progress-screen` does not matter.

### Verification fixtures

**Context**: Every spec scenario must be checkable in the browser, without growing the dev library script
(proposal, "Non-goals").

**Explored**: Adding the three extra states to `scripts/make_dev_library.py`. Rejected for this change: the
script is shared by every screen and by `render-progress-screen`'s parallel verification, a 400-clip event
would slow every rebuild's `scan`, and an unparseable event would change the list counts that other changes'
checks cite.

**Decision**:
- **Existing events** (their `reel.yaml` as the script leaves it, checked against `make_dev_library.py`):
  - `2024-06-27 - Grillning med grannar`: one chapter `''` of four clips; title `Grillkväll med grannarna`
    and date set, no location
  - `2024-08-20 - Två kapitel - Tjörn`: chapters `''` (`s1710001.mp4`, then the IGNORED `s1710004.mp4`) and
    `Kvällen` (two clips, then the NEW `Kvällen/s1710004.mp4`)
  - `2024-08-02 - Badutflykt - Varberg`: `reel.yaml` lists two of three clips; `s1710004.mp4` is NEW
  - `2024-09-01 - Sommarlov`: the MISSING `borttagen.mp4` last, with an end-of-line comment
  - `2024-07-14 - kalas`: no `reel.yaml`, so inherited hints (`Kalas`, `2024-07-14`)
  - `2024/Blandat`: a document without chapters, date only from `reel.yaml`
  - `2024-06-21 - Midsommar - Dalarna`: title `Midsommar`, date and location set
  - `2024-02-30 - Omöjligt datum`: no `reel.yaml`, unusable metadata (folder title `Omöjligt Datum`)
- **Ad hoc, only in the implementing agent's own library copy, never committed:**
  - `2024/2024-09-15 - Stor dag`, with 400 symlinks `c0001.mp4`…`c0400.mp4` to one cut clip and no
    `reel.yaml`
  - `2024/2024-09-16 - Två mappar`, with two root clips and two in `Kväll/`, and no `reel.yaml`
  - `2024/2024-09-17 - Bruten fil`, with one clip and a `reel.yaml` that does not parse (for example
    `chapters: [`)

  With these, the list holds 12 readable events plus two under "Needs attention" (`Omöjligt datum` and
  `Bruten fil`) until `Omöjligt datum` is fixed.

  For task 6.1's combined check only, `2024/2024-12-01 - Lång` is added after task 5.1: 40 symlinks
  `a01.mp4`…`a40.mp4` cycling through `clips/s1710001.mp4`…`clips/s1710004.mp4`
  (`render-progress-screen`'s recipe), so a CPU render outlasts the check.

**Rationale**: The script's fixtures serve every screen. The scale and unparseable cases are verification
aids, not states the screens must show day to day.

## Failure behavior and idempotency

- **Reading never writes.** Entering Edit mode issues only GETs. A failed read shows its cause and offers
  no editing.
- **A save is exactly one conditional PUT per explicit action.** A refused PUT writes nothing: the service
  validates before its atomic replace (`editorial.py:63-75`, `writer.py:59-82`). The draft is kept for
  every failure.
- **Retry after a lost answer.** If a save reached the service but its answer was lost, Retry sends the
  same `If-Match`. Every edit this editor can make changes the ETag, because the ETag hashes every typed
  field except `sort` (`staleness/fingerprint.py:63-72`, `reel/document.py:191-204` `to_dict`), and the
  editor never touches `sort`. So the answer is a 412, "Reload latest" then shows the saved state, and
  nothing is written twice.
- **Overwrite** is re-read plus PUT. Repeating it after success gives an identical file.
- **No render interaction.** The write never enqueues and never touches the manifest. A save during a
  running render leaves that render using the document it claimed, and the event reads as stale again
  afterwards. A render that adopts NEW clips writes `reel.yaml` itself (`scheduler/worker.py:75` calls
  `cli/build.py:43-58` `prepare_and_persist`), so an edit left open across such a render gets a 412 on
  Save, which is the conflict path above. There is no worker or `--force` path in this change.
- **No `RENDER_GRAPH_VERSION` bump**, no API or schema change, no migration.

## Risks / Trade-offs

- **[The legacy dnd-kit line is frozen (last release 2024-12)]** → The surface used is small (core,
  sortable, CSS transform) and MIT. The lockfile pins it. D-8 records the condition for moving to
  `@dnd-kit/react` (1.0, or #2116 fixed).
- **[The 400 names no field]** → The message is shown once, for the date-and-title group, with both inputs
  marked invalid. A future API change could add a field pointer. The UI would then narrow the message
  without a spec change.
- **[A refused link or typed address leaves a Forward entry]** The browser pushes the new entry before the
  page can refuse it; undoing it steps back past it, so it stays as a Forward entry. Forward then asks
  again, and Discard or a later navigation replaces it. → Accepted; a refused Back or Forward changes
  nothing in the history. The Navigation API, which could cancel instead, is not yet available
  everywhere.
- **[Comments on clip entries depend on the engine gate]** At `541c44c`, `_apply_chapters` empties and
  refills every chapter's clip list (`editorial.py:188-191`), so a save would drop end-of-line comments on
  clip entries, even in untouched chapters and for a body sent back unmodified (Principle II, and the
  `api-service` "Saving an unmodified document is a no-op" scenario). → Fixed in the engine by the gate
  `editorial-chapter-roundtrip`, which task 1.1 requires on main. Task 5.1 checks it end to end: after the
  Sommarlov swap, `borttagen.mp4` keeps its `# MISSING` comment, and a location-only save on Grillning
  leaves the chapter lines byte-identical.
- **[A re-read or a Render by `render-progress-screen` while editing]** A failed self-started re-read would
  replace the ready view and unmount a dirty editor, and a Render next to an open editor renders the saved
  file, not the draft (a render that adopts NEW clips also rewrites `reel.yaml`, forcing a 412). → The seam
  in "Where it mounts": `load()` never touches `editing`, every exit re-reads, the draft survives a new
  `event` object, self-started re-reads are deferred while editing, and `RenderControl` is blocked with a
  reason. Whichever change archives second wires (b) and (c) and runs the combined check (task 6.1 here).
- **[Two live regions]** dnd-kit renders its own region for the drag path, and the editor has one for the
  button path. → Each move is announced once, by whichever path made it.
- **[Every row re-renders during a drag at 400 rows]** `useSortable` subscribes each row to the context. →
  Rows are memoised, and task 5.1 measures the keyboard step and the button move. When the budget is
  exceeded, the implementer stops and reports rather than adding virtualisation or a dependency.
- **[`draft.ts` has no committed unit test]** `tsc` is the frontend gate, and the `web-app` spec allows no
  runner in v1. → A scratch Node type-stripping check exercises it (task 2.2), and the browser pass captures
  real PUT bodies (task 5.1). Neither is committed.
- **[A detail/document race]** → `detailMatchesDocument` plus `If-Match` cover both sides of the document
  read.
- **[Overwrite discards the other change wholesale]** → A confirmation dialog states exactly that, and the
  safe choice (Reload) is the primary one.
- **[Parallel edits to `EventDetail.tsx`]** → The ownership split above, a rebase before archiving, and the
  conditional integration task 6.1.

## Migration Plan

- Run `npm ci` in `web/` (new dependencies), then rebuild `web/dist` with the `web/README.md` container
  command. `serve` mounts it as before.
- `reel.yaml` files written by the editor are ordinary editorial writes, the same writes the API makes for
  any client. Nothing needs migrating.
- Rollback: revert the web change and run `npm ci` again. Files already saved stay valid documents.
