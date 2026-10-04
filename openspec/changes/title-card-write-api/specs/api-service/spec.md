## MODIFIED Requirements

### Requirement: Editorial write endpoint
The service SHALL expose `PUT /api/v1/events/{event_id}/reel`, accepting the full desired editorial state
for the event (metadata, ordered chapters and their clips, per-clip properties, each chapter's optional title-card overrides, `ignore`, and the `look`
override) and delegating to the engine's editorial-write operation. The endpoint MUST contain no editorial
logic of its own: it parses and validates the request shape, calls the operation, and maps outcomes to
responses. The response SHALL echo the persisted document together with the event's resulting staleness
verdict, so a client needs no follow-up read. Read endpoints remain read-only and unaffected.

The request body is the event's **complete** editorial state (D-E2), not a patch. A section the body omits
SHALL be treated as empty, so omitting `ignore`, chapters, clip properties or `look` clears them; the one
exception is a chapter's `card`, which when absent or `null` keeps the card `reel.yaml` already holds (see
the chapter title-card requirement). A client
preserves everything it does not mean to change by submitting what the editorial read returned, with its edit
applied.

The endpoint SHALL answer each failure by its cause, and nothing SHALL be written for any of them:

- **404:** an unknown event.
- **400, a validation problem body:** a submitted state that is invalid, including one the engine refuses
  because the event would lack a real date or a title, or would carry a future date. That refusal SHALL
  carry the unusable-metadata failure kind.
- **412:** a stale precondition (see the conditional write requirement).
- **502, the scan-failure problem body:** an event whose **existing** document cannot be read. It SHALL name
  the event and carry the same failure kind the events reads would report, and SHALL NOT be a 400, because
  the request was not at fault.
- **502, naming the operating-system error:** a validated document the filesystem refuses to store, for
  example a read-only mount. It is never an unshaped server error.

The existing document SHALL be read before the write on every request, with or without a precondition, so
the two paths answer a broken file identically. The endpoint SHALL publish each of these responses, the
shared problem body shape, and the `ETag` header of a successful write in the service's OpenAPI schema.

#### Scenario: Save persists and echoes
- **WHEN** `PUT /api/v1/events/{event_id}/reel` sends a state with a changed title and clip order
- **THEN** the event's `reel.yaml` reflects it, and the response echoes the persisted document with the
  event's new staleness verdict

#### Scenario: Save makes the event stale over the API
- **WHEN** a previously fresh event is saved via the write endpoint
- **THEN** the response's verdict — and a subsequent `GET /api/v1/events/{event_id}` — report it stale
  citing the editorial component, while no job has been created

#### Scenario: Invalid state is rejected loudly
- **WHEN** the submitted state fails validation
- **THEN** the response is a validation problem body naming the offending part, and the event's `reel.yaml`
  is unchanged

#### Scenario: Unknown event
- **WHEN** the endpoint targets an event id that does not resolve under the configured project root
- **THEN** the response is 404 with a problem body

#### Scenario: Saving an unmodified document is a no-op
- **WHEN** the document echoed by the write endpoint is submitted back unmodified via the write endpoint
- **THEN** the persisted `reel.yaml` is byte-for-byte unchanged, and the response echoes the same document
  again (the write endpoint's read and write models are the same shape; the read endpoints' detail model
  stays read-only and is deliberately not a write body)

#### Scenario: Omitting a section clears it
- **WHEN** an event's `reel.yaml` holds an `ignore` list, and a body with a changed title but no `ignore` is
  written
- **THEN** the persisted document has no `ignore` list; and when the same edit is written with the `ignore`
  list the editorial read returned, the list is preserved

#### Scenario: A write onto a broken file is the file's fault
- **WHEN** a body is written, without `If-Match`, to an event whose existing `reel.yaml` cannot be parsed
- **THEN** the response is the scan-failure 502 naming the event, with the unparseable-`reel.yaml` failure
  kind, not a 400, and the file is untouched

#### Scenario: A state that would leave the event undated is refused
- **WHEN** a body for the event folder `2024/Blandat`, whose name has no date, omits `metadata.date`
- **THEN** the response is 400 with the unusable-metadata failure kind and a detail stating the missing
  date, and `reel.yaml` is unchanged

#### Scenario: Saving to a read-only archive
- **WHEN** a valid body is written to an event on a filesystem mounted read-only
- **THEN** the response is a 502 problem body whose detail names the read-only error, the file is
  unchanged, and the response is not an unshaped server error

#### Scenario: The schema publishes the write's responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the write declares its 400, 404, 412 and 502 responses in the shared problem body shape, and the
  `ETag` header of its 200 response

## ADDED Requirements

### Requirement: The editorial document carries each chapter's title card
The editorial body that `PUT /api/v1/events/{event_id}/reel` accepts, that `GET /api/v1/events/{event_id}/reel`
returns and that the write echoes SHALL carry, for each chapter, an optional `card`: the chapter's title-card
**overrides**, with the keys and meaning the engine's card mapping has in `reel.yaml` - `title`, `subtitle`,
`duration`, `background` (`black` or `video`), and the style overrides `font_family`, `title_font_size`,
`subtitle_font_size`, `text_color` and `position`. Every field is optional and a field that is `null` or absent
means "no override": the card inherits it, and nothing is written for it. A chapter whose `card` has no field set
(`{}`, or only `null` fields) has no card entry in `reel.yaml`; a chapter whose `card` is absent or `null` keeps the
card `reel.yaml` already holds (the engine's rule, so a client that does not know cards cannot erase one). The default chapter `""` holds the opening card. The event-wide card
style is the existing `look.title_card` part of `look`; `look` stays an opaque map in the body.

The endpoint SHALL contain no card validation of its own: the request shape (known keys, JSON types) is checked
by the body model, and every value rule - ranges, the allowed `background` and `position` values, and that
`font_family` is a family of the font registry - is the engine's, so a card is refused over the API exactly as
the engine refuses it in a loaded document. A submitted card the engine refuses SHALL be a **400** problem body
whose `detail` names the chapter and the field (for example `card.duration` of chapter `Dag 2`), as for any
other invalid submitted state; a `look.title_card` the engine refuses SHALL be refused the same way, naming the
`look.title_card` field. A card key the body model does not know is rejected, naming the key. Nothing is written
for any of them.

The write SHALL keep every property the editorial write already has for the rest of the document: comments and
key order of `reel.yaml` survive, an unmodified echo submitted back leaves the file byte-for-byte unchanged, and
a write that changes a card makes the event stale through the editorial component without enqueuing a job. A
chapter's `card` follows the chapter by name: renaming a chapter in a write carries its card to the new name,
and a write that sends a chapter's `card` with no field set removes that chapter's card.

#### Scenario: A card is saved and returned
- **WHEN** `PUT …/reel` sends a chapter `Dag 2` with `card: {title: "Dag två", subtitle: "Stranden", duration: 5,
  background: "video", font_family: <a registry family>}`
- **THEN** the chapter's entry in `reel.yaml` holds those five card keys and no others, the response echoes the
  same `card` (the unset fields `null`), and `GET …/reel` returns it

#### Scenario: The title can be overridden without renaming the chapter
- **WHEN** a write sets `card.title` on the chapter `Dag 2` and leaves the chapter's `name` unchanged
- **THEN** the chapter is still named `Dag 2` in `reel.yaml`, the clips' order is untouched, and the card carries
  the new title

#### Scenario: The opening card lives on the default chapter
- **WHEN** a write sets `card: {subtitle: "Sommaren 2024"}` on the chapter named `""`
- **THEN** `reel.yaml` holds the card on the default chapter, and no other chapter gains one

#### Scenario: An invalid card is refused, naming the field
- **WHEN** a write sends `card.duration` as `-3`, or `card.font_family` as a family that is not in the registry,
  or `card.background` as `"gradient"`
- **THEN** the response is 400 with a problem body whose `detail` names the chapter and that field, and
  `reel.yaml` is byte-for-byte unchanged

#### Scenario: An unknown card key is rejected
- **WHEN** a write sends `card: {colour: "#fff"}`
- **THEN** the response rejects the body, naming `colour`, and `reel.yaml` is unchanged

#### Scenario: An invalid event-wide card style is refused
- **WHEN** a write sends `look: {title_card: {title_font_size: "big"}}`
- **THEN** the response is 400 with a problem body naming `look.title_card.title_font_size`, and `reel.yaml` is
  unchanged

#### Scenario: Saving an unmodified document with cards is a no-op
- **WHEN** an event whose `reel.yaml` holds a commented chapter with a `card` is read with `GET …/reel` and the
  body is written back unmodified
- **THEN** `reel.yaml` is byte-for-byte unchanged and the comments survive

#### Scenario: A card edit makes the event stale and enqueues nothing
- **WHEN** a fresh, rendered event is saved with a changed `card.title`
- **THEN** the response's staleness verdict is stale citing the editorial component, and no job exists

#### Scenario: A card follows its chapter's rename
- **WHEN** a write renames the chapter `Dag 2` to `Dag två` and sends the same `card` on it
- **THEN** the persisted chapter `Dag två` holds the card, and `Dag 2` no longer exists

#XX
- **WHEN** a chapter with a persisted card is written with no `card`
- **THEN** the persisted chapter has no card entry, in keeping with the body being the complete state

### Requirement: The event detail reports each chapter's resolved title card and the event's card style
`GET /api/v1/events/{event_id}` SHALL report, for every chapter it lists (the default chapter `""` included),
a `card`: the **resolved** card the engine would draw for that chapter, and, for the event, a `title_card`: the
event's resolved card style. The values are produced by the engine's own resolution of the document (the layering
of the project `config.yaml` `look`, the event `look.title_card` and the chapter's own overrides, and the defaulting
of the title and subtitle), not by the service and not by the client.

A chapter's `card` SHALL carry concrete, never null, values: `title`, `subtitle`, `duration` (seconds),
`background` (`black` or `video`) and the effective style `font_family`, `title_font_size`,
`subtitle_font_size`, `text_color` and `position`. `title` is the chapter's override when it has one, else the
chapter's name, and for the default chapter the event's title; `subtitle` is the override, else empty (a card shows no date or
place unless the author wrote it). The event's `title_card` SHALL carry `duration`, `background` and the same
five style fields, as the event-wide layer leaves them before any chapter overrides. A font family no override
named is the bundled default. The report SHALL be probe-free and read-only, and SHALL add no database read.
It describes what a render would draw; it does not claim the render draws a card for a chapter whose clips all
turn out not to play, which only a render knows.

When the event-wide `look.title_card` cannot be resolved (a hand-edited value the engine refuses), the detail
SHALL still answer 200 so the author can open the event and correct it: `title_card` and every chapter's `card`
are `null` and `title_card_error` names the field and the reason. Absence of an error is `title_card_error:
null`. A single chapter whose own card the engine cannot resolve (a hand-written `font_family` outside the
registry) has `card: null` and a `card_error` naming the field, while the other chapters are reported. Nothing is fabricated in place of a card that cannot be resolved.

#### Scenario: An event with no card configuration reports the defaults
- **WHEN** the detail of an event whose `reel.yaml` has no `look.title_card` and no `card` is read, in a project
  whose `config.yaml` has none either
- **THEN** every chapter's `card` carries the documented defaults, the title is the chapter name (the event title
  for the default chapter), the subtitle is empty, the font is `DejaVu Sans`, and `title_card` carries the same
  defaults

#### Scenario: An override wins over the event style and the project style
- **WHEN** the project `config.yaml` sets `look.title_card.font_family` to one registry family, the event's
  `reel.yaml` sets another, and the chapter `Dag 2` sets a third on its `card`
- **THEN** that chapter's `card.font_family` is the third, another chapter's is the second, and `title_card`
  reports the second

#### Scenario: The title can differ from the chapter name
- **WHEN** the chapter `Dag 2` has `card: {title: "Dag två"}`
- **THEN** its resolved `card.title` is `Dag två` and the chapter is still listed as `Dag 2`

#### Scenario: The opening card shows no date or place
- **WHEN** an event with a date, a location and a description and no card on the default chapter is read
- **THEN** the default chapter's `card.title` is the event title and its `card.subtitle` is empty

#### Scenario: A chapter that the document does not list still has a card
- **WHEN** a clip on disk belongs to a chapter the document does not list, so the detail adds that chapter
- **THEN** the added chapter has a resolved `card` from the defaults, with its name as the title

#### Scenario: A bad event style does not lock the event
- **WHEN** a hand-edited `look.title_card.position` holds a value the engine refuses
- **THEN** the detail is 200, `title_card` and every `card` are `null`, and `title_card_error` names
  `look.title_card.position`, while the clips, chapters and staleness are reported as usual

#### Scenario: The read is read-only and probe-free
- **WHEN** the detail is read
- **THEN** no file is written under the event, no subprocess is started, and the request reads no more of the
  media than it did before this requirement

### Requirement: The font registry is listed over REST
The service SHALL expose `GET /api/v1/fonts`, returning the engine's font registry in its order: for each
bundled font its `family` (the name `card.font_family` and `look.title_card.font_family` accept), its
`display_name`, its `weights` (the weights the registry bundles, as integers) and `default`, true for exactly the
one font the engine uses when none is named. The list SHALL be produced by the registry module the schema and the
renderer read, so the three cannot disagree, and SHALL not read the disk, the project or the database. It SHALL be
read-only, need no event, and publish its response model in the OpenAPI schema.

#### Scenario: The list is the registry
- **WHEN** `GET /api/v1/fonts` is requested
- **THEN** the response is 200 and lists every registry family exactly once, in the registry's order, each with
  its display name and weights, and exactly one entry has `default: true`, the bundled default

#### Scenario: Every listed family is accepted by the write
- **WHEN** each listed `family` is used as a chapter's `card.font_family` in a write
- **THEN** every write succeeds

#### Scenario: A family that is not listed is refused by the write
- **WHEN** a write uses a family that the list does not hold
- **THEN** the write is refused as an invalid card, naming `font_family`

### Requirement: A draft title card is previewed as a PNG
The service SHALL expose `POST /api/v1/events/{event_id}/title-card/preview`, which renders **one title card**
from a posted draft and returns it as `image/png`. The request body holds the draft only: `chapter` (the
chapter's name, `""` for the opening card, default `""`), `card` (the same overrides as the editorial `card`,
default none), `style` (optionally a draft of the event-wide `look.title_card`; when absent, the event's saved
one) and `event_title` (optionally the draft event title the opening card defaults to; when absent, the saved
document's title). The draft is resolved by the same resolution the event detail and a render use, layered on the
project `config.yaml` and the event's saved `look`, so what is previewed is what the draft would render once saved.
The image SHALL be produced by the same renderer a render uses, at the event's target resolution (the resolved
`look.target_resolution`, 1920x1080 by default), and for a `background` of `black` it SHALL be the card the
render draws on black. For a `background` of `video` it SHALL be the text on a **fully transparent**
background, because the card is drawn over the clip's picture; the client composes it over the frame.

The operation SHALL be read-only and light: it writes nothing (not `reel.yaml`, not a cache, not a file under the
event), starts no subprocess and no ffmpeg, reads no media, takes no job slot and reads no database row. The
response SHALL be `Cache-Control: no-store`. It SHALL answer each failure by cause:

- **404:** an unknown event.
- **400, a problem body naming the field:** a draft the engine refuses (including a font family not in the
  registry), the same refusal the editorial write gives.
- **422:** a body that is structurally malformed or breaks a size bound (see the bounded requirement).
- **502:** an event whose existing `reel.yaml` cannot be read (the scan-failure problem body with its failure
  kind, as the other event routes), or a card that cannot be drawn although the draft is valid (a registry
  font the host's font configuration does not resolve), naming the cause.
- **503:** the drawing backend (Cairo/Pango) is not available in this process, naming it; or the service is busy
  (see the bounded requirement).

The endpoint SHALL publish its 200 as `image/png`, its failures in the shared problem body shape, and the request
and response models in the OpenAPI schema.

#### Scenario: A black card is previewed at the target resolution
- **WHEN** a draft for the chapter `""` with `card: {title: "Sommaren", subtitle: "2024"}` is posted to an event
  whose resolved target resolution is 1920x1080
- **THEN** the response is 200 `image/png`, a 1920x1080 image, whose bytes equal the image the render's card
  renderer produces for that card, and the headers carry `Cache-Control: no-store`

#### Scenario: The target resolution of the event decides the size
- **WHEN** the event's `look` sets `target_resolution: [1280, 720]`
- **THEN** the preview is a 1280x720 image

#### Scenario: A video card is the text on transparency
- **WHEN** a draft with `card: {background: "video"}` is posted
- **THEN** the image is RGBA and its corner pixel is fully transparent, while a pixel in the text is opaque

#### Scenario: The draft is previewed without saving it
- **WHEN** a draft title differs from the one in `reel.yaml` and is posted
- **THEN** the image shows the draft title, and `reel.yaml` is byte-for-byte unchanged afterwards

#### Scenario: The draft event style overrides the saved one
- **WHEN** a draft posts `style: {text_color: "#ff0000"}` for an event whose saved style has a white text
- **THEN** the image's text is red, and a draft without `style` shows the saved colour

#### Scenario: The opening card defaults to the draft event title
- **WHEN** the default chapter's draft carries no `card.title` and the request sends `event_title: "Nytt namn"`
- **THEN** the image shows `Nytt namn`; with no `event_title` it shows the saved title

#### Scenario: Each registry font renders
- **WHEN** a draft names each registry family in turn
- **THEN** each response is a PNG, and no two families produce byte-identical images for the same text

#### Scenario: An invalid draft names the field
- **WHEN** a draft posts `card.title_font_size` as `0`, or `font_family` as `"Comic Sans"`
- **THEN** the response is 400 with a problem body naming that field, and no image is produced

#### Scenario: An unknown event is 404
- **WHEN** the preview targets an event id that does not resolve under the project root
- **THEN** the response is 404 with a problem body

#### Scenario: A broken reel.yaml is the file's fault
- **WHEN** the event's existing `reel.yaml` cannot be parsed
- **THEN** the response is the scan-failure 502 with the unparseable-`reel.yaml` failure kind, not a 400

#### Scenario: The drawing backend is missing
- **WHEN** the process cannot load Cairo/Pango
- **THEN** the response is 503 whose detail names the backend, never an unshaped 500

#### Scenario: The preview touches nothing
- **WHEN** a preview is requested with the dev library's cache directories, `reel.yaml` and the job table observed
- **THEN** none of them changed, and no subprocess was started

### Requirement: The title-card preview is bounded
The preview endpoint SHALL bound what one caller can make the service do. The draft's free text SHALL be limited:
`card.title` and `event_title` to 200 characters and `card.subtitle` to 400; a longer one is a 422 naming the
field. The image SHALL be only the size the event renders at, never a size the request chooses. The service SHALL
draw at most two previews at once per process; a request that cannot start within 10 seconds of waiting for a
slot SHALL be answered 503 with `Retry-After` and a problem body, and SHALL not be drawn after it was answered.
Waiting SHALL NOT occupy a worker thread, so the rest of the API keeps answering while previews wait. The bounds
belong to the preview request only: the editorial `card` the write accepts has no length limit of its own beyond
the engine's, so a document that is longer than the preview allows still round-trips.

#### Scenario: An over-long title is refused
- **WHEN** a draft's `card.title` is 201 characters
- **THEN** the response is 422 naming `card.title`, and nothing is drawn

#### Scenario: A document longer than the preview bound still saves
- **WHEN** a write sets a 300-character `card.title`
- **THEN** the write succeeds (the engine sets no such limit), and only the preview refuses that title

#### Scenario: A busy service says so
- **WHEN** two previews are drawing and a third waits longer than the wait limit
- **THEN** the third is answered 503 with `Retry-After`, and the other API routes answer while it waits

#### Scenario: Previews of the same draft share no state
- **WHEN** two different drafts are posted at the same time
- **THEN** each response shows its own draft
