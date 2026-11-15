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
grid-template: "top top top" auto
               "bin view insp" minmax(0, 1fr)
               "tl tl tl" minmax(280px, 38vh) / 240px minmax(0, 1fr) 340px;
```
The top row is at least 3rem and as tall as the bar is drawn: `Workspace` measures it (`--ws-top-measured` on
`<html>`) so notifications, sticky panel headings and the scroll padding clear it. Each pane scrolls on its own and is
marked `[data-ws-scroll]`; focus-in-view, drops and Page Up/Down measure against the closest such pane, falling back
to the page. Below 960 px wide: one column in the order top, view, tl, insp, bin, and the page scrolls; the top bar
takes two lines (the event; the save controls, Done and the theme switch, wrapping in page order) and sticks, unless
it would take more than two fifths of the window (or the window is under 28rem), when it rests at the page's top.

### D2. The Timeline is split into three parts over one state
`useTimeline(...)` holds what `Timeline` holds today (lay, zoom, video, playhead store, edge/trim state) and returns
its three parts as elements over that state: `viewer` (stage + transport, with Previous / Next clip added), `track`
(tool row + lanes) and `cutPanel` (CutFields + suggestion decision), each its own `.timeline` box. `Timeline` reads
`TimelinePanesContext` (`timeline/panes.ts`: the viewer and cut elements, `onCutSelected`): when the workspace
provides both panes it portals the viewer and the cut panel into them and renders the track in place, so it stays one
React tree; without them the three are stacked in `.tl-parts`. There is still exactly one `<video>` ("Edit mode holds
one video at a time").

### D3. The bin reuses the lists
The bin renders `ChapterDrag` / `ClipOrderList` with a compact row variant: handle, position and name; a 52×29
thumbnail with the length the clip plays and its status; the Cuts control and the row's tools (size and modified
time are left out). Every control stays (marks, rotate, Move up/down, Remove/Undo, Cuts, Move marked to…, Add
chapter, New/Ignored/Missing). The `KeyboardSensor` and announcements are kept, so reordering stays possible without
a pointer. Rows off screen are skipped as on the stacked page (`content-visibility`, with the compact rows' own
measured estimates); from a 22rem bin (stacked) a row takes two lines.

### D4. The save bar becomes the top bar
`SaveBar`'s states (one primary action: Save / Reload latest / Back to the event list) are kept; it renders in the top
bar in its `top` variant, and the stacked page's held/resting placement is off in the workspace. In the wide frame
the conflict and failure explanations open as a panel positioned under the bar (at most 40vh, scrolling within
itself): it may cover the upper panes (bin, viewer, inspector) but not the Timeline. Measured 2026-11-15 at 1280 wide
(conflict 79 px, failure 103 px tall, from 56 px): it ends above the Timeline at 720, 600 and 500 px tall; the 40vh cap
does not follow the Timeline's top, so in a window about 400 px tall (Timeline from 120 px) it overlaps the Timeline by
15–39 px, a known gap of short wide windows. Below 960 px the explanation is in the bar's flow under the save
controls, and while the bar sticks it gets what is left of the bar's two fifths of the window (at least 3rem). In both, it follows Reset and Save in the DOM, so tab order matches the drawn order.

### D5. Theme
The workspace uses the same tokens for light and dark; the switch in the top bar (`ThemeControl`, shared with the
app header) writes the same `data-theme` and `auto-reel:theme`, and `theme.ts` dispatches an event so every switch
shows the current choice. No new tokens (the mock's track title-bar colours were not kept).

### D6. The inspector has Event and Cut tabs, picked by hand
The inspector is a tablist (roving tabindex, arrow keys, Home and End, labelled panels). **Event** holds Details,
Poster, the render aside and a button "All title cards in this event" that opens the card dialog on that tab, with
whether title cards are on in words; the card style and the Title cards switch stay in the dialog
(`cardSelection.open` takes the tab to open on). **Cut** holds the Timeline's cut panel (mounted while hidden, for the
portal) and says how to select a cut when empty. Each press that selects a cut or a suggestion shows Cut without
moving focus from the track; a save refused at the Details fields while Cut shows switches to Event first, so the
editor holds the tab. Following the selection is `editor-selection`'s.

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
