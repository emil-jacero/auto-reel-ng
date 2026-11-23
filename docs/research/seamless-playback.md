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

### 6.6 Chrome with a null audio sink

§6.5 said Chrome's 150 ms `play()` to first-frame residual might be an artifact of having no audio sink at all. This
subsection reruns Chrome with a real audio path that cannot reach the speakers.

**Setup.**
- A PipeWire null sink, `pactl load-module module-null-sink sink_name=claude_null` (module 536870916). The default sink
  was never set by the run, and the module was unloaded at the end (`pactl list short sinks` no longer lists it).
- Chrome 158.0.8127.36 (Flatpak), a fresh profile, headed on the host display, the same flags as §6.1 but **with** the
  pulseaudio socket and `flatpak run --env=PULSE_SINK=claude_null com.google.Chrome ...`. Two configurations:
  `--mute-audio` kept as a second guard, and **no** `--mute-audio`.
- A watchdog polled `pactl --format=json list sink-inputs` every 0.2 s and was set to kill Chrome if any Chrome stream
  was on another sink. It never fired: all 68 logged snapshots, in both configurations, show Chrome's stream on
  `claude_null` (not muted by the stream flag, corked and uncorked as the elements played). With `--mute-audio` the
  stream is still created, so that flag does not remove the audio path on this build. Audio-less proxies (`-na`)
  create no stream.
- Same scenario, definitions and scripts as §6.1 to §6.4: the app probe 7 runs (21 boundaries), the spike 3 runs of
  9 boundaries (27 per case). Every run was `visibilityState: visible`. The app was only read, with writes refused in
  the page (three refused `title-card/preview` POSTs per run). Raw results and the sink log:
  `results/spike2/` in the session scratchpad (`measure/`), not in the repo.

**Results** (ms; p50 / p90, hold also max).

| Case | Sink | Steady p50 | Longest hold p50 / p90 / max | Lost p50 / p90 | Lost, `duration` end, p50 / p90 |
|---|---|---|---|---|---|
| today, in the app (n = 21) | none (§6.2) | 66.7 | 150.1 / 150.1 / 150.2 | 235.9 / 240.6 | 195.9 / 200.6 |
| today, in the app (n = 21) | null, `--mute-audio` | 50.0 | 83.2 / 83.4 / 83.4 | 142.9 / 147.7 | 102.9 / 107.7 |
| today, in the app (n = 21) | null, unmuted | 50.0 | 66.7 / 89.5 / 93.9 | 141.3 / 146.0 | 101.3 / 106.0 |
| spike, one element (n = 27) | none (§6.3) | 100.0 | 150.1 / 150.1 / 150.2 | 196.3 / 201.3 | |
| spike, one element (n = 27) | null, `--mute-audio` | 50.1 | 66.7 / 66.7 / 66.8 | 105.1 / 110.4 | |
| spike, one element (n = 27) | null, unmuted | 51.4 | 68.1 / 71.7 / 87.0 | 105.9 / 109.0 | |
| spike, two, `opacity: 0` (n = 27) | none (§6.3) | 100.1 | 150.1 / 166.8 / 166.9 | 166.7 / 166.8 | |
| spike, two, `opacity: 0` (n = 27) | null, `--mute-audio` | 83.3 | 66.7 / 66.8 / 83.4 | 72.6 / 86.2 | |
| spike, two, `opacity: 0` (n = 27) | null, unmuted | 67.6 | 66.7 / 69.5 / 69.7 | 70.8 / 74.5 | |

Steps of the two-element hand-over, p50: `play()` to `playing` and to the first frame **66.4 ms** (49.6 to 83.2) with
`--mute-audio`, **66.5 ms** (49.9 to 69.3) unmuted, against 149.9 ms with no sink; last frame to the incoming first
frame 66.7 ms in both, against 150.1 ms. In the one-element spike `play()` to `playing` is 0.1 ms and the cost sits in
the seek (7.8 ms), `loadedmetadata` (11 to 12 ms) and the wait for the first frame (last frame to first frame 33 to
37 ms).

**Against the gate** (all runs, as in §6.4; no run met the validity rule, steady is at most two frame intervals).

| Case (null sink, unmuted) | p90 lost | p90 hold vs steady + 20 | Max hold | Meets? |
|---|---|---|---|---|
| today, in the app | 146.0: no | 89.5 vs 70.0: no | 93.9: yes | **no** |
| one element (spike) | 109.0: no | 71.7 vs 71.4: no | 87.0: yes | **no** |
| two elements, `opacity: 0` | 74.5: no | 69.5 vs 87.6: yes | 69.7: yes | **no** (lost) |

With `--mute-audio` the outcome is the same: p90 lost 147.7, 110.4 and 86.2 ms, all above 20 ms; the hold and max-hold
terms are met by the one-element and two-element spikes.

**What this changes.**
- **The 150 ms residual was partly a no-sink artifact.** With a sink that accepts the stream, `play()` to first frame
  falls from about 150 ms to about 66 ms (the same 4-vsync quantum seen in the steady hold), and the two-element
  p90 lost falls from 166.8 to 74.5 ms (86.2 ms muted). Today's app falls from 240.6 to 146.0 ms. The earlier numbers
  overstated Chrome's loss for a user with audio.
- **It is still not seamless.** The two-element hand-over keeps about 70 to 86 ms of lost time in Chrome with audio,
  well over the 20 ms gate, and its two-element saving over today's single element is about 70 ms (p90 lost
  146.0 to 74.5). The audio-less diagnostic (§6.4: 1.6 ms) says the remaining cost still comes with the audio track:
  the audio renderer starts the standby's stream at `play()`, and the first frame waits for it.
- **`--mute-audio` does not change the audio path** here (the stream exists, on the sink, and the numbers differ by
  small amounts, within the spread between two runs of one configuration). It is not the cause of the residual.
- Hence a plain "play the standby at the boundary" two-element swap does not satisfy the gate in Chrome. A design that
  starts the standby's playback (audio included) before the boundary, or one that decouples audio from the video
  swap, is what would be needed. That is outside this measurement.

**Caveats.** The null sink has no hardware clock, so its latency model is not the operator's actual device. The
operator's default sink at the end of the run was a Bluetooth sink that appeared during the session; Chrome was only
ever routed to `claude_null` and nothing was moved. Chrome's presentation cadence caveats of §6.5 (50 fps on 60 Hz,
dropped callbacks) apply unchanged, so the lost column is the robust one.

### 6.7 Early standby start

Today the standby's `play()` is called on the outgoing clip's last kept frame, and its first new frame comes after the
play start-up (Firefox 160 about 24 ms, Chrome 66 ms with a sink and 150 ms without). This subsection starts the standby
before the boundary so that its clock is already running when the outgoing clip ends.

**Method.**
- The §6.1 to §6.6 harness, with a new page (`spike3.html` in the session scratchpad `measure/`; analysis
  `analyze3.py`). Two elements, the standby hidden with `opacity: 0`. 27 boundaries per case (3 runs of 9), every run
  `visibilityState: visible` (Firefox and Chrome windows kept above with a KWin script, by pid, as in §6.1).
- The incoming clip's first kept frame is a trimmed in-point, **IN = 0.100 s** (frame 5), so that the standby can be
  pre-sought before it. (With IN = 0 a pre-seek "before the first kept frame" is impossible.) The outgoing clip's kept
  end is 6.02 s; its last kept frame is 6.00.
- Cases are named `early-L-P`: `play()` on the standby L ms before the outgoing's kept end (a timer from a median
  `callback time - mediaTime` offset of the outgoing's frame callbacks, because Firefox reports only every other
  frame), the standby pre-sought to IN - P. The outgoing pauses at its last kept frame (the decision, as before). The
  swap is on the standby's first presented frame at or after IN, but not before the outgoing's last frame has had its
  20 ms. With P = 0 the pre-sought frame is already presented, so the swap is at decision + 20 ms. `-mu`: the standby
  is muted from `play()` to the swap and unmuted at the swap. Unmuted otherwise, as in §6.3.
- L values: 20 (1 frame), 40 (2 frames), and the browser's measured `play()` to first frame p50 ("lat"): 24 (Firefox
  160), 66 (Chrome, null sink, §6.6), 150 (Chrome, no sink, §6.3). `early-20-0` is the control: today's scheme with the
  in-point pre-sought. `two-opacity` is §6.3's case, rerun in the same session.
- Setups. Firefox 160.0.1 Flatpak, no audio socket, `media.volume_scale=0.0`. Chrome 158 Flatpak, `--mute-audio`, once
  with no audio socket and once with `PULSE_SINK=claude_null` (a `module-null-sink` created and unloaded for the run;
  the default sink was `alsa_output.usb-Razer...` before and after and was never touched; the module is gone).
- Lost is reported two ways. **D7** (as §6: `currentTime` of the outgoing at the decision and of the incoming at +0.5 s)
  and **frame clock** (the same formula, with both positions taken from the frame callbacks' `callback time -
  mediaTime` median). In Firefox, `currentTime` of a playing element is stale by up to about 40 ms (a read at the
  decision gave 5.96 when the frame on screen was about 6.00), which biases D7 lost low by 30 to 40 ms in the timer-based
  cases. **Use the frame-clock column in Firefox.** In Chrome the two agree to about 10 ms.
- **A negative lost is not good.** It means the standby's media clock ran ahead of what was shown, i.e. content at
  the start of the incoming clip was skipped (a jump, and the audio ahead of the picture). The target is about 0.

**Results** (ms, p90 unless stated; hold gate = steady p50 + 20; "meets" = lost frame-clock within 20 and no more
than about 20 ahead, hold p90 within the gate, max hold at most 100).

Firefox 160.0.1 (steady hold p50 40; the two-opacity baseline's steady is 66):

| Case | Lost D7 | Lost frame clock (p50 / p90) | Hold p90 / max | Gate hold | Meets? |
|---|---|---|---|---|---|
| two-opacity (today's two-element swap) | 27.4 | 19.5 / 20.7 | 117.0 / 128.4 | 86.2 | no |
| early-20-0 (control) | -56.0 | -26.8 / -25.8 | 60.3 / 61.0 | 60.1 | no (ahead, hold +0.2) |
| **early-20-20** | -36.0 | -6.3 / -4.8 | **52.1 / 53.3** | 60.1 | **yes** |
| early-40-40 | 9.1 | -6.7 / -5.2 | 72.8 / 73.6 | 60.1 | no (hold) |
| early-24-24 | -32.5 | -10.2 / -8.0 | 74.6 / 85.6 | 60.1 | no (hold) |
| early-24-0 | -57.3 | -29.8 / -28.2 | 59.3 / 60.0 | 60.1 | no (28 ms ahead) |
| early-24-24-mu | -20.2 | -3.4 / -2.8 | 72.4 / 84.0 | 60.1 | no (hold) |
| early-24-0-mu | -44.7 | -43.6 / -42.6 | 58.8 / 60.0 | 60.1 | no (43 ms ahead) |

Chrome 158, no audio sink (L = lat = 150; steady p50 50):

| Case | Lost D7 | Lost frame clock (p50 / p90) | Hold p90 / max | Gate hold | Meets? |
|---|---|---|---|---|---|
| two-opacity | 166.8 | 205.0 / 215.1 | 156.7 / 166.7 | 120.0 | no |
| early-20-0 (control) | 116.4 | 113.4 / 114.7 | 134.3 / 134.8 | 70.1 | no |
| early-20-20 | 136.4 | 153.4 / 156.7 | 283.3 / 283.3 | 70.1 | no |
| early-40-40 | 113.7 | 136.7 / 140.0 | 250.1 / 250.1 | 70.1 | no |
| early-150-150 | 93.4 | 116.7 / 116.8 | 183.3 / 183.4 | 70.1 | no |
| **early-150-0** | -11.6 | -10.1 / 6.7 | **65.8 / 66.0** | 70.1 | **yes** |
| early-150-150-mu | 50.8 | 46.7 / 58.0 | 183.3 / 183.4 | 70.1 | no |
| early-150-0-mu | -54.2 | -46.7 / -46.6 | 65.7 / 66.1 | 70.1 | no (47 ms ahead) |

Chrome 158, null sink `claude_null`, `--mute-audio` (L = lat = 66; steady p50 50, baseline 83):

| Case | Lost D7 | Lost frame clock (p50 / p90) | Hold p90 / max | Gate hold | Meets? |
|---|---|---|---|---|---|
| two-opacity | 83.8 | 88.4 / 106.4 | 83.3 / 83.4 | 103.3 | no |
| early-20-0 (control) | 35.1 | 26.7 / 34.7 | 70.7 / 71.0 | 70.1 | no |
| early-20-20 | 53.4 | 50.0 / 57.4 | 283.3 / 283.4 | 70.1 | no |
| early-40-40 | 54.1 | 46.7 / 60.0 | 250.1 / 250.1 | 70.1 | no |
| early-66-66 | 57.3 | 46.6 / 60.1 | 266.7 / 266.7 | 70.1 | no |
| **early-66-0** | -9.8 | -16.6 / -6.7 | **66.1 / 66.3** | 70.1 | **yes** |
| early-66-66-mu | 53.2 | 40.1 / 46.0 | 266.7 / 266.7 | 70.1 | no |
| early-66-0-mu | -23.4 | -33.3 / -24.0 | 66.1 / 66.3 | 70.1 | no (24 ms ahead) |

**What the numbers say.**
- **The literal scheme (pre-seek to first kept frame - L, `play()` L before the end) does not help.** The standby's clock
  starts after its play latency, so pre-seeking L earlier just moves its first kept frame L later: Chrome 66-66, 150-150,
  40-40 and 20-20 all lose 45 to 136 ms and hold 180 to 283 ms. In Firefox it is neutral to slightly worse (20-20 passes
  at 24 ms latency only because one frame of pre-roll matches the 20 ms last frame; 40-40 and 24-24 skip 20 to 40 ms and
  hold longer).
- **What works is a different split: pre-seek the standby exactly to its first kept frame (P = 0), call `play()` about
  the measured play latency before the outgoing's end, unmuted, and show the already presented pre-sought frame at the
  boundary.** In Chrome that meets the gate in both audio setups (`early-66-0`, `early-150-0`: p90 lost -10 to 7 ms,
  hold p90 66 ms against a 70 ms limit, max hold 66 ms, steady 50). It is the only variant that does.
  - The lost time is linear in the mismatch, `lat - L`. Under-compensating (early-20-0 against a 66 or 150 ms latency)
    leaves 27 and 114 ms of lost; over-compensating leaves the standby ahead (skipped content), which is what the muted
    variant shows.
  - **Muting the standby until the swap makes it worse.** A muted element has no audio start-up, so its clock runs
    at once and is ahead by the whole `lat`: Chrome `-mu` runs 24 ms (null sink) and 47 ms (no sink) ahead, Firefox
    24-0-mu 43 ms. The audio start-up is the cost being hidden, so it has to be paid before the boundary, with the
    element unmuted. (Unmuting at the swap did not add a visible stall; hold is the same as unmuted.)
  - **Firefox does not get a clean pass from the same recipe.** With P = 0 (early-24-0, early-20-0) its clock runs 26 to
    30 ms ahead of the frames (its `play()` starts the clock at once, and the first frame is late). With P = 20,
    L = 20 (one frame of pre-roll and `play()` on the last frame) it is aligned (lost -5 ms) and meets the gate. In
    Firefox the earliest start is not needed: the best case equals today's `play()` time with a one-frame pre-seek.
    The Firefox hold terms are close to the 40 ms frame-report resolution, so "meets" there is at the resolution
    limit.
- **Today's two-element swap, rerun here for comparison** (`two-opacity`), reproduces §6.3 and §6.6: Firefox p90 lost 21
  (frame clock), hold p90 117; Chrome 84 (null sink) and 167 ms (no sink).
- Needs the play latency up front. The recipe depends on knowing `play()` to first frame on this machine and audio
  device (24 ms Firefox here, 66 ms Chrome with the null sink, 150 ms with no sink). A real device (a Bluetooth sink,
  for one) has other values, and no run here measured a mismatch other than the ones in the tables. A calibration per
  session (time the first standby `play()`) would be needed before this could be adopted, and it would still need
  checking on the operator's real sink.

**Overlap, duplicates and audio doubling.**
- **Picture.** The standby stays `opacity: 0` until the swap and the outgoing is paused on its last kept frame at the
  decision, so both are never visible together by construction. From the frame callbacks' `shown` tags, over all cases
  (27 boundaries each, 25 cases): 0 outgoing frames after the swap, 0 standby frames before it, 0 repeated frames
  (same `mediaTime` twice in a row) and 1 backwards `mediaTime` step (Firefox `early-24-24-mu`). Duplicate detection
  rests on the callbacks, and Firefox reports every other frame, so a single repeated frame could be missed there. The
  one thing that does show is a jump: the skipped content in the "ahead" cases above (20 to 140 ms of the incoming
  clip, no overlap).
- **Audio.** The elements are both playing, unmuted, from the standby's `play()` to the outgoing's pause: **0 to 1 ms**
  for L = 20, 20 to 24 ms (Firefox, L = 40), 4 ms (Firefox, L = 24), 23 ms (Chrome 40-40), **46 ms (Chrome, null sink,
  66-0) and 130 ms (Chrome, no sink, 150-0)**. That is structural: the two audio streams exist at once, and the
  standby's does not produce sound until its audio start-up is over (about the same time as the boundary, which is the
  point), so the audible overlap should be near zero when L matches the latency and about `L - lat` otherwise. **That was
  not checked by ear or by recording**: nothing reached the speakers by rule, and the null sink's monitor was not
  captured. The muted variants have no overlap at all but skip content.
- Chrome's stream was on `claude_null` in all 1725 logged snapshots of this run (parsed per stream: Chrome only on
  the null sink; the other streams in the log are the operator's own Firefox, untouched). The §6.6 watchdog compared
  against a pattern that never matched its own log lines (`#id sink`), so its "never fired" says nothing; this run's
  watchdog is the same script, and the check that counts is the per-stream parse above.

**Caveats.**
- Playing latency was measured on a null or absent sink. §6.5 applies: the operator's real device may differ, and a
  Bluetooth sink would be larger.
- Firefox's `currentTime` staleness makes D7 lost unreliable there (above), and Firefox reports every other frame, so
  its hold and steady cannot resolve the 20 ms gate. The Chrome result (hold p90 66 against 70) is within 4 ms of the
  limit as well, helped by the 4-vsync cadence of 50 fps on 60 Hz.
- IN = 0.100 differs from §6.3's frame-0 start (so the in-point seeks mid-GOP); the `early-20-0` control and the
  rerun `two-opacity` are the comparisons.
- The decision is on a timer predicted from the frame callbacks (the frame 6.00's expected time) rather than the first
  reported frame, because Firefox skips that frame. The earlier Firefox cases decided on the first reported frame at or
  after 6.00, which can be 6.04.
- One Firefox session was restarted (a stale BiDi session); all kept runs were `visible`.
- Raw results, logs and the sink-input log: `results/spike2/` in the session scratchpad (`measure/`): `ff160-*`,
  `chrome-nosink-early-*`, `chrome-null-early-*`, `analyze3-*.txt`, `early-sinkinputs.log`. Scripts: `spike3.html`,
  `measure3.py`, `measure_ff3.py`, `analyze3.py`, `runE_*.sh`. Not in the repo.

### 6.8 Functional run of the built hand-over (task 2.2, 2026-11-23, headless)

Playwright 1.65 headless (Firefox 159 and Chromium from the image, writes refused, muted at the browser, no audio
device), the branch's own Vite against `Grillning med grannar` (four 6.02 s proxies; the first chapter's black card
plays for about 6 s first). These runs check behaviour, not the gate: headless presents every 33 to 100 ms, so they say
nothing of lost time or hold.

- **What triggered the hand-over** (plain boundaries, 18 in 6 runs after the fixes below): `timer` 18, `frame` 0,
  `ended` 0. Over the other scenarios, 28 more boundaries: `timer` 24, `frame` 1 (a Play resumed 80 ms before a trailing
  cut), `seeked` 1 (the slow proxy: the last frame held 2.0 s, no blank sample in 2160), the rest `timer`.
- **LEAD observed** (median after each sample): Firefox 159 49 to 66 ms, Chromium 85 to 104 ms. **P**: 0 on every IN = 0
  boundary (no pre-roll possible). With a leading cut on every clip it went 0, 0, then 40 (the clamp) in Firefox and
  stayed 0 in Chromium; one Chromium run reached 38 after a cancel. Firefox's P is unsettled here: 3.1 decides it.
- **Cancel during the lead**: pause, Next clip and a scrub paused the standby and sent it back to its pre-sought
  position (Firefox: `seeking` then `seeked` 10 ms later, the clip stayed shown, no swap); a Play 6 ms after the pause
  (a trailing cut makes the boundary come at once) handed over only after the standby's `seeked` in both browsers.
  A pause after the decision swaps and leaves the incoming clip paused at its first kept frame.
- **Two findings that shaped the code.** (1) In Firefox, writing another slot's `src` from inside a frame callback ends
  the shown slot's `requestVideoFrameCallback` chain for good (a fresh registration never fires either, while
  `mozPaintedFrames` goes on): the swap and the frame loop now defer that write to its own task (`aimSoon`). Before it,
  4 of 6 Firefox boundaries came through `ended`, 1.5 s late (the swap watchdog). (2) Firefox reports the pre-sought
  frame again at `play()` (`currentTime` still at the sought position); counting it made LEAD 3 to 11 ms, so a LEAD or
  alignment sample needs `currentTime` past the sought position as well.
- Scripts: `pw/h22.py`, `pw/sc.py` in the session scratchpad. Not in the repo.
