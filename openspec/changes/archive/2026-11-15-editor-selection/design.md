## Context

After `editor-workspace-layout`, the inspector has Event and Cut tabs chosen by hand. Selections are separate:
`Track`'s `selected` cut, `useSuggestions`' `selectedId`, and the card selection in `EventDetail` (kept above Edit mode
so a remount keeps it; spec "A card is selected from the Timeline or the list, as one selection").

## Decisions

### D1. One selection model, kept where the card selection is kept today

```ts
export type Selection =
  | { kind: 'none' }
  | { kind: 'clip'; identity: string }
  | { kind: 'cut'; identity: string; key: string }
  | { kind: 'card'; chapter: ChapterKey }
  | { kind: 'suggestion'; id: string }

export function keptSelection(sel: Selection, world: World): Selection  // 'none' when the target is gone
export function inspectorTab(sel: Selection): 'clip' | 'card' | 'suggestion' | 'event'  // cut → 'clip'
```

Held in `EventDetail` (as the card selection is now), so Refresh, Save and remounts keep it. `useSuggestions` and
`Track` read and write it through one setter; their own state is removed.

### D2. Clip press vs. handle press
The block's body selects the clip; edge zones, cut handles and card handles keep their presses (the existing
nearest-wins hit test decides first). A clip press does not move the playhead; a double press does (iMovie-like).

### D3. The card editor is docked
`CardInspectorPanel` renders inside the inspector's Title card tab; the `Dialog` wrapper, its focus-return and
scroll-lock code are removed. The tabs "This title card" / "All title cards in this event" stay. Preview above the
fields (the inspector is 340 px wide).

### D4. Bin ↔ track
Selecting in the bin scrolls the track to the clip if it is out of view (no zoom change); selecting on the track
scrolls the bin row into view. Neither moves keyboard focus to the other pane.

## Research & Decisions

### Docking instead of a dialog
**Context**: `card-editor-dialog` moved the card inspector into a modal so the track never moved.
**Explored**: mock board inspector "Title card" state; `edit/card/Inspector.tsx` already separates panel and dialog.
**Decision**: dock it; the workspace's fixed panes already guarantee the track does not move.
**Rationale**: a modal over a workspace hides the picture and the track the card is about.

## Risks / Trade-offs

- **Many specs mention the dialog** (focus return, Escape closes the dialog) → task 0.2 sweeps `web-app` and
  `event-timeline` for "dialog" in card requirements.
- **Keyboard**: clip blocks become focusable buttons; Tab order per clip is now clip, Trim In, cut handles, Trim Out.
  Windowing keeps the Tab count bounded.

## Failure behaviour
Display-only; edits go into the one draft as today.
