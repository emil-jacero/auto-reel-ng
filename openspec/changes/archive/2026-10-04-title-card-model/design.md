## Context

What the code does today (origin/main `143f0fc`), which this design builds on:

- `render/title/decorator.py` parses **one** `TitleCardConfig` from `plan.look["title_card"]` and gives every
  chapter that resolved a title clip the same duration and style. The card is inserted by the `title` decorator, which
  runs only when `look.decorators` lists `title` (`resolve_decorator_names`: absent means `("none",)`). The user's
  project config (`auto-reel-real-test/library/config.yaml`) sets `decorators: [title]`.
- `render/title/content.py::compose_content` gives the default chapter (`""`) the event title plus date, `Plats:`
  location and description, and any other chapter its name only. `render.py` draws line 0 at `title_font_size` and
  every later line at `subtitle_font_size`.
- `reel/schema.py::_parse_chapters` reads `{name, clips}` and ignores every other chapter key. `look` is opaque in
  the loader (the `reel-document` spec), and `event/resolution.py::_merge_look` shallow-merges the document's
  top-level `look` keys over the project's, so an event's `look.title_card` replaces the project's whole
  `title_card` map. That is existing behaviour and this change does not touch it.
- `event/editorial.py::_apply_chapters` reuses an existing chapter node (by name, else by its clips) and rewrites
  only `name` and `clips`; any other key on the node, and its comments, stay. The API reaches it with
  `payload.model_dump(by_alias=True)`, which yields `None` for every field the client did not send.
- `ReelDocument.to_dict()` is the editorial hash and the editorial ETag (`staleness/fingerprint.py`).
- Layering (Principle VI): `reel/` is below `event/` is below `render/`. `render/` already imports `reel/` and
  `event/`; the reverse is forbidden.

## Goals / Non-Goals

**Goals:**

- A chapter can carry a validated `card:` in `reel.yaml`; the default chapter's card is the opening card.
- The engine draws each card from its own text, length and style layered over the event-wide style.
- No writer drops a card by omission, and a document without a card is byte- and hash-identical to before.
- The effect on staleness is stated exactly.

**Non-Goals:** the proposal's list (video background rendering, font registry, API, editor, default-on decorator).

## Research & Decisions

### Where a card lives

**Context**: the user wants to edit a card's title, subtitle, font and length "again" in the editor, so a card needs a
home in the editorial document that survives reorder, rename and cuts.
**Explored**: (a) a top-level `cards:` map keyed by chapter name; (b) a property of the chapter's title clip in
`clips:`; (c) an optional mapping on the chapter. No research study exists for this (`research/v2/` covers proxies,
PCM audio and the timeline), so this rests on the code: `reel-document` keeps *structure* in `chapters` and
*properties* in `clips` keyed by identity, and `editorial.py` already pairs a renamed chapter with its old node by
its clips.
**Decision**: (c), `chapters[i].card`. The default chapter `""` holds the opening card.
**Rationale**: (a) breaks on every rename (the key is the chapter's name, which the editor changes freely). (b) moves
the card when the title clip changes (`title: true` on another clip, or a cut that removes the clip, which the engine
already handles by moving the card to the next clip), and a card is not a clip property. (c) is renamed, reordered and
deleted with its chapter by the machinery that already exists, and a chapter reads as "a heading and its clips".

### The key set and the ranges

**Context**: the validation must be fail-loud and the editor needs bounds it can offer.
**Explored**: the existing `look.title_card` keys (`config.py`), and what the user named: text on black or on video,
title, subtitle, font, length.
**Decision**: `card` keys, all optional.

| key | type and range | note |
|---|---|---|
| `title` | string, not blank | overrides the heading; absent means chapter name (event title for `""`) |
| `subtitle` | string, any (empty allowed) | absent or empty means no subtitle line |
| `duration` | finite number, `0.5 <= d <= 60` seconds | |
| `background` | `black` or `video` | absent means the event-wide value, default `black` |
| `font_family` | string, not blank | registry check belongs to `title-card-fonts` (below) |
| `title_font_size`, `subtitle_font_size` | integer, `8 <= n <= 400` | defaults 96 and 48 at 1080p |
| `text_color` | `#RRGGBB`, either case | |
| `position` | `center`, `top`, `bottom` | the renderer's own set |

**Rationale**: the bounds are product choices, not measurements, and are stated so a test can pin them. 0.5 s is about
twelve frames at 25 fps, below which the default two-second fades clamp to almost nothing; 60 s catches a unit slip
(milliseconds typed as seconds). 8 to 400 px brackets legible text on a 1080p canvas (a 400 px line is over a third of
the height). `text_color` is `#RRGGBB` only, although the renderer also accepts five colour names for the event-wide
style: the card keys are what an editor's colour picker writes, and one spelling means one hash. The ranges apply to
`card` only; the existing event-wide `look.title_card` keys keep their current (unranged) rules so no project config
that loads today stops loading. Bool is never a number (`true` is not `1`), as everywhere else in the schema. A key that is present with a `null` value fails loud: YAML reads an unquoted `text_color: #FFD700` as a comment, i.e. `null`, and treating that as "unset" would silently ignore the user's colour (Principle I); the error says to quote it. (The metadata fields, by contrast, accept `null` as unset; a card key is either absent or has a value.)
Unknown keys fail loud, listing the allowed ones, so a typo (`titel`) is an error and not a silently ignored override.

### Where the keys and the validation live

**Context**: `reel/` must validate at load time (the user gets the error when the file is read, not when a render
starts), but the allowed sets are a render concept.
**Decision**: a new `reel/card.py` holds the frozen `ChapterCard` dataclass (every field `Optional`), the allowed key
set, the `background` and `position` sets and the numeric bounds. `reel/schema.py::_parse_card` validates with the
existing coercion helpers (`_is_boolish`, `_opt_str`, `_req_time` style) and attaches `Chapter.card`.
`render/title/config.py` imports the sets from `reel/card.py`, never the other way round (Principle VI).
**Rationale**: one definition of the sets, so the loader and the renderer cannot drift, and no upward import.
**Consequence for fonts**: `reel/` cannot import `render/title/fonts.py`, so `card.font_family` is checked at load only
as "non-blank string". Membership in the registry is checked where the effective config is parsed (render time and the
API's draft validation), by the same `parse_title_card_config` that already checks `look.title_card.font_family`. A
`reel.yaml` naming an unregistered family therefore loads, and that event's render fails loud naming the family and
the registered ones. This is the supervisor's "limited to the registry once `title-card-fonts` lands", honoured at the
only layer that can.

### How a card's style is resolved

**Context**: the effective style is defaults, then `look.title_card`, then the card's overrides, and fades must clamp
against the *final* duration.
**Explored**: overlaying the parsed `TitleCardConfig` with `dataclasses.replace` (the fades were already clamped
against the event-wide duration, so a card that lengthens the duration inherits fades shrunk for the shorter one, and
the result would depend on order); overlaying the raw mappings and parsing once.
**Decision**: overlay at mapping level. `resolve_card_config(look_title_card, card)` builds `dict(look_title_card)`,
sets each non-`None` card field under the same key (`duration`, `background`, `font_family`, `title_font_size`,
`subtitle_font_size`, `text_color`, `position`), and calls `parse_title_card_config` once. `title` and `subtitle` are
text, not style, and go to `compose_content`.
**Rationale**: one parse means one clamp, against the final duration, and every existing rule (types, `position`,
fades) applies to a card with no new code path. A card with `duration: 1` and the default 2 s fades renders 0.5 s in,
0.5 s out, exactly as an event-wide `duration: 1` does today (spec: "Fades clamped to card duration").
`look.title_card.background` is a new accepted key (`black` | `video`, default `black`); it is distinct from the
existing `background_color`/`background_opacity`, which colour the `black` card's fill.

### The text of a card

**Decision**: `TitleCardContent` becomes `heading` and `subtitle` (the `date`, `location`, `description` fields and
the `Plats:` helpers are deleted, Principle VII, since nothing else uses them: `rg` finds them only in
`content.py`, `render.py`, `__init__` exports and `tests/test_title_card.py`). Heading = `card.title`, else the chapter
name, else for `""` the event title from the plan's resolved metadata. Subtitle = `card.subtitle` when non-empty.
`title_card_lines` returns `[heading]` or `[heading, subtitle]`, so the renderer's "line 0 is the title size, later
lines the subtitle size" rule is unchanged. A card with an empty heading (default chapter, no `card.title`, no event
title) raises `TitleCardError` naming the chapter instead of drawing an empty card: a processable event always has a
title (`require_processable`), so this only fires on a plan built by hand.
**Rationale**: the user's decision ("subtitle always free text, empty by default on every card; the opening card stops
showing date/place automatically") taken literally. The one public function `resolve_card(plan, chapter)` returns the
`TitleCardRequest` (config and content) for a chapter; the decorator calls it, and `title-card-write-api` calls it to
report the resolved card, so the editor never re-implements the layering (Principle V).

### `background: video` before `title-card-over-video`

**Context**: the field must exist now (the editor and the API gate on this change) but its renderer is a later change.
**Explored**: render `video` as black until then (a silent substitution of the wrong look, which Principle I forbids);
refuse at load (then the editor could not store the choice ahead of the renderer, and a reel.yaml written by a newer
engine would stop loading on this one); accept and fail the render.
**Decision**: accept and round-trip it; the `title` decorator raises `TitleCardError("chapter <name!r>: card
background 'video' is not rendered by this engine")` for any card whose effective `background` is `video`, before any
segment is encoded. The render of that event fails and is reported failed; other events are untouched (per-event
isolation). `title-card-over-video` replaces the error with the overlay.
**Consequence**: the editor must not offer `video` before `title-card-over-video` has landed. The supervisor's order
(over-video gates the editor screens) covers it; it is recorded here so it is not forgotten.

### Staleness: exactly which events turn stale

**Context**: Principle IV requires a `RENDER_GRAPH_VERSION` bump when bytes change for identical inputs, and the
fingerprint must stay probe-free. A card with no `card:` key is a document the user did not touch, so the editorial
hash cannot be what notices the change.
**Decision**: raise `RENDER_GRAPH_VERSION` by one from the value on origin/main when the change lands (4 to 5 today;
`title-card-fonts` also proposes 5, so the second to merge takes 6 and writes its own line in the constant's
comment). `Chapter.to_dict()` emits `card` only when the chapter has one.
**Effect, exactly:**

| event | what the fingerprint does |
|---|---|
| has a `render-manifest.json` from the previous engine id (any look, with or without the `title` decorator) | `engine` component changes: stale once, reason `engine`, until re-rendered. Every rendered event, because the fingerprint cannot see which looks use the decorator without a second code path |
| `reel.yaml` has no `card:` anywhere | `editorial` component unchanged, so the editorial ETag a client holds stays valid across the deploy |
| `reel.yaml` gains a `card:` later | `editorial` moves, like any edit |
| never rendered, or no manifest | no change: it is NEW or unrendered already |
| project `defaults` (`look` in `config.yaml`) | unchanged; `look.title_card.background` is just another default when set |
| proxy cache | untouched: proxies are not a staleness input and key on their own `PROXY_VERSION` (`tests/test_proxies_isolation.py` guards that `staleness/` never imports them) |

**Alternatives rejected**: no bump and rely on the editorial hash (wrong: nothing in `reel.yaml` changed, so a
changed opening card would never be re-rendered, a Principle IV violation); folding the effective card text into the
`defaults` or `editorial` hash (moves every event's hash anyway, and puts a render computation into the editorial
ETag); making the engine component conditional on the decorator list (a second fingerprint path for a saving the
D-C8 trade-off already accepts). For the real library this is not a loss: its project config enables `title`, so
every event's opening card does change.
**The PR text for the supervisor**: "after this change every rendered event reports stale once (reason: engine); the
opening card no longer shows date/place, so a re-render is the point."

### The writers

**Round trip.** `document_to_data` re-emits the loaded structure, so a hand-authored `card:` with comments is
byte-stable with no code. The fresh path (`writer._chapters_seq`, for documents built from typed fields) writes
`card` between `name` and `clips`, only the keys that are set, in the table's order.

**Editorial write.** The semantic for a chapter's `card` in the desired state:

| desired chapter | result on disk |
|---|---|
| no `card` key, or `card: null` | the chapter's existing card is **left as written** (comments included) |
| `card: {}` | the card is **removed** (the document keeps no empty `card:`) |
| `card: {title: ..., ...}` | merged into the chapter's `card` node key by key: a key absent from the desired card is removed, a key whose value is equal is left as written (its comment and number spelling stay), a changed key takes the new value; a fresh `card` is inserted directly after `name` |

A `None` value inside a desired card means "key absent". The merged data is validated by `build_document` before
anything is written, so an invalid card is refused and the file is untouched; a save that changes nothing writes
nothing (existing rule). A renamed chapter keeps its card through the existing pairing by clips; a deleted chapter
drops it; moving a clip between chapters never touches either chapter's card.
**Why absent and null both mean "leave it".** Today's clients (`ChapterBody` is `{name, clips}`, forbids extra
fields) cannot send a card, and the API builds the desired state from `model_dump`, which turns every omitted field
into `None`. If absent meant "remove", every v1 save would erase every card, and so would the first API change that
adds an optional `card` field without `exclude_unset`. Removal needs an explicit `{}`. `title-card-write-api` is told
this in the PR text.
**Why the spec delta sits in `reel-document`.** The brief allows two capability deltas. The two natural homes are
`reel-document` (the document and the one canonical writer) and `title-card` (the engine); `editorial-write` would be
a third. The write semantics are written as one requirement in `reel-document` ("A chapter's card is carried by every
writer"), next to the round-trip requirement they extend. The `editorial-write` spec's "desired editorial state" list
is true as written (a card is part of a chapter), and `title-card-write-api` documents the API half.

### Automatic cards

**Context**: "should automatically create a title card in the beginning; each chapter should generate a title card".
**What is already automatic**: with the `title` decorator on, every chapter that has an included clip gets a card
(its chapter name as the heading), and the default chapter's card is the opening card; with this change both also
have defaults for every field, so a card needs no `card:` to exist.
**What is not**: the decorator itself is opt-in per project (`look.decorators`). Flipping the default so a project
with no `decorators` key gets cards would add seven seconds and a Cairo/Pango dependency to every render in every
project and to most of the test suite (every `render_movie` test that passes a bare plan). That is a larger,
separable change with its own output impact, so it is left out and reported to the supervisor as the one open
question. An event with no default chapter (all clips in named folders) has no opening card; giving it one needs a
chapter-times answer (which chapter does the card belong to) and is also left out.

### Failure, idempotency, and the graph

- **Fails loud, at load:** any invalid `card` (naming `chapters[i].card.<key>`), as a parse error. **At render:**
  an unregistered or unresolvable font, an unrecognised `look.title_card` value, `background: video`, an empty
  heading; each is a `TitleCardError`/`FontResolutionError`, reported as that event's failure, never as rendered.
- **No new graph.** The card is still its own segment: the PNG from `render_title_card` looped for `duration`
  seconds, the `fade` filter for the clamped fades, a synthesized silent audio track, encoded to the target spec on
  the chosen profile like any other segment. What changes is only the per-chapter `ProducedSegment(duration, fade_in,
  fade_out)` it already carries, so the emitted ffmpeg arguments per profile and the CPU fallback are unchanged in
  shape (the `-t` and the `fade=…:d=` values differ per card).
- **Idempotent:** the same document renders the same bytes and the same fingerprint, on a re-run (skipped by the
  gate), on `--force` (replaced, identical), and after a worker killed mid-render (the `.part` is discarded; nothing
  looks rendered). An editorial write is idempotent by the no-change rule.
- **Unchanged:** the anchor rules (the card precedes the title clip's first kept span, or the chapter's first
  surviving segment when cuts remove it; no card for a chapter with no surviving segment). A `card` on a chapter
  that ends up with no included clip stays in the document and draws nothing.

## Risks / Trade-offs

- **The package count is three, not two** (`reel`, `render`, `event`). The `event/` parts are a plan field with its
  pass-through and the editorial merge; both are small and neither could live elsewhere (the decorator sees only the
  plan; the editorial write path is `event/editorial.py`). Splitting them would leave a document field the engine
  cannot yet read, or a render that cannot see its field, so they stay together; this is the one place the
  two-package limit is exceeded, and it is named rather than hidden.
- **Whole-archive staleness for a text change.** Accepted under D-C8 and unavoidable under Principle IV; the cost is
  one re-render per event the user chooses to make current.
- **Two changes bump the same constant.** `title-card-fonts` and this change both write `RENDER_GRAPH_VERSION`; the
  second to merge conflicts on one line and takes the next number. The supervisor sequences it.
- **`look.title_card` replaces, not merges, across project and event.** An event that sets `look.title_card` loses the
  project's whole map (existing shallow merge). Per-card overrides do not have that problem. Not changed here; it
  will surprise an editor that shows "event style" and is worth a follow-up.
- **`video` fails a render** until `title-card-over-video`. Nothing writes it until the API and editor land, so it
  can only come from a hand-edited file or a config default, where the loud error is the right answer.
- **A font typo in `card.font_family` loads and fails at render**, because the loader cannot see the registry.
  The API's draft validation (`title-card-write-api`) is where it is caught before saving.
