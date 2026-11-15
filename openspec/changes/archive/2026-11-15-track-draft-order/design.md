## Context

`Timeline` lays out `shownClips(event)` (`timeline/layout.ts:140`): it walks `event.chapters` of the page's live read,
skips ignored, missing and excluded clips, and returns `ShownClip { identity, name, chapter, ...proxy }`. The editor's
draft keeps the order separately (`edit/draft.ts`): `DraftChapter { key, readName, name, deleted }` and
`Orders = Map<ChapterKey, identities[]>` (movable clips only). Cards come from the detail's resolved
`chapters[].card`, keyed by the chapter's **saved** name (`CardSpec.chapter`), and from the draft's card edits.

## Goals / Non-Goals

**Goals:** the track draws exactly the order and chapters the save would write; nothing else about the Timeline's
behaviour changes. **Non-goals:** see the proposal.

## Decisions

### D1. One pure function builds the drawn clips from the draft

```ts
// timeline/layout.ts
export function draftClips(
  live: Pick<EventDetail, 'chapters'>,          // facts, by identity
  chapters: readonly DraftChapter[],            // order of chapters, names, deleted flag
  orders: Orders,                               // movable identities per chapter key
): { clips: ShownClip[]; omitted: Omitted; names: string[] }
```

- Builds `factsByIdentity` from `live.chapters[].clips[]` once.
- Walks `chapters` in draft order, skipping `deleted`; for each identity in `orders.get(key)` looks up the facts and
  applies `shownClips`' rules (ignored skipped, missing/excluded counted in `omitted`). An identity with no facts is
  skipped and counted as missing.
- `chapter` on each `ShownClip` is the index among **drawn** chapters; `names` is the drawn chapters' names, fed to
  `chapterBands`.
- `shownClips(event)` stays for the read paths that have no draft; Edit mode always uses `draftClips`.

### D2. Cards: map by key, synthesise for added chapters

- A drawn chapter whose `readName !== null` uses the resolved card of `readName` (renames keep their card).
- A drawn chapter with `readName === null` (added this session) gets
  `synthCard(base, styleDraft, name)`: `base` is the opening chapter's resolved card, else the first resolved card;
  the draft's event card style (`edit/cardStyle.ts applyStyle`) is applied on top; `title = name`; no chapter
  override exists yet, so nothing else changes. With no resolved card at all the block is drawn as a placeholder of
  the event-style length, named "Title card for <chapter>, shown after save".
- Cards are drawn only when title cards are on (the draft's switch), as today.

### D3. The live read and the draft stay two moments

The draft is the snapshot Edit mode opened with; facts follow the live read (a proxy job ending, a clip vanishing).
`draftClips` joins them by identity, so a proxy that finishes mid-edit still appears in the right place.

## Research & Decisions

### Why the track showed the saved order
**Context**: needed to know whether the rule protected an invariant.
**Explored**: `openspec/changes/archive/2026-10-03-timeline-trim/design.md` (§"Order is the saved order", Context 3);
`timeline/layout.ts` `shownClips`; `edit/draft.ts` types.
**Decision**: draw the draft order.
**Rationale**: the rule was deferred work ("left to a later one"); trims are keyed by identity, not place, so they
are unaffected.

### Card of an added chapter
**Context**: the service resolves cards only for saved chapters.
**Explored**: options — synthesise in the browser / placeholder / omit until save (explore session 2026-11-15).
**Decision**: synthesise from an existing resolved card plus the draft style (user chose option 1).
**Rationale**: length and background drive the layout (a black card adds time); a placeholder or an omission would
move clips on Save.

## Risks / Trade-offs

- **Synthesised card differs from the render** (e.g. a project default the event card does not show) → only the
  image may differ; length and background come from the same resolved values. Mitigated by the save, after which the
  service's card replaces it.
- **Performance on 400-clip events**: `draftClips` is O(clips) and memoised on `(live, chapters, orders)`; the
  drag-smoothness gate of `edit-list-paint-cost` is re-measured.

## Failure behaviour

Nothing is written; the change is display-only. A draft identity without facts is skipped and counted, never
invented (Principle I applied to the browser). Re-runs and restarts do not apply.
