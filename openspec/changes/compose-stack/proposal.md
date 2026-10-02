## Why

GUI v1 has merged: chapters, cuts, cross-chapter drag, the movie player and clip preview. Testing it still
takes several manual steps. The tester starts a Postgres container, runs `alembic upgrade head`, builds
`web/dist` in a `node:22` container, and runs `auto-reel serve` and `auto-reel worker` by hand. They must also
remember never to point either one at `auto-reel-media/`, which is a shared fixture. The user asked for
"a docker-compose with the server and a worker, and link in the auto-reel-media", so that one command brings
up a stack they can test.

The repo already holds the start of HLD §4.12. That section has **D-1**: "the container bundles
jellyfin-ffmpeg", pinned, ffmpeg ≥ 7.1 asserted. **D-7** says "ship Postgres in the compose/deployment
stack". There is also a `Containerfile`. The R0 spike (`spike-compose/`, findings in the session's
`research/compose-spike.md`) showed that this Containerfile **cannot be built**, for two reasons:

- `FROM jellyfin/jellyfin-ffmpeg:latest` does not exist on any registry. Jellyfin ships jellyfin-ffmpeg only
  as `.deb` packages.
- `ENTRYPOINT ["python3", "-m", "auto_reel_ng"]` fails with "No module named auto_reel_ng.__main__".

Even once built, the image would serve no web client. `web/dist` is not in the image (§4.10: "deferred to §6
phase 11"), and for a normal pip install `api/app.py` `web_dist_dir()` resolves to
`<site-packages>/web/dist`, which does not exist.

This change is **the first, local-only slice of HLD §6 phase 11 (Packaging)**. It delivers a working image
plus a compose stack for testing on the developer's own machine. Nothing is published.

**§8.12** ("single image, all vendors") is still open, and this change narrows its scope around it. It
covers AMD/Intel VAAPI through `/dev/dri` passthrough, plus a CPU-only override. NVIDIA (`--gpus`, CUDA
userspace) and a published image are out of scope. The spike adds one data point to §8.12, recorded in the
HLD: jellyfin-ffmpeg8 bundles its own libva and the `radeonsi`, `iHD` and `i965` VA drivers, so no host VA
driver or Mesa package is needed in the image.

## What Changes

- **The `Containerfile` builds, and the image it produces works.**
  - Base: `debian:trixie-slim`. Trixie is needed because Python ≥ 3.13 is required and trixie ships 3.13.
  - ffmpeg: `jellyfin-ffmpeg8`, pinned through `ARG JELLYFIN_FFMPEG_VERSION=8.1.3-1-trixie` and installed
    from the Jellyfin apt repo.
  - A multi-stage `node:22` build produces `web/dist`.
  - The package is installed editable in `/app`, so `web_dist_dir()` finds `/app/web/dist` with no code
    change.
  - The entrypoint becomes `ENTRYPOINT ["auto-reel"]`.
  - `/usr/lib/jellyfin-ffmpeg` goes first on `PATH`, so the bundled `vainfo` names the GPU.
  - The Python dependencies are installed in their own layer before the source is copied, so a source edit
    rebuilds quickly.
  - A new `.dockerignore` keeps `data/`, `.env`, `.git`, `.venv`, `web/node_modules`, `web/dist` and the
    non-runtime trees (`experiments/`, `docs/`, `openspec/`, `tests/`) out of the build context. It is
    `.dockerignore` rather than `.containerignore` because the docker-compose client behind `podman compose`
    reads only `.dockerignore`. Measured in review: with `.containerignore` it uploaded 629 MB of `data/`,
    and with `.dockerignore` 418 B.
- **A repo-root `compose.yaml` (project `auto-reel-stack`) runs the stack.**
  - `db` is Postgres 16. It is not published, has a `pg_isready` healthcheck and keeps its data in a named
    volume.
  - `migrate` runs `alembic upgrade head` once the db is healthy.
  - `seed` runs once and builds the scratch library.
  - `server` runs `auto-reel serve`, published on `127.0.0.1:${AR_PORT:-8132}`.
  - `worker` runs `auto-reel worker`, with `/dev/dri` passed through.
  - `server` and `worker` start only after both `migrate` and `seed` have exited 0. Both use
    `restart: unless-stopped`.
  - `server` builds the image with `pull_policy: build`, and the other services use the same tag with
    `pull_policy: never`. Every `up` therefore runs the checked-out code (a cached rebuild), and nothing
    tries to pull the local tag.
- **auto-reel-media is linked in read-only and never written or relabeled.**
  - It is mounted `:ro` at `/media/auto-reel-media`, with `security_opt: [label=disable]` on the services
    that mount it. `:z`/`:Z` is never used.
  - `seed` builds a writable **scratch library** under `./data/library`:
    - one folder per fixture event, holding **absolute symlinks** to the clips and a **real copy** of
      `reel.yaml`;
    - the `samples/` clips as event `2025/2025-01-15 - Provklipp`;
    - the MPEG-4 Part 2 legacy render as an event of its own, `2025/2025-01-16 - Gammal rendering`.
  - Re-running `seed` never overwrites an edit. `seed --reset` wipes the scratch library and outputs.
  - Movies go to `./data/library-output`, and thumbnails and the Mesa shader cache go to `./data/cache`.
- **The CPU-only override is `compose.cpu.yaml`.** It sets `devices: !reset []` and runs
  `worker … --device cpu`, for a host without `/dev/dri`.
- **The new `.env.example`** holds `AR_PORT`, `AR_MEDIA_DIR`, `AR_DATA_DIR` and `AR_DB_PASSWORD`, all dev
  defaults with no secrets. `.gitignore` gains `/data/` and `/.env`.
- **Ports.** The only host port is `127.0.0.1:${AR_PORT:-8132}`. It does not collide with the dev database
  on 5432 (Postgres is not published) or with an ad hoc `auto-reel serve` on 8080. `AR_PORT` in `.env`
  changes it.
- **The new `scripts/seed_compose_library.py`** is stdlib only and is baked into the image. It ships with
  `tests/test_seed_compose_library.py`.
- **Docs.**
  - README gets a section "Run the stack with compose": build, up, open, logs, down, reset, the CPU override
    and GPU notes.
  - The HLD gets:
    - **D-17** (local compose stack);
    - in §4.12, the facts on how jellyfin-ffmpeg is obtained;
    - a pre-publish warning that `jellyfin-ffmpeg8` 8.1.3 bundles `libfdk_aac`;
    - the §4.10 `web/dist` line updated;
    - a §6 phase 11 status note.

## Non-goals

- **No published image**, registry push or release. D-1 requires a GPL source offer for a published image.
  The spike also found that `jellyfin-ffmpeg8` 8.1.3 bundles `libfdk_aac`, which goes against D-1's "never
  bundle the nonfree/fdk-aac variant in a published image". That has to be settled before anything is
  published, and it is recorded in the HLD as a blocker.
- **No NVIDIA path** (`nvidia-container-toolkit`, `--gpus`, CUDA) and no answer to §8.12 beyond the VAAPI
  data point above.
- **No engine or API code change.** In particular, `web_dist_dir()` gets no env override (design,
  "How web/dist reaches the server").
- **No fix for the VAAPI MPEG-4 Part 2 failure.** radeonsi cannot decode MPEG-4 Part 2, and normalize has no
  software-decode + `hwupload` fallback, so on the GPU profile the whole event fails. The seed isolates that
  clip in its own event, so it fails alone and is reported as failed (Principle I). The fix is a follow-up in
  `render/`/`accel/`.
- **No fix for the non-monotonic job progress** during the "re-encoding copied segments" pass. That is a
  follow-up.
- **No restart after a host reboot.** `restart: unless-stopped` covers crashes. A reboot needs
  `podman-restart.service`, which the README tells the user how to enable. Nothing on the host is changed.
- **No rootful Docker support or testing.** Rootful Docker would write root-owned files under `./data`. It
  is documented as untested.
- **No exposure beyond loopback.** The API has no authentication, so the GUI port binds `127.0.0.1` only.
- **No RDNA4 verification.** The host has a Radeon 860M (RDNA 3.5), not the RX 9070 XT that `CLAUDE.md`
  names. RDNA4 VAAPI is inferred from Mesa 26.0.8 and still needs a run on that card.

## Capabilities

### New Capabilities

- `container-stack`: what the local container image and compose stack guarantee:
  - the image builds from the repo with a pinned jellyfin-ffmpeg and serves the web client;
  - the stack starts in order (db healthy → migrate, seed → server + worker);
  - the GUI is on loopback;
  - the fixture is mounted read-only and never relabeled, behind an idempotent scratch library with a reset;
  - the worker gets GPU passthrough with a CPU-only override;
  - edits and job history survive `down`/`up`.

### Modified Capabilities

None. `headless-cli`, `api-service` and `web-app` behaviour is unchanged. The stack runs the existing
`serve`, `worker` and `alembic` commands as they are.

## Impact

- **Baseline:** written against `main` at `fed5065`.
- **Packages:** none under `auto_reel_ng/`.
  - New files: `compose.yaml`, `compose.cpu.yaml`, `.env.example`, `.dockerignore`,
    `scripts/seed_compose_library.py`, `tests/test_seed_compose_library.py`.
  - Changed: `Containerfile`, `.gitignore`, `README.md`, `docs/high-level-design.md`.
- **CLI vs API (Principle V):** neither changes. The stack is a client of the existing `serve`, `worker`,
  `enqueue` and `jobs` commands.
- **Complexity (Principle VII):**
  - The seed script is about 90 lines of stdlib. It is the smallest way to give the GUI a writable library
    without writing to the fixture: the GUI writes `reel.yaml` and the render writes
    `<event>/.auto-reel/cache/`, so a read-only library cannot work. The existing `scripts/make_dev_library.py` does not fit,
    because it cuts copies, needs the database and a worker, and rebuilds its library from scratch on every
    run (design, "The seed").
  - `label=disable` is the one way the spike found to read a `user_home_t` directory without relabeling it.
- **Dependencies:** no Python dependency is added.
  - New base images: `docker.io/library/debian:trixie-slim`, `docker.io/library/node:22` (build stage only)
    and `docker.io/library/postgres:16-alpine`.
  - The apt repo `repo.jellyfin.org/debian` provides `jellyfin-ffmpeg8`. That is the D-1 binary, obtained the
    only way Jellyfin ships it.
- **Rendered output:** the engine is unchanged, so there is no `RENDER_GRAPH_VERSION` bump. Inside the image
  the engine identity carries ffmpeg 8.1.3-Jellyfin rather than the host's ffmpeg, so a movie rendered on the
  host would show as stale in the stack. That is the staleness contract working as designed, and the seeded
  scratch library starts with no renders anyway, because the seed never copies the fixture's `.auto-reel/`.
  Fingerprint inputs are unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change and no Alembic migration. The stack's own database
  starts empty and is migrated by `migrate`.
- **Image:** 521 MB, first build about 1 m 45 s (spike, `localhost/auto-reel-ng:spike`).
- **Size (Principle VIII):** one capability (new), no engine package, and 10 tasks:
  - one baseline;
  - one for the image;
  - one for the seed and its test;
  - two for compose;
  - three end-to-end verification tasks;
  - one for docs;
  - the validation gates.

  The files touched are packaging files at the root, plus `scripts/` and `tests/` for the seed.
