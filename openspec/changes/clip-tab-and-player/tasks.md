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
  Status (2026-11-21, round 4, left open on one item):
  - Full matrix in Firefox 159 and Chrome 158: 0 FAIL in both (Firefox 102 PASS, 6 PART; Chrome 100 PASS, 2 PASS\*, 5 PART,
    1 PREX). The PART and PREX rows are outside the page (touch emulated, no HEVC in Firefox, a Sony clip's sound in
    Firefox, no real touch screen) or are the accepted gates below. Firefox 132 was not run again this round. Since the
    player now starts hidden in a short window (design D3), the harness stores the choice `shown` before the older
    scenarios; the height-rule scenarios (H1a to H1e: default state, the rule, empty and closed player, focus, Watch) run
    without it and pass in both browsers. Light and dark screenshots at 1440, 1100 and 390 px, shown (empty, closed,
    open) and hidden, were read in both browsers: nothing is clipped.
  - Rows (default state, player hidden, fine pointer): 3 whole rows at 1280×720 and 4 at 1440×900. With the player
    shown: 1 whole row at either size when a clip is shown (design D3).
  - Selecting 50 clips one after the other makes no media request and creates no clip video (M3, M3b), both browsers.
  - Accepted as pre-existing and out of scope (operator decision 2026-11-21): the main specs' 400-clip speed gates that
    fail the same way on `origin/main` 1ae3c68b:
    - zoom-slider drag (at most 2 % of frames over 25 ms, Chrome 4x production build): branch 3.21 % against
      `origin/main` 3.53 %; the archived commit 7538e62c reproduces 0.33 %, so `main` regressed after it (follow-up in
      `docs/editor-workspace.md`);
    - first edit over 400 clips (at most 50 ms over the second): Chrome 222 ms against 203 ms on `origin/main` (227 ms in
      the round-4 matrix), Firefox 71 ms against 66 ms (81 ms in the round-4 matrix); the branch adds about 15 to 40 ms to
      the first Move;
    - scrub (at least 30 frames per second): Firefox 159 is UNVERIFIED because the harness reads 22 fps on the archived
      commit (branch 27.6, `origin/main` 27.5); Chrome 43.9 fps.
  - Open, C5 (a cut that ends between two frames is jumped over once) in Firefox 159: a frame at the cut's own start
    slips through in some plays. Interleaved A/B, 5 plays a round, branch :5181 against `origin/main` :5182, Firefox 159:
    branch 116 of 130 plays clean (89 %), `origin/main` 128 of 130 (98 %), Fisher exact p = 0.003 (round-4 run alone:
    37 of 40 against 40 of 40). Chrome 158: 30 of 30 on both. So the slip exists on `origin/main` but is about seven
    times as frequent on the branch; an earlier summary of 20 of 20 against 19 of 20 is not what the logs add up to. The
    single-play C5 in the full matrix passes in both browsers. The frame loop in `ClipPreview` is not changed by this
    change (its Skip state is held by the player and the preview remounts when the player opens or closes), so the cause
    is probably the player's box or the remount, not yet found. Logs (harness scratchpad): `logs/c5_ab_firefox.txt`,
    `logs/c5_ab_firefox2.txt` (branch 79 of 90, `origin/main` 88 of 90), `logs/c5_ab_chrome.txt`, and
    `logs/r4/c5_ab_firefox.txt`.
  - Operator decision (round 4): the player starts hidden in a window shorter than 70.125rem (1122 px) until the
    operator chooses (design D3).
- [x] 3.2 Record the change:
  - HLD D-28: a "Player" bullet (the preview docks in the bin, shows the selection's last clip, and loads on Play only)
    and the Clip tab built by the editor with the Timeline's track-only part. Amend D-20's one-video note to name the
    player.
  - §6 item 10: this change is built.
  - `docs/editor-workspace.md`: add a row for `clip-tab-and-player`.
- [ ] 3.3 Gates: `npm test`, `npm run check` and `npm run build` in podman; `openspec validate clip-tab-and-player
  --strict`.
