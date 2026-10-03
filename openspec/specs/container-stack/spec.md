# container-stack Specification

## Purpose

Bring up a local, testable auto-reel-ng with one command. A container image holds the engine, the pinned
jellyfin-ffmpeg and the built web client. A compose stack runs Postgres, the migration, the API service and
a render worker against a writable scratch library. That library links the shared `auto-reel-media` fixture
read-only and never writes to it.

## Requirements

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

### Requirement: The service in the image serves the web client

`auto-reel serve` run from the image SHALL serve the built web client at `/`, and it SHALL do so with no
setting, flag or environment variable. The service SHALL log the directory it serves the client from.

#### Scenario: The GUI loads on the stack's port
- **WHEN** the stack is up with the default `AR_PORT`
- **THEN** `GET http://127.0.0.1:8132/` returns 200 with the client's `index.html`, and the server log
  contains `serving the built web client from /app/web/dist`

### Requirement: One command starts the stack in dependency order

From a repository checkout, `podman compose up -d` SHALL build the image from that checkout, reusing
cached layers. It SHALL NOT try to pull the stack's own image. It SHALL then start these services in this
order:

1. a Postgres database
2. a one-shot migration that brings the database to the Alembic head, started only once the database
   reports healthy
3. a one-shot seed of the scratch library, which does not wait for the database
4. the API service and one render worker, started only after both the migration and the seed have exited
   with status 0

If the migration or the seed exits non-zero, the API service and the worker SHALL NOT start.

The stack SHALL publish exactly one host port: the GUI, bound to `127.0.0.1` on `AR_PORT` (default 8132).
The database SHALL NOT be published on the host. The API service and the worker SHALL restart after a
crash, and the one-shot services SHALL NOT restart. Every path, the port and the database password SHALL
default to the documented dev values when no `.env` file exists.

#### Scenario: First start from a clean state
- **WHEN** no container, volume or `./data` directory of the `auto-reel-stack` project exists, and
  `podman compose up -d` runs
- **THEN**:
  - the migration logs the upgrade to head after the database is healthy
  - the seed exits 0
  - the API service and the worker then start
  - the GUI answers on `127.0.0.1:8132`
  - `podman port` lists no host port for the database

#### Scenario: The next up runs the changed code
- **WHEN** the stack is up, a file under `auto_reel_ng/` changes, and `podman compose up -d` runs again
- **THEN**:
  - the image is rebuilt, and the dependency layer comes from the cache
  - `server` and `worker` are recreated from the new image
  - no line of the output tries to pull `localhost/auto-reel-ng:compose`

#### Scenario: The dev database is not disturbed
- **WHEN** the dev Postgres container `auto-reel-ng-dev-db` already holds host port 5432, and the stack
  starts
- **THEN** the stack starts without a port conflict, and `auto-reel-ng-dev-db` keeps running untouched

#### Scenario: A worker that crashes comes back
- **WHEN** the worker's main process is killed with SIGKILL
- **THEN** the worker container is restarted, and its restart count becomes 1

### Requirement: The auto-reel-media fixture is linked read-only and never changed

The stack SHALL mount the `auto-reel-media` directory (default `../auto-reel-media`, overridable through
`AR_MEDIA_DIR`) read-only, at the same path in every service that mounts it. It SHALL NOT relabel the
directory's SELinux context. No action of the stack SHALL create, modify or delete a file under that
directory, nor change any file's mode or context. That covers seeding, re-seeding, reset, scanning, rendering,
thumbnailing, playing in the GUI and saving in the GUI.

#### Scenario: A GUI save and a render leave the fixture untouched
- **WHEN** a marker file is created outside the fixture, and then the stack is started, an event is
  rendered, both players play and a GUI title edit is saved
- **THEN**:
  - `find auto-reel-media -newer <marker>` prints nothing
  - a sorted listing of paths, sizes, mtimes and modes is identical to the one taken before
  - every entry's SELinux context is still `user_home_t`

#### Scenario: A write through the mount is refused
- **WHEN** a process in the worker tries to create a file under `/media/auto-reel-media`
- **THEN** it fails with "Read-only file system"

### Requirement: The seed builds an idempotent scratch library over the fixture

The one-shot seed SHALL build a writable `year-event` library under `AR_DATA_DIR` (default `./data`), at
`library/`. It SHALL also create its output directory `library-output/`. Specifically:

- For each `input/<year>/<event>/` folder of the fixture, the seed SHALL create `library/<year>/<event>/`.
  It SHALL hold a **real copy** of the event's `reel.yaml` and mirror every other entry of the event: a
  subdirectory, such as a chapter folder, as a real directory, and a file as an **absolute symlink** to it.
- The fixture's clips under `samples/` SHALL be linked as the event `2025/2025-01-15 - Provklipp`. The one
  exception is the files whose names start with `legacy-`, which SHALL be linked as the event
  `2025/2025-01-16 - Gammal rendering`.
- The seed SHALL NOT carry over the fixture's `.auto-reel/` cache directory, at any depth.
- Every symlink SHALL resolve to the same fixture file in the seed, the API service and the worker.

Re-running the seed SHALL create only missing folders and links, and SHALL copy a `reel.yaml` only into an
event that has none. It SHALL never overwrite, delete or re-link an existing entry. Run with `--reset`, the
seed SHALL first empty the scratch library and its output directory, then seed again.

If the fixture is not mounted, or has no `input/` directory, the seed SHALL exit non-zero with a message
naming the missing path.

#### Scenario: The fixture event becomes a writable scratch event
- **WHEN** the seed runs against the fixture event `input/2024/2024-06-27 - grillning med grannar/`, which
  holds `s1710001.mp4` … `s1710004.mp4`, `reel.yaml` and `.auto-reel/`
- **THEN**:
  - `library/2024/2024-06-27 - grillning med grannar/` holds four symlinks whose targets are
    `/media/auto-reel-media/input/2024/2024-06-27 - grillning med grannar/s171000N.mp4`
  - it holds a regular-file `reel.yaml` that is byte-identical to the fixture's
  - it holds no `.auto-reel/`

#### Scenario: A chapter folder is mirrored, not dropped
- **WHEN** a fixture event holds `s1710001.mp4` and a chapter folder `Kvällen/` with `s1710002.mp4`
- **THEN** the scratch event holds a symlink `s1710001.mp4` and a real directory `Kvällen/` holding a
  symlink `s1710002.mp4`, each pointing at its fixture file

#### Scenario: Samples are split so the MPEG-4 Part 2 render fails alone
- **WHEN** the seed runs against `samples/`, which holds nine sample clips plus
  `legacy-render-mpeg4-mp3.mp4`
- **THEN** `2025/2025-01-15 - Provklipp` links the nine clips and `2025/2025-01-16 - Gammal rendering` links
  only `legacy-render-mpeg4-mp3.mp4`

#### Scenario: Re-seeding keeps a GUI edit
- **WHEN** a GUI save has changed the scratch `reel.yaml` title of `Provklipp`, and the stack is brought
  `down` and `up` again
- **THEN** the seed reports every `reel.yaml` and link as kept and none as new, and the edited title is
  still in the scratch `reel.yaml`

#### Scenario: Reset restores the fixture's editorial state
- **WHEN** `podman compose down -v` runs, then `podman compose run --rm seed --reset`, then
  `podman compose up -d`
- **THEN**:
  - the scratch `reel.yaml` files equal the fixture's again
  - `library-output/` is empty
  - the job list is empty

#### Scenario: Missing fixture fails loud
- **WHEN** `AR_MEDIA_DIR` names a directory that has no `input/`
- **THEN** the seed exits non-zero with a message naming `/media/auto-reel-media/input`, and the API service
  and the worker do not start

### Requirement: The worker renders on the passed-through GPU, with a CPU-only override

By default the stack SHALL pass the host's `/dev/dri` to the worker, and to no other service. The worker
SHALL then select its profile by the engine's own capability detection and self-test (D-3, D-4). It SHALL
log the selected profile and render node at start.

The repository SHALL ship a CPU-only override file. With that file, the worker SHALL get no device and run
with `--device cpu`.

A render job's result SHALL be the engine's own result: a job whose event cannot be normalized on the
selected profile SHALL be reported as failed, and it SHALL NOT affect other events' jobs.

#### Scenario: An AMD render node gives a VAAPI render
- **WHEN** the host exposes `/dev/dri/renderD128` (AMD Radeon 860M, radeonsi), the stack is up, and
  `2025/2025-01-15 - Provklipp` is enqueued. Its clips include 4K50 H.264 at 119 Mb/s, PCM audio, a portrait
  1080×1920 clip, a rotate-90 HEVC MOV and 720p.
- **THEN**:
  - the worker logged `profile=amd render_node=/dev/dri/renderD128` at start
  - the job ends `done`
  - the movie in `library-output/` reports `h264_vaapi` in its encoder tag

#### Scenario: A codec without VAAPI decode fails its own event only
- **WHEN** `2025/2025-01-16 - Gammal rendering` (MPEG-4 Part 2 + MP3) and `Provklipp` are both enqueued on
  the VAAPI profile
- **THEN** the `Gammal rendering` job ends `failed`, its error names the failing normalize, and the
  `Provklipp` job still ends `done`

#### Scenario: A host without a usable GPU renders on the CPU
- **WHEN** the stack is started with the CPU-only override, and `2025/2025-01-16 - Gammal rendering`
  (MPEG-4 Part 2 + MP3), which fails on the VAAPI profile, is enqueued
- **THEN** the worker logs `profile=cpu render_node=None`, the job ends `done`, and the movie reports
  `libx264` in its encoder tag

### Requirement: Stopping the stack is clean and keeps state

`podman compose stop` and `podman compose down` SHALL stop the API service and the worker through their
graceful shutdown, and each SHALL exit with status 0. `down` without `-v` SHALL keep the database volume
and everything under `AR_DATA_DIR`, so a later `up` shows the same edits, renders and job history. `down -v`
SHALL remove the database volume.

#### Scenario: Down and up keep edits and renders
- **WHEN** an event has been rendered and a GUI edit saved, then `podman compose down` and
  `podman compose up -d` run
- **THEN**:
  - the edit is still shown
  - the rendered movie still plays
  - the job list still holds the earlier jobs
  - the edited event shows as needing a render because of its editorial change

#### Scenario: Stop exits zero
- **WHEN** `podman compose stop server worker` runs while the stack is idle
- **THEN** the worker logs that it stopped cleanly, the server logs `Application shutdown complete`, and
  both containers exit with status 0
