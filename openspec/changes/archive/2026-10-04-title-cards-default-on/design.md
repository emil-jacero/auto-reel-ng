## Context

- `resolve_decorator_names(look)` (`render/decorators.py`) returns `("none",)` when `look.decorators` is absent
  and is the single place the render consults (`render_movie` in `render/orchestrator.py`). `look` is the plan's
  merged look: `resolve(document, look_defaults=...)` layers the event `look` over the project `config.yaml` `look`
  (D-2, D-J), a key at a time, so an event's `decorators` replaces the project's whole list.
- The `title` decorator already skips a chapter that has no title clip or is wholly cut, and treats a `video`
  background as an overlay, so turning it on by default needs no placement change.
- The event detail resolves cards with `resolve(resolved, look_defaults=...)` in `api/card_read.py`, so the merged
  look is already in hand there, probe-free.
- The fingerprint's `defaults` component hashes the merged look; an absent list hashes the same before and after
  this change, so nothing but `RENDER_GRAPH_VERSION` can mark the old outputs stale (as for `title-card-model`, D-24).

## Goals / Non-Goals

**Goals:**
- A project that never mentions decorators renders an opening card and a card per named chapter.
- The effective state, and which layer decided it, is one engine function used by the render and the API.
- Opting out stays one line and is explicit.

**Non-Goals:**
- No web change (the timeline's `unset` handling is a follow-up change reading `title_cards`); no new card
  fields; no change to how a card is placed, drawn or sized; no writing to `reel.yaml` or `config.yaml`.

## Decisions

1. **The default lives in `resolve_decorator_names`, not in the project config template.** An absent or `null`
   list resolves to `("title",)`. Alternative considered: have the importer or `config.yaml` template write
   `decorators: [title]`; rejected because existing projects and hand-made events would keep rendering no cards,
   and the fact would be duplicated on disk.
2. **`[]`, `[none]` and any list without `title` mean no cards, unchanged.** `none` stays registered as the no-op.
   This keeps every explicit file meaning what it meant, so the only behaviour change is for files that were
   silent. Alternative considered: treat `[]` as absent; rejected because `[]` is the only way to say "no cards"
   that cannot be mistaken for "unset".
3. **One function reports the state: `title_cards_state(event_look, project_look)` next to
   `resolve_decorator_names`.** It returns `enabled` (the effective names include `title`) and `source`:
   `event` when the event's `reel.yaml` look has a `decorators` key that is not null, else `project` when the
   project look has one, else `default`. The detail passes the document's own `look` and the project's
   `look_defaults` (it already holds both); the render path calls the same module for the names, so the two cannot
   disagree. A non-list `decorators` fails loud in both places as today; the detail then answers as
   `title_card_error` does for a bad style (200, the field named), never a guessed `enabled`. Alternative
   considered: derive `enabled` in the web from `look`; rejected because the web cannot see `config.yaml` (the
   reason the timeline guesses).
4. **`RENDER_GRAPH_VERSION` +1 over-invalidates on purpose.** The fingerprint cannot tell which events have no
   decorators without a second path; one re-render of the archive is the accepted D-C8 cost. History line:
   "title-cards-default-on (an event with no `look.decorators` now renders its opening and chapter cards)".
5. **API shape.** `title_cards: {enabled: bool, source: "event"|"project"|"default"}` on the event detail,
   always present (never null), added to the OpenAPI schema with a closed `source` enum, `schema.d.ts`
   regenerated in the same change. It describes what a render would do; like `card`, it does not claim a chapter
   with no title clip or wholly cut clips gets a card.

## Risks / Trade-offs

- Every archive event re-renders once. Mitigation: it is the point of the change and is announced in the HLD
  entry; `[]` in the project `config.yaml` restores the old behaviour for a whole project in one line.
- A sample or dogfood library that relied on no cards starts rendering them; the importer, `make_dev_library.py`
  and the in-repo fixtures are checked by a test that no code path writes `decorators: [none]` or `[]`.
- Existing tests that render with an empty look will now get a card segment; they are updated to name
  `decorators: []` where they mean "no card".
- The web timeline's `off`/`unset` model and the `event-timeline`/`timeline` specs still describe the guess;
  this change does not touch them, and the follow-up must not be lost: the HLD entry lists it.
