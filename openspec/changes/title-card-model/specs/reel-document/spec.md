## MODIFIED Requirements

### Requirement: Structure and properties are normalized apart

The schema SHALL keep editorial structure separate from per-clip properties. `chapters` SHALL be an ordered
list of chapters, each with a name, an ordered list of clip references (identities only) and an optional
`card` (see "A chapter may carry a title card"). `clips` SHALL be
a map keyed by clip identity whose values hold per-clip properties (`trims`, `title`, `rotate`, `exclude`). A
clip reference in `chapters` and its property entry in `clips` SHALL share the same identity key.

#### Scenario: Chapter holds references, not properties
- **WHEN** a chapter lists a clip
- **THEN** the chapter entry is the clip's identity reference and any trims/title/exclude for that clip live in the `clips` map under the same identity

#### Scenario: Properties survive a reorder
- **WHEN** a clip's position is changed within or across chapters but its `clips` entry is untouched
- **THEN** its trims and other properties remain associated with it unchanged

#### Scenario: A card belongs to its chapter, not to a clip
- **WHEN** a clip is moved from a chapter that has a `card` into another chapter
- **THEN** neither chapter's `card` changes, and the clip's `clips` entry is untouched

## ADDED Requirements

### Requirement: A chapter may carry a title card

A chapter MAY carry an optional `card` mapping: the content and look of the title card the movie shows at the
start of that chapter. The default chapter (name `""`) holds the opening card. Every key of `card` is optional,
and the loader SHALL accept exactly these keys with exactly these values:

- `title`: a string that is not blank. Absent means the card's heading is the chapter's name, or the event title
  for the default chapter.
- `subtitle`: a string, which MAY be empty. Absent or empty means the card has no subtitle line.
- `duration`: a finite number of seconds, at least `0.5` and at most `60`.
- `background`: `black` or `video`.
- `font_family`: a string that is not blank. Whether it names a font the renderer can use is decided when the
  card is rendered, not when the document loads.
- `title_font_size` and `subtitle_font_size`: integers from `8` to `400` inclusive.
- `text_color`: `#` followed by six hexadecimal digits, in either case.
- `position`: `center`, `top` or `bottom`.

A `card` that is absent or `null` means no overrides, and an empty mapping is valid and means the same. The
loader SHALL fail loud, with the parse error naming the location `chapters[i].card.<key>`, on a `card` that is not
a mapping, a key outside this set (the error SHALL list the allowed keys), a value of the wrong type (a boolean is
never a number), a number outside its range or not finite, a blank `title` or `font_family`, a malformed
`text_color`, and a key whose value is `null`: a key that is present must have a value, and an unquoted
`text_color: #FFD700` is a YAML comment, so it reads as `null` and the error SHALL say to quote the colour. It
SHALL NOT drop, clamp or correct a value. An unknown key on a chapter outside `card` remains
ignored, as before.

The document's editorial hash SHALL include a chapter's `card` only when the chapter has one, so that a document
with no card hashes exactly as it did before this requirement.

#### Scenario: A full card loads
- **WHEN** the default chapter sets `card: {title: Midsommar 2024, subtitle: Hos mormor, duration: 5, background: black, font_family: DejaVu Serif, title_font_size: 110, subtitle_font_size: 50, text_color: "#FFD700", position: bottom}`
- **THEN** the document loads and `chapters[0].card` holds each of those values

#### Scenario: An empty or null card means no overrides
- **WHEN** a chapter sets `card: {}` or `card:` with nothing after it
- **THEN** the document loads, and the chapter has no overrides

#### Scenario: An unknown key fails loud and lists the allowed keys
- **WHEN** a chapter's card sets `titel: Hej`
- **THEN** loading fails with a parse error naming `chapters[0].card.titel` and listing `title`, `subtitle`, `duration`, `background`, `font_family`, `title_font_size`, `subtitle_font_size`, `text_color` and `position`

#### Scenario: A duration out of range fails loud
- **WHEN** a card sets `duration: 0.1`, or `duration: 600`, or `duration: .inf`
- **THEN** each fails with a parse error naming `chapters[i].card.duration`

#### Scenario: A boolean is not a number
- **WHEN** a card sets `title_font_size: true` or `duration: false`
- **THEN** loading fails with a parse error naming that key

#### Scenario: A font size outside 8 to 400 fails loud
- **WHEN** a card sets `subtitle_font_size: 7` or `title_font_size: 401`
- **THEN** loading fails naming that key, and a card setting `8` and `400` loads

#### Scenario: A blank title fails loud
- **WHEN** a card sets `title: "   "` or `font_family: ""`
- **THEN** loading fails naming that key

#### Scenario: A malformed colour fails loud
- **WHEN** a card sets `text_color: red` or `text_color: "#FFF"` or `text_color: "#GG0000"`
- **THEN** loading fails naming `chapters[i].card.text_color`

#### Scenario: An unquoted colour fails loud instead of reading as unset
- **WHEN** a card is written `text_color: #FFD700` without quotes
- **THEN** loading fails naming `chapters[i].card.text_color`, saying the value is null and that a `#RRGGBB` colour must be quoted

#### Scenario: A null value fails loud
- **WHEN** a card sets `subtitle:` with nothing after it
- **THEN** loading fails naming `chapters[i].card.subtitle`

#### Scenario: A card on the wrong type fails loud
- **WHEN** a chapter sets `card: [title, Hej]`
- **THEN** loading fails naming `chapters[i].card` and saying it must be a mapping

#### Scenario: The font family is not checked against fonts at load
- **WHEN** a card sets `font_family: Not A Real Font`
- **THEN** the document loads

#### Scenario: A document without a card hashes as before
- **WHEN** a document has no `card` on any chapter
- **THEN** its editorial hash equals the hash computed for the same document before cards existed, and a document that adds a card has a different hash

### Requirement: A chapter's card is carried by every writer

Every writer of `reel.yaml` SHALL keep a chapter's `card`. The round-trip writer SHALL keep the comments and the key
order inside a loaded `card` byte-stable, and a document built from typed fields SHALL write the `card` of a chapter
that has one between its `name` and its `clips`, setting only the keys that have a value.

The editorial write operation SHALL treat a chapter's `card` in the desired state as follows. A chapter with no
`card` key, or a `card` of `null`, SHALL leave the chapter's existing card exactly as written, comments included,
so a client that does not know cards cannot erase one by omission. A `card` that is an empty mapping SHALL remove
the chapter's card. A `card` with keys SHALL be merged into the chapter's existing `card` node key by key: a key the
desired card does not have is removed, a key whose value is equal is left as written (its comment and the spelling
of its number stay), a key whose value differs takes the new value, and a `None` value stands for an absent key. A
card on a chapter that had none SHALL be written directly after the chapter's `name`. The merged document SHALL
be validated, with the rules above, before anything is written, so an invalid card is refused and the file is left
untouched. A chapter renamed in the same write SHALL keep its card (it is paired with its node by its clips), a
chapter dropped from the desired state SHALL drop its card, and a save that changes nothing SHALL write nothing.

#### Scenario: A commented card round-trips byte-stable
- **WHEN** a `reel.yaml` whose default chapter has a `card:` with a comment on its `subtitle` line is loaded and written back unchanged
- **THEN** the output is byte-for-byte the input

#### Scenario: A typed-field document writes its card between name and clips
- **WHEN** a document built in memory has a chapter with `card.title` and `card.duration` set
- **THEN** the written chapter lists `name`, then `card` with `title` and `duration` only, then `clips`

#### Scenario: A write that omits the card keeps it
- **WHEN** an editorial write sends the chapters of an event whose default chapter has a commented `card`, with no `card` key on any chapter
- **THEN** the file's `card` lines, comments included, are unchanged, and a write that changes nothing else writes nothing

#### Scenario: A null card keeps it
- **WHEN** an editorial write sends `card: null` for a chapter that has a card
- **THEN** the chapter's card is left as written

#### Scenario: An empty card removes it
- **WHEN** an editorial write sends `card: {}` for a chapter that has a card
- **THEN** the persisted chapter has no `card` key

#### Scenario: A changed card is merged key by key
- **WHEN** a chapter's card is `{title: A, duration: 5  # keep}` and the desired card is `{title: B, duration: 5, subtitle: S}`
- **THEN** the persisted card has `title: B`, `duration: 5` with its comment unchanged, and `subtitle: S`

#### Scenario: A key left out of the desired card is removed
- **WHEN** a chapter's card is `{title: A, subtitle: S}` and the desired card is `{title: A}`
- **THEN** the persisted card has only `title`

#### Scenario: A new card goes after the name
- **WHEN** an editorial write gives a chapter with `name` and `clips` a card
- **THEN** the persisted chapter lists `name`, then `card`, then `clips`

#### Scenario: A renamed chapter keeps its card
- **WHEN** an editorial write renames a chapter that has a card and sends the same clips under the new name
- **THEN** the persisted chapter has the new name and the same card

#### Scenario: A deleted chapter drops its card
- **WHEN** an editorial write omits a chapter that had a card
- **THEN** the persisted document has no trace of that card

#### Scenario: An invalid card is refused and nothing is written
- **WHEN** an editorial write sends a card with `duration: 0`
- **THEN** the write raises the parse error naming `chapters[i].card.duration`, and the file's bytes and modification time are unchanged
