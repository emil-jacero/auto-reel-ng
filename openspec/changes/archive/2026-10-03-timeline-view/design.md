## Context

Motivation and scope: `proposal.md`. Requirements: `specs/event-timeline/spec.md`, `specs/web-app/spec.md`.

**What exists on `main` today** (checked 2026-10-03):

- The event page (`web/src/events/EventDetail.tsx`) reads `GET /api/v1/events/{id}` and shows a Movie section
  (`movie/MoviePanel.tsx`, D-15) above `page-content`, whose `ReadyView` holds the chapters. `ReadyView` calls
  `useReadCuts(eventId, event)` (`cuts/ReadCuts.tsx`): one `GET …/reel` after each event read, giving
  identity → `Trim[]` (`{in, out, reason}` in seconds). Edit mode (`edit/EventEditor.tsx`) replaces `ReadyView`;
  the movie section is not shown in it, so Edit mode holds at most one `<video>` (D-16).
- `ClipOut` carries identity, status (`new|missing|active|ignored`), `size`, `mtime`, `duration` (the thumbnail
  sidecar's, possibly null) and `excluded`. It has **no fps, dimensions or rotation**: the events read is probe-free
  (HLD §4.9).
- `preview/playback.ts` is pure: `skipSpans` (cuts as the render joins them, whole ms), `skipAt`, `toEnd`,
  `END_SLACK_MS`. `cuts/times.ts` has `formatTime`, `formatLength`, `reasonWords`, `spanWords`.
- `jobs/store.ts` is the one jobs WebSocket plus single-job reads. `jobs/useJob.ts`'s `useEventJob(eventId, latest)`
  indexes the store's jobs by `event_dir` through `jobs/kinds.ts` (`isRender`, `newestRenderByEvent`,
  `countRenders`, landed with `job-kind`): the newest **render** per event, and the header counts renders only;
  `RenderControl` and `LiveJobCell` show what `useEventJob` returns. Toasts fire only for jobs that `track()`
  registered. `markEventsChanged()` runs on every job ending.
- `npm test` is `node --test --experimental-strip-types "src/**/*.test.ts"` over pure modules, type-checked by
  `tsconfig.test.json`. There is no component test runner and none is added (web-app: "The type-check is the
  frontend's gate"; D-8). Components are verified in real browsers (task 8).

**What the gates add** (from `v2-plan.json` and `research/v2/synthesis.md`; names are re-checked in task 1.1):

- `timeline-model` (D-20): `web/src/timeline/model.ts`, pure, moved from `research/v2/timeline-library/proto/src/model.ts`
  (checked on `main`, 2026-10-03): `ClipFacts {durationMs, fps}` and `clipFacts(seconds, fps)`, `layout(clips)` →
  `{startsMs, totalMs}`, `clipAt`, `timeToPx`/`pxToTime`, `View {pps, scrollLeft, width}`, `zoomAt`, `fitPps`,
  `clampPps` with `MIN_PPS` 4, `MAX_PPS` 240, `DEFAULT_PPS` 40, `tickStepMs`, `visibleClips(layout, view, overscanPx)`
  and `visibleTicks`, `cutSpans`, `cutRects`, `movieLengthMs`; plus trim limits and snapping, which this change does
  not use (read-only). Every time is whole milliseconds; a duration or rate that is not above zero is refused
  (`ModelError`), never defaulted.
- `proxy-state-read`: each event-detail clip gains `proxy?: ProxyOut | null` (`null`/absent = unknown) with
  `state: absent|ready|stale|failed`, `version` (the proxy file's entity-tag without quotes, ready only: the `v`),
  `reason` (failed only) and `facts: ProxyFactsOut` (`duration` seconds = the **source's** probed duration,
  `fps_num`/`fps_den`, `vfr`, `width`, `height`, `rotation`, `audio_codec`, and `filmstrip {tile_width, tile_height,
  columns, tiles, interval}`). Read by `stat` and JSON only.
- `proxy-media-endpoints`: `GET /api/v1/events/{id}/proxy?clip=&v=` and `…/filmstrip?clip=&v=` through
  `media_response` (Range, If-Range, ETag, HEAD); an absent entry is a problem body (404), never a 200.
- `proxy-enqueue-endpoint`: `POST /api/v1/events/{id}/proxies` with the jobs' 201 / 200-fresh / 409 semantics;
  `kind` (`render`|`proxy`, required) in `JobOut`, in `JobSummaryOut` and in WS frames. `latest_job` is **always
  the latest render** (the schema says so), so R1 does not arise.
- `clip-preview-proxy` (merged): `api/clipMedia.ts` already builds `proxyUrl(eventId, clip, version)` (event id
  encoded per segment, `clip` and `v` as query) and `probeProxy`; `preview/source.ts` has `previewSource`,
  `copyLengthMs` and `copyHasSound`. This change reuses them; it adds only the filmstrip address.
- Proxy contract (D-21, from `proxy-encode`): MP4 +faststart, H.264 High yuv420p, SAR and rotation applied, short
  side 540, `-bf 0`, GOP `round(fps)`, AAC-LC 128k, `-fps_mode passthrough` (proxy time = source time). Filmstrip
  sprite (`filmstrip-sprites`): 1 fps, 160x90 tiles, 10 columns, at most 120 tiles, JPEG.

## Goals / Non-Goals

**Goals**

- A read-only one-track timeline on the event page that meets the research's scrub gate (median scrub >= 30 fps,
  frame-step p90 <= 60 ms) in Chrome 154 and Firefox >= 155 on the shipped proxy shape.
- A Prepare state that is the only way the page starts a proxy job, with live progress.
- A render region, list rows and header that never show a proxy job as a render.
- Every structure that `timeline-trim` and `timeline-overlays` need to hang handles and lanes on: clip blocks that
  know their start and `pps`, a playhead store, a single video controller.

**Non-goals** (beyond the proposal's): any editing state, any `localStorage`; seamless boundaries; changing the
proxy shape if the gate numbers fail (that is a `PROXY_VERSION` bump in `proxy-encode`; this change would report
the numbers and stop).

## Research & Decisions

### 1. Entry: a Timeline section with its own toggle, not an Edit-mode entry

**Context**: the task leaves it open: "Edit mode entry or its own toggle — decide".
**Explored**: Edit mode owns a draft, `SaveBar`, `requestLeave`/`useSaving` guards and a 2,000-line editor
(`edit/EventEditor.tsx`); `ReadyView` already has `reel` data; the Movie section sits outside the content so a
Refresh keeps it; D-16 limits Edit mode to one video. `timeline-trim` needs the draft.
**Decision**: a "Timeline" section at the top of `ReadyView`'s content, below the Movie section, closed by default,
with an Open/Close button. Edit mode shows none. `timeline-trim` decides how the same `Timeline` component is
mounted in Edit mode (with `cuts` from the draft instead of from `useReadCuts`); this change passes cuts in as a
prop for that reason.
**Rationale**: this slice writes nothing, so it should not sit behind the unsaved-edits machinery, and viewing the
footage is useful without the intent to edit. Inside `ReadyView` it shares the page's one `useReadCuts` read
(no second `GET …/reel`) and is replaced by placeholders on a Refresh like the chapters (closed afterwards: no
persistence, proposal non-goal). A top-level toggle in `page-actions` was rejected: the section needs room for
Prepare, counts and notes, and a toggle far from its section is hard to reach by keyboard.

### 2. Timeline source of truth: proxy facts; cuts from the reel read; no browser lengths

**Context**: D-16 trusts the browser's `video.duration` for a cut check, and says Firefox's runs up to 60 ms
longer. A track laid out from browser durations would shift while it loads.
**Decision**: clip length = `facts.duration` (seconds, from the proxy job's probe, never defaulted). `facts` missing
on a `ready` proxy is "not ready" (spec). Frame step = `1 / facts.fps`; VFR (`facts.vfr`) uses the nominal interval
and the page makes no frame-accuracy claim (the proxy research proved frame-exact seeking on CFR only; cuts are in
milliseconds, D-14, so VFR clips stay correct). Cuts are `useReadCuts`' `Trim[]`, converted to whole ms and joined by
`skipSpans` (reuse, not a second merge). Rotation is already applied in the proxy, so facts' dimensions are the
displayed ones and nothing here rotates anything.
**Rationale**: Principle I: never fabricate a length. One merge rule for the preview, the render and the timeline.

### 3. The pure layer (what `npm test` covers)

New pure modules under `web/src/timeline/`, imports `import type` or pure modules only (the existing
`node --experimental-strip-types` constraint, as `preview/playback.ts` does):

- `layout.ts`: `shownClips(event, cuts)` → `{clips, omitted: {missing, excluded}}` in play order, each with chapter
  index, name (`clipNames` rules), `ClipFacts` (`clipFacts(duration, fps_num / fps_den)`), the filmstrip geometry,
  `version`, cut spans; `readiness(clips)` → counts by state and
  `{open: boolean}`; `chapterBands(clips)` (heading rule: name, else "Main" beside named chapters, else "Clips");
  `movieSeconds(clips)`; `filmTiles(geometry, clipSeconds, pps, window)` → which tiles at which x and sprite
  coordinates; `proxyAddress` / `filmstripAddress` live in `api/proxies.ts` (3 below).
- `scrub.ts`: the **seek coalescer**, a small state machine with injected callbacks (`seek(clip, t)`,
  `load(clip)`): `request(target)` records the latest target; when idle it starts one load/seek; `settled()` (on
  `seeked`/`loadedmetadata`) starts the latest target if it differs. At most one seek in flight, always ends at
  the last target. Tested with a fake clock.
- `keys.ts`: `playheadKey(key, shift, fps)` → `{delta seconds} | {to: 'start'|'end'} | {toggle: 'play'}`; frame
  steps in whole ms so `1.00 - 3/25 = 0.88` exactly (the same reason `playback.ts` works in ms).
- `follow.ts`: from the video's reported `{clip, t}` and the clips' cut spans, the next action while playing
  (`skipAt` reused over the clip's spans) and the boundary rule (end of clip → next clip at t = 0).

Components (`Timeline.tsx`, `Track.tsx`, `Prepare.tsx`, `TimelineSection.tsx`, `useTimelineVideo.ts`) are thin over
these and are exercised in the browser.

### 4. One `<video>`, `src` swap at boundaries, latest-wins seeks

**Context**: the research prototype scrubbed at 60 fps with 6–12 ms seeks, but on 640x360 GOP-12 proxies; the
proxies research measured the shipped shape (540p, `-bf 0`, GOP 1 s) at median scrub 39 fps Chrome / 35 fps Firefox
(132) on a quiet host, 16–23 on a loaded one, step 17–53 ms (`research/v2` X2). The gate is therefore >= 30 fps and
p90 <= 60 ms, not 60.
**Explored**: two preloaded elements (seamless, doubles decoders and doubles the state to keep in step) vs one
element with a swap (measured first frame 15–23 ms for a +faststart proxy, so the flash is small). `fastSeek`
(keyframe-only, Firefox only) was not used: the Timeline must show the exact frame at the playhead.
**Decision**: one element. `useTimelineVideo` owns it: `target = {clipIndex, t}` from a `Playhead` external store
(the prototype's 17-line store: `get`, `set`, `subscribe`, read through `useSyncExternalStore`, so a scrub
re-renders only the readers of the playhead, not the clips). A target in another clip sets `src` to that clip's proxy
address and, on `loadedmetadata`, `currentTime`; a target in the same clip sets `currentTime`. The seek coalescer
(Decision 3) keeps one in flight. The video is `preload="auto"` for the shown clip only, `muted` is NOT set
(Play has sound), `playsInline`, no native controls. While scrubbing the element is paused; the "presented frame"
for the gate is read with `requestVideoFrameCallback` where available (both target browsers have it) and falls back
to `seeked`.
A seek goes a quarter frame into the wanted frame (`seekSeconds`): frame times are whole milliseconds, and at 29.97 fps
frame 1 starts at 33.37 ms but is listed at 33 ms, so seeking to the listed time can show frame 0. The frame callbacks are
cancelled whenever `src` changes or playing stops (`disarm`): Firefox never calls a callback of the old source, so a
chain that kept its handle would never be re-armed. The pointer handlers that scrub from the ruler are also on the
playhead's grip, which sits over the ruler: a drag that starts on it is the first thing a user tries.
**Rationale**: smallest thing that can meet the gate; the boundary flash is an accepted decision (brief).
**If the gate fails**: report the measured numbers and the shape variants tried in the verification notes; the remedy is
`proxy-encode`'s (GOP 0.5 s = 46 fps for +16 % disk; E1 pins the shape), not a different timeline.

### 5. The gate protocol (so the numbers mean the same thing as the research's)

Run from the scratchpad (never in the repo), in `localhost/playback-research:chrome` (Chrome 154) and an image with
Firefox >= 155 (`localhost/pcm-audio-research:pw163` has 155 per the PCM report; **task 8.1 checks
`firefox --version` and stops if it is lower**), against the service on port 8312 with a dev library of symlinked
`auto-reel-media` clips (real Sony 1080p25 PCM, a rotated phone clip, a legacy MPEG-4 one) whose proxies were made by
the real Prepare button and a real worker.

- **Scrub**: a mouse drag over one clip's span on the ruler, 2 s sweep; the clip is zoomed to fill the track, the pointer's x
  follows the clock (not a fixed number of moves), so the page gets a move per frame and the browser coalesces the rest;
  frames counted with `requestVideoFrameCallback` (distinct `mediaTime`s presented) divided by the sweep's duration;
  5 sweeps per clip, the median over all sweeps of all ten sampled clips (one per archive class: Sony 1080p25 and 4K25 PCM,
  1080p50, 4K50 at 119 Mb/s, portrait, two rotated, a 720p MSNV, 1080p25, MPEG-4).
- **Step**: focus the playhead, press Right 40 times 1 s apart; time from `keydown` to the next
  `requestVideoFrameCallback` presenting a frame; the 90th percentile over four sources (Sony 1080p25, 1080p50, 4K50,
  portrait: 160 steps).
- Both are repeated once on an idle host. A host-load note goes with the numbers (the research saw 16 fps on a loaded host).
- Also recorded: first frame after a swap; the DOM clip count at Fit for a generated 400-clip event; the bundle delta.

### 6. Addresses, and the `v` token

**Context**: D-15: Chrome fails to play a replaced file at an address that served the old one; the movie player reads
the entity-tag by a one-byte range request.
**Decision**: the proxy address is `clipMedia.ts`'s `proxyUrl(eventId, clip, version)`; `api/proxies.ts` adds
`filmstripUrl(eventId, clip, version)` for `…/filmstrip?clip=…&v=<token>`, typed against the generated `paths`
(`satisfies keyof paths`, as `clipMedia.ts` does), the id encoded per segment. The token is `proxy.version`, the
entity-tag (no quotes) that `proxy-state-read` publishes with a ready entry; a ready entry without one is not ready
(no first-byte request per clip at open, which would put 25–400 requests in front of the first frame).
**Rationale**: no request before the user opens the timeline; the address changes exactly when the file does.

### 7. Filmstrip drawing and windowing

**Context**: sprite = 1 tile per second, 160x90, 10 columns, <= 120 tiles; prototype measured 112 DOM nodes for 400
clips windowed against 6,889 unwindowed (fps 60 vs 48 at 4x CPU).
**Decision**: the track is one `position: relative` box of `totalSeconds * pps` px inside a horizontal scroller. A
`useVisibleRange` hook keeps `{left, width}` of the scroller in state, updated from `scroll`/`resize` in a
`requestAnimationFrame`. `model.ts`'s windowing returns the clip index range; the margin is one view width each
side. Per visible clip, `filmTiles` yields tiles of height 54 px (width 96 px) each as an absolutely positioned
`<span>` with `background-image: url(<sprite>)`, `background-size` scaled from the sprite's pixel size, and
`background-position` from the tile's column/row; the tile for place `x` is second `floor(x / pps)` (the nearest
second), tiles are dropped, not squeezed, when `pps * 1 s < 96 px`. A clip with `< 1 s` has its one tile. The
sprite URL is on the visible tiles only, so a clip out of the window requests nothing (spec). The ruler's labels are
windowed the same way (a label step chosen so labels are >= 70 px apart, from the prototype). A clip narrower than
6 px draws only its block (no name, no tiles, no cuts) but keeps its group, accessible name and keyboard focus
(roving: the track is one tab stop, arrows move between clips is **not** in this slice; the playhead is the keyboard
control, and clip blocks are reachable by the playhead's position: they carry `tabIndex={-1}`).
**Failure**: a sprite whose first request fails (`<img>` probe via one `Image()` per sprite with `onerror`, started
when the first visible tile of that clip appears) marks the clip "no picture" and raises one note for the Timeline,
not one per clip; the clip stays otherwise whole.

### 8. Prepare, and the jobs-by-kind filter

**Context**: after `job-kind` the unique active index is per (project, event, kind), so a render and a proxy job for one
event can coexist, and the store/WS/reads carry both.
**Decision**:
- `api/proxies.ts#enqueueProxies(eventId)` returns a value per answer, mirroring `enqueueJob`: `enqueued` (201,
  `JobOut`), `ready` (200), `active` (409, with the job id in the body as the render's 409 gives it), `problem`
  (404/502), `database` (503 `check: database`), `unreachable`, `unpublished`. Not abortable (a write).
- The render side exists (`jobs/kinds.ts`, `job-kind`): `useEventJob` shows the newest render, the header counts
  renders. This change adds the proxy side next to it: `kinds.ts` gains `newestProxyByEvent(jobs)` (the same index
  with the kind as a parameter) and `useProxyJob(eventId)` in `useJob.ts` reads it (the store only: `latest_job` is
  always a render, so a proxy job has no read to fall back on; `choose(live, undefined, …)` is the live job or none).
  `store.ts` itself stays kind-blind (it holds all active jobs; snapshot/delta reconciliation is unchanged), and
  `track()` is never called for a proxy job, so it never raises the "Rendered …" toast.
- `latest_job` is always the latest render (`JobSummaryOut`'s definition on `main`), so a Prepare never costs a read
  the last render's outcome. A proxy job that ended before the page was opened is not shown (nothing reads it);
  the clips' states say what is missing.
- Prepare's words: `JobMeter` gains an optional `label` (the `<progress>`'s accessible name, "Render progress" by
  default, "Proxy progress" here) and `JobState` gains a `statusLabel` table for the pill words (`JOB_STATUS_LABEL` is
  render-worded: "Rendering"; `timeline/labels.ts` has `PROXY_STATUS_LABEL`: "Preparing proxies", "Proxies ready",
  "Preparing failed", "Preparing canceled"), a `Record` over `JobStatus` so a new status fails `tsc`. The table sits in
  `timeline/labels.ts`, not `jobs/labels.ts`, because that file imports a component module and `npm test` could not
  load it.
- Completion: when the shown proxy job ends while the page watches it (live or reconciled), Prepare calls the page's
  `onFinished` (the same quiet `reread` the render region uses), whichever way it ended. A failed or canceled job
  leaves the counts as the next read gives them; the button stays. A job that ended before the page opened is not shown. No toast (nothing tracked); status changes go to a `role="status"` region inside the
  section, as the render region does.
- Idempotency: pressing twice sends one request (a ref set in the click handler, like `RenderControl`); a re-read never
  enqueues; a 409 shows the running job; a worker restart mid-job is the `proxy-job` change's requeue and shows as
  the job's `requeue_count`, which `choose` already handles.

**Rationale**: the filter is the smallest change that keeps every existing screen true; touching `store.ts` would
risk the WS lifecycle tests for no gain.

### 9. Play with cut skipping

**Decision**: reuse, do not restate. While playing, `useTimelineVideo` runs the preview's loop: on each presented
frame (`requestVideoFrameCallback`, else `timeupdate`), `skipAt(spans, ms, stepMs, lengthMs)`; `{seek}` sets
`currentTime`, `{stop}` ends the clip, and `ended`/`stop` go on into the next clip at 0 (after its leading cut, if
any: `skipAt` at 0). `lengthMs` = `facts.duration` in ms. At the last clip it pauses with the playhead at the end.
The playhead store is updated from the same callback (not `timeupdate`'s 250 ms).
**Sound**: the proxy's AAC plays everywhere; the original's silent-in-Firefox note does not apply here and is not shown.
The PCM-source clip in Firefox is verified in task 8.1 (decoded peak > 0 through an `AudioContext` analyser).
**Autoplay**: Play is a user gesture; a `NotAllowedError` from `play()` becomes the note "The browser did not
start playing", paused.

### 10. One playing video per page

**Decision**: `playback/exclusive.ts` (pure registry plus two DOM calls): `claimPlayback(el)` pauses the previously
claimed element; both `MoviePanel`'s player and the Timeline's video call it from their `play` event. No shared state
in React. (`Edit mode shows no movie` already keeps D-16's one-video rule there.)
**Alternative rejected**: unmounting the movie player when the Timeline opens — it would lose the operator's place
(and D-15's "A Refresh keeps the player" work).

### 11. Layout, look and motion

- Reuses `tokens.css` (`--dur-fast` is already zeroed under reduced motion), `Alert`, `Pill`, `Icon` (`play`, `pause`,
  `plus`, `x` exist; adds `minus` and `maximize` if missing) and the toolbar patterns of `preview/preview.css`. A
  new `timeline/timeline.css`, imported by `Timeline.tsx`, with tokens only (no raw colors): clip block, filmstrip
  tile, hatch (`repeating-linear-gradient`, `currentColor` stripes on `--surface`) per reason with a visible text
  label for large spans, playhead line (2 px) with a 24 px grip (44 px under `(pointer: coarse)`), chapter band
  sticky label (`position: sticky; left: 0`).
- Scroller: `overflow-x: auto; overscroll-behavior-x: contain; touch-action: pan-x pan-y` on the track body, and
  `touch-action: none` on the ruler (the touch scrub surface), so a swipe on the track pans and does not move the playhead.
- Pointer: `setPointerCapture` on `pointerdown` on the ruler/track (mouse and pen), move events feed the
  coalescer; a tap seeks on `pointerup` for touch on the track body.
- Zoom state: `{pps}` in the section; zoom anchors on the playhead by adjusting `scrollLeft` in the same commit.
- Under `prefers-reduced-motion` the scroller uses `scroll-behavior: auto` and `scrollTo` is called without smooth.

### 12. Accessibility mapping

The region is `<section aria-labelledby>`; the chapter band `<ol>`; each clip a `role="group"` named by the page's
clip name with `aria-description` / `aria-describedby` for "length, N cuts"; each cut span a `<span role="img"
aria-label="Cut 2.0 to 4.0 s, black">`; the playhead `role="slider"` with `aria-valuemin/max/now/text`; toolbar
buttons are real `<button>`s. Controls that do work are never `disabled` while busy (`aria-disabled` +
`aria-busy`, as the page's buttons are, so focus stays). Polite status region inside the section for the playhead
commit, the Prepare job's state changes, and notes. Not measured by the research and not claimed: a real screen
reader's output (task 8.1 uses `aria_snapshot`).

### 13. HLD

D-20 (recorded by `timeline-model`) gets a "First slice" paragraph: read-only, own section, facts-driven layout,
one video, the coalescer, gate numbers as measured (task 8), what stays: trim, overlays, boundary preload, undo.
§4.10 v2 bullet: "timeline view landed (read-only)". §6 phase 9 note. D-15 and D-16 "what stays v2" lines say
scrubbing landed with the Timeline and that the Timeline plays the proxy (sound in Firefox) while the original stays
silent there. No new D-number.

## Risks / Trade-offs

- **[R1] `latest_job` may be the newest of any kind** → resolved at 1.1: it is the latest render by definition.
- **[R2] Scrub fps below the gate on the shipped proxy** (research: 35–39 fps on a quiet host, 16–23 loaded) → measure
  on an idle host, record load; if it fails, the remedy is a `PROXY_VERSION` bump in `proxy-encode` (GOP 0.5 s), reported,
  not hidden by relaxing the gate.
- **[R3] Firefox < 155 in the image** → task 8.1 checks the version and stops; do not claim Firefox numbers from 132.
- **[R4] Wire names differ** (`proxy.state`, `facts.*`, `v`) → resolved at 1.1: the names are in Context above;
  this change follows the generated types.
- **[R5] A first-time event costs 41–78 s per 10 min of footage to prepare** (research risk 9) → the Prepare state
  shows progress and the clip counts; the track is not usable meanwhile (locked: facts come from the job).
- **[R6] Flash at clip boundaries** → accepted (brief); a second preloaded element is `timeline-boundary-preload`.
- **[R7] The clip block's `background-image` cannot report a failed sprite** → the one-`Image()` probe per sprite;
  at most one extra request per visible clip, served from the browser cache for the tiles.
- **[R8] Two `<video>`s on a page (movie + timeline)** → `claimPlayback`; neither loads bytes before it is opened
  or played (`preload="none"` on the movie, no element before Open on the Timeline).
- **[R9] Variable frame rate** → nominal step, no accuracy claim; cuts stay in ms.

## Migration Plan

None. Additive in `web/`; the built `web/dist` is replaced by the normal build. Rollback = revert the commit; no
stored state, no migration, no data format. Existing events without proxies simply show Prepare.

## Open Questions

- Whether the open/closed state and the zoom should survive a Refresh (`localStorage` is for per-viewer
  conveniences only); deferred: it changes no requirement here.
- Whether the Prepare state should offer Cancel for a running proxy job: deferred with `timeline-trim`.
