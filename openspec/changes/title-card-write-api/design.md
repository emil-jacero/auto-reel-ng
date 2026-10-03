## Context

See proposal.md, "Why". Written against `origin/main` at `143f0fc`, before its gates merged; re-checked at implementation against
`3bfa096` (both gates merged), and the "Gate" table below records the names the code really has. Line numbers are omitted: the gates move
`reel/`, `render/title/` and `event/editorial.py`.

**The API today** (`api/schemas.py`, `api/serialize.py`, `api/events_read.py`, `api/routes/events.py`):
- `EditorialDocumentBody` is `extra="forbid"`: `metadata`, `look` (an opaque `Dict[str, Any]`), `chapters`
  (`ChapterBody`: `name`, `clips`), `clips` (`ClipPropertiesBody`), `ignore`. `put_reel` resolves the event, reads
  the existing document (so a broken file is a 502, never a 400), checks `If-Match`, then
  `apply_editorial_write(event_dir, payload.model_dump(by_alias=True))`, mapping `EventMetadataError` and `ReelError`
  to a 400 problem body, `OSError` to a 502. `document_to_body` is the one converter from a `ReelDocument` to the
  body, used by `GET …/reel` and by the write's echo.
- The detail (`events_read.get_event`) builds `ChapterOut(name, clips)` from the document and the disk and reads
  `config.yaml` once per request for `project_look_defaults(settings)` (D-2). It reports **no part of `look`**.
- Event routes live in `routes/events.py` (the greedy `/events/{event_id:path}` detail last); `routes/media.py` holds
  the `{event_id:path}/media|movie|proxy|filmstrip` reads. `ThumbnailGate` (`api/thumbnails.py`) is the model for
  bounding extraction work: asyncio semaphore, no thread held while waiting.
- `render_title_card(config, content, target, dest) -> Path` (`render/title/render.py`) draws with Cairo/Pango and
  uses only `target.width` and `target.height`; `TargetSpec` is built by `derive_target` from the look **and the
  probed clips and the acceleration profile**, none of which a preview may need. `render/target.py` has the
  look's resolution rule as the private `_resolution(look)`.
- The drift test (`tests/test_api_openapi.py`) compares `web/openapi.json` with the app's own schema;
  `web/src/api/schema.d.ts` is generated from it (`npm run generate:types`).

**What this change must respect** (`plan/v2-plan.json`, the supervisor's design):
per-card fields live on the chapter in `reel.yaml`, the default chapter `""` holds the opening card; the card's
title defaults to the chapter name (event title for the opening card) and is overridable without renaming the
chapter; the subtitle is always free text, empty by default; the event-wide style is `look.title_card`; the font set
is the registry. `title-card-model` owns the schema, the validation, the resolution and the staleness consequence;
`title-card-fonts` owns the registry. This change is the transport.

## Gate

`title-card-model` and `title-card-fonts` merge into `origin/main` before this change is implemented. This design
assumes, and task 1.1 checks, the following; each is stated as the thing this change **uses**, never as something it
adds, except where marked.

| Assumed from | What this change uses | Found on `main` (task 1.1) |
|---|---|---|
| `title-card-model` | a typed card value parsed from a chapter's `card:` mapping, strict (unknown keys, types, ranges), raising a typed error that names the field | `reel/card.py::ChapterCard` (frozen, all `Optional`); validated by `reel/schema.py::_parse_card` at load and in `build_document`, raising `ReelParseError` (a `ReelError`) with `loc` `chapters[i].card.<key>`; the registry check is not there (`reel/` is below `render/`) |
| `title-card-model` | a `ReelDocument`/`ResolvedChapter` that carries the card, so `document_to_body` can read it | `Chapter.card`, `ResolvedChapter.card` |
| `title-card-model` | `apply_editorial_write` accepts a chapter's `card` key, keeps comments, validates through the same parser, drops `None` fields | `event/editorial.py::_apply_card`: `None`/absent `card` keeps the card on disk, a mapping with no non-`None` value removes it, `None` fields are dropped. So the route does **no** shaping (decision 2 is now the engine's) and an absent `card` does not remove |
| `title-card-model` | one function that resolves a chapter's card (title, subtitle, duration, background, effective config) from the resolved look, the chapter and the event metadata, used by `compose_content` and the decorator | `render/title/decorator.py::resolve_card(plan: RenderPlan, chapter: ResolvedChapter) -> TitleCardRequest(config, content)`; it raises `TitleCardError`. **This change calls it and never re-derives a field** |
| `title-card-model` | `look.title_card` validated at write time (the engine's `reel` validation), not only at render time | **No**: only `title_decorator` parses it, at render time. So the API validates it (and each sent card's `font_family`) with `render/title/config.py` before the write: `event/` cannot import `render/` (Principle VI) |
| `title-card-model` | `background` in the look/card parse, `video` meaning "no opaque background" for the preview | `TitleCardConfig.background == "video"`; `background_opacity` stays 1.0, so the preview needs one engine helper, `render/title/config.py::overlay_config`, that returns the config with `background_opacity` 0 for `video` |
| `title-card-fonts` | a registry module: families, display names, weights, the default; a `FontResolutionError` for an unknown or unresolved family | `render/title/fonts.py`: `BUNDLED_FONTS: tuple[FontFamily, ...]` (`family`, `display_name`, `role`, `files[].weight`), `DEFAULT_FONT_FAMILY`, `font_for(name)`, `registered_families()` |
| `title-card-fonts` | the engine setting up fontconfig for Pango itself (`FONTCONFIG_FILE`), so host and test runs find the bundled fonts | `configure_fontconfig()`, called by `render._load_backend`; the preview test draws each family on the host |

## Goals / Non-Goals

**Goals**
- The editor can save, read back and render a card with the three verbs it already has (PUT/GET `…/reel`, GET
  detail) plus two new ones (fonts, preview), with no title-card rule in the browser.
- The preview is the renderer's own image, at the event's resolution, for a draft that is not saved.
- A bad card or style is refused with the field's name, and never takes an event out of the editor's reach.

**Non-Goals** (beyond the proposal's)
- Validation rules of any kind in `api/`. They stay in `title-card-model`.
- A preview of the over-video composite, the fades, or the clamp warning (those are render facts).
- Per-chapter card on the events **list** row, or any aggregate ("event has cards").

## Decisions

**1. The write body gains `ChapterBody.card`, a typed `CardBody`, with `look` left opaque.**
`CardBody` is a Pydantic model (`extra="forbid"`) with all-optional fields named exactly as the `reel.yaml` card keys
(`title`, `subtitle`, `duration`, `background`, `font_family`, `title_font_size`, `subtitle_font_size`, `text_color`,
`position`). It checks only shape (key set, JSON types) - Pydantic gives the generated TypeScript a real type and
rejects an unknown key with its name - and **no value rules**. `background` and `position` are plain strings in the
body for the same reason: if they were `Literal`s the vocabulary would be defined twice, in the engine and in the
schema, and a new position would need two edits. The engine's refusal is the single source and arrives as a 400 with
the field named. `look` stays `Dict[str, Any]` as today: the event-wide style needs no body type, because the editor
edits `look.title_card` and the engine validates it.
*Alternatives:* `card: Dict[str, Any]` like `look` - no type for the client and an unknown key surfaces as an engine
message instead of a schema fact; `Literal` enums for `background`/`position` - a second source of the vocabulary;
a separate `PUT …/cards` endpoint - splits one document write into two, loses the single `If-Match`/atomic write and
makes a rename-plus-card edit non-atomic.

**2. Absent and `null` mean "no override"; the engine already drops `None` fields.**
`GET …/reel` returns `card` with every unset field `null` (a full, typed object; `card: null` for a chapter with no
card entry), which is the form that round-trips. On the way in nothing is shaped: `apply_editorial_write` drops `None` fields inside a `card`, removes a card
that is left with no field (`{}`), and **keeps** the card on disk when `card` is absent or `null` (found at
implementation; this replaces the first draft's "a write without `card` removes it"). Removal is `card: {}`.
An unmodified round trip writes nothing. Task 2.1 pins these.

**3. The detail adds `ChapterOut.card` and `EventDetailOut.title_card` from one engine function, and degrades to
`null` + `title_card_error`.**
Both are filled by the `title-card-model` resolver, fed by the same inputs the render uses: the document, the
project look defaults the detail already reads per request, and the metadata. `ResolvedCardOut` (title, subtitle,
duration, background, font_family, title_font_size, subtitle_font_size, text_color, position) and `TitleStyleOut`
(the same without title/subtitle) are values, never null. Why not just return the raw overrides plus the style and let
the client merge? Because the layering (project < event < chapter) and the title defaulting are exactly the logic
that must not exist twice (Principle V; HLD D-8's thin client). Why the effective style only five fields, not
outline/shadow/fades? Those are the fields a card may override and the editor edits; the rest is event styling the
raw `look` already carries. Why the `title_card_error` instead of a 502? A 502 would make an event whose
`look.title_card` was hand-broken impossible to open in the editor that is meant to fix it, while every other
fact of the detail is still true. It is not a silent default: the field is `null` and the error is named.
A chapter whose own card cannot be resolved (a hand-written `font_family` outside the registry, which the loader
accepts) gets `card: null` and `ChapterOut.card_error`, the rest of the event is reported. A malformed **chapter**
card in `reel.yaml` is different: the engine refuses it when the document loads, so the whole
event is the existing unparseable-`reel.yaml` 502 (this change does not alter that; a hand edit is the way out).
*Alternative:* resolve in the client from `GET …/reel` and the project config - needs the project look in the client
and a second implementation; rejected.

**4. `GET /api/v1/fonts` is a static read of the registry, in a new small router.**
A new `routes/title_cards.py` holds the fonts route and the preview route (they share the registry and the title-card
engine, and `routes/events.py` is already 600 lines). No disk, project or database read, so it has no failure path
beyond the process being broken; it is registered with the other routers in `app.py`. `FontOut`: `family`,
`display_name`, `weights`, `default`.

**5. The preview is a POST of a draft, resolved like a render, drawn by an in-memory entry point.**
- *Route and registration.* `POST /api/v1/events/{event_id:path}/title-card/preview`. Registration order does not
  matter: it is the only POST with that suffix, and the greedy detail route is a GET.
- *Body.* `chapter`, `card`, `style` (a `look.title_card` draft, opaque like `look`), `event_title`. The draft is
  *resolved by the same engine function as the detail* over a document view in which the chapter's `card`, the event's
  `look.title_card` and the metadata title are replaced by the draft's. The route builds no field of the result.
  Why a draft `style` and `event_title` and not only `card`: the editor edits the event-wide style and the title in
  the same Edit mode draft; a preview built only from saved values would lag one edit behind exactly where the user
  is looking.
- *Image.* A new `render_card_png(config, content, width, height) -> bytes` in `render/title/render.py`
  (task 1.2); `render_title_card` calls it and writes the bytes, so the two cannot differ and the
  title-card spec's "same image for render and preview" is a test. The size is the event's resolved
  `look.target_resolution` - `_resolution(look)` made public as `look_resolution` in `render/target.py` and reused,
  not copied - **not** a `TargetSpec`, which would need probed clips and an acceleration profile (a fabricated stand-in
  would breach Principle I).
- *`background: video`.* The config the resolver yields for a `video` card has no opaque background (the
  renderer's existing `background_opacity`); the preview renders it as it is. If the model expresses `video` some
  other way, the route does not translate it: task 1.1 records the real mechanism, and if it does not yield a
  transparent config the one-line mapping goes into the engine (the resolver), never the route.
- *Why PNG and not JSON of layout.* A browser cannot reproduce Pango's wrapping, kerning, outline and the bundled
  fonts; the image is the only faithful preview, and the editor overlays it (CSS `opacity` and positioning are the
  editor's).
*Alternatives:* render a card for the saved document only (`GET …/title-card/<chapter>.png`) - stale by one edit,
and would need the chapter name in the path next to `{event_id:path}`; the client draws the card in canvas/CSS with
the same fonts - two renderers that drift, and the fonts would have to be served; render through ffmpeg/drawtext -
subprocess, and not the render's drawing.

**6. The preview's bound is a gate like `ThumbnailGate`, with a wait limit.**
`app.state.title_card_gate`: an `asyncio.Semaphore(2)` and a 10 s wait (`asyncio.wait_for` on the acquire). The draw
runs in `run_in_threadpool` once a slot is held, so waiting holds no thread. A timeout is a 503 problem with
`Retry-After: 2`. A 1920x1080 draw is tens of milliseconds, so the limit only matters under a burst (an editor sending
a request per keystroke); the editor debounces, and the server is correct without it. Free-text length limits are on a
preview-only subclass of `CardBody` (`PreviewCardBody`), so the editorial `card` keeps the engine as its only value
rule and a long hand-written title still round-trips. No cache: a draft is the one input that is never repeated.
*Alternative:* a per-event or per-client limiter - state with no demand; the global two is the thumbnail route's shape.

**7. No CLI subcommand.**
Principle V says new engine capability lands with its CLI surface. The capabilities this change touches are not new
engine capabilities: cards in `reel.yaml` render through `auto-reel render` (`title-card-model`'s surface), the
registry is a module, and the in-memory function is a refactor of the renderer's own write. A `title-card preview`
command that prints PNG bytes would be a feature with no use. Recorded here so the omission is a decision.

**Spec deltas.** `api-service` gets five ADDED requirements and no MODIFIED one: the editorial write/read
requirements say the body holds "metadata, ordered chapters and their clips, per-clip properties, `ignore`, `look`",
which stays true with a chapter's card as part of a chapter, and the "detail is not an editorial write body"
requirement's rejection of a detail-shaped body still holds (a detail's `chapters[].card` is the resolved shape with
`title`/`subtitle` non-null and the detail has other non-body fields, so it is still rejected). `title-card` gets one
ADDED requirement. Task 1.1 re-reads the gates' own deltas and, if a gate MODIFIED a requirement these depend on
(for example the title-card spec's content composition), corrects cross-references, names only.

**HLD.** D-20 is the timeline and D-21 the proxy contract; this change introduces no decision number. Its record is a
§4.10 v2 paragraph (what the API exposes, the resolved-card shape, the preview and its bounds, the
`title_card_error` degradation) and a §6 slice line, beside `title-card-model`'s and the web changes' own notes;
task 5.2.

## Risks / Trade-offs

- **[`look.title_card` is not validated at write time by `title-card-model`]** (its plan entry validates the chapter
  `card` and says nothing about `look`) → the scenario "An invalid event-wide card style is refused" would fail and a
  bad style would be saved, then show as `title_card_error`. Task 1.1 checks; if absent, the fix is one call of the
  existing parser in the engine's write validation (`event/editorial.py`/`reel/`, a third package for two lines),
  reported in the PR rather than weakening the requirement. Task 2.2's test is written first and fails until it is so.
- **[The model's `None` handling differs from decision 2]** → the route shapes (drops `None`) either way; the test
  pins the persisted YAML, not the mechanism.
- **[Preview and the render drift]** (a second code path to the image) → one function; a byte-equality test between
  the file and the bytes, and between the API's PNG and the engine's for the same resolved card.
- **[Host font configuration]** the bundled fonts render only when `title-card-fonts`' fontconfig set-up is active in
  the process → the test per registry family runs on the host (the gate's promise); if it skips (no Cairo/Pango) it
  says so, as the five title-card tests do today.
- **[The resolved card describes a card the render may not draw]** (a chapter whose clips are all excluded plays
  nothing) → documented in the requirement; the read claims what the render would draw for the chapter, not that
  the chapter plays.
- **[Registry in the schema]** not typing `background`/`position`/`font_family` as enums means the generated types are
  `string` → the editor gets the font list from `GET /fonts`, and the two small vocabularies from the engine's
  refusal; a published enum could be added later without a wire change.
- **[A request per keystroke]** → the gate bounds the burst and the editor debounces; no server-side coalescing.

## Open Questions

- Whether the editor should receive `card_defaults` (the style/duration the event would give a chapter with no
  overrides) separately from `title_card`. They are the same values by construction (`title_card` is the
  event-wide layer), so this change does not add a second field; the web change can ask for one if its reset-to-default
  control needs more.
