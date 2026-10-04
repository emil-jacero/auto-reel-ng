## 1. Editorial body and detail (api)

- [x] 1.1 Carry `poster` in the editorial body models (`GET`/`PUT …/reel`: absent keeps, `null` removes, `{clip, at}` sets, unknown key rejected) with the engine's own validation and 400s naming `poster.clip` / `poster.at` (an unplayed clip is accepted, as the engine does); tests: set, keep, remove, refusals, byte-identical echo, stale verdict with no job (`pytest -m "not requires_db"`)
- [x] 1.2 Report `poster` and `poster_note` on the event detail from the engine's poster resolution, probe-free, with `source` a closed enum; tests: chosen, default with `at: null`, fallback note, no playable clip, bad hand-edited value (the event failure), no subprocess, no DB read

## 2. Poster endpoint (api)

- [x] 2.1 Add `GET /api/v1/events/{event_id}/poster.jpg`: fresh sidecar, else the engine's draw from the original, cached beside the thumbnails, `ETag`, `private, no-cache`, 304 without extraction, shared cap and single-flight, 60 s failure memory, 404/502 problem bodies, no DB, no writes; tests with real ffmpeg on small fixtures for each source, a cold-cache 304, a past-the-end `at`, and the library left byte-identical
- [x] 2.2 Regenerate `web/openapi.json` and `web/src/api/schema.d.ts`; the drift test finds nothing changed after regeneration and the schema holds the poster response, the detail fields and the body's `poster`

## 3. Web: the model and the cover (web)

- [ ] 3.1 Add the poster draft to the edit model (as read, removed, chosen; changed words; write body; Undo and Reset) and the pure mapping from the Timeline's playhead to a clip and `at` in milliseconds, with "disabled because" reasons; `npm test` unit tests including a time inside a cut, a card block, a rotated clip and an unchanged draft writing nothing
- [ ] 3.2 Show the cover on the event list rows and the event page header (lazy, reserved 16:9 box, alt text, placeholder on 404 or error); a test for the URL, alt and placeholder words, then `tsc` and `npm run build`

## 4. Web: Edit mode (web)

- [ ] 4.1 Add Use as poster to the Timeline's Edit mode (frame snapshot from the one `<video>`, focus kept, one announcement, disabled states) and the poster area with Default / Chosen frame / not saved and Use default; `npm test` for the state words and the draft, `tsc` clean
- [ ] 4.2 Wire Save, the save bar's "poster changed", the fallback note and `poster_note`, and the post-save swap from snapshot to the served image; tests for the write body and for no write when unchanged

## 5. Verification and docs

- [ ] 5.1 Run Playwright from the scratchpad in Chrome and Firefox against a dev library (writes routed to stubs): list cover and placeholder, page header, Use as poster, Save, Use default, Reset, light and dark at 1280 and 390, looking at the screenshots; fix what they show
- [ ] 5.2 Update `docs/high-level-design.md`: §4.9 (the poster endpoint and the detail fields), §4.10 and §6 (event poster frames built, the v2 list closed), a D-20 note (Use as poster on the Timeline, snapshot in the browser) and a D-15 note (no `v`: `no-cache` with a validator); the docs tests find the sections by heading and pass
