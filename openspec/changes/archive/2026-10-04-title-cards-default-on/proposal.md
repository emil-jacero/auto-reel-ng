## Why

The user asked (2026-10-03, title cards): "1. Should automatically create a title card in the beginning
2. Each chapter should generate a title card. I want the title cards to be configured." The card model, the
renderer, the editor and the timeline block all exist now, but a render draws no card at all unless
`look.decorators` lists `title`: `resolve_decorator_names` returns `("none",)` for an absent list. A new event
therefore renders with no opening card and no chapter cards, which contradicts points 1 and 2. The web timeline
also has to guess an "unset" state, because the event detail does not say what the merged look (reel.yaml over
the project `config.yaml`) actually resolves to.

## What Changes

- When `look.decorators` is absent from both the event's `reel.yaml` and the project `config.yaml`, the
  effective decorators are `["title"]`: an opening card for the default chapter and a card per named chapter, as
  the `title` decorator already places them. An explicit list keeps its meaning: `[]` or `[none]` is no cards,
  and a list without `title` is no cards.
- `RENDER_GRAPH_VERSION` is bumped by one (7 on current main, re-check at apply) with a history line: events
  with no decorators now render cards. Every previously rendered event reports stale once, reason `engine` (D-C8).
- The event detail reports `title_cards: {enabled, source}` where `source` is `event`, `project` or `default`,
  computed probe-free from the merged look by the same function the render uses. OpenAPI and `web/src/api/schema.d.ts`
  are regenerated; the drift test stays green.
- Nothing in the legacy importer, `scripts/make_dev_library.py` or the sample libraries writes
  `decorators: [none]` implicitly (checked at apply, asserted by a test over the importer and the script).
- HLD: a decision entry D-25 (next free number after D-24) and notes in §4.10 and §6; the "Deliberately not
  here: the cards are still opt-in" line in the `title-card-model` note is replaced.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `title-card`: "Title decorator places each chapter's card" is modified: an absent `look.decorators` now means
  `title`, and the explicit-list meanings are stated.
- `api-service`: a new requirement, the event detail reports whether title cards are enabled and where that was
  decided.

## Impact

- Code: `auto_reel_ng/render/decorators.py` (the one effective-decorators function), `auto_reel_ng/staleness/fingerprint.py`
  (version and history), `auto_reel_ng/api/` (detail model, `card_read.py` or `events_read.py`, OpenAPI), packages
  `render` and `api`. No web code; the timeline's `unset` guess becomes a follow-up that reads `title_cards`.
- Existing outputs: every rendered event re-renders once with cards (accepted; `--force` is not needed, the
  engine reason makes it stale). A user who wants none writes `decorators: []`.
- Tests: `tests/test_render.py`, `tests/test_title_card.py`, `tests/test_api_events*.py`, `tests/test_api_openapi.py`,
  `tests/test_staleness*.py`.
