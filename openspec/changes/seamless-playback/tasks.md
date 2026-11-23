All work is in `web/`, plus the HLD, `docs/editor-workspace.md` and `docs/research/seamless-playback.md`.
- **Node** runs only in podman (`docker.io/library/node:22`), with the repo root mounted and `-w /app/web`. Some web
  tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo.
  - Functional checks intercept PUT, POST and DELETE.
  - Timing runs refuse writes inside the page instead, because a route turns off Chromium's HTTP cache
    (`docs/research/seamless-playback.md` §1).
  - Functional checks mute the browser (`--mute-audio`; no audio socket or `/dev/snd` passed in). Gate timing runs
    have the sound on and routed to a null sink, as `docs/research/seamless-playback.md` §6.6 did, so nothing plays
    through the operator's speakers.

## 0. Gate

- [x] 0.1 Dependency gate: `plain-clip-bin`, the last change of the plain clip bin series, MUST be archived, and so,
  by their own gates, every change before it. Both of these must succeed from the repo root:
  - `ls -d openspec/changes/archive/*-editor-shortcuts openspec/changes/archive/*-clip-context-menu openspec/changes/archive/*-clip-multi-select openspec/changes/archive/*-chapters-in-inspector openspec/changes/archive/*-clip-tab-and-player openspec/changes/archive/*-plain-clip-bin`;
  - `test ! -d openspec/changes/plain-clip-bin`.

  If any check fails, STOP and report which one.

  Then rebase the deltas. Copy the four MODIFIED requirement blocks again, whole, from the then-current
  `openspec/specs/event-timeline` and `openspec/specs/web-app`, and re-apply this change's edits to them.
  `clip-tab-and-player` modifies "Edit mode holds one video at a time" and "The event page plays one video at a
  time" (the bin's player), so do not overwrite its text. Verify with `openspec validate seamless-playback --strict`
  and a diff of each block against its main-spec version, which shows only this change's edits.
- [x] 0.2 Measure first, headed, before any wiring. Run the research note's app probe (§1–2) and spike (§3) on the
  host's display, in Chrome 157 and in Firefox 155 or newer. Use at least 20 boundaries per case. Record in
  `docs/research/seamless-playback.md` §6: steady hold, longest hold, lost play time, and the chain's steps.

  STOP and report if the plain two-element hand-over misses the gate in either browser, or if today's single element
  already meets it.

  Done: measured (§6.1 to §6.7). STOP condition 1 held for the plain design. The operator chose the early-start
  amendment on 2026-11-23 (design D4); the audio-overlap and real-sink check was skipped by choice.

## 1. Rules (web/src/timeline, web/src/playback)

- [x] 1.1 Add `timeline/standby.ts` (design D2): `standbyTarget`, the `Standby` states with `standbyStep`, and
  `atBoundary`; and `timeline/lead.ts` (design D4): a pure calibrator (LEAD and pre-roll P) and the early-start
  timing helper. Verify
  with `standby.test.ts` and `lead.test.ts`. `standby.test.ts` must cover:
  - the target after a plain clip, after a clip with a leading cut (the cut's end), over a clip cut whole, before a
    black-card gap (null), and at the last clip (null);
  - every transition, including an error and a re-target while loading;
  - `lead.test.ts`: the P law is closed-loop (`needed = max(0, P_used + error)`, negative errors included, median of
    9, clamped [0, 40] and to IN). Cases: a fixed Chrome-like series (P stays within about a millisecond of 0); a **closed-loop Firefox simulation**
    where the browser's skip is `28 - P_applied`: P converges to about 28 and stays within one frame of it over 20 or
    more hand-overs; an **overshoot** case (P starts above the need) where P comes back down; IN = 0 gives no sample.
  - the wait path: `started` is sent by the wait path's `play()` too; `cancelled` during it, then `atBoundary`
    answers `wait` until `seeked`.
  - the lead: `started` from `ready` only (and `playAt` kept), `cancelled` to `seeking` and then `ready` on `seeked`,
    both ignored in other states, and `atBoundary` `wait` on a cancelled standby that is still seeking;
  - `hand-over`, `wait` and `load` for a ready, loading or other-target standby.

  `lead.test.ts` must cover:
  - the calibrator: LEAD is 40 ms before any sample, the median of the last 9 (older ones dropped), clamped to
    [0, 250] ms (a negative and a huge sample); P is 0 before any sample, the closed loop of D4
    (needed = max(0, P_used + error), negative errors included; at P_used = 0 a negative error samples 0), clamped to
    [0, 40] ms and to the incoming in-point (0 at IN = 0); the
    reset of both on `devicechange`; a Chrome-like series (errors near 0) keeps P within about a millisecond of 0 (0.5 on the fixed series), a Firefox-like one (about
    +28 ms) raises it;
  - the timing helper: given a frame clock (callback time minus media time, as a median over the last second), S's
    kept end and the lead, it returns both `startAt` and `decideAt`; a start time already past (start at once), a
    lead longer than the time left, and `decideAt` a margin (at most half a frame interval, 6 ms) before the kept end; `shownIsFirstKept` for the swap rule.
- [x] 1.2 Give `anotherPlays` and `watchOtherStarts` in `playback/coordinator.ts` an `own` predicate (design D5).
  Verify with `coordinator.test.ts`, which must check that:
  - a paused second element of the same player is not "another", and neither is a second own element that plays
    while the first plays (the lead);
  - the player's own start does not call `onOther`, and a third video's does;
  - `VideoRoot.samePlayer` and `pauseOthers(started, videos, samePlayer?)`: `keepOneVideoPlaying` leaves a started
    video's own-player videos playing and still pauses any other (D5); the Timeline's stage carries `data-player` (2.1).

## 2. Wiring (web/src/timeline)

- [x] 2.1 Render two slots in the stage (design D1):
  - CSS: both positioned in the 16:9 box, the standby at `opacity: 0`;
  - attributes: `data-player` on the stage around both slots (one player for `samePlayer`), `data-standby` and `muted` on the standby, `aria-hidden` and `tabIndex=-1` on both, a turn per
    slot;
  - `held` renders neither.

  Verify with `npm test` and `npm run check`, then in Playwright:
  - while paused, only one slot has a `src`;
  - screenshots of the stacked page and the workspace at 390, 1280 and 1440 px, light and dark, with an unturned and
    a 90-degree clip, looked at for size, clipping, and the card layer on top.
- [x] 2.2 Preload, start early and hand over in `useTimelineVideo.ts` (design D3, D4):
  - the standby loads while Play holds and is re-targeted on a draft edit or a seek;
  - the early start: arm from the shown slot's frame clock with the two timers of the timing helper (start the
    standby, unmuted, `data-standby`, one lead before the kept end; decide at the predicted last kept frame, with
    `onFrame` and `ended` as backstops), and swap at the decision when the standby already shows the first kept frame (else on its first frame at or past it); seek the standby to the first kept frame
    less P; sample LEAD and P at every hand-over and reset them on `devicechange`;
  - cancel during the lead (pause, scrub, seek, Previous/Next clip, a yield, an event reload): the standby pauses,
    is sought back to its pre-sought position (first kept frame less P), and is `seeking` until that lands (a second Play meanwhile takes `wait`);
    the shown slot stays;
  - `advance()` follows `atBoundary`, with `wait` and `load` as fallbacks;
  - each slot gets its own handlers, and the coalescer is bound to the shown slot;
  - both slots are released on `held` and on unmount.

  Update the hook's header comment. Verify in Playwright (Firefox first, then Chromium; writes intercepted) every
  scenario of "Play crosses a clip boundary without a pause". These include:
  - no proxy request at a plain boundary;
  - a leading cut, and a clip cut whole;
  - a slowed proxy, by delaying one clip's route: the last frame is held and nothing is blank;
  - a reorder during play;
  - a pause, and a scrub, during the lead: the shown clip stays, the standby is paused at or before its first kept frame (back at its pre-sought position), and a
    Play pressed while it is still seeking does not hand over until `seeked`.

  Also log how often the `ended` backstop is what triggers the hand-over.
- [x] 2.3 Make Use as poster and `useFrameReady` read the shown slot through `shown()` and `onSwap` (design D6), and
  update `posterFrame.ts`'s header. Verify in Playwright "Use as poster after a hand-over", and the existing poster
  scenarios of `web-app`.

## 3. Verification and record

- [x] 3.1 Run Playwright in Chromium and Firefox over every scenario of both deltas (`event-timeline`, `web-app`).
  - Carried over from 2.2 (review): run the black-card boundary; force "Play again while the standby is returning" (Play during the standby's `seeking`, e.g. delayed range requests); scrub during the lead in Chromium as well as Firefox; the cancel-after-decision paths (`finishOnSeek`, `wait` -> `started` -> cancel); Firefox with P forced above 20 (seed `calibration`), a 50 fps proxy, a leading cut on the next clip and a delayed proxy (the `seeked` hand-over). Land 2.3 (`shown()` / `onSwap` for poster and frame-ready) before any merge or user-facing build.
  Then re-measure headed on the host's display, and record the numbers in `docs/research/seamless-playback.md` §6:
  - the boundary gate as revised (design D7): at least 20 plain boundaries per browser, Firefox first, with sound on
    and routed to a null sink (`pactl load-module module-null-sink`, `PULSE_SINK`; check the sink inputs, never change
    the default sink, unload the module afterwards), and the same script against the single-element hand-over reported
    beside it; record the lead's observed values (its median, range and clamp hits) per browser;
  - the scrub (median ≥ 30 distinct frames per second);
  - the frame step (p90 ≤ 60 ms over 40 Right presses);
  - the card hand-over (no sampled blank frame);
  - the readout's fixed width across the first clip's end.

  Done 2026-11-23 (the runs and the record), `docs/research/seamless-playback.md` §6.9 and §6.10. **Operator decision
  (2026-11-23): after watching the built branch headed in Firefox the operator judged the boundaries "not that bad
  actually" and stopped optimization. The change ships as measured in §6.10.** Resolution of the open items:
  1. Gate (swap timing, D7): swap fixed (`b9240998`) and re-measured. **Accepted as measured**; the spec now states the
     measured per-browser bounds (IN = 0), a relative clause against the single element, and leading cuts as a known
     limitation. Firefox IN = 0: hold p50 / p90 / max 51 / 83 / 134 ms, p10 lost -41.5; Chrome IN = 0 passes the first
     gate's every term; leading cuts fail it in both browsers. Follow-up: P worsens leading cuts (candidate: drop P).
  2. First-frame clause: **known limitation / follow-up.** The spec allows 5 frames (0.10 s); typical 2 to 3 frames.
  3. "Pause during the lead": fixed (`097c0deb`), passes in Firefox and Chromium. Done.
  4. "The clips shrink under the playhead": **accepted as unverified** (re-read route); layout path verified through
     Ignore clip.
  Also recorded as risks in design.md: Bluetooth and real-sink latency unmeasured, audio overlap during the lead
  unchecked. Scrub, frame step, card hand-over and readout pass; the finger swipe ran in Chromium only.

- [x] 3.2 Record the change (the HLD states the gate as measured and accepted, not the first gate):
  - HLD D-20: an "Amended …, change `seamless-playback`" bullet covering the two slots, the standby rules, plain
    boundaries only, the flash now accepted only for moves of the playhead, and the measured gate. Note on the "What
    stays" list and on the card bridge's "No second `<video>`" that the standby is built and does not cross black
    cards.
  - "`seamless-playback` is built" in §6 item 10.
  - `web/README.md`: the "One video plays at a time" paragraph names the Timeline's two slots as one player.
  - `docs/editor-workspace.md`: the `seamless-playback` row.
- [x] 3.3 Gates: `npm test`, `npm run check` and `npm run build` in podman, recording the bundle delta in the HLD
  bullet; `openspec validate seamless-playback --strict`.
