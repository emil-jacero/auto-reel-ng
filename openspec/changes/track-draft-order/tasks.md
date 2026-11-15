All tasks are in `web/` (plus the HLD). Node runs only in podman (`docker.io/library/node:22`); Playwright runs from
the scratchpad, never from the repo, with PUT/POST/DELETE intercepted except the write being tested.

## 0. Gate

- [x] 0.1 Dependency gate: this change has **no** dependency change. Confirm the ground is clear before starting:
  `openspec list --json` lists no other active change that touches `web/src/timeline/` or the `event-timeline` spec
  (if one does, STOP and ask which goes first), and `git status` on `main` is clean.
  Status (2026-11-15): the five other active changes (`editor-workspace-layout`, `editor-selection`, `track-drag-edit`,
  `editor-undo`, `clip-split`) all depend on this one, so this goes first; `main` is clean.
- [x] 0.2 Spec freshness: compare the REMOVED + ADDED pair in `specs/event-timeline/spec.md` with the current
  `openspec/specs/event-timeline/spec.md` requirement "The Timeline is shown only in Edit mode, open from the start"; carry over any text changed since 2026-11-15.
  Status (2026-11-15): the main requirement is unchanged since the proposal, but the ADDED text had paraphrased it and
  dropped obligations; restored word for word: the Timeline is the one on which the operator trims cuts, pressing Edit
  opens it, the read view's "no line or region naming a selected title card" and "whatever the number of clips",
  "it only reads" and the pointer to "The Timeline asks for the clips' proxies when they are missing", "the Timeline
  follows" the proxy job's read, the cuts drawn as the draft lists them, "the cuts of every clip stay editable", Play
  "so that a trim is heard and seen before it is saved", and "The cuts are never 'being read' and never
  'unreadable'". To keep `--strict` under its 500-character limit, "The read view keeps everything else it shows" and
  "The Edit-mode Timeline's cuts are the draft's" are their own requirements (the Play-skips-a-trim scenario moved to
  the latter); the Migration names all six.

## 1. Pure model (web/src/timeline)

- [x] 1.1 Add `draftClips(live, chapters, orders)` to `timeline/layout.ts` (design D1). Verify with
  `layout.test.ts` cases: reorder, cross-chapter move, deleted chapter, added chapter, identity without facts counted
  as missing, ignored skipped, names follow the draft.
- [x] 1.2 Add the card mapping to `timeline/cards.ts`: resolved card by `readName`, `synthCard` for added chapters,
  placeholder when nothing resolved (design D2). Verify with `cards.test.ts` (rename keeps duration/background, black
  added card shifts later clips, title cards off draws none, no resolved card → placeholder words).

## 2. Wiring (web/src/edit, web/src/timeline)

- [x] 2.1 Pass the draft's `chapters` and `orders` from `edit/EventEditor.tsx` through `TimelineSection` to `Timeline`;
  use `draftClips` in Edit mode; memoise on the three inputs. Verify with `npm test` and `npm run check`.
- [x] 2.2 Remove `ORDER_SAVED` and its `Alert` (`timeline/labels.ts`, `Timeline.tsx`) and the `orderChanged` note path.
  Verify `grep -rn ORDER_SAVED web/src` is empty and `npm run check` passes.

## 3. Browser verification (scratchpad only)

- [ ] 3.1 Playwright in Chrome and Firefox against a dev service with its own DB, port and library copy: every
  scenario of the delta (reorder drawn, Reset, deleted chapter, added chapter's black card shifts clips, rename keeps
  card, Play order), light and dark at 1280 and 390; screenshots looked at.
  Status (2026-11-15; Chrome stable via Playwright 1.49 `channel=chrome` and Firefox 1.49, port 8101, DB
  `arel_track_draft_order`, scratch library with `Utkast` (Main 1/2/4, Kvällen 3; black 3.0 s event style, Kvällen
  4.0 s over video), `Utan kort` (unresolvable `look.title_card`), `Borta` (no proxies)): 24/25 in each of the 8 runs
  (2 browsers x 1280/390 x light/dark) plus 7/7 per browser for Prepare, proxies prepared mid-edit with a clip gone
  from disk, and the unsaved trim. Passing: read view has no Timeline; a reorder is drawn at once, no saved-order
  note, nothing written; Play from 0 plays `s1710002` then `s1710001`; a cross-chapter move is drawn and Reset draws
  the saved order; a deleted chapter draws no band and no card, its clip in the opening chapter, listed with Undo; an
  added "Morgon" gets a 3.0 s black card, `s1710004` starts 3.00 s after `s1710003` ends, the movie 27.08 -> 30.08 s;
  a rename keeps the 4.0 s video card over the chapter's first clip, titled with the new name; with no resolved card
  and no style the lane draws no block and its note says why, and with a draft style typed it draws "Title card for
  Morgon, shown after save"; `s1710004` removed from disk mid-edit is not drawn after the proxy job's re-read while
  the lists keep the draft; Play skips an unsaved 1.0-3.5 s cut. Found and fixed: a playhead on the opening card
  followed the first clip after a reorder, so Play started mid-track (`afterRead`, test in `position.test.ts`).
  **Open (spec conflict):** scenario "Title cards off" says no card is drawn; the build draws every card in the off
  look (dashed, "not enabled", no time added: movie 24.08 s = footage), as the main spec's card-lane requirement
  ("When title cards are not enabled, every chapter with footage SHALL have its block drawn in an off look") demands.
  The delta scenario needs rewording (e.g. "no card adds time; each is drawn in the off look") or a decision.
- [x] 3.2 Gates: the 80-clip drag measurement of `edit-list-paint-cost` (Chrome 4x) still passes; 400-clip windowing
  unchanged; bundle size before/after recorded.
  Status (2026-11-15, load 1.9-2.6, one session, this branch on :8101 and `origin/main` 46c0f351 on :8102, same DB and
  library; the archived scripts are gone, so rebuilt in SCRATCH: rAF frame deltas during the input, % over 25 ms):
  Trim end edge drag on the 80-clip event (46 px/s zoom, third clip in view, 180 moves of 1 px every 22 ms), Chrome 4x,
  five launches: 0.2 / 0.2 / 0.4 / 0.2 / 0.2 % -> median 0.2 % (p95 16.8 ms), idle 0 % in all five; `origin/main`
  median 0.39 %, idle 0 %. Firefox x3: 0.82 % each (main 0.82 %). Zoom-slider drag on 400 clips (Fit -> 127 px/s),
  Chrome 4x x3: 1.73 / 1.05 / 1.41 % (main 1.77 / 1.05 / 2.76 %); Firefox 0 %. Windowing on 400 clips: 92 clip
  blocks drawn at Fit and 72 at 5 px/s, 400 list rows, on both builds. Bundle (`npm run build`): JS 663.99 kB
  (gzip 215.06) -> 665.78 kB (gzip 215.85), +1.79 kB; CSS 95.71 kB unchanged.

## 4. Docs and validation

- [x] 4.1 Amend D-20 in `docs/high-level-design.md` (the Edit-mode Timeline draws the draft order; added chapters'
  cards built in the browser) and the §6 item 10 note; tick `docs/editor-workspace.md` slice 0.
- [x] 4.2 Gates: `npm test`, `npm run check`, `npm run build` in podman; `openspec validate track-draft-order --strict`.
  Status (2026-11-15): `npm test` 1169/1169 (repository root mounted, `-w /repo/web`), `npm run check` clean, `npm run
  build` JS 665.78 kB (gzip 215.85), CSS 95.71 kB; `openspec validate track-draft-order --strict` valid.
