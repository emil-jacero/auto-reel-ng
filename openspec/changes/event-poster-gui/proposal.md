## Why

`event-poster-engine` gives an event a poster: an optional `poster: {clip, at}` in `reel.yaml`, written as
`<movie stem>-poster.jpg` beside the movie and embedded as its cover at render. Nothing in the service or the
page can show it, read it or choose it. The event list is a wall of text rows, and the operator has no way to say
which frame stands for an event. This is the last open v2 item (HLD §6).

## What Changes

- **API.** The event detail reports the effective `poster` (`clip`, `at`, `source` of `event` or `default`);
  `GET /api/v1/events/{event_id}/poster.jpg` serves it, from the rendered sidecar while that is fresh, else drawn
  from the clip's proxy (or the original when no proxy is ready); the editorial body of `PUT …/reel` and
  `GET …/reel` carries `poster` (`null` removes it, absent keeps it). OpenAPI and `schema.d.ts` regenerated.
- **Event list and event page.** Each event shows its poster as a cover image (lazy, fixed aspect, alt text, a
  placeholder when it has none). The event page header shows it.
- **Edit mode.** The Timeline gets **Use as poster**, which sets the draft's poster to the playhead's clip and time;
  the poster area says **Default: first clip** or **Chosen frame** and offers **Use default**. Save, Undo and Reset
  treat the poster as any other draft edit and the save bar says "poster changed".
- No new endpoint writes the library, no new job kind, no new runtime dependency, no database read.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: the poster endpoint, the event detail's `poster`, the poster in the editorial body.
- `web-app`: the cover image on the list and the page, and the poster's editing in Edit mode.

## Impact

- `auto_reel_ng/api/` (a poster read module beside `thumbnails.py`, `schemas.py`, the events and reel routes,
  `openapi.py`), the engine's poster operations from `event-poster-engine` (reused, not changed).
- `web/src/` (events list and page, `edit/`, `timeline/`, `api/`), `web/src/api/schema.d.ts` and `web/openapi.json`.
- `docs/high-level-design.md` (§4.9, §4.10, §6, D-15/D-20 notes), `tests/` and the web tests.
- Depends on `event-poster-engine` (merged first). No migration, no change to `RENDER_GRAPH_VERSION`.
