## Why

The user wants title cards that are configured and edited, not only rendered: "Should automatically create a title
card in the beginning; each chapter should generate a title card. I want the title cards to be configured, text on
black or text on a piece of video ... visible in the editor, so that you can edit the title of it again, and maybe
a subtitle. You can also edit the font and drag to edit the length" (user, 2026-10-03; HLD §4.10 v2 "look/style
editor ... title card live-ish preview"). The engine cannot carry any of that today:

- **A card has no editorial home.** The only card setting is the opaque, event-wide `look.title_card`
  (HLD §4.4, D-G of the title-card change). Nothing in `reel.yaml` says what one card says or how long it lasts, so
  an editor has nothing to read, show or write back. A chapter's card text is also derived only from the chapter
  name, and the opening card is hard-wired to the event title plus date, `Plats:` location and description.
- **The opening card says things the user does not want by default.** The user's decision (2026-10-03): the
  subtitle is always free text and empty by default on every card; the opening card stops showing date and place
  automatically.
- **A bad card value fails late.** `look.title_card` is parsed at render time (`parse_title_card_config`), so a typo
  in a font size is found when a render starts, and a per-card value would be found on the same late path.

This change is the engine half of the title-card work of GUI v2 and gates the rest (`title-card-write-api`,
`title-card-over-video`, the editor screens). It is HLD §6 phase 9 (GUI v2) and resolves no §8 research item;
`research/v2/` has no title-card study, so no number here comes from it. Evidence relied on: the user request above
and the supervisor's design (`plan/v2-plan.json`, `title-card-model`); the code as read on origin/main (`render/title/
{config,content,decorator,render}.py`, `reel/{document,schema,writer}.py`, `event/{plan,resolution,editorial}.py`,
`render/decorators.py`); the `title-card`, `reel-document` and `editorial-write` specs; the real project config
(`auto-reel-real-test/library/config.yaml`: `look.decorators: [title]`); HLD §4.4, §4.6, §4.10 and D-C8 (an
over-bump costs one archive re-render and is accepted).

## What Changes

- **`reel.yaml` gains an optional per-chapter `card:` mapping** (schema stays `version: 0`; additive). Keys, all
  optional: `title`, `subtitle`, `duration`, `background` (`black` | `video`), and the style overrides
  `font_family`, `title_font_size`, `subtitle_font_size`, `text_color`, `position`. The **default chapter `""` holds
  the opening card**; a named chapter's `card` is that chapter's card. It is validated fail-loud when the document
  loads (unknown key, wrong type, out-of-range value, blank text, malformed colour), naming `chapters[i].card.<key>`.
- **The card's text is the card's own.** Heading = `card.title`, else the chapter name, else (default chapter) the
  event title. Subtitle = `card.subtitle`, empty by default. The opening card no longer shows the date, the
  location or the description. A chapter can retitle its card without being renamed.
- **The event-wide style stays `look.title_card`** and gains one key, `background: black | video` (default `black`).
  A card's effective style is the engine defaults, then `look.title_card`, then the chapter's `card` overrides, parsed
  once so the fades are clamped to the final duration. One public function, `resolve_card(plan, chapter)`, returns
  the effective config and the text, for the decorator now and for the API's resolved-card read later.
- **`background: video` is accepted and round-trips but is not rendered yet.** A render that reaches it fails that
  event loud with a typed error rather than drawing black; `title-card-over-video` replaces that error.
- **Writers keep the card.** The round-trip writer keeps comments and key order inside `card`; the editorial write
  path (`apply_editorial_write`) sets, merges and removes a chapter's card and never drops it by omission.
- **Rendered output changes for identical inputs: `RENDER_GRAPH_VERSION` is raised by one** (4 to 5 on today's
  origin/main; `title-card-fonts` proposes 5 as well, so whichever lands second takes 6). The staleness effect is
  stated exactly in the design (every rendered event turns stale once, reason `engine`).
- **HLD:** a new decision (D-22 today) for the card model, and amendments to §4.4, §4.6 (schema sketch), §4.10 and
  §6.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reel-document`: MODIFIED "Structure and properties are normalized apart" (a chapter also holds an optional
  `card`); ADDED "A chapter may carry a title card" (keys, ranges, fail-loud) and "A chapter's card is carried by
  every writer" (round trip and the editorial write semantics; see the design for why this sits here and not in
  `editorial-write`).
- `title-card`: MODIFIED "Title card rendered to an image at the target resolution" (text from the card, no date,
  location or description) and "Title decorator inserts a synthetic title segment" (a per-chapter effective config,
  `video` fails loud); ADDED "A card's effective style layers the chapter's overrides over `look.title_card`".

## Impact

- **Packages:** `auto_reel_ng/reel` (new `card.py`; `document.py`, `schema.py`, `writer.py`, `__init__.py`) and
  `auto_reel_ng/render` (`title/config.py`, `title/content.py`, `title/decorator.py`, `title/__init__.py`,
  `render/__init__.py`, `staleness/fingerprint.py` for the one constant). Two further touches in `auto_reel_ng/event`
  are unavoidable and are named so the package count is honest: `event/plan.py` + `event/resolution.py` carry the
  card from the document onto the plan (one field and its pass-through; the decorator only sees the plan), and
  `event/editorial.py` accepts the field on the editorial write path, which the supervisor's summary requires. No
  `api/`, `cli/`, `persistence/` or `web/` change.
- **CLI vs API (Principle V):** the engine owns every decision. `auto-reel render` draws the cards from `reel.yaml`
  and `auto-reel scan` reports the staleness; there is no new subcommand (a card is edited in `reel.yaml` until the
  API and the editor land). The API reaches the same functions later (`title-card-write-api`).
- **`reel.yaml` schema:** additive `chapters[].card`, still `version: 0`. An engine that predates it ignores the key
  (chapter parsing does not reject unknown chapter keys), so a newer file is not unreadable by an older engine; it
  only draws the old card. **`config.yaml` schema:** `look` is opaque, so `look.title_card.background` needs no
  schema change. **No Alembic migration and no rescan**: Postgres holds no card field and the index is rebuilt from
  disk (Principle II).
- **Rendered output and the fingerprint (Principle IV):** output changes for identical inputs (the opening card's
  text; the per-card length and style), so `RENDER_GRAPH_VERSION` is raised. The fingerprint's inputs are otherwise
  unchanged: `card` joins the editorial component only when a chapter has one, so a document without a card hashes
  exactly as before (an editorial ETag held across the deploy stays valid). No probe is added.
- **Tests:** new `tests/test_reel_card.py`; extended `tests/test_reel_writer.py`, `tests/test_event_editorial.py`,
  `tests/test_event_resolution.py`, `tests/test_title_card.py` (including a real small render, `has_ffmpeg` +
  `has_fonts`) and `tests/test_staleness_fingerprint.py`. The existing title-card tests that assert the date and
  `Plats:` lines are rewritten to the new content.
- **Dependencies:** none new (Principle VII).

## Non-goals

- **No card over video.** `background: video` is only stored and validated here; the overlay on the first clip's
  start, its timing and its fades are `title-card-over-video`.
- **No font registry and no bundled fonts.** `font_family` is any non-blank string here; the curated set, the
  registered-family check and the image packaging are `title-card-fonts`.
- **No API, no editor, no preview.** `EditorialDocumentBody`/`ChapterBody` stay untouched (`api/` is
  `title-card-write-api`'s); the timeline block and drag-to-length are later web changes.
- **No default-on title decorator.** Cards still render only when `look.decorators` includes `title`, as today
  (the user's own project config sets it). Making `title` the default for a project with no `decorators` would
  change every render in every project and every test; it is a separate, one-line change the supervisor may want
  (design, "Automatic cards").
- **No opening card for an event with no default chapter.** An event whose clips are all in named chapters has no
  `""` chapter, hence no opening card, as today.
- **No migration of the old opening-card text.** An event that relied on the automatic date and place on its first
  card gets a card without them on its next render; its author can add them as `card.subtitle`.
