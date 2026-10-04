## Context

After `edit-mode-declutter` the event page still opens each section with prose. The inventory below is read
from the source on `origin/main` (e5d3041): `edit/EventEditor.tsx` (the Details lead, the `edit-hint` block,
the marks line), `edit/PosterPanel.tsx`, `edit/marks.ts`, `edit/chapterNames.ts`, `timeline/Timeline.tsx`,
`timeline/CutFields.tsx`, `timeline/labels.ts`, `timeline/overlays/`, `edit/card/EventTab.tsx`. The research
evidence this change relies on is the web budget and the existing patterns, not new media facts: D-8 (no new
runtime dependency), `Dialog`/`Alert` in `web/src/ui/`, and the unit-test runner (`node:test`, `npm test`).
Verification baselines (paragraph counts) are taken on `2024-08-20 - Två kapitel - Tjörn` before the change.

### Inventory

Class **A** stays visible (state or action), **B** moves into a section's help, **C** is removed as redundant.
"R" read view, "E" Edit mode.

| Text (source) | Mode | Class | Where it goes |
|---|---|---|---|
| Details lead "What reel.yaml says. An empty field inherits from the folder name." / "Save writes these…" (`EventEditor` `edit-lede`) | E | B | Details help |
| Per-field inherited-value hint (`MetadataForm` `field-hint`, "Left empty: inherits…") | E | A | stays: states what saving does |
| Date incomplete / refusal alert | E | A | stays |
| Poster state "Default: first clip", "Chosen frame, not saved" (`poster-area-state`) | E | A | stays |
| `poster_note`, "this clip does not play, the default is used" (`poster-area-note`) | E | A | stays |
| "Pick the frame on the Timeline, then press Use as poster. The poster is the frame of the original clip at that time; a render writes it beside the movie." (`poster-area-words`) | E | B | Poster help |
| Use as poster's disabled reason (`tl-poster-why`) | E | A | stays: reason of an unavailable control |
| `Movie 3:12.00 of 3:45.00 of footage, with 8 s of title cards` (`tl-summary` paragraph under the track) | R, E | B (re-formed) | compact stat in the control row, class A as a number |
| "The Timeline fades a card in and out over 2 s each… not shown here." (`CARDS_FADES`, `tl-cards-note`) | R, E | B | Timeline help (the selected-card read-out is removed, D8) |
| Lane "Not analyzed. Run `auto-reel analyze <root>`, then Refresh." (`NEVER_ANALYZED`) | R, E | B + A | badge "Not analyzed" stays (state); the command goes to the Timeline help |
| "Analyzed: nothing to suggest." (`ANALYZED_CLEAN`) | R, E | A | stays: state |
| Icon legend under the lane (`Legend`) | R, E | A | stays: names icon-only marks ("Every suggestion's kind…" requires it) |
| "Dismissed suggestions come back when the page is reloaded." (`DISMISSAL_NOTE`) | E | B | Timeline help |
| "No cut selected. Select a cut by its handle or its span to type its times." (`NO_SELECTED_CUT`) | R, E | C | not drawn when nothing is selected |
| Cut fields' hint "m:ss… Enter takes a time; Escape puts the old one back." | R, E | B | Timeline help; the fields keep `aria-describedby` to it, shown only with a selected cut |
| "Reading the cuts…", "cuts could not be read", "Trimming is unavailable while a save…" | R, E | A | stays |
| "Drag a clip by its handle, or use its arrows…" (`edit-hint`, two variants) | E | B | Clips help |
| " Ignored clips are not played and cannot be moved." / " A missing clip is not on disk…" (`edit-hint`) | E | B | Clips help (each clip row already states its status) |
| "Saving adds N new clips to reel.yaml." / "A new clip joins reel.yaml once…" (`edit-hint`) | E | A | stays, as its own line shown only while a new clip exists |
| "Mark clips with the box at the top right…" (`MARK_HINT`) | E | B | Clips help |
| "2 clips marked", Clear marks | E | A | stays |
| "The event's own chapter: its title card shows the event's title…" (`OWN_CHAPTER_NOTE`, chapter tools row) | E | B | Clips help |
| Chapter later-clips notes "Its 1 ignored clip will be listed here" (`chapterNames`) | E | A | stays: what saving will do |
| "No clips. This chapter is left out of the movie." and the empty drop area text | R, E | A | stays: empty state |
| "1 ignored clip, not played" caption (`ignored-caption`) | R, E | A | stays: a count |
| "Mark a clip to move it." / "Choose a chapter." / "Unavailable while saving." (marks line reason) | E | B (conditional) | Move's tooltip and `aria-describedby`; a line only after Move is pressed |
| Title cards tab lead "Every title card of this event follows these. A card can override any of them…" (`ci-lede`) | E | B | the tab's Help |
| Movie panel notes ("outdated"), Needs render + reason, missing-clip alerts, save bar, errors | R, E | A | stays |

The card dialog's other texts (override words, inherited hints, the Title cards switch note, font list
errors) are class A and stay; the dialog's fields and controls are untouched.

## Goals / Non-Goals

**Goals:**
- Fewer always-visible paragraphs in both modes with no information lost: B text stays in the DOM.
- A help toggle that is keyboard- and screen-reader-friendly, remembered per section, safe without storage.
- Pure helpers unit-tested with the existing `node:test` runner.

**Non-Goals:**
- Any change to behavior, controls, the card dialog's fields or the write API.
- A global "hide all help" switch, per-event help state, tours or tooltips on every control.
- New runtime dependencies, an icon set change, a help-content system.

## Decisions

**D1. One `HelpToggle` + `HelpPanel` pair in `web/src/ui/help/`.** The toggle is a `button` in the section's
`panel-header` (after the heading, before other header controls), with the information icon and the word
"Help", `aria-expanded`, `aria-controls` the panel's id, `min-height`/`min-width` 44 px. The panel is a
sibling element with `hidden` while closed, never unmounted, so `aria-describedby` still resolves and a find-in-
page or a screen-reader search of the DOM does not lose the text. Alternative rejected: native `<details>`; its
summary cannot sit in the header beside other controls, and its open state cannot be persisted without script.

**D2. State in `helpState.ts` (pure, injected storage).** `readHelp(section, storage)` and
`writeHelp(section, open, storage)` with key `auto-reel.help.<section>`; every access in `try/catch`; a throwing
or absent storage reads as closed and writes nothing. A `useHelp(section)` hook wraps it with `useState`, so
the open state also lives for the page visit when storage fails. Sections: `details`, `poster`, `timeline`,
`clips`, `cards`. Per section, not per event: help is learned once. The Timeline's key is shared by both modes.

**D3. The marks line keeps its place; the how-to leaves it.** `MARK_HINT` is replaced in `mark-head` by the
Clips toggle, so the row holds the toggle, the count and Clear marks. The `edit-hint` info block is removed in
favour of the panel plus a separate state line ("Saving adds…") that renders only when it has words. The Clips
panel is one element above the marks line (so the toggle stays in the row and the panel opens under it).

**D4. Move's reason leaves the page and returns on demand.** Move keeps `aria-disabled`, `title` and
`aria-describedby` (an element with the reason, visually hidden). A press while unavailable sets "reason shown"
state that renders the existing reason line below the toolbar; it clears when the reason itself changes (a mark,
a chosen chapter, the end of a save). The reservation of an empty line is dropped: `marks.ts`'s reason words and
`moveReason` do not change (the existing `marks.test.ts` keeps passing).

**D5. The movie stat is a pure formatter.** `movieStat(movie, footage, cuts, cards)` in `timeline/labels.ts`
replaces `movieWords`: terms `Movie`, `footage`, `cuts −`, `cards +`, separated by " · ", every time through
the same clock scale (the largest of the four decides, so the line never changes width as the playhead or a
trim drag changes the numbers, as "Running times are written to a fixed width" requires). The movie term keeps
the sum identity: movie = footage − cuts + cards. It sits in `tl-controls` as a muted, `font-variant-numeric:
tabular-nums` text that may wrap by term at 390 px. The supervisor's example ("Movie 0:38 · footage 0:24 ·
cards 0:14") used "footage" for the kept footage; here "footage" stays the source length it has always been
and the cut time is its own term, so nothing the old line said is lost.

**D6. "Not analyzed" is a badge.** The lane keeps its `Badge`-style element with the same text; the sentence with
the command is a Timeline help paragraph. Per-clip "Not analyzed" in a row is unchanged.

**D7. The cut fields appear with a selection.** `CutFields` returns `null` when nothing is selected; the
`tl-fields` slot has no reserved height, so the track moves down by one group when a cut is selected. Accepted:
it happens in response to the operator's press; selection by keyboard focus is the same.

**D8. The selected-card read-out is removed.** `timeline/CardInspector.tsx` draws a `section.tl-inspector`
("Title card for Test, 7.0 s, over video") whenever a card is selected; since `edit-mode-declutter` moved the
editor into a dialog it only repeats the block's accessible name (class C, redundant). The section is dropped
in the read view and Edit mode; the always-present `role="status"` paragraph stays, visually hidden, and keeps
announcing once per selection from the card as the page read it. `inspectorWords` stays (it feeds the
announcement and the block name). `CARDS_FADES` no longer refers to the slot.

## Risks / Trade-offs

- A hidden panel hides instructions from people who never press Help. Mitigation: Help is a visible, named
  button in every section that has any; state, errors and reasons stay visible.
- The stat's cuts term is new text; mitigated by the identity above and a unit test on it.
- Moving the Move reason to a press means a sighted keyboard user sees it only after trying. Mitigation: it is
  the tooltip, the accessible description, and appears at once on the press.
- Selecting a cut shifts the content under the track (D7). Mitigation: only below the track, in reaction to
  a press.
- The set of changed requirements is wide for a UI change; each MODIFIED block only changes the sentence
  that fixed a visible line, and the scenarios that cited it.
