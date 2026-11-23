# Research note: the Timeline's pause between clips

> Measured research behind `seamless-playback` (HLD D-20, "a second preloaded `<video>` for seamless boundaries").
> Date: 2026-11-18. Read-only: the operator's running dev app was only read. Writes were refused inside the page,
> and the spike played copies of four proxies from a scratch directory. Every browser here was headless or ran
> under Xvfb, in podman or on the host, with software decode and no audio device. Timings of events are therefore
> indicative, and frame cadence is not representative (§4).

## TL;DR

1. **The pause is the serialized chain at the boundary, not the network.** After the last frame:
   - the end is noticed after 4–53 ms, often by `ended` rather than by the frame;
   - the `src` swap, request and `loadedmetadata` take 12–25 ms;
   - an always-run seek takes 13–24 ms;
   - `play()` to `playing` takes 4–10 ms.

   The proxy request inside the load, with Firefox's 304 revalidation, is 4–17 ms on loopback.
2. **Two alternating, preloaded `<video>` elements lose 19 to 29 ms less play time per boundary** than today's
   swap, in all three browsers tried. The absolute residual (25–127 ms) follows each harness's presentation cadence
   and possibly the audio sink's start. It cannot be judged headless, so a headed measurement gates the work (§5).
3. **`opacity: 0` hides a standby as well as stacking it under the shown element.** Both gave identical numbers in
   every browser.
4. **No `Cache-Control` change is needed.** A preloaded standby hides the request. The route does not pin bytes to
   `v`, so long caching would be unsafe (`browser-playback.md` §8).

## 1. Method

- **The app.** The dev app (Vite on 5173, the service behind it) served `2024-06-27 - Grillning med grannar`: one
  chapter of four clips, `s1710001.mp4` to `s1710004.mp4`. Each proxy is 6.02 s, 50 fps, 960x540, H.264 + AAC, so
  a run crosses three plain clip-to-clip boundaries.
- **The browsers.** The image was `mcr.microsoft.com/playwright/python:v1.63.0-noble`, with Chromium 153.0.8010.12
  and Firefox 155.0, run with `--network host`.

  This Chromium decoded the H.264 proxies (`videoWidth` 960, advancing `mediaTime`). That differs from the bundled
  Chromium of `browser-playback.md` §3 (Playwright 1.49).

  Google Chrome 157.0.8103.78 (the host's Flatpak) was run headless, with `--mute-audio` and the audio socket
  withheld, and driven over CDP.
- **No Playwright route.** A route turns off Chromium's HTTP cache and would change the revalidation being measured.
  An init script refused every non-GET `fetch` and XHR instead: one `POST …/title-card/preview` was refused.
- **The instrumentation.** The same init script hooked the Timeline's `video.tl-video`: the `src`, `currentTime` and
  `play()` calls, the media events, and a `requestVideoFrameCallback` loop that recorded each presented frame
  (`now`, `mediaTime`). Proxy requests and responses were taken from Playwright's events, on epoch time.
- **The scenario.** In Edit mode: Next clip twice, Left, Shift+Left twice (0:04 of `s1710001.mp4`), then Space on
  the playhead. Play ran for 22 s, through the three boundaries.

**Sound.** A host browser plays through the operator's speakers. Launch it with `--mute-audio` and without the
audio socket (`flatpak run --nosocket=pulseaudio --nofilesystem=xdg-run/pipewire-0 …`). The container has no
`/dev/snd`, so it cannot play sound. Muting at the browser keeps the element's audio path in play, so timings stay
realistic, which setting `muted` on the element would not.

## 2. Today's boundary in the running app

One sample from Chromium 153, `s1710001.mp4` into `s1710002.mp4`, in ms from `src =`:

| Event | t |
|---|---|
| last presented frame of `s1710001.mp4` (`mediaTime` 6.04) | −41.8 |
| `pause` (the clip ran out), then `src =` from `onEnded` | −0.3, 0 |
| `loadstart` | 6.6 |
| `currentTime = 0.005` (the seek to frame 0) and `loadedmetadata` | 14.8, 15.0 |
| first frame of `s1710002.mp4` on screen (still, `mediaTime` 0) | 24.8 |
| `play()`, `seeked`, `playing` | 31.3, 36.9, 37.3 |
| frames with `mediaTime` 0, 0.02, 0.06, 0.10, 0.12 | 41.5, 91.5, 141.5, 191.5, 208.2 |

So the last frame was held, or the picture was blank, for 67 ms. The incoming clip then started at about 20 fps with
skipped frames for some 200 ms before steady play.

Per boundary, min–max over 2 runs of 3 boundaries per browser. For Chromium the step rows cover 4 of the 6 boundaries
(one run's three and the sample above), and the last row covers all six:

| Step | Chromium 153 | Firefox 155 |
|---|---|---|
| last frame → `src =` (end noticed) | 30.6–52.6 | 4.4–35.9 |
| `src =` → `loadedmetadata` | 12.5–25.1 | 16–23 |
| proxy request → response (loopback) | 7–17 (206) | 4–8 (304 in 4 of 6, else 206) |
| seek (`currentTime =` → `seeked`, incl. listener order) | 17.7–24.4 | 13–21 |
| `play()` → `playing` | 5.7–9.6 | 4–8 |
| last frame of old → first frame of new | 49.9–83.3 | 30.1–73.2 |

The seek to frame 0 always runs. `load()` clears the coalescer's `shown`, and `seekSeconds(0, fps)` is a quarter
frame in. The proxy's revalidation is real (Firefox shows the 304), but it is the smallest step.

## 3. The spike: one element vs two

Four proxies of the same clips were copied to a scratch directory. A small server answered them as the route does:
byte ranges, a strong `ETag`, `private, no-cache`. A blank same-origin page played each clip from 1.5 s before its
end. With 9 boundaries per run and 3 runs per case, that is 27 boundaries per case. The modes:
- **One element (today):** at the last frame, set `src`, wait for `loadedmetadata`, seek, wait for `seeked`, play.
- **Two elements:** the next clip is preloaded, muted, into the other element and sought to its start.
  1. At the last frame: unmute and `play()` it, then `pause()` the outgoing one.
  2. On its first presented frame: swap which is shown, then preload the clip after it into the freed element.

  It was hidden either by stacking it under the shown element or by `opacity: 0`.

**Lost play time** is real time minus media time played across a boundary. It is read 500 ms after the end is
noticed, net of the outgoing clip's unplayed rest. Values are median / p90, in ms:

| Browser | One element | Two, stacked | Two, `opacity: 0` | Steady longest hold |
|---|---|---|---|---|
| Chromium 153 (headless) | 65.5 / 70.2 | 41.3 / 41.4 | 41.3 / 41.4 | 83 |
| Chromium 153 (Xvfb, headed) | 65.9 / 69.7 | 41.4 / 41.4 | 41.3 / 41.4 | 83 |
| Firefox 155 (headless) | 53.6 / 57.3 | 25.4 / 31.0 | 24.6 / 28.3 | 80 |
| Chrome 157 (host, headless) | 146.2 / 152.1 | 126.7 / 126.7 | 126.7 / 126.7 | 100 |

The "steady longest hold" is the longest a frame stayed on screen in the second before a boundary. In these
harnesses it is already 80 to 100 ms: the browsers present 10 to 40 frames a second of a 50 fps clip. So the
hold-based gate cannot be checked here: it measured no difference between modes (66–167 ms everywhere). The
lost-time measure does not depend on presentation, and it shows the two-element hand-over saving 19 to 29 ms in each
browser.

## 4. What these runs cannot tell

- **The residual.** The two-element residual (25, 41, 127 ms) is constant within each browser. It may be the end
  being noticed late at a coarse presentation cadence, or the standby's start waiting for its (fake) audio sink.
  Software decode and a fake sink are not the operator's: Chrome with VAAPI, a PipeWire device and a 60 Hz display.
- **The operator's hang.** The "split second" the operator sees may well be longer than the 67 ms plus 200 ms of
  stutter measured here. Hardware decoder start-up and the audio device's start happen at every `src` swap, and a
  preloaded standby moves the first of them off the boundary.

## 5. Recommendations (for `seamless-playback`)

1. **Two alternating `<video>` elements**, the standby hidden by `opacity: 0`, muted, preloaded and sought to the
   next clip's first kept frame while the Timeline plays. Use them for plain clip-to-clip boundaries only. The card
   bridge already hides its load.
2. **Measure headed before wiring** (the change's task 0.2). Run this spike and the app probe on the host's display
   in Chrome and Firefox, muted at the browser. Proceed only if the two-element hand-over meets the gate there: p90
   lost play time at most one frame interval, and p90 longest hold at most the steady hold plus one frame interval.
3. **Hand over on the last kept frame, with `ended` as a backstop only.** Today the end is often noticed by `ended`.
4. **Leave the proxy route and its `Cache-Control` as they are.**
