## Context

The Timeline plays through one `<video>`. It is rendered in `timeline/Timeline.tsx` (the `stage`) and driven by
`timeline/useTimelineVideo.ts`. The seek coalescer (`timeline/scrub.ts`) is the only writer of `src` and of a
scrub's `currentTime`. While playing, `arm()` follows the presented frames (`requestVideoFrameCallback`), and
`onFrame` (`timeline/follow.ts`) returns `end` on a clip's last kept frame. `advance()` then calls `nextClip` and
`moveVideo`, and the chain at the boundary is:

| Step | What happens | Measured (headless, loopback) |
|---|---|---|
| End noticed | last presented frame → `src` set (often by `ended`, not by the frame) | 4–53 ms |
| Load | `src =` → `loadedmetadata`, incl. the proxy request (206, or a 304 revalidation in Firefox) | 12–25 ms, of which the request 4–17 ms |
| Seek | always, even to the first frame: the coalescer cleared `shown`, and `seekSeconds(0)` is a quarter frame in | 13–24 ms |
| Start | `play()` → `playing` → `arm()` again | 4–10 ms |

Source: `docs/research/seamless-playback.md`, the read-only probe of 2026-11-18. In that probe, two alternating,
preloaded elements cut the play time lost at a boundary in each browser:

| Browser (headless) | One element | Two elements |
|---|---|---|
| Chromium 153 | 66 ms | 41 ms |
| Firefox 155 | 54 ms | 25 ms |
| Chrome 157 | 146 ms | 127 ms |

The two-element numbers still lose 25 to 127 ms. Headless runs cannot separate the two candidate causes:
- these browsers show a frame only every 80 to 100 ms, even under Xvfb, so the end is noticed late;
- the standby's own start, from `play()` until its clock runs, may wait for the audio sink.

Hardware decode and a real audio device could not be measured headless either. Task 0.2 measures them headed, on the
host's display, before any wiring.

The pattern already exists. `enterCard` loads and seeks the card's anchor clip behind a black card, and
`handOverReady` lets the card go only when that clip is ready. These invariants touch the element count, and each is
handled below:
- the page's one-video rule (`playback/coordinator.ts`: `anotherPlays`, `watchOtherStarts`, `resumeOrYield`);
- the clip preview's `held`;
- `posterFrame.ts` ("the Timeline's one `<video>`");
- the per-clip turn (`applyTurn`, `rotate.css`'s `[data-turned] > [data-turn]`);
- leading cuts (`nextClip` returns the cut's end);
- the scrub and step gates (HLD D-20).

## Decisions

### D1. Two slots, one shown
The stage renders two `<video class="tl-video">` elements, slots A and B. Both are direct children of `.tl-stage`,
so `rotate.css` turns each, and both have `preload="auto"`, `playsInline`, `aria-hidden="true"` and
`tabIndex={-1}`.
- **Which is shown.** The hook holds the index of the shown slot. The other slot carries `data-standby` and, except
  during the lead (D4), the `muted` property. Swapping roles sets these attributes directly, with no React render, as `data-turn` already is.
- **CSS.**
  ```css
  .tl-stage > .tl-video { position: absolute; inset: 0; }                     /* both fill the 16:9 box */
  .tl-stage > .tl-video[data-standby] { opacity: 0; pointer-events: none; }   /* rendered, never seen */
  ```
  The stage keeps its size from `aspect-ratio`, both stacked and in the workspace (`.ws-view .tl-stage`). The card
  layer comes later in the DOM, so it stays on top without a `z-index`.
- **`held`.** While a clip preview holds the page, neither slot is rendered, as today.

### D2. The standby's target and state (`timeline/standby.ts`, pure)
```ts
export type Target = { clip: number; ms: Ms }
/** Where play goes on after `clip` at a plain boundary: `nextClip`'s answer (the first clip with kept footage, at
 *  its first kept frame, so the end of a leading cut). Null at the end of the timeline, and when a black card
 *  opens the next clip's chapter (the card bridge loads it, as today). */
export function standbyTarget(clips: readonly Playable[], gaps: readonly { clip: number }[], clip: number): Target | null

export type Standby =
  | { kind: 'idle' }
  | { kind: 'loading' | 'seeking' | 'ready'; target: Target; address: string }
  | { kind: 'started'; target: Target; address: string; playAt: number }   // the early start has run (the lead)
export type StandbyEvent =
  | 'loadedmetadata' | 'seeked' | 'error' | 'released'
  | 'cancelled'                                  // the lead was cancelled: the hook paused T and re-sought it
  | { type: 'started'; playAt: number }          // `T.play()` was called at `playAt` (performance.now)
export function standbyStep(s: Standby, e: StandbyEvent): Standby
/** At the early start's timer and at the decision on S's last kept frame (and again if it is missed): hand over,
 *  wait for the standby (it holds `want` and is on its way), or load as today. */
export function atBoundary(s: Standby, want: Target, address: string): 'hand-over' | 'wait' | 'load'
```
- **Loading.** `loading` sets `src`, the clip's turn and `muted`. `loadedmetadata` leads to `seeking`, with
  `currentTime = seekSeconds(ms, fps)`. `seeked`, together with `readyState >= 2` and not `seeking`, leads to
  `ready`.
- **Started.** `{type:'started'}` is valid only from `ready` and leads to `started`, which keeps the `play()` time
  (`playAt`), the sample the lead calibrator needs (D4). Any other state ignores it, so a start can never happen on
  a standby that is still seeking.
- **Cancelled.** `cancelled` is valid from `started` and leads to `seeking`, never to `ready`: the hook has paused T
  and set `currentTime` back to its pre-sought position (first kept frame less P), and only that seek's `seeked` (with `readyState >= 2`) leads to
  `ready`. Until then `atBoundary` answers `wait`, so a second Play, or the next arming, cannot hand over to an
  element that is seeking. `cancelled` from any other state is ignored.
- **`atBoundary`.** `hand-over` for `ready` and `started` holding `want` at the same address; `wait` for `loading`
  or `seeking` holding it; `load` for `idle`, an other target or an other address. The early start's timer fires only
  on `ready`; from `started` the decision hands over at once.
- **When it goes back to `idle`.** A load error does, silently and with no retry for that address while the clip
  plays: the fallback load on the shown slot diagnoses it as today. So does a new target, which re-points the slot.
- **Tests.** `standby.test.ts` covers `standbyTarget` (leading cut, a clip cut whole, a black-card gap, the last
  clip) and every transition, including `started` (from `ready` only, `playAt` kept, ignored elsewhere),
  `cancelled` (to `seeking`, then `seeked` to `ready`, ignored elsewhere), an error and a release while `started`,
  and `atBoundary` on a cancelled standby that is still seeking (`wait`).

### D3. When the standby loads
- **The trigger.** It loads only while the operator's Play holds (`wantPlay`). The target is computed on the shown
  slot's `playing`, and again whenever it may have changed: the clips or the card map change (a draft edit), or a
  seek is made while playing.
- **A changed target** re-points the slot. An unchanged one leaves it as it is.
- **Pause** keeps the standby as it is, so Play again is ready at once. A paused Timeline never starts a load.
- **Release.** Unmounting or `held` releases both slots (`pause()`, `removeAttribute('src')`, `load()`), as the
  cleanup does today for the one.
- **Events.** Each slot's media events go through one handler set bound to the slot. Events of the standby slot go
  to `standbyStep`; those of the shown slot go to today's handlers. A `pause` or `error` of the standby never
  reaches the operator's state.

### D4. The hand-over (early start)
The standby T is sought to the incoming clip's first kept frame, less a learned pre-roll P (0 unless the session
needs it, below), and is started **before** the outgoing slot S ends, so that T's audio start-up and clock are
already running when S's last kept frame has had its time.

- **The calibrator (`timeline/lead.ts`, pure).** It learns two numbers per session from every hand-over:
  - **LEAD**, the play start-up latency: the time from `T.play()` (the `playAt` of D2's `started` state) to T's first
    presented frame. It is the running median of the last 9 hand-overs, clamped to [0, 250] ms, 40 ms before the
    first one.
  - **P**, the pre-roll, learned from the **signed alignment error** of the incoming clip: its position on its own
    frame clock (callback time minus `mediaTime`, median over its first presented frames) at the swap, against the
    position it should have (the first kept frame plus the real time since the decision). Positive is T ahead (content
    skipped). The error is measured with the P that was applied (`P_used`), so the loop is closed and the sample is the
    **pre-roll that was needed**: `needed = max(0, P_used + error)`, taken for every hand-over where P could be
    applied, **including a negative error** (an overshoot gives a smaller `needed`). P is the running median (last 9)
    of `needed`, clamped to [0, 40] ms (two frames), 0 before the first hand-over, and never more than the incoming
    clip's in-point (IN = 0 has no frames before it, so P is 0 there, and a hand-over with IN = 0 gives no sample).
    Firefox (skip 28 ms at P = 0): the first sample is 28, then aligned hand-overs at P = 28 give `needed` near 28,
    so P stays near 28 and does not fall back to 0; an overshoot (P too large, error negative) lowers `needed` and so P.
  - Both reset (LEAD 40 ms, P 0) on `navigator.mediaDevices` `devicechange`.
  - **Why two numbers.** A single LEAD fed with `play()` to first frame cannot align Firefox. Its clock starts at
    `play()` and its frames arrive late, so P = 0 runs 26 to 30 ms ahead whatever LEAD is (`early-24-0`, `early-20-0`:
    research §6.7). The pre-roll puts the frames the clock skips before the first kept frame. Chrome's error is about
    0, so P stays 0 there (a pre-roll costs it 45 to 136 ms, §6.7).
- **Arming.** The timing helper (`lead.ts`) takes S's frame clock (median of callback time minus `mediaTime` over the
  last second), S's kept end and LEAD, and returns **two** times: `startAt`, S's kept end minus LEAD, and `decideAt`,
  the predicted time of S's last kept frame (the kept end minus one frame interval). The hook sets one timer for
  each, on the frame clock, not on `onFrame`: Firefox reports only every other frame, so a decision on the first
  reported frame can land one frame late and show a frame past the kept end (research §6.7). `onFrame` returning
  `end`, and `ended`, are **backstops** that run the decision if the timer has not. When the start timer fires,
  `atBoundary(standby, want, address)` is asked and only `hand-over` from `ready` starts early; otherwise nothing
  starts, and the boundary falls back to `wait` or `load`.
- **Start.** `resumeOrYield(false, anotherPlays(own, videos))`: when another player plays, the Timeline yields (it
  stops, and nothing starts). Otherwise `T.muted = false`, `T.play()` and the `started` event with `playAt`. T stays
  `data-standby` (opacity 0) and **unmuted** through the lead: muting it during the lead makes it skip 24 to 47 ms of
  the incoming clip (research §6.7), because a muted element has no audio start-up and its clock runs ahead of its
  first frame.
- **Decision (S's last kept frame, at `decideAt`).** Mark S's pause as the hook's own, `S.pause()`,
  `playhead.set(want)`, bind the coalescer to T and `coalescer.sync(want)`. Nothing is in flight then: `arm()`
  checks `!coalescer.busy()` before `onFrame`.
- **Swap.** One frame interval after the decision, and no earlier than T's first presented frame at or past the first
  kept frame, T loses `data-standby`, S gains it and is muted, and the swap listeners run (D6). The calibrator takes
  its LEAD and P samples here. Then S loads `standbyTarget(…, want.clip)`, and `arm()` follows T.
- **Cancel during the lead.** Between the start and the swap, a pause, a scrub, a seek, Previous/Next clip, a yield
  (D5) or an event reload pauses T, sets its `currentTime` back to its pre-sought position (the first kept frame less P), and sends
  `cancelled` (D2). The standby is `seeking` until that seek lands, and `atBoundary` answers `wait` meanwhile. S
  stays shown, and the Timeline goes on as that action says. A cancelled start gives no calibrator sample.
- **`wait`:** S is paused (its own pause) and holds its last frame, and a flag like `handOverWait` is set. The
  standby's `seeked` runs the hand-over: `T.play()` now, **sending `{type:'started', playAt}` as for the early start**
  (valid from `ready`, after `seeked`), so a pause or scrub between that `play()` and the swap sends `cancelled` from
  `started` (to `seeking`, `atBoundary` `wait` until its `seeked`), and the swap on T's first presented frame at or past its
  first kept frame, not one frame after the decision (that has passed, and would show T's still frame for the whole
  play start-up, 66 to 150 ms in Chrome). This path is a fallback and does not have to meet the gate; it must show
  no blank frame and no frame of the wrong clip.
- **`load`:** today's path: `moveVideo(want)` on S.
- **The `ended` backstop** runs the same `advance()`.
- **A black-card gap** keeps `enterCard`, with the anchor loaded into the shown slot during the card.
- **The coalescer's `load`/`seek`** always act on the shown slot, so scrubs, clicks, frame steps, Previous/Next clip
  and cut seeks inside a clip are unchanged.

### D5. One player for the page (`playback/coordinator.ts`)
- **The predicate.** `anotherPlays(self, videos)` and `watchOtherStarts(root, self, onOther)` take
  `own: (video) => boolean`. The hook passes "is one of my two slots".
- **A paused standby counts for nothing.** It never counts as playing. The standby may play for up to LEAD ms while S
  still plays; both slots playing at once is the Timeline's own, so it is not "another".
- **The hand-over is not another start.** Its `play` event is the Timeline's own, so `watchOtherStarts` ignores it.
  The page's capturing listener calls `pauseOthers(T, …)`, which must not pause S during the lead (S is an own
  slot): see the next bullet. When another player plays, the hand-over has already yielded (D4), and a yield during the lead pauses T and
  seeks it back (D4, cancel).
- **One rule, one place: `samePlayer`.** `VideoRoot` gains `samePlayer(a, b)` (in `documentRoot`: both have the same
  closest `[data-player]` ancestor, which the Timeline's stage carries around its two slots). `pauseOthers(started,
  videos, samePlayer?)` skips videos of the started one's player, and `keepOneVideoPlaying` passes it, so T starting
  in the lead leaves S playing while any other video is paused. A video of a different player is paused as before
  (both slots with it). A video with no `[data-player]` ancestor is its own player.
- **Tests.** `coordinator.test.ts` gains: a paused standby is not "another"; both own slots playing during the lead
  is not "another"; the own slot's start does not call `onOther`; a third video does; T starting in the lead leaves S
  playing and pauses a third video; a different player's start pauses both slots.

### D6. The shown slot for its readers
The hook returns `shown(): HTMLVideoElement | null` and `onSwap(listener): () => void` in place of `videoRef`. The
stage gets `slotRefs`.
- **`posterFrame.ts`.** `useFrameReady` listens on the shown slot and listens again on each swap. `snapshotOf` and
  the Use as poster code take `shown()`, and the header comment is updated.
- **The turn.** `applyTurn(slot, clip)` is per slot. The effect that follows a turn change applies to both, each by
  the clip it holds.

### D7. The boundary gate and its measurement
The gate is the one in `event-timeline`, "Play crosses a clip boundary without a pause". Its terms:
- **Hold.** The longest interval between successive frames on screen, from the outgoing clip's last kept frame to
  0.5 s into the incoming one. With two slots, the incoming frames count from the swap.
- **Steady hold.** The same, over the outgoing clip's preceding second. A run counts only when no steady frame is held
  longer than 3 display refresh intervals plus 2 ms (52 ms at 60 Hz).
- **Lost.** Real time from the outgoing clip's last kept frame to 0.5 s later, minus the media time of both clips
  played in that span. It is signed: a negative value is incoming content skipped. Each clip's position is measured on
  the frame clock of its presented frames (`requestVideoFrameCallback` callback time minus `mediaTime`), not from
  `currentTime`, which is stale by up to about 40 ms in Firefox (research §6.7).

The harness is the one in the research note:
- an init script hooks both `.tl-video` slots (`requestVideoFrameCallback`, the `src`, `currentTime` and `play()`
  calls, and the media events);
- writes are refused inside the page, by patching `fetch` and XHR. A Playwright route would turn Chromium's HTTP
  cache off and change the revalidation being measured;
- the browsers run headed on the host display, the page visible throughout;
- sound is **on** in the browser and routed to a null sink (`pactl load-module module-null-sink`, `PULSE_SINK`), which
  accepts the stream but reaches no speaker. The run checks the sink inputs, never changes the default sink and
  unloads the module afterwards. Without an accepting sink Chrome's play start-up is 150 ms instead of 66 ms
  (research §6.6), so a muted or sink-less run would measure the wrong thing.

## Research & Decisions

### Two elements vs cheap mitigations vs one stream (MSE)
**Context**: the operator asked for the proper fix only (2026-11-18).
**Explored** (`docs/research/seamless-playback.md`):
- A. two alternating, preloaded elements (D-20's deferred item);
- B. one element, with the seek to frame 0 skipped, `play()` on `loadedmetadata`, the next proxy warmed, and a
  `max-age` on proxies;
- C. Media Source Extensions over fragmented proxies;
- D. B now, then A.

**Decision**: A, with no part of B shipped on its own.
**Rationale**:
- B still swaps `src`, so the decoder and the audio path are torn down at every boundary. It only shortens a chain
  that A removes.
- C changes the proxy contract. It needs fragmented MP4, a `PROXY_VERSION` bump that re-encodes about 46 GB (D-21),
  and a rewrite of seek, scrub and the frame mapping.
- A works with today's proxies and route, and reuses the card bridge's pattern.

### Hiding the standby: opacity vs stacking vs `display: none`
**Context**: a standby has to decode and present its pre-sought frame, and present its first frame after `play()`,
without being seen.
**Explored**: in the spike, `opacity: 0` and stacking under the shown slot gave the same lost time in Chromium,
Firefox and Chrome (opacity 41 / 25 / 127 ms, stacking 41 / 25 / 127 ms). An element with `display: none` is not
rendered, and Chrome does not present frames for it.
**Decision**: `opacity: 0` (D1).
**Rationale**: under stacking, a turned shown clip (a quarter turn is narrower than the stage) or a letterboxed one
would let the standby show around it. Opacity needs no `z-index`, so the card layer stays on top.

### The proxy's `Cache-Control`
**Context**: proxies are served `private, no-cache`, so every swap revalidates.
**Explored**: on loopback the request is 4 to 17 ms, including Firefox's 304. The route ignores `v`
(`get_clip_proxy` serves the current file whatever `v` says).
**Decision**: no change.
**Rationale**: the standby makes the request during the previous clip, so its cost is hidden. A `max-age` or
`immutable` on a URL that does not pin the bytes could splice two versions of a rewritten proxy
(`docs/research/browser-playback.md` §8). Leaving the header alone keeps the change web only.

### Which boundaries use the standby
**Decision**: only plain clip-to-clip boundaries, including a video card over the next clip's start. A black card
keeps its bridge, and cuts inside a clip keep their seek.
**Rationale**:
- The card's own length already hides the load, and the bridge's no-gap result is measured.
- A cut's seek is 17 to 41 ms at p90 on these proxies, and handing over there doubles the cases to verify. The
  standby could serve both later, with no change to the specs written here.

### What is accepted at the boundary
**Decision**: the sound stops with the outgoing clip's pause and starts with the incoming clip's `play()`, with no
crossfade. The incoming slot is unmuted just before `play()`, after the operator's Play gesture, so autoplay rules
allow it.
**Rationale**: the movie's own joins are hard cuts too (stream-copy concat), so the preview matches the render.

### Start the standby at the boundary, or before it
**Context**: the headed measurements (`docs/research/seamless-playback.md` §6.3 to §6.7, 2026-11-23). The operator's
primary browser is **Firefox**; Chrome must still work.
**Explored**:
- A. Plain at-boundary hand-over: `T.play()` on S's last kept frame, swap on T's first frame.
- B. Early start: `T.play()` about LEAD before S's kept end, T unmuted, sought exactly to its first kept frame (P = 0).
- C. Early start with T muted until the swap, or with a fixed pre-roll equal to the lead.
- B+. Early start with a calibrated pre-roll: P learned from the signed alignment error (D4), 0 where the browser
  needs none.

**Decision**: B+ (B with P learned). A and C are rejected. **Firefox P = 0 has no measured pass, so B alone is not
adopted; this amendment, with its P calibration, is for the operator to confirm before task 1.1.**
**Rationale**:
- A fails the gate in both browsers. Headed, p90 lost of the two-element swap is 21 ms in Firefox 160 (frame clock;
  hold p90 117 ms against 86 ms allowed), 84 to 106 ms in Chrome with a null sink and 167 to 215 ms in Chrome with no
  sink (§6.3, §6.6, §6.7). Task 0.2's STOP condition 1 held for the plain design.
- The evidence for early start, per browser (§6.7):
  - **Chrome passes with P = 0**: null sink `early-66-0` (p90 lost -10 ms, hold p90 66 ms against 70), no sink
    `early-150-0` (-12 ms, hold 66 ms).
  - **Firefox with P = 0 does not pass**: `early-24-0` and `early-20-0` run 26 to 30 ms ahead (frame-clock p90 -28 and
    -26 ms), i.e. the first 28 ms of the incoming clip is skipped at every boundary.
  - **Firefox passes only with P = 20, L = 20** (`early-20-20`: -5 ms, hold p90 52 ms against 60). That is one frame
    of pre-roll, so it is a point of B+, not of B. It sits at Firefox's 40 ms frame-report resolution, so it is the
    least certain result, and it is why both numbers are measured per session.
- **Firefox's convergence point has no measured pass.** With P learned, Firefox settles near LEAD about 24 ms and P
  about 20 to 28 ms. That is `early-24-24`, and `early-40-40` is the same family: both aligned but **failed hold**
  (`early-24-24` p90 74.6 ms, max 85.6 ms against the 60 ms gate). The only Firefox pass, `early-20-20`, has `play()`
  on the last kept frame (L = one frame interval, not LEAD). So B+ as written (`startAt` = kept end minus LEAD) is
  **not measured to pass in Firefox**; task 3.1 decides it. **Two options for the operator before task 1.1:**
  (a) in Firefox, when P > 0, set `startAt` to `decideAt` (the `early-20-20` recipe: L = one frame, T starts on S's
  last kept frame), chosen by the calibrator: it uses L = one frame interval whenever P > 0 and LEAD otherwise, so
  Chrome (P = 0) keeps the measured `early-66-0`; (b) ship B+ as written and let 3.1 decide, with (a) as the fallback
  if hold fails.
- **Why a calibrated P and not LEAD alone.** LEAD is `play()` to first presented frame (about 24 ms in Firefox).
  Feeding that back as LEAD reproduces `early-24-0`, which §6.7 marks "no (28 ms ahead)": Firefox starts its clock at
  `play()` and presents frames late, so the error is not the latency. Calibrating on the alignment error, with P as
  the second number, moves Firefox's alignment from -28 ms to about 0; it does not by itself pass the hold gate there (see above).
- **What is accepted.** The gate's floor is -40 ms (D7). Where P cannot be applied (the incoming clip's first kept
  frame is its frame 0, so IN = 0, or P has not converged on the first hand-overs), up to about 28 ms of the incoming
  clip is skipped in Firefox, within the floor and silent. This is a known limit, and 3.1 records it per browser
  from the real hand-overs.
- C is worse. A fixed pre-roll of the lead's length only moves the first kept frame later (Chrome 45 to 136 ms lost,
  holds 180 to 283 ms). Muting T until the swap skips 24 to 47 ms of the incoming clip, because the audio start-up is
  the cost being hidden.
- The lead and pre-roll depend on the machine, the browser and the audio device. A running median of the real
  hand-overs, reset on `devicechange`, replaces constants. Task 3.1 re-measures this on the built code.
- The audio overlap (both slots playing during the lead) was not checked by ear or recording, and the extra
  pre-build check against a real sink was **skipped by the operator's choice** (2026-11-23). The overlap should be
  near zero when LEAD matches the latency and about LEAD minus latency otherwise.


## Risks / Trade-offs

- **[Risk] The headed numbers differ from the headless spike.** Hardware decode and an audio sink make `play()` on a
  pre-sought element slow; Chrome waits for the audio sink before it renders.
  → Task 0.2 measured it headed. The plain hand-over missed the gate, so the early start (D4) replaced it, with a lead
  measured per session.
- **[Risk] The audio overlap and the real device.** During the lead both slots are unmuted and playing. The null sink
  has no hardware clock, and no check was made against a real sink (skipped by the operator's choice, 2026-11-23). A
  Bluetooth sink has a larger start-up latency than the clamp's 250 ms may cover, and a wrong lead means a short
  skip or a short stall at the boundary, or an audible overlap.
  → LEAD is calibrated at every hand-over and reset on `devicechange`; 3.1 records its observed values.
- **[Risk] The end is noticed late.** `onFrame` acts only on a presented frame, and Firefox reports every other
  one. The probe saw the end noticed by `ended`, 30 to 53 ms after the last frame in Chromium.
  → The decision is timed on the frame clock (D4), with `onFrame` and `ended` as backstops. Task 2.2 records how
  often a backstop is what fires.
- **[Risk] A second decoder is kept while playing**, with a third while the card bridge or a preview acts. Two 540p
  H.264 decoders are small. The standby exists only while playing, and `held` releases both.
- **[Trade-off] A short next clip** (less play than its load) or a slow proxy falls back to `wait`, or to today's
  load. It is never slower than today.
- **[Risk] Layout.** Both slots are now positioned absolutely. 2.1 takes screenshots of the stacked page and of the
  workspace, at 390, 1280 and 1440 px, light and dark, with turned clips.
- **[Risk] Gates.** The scrub (median ≥ 30 fps), the frame step (p90 ≤ 60 ms), the card hand-over (no gap) and the
  readout across a clip's end are re-measured in 3.1. Only the shown slot seeks, so no change is expected.

## Failure behaviour

Playback only:
- Nothing is written, and no request is made beyond reads of proxies the page already addresses.
- A standby that fails to load is dropped silently. The boundary then loads the clip into the shown slot, which
  reports a failure by cause, as today ("The playhead scrubs one video").
- `NotAllowedError` on the hand-over's `play()` stops the Timeline with today's "not started" note.
- No engine, job or render runs, so re-runs, `--force` and worker restarts do not apply.
