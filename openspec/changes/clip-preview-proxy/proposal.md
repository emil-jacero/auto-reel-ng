## Why

GUI v1's clip preview (HLD **D-16**, change `clip-preview-screen`) plays the clip's own file, and 2947 of the
archive's 5574 clips (25.6 of its 52.1 hours) are Sony XAVC files whose audio is PCM in MP4 (`twos`). Firefox 155 and
157 play none of it: `mozHasAudio` is `false`, no error, a silent picture (research `pcm-audio.md` §1.2, measured
on Firefox 155.0 and the 157.0 flatpak; Firefox's own `mp4parse` maps PCM to "unknown codec", §1.3). The preview
says so in a note and does nothing more. The user edits in Firefox (supervisor and user decision, v2 brief), so the editor is mute for
half of the footage it edits.

v2 builds preview copies of every clip (**D-21**, change `proxy-encode`, research `synthesis.md` §3 "D-19 (proxies)"):
540p H.264 MP4 with **AAC always** (X4: a video-only copy would be silent in Chrome too), at the same media time
as the original (`-fps_mode passthrough`). The two gate changes make them reachable by the client:
`proxy-state-read` puts each clip's proxy state and facts into the event detail, and `proxy-media-endpoints`
serves the copy with Range and an entity tag. This change is the first user-visible Firefox fix: the preview
plays the copy when it is ready, so the Sony clip has sound in Firefox (PCM report §2 (a): decoded peaks 0.264 and
0.085 in Firefox 155, equal to Chrome's and to the raw PCM's), with an explicit **Play original** for the full
file. HLD §4.10 and `synthesis.md` §5 row 9 name this change; the HLD §6 phase is 9 (GUI v2).

## What Changes

- **The preview plays the preview copy when the event detail says it is ready**, else the original exactly as in
  v1 (state absent, stale or failed: no request for a copy, and the preview says in one line why the original
  plays). The copy's address carries its entity tag as `v`, read with the one-byte request the movie player
  already uses (D-15), because Chrome fails a replaced file at an address that served the old one.
- **Play original / Play preview copy**: one explicit control that swaps the file under the playhead. It keeps the
  time (media time is the same in both files), keeps playing or paused, and is announced. The choice follows the
  clip when it moves to another chapter and is forgotten when the preview closes.
- **The no-sound note belongs to the original.** It is never shown while the copy plays; shown for the original
  in Firefox it adds that the preview copy has sound, when one is ready.
- **Set From, Set To, Skip cuts and the cut bar are unchanged**: they act on the playhead of whichever file plays,
  to the millisecond, in the same format. **The clip's length while the copy plays is the duration in the copy's
  facts** (the original's, as the engine probed it), not what the browser reads from the copy: browsers read the
  copy about 20 ms short or long (research `synthesis.md` X6), and a short reading would refuse a cut that ends
  at the original's end.
- **A copy that cannot play is told by cause**, as the original's failures are, offering Play original beside Try
  again. The page never switches by itself and never compares the copy's `Last-Modified` with the clip's `mtime`.
- **Spec and docs**: two MODIFIED requirements and one ADDED requirement in `web-app`; `web/README.md`; HLD edits
  (task 6.1).

## Non-goals

- **Not the timeline.** `timeline-view`, `timeline-trim`, `timeline-overlays` and the filmstrip are other changes.
  This change requests no filmstrip.
- **No enqueue, no Prepare action.** `proxy-enqueue-endpoint` is a later change, so the preview never starts a
  build. An unprepared clip plays its original with the v1 note.
- **No live update of a clip's proxy state.** The state is the one the event detail was read with; a copy built
  while Edit mode is open is used after the event is read again (stop editing), as for every other detail fact.
- **No server work, no new endpoint, no new dependency** (Principle VII); `api/`, `proxies/` and the schema are the
  gates'. No virtual remux and no `<audio>` sidecar: the original stays silent in Firefox (user decision, brief).
- **No change to what Save writes**, to `reel.yaml`, to staleness or to the render. No `RENDER_GRAPH_VERSION` bump.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - MODIFIED `Requirement: Edit mode previews a clip on request`: what the preview plays points at the copy; the
    no-sound note applies to the original only; nothing loads before the preview is opened now covers the copy;
    the keyboard order gains the Play original control.
  - MODIFIED `Requirement: A clip's preview sets cut times at the playhead and plays the clip as the movie will`:
    only "The clip's length" and the first line of Set From / Set To change (the copy's length is its facts').
  - ADDED `Requirement: A clip's preview plays its preview copy when one is ready`: which file plays and why, the
    address, Play original, times, failures.

## Impact

- **Packages:** `web/` only (`api/headers.ts`, `api/clipMedia.ts`, `api/movie.ts` (a function moves out),
  `preview/` (`source.ts` new and pure, `previews.ts`, `ClipPreview.tsx`, `preview.css`), `cuts/CutsPanel.tsx`
  (passes the clip's proxy state), `README.md`), plus `docs/high-level-design.md`.
- **CLI vs API (Principle V):** untouched; this is a client of the gates' routes.
- **Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump; the staleness fingerprint inputs are unchanged
  (a preview copy is not an input: D-21).
- **Schemas:** `web/openapi.json` and `schema.d.ts` are the gates' to regenerate; this change only reads them.
- **Dependencies:** none new.
- **Gates (merged into origin/main before implementation):**
  - `proxy-state-read`: each event-detail clip gains `proxy` (state `absent | ready | stale | failed`, and facts when
    ready: duration, fps, vfr, dimensions, rotation, audio codec, filmstrip geometry), read by `stat` and JSON only.
  - `proxy-media-endpoints`: `GET /api/v1/events/{event_id}/proxy?clip=&v=` through `media_response` (Range,
    If-Range, ETag, HEAD, If-Modified-Since); an absent copy is a problem body (404), never a 200; the clip route's
    path guard and auth.
  - The design is written against these plan summaries before either has merged; task 1.1 re-checks every name on
    main and stops on a mismatch.
- **Evidence relied on** (session scratchpad `research/v2/`): `pcm-audio.md` §1.2 (Firefox 155/157 silent on PCM),
  §1.3 (why, from `mp4parse`), §2 (a) (AAC in the copy: +16.4 KB/s, sync Chrome +15 ms, Firefox 0); `synthesis.md`
  §2 X4 (AAC mandatory), X6 (copy duration differs from the source by about 21 ms), X9 (proxy time = source time,
  frame-exact on `-bf 0`), §3 D-19 table (renumbered D-21), §6 risk 14 (replaced file at an unchanged URL);
  D-16's own measurement (Chrome's length equals ffprobe's, Firefox up to 60 ms longer).
- **Size (Principle VIII):** one package, one capability delta (two MODIFIED blocks and one ADDED), 10 tasks.
