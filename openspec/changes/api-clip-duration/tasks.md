## 1. api/

- [x] 1.1 Add `ClipOut.duration` (`Optional[float] = None`) in `api/schemas.py`, with the docstring updated
  (duration is the thumbnail sidecar's number, never probed), and read it in `events_read._clip_out` through
  `thumbs.recorded_duration(thumbs.thumbnail_path(...))` (the gate's reader of `<key>.json`, which takes the cached JPEG's path), with `cache_dir`/`position` resolved once per detail request and passed
  through `_build_chapters` (a MISSING clip is not looked up; an unusable sidecar, a failed key stat or a
  `ConfigError` gives `null`, the last with one warning). Verify in `tests/test_api_events.py`: a seeded
  sidecar gives `6.02` for the clip and `null` for the others; ffprobe/ffmpeg monkeypatched to raise are never
  called; the cache directory listing is identical before and after the read; a replaced file (new size or
  mtime) gives `null`; a sidecar with invalid JSON, `0`, a negative number and a string each give `null` with
  a 200; `thumbnails.position: 2` in `config.yaml` gives a 200 with every duration `null`; a MISSING clip and
  the no-document (seeding) case give `null`; the events list is unchanged.
- [x] 1.2 Regenerate `web/openapi.json` with `.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`
  on top of the merged gate code. Verify `tests/test_api_openapi.py`: the drift test passes, and a new
  assertion shows `ClipOut.properties.duration` is a nullable number and is not in `required`.

## 2. web/

- [x] 2.1 Regenerate `web/src/api/schema.d.ts` (`npm run generate:types` in the `node:22` container) and
  verify `npx tsc --noEmit` and `npm run build` pass with `duration?: number | null` on the clip type.
- [x] 2.2 Pass `clip.duration ?? null` from `edit/ClipOrderList.tsx` into `cuts/CutsPanel.tsx` and compute the
  panel's length as the preview's length, else the duration, else unknown (a pure `clipLength(previewed,
  duration)` helper next to `checkCut` in `cuts/times.ts`, so a scratch Node script can run it). Verify
  `tsc` and `build`, and that a scratch Node script over `times.ts` shows: preview 6.08 with duration 6.02
  gives 6.08; preview unknown with 6.02 gives 6.02; both unknown gives unknown; a `null` duration is never
  `0`; `checkCut` with the duration refuses `5`-`7` as `past-end` at the end field and accepts `5`-`6.02`.
- [x] 2.3 Verify in a real browser (Playwright from the scratch directory against a dev library, writes
  intercepted, never `auto-reel-media/`): once the event page has fetched the clips' thumbnails and the detail
  is reloaded, a clip's panel says "This clip ends at ..." before any preview opens and refuses `5`-`7` with
  the refusal at the end field; a clip with no thumbnail yet still shows the "does not know" text and accepts
  the cut; after opening the preview the stated length is the video's. Light and dark at 1280 and 390 px, with
  the screenshots looked at, scoped to `main:not([hidden])`.

## 3. docs/

- [x] 3.1 Amend `docs/high-level-design.md`: the §4.9 probe-free paragraph (one sentence on the sidecar-read
  duration), D-14's "cannot refuse a cut past the clip's end" sentence, and D-16's "The length" bullet; verify
  by `grep -n "carries no duration" docs/high-level-design.md` finding nothing.

## 4. Validation gates

- [x] 4.1 Run `black`/`isort` (line length 100), `mypy auto_reel_ng`, `pylint auto_reel_ng` (only the known
  cairo `no-member`), and the full `pytest` (`-m "not requires_db"` only when podman is unavailable, and say
  so); all pass. Confirm `RENDER_GRAPH_VERSION` is unchanged (rendered output does not change).
