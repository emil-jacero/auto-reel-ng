## Why

Every title card now resolves its look in three layers (the defaults, the event's `look.title_card`, the
chapter's own `card`; `title-card` spec, D-24), and `title-card-inspector` lets the operator override any field
of one card. The middle layer, the style that all of an event's cards share, can still only be changed by
hand-editing `reel.yaml`. The operator who wants every card of a wedding in one font and colour must set it on
each card, and a card cannot say which of its fields differ from the rest. The v1 look picker was deferred and
never built; this change is the event-wide half of the card editor that replaces it.

## What Changes

- Edit mode gains **Card style for this event**, one place that edits `look.title_card`: font (the bundled set
  of `GET /api/v1/fonts`), title size, subtitle size, text color, position, default length, default background
  (Black or Video). Each field can be left unset, which means the project default, shown in words.
- Each title card (the inspector's selected card and its row in the chapter list) says which of its fields it
  **overrides**; the inspector's "Use event style" falls back to the draft event style, and the live preview
  sends the draft style (`style` of `POST …/title-card/preview`), so a card shows the style as edited, unsaved.
- The edit goes into the existing draft, counts in the save bar ("Card style changed"), undoes with Undo and
  Reset, and saves through the existing editorial `PUT` as `look.title_card`; the rest of `look` and the keys of
  `look.title_card` that the form does not edit (fades, outline, shadow) go back as read.
- A `look.title_card` that the engine refuses (`title_card_error` on the detail) opens the panel on the
  refusal, in words, so the operator can correct it from the page.
- The old v1 look-editor UI, route and strings are removed if any remain. The tree holds none today (the
  editor passes `look` back as read), so this is a check that none returns, not a deletion.
- No API, engine, schema or `RENDER_GRAPH_VERSION` change. Web only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: ADDED requirements for the event-wide card style panel, how a card shows what it overrides, and
  how a save writes `look.title_card`.

## Impact

- `web/src/edit/` (a `cardStyle.ts` pure model, `CardStylePanel.tsx`, the draft, the write body, the save
  bar's counts, the inspector's fallback) and the shared preview hook of `title-card-inspector`.
- Gate: `title-card-inspector` merged (its draft cards, field editors and preview hook are reused, not
  copied).
- No new runtime dependency; the existing `node:test` runner, Playwright in Chrome 154 and Firefox >= 155.
