All work is in `web/`, plus the HLD. Work only in this change's worktree
(`/var/home/emil/dev/larnet/auto-reel-project/auto-reel-ng-scrub-fade`). Do not touch `web/src/timeline/useTimelineVideo.ts`:
the fix needs no hook change (design D4), and `playing` and `scrubStart` serve the seamless-playback hand-over.
- **Node** runs only in podman (`docker.io/library/node:22`), with the worktree root mounted and `-w /app/web`. Some
  web tests read `docs/` and `auto_reel_ng/`.
- **Playwright** runs from the scratchpad, never from the repo. It intercepts PUT, POST and DELETE.

## 0. Gate

- [x] 0.1 Check that the code and the spec are as this change assumes. Both of these must succeed from the worktree
  root:
  - `grep -n "playing ? shown.opacity : 1" web/src/timeline/CardLayer.tsx`;
  - `grep -n "opacity from its fades at that time" openspec/specs/event-timeline/spec.md`.

  If either fails, STOP and report which one. Then diff the two MODIFIED blocks of
  `specs/event-timeline/spec.md` against their main-spec versions ("The Timeline plays the title cards as the movie
  will", "The playhead can be put in a card, and the readouts count card time"). The diff must show only this
  change's edits. If another archived change has since edited either block, copy it again from
  `openspec/specs/event-timeline/spec.md` and re-apply this change's edits.

  Checked 2026-11-23: the code grep no longer matches because the change has replaced that line (as intended); the
  spec grep matches. The block-by-block diff of both MODIFIED requirements against the main spec shows every main-spec
  scenario kept, with only this change's additions and opacity wording (nothing dropped).

- [x] 0.2 Record the operator's decision on design question 1 under "Operator decision" in `design.md`. Done
  2026-11-23: option A, faithful fades at every position (paused, scrubbed, clicked, stepped), no floor; the
  keyboard-activation fix (D5) stays in this change. The tasks below are written for A.

## 1. Rule (web/src/timeline)

- [x] 1.1 Add `web/src/timeline/cardView.ts` (design D1). It exports:
  - `type CardView = { kind: 'black' | 'video'; chapter: string | undefined; opacity: number; url: string | null; title: string }`;
  - `type PictureLookup = { get(chapter: string): { url: string | null } | null }`;
  - `cardViewAt(p, placements, specs, pictures): CardView | null`, built on `shownAt` from `./play.ts`.

  The function has no play-state parameter. Imports use `.ts` extensions (`./cards.ts`, `./play.ts`,
  `./position.ts`). It does not import `useCardImages.ts` or React. Give it a header comment that names this change,
  and says the layer shows the fades at every position as the movie does.

  Verify with a new `web/src/timeline/cardView.test.ts`. Build the placements as `play.test.ts` does
  (`cardPlacements(specs, clips, 'on')` with its `spec` and `clipOf` helpers, copied locally). Build card positions as
  literals: `{ clip, ms: 0, card: { chapter, name, ms, lengthMs } }`. Pass a stub `PictureLookup`. Its header comment
  names "The playhead can be put in a card, and the readouts count card time" as the scenarios it covers. Compare
  opacities within 1e-9. It must cover:
  - (a) a 7 s black card at `card.ms` 0 / 1000 / 3500 / 6000 gives opacity 0 / 0.5 / 1 / 0.5, with `kind: 'black'`.
    These are the positions the page opening, a press, a drag, Home or a key step makes. Also `card.ms` 7000 gives 0,
    labelled in the test as the length-shrink clamp (the card-edit effect holds `card.ms` to a shortened card's end;
    no play, scrub or key lands there);
  - (a2) the step back from a clip into its card: a 4 s black card at `card.ms` 3900 (where `stepFramesOnTrack` puts a
    Left from the clip's first frame; `play.test.ts` "steps back from a clip's first frame into the end of its card"
    covers that landing) gives 0.05;
  - (b) a position as `pauseCard` leaves it (`card.ms` 1200 of 7000) gives 0.6, so Pause during the fade-in does not
    jump to 1;
  - (c) a 4 s video card over a clip with a leading cut of 0–3000 ms (window `atMs` 3000, `widthMs` 4000), as in
    `play.test.ts`'s "is a video card's window" case:
    - `{ clip: 0, ms: 4000 }` gives `kind: 'video'` and opacity 0.5;
    - `ms: 3000` gives 0 (where Previous/Next clip lands: `clipStep`'s `firstKeptMs` is the window's `atMs`);
    - `ms: 6000` gives 0.5 (fade-out);
    - `ms: 2999` and `ms: 7000` give `null`;
  - (d) a 3 s black card's clamped fades: `card.ms` 1000 gives 2/3;
  - (e) the picture: a ready picture gives its `url` and the spec's title; a missing picture (`get` returns `null`)
    or a pending one with `url: null` gives `url: null`, the same title and the same opacity. A missing spec gives
    `chapter: undefined` and `title: ''`;
  - (f) with the black-card `movie()` placements of `play.test.ts` (black cards of 3 s and 4 s, copied locally),
    `{ clip: 0, ms: 500 }` gives `null`: a black card's placement draws nothing over its clip's footage.

- [x] 1.2 Add `cardPressPart(detail, clientX, left, width): number | null` and `cardPressMs(startMs, widthMs, part:
  number | null): Ms` to `web/src/timeline/play.ts`, beside `fadesOf` (design D5). `cardPressPart` gives `null`
  when `detail === 0` (a keyboard activation), else `(clientX - left) / width` (0 when `width` is 0);
  `play.test.ts` covers it ("steps across cards"). For a number, `cardPressMs` gives `startMs + Math.min(0.999,
  Math.max(0, part)) * widthMs` (`CardLane.tsx`'s arithmetic today); for `null`, it gives `startMs +
  fadesOf(widthMs).inMs`. Verify in `play.test.ts` (a new `it` under "steps across cards"): a 4 s block at 10000
  gives 11000 for `part` 0.25, 10000 for -0.1, 13996 for 1.5, and 12000 for `null`; a 3 s block gives `startMs +
  1500` for `null` (the clamped fade-in); and `opacityAt` at the `null` landing is 1 for both.

## 2. Wiring (web/src/timeline)

- [x] 2.1 Make `web/src/timeline/CardLayer.tsx` a thin renderer of `cardViewAt` (design D2):
  - remove the `playing` prop, its doc comment and the `playing ? shown.opacity : 1` line;
  - keep `memo` and `useSyncExternalStore(playhead.subscribe, playhead.get)`;
  - render `null` when `cardViewAt` gives `null`. Otherwise render the same DOM: `.tl-card-layer` with `data-kind`,
    `data-chapter`, `data-opacity={view.opacity.toFixed(3)}` and `aria-hidden="true"`, holding the `<img>` or the
    `.tl-card-fallback` `<p>` with `style={{ opacity: view.opacity }}`;
  - update the header comment: the layer shows the card's fades at every playhead position (played, paused,
    scrubbed, stepped), as the movie does, and names `cardView.ts`.

  No CSS change.
- [x] 2.2 In `web/src/timeline/Timeline.tsx`, delete `playing={video.playing}` from the `<CardLayer …/>` element (about
  line 1330). Change nothing else in the file. Verify with `npm run check`: no caller passes `playing` to `CardLayer`.
- [x] 2.3 In `web/src/timeline/CardLane.tsx`, the black card block's `onClick` (design D5): take
  `part = cardPressPart(event.detail, event.clientX, box.left, box.width)` (`null` for a keyboard activation, else
  today's `(event.clientX - box.left) / box.width`, 0 when the box has no width) and call
  `onPlace(name, cardPressMs(block.startMs, widthMs, part))`.
  Keep `onOpen(name)` first and the video-card and off-card behaviour as they are. Add a comment in the style of
  `Track.tsx`'s: "Enter comes through as a click with no pointer (detail 0): the playhead goes where the fade-in
  ends."

## 3. Verification and record

- [x] 3.1 Done 2026-11-23 and re-run 2026-11-24 with every log saved, headless: podman Playwright 1.65.2 (Python,
  `mcr.microsoft.com/playwright/python:v1.65.2-noble`), Chromium 159 and Firefox 159, light and dark, 1440 x 900, real
  scrollbars (Chromium's `--hide-scrollbars` default is switched off), no display and no headed run. The stack is the
  real one: `auto-reel serve` and `auto-reel worker` (cpu) against a scratch library, Vite in podman. PUT, POST, DELETE
  and PATCH were intercepted and aborted, except `POST …/title-card/preview` (a read-only render the card image needs);
  each run asserts that nothing else was sent. The logs are in `final/` below
  `/var/home/emil/.cache/claude-tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/c392333e-98af-40e2-a1a2-73e75b1333a5/scratchpad/`.
  The first pass of 2026-11-23 printed to the console only and its scratch library is gone, so none of its figures is
  claimed; the runs below are the record.

  Run 1, `final/check1.log` (script `final/check1.py`, summary line "80 pass 0 fail"): 20 checks in each of the four
  browser and scheme runs, 80 of 80 (`data-kind` and `data-opacity` read after each step). The library has an opening
  black card of 7 s, a 4 s black card (Mitten), a 4 s video card and a 3 s black card, over clips symlinked from the dev
  library. Fresh load 0.000 and "Card 0:00.00 of 0:07.00", image and title invisible; one Right 0.050; Home 0.000; Left
  back 0.000; Next clip into the video card `video` 0.000; Left from a clip's first frame into the 4 s card 0.050 at
  "Card 0:03.90"; Enter on the 4 s and the 7 s block 1.000 and "Card 0:02.00"; a mouse press 1 px in from a block's left
  edge at most 0.03 (0.021 in Chromium; a pixel is 0.04 s here); a press 1.0 s into the 4 s card 0.496 (Chromium) or
  0.489 (Firefox); a press 1.0 s and 3.0 s into the video card `video` 0.5 (0.48 and 0.51 in Firefox); no layer before
  the window or after it; a paused ruler drag rises from the low first sample (0.08 to 0.1) through 26 to 27 distinct
  mid values, holds 1.000 and falls to about 0.04; the same drag held while playing equals the paused one at each of
  the 11 positions; Pause in the opening card's fade-in keeps the opacity (the six frames after the click spread at
  most 0.005, within 0.02 of the value before the click, within 0.0055 of `opacityAt` of the readout's card time, whose
  resolution is 10 ms; the bound allows for that rounding). The second pass below asserts a spread of exactly 0. The
  mid-fade and hand-over stage screenshots are in `final/shots/` (light and dark; the mid-fade ones show the card's
  image dimmed on black).

  The card hand-over, `final/check1.log` ("handover" lines) and `final/hand.log` (script `final/hand.py`: 30 stage
  screenshots across the card's end while playing, with the mean luma of each): the layer's opacity falls to 0.000 and
  the next sample has no layer, and the stage goes from the black card (mean luma 0.2 to 0.6) straight to the clip's
  frames (93.5 and up) with no blank frame between, in both browsers; the clip's proxy sits at `currentTime` 0.01 and
  `readyState` 4 during the card (the `vids` entries of the "handover" lines).

  Second pass, `final/check2.log` (script `final/check2.py`, re-run 2026-11-24 after the check names were corrected;
  summary line "56 pass 0 fail"): 14 checks in each of the four runs, 56 of 56, on a library with the same four cards.
  Pause during a video card's fade-out (opacity 0.60 to 0.62 before and on all six frames after, so exactly constant,
  equal to `opacityAt` of the readout); a Left step into the 4 s card (0.050 at "Card 0:03.90") then Shift+Right leaves
  the card (no layer, "Clip 0:00.90"), and a Shift+Left into the card (from "Clip 0:00.88" to "Card 0:03.88", 0.06) and
  the Shift+Right out of it match `opacityAt`; no Shift step that starts and ends inside a card was run in a browser
  (unit tests only); the 3 s card's clamped fades paused (presses at 0.1, 1/3, 0.5 and 0.8 of the block, each value within 0.0055 of `opacityAt` of the
  readout: about 0.2, 0.667, 1.0, 0.4); Enter on the 3 s block (1.000 at "Card 0:01.50"); Enter on the 4 s block also selects it (`aria-pressed`,
  `data-selected`) with the playhead at "Card 0:02.00" and 1.000. Pause in the opening card's fade-in with the values
  logged (the "opening pause log" lines): before the click 0.537 (Chromium light), after it 0.548 on all six frames
  (spread 0, so exactly constant). The jump over the click is 0.011 to 0.013 across the four runs (about one and a half
  frames of the 2 s fade at 60 Hz, which is 0.008 a frame; bound 0.02), and the held value is within 0.005 of
  `opacityAt` of the readout (Chromium 0.548 at 1.09 s against 0.545; Firefox light 0.565 at 1.12 s against 0.560).
  Not run in a browser: the delta scenario "A frame step into a card" (Right from the last frame of the clip before a
  4 s black card, then Shift+Right; unit tests `play.test.ts` "skips nothing: a step into a card lands on its first
  instant" and `cardView.test.ts` (a)), the length-shrink clamp (`card.ms` 7000) and the picture fallback (unit tests
  only), and "Another player starts during a card" and "A slow frame does not stretch the card" (unchanged by this
  change; unit tests).

  The check, from the original plan, in Playwright, writes intercepted. Start the app from the worktree (`task
  dev:serve`). Use an event in Edit mode whose opening card is
  black, with a black card between chapters, and an event (or a chapter) with a video card. If the dev data has no
  video card, set one in the draft without saving. Read `.tl-card-layer`'s `data-kind` and `data-opacity` after each
  step. Check every scenario of the delta, including that:
  - open the Edit page of the event whose opening card is black (a fresh load, nothing pressed): the stage is black,
    `data-opacity="0.000"`, neither the image nor the fallback title visible, the Clip readout "Card 0:00.00 of …";
    one Right gives 0.050;
  - paused, Home onto the opening black card gives `data-opacity="0.000"` and a black stage; one Right gives about
    0.05 (0.1 s into a 7 s card's 2 s fade-in);
  - paused on the first frame of a chapter's clip after a 4 s black card, Left gives the card at 3.9 s and 0.050;
  - paused, Next clip into the chapter with the video card: `data-kind="video"` and `data-opacity` at most 0.020;
  - paused, Tab to a black card's block and press Enter: the playhead is at the end of the card's fade-in (the Clip
    readout reads "Card 0:02.00 of …" for a card of 4 s or more) and `data-opacity="1.000"`; a mouse press at the
    same block's left edge still gives about 0 (at most 0.02);
  - paused, a press 1.0 s into a 4 s mid card gives `0.500`;
  - a paused ruler drag across a black card, sampled each animation frame, rises from 0, holds 1.000, falls to 0, and
    is never stuck at 1.000 over the fades;
  - the same drag started while playing gives the same values at the same positions (within 0.02);
  - Play from Home, and press Pause during the opening card's fade-in (about 1.2 s in; the exact time does not
    matter). Read `data-opacity` on the frame just before the Pause click and on each of the next five animation
    frames after it. After the Pause it is below 1.000, exactly constant across those frames (spread 0), within 0.02
    of the value read before the click (a frame or two of fade), and equal within 0.005 to `opacityAt` of the Clip
    readout's card time (`min(1, t / 2000, (7000 - t) / 2000)` for a 7 s card). The exact 0.6 at 1.2 s is the unit
    test's (1.1 b), where the position is a literal;
  - paused, a press 1.0 s into a 4 s video card's window gives `data-kind="video"` and 0.500; before the window and
    from its end on there is no `.tl-card-layer`;
  - the card hand-over sampling of `timeline-plays-cards` (a screenshot of the stage every ~100 ms across the card's
    end) still shows no blank frame.

  Take screenshots of the stage at a paused mid-fade position in light and dark at 1440 px, and look at them for the
  image's fade on black.
- [x] 3.2 Record the change:
  - HLD §6 item 10, after the "`seamless-playback` is built" line: "**`titlecard-scrub-fade` is built** (web only;
    D-20): the Timeline's card layer shows the fades at every playhead position, played or paused; a keyboard
    activation of a black card block lands where its fade-in ends; no API, engine or `RENDER_GRAPH_VERSION` change; no
    new dependency." Add the operator's decision on design question 1 in a few words (2026-11-23: faithful fades
    at every position, no floor).
  - HLD §4.10, the `timeline-plays-cards` summary ("the playhead can be put in a card (press, drag, keys) and the
    readouts count card time"): add "; the card is shown at its fades' opacity wherever the playhead is, played or
    paused (`titlecard-scrub-fade`)".
  - HLD D-20, the `timeline-plays-cards` bullet ("The Timeline shows and plays the title cards"): add one sentence
    after the fades sentence: "**Amended (`titlecard-scrub-fade`, 2026-11-23):** the card layer shows the fades at
    every playhead position (played, paused, scrubbed, stepped), as the movie does; a card's first instant is at
    opacity 0 (so an Edit page whose opening card is black opens on a black stage), Pause keeps the opacity reached,
    and a keyboard activation of a black card block lands where its fade-in ends. The decision is the pure `cardView.ts`
    (`cardViewAt`, no play state), which reverts the review fix `c2fd5d11`'s 'full when paused'."
  - `web/src/timeline/docs.test.ts`: add a `describe('docs/high-level-design.md and titlecard-scrub-fade')` with one
    `it('names titlecard-scrub-fade in §4.10, §6 and D-20')` that asserts a line naming `titlecard-scrub-fade` lies
    between `### 4.10 ` and `### 4.11 `, between `## 6. ` and `## 7. `, and between `- **D-20` and `- **D-21`, in the
    style of the `timeline-plays-cards` case.
  - `web/README.md`, the `web/src/timeline` file tree (the `play.ts` line, about line 396): add a `cardView.ts` line,
    "what the card layer shows at a position (pure; `titlecard-scrub-fade`): the card's kind, its fades' opacity at
    every position, its image or title (+ cardView.test.ts); CardLayer.tsx renders it". Change the `play.ts` line's
    "CardLayer.tsx draws the card over the picture" to point at `cardView.ts`.
- [x] 3.3 Gates, from the worktree root:
  - `podman run --rm -v /var/home/emil/dev/larnet/auto-reel-project/auto-reel-ng-scrub-fade:/app:Z -w /app/web docker.io/library/node:22 sh -c 'npm test && npm run check && npm run build'`;
  - `openspec validate titlecard-scrub-fade --strict`.

  No Python changes, so there are no Python gates. Record the bundle sizes `npm run build` reports, before and
  after, in the HLD sentence of 3.2 if they change by more than 0.1 kB gzip.
