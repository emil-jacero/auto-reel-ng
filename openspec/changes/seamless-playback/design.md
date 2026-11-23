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
- **Which is shown.** The hook holds the index of the shown slot. The other slot carries `data-standby` and the
  `muted` property. Swapping roles sets these attributes directly, with no React render, as `data-turn` already is.
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
export function standbyStep(s: Standby, e: 'loadedmetadata' | 'seeked' | 'error' | 'released'): Standby
/** At the end of the playing clip: hand over, wait for the standby (it holds `want` and is on its way), or load as today. */
export function atBoundary(s: Standby, want: Target, address: string): 'hand-over' | 'wait' | 'load'
```
- **Loading.** `loading` sets `src`, the clip's turn and `muted`. `loadedmetadata` leads to `seeking`, with
  `currentTime = seekSeconds(ms, fps)`. `seeked`, together with `readyState >= 2` and not `seeking`, leads to
  `ready`.
- **When it goes back to `idle`.** A load error does, silently and with no retry for that address while the clip
  plays: the fallback load on the shown slot diagnoses it as today. So does a new target, which re-points the slot.
- **Tests.** `standby.test.ts` covers `standbyTarget` (leading cut, a clip cut whole, a black-card gap, the last
  clip) and every transition.

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

### D4. The hand-over
When `onFrame` gives `end` on the shown slot S, `advance()` asks `atBoundary(standby, want, address)`:
- **`hand-over`:**
  1. Check `resumeOrYield(false, anotherPlays(own, videos))`. When another player plays, the Timeline yields: it
     stops, and nothing starts.
  2. Otherwise:
     - set `T.muted = false`;
     - mark S's pause as the hook's own, and call `S.pause()`, so S's last frame stays on screen;
     - call `T.play()`, then `playhead.set(want)`;
     - bind the coalescer to T and call `coalescer.sync(want)`. Nothing is in flight then: `arm()` checks
       `!coalescer.busy()` before `onFrame`.
  3. On T's first presented frame (`requestVideoFrameCallback`), swap: T loses `data-standby` and S gains it, S is
     muted, and the swap listeners run (D6). Then S loads `standbyTarget(…, want.clip)`. `arm()` follows T from its
     `playing`, as today.
- **`wait`:** S is paused (its own pause) and holds its last frame, and a flag like `handOverWait` is set. The
  standby's `seeked` runs the hand-over.
- **`load`:** today's path: `moveVideo(want)` on S.
- **The `ended` backstop** runs the same `advance()`.
- **A black-card gap** keeps `enterCard`, with the anchor loaded into the shown slot during the card.
- **The coalescer's `load`/`seek`** always act on the shown slot, so scrubs, clicks, frame steps, Previous/Next clip
  and cut seeks inside a clip are unchanged.

### D5. One player for the page (`playback/coordinator.ts`)
- **The predicate.** `anotherPlays(self, videos)` and `watchOtherStarts(root, self, onOther)` take
  `own: (video) => boolean`. The hook passes "is one of my two slots".
- **The standby counts for nothing.** It is paused until it takes over, so it never counts as playing.
- **The hand-over is not another start.** Its `play` event is the Timeline's own, so `watchOtherStarts` ignores it.
  The page's capturing listener may call `pauseOthers(T, …)`, but S is already paused. When another player plays,
  the hand-over has already yielded (D4).
- **`keepOneVideoPlaying` is unchanged.**
- **Tests.** `coordinator.test.ts` gains: a paused standby is not "another"; the own slot's start does not call
  `onOther`; a third video does.

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
- **Steady hold.** The same, over the outgoing clip's preceding second. A run counts only when the steady hold is at
  most two frame intervals.
- **Lost.** Measured 0.5 s after the hand-over decision: real time since the decision, minus the outgoing clip's
  unplayed media time, minus the incoming clip's media time played. It does not depend on presentation cadence.

The harness is the one in the research note:
- an init script hooks both `.tl-video` slots (`requestVideoFrameCallback`, the `src`, `currentTime` and `play()`
  calls, and the media events);
- writes are refused inside the page, by patching `fetch` and XHR. A Playwright route would turn Chromium's HTTP
  cache off and change the revalidation being measured;
- the browsers run headed, under Xvfb or on the host display;
- sound is muted in the browser (`--mute-audio`, with no audio device passed to a container) and never reaches the
  operator's speakers.

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

## Risks / Trade-offs

- **[Risk] The headed numbers differ from the headless spike.** Hardware decode and an audio sink could make
  `play()` on a pre-sought element slow; Chrome waits for the audio sink before it renders.
  → Task 0.2 measures the spike headed in Chrome and Firefox before any wiring, and stops the change when the
  two-element hand-over misses the gate.
- **[Risk] The end is noticed late.** `onFrame` acts only on a presented frame. The probe saw the end noticed by
  `ended`, 30 to 53 ms after the last frame in Chromium.
  → The hand-over also acts when the presented frame is past the clip's last kept frame. Task 2.2 records how often
  the `ended` backstop is what fires.
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
