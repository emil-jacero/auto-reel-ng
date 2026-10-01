# Research note — Browser playback of the archive and of our renders

> Measured research (R0) behind the media routes (`media-endpoints`), the movie player
> (`movie-player-screen`, D-15) and the clip preview (`clip-preview-screen`, D-16). Date: 2026-10-01.
> Every number below was measured on the dev host (headless browsers in podman, software decode,
> no GPU), so frame and timing figures are indicative only.

## TL;DR

1. **Range is mandatory.** About 76 % of the archive's files keep the `moov` index at the **end**: a
   browser fetches the tail before it can show a frame, and every seek is a byte range.
2. **H.264 + AAC plays everywhere** (Chrome, Firefox, WebKit), up to the archive's largest clip (4K50,
   119 Mb/s). **Every render of ours plays too**: H.264 High, AAC, `faststart`.
3. **PCM audio is the one gap.** The Sony XAVC clips (52 % of the archive) carry `pcm_s16be`. Chrome and
   WebKit play it; **Firefox plays the picture silently**, with no error. v1 serves the bytes unchanged
   and the screens say so; a server-side audio path belongs to the §8.11 proxy research (v2).
4. **Failures can be silent.** HEVC and MPEG-4 part 2 raise no `error` in Chrome or Firefox when their
   audio decodes: `videoWidth === 0` after `loadedmetadata` is the only sign.
5. **Playwright's bundled Chromium cannot decode H.264.** Every playback check uses Google Chrome
   (channel `chrome`, image below) or Firefox.

## 1. Archive survey

`ffprobe` over every `.mp4`/`.mov` under the archive's `Videos/Sorted/` (5,670 files, read-only). Other
extensions there (874 `.mts`, 438 `.m2ts`, 34 `.modd`, 10 `.vob`) were not probed: no browser plays them,
and the `.mts` files all sit under `original/`, which discovery skips.

| facet | counts |
|---|---|
| container brand | 2,975 XAVC (Sony), 1,391 isom, 876 mp42, 397 MSNV (Panasonic), 30 qt |
| video | 5,605 H.264 (3,853 High, 1,751 Main, the rest Constrained Baseline); 25 HEVC; 14 MPEG-4 part 2; all `yuv420p`/`yuvj420p` |
| resolution / fps | 4,229 1080p25, 836 1080p50, 397 720p25, 83 4K25, 28 4K50, 38 SD, a few portrait |
| H.264 level | 4.0 (1,751), 4.1 (2,910), 4.2 (836), 5.1 (83, 4K25), 5.2 (28, 4K50) |
| audio | **2,975 `pcm_s16be` 48 kHz stereo (every Sony XAVC clip, 52 %)**, 2,621 AAC 48 kHz, 51 AAC 44.1 kHz, 8 AC-3 5.1, 3 MP3, 4 `pcm_s16le` mono |
| rotation | 5 clips with `-90` side data, all under `original/` |

Outside `original/`, which is what discovery lists: 5,612 MP4, of which 5,598 H.264 and 14 MPEG-4 part 2.
The 14 are legacy rendered movies (`YYYY - Title.mp4`, 1970–2016), not event clips. **HEVC exists only in
`original/*.MOV`** (phone originals).

**`moov` placement** (a random 150-file sample): at the end of the file in about **76 %** (every sampled
Sony clip, most isom/AAC, the MSNV clips); first only for mp42 (Panasonic `S####`) and a few isom.

## 2. The samples

Ten representative files copied, byte-identical and read-only at the source, into
`auto-reel-media/samples/` (1.3 GiB; never `input/`, whose event set is a fixture):

| file | covers |
|---|---|
| `sony-xavc-1080p25-pcm.mp4` | Sony XAVC H.264 High 4.1 1080p25, **PCM audio**, `moov` at the end (153 MB) |
| `sony-xavc-4k25-pcm.mp4` | Sony XAVC 4K25 H.264 level 5.1, PCM (182 MB) |
| `h264-4k50-aac-119mbps.mp4` | 4K50 H.264 Main 5.2 at 119 Mb/s, the archive's largest bitrate, AAC, `moov` at the end (449 MB) |
| `h264-1080p50-aac.mp4` | Panasonic 1080p50 H.264 High 4.2, AAC, `moov` first (142 MB) |
| `h264-1080p25-aac.mp4` | an ordinary 1080p25 H.264 + AAC clip (20 MB) |
| `h264-720p25-aac-msnv.mp4` | Panasonic MSNV 720p25 Main (9 MB) |
| `h264-portrait-1080x1920-aac.mp4` | native portrait pixels (30 MB) |
| `h264-720p-rotate90-aac.mp4` | 1280×720 coded with `-90` rotation side data, displays 720×1280 (8 MB) |
| `hevc-mov-rotate90-aac.mov` | HEVC Main in QuickTime, rotated (15 MB) |
| `legacy-render-mpeg4-mp3.mp4` | a legacy rendered movie: MPEG-4 part 2 ASP 720p + MP3, 12.6 min (351 MB) |

The archive holds no 50 fps PCM clip, and every 4K50 clip is AAC.

## 3. Browser matrix

A page on the server's own origin creates one `<video>` per sample, served by Starlette's `FileResponse`.
Per sample: `loadedmetadata`/`canplay`, `error`, `videoWidth`, a seek to 50 %, 5 s of unmuted playback,
`getVideoPlaybackQuality()`, and an audio probe. `audioTracks` is `null` in Chrome and Firefox by default,
and `webkitAudioDecodedByteCount` counts demuxed bytes, so Chrome and WebKit were tapped with WebAudio
(`createMediaElementSource` → `AnalyserNode`, non-zero samples = decoded sound). Firefox's `AudioContext`
stays suspended without a sound card, so Firefox reports `mozHasAudio` (the track is recognized).

Cells: what played, dropped frames in 5 s, time to `seeked` at 50 %.

| sample | Chrome 154 | Firefox 132 | WebKit 18.2 | bundled Chromium 131 |
|---|---|---|---|---|
| h264-1080p25-aac | video+audio, 0, 64 ms | video+audio, 0, 76 ms | video+audio, 0, 83 ms | error 4 |
| h264-1080p50-aac | video+audio, 1, 77 ms | video+audio, 2, 120 ms | video+audio, 0, 331 ms | error 4 |
| h264-4k50-aac-119mbps | video+audio, 0, 248 ms | video+audio, 0, 150 ms | video+audio, 2, 476 ms | error 4 |
| h264-720p25-aac-msnv | video+audio, 1, 16 ms | video+audio, 0, 12 ms | video+audio, 0, 14 ms | error 4 |
| h264-720p-rotate90-aac | video+audio, 1, 38 ms, 720×1280 | video+audio, 0, 25 ms, 720×1280 | video+audio, 0, 36 ms, 720×1280 | error 4 |
| h264-portrait-1080x1920 | video+audio, 1, 877 ms | video+audio, 0, 967 ms | video+audio, 0, 1,233 ms | error 4 |
| hevc-mov-rotate90-aac | **audio only, no error**, `videoWidth` 0 | **error 4** | video+audio | error 4 |
| legacy-render-mpeg4-mp3 | **audio only, no error**, `videoWidth` 0 | **audio only, no error** | video+audio | audio only |
| sony-xavc-1080p25-pcm | video+audio, 0, 113 ms | video, **`mozHasAudio` false**, 0, 94 ms | video+audio, 0, 310 ms | audio only |
| sony-xavc-4k25-pcm | video+audio, 0, 138 ms | video, **no audio**, 0, 126 ms | video+audio, 0, 328 ms | audio only |

What a player must know:

- **Rotation is honored** by all three: the rotate-90 clip reports `videoWidth` 720, `videoHeight` 1280.
- **`canPlayType` cannot predict PCM.** Chrome answers `""` for a PCM-in-MP4 codec string, yet plays it.
- **Silent failure modes.**
  - HEVC and MPEG-4 part 2 in Chrome and Firefox: no `error` event, audio plays over a black picture, and
    `videoWidth === 0` after `loadedmetadata`. Only `original/` HEVC and the 14 legacy movies hit this,
    but `auto-reel adopt-renders` can make a legacy MPEG-4 movie an event's movie.
  - PCM in Firefox: `mozHasAudio === false` after `loadedmetadata` means no playable audio. There is no
    cross-browser equivalent.
- **Bundled Chromium** answers `""` to `canPlayType('video/mp4; codecs="avc1.640029"')` and fails every
  H.264 file with `DEMUXER_ERROR_NO_SUPPORTED_STREAMS` (`MediaError` 4).
- Chrome's HEVC is hardware-gated (VA-API), so a desktop Chrome may differ. Not tested; it does not matter
  for clips (no HEVC outside `original/`) or for renders unless a `look` selects an HEVC target.

## 4. Our rendered movie

A scratch event of four samples (720p MSNV, 1080p25 AAC, Sony PCM 1080p, portrait; two chapters) rendered
with `auto-reel render` (VAAPI, 14.6 s). `ffprobe` of the 150.6 MB, 89.57 s output:

- video: **H.264 High, level 4.0**, 1920×1080, `yuv420p`, bt709 TV range, 30 fps, 13.3 Mb/s
- audio: **AAC LC** 48 kHz stereo (the normalize step transcodes PCM to AAC, `render/normalize.py`)
- **`faststart`**: atom order `ftyp, moov, free, mdat` (`render/concat.py` passes `-movflags +faststart`), so
  playback and seeking need no tail fetch
- real container **chapters** (`ffprobe -show_chapters`: one per chapter), but **neither Chrome nor Firefox
  exposes MP4 chapters to `<video>`** (0 `textTracks`)
- a harmless `bin_data` stream carried over from the Sony clip

It plays in Chrome, Firefox and WebKit, seeks to 50 % in 173–301 ms. Chrome's requests: `bytes=0-`, then
one open-ended range per seek, no tail fetch.

The render manifest records `output` (a bare file name), the fingerprint and its components, the engine
identity and `written_at` — **no duration, codec or chapter times**. A chapter jump list for the movie
needs either a probe of the movie (breaking the probe-free read model) or chapter times recorded at render
time; both are v2 items beside the proxy work.

## 5. Starlette's `FileResponse` and ranges

Starlette 1.3.1 (FastAPI 0.139.0, uvicorn 0.51.0, h11):

| request | answer |
|---|---|
| plain GET | 200, `Accept-Ranges: bytes`, `Content-Length`, `Last-Modified`, its own `ETag` (an md5 of mtime and size) |
| `bytes=0-99`, `bytes=<n>-`, `bytes=-500` | 206 with the exact `Content-Range` |
| `bytes=0-9,20-29` | 206 `multipart/byteranges` (browsers never send it) |
| a first byte at or past the end | 416, empty `text/plain`, `Content-Range: bytes */<size>` |
| `lines=0-1`, `bytes=abc`, `bytes=5-3` | 400 `text/plain` ("Only support bytes range" for the unit) |
| `bytes=5-4` | 206 with an empty body and `Content-Range: bytes 5-4/<size>` |
| `If-Range` current / stale | 206 / 200 with the whole file |
| `If-None-Match` current | **200 with the whole body**: `FileResponse` evaluates neither `If-None-Match` nor `If-Modified-Since` |
| HEAD on a `@router.get` route | 405 (404 when the built client is mounted behind it) |
| `Cache-Control` | none unless the route sets it |

`FileResponse` streams in 64 KiB chunks, sets `etag`, `last-modified` and `content-length` with
`setdefault` (a route's own `ETag` wins and `If-Range` is checked against it), and opens the file only
**after** `http.response.start`: an unreadable file breaks off a response whose 200 has already gone out.
Without `stat_result=` it stats in `__call__` and a vanished file is a 500. The media routes therefore stat
and open the file themselves before answering, pass their own `stat_result`, set their own `ETag` and
`Cache-Control`, and answer `If-None-Match` with a 304 before `FileResponse` sees `Range`.

Starlette 1.7.0 (resolved by a fresh `pip install -e .` on 2026-10-01, as `pyproject.toml` pins only
`fastapi>=0.139.0`) answers `bytes=5-4` with 400 instead of the empty 206, and answers a set of more than
100 ranges with the whole file (read from the 1.7.0 source, not run). The project adds no pin for this: the
spec allows 206, 400 or 416 for a range browsers never send, so the media tests accept either version's
answer to `bytes=5-4`, and the media, OpenAPI and thumbnail tests pass on both 1.3.1 and a freshly resolved
1.7.0 (FastAPI 0.142.2).

## 6. Auth for media elements

`<img src>` and `<video src>` send no custom header: plain GETs (a `<video>` sends many, each with
`Range`), same-origin cookies only. Every request, each range request included, passes the app's one
`@app.middleware("http")` auth hook (D-A8, a no-op in v1). Parity with the thumbnail route is therefore
automatic, and a future token must be a cookie or a query parameter, because neither element can send
`Authorization`. Each range is a separate request through the checker, so the check must be cheap.

## 7. What `preload` costs

Chrome, on the Sony 4K25 (`moov` at the end) and 4K50 samples:

- `preload="none"`: **zero requests**, `readyState` 0, `duration` NaN.
- `preload="metadata"`: **3–4 requests per file**: `bytes=0-`, the tail for a `moov`-at-end file, then
  open-ended ranges from the first data offset (the 449 MB file was re-requested from 9.5 MB three times).
- On a faststart movie (125 MB): Chrome sent three open-ended 206s plus three 304 revalidations, then idled;
  Firefox sent one `bytes=0-`.

A list must not create `<video>` elements: create one when a preview opens.

## 8. A file replaced in place (Chrome)

From `movie-player-screen`'s spike, against the media routes: the movie file was replaced with `os.replace`
2 s into playback, then the player seeked.

| step | Chrome 154 | Firefox 132 |
|---|---|---|
| the playing element seeks | `MediaError` 3 `PIPELINE_ERROR_DECODE` | keeps playing the bytes it buffered |
| a **new** `<video>` at the **same** URL | metadata of the new file, then `MediaError` 3 at a seek | — |
| a new `<video>` at a **new** URL (`?v=x1`) | plays the new file, no error | — |

The server behaved as specified: the old element's next range carried `If-Range` with the old tag and got
the whole new file as a 200, and the new element got only the new file's 206s. The stale state is inside
Chrome, per URL. So **a file rewritten in place needs a new address**: the clip preview sends the detail's
`mtime` as `v`, and the movie player reads the movie's `ETag` with a one-byte `Range: bytes=0-0` request
(`cache: 'no-store'`) and sends it as `v`. That probe measured p50 2.6 ms, p95 4.0 ms over 30 requests.

## 9. The media routes' spike

A prototype of the exact routes on the real `create_app`, over a dev library from
`scripts/make_dev_library.py` with an added event of symlinks to every sample:

- **curl:** whole file 200; `0-99`, open-ended and suffix ranges 206 with the exact `Content-Range`; past
  the end 416 `bytes */<size>` with an empty body; `lines=0-1` 400; `If-Range` with the route's `ETag` or
  `Last-Modified` 206, stale 200; `If-None-Match` exact, `W/`, a list, `*` and with `Range` → 304,
  non-matching 200; the punctuated chapter clip `Kväll, del 2/a+b & c #1.mp4` →
  `Content-Disposition: inline; filename*=utf-8''a%2Bb%20%26%20c%20%231.mp4`; the zero-byte clip 200 empty
  and `bytes=0-` 416 `bytes */0`; a `chmod 000` clip **without** the route's own open → 500.
- **Movies on the dev library:** Kalas, Midsommar and Badutflykt (`clip_set`) 200; Grillning
  (`output_renamed`) 200 with the movie under its **old** name; `2024-07-14 - kalas` (no render record) 404;
  Sommarlov, Trasig, Blandat 404; Omöjligt datum 502; `2024` and an event's `original/` 404.
- **Chrome** (same origin): the 1080p50 AAC clip, the Sony PCM clip (`moov` at the end) and the punctuated
  clip reached metadata, seeked to 50 % in 22–83 ms and advanced 1.96 s in 2 s; the renamed movie played;
  the 404 movie and the zero-byte clip gave `MediaError` 4. Every media request was a 206, and reloading
  the `no-cache` movie produced a **304**: Chrome revalidates with `If-None-Match`.
- **Memory:** the 449 MB clip downloaded whole in 0.62 s while the service's RSS stayed at 113 MB (sampled
  every 50 ms). A client abort mid-stream left no traceback, and the next request answered 206.
- **OpenAPI:** `content: { "video/*": string }` for 200 and 206 and typed header parameters, generated by
  the repo's `openapi-typescript`; `tsc --strict` passed.

The routes as built (`media-endpoints`, task 6.1, the same dev library plus a 400-clip event of hard links):
every curl answer above held; the 449 MB clip downloaded whole in 0.47 s with no measurable RSS growth
(115 MB before and at the peak); an aborted download left no traceback and the next range answered 206; a
range lookup took p50 8.1 ms / p95 14.5 ms in the 400-clip event and p50 1.7 ms / p95 2.4 ms in an 11-clip
event; Chrome reached metadata on the PCM, 4K50, portrait, rotate (720×1280), punctuated clips and two movies
with durations within 0.1 s of `ffprobe`, seeked to 50 % and advanced at least 1.7 s in 2 s; the absent movie
and the zero-byte clip gave `MediaError` 4; a second load of a movie sent `If-None-Match` and got 304s; with
the database unreachable, a clip and a movie still answered 200.

**A trap for verification scripts:** Playwright's `page.route` disables the browser's HTTP cache while any
route is registered, so a check that intercepts requests never sees Chrome's `If-None-Match` revalidation
(only 206s). A revalidation check registers no route; it guards against writes by observing requests
(`page.on("request")`) on a page that issues none of its own.

## 10. The Chrome-channel Playwright image

Every playback check (the media routes' verification, the movie player, the clip preview) runs in Google
Chrome or in Firefox, never in Playwright's bundled Chromium (§3). The image:

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble
RUN pip install -q playwright==1.49.0 && python -m playwright install chrome
```

Built as `podman build -t localhost/playback-research:chrome .` (about 4.9 GB) and run with
`--network host`; the script launches `chromium.launch(channel="chrome")`.

## Recommendations (adopted)

1. **PCM audio: nothing server-side in v1.** Serve clips unchanged as `video/mp4`; the clip preview says when
   `mozHasAudio === false`. An AAC remux is a subprocess per request with its own cache, concurrency and
   invalidation: the §8.11 proxy design, which opens GUI v2.
2. **Detect the silent video failure:** a player treats `videoWidth === 0` after `loadedmetadata`, and
   `MediaError` 3 or 4, as "this browser cannot show this file".
3. **Stream with `FileResponse`**, open the file before answering, and answer `If-None-Match` with a 304.
4. **No chapter jump list in v1**; chapter times in the manifest are a v2 item.
5. **Create `<video>` elements on demand only**, and give a rewritten file a new URL (`v`).
