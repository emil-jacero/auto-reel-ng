## MODIFIED Requirements

### Requirement: Default output directory sits outside the project root

When neither `-o/--output` nor `config.yaml`'s `output` is set, the output directory SHALL default to
the sibling folder `<parent>/<root-name>-output` of the project root (for example, project root
`/mnt/MOL/videos/sorted` → `/mnt/MOL/videos/sorted-output`). It MUST NOT default to a path inside the
project root: the ingest layouts walk the project root's subfolders, so rendered movies filed into year
folders there would be scanned back in as events. `render`, `scan`, `enqueue`, `adopt-renders`, the worker
and the API service SHALL all resolve the same default. An explicitly configured output directory (`-o/--output` or
`config.yaml`'s `output`) is used as given, unless it equals or lies inside the directory the layout walks, which every
command refuses (capability `project-config`, requirement "The output directory never lies inside the
walked root"): the command prints `error: output directory <output> is inside the walked root <root>;
choose a folder outside it, for example <root>-output`, exits non-zero, and walks, renders and writes
nothing. An output that lies inside the project root but outside a distinct `input` directory is
honoured.

#### Scenario: Default output is a sibling of the project root
- **WHEN** `render /data/videos/sorted` runs with no `-o` and no `output` in `config.yaml`
- **THEN** movies are written under `/data/videos/sorted-output/`, and nothing is created inside
  `/data/videos/sorted/` except event sidecars

#### Scenario: Rendered year folders are never scanned as events
- **WHEN** `render` has written `sorted-output/2024/Midsommar.mp4` using the default output directory and
  `scan` then runs over the same project root
- **THEN** no event named `2024` or containing `Midsommar.mp4` is reported

#### Scenario: Explicit output is honored
- **WHEN** `render <root> -o <root>-movies` runs
- **THEN** movies are written under `<root>-movies/` as given

#### Scenario: Explicit output inside the walked root is refused
- **WHEN** `render <root> -o <root>/out` runs, with `<root>/2024/2024-07-20 - A/a.mp4` and an earlier
  `<root>/out/2024/2024-07-20 - A.mp4`
- **THEN** the command prints the error above to stderr and exits 1, no event is enumerated (so no
  `ERROR  2024: no date: folder name has a year only (2024)` line for the output's year folder appears),
  and no file is written under `<root>`

#### Scenario: Scan refuses the same output
- **WHEN** `scan <root> -o <root>/out` runs with `--layout flat`
- **THEN** it exits 1 with the same error, and `out` is never listed as an event

#### Scenario: The output equals the walked root
- **WHEN** `render <root> -o <root>` runs
- **THEN** it exits 1 with the error naming both paths

#### Scenario: Output inside the project root but outside the input directory
- **WHEN** `config.yaml` sets `input: media` and `render <root> -o <root>/out` runs
- **THEN** the walk root is `<root>/media`, the output is allowed, and movies are written under
  `<root>/out/`
