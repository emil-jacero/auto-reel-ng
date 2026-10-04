## 1. Name rules in the dialog (`web/src/edit/`)

- [x] 1.1 Add a pure `nameField` model (`edit/card/nameField.ts`) over the existing `checkName`, `decideName` and `laterClipNotes`: for a chapter and for Main, the accepted/refused result with the
  refusal words, "write each accepted name to the draft", "announce once on settle", "Escape returns the refused text to the draft's name", "Done is held by a refusal", and Main's
  empty-inherits hint and file-name note. Test with `node:test` (`nameField.test.ts`): every refusal (empty, taken, `Main`, a deleted chapter, `ß`/`SS`/`ẞ`, U+0085 spaces) with the existing
  words, typing the old name back is no edit and no announcement, one announcement for many keystrokes, Main accepts any text, and no rule is duplicated (the test imports the originals).
- [x] 1.2 Build the dialog's Name field and the "Card title (overrides the name)" / "Use the name" pair on the first tab, with the `role="alert"` refusal, the later-clip notes under the field
  and Ctrl+S held by a refused name. Test with `node:test` for the model's card-title rule (shown only when the draft card has `title`; Use the name removes it; nothing adds one) and with
  Playwright in task 8.

## 2. Length and the second tab

- [x] 2.1 Add `parseCardLength(text, range)` beside `cardLimits` in `timeline/cardLength.ts` and the Length field on the first tab (seconds, tenths, the drag's limits, not adjustable shows the reason, Use event
  style removes `duration`). Test with `node:test` in `cardLength.test.ts`: `6`, `0.5`, `60`, `0.3`, `90`, `abc`, the empty text, `4.04` (not a whole tenth, refused, never rounded), a video card
  bounded by 3.4 s, a not-adjustable card, and that a value read back equals the drag's.
- [x] 2.2 Add the tab list and the second tab "All title cards in this event" to the card dialog, moving in the style fields (font, sizes, colour, position, default length, default background, each with Use
  project default), the Title cards On/Off switch, the "Title cards are off" note, the one shared preview, the tab "1 problem" label and open-on-problem. Reuse `cardStyle.ts` and `decorators.ts`
  unchanged. Test with `node:test` for the pure tab-problem rule (which tab a `look.title_card.*`, `card.*` or `look.decorators` refusal belongs to, the label words, the tab to open on) and the arrow-key tab order.

## 3. The chapter header bar and the removals

- [x] 3.1 Put the "Edit Titlecard" button (icon and text, 44 px, named "Edit title card for <name>", `aria-pressed` from the card selection, unavailable while a save or move is pending) in every chapter's
  header bar, Main's and a draft-added chapter's included, and show the name as plain text; remove the pencil titles, the "Main title card" line and the card row from the chapter section. Test with
  `node:test` for the button's name/pressed/locked words and the chapter-section content (a pure view model) and with Playwright in task 8.
- [x] 3.2 Delete `InlineName.tsx`, `TitleCard.tsx`, `CardRow.tsx`, `cardRows.ts`, `CardStylePanel.tsx`, the panel's CSS, `TitleCardsSwitch.tsx`, `titleCardsSwitch.css`, their strings and tests, `acceptAnything`,
  and their wiring in `EventEditor.tsx`. Test: `npx tsc --noEmit` clean, `npm test` green with the removed tests gone, and a grep over `web/src` that finds none of the removed names.

## 4. Timeline and marks line

- [x] 4.1 Make `TimelineSection` open and toggle-less when `editing !== null` (the read view unchanged). Test with `node:test` for the pure open-state rule (read view closed and toggled, Edit mode open
  with no toggle, Refresh keeps it) and with Playwright in task 8: no `Open timeline`/`Close timeline` in Edit mode, the track or Prepare state visible on entry, the read view still lazy (no `<video>`, no proxy request).
- [x] 4.2 Rework `.mark-line` in `edit.css` as one aligned unit: the `--mark-control-h` token on every button and the select, one axis, one gap token, the reason as one muted hint line below, whole-group
  wrapping at 40rem and 20rem. Test with Playwright in task 8 by measuring bounding boxes (equal heights; centre lines within 1 px; reason below; no horizontal scroll at 390 and 320; no row moves when the first clip is marked).

## 5. Verification and docs

- [x] 5.1 Playwright from the scratchpad only, Chrome (`localhost/playback-research:chrome`) and Firefox >= 155 (`localhost/pcm-audio-research:pw163`, version asserted), light and dark at 1280 and 390, writes routed only
  by `**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel`, `**/reel?*`: Edit opens with the Timeline visible and no Open/Close button; each chapter bar shows the name and "Edit Titlecard" and no pencil, card row, Title cards
  section or Card style section; the dialog renames a chapter, edits Main's event title, changes the event style, turns the cards Off and On, types a length (accepted, refused); Save sends one `PUT` with the expected keys; the
  marks measurements of 4.2. Look at every screenshot; keep before/after full-page shots for the PR.
- [x] 5.2 Update `docs/high-level-design.md` (§4.10 and §6 as in the design's "HLD" section, the D-13/D-20/D-24/D-25 superseded-UI pointers) and run the gates: `npm test`, `npx tsc --noEmit`, `npm run build` (in podman,
  `node:22`), and `openspec validate edit-mode-declutter --strict`. Test: all pass, and the bundle size is recorded against the D-8 budget.
