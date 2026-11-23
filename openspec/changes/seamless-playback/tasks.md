All work is in `web/`, plus the HLD, `docs/editor-workspace.md` and `docs/research/seamless-playback.md`.
- **Node** runs only in podman (`docker.io/library/node:22`), with the repo root mounted and `-w /app/web`. Some web
  tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo.
  - Functional checks intercept PUT, POST and DELETE.
  - Timing runs refuse writes inside the page instead, because a route turns off Chromium's HTTP cache
    (`docs/research/seamless-playback.md` §1).
  - Every browser is muted at the browser (`--mute-audio`; no audio socket or `/dev/snd` passed in), so nothing
    plays through the operator's speakers.

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
- [ ] 0.2 Measure first, headed, before any wiring. Run the research note's app probe (§1–2) and spike (§3) on the
  host's display, in Chrome 157 and in Firefox 155 or newer, both muted at the browser. Use at least 20 boundaries
  per case.

  Record in a new §6 of `docs/research/seamless-playback.md`: steady hold, longest hold, lost play time, and the
  chain's steps.

  STOP and report if either of these holds:
  - in either browser, the two-element hand-over misses the gate of "Play crosses a clip boundary without a pause"
    (p90 lost ≤ 20 ms, p90 longest hold ≤ steady + 20 ms, no hold over 100 ms): the approach would not deliver;
  - today's single element already meets it: there is nothing to fix.

## 1. Rules (web/src/timeline, web/src/playback)

- [ ] 1.1 Add `timeline/standby.ts` (design D2): `standbyTarget`, the `Standby` states with `standbyStep`, and
  `atBoundary`. Verify with `standby.test.ts`, which must cover:
  - the target after a plain clip, after a clip with a leading cut (the cut's end), over a clip cut whole, before a
    black-card gap (null), and at the last clip (null);
  - every transition, including an error and a re-target while loading;
  - `hand-over`, `wait` and `load` for a ready, loading or other-target standby.
- [ ] 1.2 Give `anotherPlays` and `watchOtherStarts` in `playback/coordinator.ts` an `own` predicate (design D5).
  Verify with `coordinator.test.ts`, which must check that:
  - a paused second element of the same player is not "another";
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
- [ ] 2.2 Preload and hand over in `useTimelineVideo.ts` (design D3, D4):
  - the standby loads while Play holds and is re-targeted on a draft edit or a seek;
  - `advance()` follows `atBoundary`, and the swap happens on the standby's first presented frame;
  - each slot gets its own handlers, and the coalescer is bound to the shown slot;
  - both slots are released on `held` and on unmount.

  Update the hook's header comment. Verify in Playwright (Chromium and Firefox, writes intercepted) every scenario
  of "Play crosses a clip boundary without a pause". These include:
  - no proxy request at a plain boundary;
  - a leading cut, and a clip cut whole;
  - a slowed proxy, by delaying one clip's route: the last frame is held and nothing is blank;
  - a reorder during play.

  Also log how often the `ended` backstop is what triggers the hand-over.
- [ ] 2.3 Make Use as poster and `useFrameReady` read the shown slot through `shown()` and `onSwap` (design D6), and
  update `posterFrame.ts`'s header. Verify in Playwright "Use as poster after a hand-over", and the existing poster
  scenarios of `web-app`.

## 3. Verification and record

- [ ] 3.1 Run Playwright in Chromium and Firefox over every scenario of both deltas (`event-timeline`, `web-app`).
  Then re-measure headed, muted, on the host's display, and record the numbers in `docs/research/seamless-playback.md`
  §6:
  - the boundary gate (20 boundaries per browser);
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
