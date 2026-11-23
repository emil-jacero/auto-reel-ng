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

- [ ] 1.1 Add `timeline/standby.ts` (design D2): `standbyTarget`, the `Standby` states with `standbyStep`, and
  `atBoundary`; and `timeline/lead.ts` (design D4): a pure lead calibrator and the early-start timing helper. Verify
  with `standby.test.ts` and `lead.test.ts`. `standby.test.ts` must cover:
  - the target after a plain clip, after a clip with a leading cut (the cut's end), over a clip cut whole, before a
    black-card gap (null), and at the last clip (null);
  - every transition, including an error and a re-target while loading;
  - `hand-over`, `wait` and `load` for a ready, loading or other-target standby.

  `lead.test.ts` must cover:
  - the calibrator: 40 ms before any sample, the median of the last 9 (older ones dropped), the clamp to [0, 250] ms
    (a negative and a huge sample), and the reset to 40 ms;
  - the timing helper: given a frame clock (callback time minus media time, as a median over the last second), S's
    kept end and the lead, when to start; a start time already past (start at once), and a lead longer than the time
    left.
- [ ] 1.2 Give `anotherPlays` and `watchOtherStarts` in `playback/coordinator.ts` an `own` predicate (design D5).
  Verify with `coordinator.test.ts`, which must check that:
  - a paused second element of the same player is not "another", and neither is a second own element that plays
    while the first plays (the lead);
  - the player's own start does not call `onOther`, and a third video's does;
  - `keepOneVideoPlaying` is unchanged.

## 2. Wiring (web/src/timeline)

- [ ] 2.1 Render two slots in the stage (design D1):
  - CSS: both positioned in the 16:9 box, the standby at `opacity: 0`;
  - attributes: `data-standby` and `muted` on the standby, `aria-hidden` and `tabIndex=-1` on both, a turn per
    slot;
  - `held` renders neither.

  Verify with `npm test` and `npm run check`, then in Playwright:
  - while paused, only one slot has a `src`;
  - screenshots of the stacked page and the workspace at 390, 1280 and 1440 px, light and dark, with an unturned and
    a 90-degree clip, looked at for size, clipping, and the card layer on top.
- [ ] 2.2 Preload, start early and hand over in `useTimelineVideo.ts` (design D3, D4):
  - the standby loads while Play holds and is re-targeted on a draft edit or a seek;
  - the early start: arm from the shown slot's frame clock, start the standby (unmuted, `data-standby`) one lead
    before the kept end, decide on the last kept frame, and swap one frame interval later; measure the lead at every
    hand-over and reset it on `devicechange`;
  - cancel during the lead (pause, scrub, seek, Previous/Next clip, a yield, an event reload): the standby pauses and
    returns to its first kept frame, and the shown slot stays;
  - `advance()` follows `atBoundary`, with `wait` and `load` as fallbacks;
  - each slot gets its own handlers, and the coalescer is bound to the shown slot;
  - both slots are released on `held` and on unmount.

  Update the hook's header comment. Verify in Playwright (Firefox first, then Chromium; writes intercepted) every
  scenario of "Play crosses a clip boundary without a pause". These include:
  - no proxy request at a plain boundary;
  - a leading cut, and a clip cut whole;
  - a slowed proxy, by delaying one clip's route: the last frame is held and nothing is blank;
  - a reorder during play;
  - a pause, and a scrub, during the lead: the shown clip stays, the standby is back at its first kept frame.

  Also log how often the `ended` backstop is what triggers the hand-over.
- [ ] 2.3 Make Use as poster and `useFrameReady` read the shown slot through `shown()` and `onSwap` (design D6), and
  update `posterFrame.ts`'s header. Verify in Playwright "Use as poster after a hand-over", and the existing poster
  scenarios of `web-app`.

## 3. Verification and record

- [ ] 3.1 Run Playwright in Chromium and Firefox over every scenario of both deltas (`event-timeline`, `web-app`).
  Then re-measure headed on the host's display, and record the numbers in `docs/research/seamless-playback.md` §6:
  - the boundary gate as revised (design D7): at least 20 plain boundaries per browser, Firefox first, with sound on
    and routed to a null sink (`pactl load-module module-null-sink`, `PULSE_SINK`; check the sink inputs, never change
    the default sink, unload the module afterwards), and the same script against the single-element hand-over reported
    beside it; record the lead's observed values (its median, range and clamp hits) per browser;
  - the scrub (median ≥ 30 distinct frames per second);
  - the frame step (p90 ≤ 60 ms over 40 Right presses);
  - the card hand-over (no sampled blank frame);
  - the readout's fixed width across the first clip's end.
- [ ] 3.2 Record the change:
  - HLD D-20: an "Amended …, change `seamless-playback`" bullet covering the two slots, the standby rules, plain
    boundaries only, the flash now accepted only for moves of the playhead, and the measured gate. Note on the "What
    stays" list and on the card bridge's "No second `<video>`" that the standby is built and does not cross black
    cards.
  - "`seamless-playback` is built" in §6 item 10.
  - `web/README.md`: the "One video plays at a time" paragraph names the Timeline's two slots as one player.
  - `docs/editor-workspace.md`: the `seamless-playback` row.
- [ ] 3.3 Gates: `npm test`, `npm run check` and `npm run build` in podman, recording the bundle delta in the HLD
  bullet; `openspec validate seamless-playback --strict`.
