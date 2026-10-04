## 1. web/ pure model

- [ ] 1.1 Add `web/src/rotate/turn.ts` (no runtime imports): `normalizeTurn` (0/90/180/270 from any multiple of 90 incl.
  -90, 360, 450; `null` otherwise), `stepTurn(turn, ±1)`, `turnWords`, `turnAnnouncement`, `turnTransform(turn, boxAspect,
  pictureAspect)` giving the rotate and the fit scale. Verify with `node:test` (`turn.test.ts`, `npm test`): the
  normalisation table, wrap (270 +1 = 0, 0 -1 = 270), words, and that for a 16:9 picture in a 16:9 box a 90 turn scales to
  9/16 and a 180 turn to 1, and for a portrait picture in a 16:9 box nothing exceeds the box.
- [ ] 1.2 Add the `Turned` wrapper (`web/src/rotate/Turned.tsx`, `rotate.css`) and the `rotate-cw` icon in `ui/Icon.tsx`
  (`rotate-ccw` exists); overlays are siblings of the transformed child. Verify with `tsc --noEmit` and the build; the
  render is checked in 4.1 (a turned landscape picture fits its box, a play overlay stays upright).

## 2. web/ draft and Edit mode

- [ ] 2.1 In `edit/draft.ts` add `Rotations` to `Draft` and the baseline's read turns (`readRotations`), `turnOf`,
  `rotateClip`, `rotateGroup`, `changedRotations`, `rotationChanges`; extend `isDirty`, Reset and `buildWriteBody`
  (a changed clip writes `rotate`, a turn of 0 removes the key and never writes `rotate: 0`, other properties kept;
  the cleanup at the entry's end keeps an entry with a `rotate`). Verify with `node:test` (`rotate.test.ts`): 0 -> 90 ->
  180, left from 0 = 270, back to the saved value = clean, 0 removes the key and does not write `rotate: 0`, a clip with
  trims and a title keeps them, group of three with turns 0/90/270 right = 90/180/0 in one step, missing/ignored/removed
  clips refused.
- [ ] 2.2 In `edit/ClipOrderList.tsx` add the per-clip Rotate left / Rotate right buttons (names, icons, 44 px coarse
  targets, no drag start, no mark), disabled while a save or move is pending, with the announcements and the Undo
  step; wire through `EventEditor.tsx`. Verify with `tsc`, the build and Playwright (4.1): keyboard Tab/Enter/Space,
  accessible names, no row moves, announcement text, Undo and Reset.
- [ ] 2.3 In `edit/SaveBar.tsx` word the count ("1 clip rotated", "3 clips rotated") in the existing summary, and add
  Rotate marked left / right to the marks line (disabled with no marks, one Undo step, one announcement, marks kept).
  Verify with `node:test` for the wording and the group step (2.1's file), and Playwright (4.1): save bar height at 390,
  the marks line without horizontal scroll.

## 3. web/ turned pictures

- [ ] 3.1 Make `events/ClipThumb.tsx` take a `turn` and show the picture through `Turned`, with the play overlay, mark box
  and "No preview" box unturned; read the saved turns in the read view from the reel read the page already makes
  (`cuts/ReadCuts.tsx` path, shared) and show the "Rotated N degrees" tag with an icon in the clip's row; Edit mode passes
  the draft's turn. Verify with `node:test` for the tag words and the read of a document's turns (-90 = 270, 45 = none),
  and Playwright (4.1): thumbnails of the three rotated samples with `rotate` 0/90/180/270, tag text, no horizontal scroll
  at 320, row height unchanged at 1280.
- [ ] 3.2 Turn `preview/ClipPreview.tsx`'s `<video>` and poster by the clip's turn (draft in Edit mode, saved in the read
  view's Watch), for the preview copy and the original, with the player's controls unturned; the Movie player stays
  unturned. Verify with Playwright (4.1) in Chrome and Firefox: both files, whole and uncropped, Play original, Watch from
  the thumbnail, one video at a time still holds.
- [ ] 3.3 Turn the Timeline's `<video>` (`Timeline.tsx`, `useTimelineVideo.ts`: the turn follows the clip at the swap) and
  `Filmstrip.tsx` tiles by the clip's turn, with the lane geometry unchanged (`layout.ts` untouched). Verify with
  `node:test` that `layout.test.ts` is unchanged and green, and Playwright (4.1): tiles fitted, video turned across a
  swap from an unturned to a turned clip, trim handles and playhead where they were, no sprite or proxy request on a turn
  in Edit mode.

## 4. Verification and docs

- [ ] 4.1 Verify end to end, from the scratchpad only: `npm test`, `tsc --noEmit` and `npm run build` in node:22, then
  Playwright (Chrome 154 image and the Firefox >= 155 image) on a dev library holding the rotated samples, light and dark
  at 1280 and 390, with the screenshots looked at; confirm that thumbnails, proxies and sprites of the rotated samples
  are upright by display rotation (the assumption in design.md) and look at the 0.744-SSIM phone clip; intercept only
  `**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel` and `**/reel?*`, and check the PUT body carries `rotate` and nothing
  else changed.
- [ ] 4.2 Update `docs/high-level-design.md`: D-23's last bullet and §4.10 ("`clip-rotate-gui` follows" becomes landed:
  controls, draft, group, tag, CSS turn on every picture, no cache or contract change), D-20 (the Timeline turns video
  and tiles, lane geometry untouched), §6 roadmap line for `clip-rotate-ui`. Verify by reading the three places against
  the specs (`openspec validate clip-rotate-ui --strict` and a grep that no HLD sentence still says the GUI is to come).
