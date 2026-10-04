Conventions for every task:

- Node runs only in `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 …`
  (`npm test`, `npx tsc --noEmit -p tsconfig.test.json`, `npm run build`) with `TMPDIR` exported to the change's own
  tmp directory. Pure logic is tested with the existing `node:test` runner (D-20), never a new test framework.
- A running service or a browser check uses only this change's port (8351), database, dev library and scratch
  directory; Playwright from the scratch directory only, in Chrome and Firefox, light and dark, at 1280 and 390.
- No API, engine, schema, migration or `RENDER_GRAPH_VERSION` change; no new runtime dependency.

## 1. Gate and model

- [x] 1.1 Confirm `title-card-blocks` is archived on `main`; if not, stop and report. Write the real names into
  `design.md`: the shared selection and how a card is selected, the inspector slot, the clip a card sits over, the
  fate of the "Main title card" line and `TitleCard.tsx`; correct `specs/` cross-references (names only). Then confirm
  by one real call each that `POST …/title-card/preview` accepts a chapter not in the saved document (else `design.md`
  D5 keeps `chapter` as the saved name) and what `GET /fonts` returns. Verify: `openspec validate title-card-inspector
  --strict` passes and the design states the confirmed names.
- [x] 1.2 `web/src/edit/card/model.ts`: `CardDraft` (nine nullable overrides), `readCard(chapter)`, `normalise`,
  `cardChanged`, `titlePlaceholder`, `previewRequest` (the 200 / 400 bounds, the chapter-name-as-title rule), the
  field-from-problem mapping and `cardsChangedCount`. Verify: `model.test.ts` covers set-back-to-read is no change, `{}`
  for all-null, opening card vs chapter placeholder, bound edges 200/201 and 400/401, and a problem naming
  `card.title_font_size` of `Dag 2` maps to that field.

## 2. Draft, write and save bar

- [x] 2.1 `draft.ts`: `Draft.cards` by chapter key, `setCardField`, `clearCardField`, `resetCard`; `isDirty` and
  `buildWriteBody` write `card` only for changed cards; rename, delete and restore keep or drop a card with its chapter;
  Reset and Undo restore the read overrides. Verify: `draft.test.ts` cases for the write body (one changed card of
  three, `{}` removal, rename carries, added chapter, untouched chapter has no `card`, an unmodified draft equals the
  read body) and for `isDirty`.
- [x] 2.2 Save bar and guard: "N title card(s) changed" in `SaveBar.tsx`, unsaved-leave guard includes cards, a 400
  naming a card field is listed and routed to the field. Verify: a node test of the count text for 1, 2 and 0, and a
  component-free test that a card change makes the guard ask.

## 3. Clients and preview

- [x] 3.1 `web/src/api/fonts.ts` and `web/src/api/titleCard.ts`: typed against the generated `paths` (`satisfies keyof
  paths`), failures as values by status (400/404/422/502/503 with `Retry-After`/unreachable). Verify: node tests with a
  fake `fetch` for each status and for an abort.
- [x] 3.2 `useCardPreview`: 250 ms debounce, abort of the superseded request, previous image kept while loading,
  object-URL revoke, one 503 retry after `Retry-After`, no request over the bounds. Verify: node tests with fake timers
  and a fake client for debounce coalescing, superseded response dropped, previous image retained, and one retry.

## 4. Inspector UI

- [x] 4.1 Inspector components in `web/src/edit/card/`: fields with the "Event style" placeholder and **Use event
  style**, Black / Video choice with its words, font listbox from `GET /fonts`, sizes, colour, position, the preview
  with the clip-frame backdrop and its words, field-level messages, `card_error` display; mounted in the gate's slot;
  Escape closes. Verify: `tsc` + `npm run build` clean and `npm test` green.
- [x] 4.2 Responsive, accessible and themed: 320–1280 px with no horizontal scroll, 44 px targets under a coarse
  pointer, labelled controls, polite status, `prefers-reduced-motion`, light and dark tokens. Verify in Chrome and
  Firefox with Playwright from the scratch directory: screenshots at 1280 and 390 in both themes that are looked at, an
  axe-style check of names, and a keyboard-only run through every field.

## 5. Browser verification and docs

- [x] 5.1 End to end on the dev library (port 8351, own database), writes intercepted except the one `PUT …/reel`
  under test: select a card, edit each field, see the preview, set Video and see the backdrop, rename the chapter, Use
  event style, Save, read `reel.yaml` back (only the changed card differs, comments survive), refuse a value at the
  field. Verify: the script passes in both browsers and the screenshots show the inspector in both themes.
- [x] 5.2 Docs: HLD §4.10 and D-24 notes (inspector, draft slice, preview rules, thumbnail-frame caveat, the follow-up
  for own-face fonts and a frame-at-time route), `web/README.md` for the folder, and the web-app main spec synced at
  archive. Verify: the HLD and README name the shipped behaviour and `openspec validate title-card-inspector --strict`
  passes.
