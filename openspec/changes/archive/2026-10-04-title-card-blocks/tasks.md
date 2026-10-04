## 1. Model (`web/src/timeline/`)

- [x] 1.1 Add card placement to a new `cards.ts` (pure): `cardPlacements` (anchored / no-footage / off, the
  anchor and start rule, video clamp, `ModelError` on a bad duration) and `cardWords`. Test in `cards.test.ts`
  under `npm test`: plain chapters, a wholly cut first clip, a leading cut, no footage, decorator off, a 7 s card
  on 3 s, a bad duration, and the words for black, video, clamped, off and the opening.
- [x] 1.2 Add the track map for black cards (`trackX`, `clipTimeAt` returning clip time or "in card k", total with
  cards, windowed card range). Test: two black cards (starts 3,000 / 27,000, total 47,000), inside a card,
  round trip over every clip time, a video card shifting nothing, 2,000 chapters windowed without a visit per
  card, and that the movie's length counts black cards once.
- [x] 1.3 Add the card selection reducer (`select`, `clear`, `chapters`, `selectCut`, same object when
  unchanged). Test: exclusion with a cut, ending with the chapter, Escape/clear, no-op identity.

## 2. Data (`web/src/cuts/`, `web/src/timeline/`)

- [x] 2.1 Carry `look.decorators` from the page's read of `reel.yaml` (`ReadCutsState`) and from the Edit-mode
  draft, and derive `titleCardsOn` and the resolved cards plus `title_card_error` / `card_error` from the event
  detail into one model input. Test in `node:test`: `["title"]`, absent, `["none"]`, a non-list, both errors.

## 3. Views (`web/src/timeline/`, `web/src/edit/`)

- [x] 3.1 Draw the card lane in `Track.tsx` (black block with its time, video block with its edge marker, off
  look, error and "does not play cards" notes) with positions through the track map, windowed, in light and dark.
  Verify in Chrome and Firefox with Playwright from the scratch directory: two chapters (black and video), a
  leading cut, decorator off, an unresolved style; 1280 and 390 wide, light and dark; read the screenshots.
- [x] 3.2 Route playhead, scrub, follow, handles and marks through the map so a black card shifts them without
  changing clip time, and a press in a card's span selects the card and leaves the playhead. Test the position
  helpers with a black card present; Playwright: trim a cut after a black card and check the written times are
  unchanged (writes intercepted).
- [x] 3.3 Add the `CardRow` at the head of each chapter in `ClipOrderList` (title, subtitle, duration,
  Black/Video, font; Main keeps the event-title control; added and renamed chapters; unresolved card). Test the
  row's words in `node:test`; Playwright in Edit mode: the rows, the Main title control still edits the draft, an
  added chapter's row.

## 4. Selection and inspector slot

- [x] 4.1 Hold the card selection in the event page above the read view and Edit mode, share it between block and
  row (aria-pressed, names, Escape, exclusion with the cut selection, the polite announcement, the inspector
  slot). Playwright: select from each side, Refresh, delete the chapter, keyboard names via the accessibility
  tree, and that no request other than reads is made.

## 5. Docs and gates

- [x] 5.1 Update `docs/high-level-design.md`: D-20 (the card lane and the black-card track map), §4.10 and §6
  (card blocks built, the editor next), and README's Timeline section if it lists the lane. Test: a grep-based
  check that D-20, §4.10 and §6 name `title-card-blocks`.
- [x] 5.2 Run the gates in the web container: `npm test`, `npx tsc --noEmit` and `-p tsconfig.test.json`,
  `npm run build` (record the gzip size before and after), and confirm `dependencies` is unchanged.
