## Why

The user asked: "Some videos are rotated 90 degrees. I want a feature to rotate them so they are correct. We need to
remember this in the config as well." The engine half has landed (`clip-rotate-engine`, D-23, `RENDER_GRAPH_VERSION` 6):
`clips.<identity>.rotate` in `reel.yaml` is an extra clockwise turn on top of the clip's display rotation, the render
honours it on every profile, and the editorial PUT already accepts it. The GUI has no control for it and every preview
shows the clip unturned, so the operator cannot see what the render will do or fix a sideways clip.

## What Changes

- Edit mode gets **Rotate left** and **Rotate right** on every clip that a chapter plays and that is on disk (icons
  with accessible names, 44 px targets, keyboard), setting `clips.<identity>.rotate` in the **draft**; a turn back to
  0 removes the key. Undo, Reset and Save behave as for every other edit; the save bar says "1 clip rotated".
- The marked group (`clip-group-select-drag`) gets **Rotate marked left** and **Rotate marked right**.
- **Every picture of a clip shows the turn**, by a CSS transform on the picture the service already serves: thumbnails
  (read view and Edit mode), the clip player (read view Watch and Edit mode preview, copy and original), the Timeline's
  video and its filmstrip tiles. The transform is fitted so a 90 degree turn of a landscape picture stays inside its box.
  No proxy, sprite or thumbnail is regenerated: the display rotation is already in them, and `rotate` is not (D-21, D-11).
- The read view shows a **Rotated 90 degrees** tag (words and an icon) beside a turned clip.
- The play control on a turned thumbnail stays upright and centred (`clip-play-overlay-one-player`).
- HLD notes (D-23 follow-through, D-20, §4.10, §6).
- No API, schema, engine, fingerprint or `RENDER_GRAPH_VERSION` change; no new dependency (D-8).

## Capabilities

### New Capabilities
- `clip-rotation`: the rotate controls, the draft and save wording, the group turn, the read view's tag, and the rule
  that every clip picture shows the turn.

### Modified Capabilities
- `event-timeline`: the Timeline's video and filmstrip tiles show a clip's turn (an ADDED requirement; no existing
  requirement text changes).

## Impact

- Package `web` only: new `web/src/rotate/` (pure model, tests under `npm test`), edits in `web/src/edit/`
  (`draft.ts`, `ClipOrderList.tsx`, `SaveBar.tsx`), `web/src/events/` (`ClipThumb.tsx`, `EventDetail.tsx`),
  `web/src/cuts/ReadCuts.tsx`'s reel read, `web/src/preview/ClipPreview.tsx`, `web/src/timeline/`, `web/src/ui/Icon.tsx`.
- Evidence relied on: `research/v2/proxies.md` (proxy and filmstrip carry display rotation, not editorial; the rotated
  720p phone clip), `synthesis.md` §3 (D-21 proxy contract; no cache invalidation by editorial edits) and X6 (facts),
  `clip-rotate-engine` and D-23 (the meaning and the compose), `clip-thumbnails` ("the editorial `rotate` SHALL NOT be
  applied"), `clip-proxies` ("Editorial rotation is not baked in"), `clip-filmstrips` (tiles from the proxy).
