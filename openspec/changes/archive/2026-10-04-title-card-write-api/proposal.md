## Why

The user wants title cards to be configured and edited in the GUI: an opening card and one card per chapter,
each either text on black or text over the start of the chapter's first clip, with an editable title and
subtitle, a choice of font and a length (user, 2026-10-03; HLD §4.10 v2 "look/style editor ... title card
live-ish preview"). Two gates build the engine half: `title-card-model` gives a chapter an optional `card:`
mapping in `reel.yaml` (title, subtitle, duration, background, style overrides) beside an event-wide
`look.title_card`, validated fail-loud; `title-card-fonts` bundles ~8 OFL fonts behind one font registry. The
editor (a later web change) cannot be built on either until the service says three things it cannot say today:

- **It cannot write a card.** `PUT …/reel` takes `chapters: [{name, clips}]` and rejects any other key
  (`ChapterBody` is `extra="forbid"`), so a card cannot be saved, and `GET …/reel` cannot return one.
- **It cannot read what a card will look like.** The event detail reports no card and no title-card style at
  all - v1's "look" was shown nowhere (§4.10) - so the editor would have to re-implement the engine's layering
  (project `config.yaml` < event `look.title_card` < the card's own overrides) and the defaulting of the title
  (chapter name, or the event title for the opening card). That is logic the engine already owns (Principle V).
- **It cannot show the card.** The renderer draws a card with Cairo/Pango on the server; a browser cannot
  reproduce its layout, wrapping, outline and bundled fonts. The editor needs the engine's own image for a
  draft that is not saved yet (the title-card spec: "a render and a future GUI preview produce the same image").

## What Changes

- **`PUT …/reel` accepts a per-chapter `card`** (and `GET …/reel` and the write's echo return it): the same
  keys and the same validation as `title-card-model`'s engine mapping; an absent `card` leaves the chapter
  without overrides. An invalid card (unknown key, wrong type, out-of-range value, unknown font) is refused
  with a problem body that **names the field**, nothing is written, and an unmodified round trip stays
  byte-for-byte a no-op. The default chapter `""` holds the opening card. An invalid event-wide
  `look.title_card` is refused the same way.
- **The event detail reports every chapter's resolved card** (`chapters[].card`: title, subtitle, duration,
  background and the effective style: font, sizes, colour, position) **and the event's resolved card style**
  (`title_card`). Resolved by the engine's own function, probe-free, read-only. The editor shows what a render
  will draw and offers the raw overrides from `GET …/reel` for editing.
- **`GET /api/v1/fonts`** lists the font registry: family, display name, weights, which is the default.
- **`POST /api/v1/events/{event_id}/title-card/preview`** renders **one card as a PNG** from a posted draft
  (the chapter, its card, optionally the event-wide style and event title) at the event's target resolution,
  by the same renderer a render uses. Cairo only: no ffmpeg, no probe, no Postgres, no cache write, no
  `reel.yaml` write. Bounded: field lengths, two at a time, a wait limit (503). A `background: video` draft
  returns the text on a **transparent** PNG, for the editor to lay over the clip's frame.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated**; the drift test is green; the web's
  types compile, `npm test` and `npm run build` pass. No screen changes.
- **No change to what a render produces.** No `RENDER_GRAPH_VERSION` bump, no fingerprint input, no
  `reel.yaml`/`config.yaml` schema change (`title-card-model` owns them), no migration, no rescan. A saved card
  turns its event stale through the editorial component the existing way, which `title-card-model` already
  accounts for.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: five ADDED requirements - "The editorial document carries each chapter's title card", "The
  event detail reports each chapter's resolved title card and the event's card style", "The font registry is
  listed over REST", "A draft title card is previewed as a PNG", "The title-card preview is bounded". No existing requirement text
  changes: the editorial write/read requirements describe the body as "metadata, chapters and their clips,
  per-clip properties, `ignore`, `look`", which stays true with a chapter's `card` as one more part of a chapter
  (design "Spec deltas").
- `title-card`: one ADDED requirement - "A card image can be produced in memory for a given size" - so the
  preview and a render are provably the same image (the existing "single reusable entry point" requirement,
  made testable).

## Impact

- **Packages (two):** `auto_reel_ng/api` (`schemas.py`, `serialize.py`, `events_read.py`, `routes/events.py`,
  a new `routes/title_cards.py`, `app.py` for the preview gate, `openapi.py` unchanged, the generated
  `web/openapi.json` and `web/src/api/schema.d.ts` count with the api change) and `auto_reel_ng/render` (one
  small function in `render/title/render.py`; `render_title_card` delegates to it).
- **CLI vs API (Principle V):** every decision lives in the engine: `title-card-model`'s card validation and
  resolver, `title-card-fonts`' registry, the renderer. The routes shape requests and bytes. The CLI reaches
  the same engine through `auto-reel render` (a card in `reel.yaml` renders) and through hand-edited `reel.yaml`;
  there is deliberately no `auto-reel title-card` subcommand, because a PNG-to-stdout is not a use the CLI has
  (design "No CLI subcommand").
- **Gates:** `title-card-model` and `title-card-fonts` merge first; this change is implemented on top of them
  (design "Gate"). `title-card-over-video` is not a gate: the preview's transparent background is the renderer's
  existing `background_opacity`, not that change's overlay.
- **Tests:** `tests/test_api_editorial_write.py`, `tests/test_api_editorial_read.py`, `tests/test_api_events.py`,
  new `tests/test_api_title_card_preview.py` and `tests/test_api_fonts.py`, `tests/test_api_openapi.py`, the
  title-card render tests (the new in-memory function), the web's `npm test` / `tsc` / `npm run build`.
- **Evidence relied on:** the user's request of 2026-10-03 and the supervisor's design in
  `plan/v2-plan.json` (`title-card-model`, `title-card-fonts`, `title-card-write-api`); HLD §4.10 (v2: look/style
  editor and title-card preview), D-8 (frontend budget; types generated from the schema), D-20 (the timeline that
  will show cards); the title-card spec ("a render and a future GUI preview produce the same image"); the
  editorial-write and api-service specs. `research/v2/` has no title-card study: the proxy and timeline research
  does not bear on this change, and no number here comes from it.

## Non-goals

- **No editor screen, no timeline card block, no drag-to-length.** Those are the web changes that follow.
- **No custom fonts, no upload, no font file serving.** The registry is the bundled set; the service lists the
  names but serves no font file, and the preview PNG is the only place a card's font is seen in the browser.
- **No `title-card-over-video` behaviour.** The preview of a `video` card is the text on transparency; the
  overlay onto the clip, the fades and the clamp warning are that change's render work.
- **No card cache, no preview cache.** A preview is a draft; each request renders. (A browser may reuse the
  same request; the response is `no-store`.)
- **No card in the events list rows**, and no card on `GET …/analysis`.
