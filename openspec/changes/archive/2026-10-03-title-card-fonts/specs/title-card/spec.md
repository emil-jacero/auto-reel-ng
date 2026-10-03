## ADDED Requirements

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

## MODIFIED Requirements

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
