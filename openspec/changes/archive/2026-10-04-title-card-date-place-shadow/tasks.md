Conventions for every task below:

- Python runs from the checkout root with `.venv/bin/python -m pytest` (never `.venv/bin/pytest`), with `TMPDIR`
  exported to the change's own tmp directory (its name must not contain the word "rotate"). Node runs only in
  `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 ...`.
- A running service or a browser check uses only this change's port, database, dev library and scratch directory.
- Run black, isort, mypy, pylint and the tests of the touched modules after each task, not only at the end.
- This change adds no schema key, migration, CLI subcommand or job kind.

## 1. Default subtitle (render)

- [x] 1.1 render/title/content.py: add `default_subtitle(plan, chapter)` (ISO date line, then `Plats: <location>`,
  each only when present; `""` for any chapter but the default) and make `compose_content` use it when the card has
  no `subtitle` key (`None`), keep `""` as no subtitle, and any text as written. Verify in tests: date and place,
  date only, location only, neither (no failure), folder-name date (event dir `2024-08-20 - Midsommar - Tjörn`
  with no reel.yaml date), explicit text replaces, explicit `""` gives the heading only, a chapter card with no key
  has none, the description never appears; and `title_card_lines` gives two subtitle lines for the default.

- [x] 1.2 Absent vs empty end to end below the API: tests that `subtitle: ""` loads, survives the round-trip writer
  and `apply_editorial_write` as `""` (an absent key stays absent, a card with only `""` is kept), and that the
  editorial hash differs between absent and `""`. No production change expected; if one is needed it is made here.

## 2. Soft shadow (render)

- [x] 2.1 render/title/render.py: for `background == "video"` with `has_shadow`, draw a deterministic soft shadow
  (blurred text layer, shadow colour at 0.6 alpha, offset 0.004 x height, blur 0.006 x height) in place of the hard
  offset shadow; `black` cards keep the old path. Verify: a stored hash of a `black` card equals its pre-change
  bytes; two renders of one `video` card in separate processes are byte-identical; `render_title_card` and
  `render_card_png` agree; corners stay alpha 0; `shadow_opacity` 0 draws no shadow; the alpha profile across a
  glyph edge falls off over more than 2 px; a 1920x1080 render takes under 100 ms (printed, asserted at 500 ms).

- [x] 2.2 Real-render frames and a contrast measure: render a `video` card with white text over a bright sample
  (white-to-light-grey ramp and one real bright clip frame, composited by the real overlay path) with and without
  the shadow; save the frames in the verify scratch directory and look at them. Verify: the mean luminance in a
  band 4 to 10 px outside the glyphs is lower with the shadow by a stated margin (WCAG-style contrast of the
  white text against that band rises from under 1.5 to at least 3), and nothing outside the band changes.

## 3. Fingerprint

- [x] 3.1 staleness/fingerprint.py: `RENDER_GRAPH_VERSION` + 1 (re-check the current value at apply) with the
  history line `title-card-date-place-shadow (the opening card's default subtitle and the video card's soft shadow)`.
  Verify: the version test passes at the new value, and an event rendered before reports stale with reason `engine`.

## 4. API

- [x] 4.1 api/schemas.py and api/card_read.py: add `default_subtitle` to the resolved card, filled by the engine's
  `default_subtitle` (task 1.1); `subtitle` stays the effective one. Regenerate OpenAPI and
  `web/src/api/schema.d.ts` (the drift test stays green). Verify in API tests: the five scenarios of the
  api-service delta, including `PUT` keeping `""` and `{}` removing the card, and the preview image for `""` versus
  absent differing (title-only versus three lines, measured by text row count or pixel difference).

## 5. Web

- [x] 5.1 web/src/edit/card/model.ts, specs.ts, cardRows.ts: keep `""` and unset apart for the subtitle only
  (`textOf` unchanged for the other fields), `cardBody` and the preview body send `""`, `draftSpec` shows the
  detail's `default_subtitle` for an unset opening card and never composes one. Verify with `node:test`
  (`npm test`): `""` round-trips as `""`, unset as absent, dirty state differs between them, the preview body
  carries `subtitle: ""`, the row text for unset, `""` and typed values, and the chapter card path is unchanged.

- [x] 5.2 web/src/edit/card/Inspector.tsx and Fields.tsx: the placeholder `Default: ...`, **No subtitle** and
  **Use default** for the opening card only, keyboard reachable and announced; plain CSS in `chapters.css`.
  Verify with `npm test`, `npx tsc --noEmit` and `npm run build` in podman, and Playwright from the scratch dir
  in Chrome (`localhost/playback-research:chrome`) and Firefox (>= 155, `localhost/pcm-audio-research:pw163`):
  the six web-app scenarios, a real preview PNG of a bright-sample event showing the shadow (screenshots looked at),
  light and dark at 1280 and 390, writes intercepted on `**/reel` and `**/reel?*` only.

## 6. Documentation

- [x] 6.1 docs/high-level-design.md: edit the D-24 paragraph that says the opening card no longer shows the date
  and location (default subtitle returns; the explicit `""` opt-out) and add the soft-shadow sentence; add the
  change to the §4.10 title-card list and the §6 roadmap lines (D-20 timeline blocks, D-21 untouched), and record
  `RENDER_GRAPH_VERSION` 9. Verify: `rg "no longer shows the date"` finds nothing, and every changed sentence
  names the change.
