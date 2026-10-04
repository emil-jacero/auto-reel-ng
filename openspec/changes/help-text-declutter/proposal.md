## Why

The user asked "Why is the interface so cluttered?". `edit-mode-declutter` (#136) moved the title card
controls into one dialog; about seven always-visible lines of explanation remain on the event page, and the
user answered "yes" to the offer of a second pass: hide them behind one Help button per section and keep only
what reports a state or needs an action. Reading a page of sentences before reaching a control is the clutter;
none of those sentences is wrong, so none is deleted, except two that repeat what a control already says.

## What Changes

- **Inventory first** (design.md): every always-visible sentence of instruction or explanation on the event
  page, in the read view and in Edit mode, classified as state/action (stays), explanation (moves into a
  section's help) or redundant (removed).
- **One Help toggle per section** (Details, Poster, Timeline, Clips, and the title card dialog's Title cards
  tab): `aria-expanded`, a 44 px target, a calm muted panel under the header, closed by default, remembered per
  section in `localStorage` (guarded, so a throwing browser still works). The text stays in the DOM.
- **Four specific calls:** the movie's length becomes one compact stat in the Timeline's control row; the
  "Not analyzed" sentence becomes a small badge and the command moves into the Timeline help; the "No cut
  selected" group is not drawn until a cut is selected; the Move button's reason (`Mark a clip to move it.`)
  is its tooltip and description and appears as a line only after Move is pressed while unavailable.
- No control, field, behavior or state message changes (the card dialog's fields included).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: ADDED "Each explanation sits behind a Help toggle of its section"; MODIFIED the requirements that
  state a visible sentence: chapters (own-chapter note), drags between chapters (the instructions), marks (the
  how-to line), moving the marked clips (the permanent reason), the marks line (its hint row and reason line),
  and the clock (the movie stat's words).
- `event-timeline`: MODIFIED the track's movie length (the compact stat), the analysis lane's "Not analyzed"
  (a badge) and the selected cut's group (not drawn without a selection).

## Impact

- Web only, `web/src/` in two places: new `web/src/ui/help/` (the persisted state, the toggle) and the
  sections that gain it: `edit/EventEditor.tsx`, `edit/PosterPanel.tsx`, `edit/card/EventTab.tsx`,
  `timeline/Timeline.tsx`, `timeline/CutFields.tsx`, `timeline/labels.ts`, `timeline/overlays/`, `edit/marks.ts`.
- No API, engine, DB, dependency or staleness change; no `RENDER_GRAPH_VERSION` bump.
- HLD §4.10 / §6 / D-20 note (task 9).
