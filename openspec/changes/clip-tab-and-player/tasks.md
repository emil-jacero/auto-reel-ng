All work is in `web/`, plus the HLD and `docs/editor-workspace.md`.
- **Node** runs only in podman (`docker.io/library/node:22`), with the repo root mounted and `-w /app/web`. Some web
  tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo. It intercepts PUT, POST and DELETE.

## 0. Gate

- [x] 0.1 Dependency gate: `chapters-in-inspector` MUST be archived, and both of these must succeed from the repo root:
  - `ls -d openspec/changes/archive/*-chapters-in-inspector`
  - `grep -q "Requirement: The Event tab lists the event's chapters" openspec/specs/web-app/spec.md`

  If either fails, STOP and report which check failed. Then confirm that `openspec validate clip-tab-and-player
  --strict` reports no "Archive would refuse" note. If it reports one (for example, `editor-shortcuts`' requirement
  changed when it was archived), re-copy that requirement from `openspec/specs/` and re-apply this change's edits.

## 1. Rules (web/src/edit)

- [x] 1.1 Add `binPlayer.ts` (`shownClip`, design D1) and `binPlayerPref.ts` (design D3). Verify with
  `binPlayer.test.ts` and `binPlayerPref.test.ts`. They must check:
  - each selection kind, including a cut, several clips and a card that keeps the clip shown;
  - a shown clip that leaves the event or the disk;
  - storage that throws, which falls back to shown.
- [x] 1.2 Add `stepMove.ts` (design D6). Verify with `stepMove.test.ts`. It must check:
  - a step within a chapter, and past a missing clip;
  - the steps into the previous and the next chapter;
  - a missing clip at its chapter's edge, and the event's first and last clip, which return their reasons.

## 2. Wiring (web/src/edit, web/src/preview, web/src/timeline)

- [x] 2.1 `BinPlayer` at the top of the bin (design D2): the closed and open states, Hide and Show player, and Escape.
  The preview leaves `CutsPanel`, and the player counts as a clip preview for the workspace keys. Verify with `npm
  test` and `npm run check`, then in Playwright with the scenarios of "Edit mode previews a clip on request", "A
  clip's preview plays its preview copy when one is ready", "Edit mode holds one video at a time" and "Space on the
  player's Play after a click on a row's frame".
- [x] 2.2 Set From and Set To write the shown clip's panel fields (design D4), and the row's Watch selects the clip and
  focuses Play (design D7). Verify in Playwright:
  - every scenario of "A clip's preview sets cut times at the playhead and plays the clip as the movie will";
  - Set From with the row's panel hidden makes its Cuts control say "typed" and holds Save.
- [x] 2.3 `ClipInspector` and `ClipTrackPart` (design D5): the tab for any selected clip, with Move earlier and later,
  Move to…, Rotate, Ignore or Include, and Remove or Undo, plus the track-only part through its slot. Verify in
  Playwright:
  - every scenario of "The Clip tab offers a clip's edits whether or not the track draws it" and "The Clip tab edits
    the selected clip";
  - the `editor-selection` scenarios of the Clip tab still pass.

## 3. Verification and record

- [ ] 3.1 Run Playwright in Chromium and Firefox over every scenario of both deltas (`web-app`, `event-timeline`).
  Also:
  - measure and report how many whole rows the bin shows with the player shown, at 1280×720 and 1440×900;
  - take screenshots of the player in light and dark at 1440, 1100 and 390 px, shown and hidden, and look at them for
    clipping;
  - check that selecting 50 clips one after the other makes no media request and creates no clip video.
  Status (2026-11-21, left open): both deltas' scenarios pass or are partial for reasons outside the page in Firefox
  159, Chrome 158 and Firefox 132, except the 400-clip gates, which are the main specs' figures and fail or are not
  verified the same way on `origin/main` 1ae3c68b:
  - first edit over 400 clips (at most 50 ms over the next one): Chrome 158 diff 222 ms against `origin/main`'s 203 ms,
    Firefox 159 71 ms against 66 ms (interleaved, five fresh loads each);
  - zoom-slider drag (at most 2 % of frames over 25 ms; production builds, 4x in Chrome, the archived procedure, which
    reproduces 0.33 % on the archived commit 7538e62c): Chrome 158 3.21 % on the branch against 3.53 % on
    `origin/main`; Firefox 159 and 132 0 %;
  - scrub (at least 30 frames per second): Chrome 158 43.9 fps; Firefox 159 27.6 fps against `origin/main`'s 27.5 and the
    archived commit's 22.2 in the same harness, so that figure is not verified; frame-step p90 26 to 31 ms everywhere;
  - Skip cuts in Firefox 159: a frame at the cut's own start slips through in about one play in five, from the frame
    loop in `ClipPreview`, which this change does not touch.
  - Operator decision (round 4): the player starts hidden in a window shorter than 70.125rem (1122 px) until the
    operator chooses (design D3). In Firefox 159 and Chrome 158 with fresh storage the default state shows 3 whole
    rows at 1280×720 and 4 at 1440×900, and the height rule, "Closing gives focus back", "Watching from the row in one
    press" and the empty and closed player at 1440×1300 pass.
- [x] 3.2 Record the change:
  - HLD D-28: a "Player" bullet (the preview docks in the bin, shows the selection's last clip, and loads on Play only)
    and the Clip tab built by the editor with the Timeline's track-only part. Amend D-20's one-video note to name the
    player.
  - §6 item 10: this change is built.
  - `docs/editor-workspace.md`: add a row for `clip-tab-and-player`.
- [ ] 3.3 Gates: `npm test`, `npm run check` and `npm run build` in podman; `openspec validate clip-tab-and-player
  --strict`.
