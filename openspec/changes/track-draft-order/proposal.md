## Why

The user set the editor workspace as the next goal for the GUI on 2026-11-14 (`docs/editor-workspace.md`; mock
"auto-reel UI", board **Event page: Edit mode (editor workspace)**): "I click Edit and it resembles something like the
simple iMovie". In that workspace the clip bin and the Timeline sit side by side. Today the Timeline draws the
**saved** order while the lists below edit the **draft** order, and a note says so (`ORDER_SAVED`). Next to a bin that
reorders, a track that does not follow looks broken.

The saved-order rule was a scope cut, not a principle. `timeline-trim` (2026-10-03, D-20) says: "Order is the saved
order. A reorder made in the same Edit session is not drawn until Save (a note says so). Drawing the draft's order is a
larger change (the draft's maps onto proxy facts) and is left to a later one." This is that later change, and the
first slice of the editor workspace (HLD §6 item 10, GUI v3). It is done before the workspace shell because it
stands alone and already improves today's Edit mode.

## What Changes

- In Edit mode the Timeline draws the **draft's** chapters and clip order: a reorder, a cross-chapter move, a
  "Move marked to…", a chapter added, renamed or deleted is on the track at once, before Save. Reset puts the
  saved order back on the track.
- Clip facts (proxy, length, sprite, status) still come from the page's live read, looked up by clip identity; a
  clip the draft lists but the live read no longer has is not drawn (today's rule for vanished clips).
- Chapter bands carry the draft's names; a deleted chapter (still listed with Undo) draws nothing.
- Title cards follow the draft: a renamed chapter keeps its resolved card; a chapter **added in this session**
  gets a card **worked out in the browser** from an existing resolved card of the event (the opening card first)
  with the draft's card style applied and the chapter's name as its title (user decision, 2026-11-15, option 1).
- The note "The Timeline shows the order last saved…" goes away.
- Play, the playhead readouts, the movie length and the poster's "Use as poster" follow the drawn order.

## Non-goals

- Dragging clips **on the track** (that is `track-drag-edit`).
- The workspace layout, bin, inspector (`editor-workspace-layout`, `editor-selection`).
- Any change to how the service resolves cards; no new endpoint.
- A pixel-exact preview of an added chapter's card before Save: the block's **length, background and title** are
  right; its image is the service's preview only once saved or once the card dialog asks for one.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `event-timeline`: REMOVED + ADDED (the repo's pattern when a scenario is reversed) "The Timeline is shown only in Edit mode, open from the start" → "…and draws the draft" (draws the draft's order
  and chapters, no saved-order note); ADDED the rules for cards of renamed and added chapters on the track.
- `web-app`: MODIFIED "Edit mode adds, renames, reorders and deletes chapters" — an added chapter's card dialog says its
  card is drawn as the event's until Save when the Timeline draws a built card (only that sentence changes).

## Impact

- Web only (`web/`): `timeline/layout.ts` (a draft-order counterpart of `shownClips`), `timeline/cards.ts` (cards for
  renamed/added chapters), `timeline/Timeline.tsx` / `TimelineSection.tsx` (inputs from the draft), `edit/EventEditor.tsx`
  (pass the draft's chapters and orders), `timeline/labels.ts` (drop `ORDER_SAVED`).
- No API, engine, schema, `reel.yaml`, fingerprint or `RENDER_GRAPH_VERSION` change; no Alembic migration, no rescan.
  The CLI is not touched (nothing in `api/` changes, Principle V holds).
- No new dependency.
- HLD: amend D-20 (the Timeline draws the draft order) and the §6 item 10 note.
- Depends on nothing; `editor-workspace-layout` depends on this change.
