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

### 6.9 Built (task 3.1, 2026-11-23)

Everything here was run on the built code (`feat/seamless-playback` at `f6e9c834`) against `2024-06-27 - Grillning med
grannar` (four 6.02 s, 50 fps proxies). **The boundary gate of D7 fails in both browsers, "A plain boundary" fails its first-frame clause and "Pause during the lead" its last clause.** Details below; nothing was
tuned and no definition was changed after the first headed run. (The task asked for a subsection "§6.8 Built"; §6.8
already holds the task 2.2 functional run, so this one is §6.9.)

#### Setup

- **Builds compared.** The built app is the branch's Vite (port 5174). The single-element hand-over it replaces is
  `web/` of `d11e2345` (the parent of the first code commit), exported with `git archive` into the scratchpad and served
  by its own Vite (port 5175), same service, same proxies, same hook. Only the Timeline differs.
- **Service.** The task named the service on `127.0.0.1:8080`; nothing there answers `/api/v1`. The dev service the
  earlier runs used (`auto-reel serve` on port 8102) was gone half-way through this task, so a second `auto-reel serve`
  of the same library was started on 8102 from the main checkout's venv (no writes: the page refuses them) and stopped
  at the end.
- **Functional runs.** Playwright 1.65.2, Firefox 159 and Chromium from the image, headless, muted, no audio device, PUT,
  POST and DELETE intercepted. Scripts in the session scratchpad (`pw/f31.py`, `pw/f31lib.py`), not in the repo.
- **Headed runs.** Firefox 160.0.1 and Chrome 158.0.8127.36 (Flatpaks), fresh profiles, on the host display, **sound on**
  and routed to a PipeWire null sink (`pactl load-module module-null-sink sink_name=claude_null`, module 536870916,
  `PULSE_SINK=claude_null` in each browser's environment; unloaded at the end, `pactl list short sinks` no longer lists
  it). The default sink (the operator's headset) was never touched. A watchdog logged every sink input and was set to
  kill my browser if one of its streams sat on another sink. All 355 Firefox and 82 Chrome snapshots of my instances show
  their streams on `claude_null` (6 Firefox snapshots show a corked stream not yet routed). The operator's own Firefox
  streams were on their headset throughout and were not touched. (A first watchdog compared against any new stream. It killed the browser once because of the operator's own audio
  and once because of my own corked, not yet routed stream; it was replaced by one that matches the Flatpak instance id
  of the stream and ignores unrouted streams. No kept run was affected: each started on a fresh browser.)
- **Page visible throughout.** A KWin script kept my browser windows above the others. `visibilityState` was sampled
  every 2 s in every loop: 0 `hidden` samples in all 64 loops kept, `hasFocus()` true at the end of each. In-page writes
  were refused (3 `title-card/preview` POSTs per block), no Playwright route.
- **Script.** One loop is: put the playhead at 0:04 of `s1710001.mp4`, press Play, 21.8 s of play (three plain
  boundaries, `s1 -> s2 -> s3 -> s4`), Pause if still playing. A block is a fresh tab, so a fresh calibration. Per
  browser: `built` 12 loops, `single` 8 loops, `built` 12 loops, in one browser session (72 built and 24 single
  boundaries). Firefox ran first.
- **Definitions** are D7's, computed from the frame callbacks of both slots (`requestVideoFrameCallback`, callback time and
  media time, `sb`-tagged frames of the standby excluded, the incoming's frames counted from the swap):
  - lost = (frame-clock offset of the incoming over its first 0.5 s) minus (offset of the outgoing over its last second)
    minus 6020 ms (the kept end);
  - hold = longest gap between successive visible callbacks from the outgoing's last callback to 0.5 s after the incoming's
    first;
  - steady = the same over the outgoing's last second, valid when at most 52 ms;
  - percentiles by linear interpolation; hold limit = median steady plus 20 ms in whole milliseconds.

#### The boundary gate (headed, null sink, sound on)

ms; "valid" = boundaries whose steady play kept its cadence (the gate counts only these); "all" = every boundary.

Firefox 160.0.1:

| Case | n (valid / all) | Lost p10 / p50 / p90 | Hold p50 / p90 / max | Steady median | Hold limit | Max skip |
|---|---|---|---|---|---|---|
| **built** (valid) | 69 / 72 | -40.6 / -10.0 / 7.2 | 117.0 / 133.0 / 150.0 | 50.0 | 70 | 53.0 |
| built (all) | 72 | -40.0 / -10.2 / 7.0 | 117.0 / 133.0 / 150.0 | 50.0 | 70 | 53.0 |
| single element (valid) | 12 / 24 | 217.2 / 222.5 / 263.0 | 234.0 / 250.9 / 267.0 | 50.5 | 70 | 0 |
| single element (all) | 24 | 219.2 / 247.5 / 279.3 | 167.0 / 245.2 / 267.0 | 83.5 | 104 | 0 |

Chrome 158.0.8127.36:

| Case | n (valid / all) | Lost p10 / p50 / p90 | Hold p50 / p90 / max | Steady median | Hold limit | Max skip |
|---|---|---|---|---|---|---|
| **built** (valid) | 72 / 72 | -40.0 / -29.9 / -7.4 | 83.3 / 116.6 / 133.2 | 33.4 | 53 | 56.6 |
| single element (valid) | 6 / 24 | 129.1 / 140.0 / 146.7 | 83.4 / 91.8 / 100.1 | 33.5 | 53 | 0 |
| single element (all) | 24 | 126.7 / 146.7 / 160.0 | 83.3 / 83.4 / 100.1 | 66.7 | 87 | 0 |

**Verdict.**

| Term | Firefox built | Chrome built |
|---|---|---|
| p90 lost at most 20 ms | 7.2: yes | -7.4: yes |
| p10 lost at least -40 ms | -40.6: **no** (by 0.6 ms; -40.0 over all 72) | -40.0: yes (on the limit) |
| p90 hold at most steady + 20 | 133.0 against 70: **no** | 116.6 against 53: **no** |
| no hold over 100 ms | max 150.0: **no** | max 133.2: **no** |
| no skip over 60 ms | 53.0: yes | 56.6: yes |
| **Gate** | **FAILS** | **FAILS** |

The gate fails in Firefox, the primary browser, on the hold terms (and by 0.6 ms on the lost floor, if only valid
boundaries count), and in Chrome on the hold terms. It is a large improvement on the single element in lost time (Firefox
about 220 ms to about -10 ms median, Chrome about 140 ms to about -30 ms median), but it is not within one frame
interval of continuity.

**Lead and P as observed** (built, all 72 hand-overs each, every one by the `timer` path, none by `frame`, `ended` or
`seeked`):

| Browser | LEAD median (min to max) | LEAD clamp hits (0 / 250) | P |
|---|---|---|---|
| Firefox 160 | 52 ms (40 to 83) | 0 / 0 | 0 on every hand-over |
| Chrome 158 | 72 ms (54 to 84) | 0 / 0 | 0 on every hand-over |

P is 0 on every hand-over because every incoming clip here starts at frame 0 (IN = 0): no pre-roll is possible, so the
alignment error cannot be corrected on this event. The consequence is visible in lost: the incoming clip's media clock
runs ahead of its picture, so the start of the incoming is skipped (Chrome p50 -29.9 ms, Firefox p50 -10.0 ms, down to
-56.6 and -53.0 ms), within the -60 ms skip limit but at the -40 ms floor at p10.

**Where the hold comes from.** Diagnostic, not part of the gate. In every boundary the hold is the gap from the outgoing's
last reported frame to the incoming's first reported frame after the swap. The swap is not at the one-frame step after
the last kept frame: `swap` runs from the incoming slot's next frame callback once `swapAt = decision + one frame
interval` has passed (`useTimelineVideo.ts`, `onFrameOf`). Timing from the frame clock of the outgoing (time of its
frame 6.00) to the DOM swap, 72 boundaries each:

| Browser | swap minus t(6.00), p10 / p50 / p90 | first incoming callback after the swap, p10 / p50 / p90 |
|---|---|---|
| Firefox 160 | 43 / 59 / 77 ms | 19 / 21 / 37 ms |
| Chrome 158 | 24 / 34 / 47 ms | 16 / 49 / 50 ms |

So the last kept frame is held about 40 to 60 ms (Firefox) or 20 to 30 ms (Chrome) longer than the one frame step, because
the swap waits for the next callback of the incoming slot, and Firefox reports only every other frame. The
single-element hold is 250 ms (Firefox) and 83 ms (Chrome) for comparison. Firefox's callback resolution (40 ms)
also inflates the measured hold by up to one reporting interval, because D7 counts from the outgoing's last *reported*
frame, which is up to 40 ms before its frame 6.00. This note is a reading of the numbers and the code, not a tested fix.

**Steady cadence.** Firefox reports 33 or 50 ms gaps in steady play (about every other frame); 69 of 72 built boundaries
and 12 of 24 single-element boundaries were valid. Chrome's steady gaps are 33 or 50 ms; all 72 built boundaries but only 6
of 24 single-element ones were valid (the baseline's steady play is 67 ms more often: its steady median over all is 66.7
ms). The single-element comparison therefore rests on 12 (Firefox) and 6 (Chrome) valid boundaries; the "all" rows have 24.

#### Scrub, frame step, card hand-over, readout (headed, null sink, built)

| Check | Firefox 160.0.1 | Chrome 158.0.8127.36 | Limit |
|---|---|---|---|
| Scrub, distinct frames presented per second, median (min to max over 24 / 12 one-second windows) | 30 (29 to 31) | 58 (49 to 60) | at least 30 |
| Frame step, keydown to the next presented frame, 40 Right presses, p50 / p90 / max | 15.9 / 26.6 / 230.4 ms | 17.2 / 22.0 / 24.3 ms | p90 at most 60 ms |
| Card hand-over, opening card to clip 1, sampled blank frames (each rAF, 600 ms around the card layer going away) | 0 of 6 hand-overs | 0 of 6 | none |
| Readout across the first clip's end, width and left edge | one width and one left edge per element in all samples (299.7 / 366 px at 1280 / 390 px) | same (299.6 / 351 px) | fixed width |

- **Scrub.** A scripted drag over each of the four clips (188 pointer moves of 16 ms, so 3 s; Chrome took 3.2 s, Firefox
  6.3 s through its BiDi pointer actions), counted as distinct `mediaTime` among the reported frames in each whole
  second of the drag (12 windows in Chrome, 24 in Firefox). Firefox sits on the limit (30.0 median, 29 at the minimum); its callbacks count the frames it
  reports (`presentedFrames` delta also 30), so this is the same resolution caveat.
- **Readout.** Four runs per browser (1280 and 390 px wide, light and dark), 100 ms samples (52 to 53 each) across the
  first clip's end: the readout box has one width and one left edge, every text from the first clip's `Clip 0:04.00 of
  0:06.02 Event 0:11.00 of 0:31.08` into the second's, and the slider's value text names clip and event. **The event is not
  the one the spec scenario names** (clips of 9.00, 40.00 and 6.02 s, event 55.02): the library has none; this event's
  clips are 6.02 s each (event 31.08). Chrome here is 158 (the spec floor is 157).

#### Functional run in Playwright, Firefox and Chromium, every scenario

Headless, muted, writes intercepted. **Pass in both browsers** unless stated:

- **`event-timeline`, added:** a plain boundary (no blank sample, the first reported frame of the next clip at media time
  0.06 to 0.1, so 3 to 5 frames are skipped: **this fails the scenario's clause "the first frame ... is its first frame"**, which the functional check did not enforce; see the skipped start in the gate; its proxy requested before the clip ended and not again at the swap, playhead and readout in the next
  clip); into a leading cut (first frame at 1.5, none inside the cut); over a clip cut whole; a slow proxy (the last
  frame held until the proxy arrived, then a `seeked` hand-over, no blank sample); the order changed while playing; **into
  a black card** (a second chapter with a 3 s card; 0 blank samples outside the card's span; the standby takes no part
  and the card covers the shown slot's load of the next clip, which shows blank video samples under it only); a scrub in the
  lead (Chromium too: the shown slot and the standby paused 100 ms in, the standby at its pre-sought 1.5 s, play resumed
  after the scrub); Next clip in the lead; "Play again while the standby is returning" (the return seek forced to take 700
  ms by deferring it in the page; Firefox and Chromium both: the swap came only after the standby's `seeked`, first
  frame at 1.56 and 1.58); the cancel-after-decision paths (a pause 40, 90 and 140 ms after the standby started: no blank,
  everything paused; a late proxy whose standby starts and is cancelled right after it started: swap then paused at the
  first kept frame; a pause after the decision with the standby's seek slow); Firefox and Chromium with **P above 20**
  (learned from leading cuts on every clip: P went 0, 0, then 40, the clamp, in Firefox; 0, 0, 0, 40, 40, 28 and 35 in
  Chromium) followed by a delayed proxy and the `seeked` hand-over (first frame 1.56 and 1.54, 0 blank samples).
- **standby requirement:** nothing loads while paused (only the proxies of the clips the playhead visited; the second slot
  has no `src`); the standby is muted, `opacity: 0`, `aria-hidden`, `tabindex -1` while it waits, and unmuted and
  playing, still `opacity: 0` and the button still `Pause`, in the lead state (the lead state was held still by
  starting the standby by hand; the 100 ms window of a real lead cannot be photographed), stage screenshots show only
  the shown clip; another player starting 1 s before the boundary (a foreign `<video>` and the bin's preview player: the
  Timeline pauses, the standby did not start); a preview opened while the Timeline plays (one video left, no Timeline
  proxy requested); Use as poster after a hand-over (the poster area shows the shown slot's frame); the standby is turned
  before it is shown (turned 90, then Rotate right before the boundary: the shown slot has 180, no proxy requested again).
- **`web-app`:** the Movie section's player is paused when a clip's player is started in the read view (Firefox and
  Chromium, the read view only: Edit mode has no Movie section, so the scenario "Play on the event's movie in the last
  second" was run with a foreign `<video>` and the bin's preview player).
- **`event-timeline`, modified:** a scrub shows the right frame; the grip is dragged; a scrub across a boundary (never
  more than one slot with a `src`, no standby event); "The proxy is gone" (a 404 problem body for the second clip: "The
  proxy of s1710002.mp4 is no longer there.", the Prepare button, four clips on the track, the third clip plays); a clip
  press does not move the playhead; a clip drag does not scrub; a double press places the playhead; a finger swipe on a
  clip scrolls (Chromium only: Playwright's Firefox has no touch emulation); a preview releases the Timeline's video and
  scrubbing closes the preview; the turn follows the clip.
- **Not run in Playwright:** "The clips shrink under the playhead" (Edit mode re-reads only the render verdict, so no
  quiet re-read of the clips could be triggered from the page); the finger swipe in Firefox; the scrub, readout, step
  and card measurements in the headless runs (they are in the headed table above).

**Two scenarios fail in both browsers.** (1) "A plain boundary", its first-frame clause: the incoming clip's first reported frame is at 0.06 to 0.1 s (`pw/out31/ffF.txt`: `first_mt` 0.1, `ok` true because the check does not test the clause), and the gate's skips are up to 53 / 56.6 ms. Design D4's "What is accepted" (about 28 ms, Firefox only, IN = 0) is contradicted: about 30 ms median and up to 57 ms in Chrome, with IN = 0 the common case. The spec clause or the design must change (operator decision). (2) **"Pause during the lead", its last clause.** A pause just after the standby started
leaves the Timeline paused on `s1710001.mp4` at 5.97 s, the standby paused at its pre-sought position (0.005 s), no frame of
`s1710002.mp4` shown. Pressing Play then does **not** cross the boundary through the standby: the playhead is within
`END_SLACK_MS` of the clip's end, so `play()` takes `startFrom`'s next-clip start (`follow.ts`), `moveVideo` loads the
next clip into the shown slot, and the standby is re-targeted. The result is the accepted "move of the playhead" flash
(2 to 3 blank video samples at the load, 0 at the swap of the next boundary), not a seamless boundary. This is the
existing Play-from-the-end rule colliding with the scenario's wording, not a regression in the hand-over. Either the
scenario's last clause becomes "Play then goes on into the next clip's first kept frame", or `play()` hands over to a
ready standby when `startFrom` leaves the clip.

#### What this run could not verify

- The gate on the operator's real audio device (a null sink has no hardware clock); the audible overlap in the lead
  (nothing reached a speaker, by rule, and the null sink's monitor was not captured).
- **"The clips shrink under the playhead" is unverified**, and a headed gate with IN > 0 (leading cuts) was not run, so P above 0 was never measured headed.
- The event of the readout scenario (9.00 / 40.00 / 6.02 s) and the Chrome and Firefox versions named (Chrome 158, which satisfies the spec floor of 157, and Firefox
  160 ran).
- Display refresh other than 60 Hz; other proxies than the four 6.02 s, 50 fps ones; a clip entered at IN > 0 in the gate
  (P is learned only there; its functional runs above are not gate runs).
- The 100 ms standby start window as a screenshot, and "The clips shrink under the playhead".
- Instrumentation cost: both slots carry a frame callback, a rAF sampler and a 100 ms readout timer in these runs (the
  same hook for the built and the single-element runs).
- Raw results: `gate/results/gate-firefox-ff1.json`, `gate-chrome-ch1.json`, `scrub-*`, `step-*`, `card-*`, `readout-*`,
  `sinkinputs.log`; functional output `pw/out31/ffF.txt`, `chF.txt` (session scratchpad, not in the repo).

### 6.10 Fixed swap (task 3.1 re-measured, 2026-11-23)

The fix is `b9240998` (the standby is swapped in the decision's task, and the decision is made just before the kept
end) plus `097c0deb` (Play within the end slack hands over to the standby). Everything here ran on `097c0deb`, the head
of `feat/seamless-playback`, headed, on the host's display, Firefox 160.0.1 first and then Chrome 158.0.8127.36.
**The boundary gate of D7 still fails in Firefox (the primary browser) on both events, and in Chrome on the
leading-cut event. It passes in Chrome on the IN = 0 event.** Nothing was tuned after the first headed run and no
definition was changed. The hold fell sharply on IN = 0 (Firefox p50 117 to 51 ms, Chrome p50 83 to 33 ms), and the new
failure is the leading-cut case, where the pre-roll path (P above 0) now carries the hold.

#### Setup, as §6.9 unless stated

- **Service and library.** No event of the dev library (`auto-reel-dev/library`) has leading cuts at plain boundaries
  (the one trimmed clip, in `2024-08-20 - Två kapitel - Tjörn`, is a trailing cut after a chapter card). A scratch
  library was built in the session scratchpad (`lib/2024/`), served read-only by `auto-reel serve` on port 8102 from the
  main checkout's venv, and stopped at the end. It holds two events over the same four 6.02 s, 50 fps clips (symlinks to
  `auto-reel-dev/clips`, the clips §6.9 used, not the 348 MB originals of `auto-reel-media`, which was not touched; the
  proxies came from the shared proxy cache, nothing was re-encoded):
  - **IN = 0:** `2024-06-27 - Grillning med grannar`, the event of §6.9.
  - **Leading cut:** `2024-06-28 - Ledande klipp`, `reel.yaml` with `trims: [{in: 0.0, out: 0.5}]` on clips 2 to 4, so
    each of the three plain boundaries enters its clip at IN = 0.5 s. Clip 1 is uncut.
- **Builds.** The built app is this branch's Vite (podman, port 5174, `sp-vite`). The single element is `web/` of
  `d11e2345` (podman, 5175, `sp-vite-base`), the same service, the same hook. Both containers were removed.
- **Browsers and sound.** Flatpak Firefox and Chrome, fresh profiles, `PULSE_SINK=claude_null` on a PipeWire null sink
  (`module-null-sink`, module 536870916), **sound on**. The watchdog logged every sink input (352 snapshots); of the 313
  stream entries of my instances, 309 are on `claude_null` and 4 are an unrouted, corked Firefox stream (sink `?`, as in
  §6.9). `ABORT.txt` was never written. The default sink (the operator's headset) was never changed. The module was
  unloaded at the end: `pactl list short sinks` no longer lists `claude_null`, and the default sink is still the
  headset. My browsers were stopped by process id.
- **Visibility.** KWin keep-above loop as in §6.9. `visibilityState` was sampled every 2 s in each of the 96 loops:
  0 `hidden` samples, `hasFocus()` true at the end of each.
- **Script and plan.** Unchanged: 0:04 of `s1710001.mp4`, Play, 22 s, three plain boundaries per loop, a fresh tab per
  block, writes refused in the page.
  - IN = 0 event: `built` 12 loops, `single` 8, `built` 12 per browser (72 built and 24 single boundaries).
  - Leading-cut event: `built` 6, `single` 4, `built` 6 per browser (36 built and 12 single boundaries).
- **Definitions.** D7's, as in §6.9. For the leading-cut event "lost" subtracts the kept span the clocks should have
  advanced, `6020 - IN * 1000` ms, in place of 6020 ms (the incoming clock starts at IN), and the filter on the first
  frame's media time is IN + 0.6 s in place of 0.6 s. Same percentiles, same limits (hold limit = median steady + 20 ms).
  The hand-over record is now matched up to 60 ms after the first incoming frame, since the swap runs in the decision's
  task; the 12 hand-overs of the first analysis that showed `None` were swaps logged just after that frame, and all 216
  built hand-overs are `timer`.

#### The boundary gate, IN = 0 event

ms. "valid" = steady play kept its cadence.

Firefox 160.0.1:

| Case | n (valid / all) | Lost p10 / p50 / p90 | Hold p50 / p90 / max | Steady median | Hold limit | Max skip |
|---|---|---|---|---|---|---|
| **built** (valid) | 71 / 72 | -41.5 / -12.0 / 7.0 | 51.0 / 83.0 / 134.0 | 50.0 | 70 | 56.0 |
| built (all) | 72 | -41.4 / -12.2 / 6.7 | 51.0 / 83.0 / 134.0 | 50.0 | 70 | 56.0 |
| single element (valid) | 8 / 24 | 222.2 / 264.0 / 275.1 | 242.0 / 255.5 / 266.0 | 50.0 | 70 | 0 |
| single element (all) | 24 | 217.3 / 238.8 / 269.4 | 58.5 / 250.0 / 266.0 | 183.0 | 203 | 0 |

Chrome 158.0.8127.36:

| Case | n (valid / all) | Lost p10 / p50 / p90 | Hold p50 / p90 / max | Steady median | Hold limit | Max skip |
|---|---|---|---|---|---|---|
| **built** (valid) | 72 / 72 | -39.4 / -31.0 / -14.6 | 33.5 / 50.1 / 66.7 | 33.5 | 54 | 59.5 |
| single element (valid) | 10 / 24 | 127.4 / 130.6 / 141.3 | 83.4 / 83.4 / 83.5 | 50.0 | 70 | 0 |
| single element (all) | 24 | 128.3 / 138.1 / 152.9 | 83.4 / 83.5 / 100.0 | 66.7 | 87 | 0 |

The single element's steady play is irregular in both browsers (8 and 10 valid boundaries of 24), so its rows rest on
those; they only tell that the old hand-over still loses 130 to 260 ms and holds 83 to 266 ms.

**Verdict, IN = 0 event** (valid boundaries):

| Term | Firefox built | Chrome built |
|---|---|---|
| p90 lost at most 20 ms | 7.0: yes | -14.6: yes |
| p10 lost at least -40 ms | -41.5: **no** (by 1.5 ms; -41.4 over all 72) | -39.4: yes |
| p90 hold at most steady + 20 | 83.0 against 70: **no** | 50.1 against 54: yes |
| no hold over 100 ms | max 134.0: **no** (1 of 72 over 100; 6 over 83) | max 66.7: yes |
| no skip over 60 ms | 56.0: yes | 59.5: yes (0.5 ms under) |
| **Gate** | **FAILS** | **PASSES** |

Against §6.9 (built before the fix): Firefox hold p50 / p90 / max 117 / 133 / 150 became 51 / 83 / 134, p10 lost -40.6
became -41.5, p90 lost 7.2 became 7.0. Chrome hold p50 / p90 / max 83 / 117 / 133 became 33.5 / 50.1 / 66.7, p10 lost
-40.0 became -39.4. The hold tail is the thing that moved; the lost floor did not (the skipped start is the same, see
below).

#### The boundary gate, leading-cut event (IN = 0.5 s, P exercised)

Firefox 160.0.1:

| Case | n (valid / all) | Lost p10 / p50 / p90 | Hold p50 / p90 / max | Steady median | Hold limit | Max skip |
|---|---|---|---|---|---|---|
| **built** (valid) | 35 / 36 | -33.0 / 3.0 / 29.8 | 84.0 / 117.0 / 134.0 | 50.0 | 70 | 40.0 |
| built (all) | 36 | -33.0 / 1.5 / 29.8 | 84.0 / 117.0 / 134.0 | 50.0 | 70 | 40.0 |
| single element (valid) | 7 / 12 | 178.5 / 191.0 / 237.2 | 183.0 / 226.8 / 267.0 | 50.0 | 70 | 0 |
| single element (all) | 12 | 179.6 / 209.5 / 280.2 | 183.0 / 215.3 / 267.0 | 51.0 | 71 | 0 |

Chrome 158.0.8127.36:

| Case | n (valid / all) | Lost p10 / p50 / p90 | Hold p50 / p90 / max | Steady median | Hold limit | Max skip |
|---|---|---|---|---|---|---|
| **built** (valid) | 36 / 36 | -19.2 / -2.7 / 20.5 | 66.7 / 83.5 / 116.7 | 33.5 | 54 | 39.3 |
| single element (all) | 12 | 127.2 / 137.4 / 153.8 | 83.4 / 83.5 / 100.1 | 66.7 | 87 | 0 |

(The single element had 1 valid boundary of 12 in Chrome, so only its "all" row is shown.)

**Verdict, leading-cut event** (valid boundaries, built):

| Term | Firefox | Chrome |
|---|---|---|
| p90 lost at most 20 ms | 29.8: **no** | 20.5: **no** (by 0.5 ms) |
| p10 lost at least -40 ms | -33.0: yes | -19.2: yes |
| p90 hold at most steady + 20 | 117.0 against 70: **no** | 83.5 against 54: **no** |
| no hold over 100 ms | max 134.0: **no** (9 of 36 over 100 across both blocks) | max 116.7: **no** (3 of 36) |
| no skip over 60 ms | 40.0: yes | 39.3: yes |
| **Gate** | **FAILS** | **FAILS** |

The lost floor is now met (the leading cut has a real pre-roll to align with, so the incoming start is no longer
skipped), but the upper side fails: the hand-over now costs time (positive lost) and holds longer.

#### LEAD and P as observed (built, `timer` hand-overs, every one)

| Event | Browser | LEAD median (min to max) | LEAD clamp hits (0 / 250) | P median (min to max) | P clamp (40) hits |
|---|---|---|---|---|---|
| IN = 0 | Firefox 160 | 52 ms (40 to 80) | 0 / 0 | 0 (0 to 0) | 0 |
| IN = 0 | Chrome 158 | 69 ms (40 to 80) | 0 / 0 | 0 (0 to 0) | 0 |
| leading cut | Firefox 160 | 65 ms (40 to 83) | 0 / 0 | 15 ms (0 to 38) | 0 |
| leading cut | Chrome 158 | 71.5 ms (40 to 84) | 0 / 0 | 29.5 ms (0 to 40) | 10 of 36 |

**P is above 0 in Firefox on the leading-cut block**, as the task asked: 32 of 36 hand-overs had P above 0 (median 15, up
to 38 ms), and in Chrome 31 of 36 (median 29.5, 10 at the 40 ms clamp). The first boundary of each block runs with P = 0
(nothing learned yet), which is the 4 and 5 hand-overs with P = 0.

#### Where the hold comes from now (diagnostic, not part of the gate)

On the IN = 0 event the swap is no longer late: the last reported frame of the outgoing to the swap is 39 ms (p50, p10
to p90 29.5 to 48.5) in Firefox, against 59 (43 to 77) in §6.9, and 27 ms (14.6 to 40.9) in Chrome against 34 (24 to
47). The hold is now the display cadence: Firefox reports every other frame, so a 50 ms hold is two reported
intervals, and 6 of 72 Firefox boundaries held more than 83 ms.

On the leading-cut event the hold depends on P:

| Event, browser | Hold, P = 0: n, p10 / p50 / p90 | Hold, P above 0: n, p10 / p50 / p90 | Lost, P above 0, p10 / p50 / p90 |
|---|---|---|---|
| leading cut, Firefox | 4: 50.0 / 50.0 / 73.8 | 32: 51.0 / 84.0 / 117.0 | -33.0 / 4.0 / 30.0 |
| leading cut, Chrome | 5: 40.1 / 50.1 / 76.8 | 31: 49.9 / 66.7 / 83.5 | -19.2 / -2.6 / 20.7 |

So with P = 0 the hold is the same 50 ms as on the IN = 0 event, and the extra hold and the positive lost come with the
pre-roll (the learned P). The hold of the incoming clip also grows with the boundary's position in the loop (Firefox
median, incoming clip 2, 3, 4: 50 to 75, 84 to 92, 100 to 117 ms across the two blocks), which is when P has been learned
and is largest. This is a reading of the numbers; the code path that carries P was not instrumented in this run and
nothing was changed to test it. What it points at is the pre-roll hand-over, not the swap timing.

#### Per-term verdict, both events, both browsers

| Gate term | Firefox IN = 0 | Firefox cut | Chrome IN = 0 | Chrome cut |
|---|---|---|---|---|
| p90 lost at most 20 | yes (7.0) | no (29.8) | yes (-14.6) | no (20.5) |
| p10 lost at least -40 | no (-41.5) | yes (-33.0) | yes (-39.4) | yes (-19.2) |
| p90 hold at most steady + 20 | no (83 / 70) | no (117 / 70) | yes (50.1 / 54) | no (83.5 / 54) |
| no hold over 100 | no (134) | no (134) | yes (66.7) | no (116.7) |
| no skip over 60 | yes (56.0) | yes (40.0) | yes (59.5) | yes (39.3) |
| Gate | fails | fails | passes | fails |

#### Functional scenarios re-run (Playwright, headless, muted, writes intercepted, HEAD)

Firefox 159 and Chromium, on the IN = 0 event.

- **"A plain boundary", first-frame clause: still not met in the strict reading.** The incoming clip's first reported
  frame is at media time 0.06 s (Firefox 159) and 0.04 s (Chromium), so 2 to 3 frames are skipped before the first one
  reported. In the headed gate, over 72 IN = 0 boundaries: Firefox's first reported frame is at or before 0.02 s in 21,
  at or before 0.04 s in 55, and after 0.06 s in 3 (max 0.10); Chrome at or before 0.02 s in 15, at or before 0.04 s in
  64, after 0.06 s in 2 (max 0.08). Neither browser reports every frame (§6.5), so a first reported frame at 0.02 to
  0.04 s may be frame 0 or 1 reported late; the data cannot tell. The skipped start shows as the lost floor of the
  table (Firefox p10 -41.5, Chrome p10 -39.4). Blank samples 0, proxy requested before the clip ended and not at the
  swap, readout in the next clip: all fine. The check's own threshold (0.12 s) still passes; the clause is therefore
  still open for the operator (design D4's "What is accepted" is closer to the data now, about 12 to 31 ms median
  skip, but the spec wording "its first frame" is not strictly true).
- **"Pause during the lead": passes in both, including the last clause.** After the pause the shown slot is paused at
  5.97 s (Firefox) and 5.96 s (Chromium), the standby paused at 0.005 s on `s1710002.mp4`, no frame of it shown. Play
  then hands over through the standby (`handover play`, first frame at 0.06 s, max gap 50.2 ms in Firefox and 33.4 ms
  in Chromium, 0 blank samples).
- **"The clips shrink under the playhead": triggered through a draft edit, not through the quiet re-read.** In Edit
  mode the page re-reads only the render verdict (`refreshVerdict`), so a quiet re-read cannot take a clip away from
  the Timeline, and none could be forced from the page. The same layout path was reached by selecting the clip under
  the playhead (`s1710002.mp4` at 0:02) and pressing "Ignore clip": the Timeline stayed on the page with 3 clips, the
  playhead went to the start (the opening card, "title card for the opening, 0.0 s of 7.0 s", card layer opacity 1.0
  over the first clip's slot), no page error, no refused write beyond the intercepted ones (none). Blank video samples
  (5 in Firefox, 6 in Chromium) were under the opaque card layer. Passes in both browsers for that route; the
  re-read route itself remains **unverified** (a unit-level test of `position.ts` covers a clip that is gone).

#### What this run could not verify

- The operator's real audio device (a null sink has no hardware clock), and the audible overlap in the lead.
- Display refresh other than 60 Hz; other proxies than the four 6.02 s, 50 fps ones; the readout event of the spec.
- Scrub, frame step, card hand-over and readout were not re-run (not touched by the fix; §6.9 holds them).
- The quiet re-read route of "The clips shrink under the playhead".
- Instrumentation cost, as in §6.9 (the same hook for built and single).
- Raw results: `gate/results/gate-firefox-ff-in0.json`, `gate-firefox-ff-lead.json`, `gate-chrome-ch-in0.json`,
  `gate-chrome-ch-lead.json`, `sinkinputs.log` (session scratchpad, not in the repo); the analysis is
  `gate/analyze_gate2.py` and `gate/diag_fixed.py`; the functional runs `pw/f31.py` (`plain`, `pause-in-lead`,
  `clips-shrink`).
