## MODIFIED Requirements

### Requirement: The image builds from a checkout and carries the pinned ffmpeg

The repository's `Containerfile` SHALL build with rootless podman from a clean checkout, meaning one with no
`web/dist`, no `web/node_modules` and no `.venv`. The resulting image SHALL contain:

- the `auto-reel` command as its entrypoint
- `jellyfin-ffmpeg8` at the version pinned by the `JELLYFIN_FFMPEG_VERSION` build argument, which the engine
  resolves as its default ffmpeg and ffprobe and accepts as ≥ 7.1 (D-1)
- the Cairo/Pango runtime and the bundled title-card font set from `fonts/` (DejaVu Sans and the registered
  families), resolvable through the engine's fontconfig
- the web client built from `web/`

The image SHALL NOT need a host-installed VA driver or Mesa package. The build context SHALL exclude the
stack's data directory, `.env`, `experiments/`, `.venv`, `.git`, `web/node_modules` and `web/dist`. That
holds both for the context `podman build` reads and for the context `podman compose` sends.

#### Scenario: The image runs the CLI by default
- **WHEN** the image is built and run with `--help` as its only argument
- **THEN** it prints the `auto-reel` usage that lists its subcommands and exits 0, rather than failing with
  "No module named auto_reel_ng.__main__"

#### Scenario: The bundled ffmpeg is the pinned build
- **WHEN** the image's default ffmpeg reports its version
- **THEN** it reports `8.1.3-Jellyfin` for the default `JELLYFIN_FFMPEG_VERSION=8.1.3-1-trixie`, and the
  engine accepts it as ≥ 7.1

#### Scenario: Scratch data is not sent to the build
- **WHEN** `./data/library-output` holds an 848 MB rendered movie and `podman compose build server` runs
- **THEN**:
  - the reported `Sending build context` is a few MB, not hundreds
  - the image contains no `/app/data`

#### Scenario: Every registered font resolves in the image
- **WHEN** the image is built and its engine verifies the bundled fonts
- **THEN** every registered family resolves at every weight it declares, and a build in which one does not resolve fails

#### Scenario: A card renders in a bundled family in the image
- **WHEN** a title card is rendered in the image with `font_family` set to a registered family other than DejaVu Sans
- **THEN** the card is drawn in that family and no host or Debian font is involved

