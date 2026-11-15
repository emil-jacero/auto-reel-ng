## Context

`EventEditor.tsx` (≈3000 lines) owns the draft and renders every Edit-mode section in one column inside
`EventDetail`'s page (`--page-max: 72rem`, app header above). `Timeline.tsx` renders the picture (`tl-stage`), the
transport and zoom (`tl-controls`), the `Track`, `CutFields` and the notes as one tree; small parts that move every
frame already read a playhead store. Selections today: cut (in `Track`), suggestion (`useSuggestions`), card (kept in
`EventDetail`).

## Goals / Non-Goals

**Goals:** the same Edit mode, every behaviour kept, in a four-pane frame. **Non-goals:** new editing behaviour.

## Decisions

### D1. The frame replaces the page, not the route
Edit stays `#/event/<id>` with Edit mode on. When on, `EventDetail` renders `<Workspace>` instead of the page body and
the app header is hidden (`data-workspace` on `<html>` hides it via CSS); leaving restores both. The leave flow and
the unsaved guard are unchanged.

```
grid-template: "top top top" 48px
               "bin view insp" 1fr
               "tl tl tl" minmax(280px, 38vh) / 240px 1fr 340px;
```
Below 960 px wide: one column in the order top, view, tl, insp, bin, and the page scrolls.

### D2. The Timeline is split into three parts over one state
`useTimeline(...)` holds what `Timeline` holds today (lay, zoom, video, playhead store, edge/trim state) and returns
it; `<TimelineViewer>` (stage + transport), `<TimelineTrack>` (tool row + lanes) and `<TimelineCutPanel>` (CutFields +
suggestion decision) render from it in different panes. There is still exactly one `<video>` ("Edit mode holds one
video at a time").

### D3. The bin reuses the lists
The bin renders `ChapterDrag` / `ClipOrderList` with a compact row variant (thumbnail 52×30, name, kept length,
pills). The `KeyboardSensor` and announcements are kept, so reordering stays possible without a pointer.

### D4. The save bar becomes the top bar
`SaveBar`'s states (one primary action: Save / Reload latest / Back to the event list) are kept; it renders in the top
bar. The conflict and failure explanations open as a panel under the bar, never over the panes.

### D5. Theme
The workspace uses the same tokens for light and dark; the switch in the top bar writes the same `data-theme` and
`auto-reel:theme`. No new tokens except the track's title-bar colours if the mock's are kept.

## Research & Decisions

### Layout model
**Context**: iMovie-like editing with picture, track and lists on screen together.
**Explored**: mock board (canvas "auto-reel UI"); explore session 2026-11-15 (List view dropped: the bin is the
lists, `ChapterDrag` already has keyboard reorder).
**Decision**: one workspace, no List/Workspace switch.
**Rationale**: avoids maintaining two layouts; accessibility is kept by the bin's keyboard sensor.

## Risks / Trade-offs

- **Splitting `Timeline.tsx` breaks the paint-cost gate** → re-measure `edit-list-paint-cost`'s drag in Chrome 4x.
- **Specs written against the stacked page** (scroll, focus-in-view, save bar resting) → task 0.2 sweeps `web-app` for
  requirements that assume the stacked page and lists any extra REMOVED/MODIFIED before implementation.
- **400-clip events in a 240 px bin** → the bin windows its rows as the lists do today.

## Failure behaviour
Display-only; saves, conflicts (412) and failures behave as today, shown in the top bar.
