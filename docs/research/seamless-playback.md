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

## 6. Headed re-measurement on the host display (task 0.2, 2026-11-23)

Everything in §1-5 ran headless or under Xvfb. This section repeats the app probe and the spike headed, on the host's
display, with the gate's definitions (`design.md` D7). The dev app was only read, and the spike played copies of the
proxies.

### 6.1 Method deltas

- **Browsers, headed, on the host's display (KDE Plasma, 60 Hz).**
  - **Google Chrome 158.0.8127.36** (Flatpak), driven over CDP by Playwright 1.65.2 from the podman image
    `mcr.microsoft.com/playwright/python:v1.65.2-noble`, which holds only the driver, with `--network host`. Launched
    with `--mute-audio --ozone-platform=wayland`, a fresh profile, and
    `--disable-backgrounding-occluded-windows --disable-renderer-backgrounding
    --disable-features=CalculateNativeWinOcclusion` so that the page is never throttled as hidden.
  - **Firefox 160.0.1** (Flatpak), driven over WebDriver BiDi by a small client (no Playwright: it cannot drive a stock
    Firefox). A fresh profile with `media.volume_scale=0.0` and autoplay allowed. Its window was kept above the others
    through a KWin script (`keepAbove` on this window only): without it the tab turned `hidden` after two runs, and those
    runs were thrown away. `visibilityState` was `visible` at the end of every run kept.
  - **Firefox 159.0** from the Playwright image, headed on the host's X display from the container, as a second
    opinion. The container has no GPU, so its presentation is software-rendered and less representative.
  - Both Flatpaks ran as `flatpak run --nosocket=pulseaudio --nofilesystem=xdg-run/pipewire-0 …`. **No audio device
    was reachable, in either browser, and nothing played through the speakers.** See 6.5.
- **No Playwright route.** `fetch` and XHR writes were refused inside the page, as in §1. The app probe refused three
  `POST …/title-card/preview` per run.
- **Instrumentation.** Same hook as §1 (`src`, `currentTime`, `play()`, media events, `requestVideoFrameCallback`
  frames on `now`). `shown` slots were tagged for the two-element spike. The scripts live in the session scratchpad,
  not in the repo.
- **Scenario.** Unchanged: Edit, Next clip twice, Left, Shift+Left twice (0:04 of `s1710001.mp4`), Space, 22 s.
  - The app probe is 3 boundaries per run, 7 runs: **21 boundaries per browser**.
  - The spike is 9 boundaries per run (a 10-clip chain over the four proxies), 3 runs: **27 per case**. After each
    boundary plus 0.7 s the shown element is sought to 1.5 s before its end.
- **Definitions** (D7).
  - Decision: the app's `src =`; in the spike, the first presented frame at or after 6.00 s (the last kept frame).
  - Hold: the longest gap between successive presented frames from the outgoing clip's last frame to 0.5 s after
    the incoming's first. With two slots, only the outgoing slot's frames up to the decision and the incoming
    slot's frames from the swap count.
  - Steady hold: the same over the preceding second. A run counts as valid only when steady is at most two frame
    intervals (40 ms).
  - Lost: at decision + 0.5 s, real time since the decision, minus `6.02 - currentTime` of the outgoing clip, minus
    `currentTime - 0.005` of the incoming one. The clip's kept end is 6.02 s, while the element's `duration` is 6.06 s
    (the audio tail). In the app every hand-over is by `ended` at 6.06 s, so with the kept end the lateness counts
    as lost time; the table notes the value with `duration` as the end.
  - The gate takes the case's p50 steady hold as "steady".
- **Diagnostic cases** (not the gate): `-na` plays audio-less copies (`ffmpeg -an -c copy`) of the same proxies, and
  `two-stack` stacks the standby under the shown element instead of `opacity: 0`.

### 6.2 Today's single element in the running app (the app probe)

21 boundaries per browser. All 21 hand-overs came from `ended`, none from the frame callback. Values in ms.

| | Chrome 158 | Firefox 160.0.1 | Firefox 159 (Playwright) |
|---|---|---|---|
| Steady hold p50 / p90 | 66.7 / 100.0 | 82.3 / 91.0 | 80.0 / 80.3 |
| Longest hold p50 / p90 / max | 150.1 / 150.1 / 150.2 | 51.6 / 54.3 / 97.9 | 40.2 / 44.8 / 50.7 |
| Lost p50 / p90 | 235.9 / 240.6 | 88.3 / 90.3 | 98.0 / 99.1 |
| Lost, with `duration` as the end, p50 / p90 | 195.9 / 200.6 | 48.3 / 50.3 | 58.0 / 59.1 |
| Valid runs (steady at most 40 ms) | 0 of 21 | 0 of 21 | 0 of 21 |

The chain's steps, p50 (min to max):

| Step | Chrome 158 | Firefox 160.0.1 |
|---|---|---|
| last frame to `src =` (end noticed) | 32.2 (23.8 to 45.9) | 5.2 (1.1 to 24.2) |
| `src =` to `loadedmetadata` | 19.7 (15.8 to 27.4) | 14.0 (12 to 18) |
| `currentTime =` to `seeked` | 13.6 (6.9 to 15.2) | 22.0 (17 to 30) |
| `play()` to `playing` | 6.1 (4.7 to 8.7) | 4.0 (3 to 7) |
| last frame to the incoming's first frame | 66.8 (66.7 to 83.5) | 36.9 (21.4 to 54.3) |

In Chrome the incoming clip's first frame (frame 0) is on screen at about the time of `playing`, and its second only
about 150 ms later: the 150 ms hold in the table. Frames then come at the normal rate, so Chrome's loss is the
**start of playback after `play()`**, not the swap steps (6.3).

### 6.3 The spike: one element vs two (27 boundaries per case, ms)

| Browser | Case | Steady p50 | Longest hold p50 / p90 / max | Lost p50 / p90 | Valid |
|---|---|---|---|---|---|
| Chrome 158 | one element | 100.0 | 150.1 / 150.1 / 150.2 | 196.3 / 201.3 | 0 |
| Chrome 158 | two, `opacity: 0` | 100.1 | 150.1 / 166.8 / 166.9 | 166.7 / 166.8 | 0 |
| Chrome 158 | two, stacked | 100.1 | 150.1 / 166.8 / 166.8 | 166.7 / 166.8 | 0 |
| Chrome 158 | one, **no audio track** | 50.1 | 50.1 / 50.1 / 50.1 | 22.0 / 29.9 | 0 |
| Chrome 158 | two, `opacity: 0`, **no audio track** | 50.1 | 50.1 / 50.1 / 50.2 | -0.7 / 1.6 | 0 |
| Firefox 160.0.1 | one element | 50.1 | 45.7 / 68.0 / 76.7 | 68.6 / 69.7 | 13 |
| Firefox 160.0.1 | two, `opacity: 0` | 69.8 | 52.4 / 117.0 / 123.2 | 26.6 / 28.6 | 12 |
| Firefox 160.0.1 | two, stacked (n = 18) | 54.9 | 55.7 / 117.0 / 120.7 | 27.0 / 29.1 | 9 |
| Firefox 160.0.1 | one, no audio track | 64.6 | 66.4 / 75.1 / 88.6 | 80.2 / 120.3 | 12 |
| Firefox 160.0.1 | two, `opacity: 0`, no audio track | 68.1 | 51.0 / 106.8 / 152.0 | 39.2 / 40.2 | 10 |
| Firefox 159 | one element | 40.1 | 40.1 / 40.2 / 80.2 | 79.2 / 82.0 | 23 |
| Firefox 159 | two, `opacity: 0` | 40.1 | 50.2 / 65.5 / 88.2 | 38.2 / 41.7 | 24 |

`opacity: 0` and stacking again agree (as in §3). The last Firefox 160 stacked run lost its BiDi session, which leaves
18 boundaries for that diagnostic case.

The chain's steps of the two-element hand-over, p50 (min to max):

| Step | Chrome 158 | Chrome 158, no audio | Firefox 160.0.1 |
|---|---|---|---|
| last frame to `play()` | 0.3 (0.2 to 0.5) | 0.3 | 0.0 (0 to 1) |
| `play()` to `playing` and to the first frame | 149.9 (149.5 to 166.8) | 16.3 (15.5 to 16.6) | 24.0 (14 to 27) |
| last frame to the incoming's first frame | 150.1 (150.0 to 166.9) | 16.7 | 52.4 (43.4 to 123.2) |

For the one-element spike the steps are the app's: `src =` to `loadedmetadata` 11.4 ms and seek 11.5 ms in Chrome
(11.0 and 20.0 in Firefox 160), and the hand-over is called at the frame, with no `ended` lateness.

### 6.4 Against the gate

Gate ("Play crosses a clip boundary without a pause"): p90 lost at most 20 ms, p90 longest hold at most steady + 20 ms,
no hold over 100 ms. Evaluated on all runs, since Chrome has no valid runs (its steady hold is 50 to 100 ms).

| Browser | Case | p90 lost | p90 hold vs steady + 20 | Max hold | Meets? |
|---|---|---|---|---|---|
| Chrome 158 | today, in the app | 240.6: no | 150.1 vs 86.7: no | 150.2: no | **no** |
| Chrome 158 | two elements (audio track) | 166.8: no | 166.8 vs 120.1: no | 166.9: no | **no** |
| Chrome 158 | two elements, no audio track (diagnostic) | 1.6: yes | 50.1 vs 70.1: yes | 50.2: yes | yes |
| Chrome 158 | one element, no audio track (diagnostic) | 29.9: no | 50.1 vs 70.1: yes | 50.1: yes | no (lost) |
| Firefox 160.0.1 | today, in the app | 90.3: no | 54.3 vs 102.3: yes | 97.9: yes | **no** (lost) |
| Firefox 160.0.1 | two elements | 28.6: no | 117.0 vs 89.8: no | 123.2: no | **no** |
| Firefox 159 | today, in the app | 99.1: no | 44.8 vs 100.0: yes | 50.7: yes | **no** (lost) |
| Firefox 159 | two elements | 41.7: no | 65.5 vs 60.1: no | 88.2: yes | **no** |

- **Today's single element does not meet the gate** in either browser. There is something to fix.
- **The two-element hand-over, as spiked, does not meet the gate in either browser.** It saves play time (Chrome
  196 to 167 ms, Firefox 160 70 to 29 ms, Firefox 159 82 to 42 ms, p90 of lost), but the residual is far above 20 ms,
  and in Firefox 160 the upper tail of the hand-overs holds 117 to 123 ms.
- **In Chrome the residual is the audio track, in every mode.** The same hand-over with audio-less proxies loses
  1.6 ms (p90) and holds as long as the steady hold. A `play()` on an element with audio takes 150 ms to produce its
  next frame, whether that element was preloaded or not.

### 6.5 Caveats

- **No audio device.** The rule that nothing may reach the speakers withheld the Flatpaks' audio sockets, so both
  browsers used a null or absent sink. The 150 ms audio start in Chrome may be that sink's behaviour or Chrome's own
  audio renderer start-up. This run cannot tell. Telling needs a sink the operator's speakers are not behind, such
  as a muted PipeWire null sink, which is the operator's call. Until then the verdict for Chrome rests on a setup the
  operator does not have. Firefox's residual (27 ms) does not depend on the audio track (the `-na` cases are equal
  or worse).
- **Presentation cadence.** Chrome shows the 50 fps proxies on the 60 Hz display with a 50 ms gap every fourth
  vsync, so its steady hold is 50 to 100 ms and no Chrome run meets the "at most two frame intervals" validity rule.
  Firefox 160 meets it for about half of its boundaries. The gate was evaluated on all runs, with the p50 steady
  hold. The steady p90 also includes the last frame's own approach (a 100 ms gap into frame 6.04).
- **Neither browser reported every frame.** In the raw frame logs, the `mediaTime` step between successive
  `requestVideoFrameCallback`s is 20 ms for about 75% of steps in Chrome and 40 ms for the rest, so Chrome drops about
  one frame in five. In Firefox (both builds) it is 40 ms for about 90% of steps, so Firefox reports every other
  frame. Firefox's "valid" runs (steady at most 40 ms) are therefore runs at 25 presented frames per second, not 50.
  Hold and steady are measured at that cadence. Lost does not depend on it (D7), so the lost column is the most
  reliable one here.
- **Firefox.** Its callback times have 1 ms resolution. In the two-element spike its first callback after `play()` is the
  already presented pre-sought frame, so "last frame to first frame" there (6.5 ms in 159) is not a new frame.
  Firefox 159 is the Playwright build in a container without a GPU.
- **`ended` hand-overs.** The app notices the end only through `ended` (6.06 s, after the video's last frame), and
  the spike hands over at the last frame. The 40 ms between the two is in the app's `lost` when the kept end is used,
  and not in the one with `duration` as the end.
- The two-element spike unmutes the standby at `play()` and mutes the freed slot, as in §3. It does not try to start
  the standby's audio before the boundary. That was outside this task.
