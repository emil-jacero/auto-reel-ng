## 1. Engine (render)

- [x] 1.1 In `render/decorators.py`, make an absent or null `look.decorators` resolve to `("title",)`, keep `[]`, `[none]` and lists without `title` as no cards, and keep a non-list failing loud naming `look.decorators`; update the module and `resolve_decorator_names` docstrings. Test: absent -> title; explicit `[]` -> none; `[none]` -> none; `["other"]`-style list -> no title; `"title"` string -> `RenderError`.
- [x] 1.2 Add `title_cards_state(event_look, project_look)` beside it, returning `enabled` and `source` (`event` when the event look sets a non-null `decorators`, else `project`, else `default`); share one helper with 1.1 so the render and the report cannot disagree. Test: the three sources, project `[]` winning over the default, event `[title]` winning over project `[]`, a non-list raising.
- [x] 1.3 Render plan test: a plan with a default chapter and a named chapter (each with a title clip) and no decorators in either layer builds a card segment per chapter through `render_movie`'s segment path; the same plan with `decorators: []` in the event, and with `[]` only in the project `config.yaml`, builds none. Update the existing render and title-card tests that relied on an empty look meaning "no card" to name `decorators: []`.
- [x] 1.4 Bump `RENDER_GRAPH_VERSION` by one (7 on main at spec time, re-check) in `staleness/fingerprint.py` with the history line "title-cards-default-on: an event with no `look.decorators` now renders its opening and chapter cards". Test: an event whose manifest carries the previous version reports stale with reason `engine`, and the existing fingerprint-stability tests still pass at the new value.

## 2. API

- [x] 2.1 Add `title_cards: {enabled, source}` (closed `source` enum) and `title_cards_error` to the event detail model and fill them in `api/card_read.py` (or `events_read.py`) from `title_cards_state` with the document's look and the project's `look_defaults`; a non-list `decorators` gives 200 with `title_cards: null` and the error. Test: detail per source (default, event, project, event overriding project), a list without `title`, the bad value, and a read that writes no file, starts no subprocess and adds no database read.
- [x] 2.2 Regenerate the OpenAPI document and `web/src/api/schema.d.ts` (Node in podman only); `tests/test_api_openapi.py` drift test green and the schema carries the enum; `npx tsc --noEmit` in `web/` still passes with the regenerated types.

## 3. Callers and data

- [x] 3.1 Audit every writer of `look.decorators` (legacy importer, `scripts/make_dev_library.py`, test fixtures, the sample libraries read-only) and remove any implicit `decorators: [none]` or `[]`. Test: importing a legacy event and building a dev library produce a `reel.yaml` with no `decorators` key, so the event reports `{enabled: true, source: "default"}`.

## 4. Docs

- [x] 4.1 HLD: add decision **D-25** (title cards are on unless `look.decorators` says otherwise; the three-source report; the one-time engine re-render; how to opt out), replace the "Deliberately not here: the cards are still opt-in" line in the `title-card-model` note, record the change in §4.10 and §6 with the follow-up that the web timeline reads `title_cards` instead of its `unset` guess, and update the `look.decorators` line in the `config.yaml` description (D-2). Test: `openspec validate title-cards-default-on --strict` passes and the HLD cross-references (D-24, D-C8) resolve.
