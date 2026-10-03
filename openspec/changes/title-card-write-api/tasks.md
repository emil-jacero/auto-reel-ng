Conventions for every task below:

- Python runs from the checkout root with `.venv/bin/python -m pytest` (never `.venv/bin/pytest`), with `TMPDIR`
  exported to the change's own tmp directory (`/tmp` has a small quota). Node runs only in
  `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 ...`.
- A running service or a browser check uses only this change's port, database, dev library and scratch directory.
  Never the shared dev library, `auto-reel-media/`, or another change's resources; never remove a container this
  change did not create (the `auto-reel-ng-test-pg-*` ones belong to pytest).
- Run black, isort, mypy, pylint and the tests of the touched modules after each task, not only at the end.
- This change adds no `RENDER_GRAPH_VERSION` bump, fingerprint input, schema key, migration or CLI subcommand.

## 1. Gate and the engine seam

- [ ] 1.1 Confirm that the archived `title-card-model` and `title-card-fonts` changes exist on `main`. If one does
  not, stop and report. Then check each row of design "Gate" against the code they left and write the real names
  into the design: the card value and its parse function and error class, the attribute a chapter's card has on
  the document, how `apply_editorial_write` takes a chapter's `card` (and `None` fields), the card resolver's
  name and signature, whether `look.title_card` is validated at write time, how `background: video` reaches the
  render config, and the font registry's module and entry shape. Re-read the gates' own deltas and correct
  cross-references in `specs/` (names only, never behaviour). Verify: every row of design "Gate" holds or the
  design and specs are corrected (the `look.title_card` row decides whether task 2.2 adds an engine call), and
  `openspec validate title-card-write-api --strict` passes.

- [ ] 1.2 render/: add `render_card_png(config, content, width, height) -> bytes` to `render/title/render.py`, make
  `render_title_card` call it and write the bytes, and make the look's resolution rule public as `look_resolution`
  in `render/target.py` (`_resolution` becomes a use of it, behaviour unchanged). Verify in the title-card render
  tests: the file `render_title_card` writes at a 1920x1080 target equals `render_card_png(…, 1920, 1080)` byte
  for byte; with `background_opacity` 0 a corner pixel is fully transparent and a text pixel is not; an
  unresolvable family raises the same typed error from both; `look_resolution` returns the same pair for the
  cases `_resolution`'s tests cover and fails loud on `[0, 1080]`; the existing golden title-card tests are
  unchanged (render bytes identical, so no `RENDER_GRAPH_VERSION` bump).

## 2. api/ - the card in the editorial document

- [ ] 2.1 `CardBody` (all-optional, `extra="forbid"`, shape only, no value rules) and `ChapterBody.card`;
  `document_to_body` fills it from the document's chapter (unset fields `null`, `card: null` for a chapter with
  no card entry); the engine already drops `None` card fields and removes an empty card, so `put_reel` does no shaping (design
  decisions 1-2). Verify in `tests/test_api_editorial_write.py` and
  `tests/test_api_editorial_read.py` (against the real engine, no mocks): a card with five keys on `Dag 2` is
  persisted with exactly those keys, echoed and read back; `card.title` set while the chapter keeps its name;
  the opening card on the default chapter `""` only; an unmodified `GET …/reel` body written back leaves a
  commented `reel.yaml` byte-for-byte unchanged and its comments intact; renaming a chapter with the same
  `card` moves the card; `card: {}` removes it and a missing or `null` `card` keeps it; a card edit on a fresh rendered event returns a
  stale verdict citing the editorial component and creates no job (the `requires_db` marker as in the
  neighbouring tests); the detail-shaped body is still rejected.

- [ ] 2.2 Refusals name the field. Verify (tests first). The registry and `look.title_card` checks are made by the route before the write, with
  `render/title/config.py` (`event/` cannot import `render/`); no engine write path changes:
  `card.duration: -3`, an unregistered `card.font_family`, `card.background: "gradient"` and
  `card.position: "left"` each yield 400 whose `detail` names the chapter and the field; `card: {colour: "#fff"}`
  is rejected naming `colour`; `look: {title_card: {title_font_size: "big"}}` is 400 naming
  `look.title_card.title_font_size`; a 300-character `card.title` is accepted; in every refusal `reel.yaml` is
  byte-for-byte unchanged and no temporary file is left.

## 3. api/ - the detail reports the resolved card

- [ ] 3.1 `ResolvedCardOut`, `TitleStyleOut`, `ChapterOut.card`, `EventDetailOut.title_card` and
  `title_card_error`, filled in `events_read.get_event` by the model's resolver over the document, the per-request
  project look defaults and the metadata (design decision 3); a bad event style yields `null` + the named error,
  never a 502 and never a default. Verify in `tests/test_api_events.py`: an event with no configuration reports
  the documented defaults (chapter-name title, the event title on the default chapter, empty subtitle, `DejaVu
  Sans`) and the opening card shows no date or place even when the metadata has them; the project/event/chapter
  layering of `font_family` yields the chapter's, the event's and `title_card`'s values; `card.title` differs from
  the chapter name; a chapter that exists only on disk has a defaults card; a hand-broken
  `look.title_card.position` leaves the detail 200 with `title_card` and every `card` null and the error naming
  the field; the request starts no subprocess and writes nothing (monkeypatch `subprocess.Popen` to raise; compare
  the event tree); the events list rows are unchanged.

## 4. api/ - fonts and the preview

- [ ] 4.1 `GET /api/v1/fonts` in a new `routes/title_cards.py` (registered in `app.py`), `FontOut`
  (`family`, `display_name`, `weights`, `default`) read from the registry module. Verify in
  `tests/test_api_fonts.py`: the list equals the registry in order with exactly one `default: true`; every listed
  family is accepted as `card.font_family` by a write and an unlisted one is refused (2.2); the route reads
  no project, disk or database (it answers with the app built on the schema-dump settings).

- [ ] 4.2 `POST /api/v1/events/{event_id:path}/title-card/preview`: `PreviewCardBody` (length limits), the draft
  resolved by the same resolver as the detail, drawn by `render_card_png` at `look_resolution` of the event's
  resolved look, in the threadpool under `app.state.title_card_gate` (2 slots, 10 s wait, 503 + `Retry-After`),
  `image/png` with `Cache-Control: no-store`, every failure a problem body by cause (design decisions 5-6).
  Verify in `tests/test_api_title_card_preview.py` against the real engine: a black draft is a 1920x1080 PNG
  byte-equal to `render_card_png` for the same resolved card; `target_resolution: [1280, 720]` gives 1280x720;
  `background: video` gives RGBA with a transparent corner and opaque text; the draft title is shown and
  `reel.yaml` is unchanged; a draft `style` colour and a draft `event_title` win over the saved ones and are
  absent otherwise; one request per registry family gives distinct PNGs; `title_font_size: 0` and `"Comic Sans"`
  give 400 naming the field; an unknown event 404; an unparseable `reel.yaml` the scan-failure 502; Cairo import
  failure (monkeypatched backend loader) 503 naming it; a 201-character title 422; with a gate of one slot and a
  held draw a second request waits and a third beyond the wait limit (a patched 0.1 s limit) gets 503 with
  `Retry-After` while `GET /healthz` answers; nothing under the dev library's cache directories, `reel.yaml` or the
  jobs table changed and no subprocess started.

## 5. Schema, documentation and a real browser

- [ ] 5.1 Regenerate `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and
  `web/src/api/schema.d.ts` (`npm run generate:types` in the node container); extend the expected paths and models
  in `tests/test_api_openapi.py` (`/api/v1/fonts`, the preview path with an `image/png` 200 and its problem
  responses, `CardBody`, `ResolvedCardOut`, `TitleStyleOut`, `FontOut`, `title_card_error`). Verify: the drift
  test is green; `npx tsc --noEmit`, `npm test` and `npm run build` pass in the node container with no web source
  change beyond the generated file (a screen that spreads a chapter now sees `card` and compiles); then the full
  `.venv/bin/python -m pytest` (in the background, generous timeout), black, isort, mypy and pylint are clean, and
  `openspec validate title-card-write-api --strict` passes.

- [ ] 5.2 Record the change in `docs/high-level-design.md`: a §4.10 v2 paragraph (the editorial `card`, the detail's
  resolved card and `title_card` with `title_card_error`, `GET /fonts`, the preview and its bounds, the transparent
  `video` preview) and a §6 slice line; no new D- number (D-20 is the timeline, D-21 the proxy contract). Verify:
  the paragraph names the routes, the gates and the "no CLI subcommand" decision, and a grep finds no stale claim
  that the opening card shows date and place or that the detail reports no `look`.

- [ ] 5.3 Real-browser check, from the change's scratch directory only: against a service on this change's port
  and dev library, with Playwright in `localhost/playback-research:chrome` and in the Firefox image, fetch the
  preview of a black and of a `video` draft and show each in an `<img>` over a coloured page and over a dark
  one, and PUT then GET a card (writes to the dev library copy only). Verify: both browsers decode the PNG at the
  event's resolution, the transparent card shows the page colour through it, the fonts list has the registry's
  entries, the saved card reads back, and the screenshots (looked at, not just taken) show text in the chosen
  font; no web source changed.
