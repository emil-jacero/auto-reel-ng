## Why

The operator asked that a title card is created at the start and for each chapter, and that the cards are configured
(2026-10-03). `title-cards-default-on` made the render draw cards unless `look.decorators` lists no `title`, and the
event detail now reports the effective answer as `title_cards: {enabled, source}`. The page still guesses: the Timeline
reads `reel.yaml`'s `look.decorators`, treats an absent key as "unset" (dashed blocks, "not enabled", "title cards are
not counted"), and Edit mode has no way to turn the cards off or back on. Reviews of `title-card-event-style`,
`title-card-duration-drag` and `title-card-blocks` also left four defects in the card editing screens.

## What Changes

- Edit mode gets one per-event switch "Title cards: On / Off" that edits `look.decorators` in the same draft (Save,
  Undo, Reset, a save-bar phrase), keeping the other decorator names.
- The Timeline's card lane, Edit mode's card rows and the movie-length readout use the detail's `title_cards.enabled`
  (and the draft's switch while it differs); the "unset" wording and the model's `unset` state are removed.
- The event's own chapter shows ONE opening-card row: the "Main title card" line and the card row become one.
- Every segmented control of the card inspector and of the event card style panel shows the value it inherits as
  pressed, in a muted style, with "(event style)" or "(project default)", instead of nothing pressed.
- The Background helper copy becomes "Black: text on black, before the chapter" / "Video: text over the start of the
  chapter's first clip".
- Layout fix: selecting a card opens the inspector BELOW the track, so the track does not move; pressing a card's
  duration handle selects that card again.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `event-timeline`: the card lane, the card rows and the movie length follow `title_cards.enabled`; one opening-card
  row; a duration-handle press selects the card.
- `web-app`: the Title cards switch and its save; segmented controls show the inherited value; the Background copy; the
  inspector opens below the track.

The pure model's "`unset`" sentence in `timeline` ("The model places each chapter's card as the render does") loses its
meaning with this change; it is a one-clause edit of that requirement, listed as task 1.4 rather than a third delta
(see design, Decision 6).

## Impact

- `web/` only: `web/src/timeline/` (`cards.ts`, `labels.ts`, `Timeline.tsx`, `TimelineSection.tsx`, `CardHandles.tsx`),
  `web/src/edit/` (`draft.ts`, a new `decorators.ts` and `TitleCardsSwitch.tsx`, `EventEditor.tsx`, `CardRow.tsx`,
  `TitleCard.tsx`, `ClipOrderList.tsx`, `CardStylePanel.tsx`, `card/Fields.tsx`, `card/Inspector.tsx`, `card/card.css`),
  `docs/high-level-design.md`, `web/README.md`. No API change: `title_cards` is already in the schema
  (`api-service`, `title-cards-default-on`). No new dependency, no `RENDER_GRAPH_VERSION` bump.
- Evidence relied on: `render/decorators.py` `title_cards_state` (what the API reports and why a web guess can
  disagree: the project `config.yaml` look is invisible to the page); `web/src/timeline/cards.ts` `titleCardsOn`
  (the guess); `edit/ClipOrderList.tsx:895` (`CardRow` wrapping `TitleCard`, both present on main); the
  `be54738` commit (handle press stopped selecting, the cause of the inspector jump). No new research is needed.
