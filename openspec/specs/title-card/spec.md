# title-card Specification

## Purpose

Give auto-reel its title cards: parse a typed title-card configuration from the resolved `look.title_card`
sub-map at render time, render an event's title card to an RGBA image at the target resolution via Cairo +
Pango (real typography with fail-loud fontconfig font resolution, outline/shadow/background/fades), and
register a `title` decorator that inserts a synthetic title segment before each chapter's title clip with text
composed from event metadata and the chapter name. The renderer is a single reusable seam so a render and a
future GUI preview produce the same image.

## Requirements

### Requirement: Title-card config parsed from `look`

The engine SHALL parse a typed title-card configuration from the resolved `look.title_card` sub-map at render
time, without requiring `reel-document` to validate or model it. The config SHALL cover font family, font
sizes, text color, outline and shadow, background (color and opacity), fade-in/fade-out durations, total card
duration, and text position. Absent fields SHALL take documented defaults. The engine SHALL clamp the combined
fade durations to the total card duration so a card never fades for longer than it is shown. A malformed value
(wrong type/shape) SHALL fail loud with a typed error rather than be silently ignored.

#### Scenario: Defaults applied when `look.title_card` is silent
- **WHEN** a title decorator runs and `look.title_card` omits the fade and duration fields
- **THEN** the parsed config uses the documented default durations and the card still renders

#### Scenario: Fades clamped to card duration
- **WHEN** the configured fade-in plus fade-out exceeds the configured card duration
- **THEN** the parsed config reduces the fades so their sum does not exceed the duration

#### Scenario: Malformed config fails loud
- **WHEN** `look.title_card` carries a value of the wrong type for a known field
- **THEN** the engine raises a typed error naming the field rather than rendering with a guessed value

### Requirement: Title card rendered to an image at the target resolution

The engine SHALL render a title card to an RGBA image sized to the target spec's resolution, using Cairo +
Pango for text layout (centering, wrapping within a column, kerning/interline) so titles, dates, locations,
and descriptions are laid out without manual glyph positioning. The card text SHALL be composed from the event
`metadata` (title, date, location, description) for the movie's first/default card, and SHALL use the chapter
name as the heading for a non-default chapter's card. The renderer SHALL honor the parsed config's outline,
shadow, and background settings. The renderer SHALL be a single reusable entry point so the same image is
produced for a render and for a future GUI preview.

#### Scenario: Card image matches the target resolution
- **WHEN** the target spec is 1920×1080 and a title card is rendered
- **THEN** the produced image is a 1920×1080 RGBA image

#### Scenario: Card text composed from event metadata
- **WHEN** the default chapter's card is rendered for an event with a title, date, and location
- **THEN** the rendered card contains the event title and the formatted date/location text

#### Scenario: Non-default chapter card uses the chapter name
- **WHEN** a card is rendered for a chapter other than the default
- **THEN** the card's heading is that chapter's name

### Requirement: Fail-loud font resolution

The engine SHALL resolve the configured font family through fontconfig, as configured by the engine itself from the
bundled font set, before rendering and SHALL raise a typed error if the family does not resolve at the weight the
card is drawn at, naming the requested family and the bundled default. It SHALL NOT allow a silent font
substitution to produce a card in an unintended typeface, including a face of another weight than the one asked
for. A bundled default font family SHALL be available so rendering succeeds without any per-event font configuration
and without any system font installed.

#### Scenario: Unresolved font family fails loud
- **WHEN** the configured font family does not resolve through the engine's fontconfig
- **THEN** the engine raises a typed error naming the family rather than rendering in a substituted font

#### Scenario: A missing weight fails loud
- **WHEN** a registered family declares a weight whose font file is absent from the fonts directory and a card is drawn at that weight
- **THEN** the engine raises a typed error naming the family and the weight rather than drawing a synthesized bold

#### Scenario: Bundled default renders without configuration
- **WHEN** no font family is configured in `look.title_card`
- **THEN** the card renders using the bundled default font family, with no system font installed

### Requirement: Title decorator inserts a synthetic title segment

The engine SHALL register a `title` decorator (an inserter) selectable via `look.decorators`. When applied, it
SHALL insert one synthetic title segment for each chapter that resolved a title clip (the clip resolved as
`is_title`), carrying the producer reference, the resolved card duration, the look-derived card config, and the
chapter membership of the segment it precedes. The card SHALL be placed immediately before the title clip's
first surviving segment (for a clip with partial cuts, its first kept span). When cuts remove the title clip
entirely, so that it contributes no segment, the card SHALL instead be placed immediately before the first
surviving source segment of the same chapter, so the chapter still opens with its card. When every clip of the
chapter is cut away, so that the chapter has no source segment, no card SHALL be inserted for it. A chapter
that resolved no title clip SHALL get no card. When `look.decorators` does not include `title` (or is absent),
no title segment SHALL be produced and behavior SHALL be unchanged.

#### Scenario: Title segment inserted before a chapter's title clip
- **WHEN** the `title` decorator is applied to a plan whose default chapter has a title clip
- **THEN** the segment list contains a synthetic title segment immediately before that chapter's title clip, carrying that chapter's name

#### Scenario: Per-chapter title segments
- **WHEN** the `title` decorator is applied to a plan with two chapters that each have a title clip
- **THEN** a synthetic title segment is inserted before each chapter's title clip

#### Scenario: No title decorator means no card
- **WHEN** `look.decorators` does not include `title`
- **THEN** the segment list contains no synthetic title segment

#### Scenario: Partially cut title clip keeps its anchor
- **WHEN** the chapter's title clip has a cut span over its first seconds and a kept span after it
- **THEN** the synthetic title segment is placed immediately before that clip's first kept span, exactly as for an uncut clip

#### Scenario: Fully cut title clip moves the card to the next clip
- **WHEN** a chapter is `[a.mp4 (title, 10 s), b.mp4]` and a cut span covers all of `a.mp4`
- **THEN** the chapter's synthetic title segment is placed immediately before `b.mp4`'s first segment, carrying that chapter's name and heading, and the chapter has exactly one card

#### Scenario: Fully cut title clip with later surviving clips in several chapters
- **WHEN** two chapters each have a title clip, the first chapter's title clip is wholly cut, and the second chapter is untouched
- **THEN** the first chapter's card moves to its next surviving segment, the second chapter's card stays before its title clip, and each card still carries its own chapter's name

#### Scenario: Chapter cut away entirely gets no card
- **WHEN** every clip of a chapter, including its title clip, is wholly cut
- **THEN** no synthetic title segment is produced for that chapter and the chapter is absent from the segment list, as it is without the decorator

#### Scenario: Chapter without a title clip gets no card
- **WHEN** no clip of a chapter resolved as the title clip
- **THEN** no synthetic title segment is produced for that chapter, whether or not its clips are cut

### Requirement: A bundled font set

The repository SHALL bundle, under a top-level `fonts/` directory, the fonts a title card may be drawn in: DejaVu
Sans (the default) and eight further families, one for each of these roles: a clean sans, a geometric sans, a
humanist sans, a serif, a display serif, a condensed, a handwritten script and a monospace. Every further family
SHALL be licensed under the SIL Open Font License. Every family SHALL ship its license text in `fonts/` as a `.txt`
file, as static font files with one file per weight it declares, and SHALL cover Basic Latin, Latin-1 and the Latin Extended-A letters of the Nordic, Western and Central European alphabets and Turkish (the set of the scenario below; Esperanto and Maltese letters and ligatures such as Ĳ are outside it, because most families omit them).
The directory SHALL hold a `fonts.conf` that lists only that directory, and SHALL NOT exceed 8 MB in total.

#### Scenario: The set is complete and licensed
- **WHEN** the files under `fonts/` are compared with the registry
- **THEN** every registered family has its font files and a license text there, DejaVu Sans plus eight others are
  registered, and no font file in the directory is unregistered

#### Scenario: Swedish and Central European text has every glyph
- **WHEN** "Åsa, Örjan och Märta åt smörgås på café" and the Latin Extended-A letters of the Polish, Czech, Slovak, Hungarian, Croatian, Slovenian, Romanian, Turkish, Latvian, Lithuanian and Estonian alphabets and French Œ and Ÿ are laid out in each registered family at each declared weight
- **THEN** Pango reports no unknown glyph

#### Scenario: Every registered family renders a card
- **WHEN** one card is rendered for each registered family at the target resolution
- **THEN** every render succeeds, none is blank, and no two families produce the same pixels for the same text

### Requirement: One font registry

The engine SHALL hold the bundled fonts in one registry module that does not import Cairo or Pango. For each family
the registry SHALL give the family name as fontconfig knows it, a display name, its role, the weights it declares,
its font files with a SHA-256 each, and its license file. The registry SHALL keep DejaVu Sans as the default
family, SHALL look a family up ignoring case, and SHALL raise a typed error that names the registered families for
a name it does not hold. The schema, the preview API and the GUI SHALL read the family list from this registry and
not keep their own.

#### Scenario: Lookup ignores case and returns the canonical entry
- **WHEN** the registry is asked for "dejavu sans"
- **THEN** it returns the entry whose family is "DejaVu Sans"

#### Scenario: An unknown family names the choices
- **WHEN** the registry is asked for "Comic Sans"
- **THEN** it raises a typed error that names "Comic Sans" and lists every registered family

#### Scenario: A changed font file is noticed
- **WHEN** a bundled font file's bytes differ from the SHA-256 the registry records
- **THEN** the registry test fails, and its message says that a changed font is a render input and
  `RENDER_GRAPH_VERSION` must be bumped with it

#### Scenario: The registry loads without the drawing backend
- **WHEN** the registry module is imported in a process where Cairo and Pango are not importable
- **THEN** the import succeeds and lists the families

### Requirement: The engine finds the bundled fonts itself

Before the first Pango font map of the process is created, the renderer SHALL point fontconfig at `fonts/fonts.conf`
by setting `FONTCONFIG_FILE`, so that the bundled directory is the only font source of the renderer, whatever the
host has installed and whatever `FONTCONFIG_FILE` held. `AUTO_REEL_FONTS_DIR` SHALL move the directory. When the
directory or its `fonts.conf` does not exist, the renderer SHALL raise a typed error that names the path it looked
at. A host with no system font installed SHALL render every registered family.

#### Scenario: A host run needs no system install
- **WHEN** a card is rendered in a fresh process with `FONTCONFIG_FILE` unset and `font_family` "DM Serif Display"
- **THEN** the card renders in DM Serif Display, and `fc-list` under the engine's `fonts.conf` lists only the bundled families

#### Scenario: A host font cannot shadow or fill in
- **WHEN** a host has a family installed that the registry does not hold and the config asks for it
- **THEN** the config is refused as an unregistered family, and a glyph missing from a bundled family is not drawn from the host's font

#### Scenario: The fonts directory can be moved
- **WHEN** `AUTO_REEL_FONTS_DIR` names a copy of `fonts/` elsewhere
- **THEN** the renderer uses that copy, and a path with no `fonts.conf` raises a typed error naming the path

### Requirement: The configured font family is a registered family

`parse_title_card_config` SHALL accept a `font_family` only when it names a registered family (ignoring case) and
SHALL keep the registry's canonical spelling. An unregistered family SHALL fail loud with a typed error that names
the field `look.title_card.font_family`, the value and the registered families. An absent or null `font_family`
SHALL mean the default family.

#### Scenario: A registered family is accepted and canonicalised
- **WHEN** `look.title_card.font_family` is "dm serif display"
- **THEN** the parsed config's family is "DM Serif Display"

#### Scenario: An unregistered family is refused at parse time
- **WHEN** `look.title_card.font_family` is "Papyrus"
- **THEN** parsing raises a typed error naming `look.title_card.font_family`, "Papyrus" and the registered families, before any rendering

#### Scenario: Silent means the default
- **WHEN** `look.title_card` has no `font_family`
- **THEN** the parsed config resolves to "DejaVu Sans"
