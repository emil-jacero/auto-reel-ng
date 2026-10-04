## Why

`title-card-blocks` makes every chapter's title card visible and selectable in Edit mode, with an empty inspector
slot. The engine and the service can already store, resolve and draw a per-chapter card (`title-card-model`,
`title-card-fonts`, `title-card-over-video`, `title-card-write-api`), but the only thing an operator can edit is the
event's title through the "Main title card" line. The user asked to "edit the title of it again, and maybe a
subtitle", choose "text on black or text on a piece of video", and "edit the font". Until the inspector exists, none of
that is reachable from the GUI.

## What Changes

- Fill the inspector slot: selecting a title card in the Timeline or the chapter list opens that card's inspector in
  Edit mode, with its title, subtitle, Black / Video background, font (from `GET /api/v1/fonts`), title size,
  subtitle size, text colour and position.
- Every field is a per-card override with a **Use event style** control that clears it. An empty title follows the
  chapter's name (the event's title for the opening card) and says so as its placeholder; editing a card's title never
  renames the chapter.
- A live preview from `POST /api/v1/events/{event_id}/title-card/preview`: debounced about 250 ms, stale requests
  cancelled, the previous image kept while loading, failures in words. A Video card is composed over a frame of the
  clip the card sits over.
- Card edits are part of Edit mode's one draft: saved with the existing Save, undone with Undo and Reset, guarded
  against leaving, counted in the save bar ("2 title cards changed"), carried to the chapter's new name by a rename,
  and refused by the service at the field it names.
- The "Main title card" line stays as the event title's control; the opening card's heading is its own `card.title`
  in the inspector, which follows the event's title while empty and says so.
- HLD: a note under §4.10 and D-24; no new decision number.
- No API change, no engine change, no new runtime dependency, no `RENDER_GRAPH_VERSION` bump.

## Capabilities

### New Capabilities

### Modified Capabilities

- `web-app`: ADDED requirements for the title-card inspector, its live preview and how card edits join the draft, the
  save bar and the write. No existing requirement text is edited, because `title-card-blocks` (the gate) rewrites the
  title-card rows of this capability first; the reconciliation with its text is task 1.1.

## Impact

- `web/src/edit/` (draft slice for cards, build of the write body, save-bar count, unsaved guard), a new
  `web/src/edit/card/` folder (inspector, preview, font picker, pure model), `web/src/api/` (fonts and preview clients),
  styles. `web/openapi.json` and `schema.d.ts` already carry the routes (`title-card-write-api`).
- Reads `fonts`, the event detail's resolved `card` / `title_card`, the thumbnail route. Writes only through the
  existing `PUT …/reel`.
- Gate: `title-card-blocks` (selection model and the inspector slot). Package: `web`.
