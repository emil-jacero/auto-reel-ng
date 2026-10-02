## Context

See proposal.md, "Why". The relevant state of `main` at `fed5065`:

- **`Containerfile`.** It has never been built in CI, and it cannot be built: its base image does not exist,
  and its entrypoint names a missing `__main__` (spike, finding 1).
- **`api/app.py` `web_dist_dir()`** returns `Path(__file__).resolve().parent.parent.parent / "web" / "dist"`.
  Its docstring reserves phase 11 as the only reason to edit it, and says "an installed wheel finds no
  directory here and simply serves no client, which is a supported state".
- **The runtime's default binaries.** `FfmpegRuntime` already resolves `/usr/lib/jellyfin-ffmpeg` as the
  bundled default after explicit arguments and `AUTO_REEL_NG_FFMPEG`/`AUTO_REEL_NG_FFPROBE`. No engine change
  is needed for the image's ffmpeg.
- **The engine writes into the library.** A render writes `<event>/.auto-reel/cache/render-manifest.json`,
  and it writes a generated `reel.yaml` into an event that has none. In the spike, a render created one in
  both sample events. The output default is the sibling `<root>-output` directory, and thumbnails go to
  `$XDG_CACHE_HOME/auto-reel/thumbnails/`.
- **The fixture.** `auto-reel-media/` holds:
  - one event, `input/2024/2024-06-27 - grillning med grannar/`: `s1710001.mp4` … `s1710004.mp4` (uniform
    1080p50 H.264, 809 MiB), a version-0 `reel.yaml` with no `look.title_card` (so no title card), and a
    `.auto-reel/` cache;
  - `samples/`: ten clips, one of which is `legacy-render-mpeg4-mp3.mp4`;
  - an empty `output/`.

  Its SELinux context is `unconfined_u:object_r:user_home_t:s0`.
- **The host.**
  - Rootless podman 5.8.7 with crun. SELinux is enforcing.
  - `podman compose` hands off to docker-compose v5.5.1 through the user `podman.socket`.
  - The only GPU is an **AMD Radeon 860M (RDNA 3.5, Krackan)** on `/dev/dri/renderD128`, mode `0666
    root:render`.
  - The dev database `auto-reel-ng-dev-db` holds host port 5432. Port 8080 is the user's ad hoc `serve`.
  - `podman-restart.service` (user) is disabled.

All "measured" or "proved" statements below come from the R0 spike run on 2026-10-02 in
`auto-reel-project/spike-compose/`. Its files are `Containerfile.spike`, `compose.yaml`, `compose.cpu.yaml`,
`seed.py`, `captest.py`, `pw/check.py` and `logs/`. The findings note is the session's
`research/compose-spike.md`, and its key lines are quoted below. Anything the spike did not run is marked
**(not proven)** and has a verify step in tasks.md.

## Goals / Non-Goals

**Goals:**
- `podman compose up -d` from the repo root, starting from nothing, gives a GUI on `127.0.0.1:8132`, a
  worker that renders on the GPU, and a scratch library whose edits persist.
- Every file the stack writes lands under `AR_DATA_DIR` or in the `pgdata` volume. Nothing is written to
  `auto-reel-media/`, and nothing in it is relabeled.
- No engine or API code changes. Every file this change adds is packaging, the seed script and its test, or
  docs.

**Non-Goals:**
- A wheel that carries `web/dist`, an env override for `web_dist_dir()`, or a published image (Decisions,
  "How web/dist reaches the server").
- Any software fallback for codecs that VAAPI cannot decode (proposal, Non-goals).
- A server healthcheck, a reverse proxy, TLS or auth. The port binds loopback only.

## Decisions

### File layout: everything at the repo root

```
Containerfile          (rewritten)
.dockerignore          (new)  read by BOTH podman build and the docker-compose client; see below
compose.yaml           (new)  project name: auto-reel-stack
compose.cpu.yaml       (new)  CPU-only override
.env.example           (new)  AR_PORT=8132, AR_MEDIA_DIR=../auto-reel-media, AR_DATA_DIR=./data, AR_DB_PASSWORD=auto_reel_ng
scripts/seed_compose_library.py   (new, baked into the image at /app/scripts/)
tests/test_seed_compose_library.py (new)
.gitignore             (+ /data/, /.env)
```

**Why the root and not `deploy/`.** `Containerfile` is already at the root. `podman compose` looks for
`compose.yaml` in the working directory and reads `.env` from the same directory. Relative bind sources
resolve against the compose file's directory, so `../auto-reel-media` names the sibling fixture with no
`-f`. A `deploy/` folder would force `-f deploy/compose.yaml` on every command, and would mean
`../../auto-reel-media`. The project name `auto-reel-stack` keeps its containers
(`auto-reel-stack-server-1`, …) and its volume (`auto-reel-stack_pgdata`) clearly apart from
`auto-reel-ng-dev-db` and the `auto-reel-ng-test-pg-*` containers.

### Image: Debian trixie + the Jellyfin apt package, editable install, web stage

The image follows `Containerfile.spike`, which the spike proved, with three small changes: `PATH` moves
into the image, the Python dependencies get their own cached layer, and the file gets comments. In outline:

```dockerfile
ARG JELLYFIN_FFMPEG_VERSION=8.1.3-1-trixie

FROM docker.io/library/node:22 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM docker.io/library/debian:trixie-slim
ARG JELLYFIN_FFMPEG_VERSION
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -d /etc/apt/keyrings \
    && curl -fsSL https://repo.jellyfin.org/jellyfin_team.gpg.key -o /etc/apt/keyrings/jellyfin.asc \
    && printf 'Types: deb\nURIs: https://repo.jellyfin.org/debian\nSuites: trixie\nComponents: main\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/jellyfin.asc\n' \
         > /etc/apt/sources.list.d/jellyfin.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        "jellyfin-ffmpeg8=${JELLYFIN_FFMPEG_VERSION}" \
        python3 python3-pip python3-gi python3-gi-cairo gir1.2-pango-1.0 \
        libcairo2 libpango-1.0-0 libpangocairo-1.0-0 fonts-dejavu \
    && fc-cache -f \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
# The bundled vainfo names the GPU in the worker's device list (accel devices.vainfo_name runs it from PATH).
ENV PATH=/usr/lib/jellyfin-ffmpeg:${PATH}
WORKDIR /app
# Dependency layer: only pyproject.toml plus stubs, so a source edit does not re-download every wheel.
COPY pyproject.toml /app/
RUN touch README.md && mkdir auto_reel_ng && touch auto_reel_ng/__init__.py \
    && python3 -m pip install --no-cache-dir --break-system-packages -e .
COPY . /app
COPY --from=web /web/dist /app/web/dist
ENTRYPOINT ["auto-reel"]
```

The existing comment block on Cairo/Pango/fontconfig is kept. A short header says:

- why the base is not a jellyfin-ffmpeg image (none exists);
- that the image is local-only and MUST NOT be published while the D-1 pre-publish blocker stands (Risks).

Spike evidence:

- "first build `real 1m45.5s`", "final image … **521 MB**".
- `pip` "Requirement already satisfied" for pycairo 1.27.0 and pygobject 3.50.0, so nothing is compiled.
- `ffmpeg version 8.1.3-Jellyfin`, asserted `(8, 1)` through `runtime.JELLYFIN_FFMPEG_DIR`.
- The package "declares **no Depends on libva or Mesa**: it bundles its own VA userspace".

The spike set `PATH` in compose. Setting it in the image is the same environment, so the worker's GPU name
does not depend on the compose file **(not proven; verified by the worker's device name in task 5.1)**.

**Layer order (SHOULD).** The stack rebuilds the image on every `up` (see "Compose services"), so a source
edit must not cost a full `pip` download. The spike ran `COPY . /app` before `pip install -e .`, so any file
change re-ran the 73 MB pip layer. The outline installs the dependencies against `pyproject.toml` and a stub
package first. The editable install writes a `.pth` that points at `/app`, so the real sources copied
afterwards are what gets imported, and the `auto-reel` console script resolves through it **(not proven;
task 2.1 verifies `--help` after the full copy, and that a source-only rebuild reuses the pip layer)**. If
hatchling's editable install does not resolve the later sources, the fallback is the spike's order
(`COPY . /app`, then `pip install -e .`), and the cost is a slower rebuild.

### Build context: `.dockerignore`, not `.containerignore`

The spike built with `podman build`, which reads `.containerignore`. The stack builds through
`podman compose`, which hands the build to the docker-compose v5.5.1 client. That client packs the context
itself, and it reads only `.dockerignore`. Measured in review on this host (a scratch project with a 600 MB
file under `data/`):

| ignore file | `Sending build context to Docker daemon` | `data/` in the image |
|---|---|---|
| `.containerignore` with `data/` | **629.3MB** | no (podman drops it server-side) |
| `.dockerignore` with `data/` | **418B** | no |

**Decision:** the ignore file is `.dockerignore`. buildah reads it when there is no `.containerignore`, so
`podman build` and `podman compose` exclude the same paths. A `.containerignore` would also shadow it for
`podman build`, so the repo MUST NOT have one. Excluded: `data/`, `.env`, `.git/`, `.venv/`, `.claude/`,
`.mypy_cache/`, `.pytest_cache/`, `**/__pycache__/`, `web/node_modules/`, `web/dist/`, plus `experiments/`,
`docs/`, `openspec/` and `tests/`, which the image never runs. That way a docs or spec edit does not rebuild
the image. Without this file, every `up` would send each rendered movie under `./data/library-output`
(848 MB for grillning alone) to the build.

**Added after the Phase 1 review (supervisor decision, 2026-10-02):** `README.md` (the dependency layer
installs against a stub `README.md`, which pyproject's `readme` needs; nothing reads it afterwards, so a
README edit no longer rebuilds the image and recreates `server`/`worker`; measured: `--help`, `pip show
auto-reel-ng` and the `auto-reel` entry point unchanged) and the coverage artifacts `.coverage`,
`.coverage.*`, `htmlcov/`, `coverage.xml` (a pytest run rewrote the 400 kB `.coverage` and so forced a
rebuild on the next `up`).

**Alternatives considered:**

- **`FROM jellyfin/jellyfin`** (the server image that contains jellyfin-ffmpeg). It is a whole media server,
  its distro is not ours to pin, and its Python may not be ≥ 3.13. Rejected.
- **Bookworm.** It ships Python 3.11, which is below `requires-python >= 3.13`. Rejected.
- **BtbN static `gpl` build.** D-1 names jellyfin-ffmpeg as the default, and BtbN builds do not bundle a VA
  driver tree. Rejected for this change.

### How web/dist reaches the server: editable install, no code change

The spike measured both ways:

- **Editable install.** "`auto_reel_ng.__file__` = `/app/auto_reel_ng/api/app.py`, so the function returns
  `/app/web/dist`, which exists. The server logs `serving the built web client from /app/web/dist`, and
  `GET /` returns 200."
- **Normal install.** "the function returns `/tmp/t/web/dist` and `is_dir()` is False."

**Decision:** an editable install in `/app`, with the web stage's output copied to `/app/web/dist`. There is
no change to `web_dist_dir()`.

**Rationale:**

- It is proven, and it needs zero code.
- It keeps this change free of any `auto_reel_ng/` package, and of any delta to `api-service`.
- `web_dist_dir()`'s docstring argues against a settings key: "exactly one correct answer per deployment and
  no operator ever chooses it", Principle VII. An `AUTO_REEL_NG_WEB_DIST` env var is the kind of
  operator-facing key the docstring rules out.

The price is that the image depends on `/app` staying the source tree. That holds for an image built from
this checkout and is stated in the Containerfile comment.

**Alternatives considered:**

- **(b) Env override in `web_dist_dir()`.** The spike called it "the cleaner contract". It is the right move
  once a *wheel* must carry the client, and that belongs to the phase 11 slice that publishes. Deferred.
- **(c) Ship `web/dist` as package data and resolve it with `importlib.resources`.** That changes the wheel
  build and `web_dist_dir()`, and nothing here needs it yet. Deferred to the same slice.

### SELinux: `label=disable` on the media-mounting services, never `:z`/`:Z`

Spike evidence:

```
$ podman run --rm -v $M:/media/auto-reel-media:ro … ls /media/auto-reel-media/samples
ls: cannot open directory '/media/auto-reel-media/samples': Permission denied
$ podman run --rm --security-opt label=disable -v $M:/media/auto-reel-media:ro … ; touch /media/auto-reel-media/x
touch: cannot touch '/media/auto-reel-media/x': Read-only file system
$ ls -dZ auto-reel-media  ->  unconfined_u:object_r:user_home_t:s0   (unchanged)
```

**Decision:** `security_opt: [label=disable]` goes on `seed`, `server` and `worker`, and the media mount is
read-only. `:z`/`:Z` MUST NOT appear anywhere on the media mount. `:z` would rewrite the context of the
user's directory tree, and `:Z` would also make it private to one container.

`migrate` mounts nothing and resets to `security_opt: []`, so it runs confined as `container_t`, as in the
spike. `db` stays confined with its named volume.

The data dirs are plain bind mounts. The spike found that "Missing bind-source dirs are created
automatically under the podman provider … owned by `emil`".

**Alternative considered:** setting the `container_file_t` context on the fixture by hand with `chcon`.
That changes the fixture's labels, so it was rejected for the same reason as `:z`.

### Media mount: read-only, and a missing fixture must not be created

The spike used short syntax (`…:/media/auto-reel-media:ro`). Short syntax also auto-creates a missing
source. With a wrong `AR_MEDIA_DIR`, that would quietly create an empty directory where the user expected
their fixture. The media mount therefore uses long syntax:

```yaml
- type: bind
  source: ${AR_MEDIA_DIR:-../auto-reel-media}
  target: /media/auto-reel-media
  read_only: true
  bind: {create_host_path: false}
```

**(not proven under the podman provider; task 4.2 verifies it).** If the provider still creates the
directory, the fallback is the spike's short syntax, `:ro` with no `z`. The seed's fail-loud check on
`input/` then stops the stack, and the README states the side effect. Either way the mount is read-only
and is never relabeled.

**Measured in task 4.2 (2026-10-02): the fallback applies.** Under docker-compose v5.5.1 on the podman
socket, `AR_MEDIA_DIR=<missing dir> podman compose run --rm seed` created `<missing dir>` empty although
`podman compose config` rendered `create_host_path: false`; the podman API does not honour it. So
`compose.yaml` uses the short syntax `${AR_MEDIA_DIR:-../auto-reel-media}:/media/auto-reel-media:ro`, with a
comment saying so. The seed then exits 1 naming `/media/auto-reel-media/input`, `up` leaves `server` and
`worker` in state Created (never started), and the README states the side effect.

### Compose services and start-up order

The structure is the spike's `compose.yaml`, which was measured:

> "The first `up -d` from a clean state took **5.6 s**. Seed and db start in parallel. Once db is
> 'Healthy', migrate runs. Server and worker start only after both seed and migrate have 'Exited' (0).
> Migrate logs `ce3faf27bcfd -> 8941c65cba0d -> 505f2d2c5ca1`; on later `up`s it is a no-op."

```yaml
name: auto-reel-stack

x-app: &app
  image: localhost/auto-reel-ng:compose
  environment:
    DATABASE_URL: postgresql+psycopg://auto_reel_ng:${AR_DB_PASSWORD:-auto_reel_ng}@db:5432/auto_reel_ng
    XDG_CACHE_HOME: /data/cache          # thumbnails + Mesa shader cache out of the container layer
    TMPDIR: /data/tmp                    # render scratch out of the container layer (see below)
  security_opt: [label=disable]
  volumes:
    - {type: bind, source: "${AR_MEDIA_DIR:-../auto-reel-media}", target: /media/auto-reel-media,
       read_only: true, bind: {create_host_path: false}}
    - ${AR_DATA_DIR:-./data}/library:/data/library
    - ${AR_DATA_DIR:-./data}/library-output:/data/library-output
    - ${AR_DATA_DIR:-./data}/cache:/data/cache
    - ${AR_DATA_DIR:-./data}/tmp:/data/tmp

services:
  db:        # postgres:16-alpine, pgdata volume, NOT published,
             # healthcheck pg_isready -U auto_reel_ng -d auto_reel_ng every 2 s x 30, restart unless-stopped
  migrate:   {<<: *app, entrypoint: [python3, -m, alembic, -c, /app/alembic.ini, upgrade, head],
              volumes: [], security_opt: [], depends_on: {db: {condition: service_healthy}}, restart: "no"}
  seed:      {<<: *app, entrypoint: [python3, /app/scripts/seed_compose_library.py], restart: "no"}
  server:    {<<: *app, build: {context: ., dockerfile: Containerfile},
              command: [serve, /data/library, --host, 0.0.0.0, --port, "8080"],
              ports: ["127.0.0.1:${AR_PORT:-8132}:8080"], depends_on: {migrate: ok, seed: ok}, restart: unless-stopped}
  worker:    {<<: *app, command: [worker, /data/library], devices: [/dev/dri:/dev/dri],
              depends_on: {migrate: ok, seed: ok}, restart: unless-stopped}
volumes: {pgdata: {}}
```

**Render scratch: `TMPDIR=/data/tmp` (added after the Phase 1 review, supervisor decision).** The render
writes its normalized segments into `tempfile.TemporaryDirectory(prefix="auto-reel-render-")`, which
defaults to `/tmp`, the container's writable layer. The Phase 1 run saw `/tmp/auto-reel-render-*` in the
Gammal error, against the Goal above. `TMPDIR=/data/tmp` plus a bind mount of `${AR_DATA_DIR}/tmp` puts it
on the host. The mount is what guarantees the directory exists (the provider creates a missing bind
source), which matters because Python's `tempfile` silently falls back to `/tmp` when `TMPDIR` is missing.
Measured: a Provklipp VAAPI render peaked at 616 MB in `./data/tmp/auto-reel-render-*`, the directory was
empty afterwards, and the worker's `/tmp` stayed empty (`podman diff` shows only mount points and `.pyc`).

In this outline, `ok` stands for `{condition: service_completed_successfully}`. `x-app` also carries
`pull_policy: never`, and `server` overrides it with `pull_policy: build`. `db` is the spike's service:

```yaml
  db:
    image: docker.io/library/postgres:16-alpine
    environment:
      POSTGRES_USER: auto_reel_ng
      POSTGRES_PASSWORD: ${AR_DB_PASSWORD:-auto_reel_ng}   # dev default; applied only when pgdata is created
      POSTGRES_DB: auto_reel_ng
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: {test: [CMD-SHELL, pg_isready -U auto_reel_ng -d auto_reel_ng], interval: 2s, timeout: 3s, retries: 30}
    restart: unless-stopped
```

`AR_DB_PASSWORD` is a dev default, not a secret: the database is reachable only on the project network.
Postgres applies it only when it initialises an empty `pgdata`, so changing it later needs `down -v`. The
README says so.

Choices:

- **`build:` is on `server` only, with `pull_policy: build`, and every other app service has
  `pull_policy: never`.** All of them name the same `image:` tag, so the context is built once. Measured in
  review with docker-compose v5.5.1, on a scratch project with a `build:` service and an `image:`-only
  service that share a `localhost/` tag:
  - With the default policy, compose first tries to **pull** the tag. It prints `Image localhost/…
    Error connection refused`, then builds anyway. The error is harmless, but it is misleading on the very
    first `up`.
  - With `pull_policy: build` on the builder and `never` on the rest, no pull is attempted. Each `up`
    rebuilds from cache in under a second when nothing changed. After a source change, the next `up`
    rebuilds, then recreates and restarts the containers that use the image.

  That is the behaviour a test stack wants: `podman compose up -d` always runs the checked-out code, and
  there is no `--build` to forget. The cost is a cached rebuild on each `up`, and with the layer order
  above, a source edit costs about one `COPY`.
- **The server binds loopback.** The API has no authentication: D-A8 is only a hook, and its default
  checker allows every request. The GUI writes `reel.yaml`, so the port MUST NOT listen on other interfaces
  by default. The user can edit the `ports:`
  line to change that. No variable is added for it (Principle VII).
- **Postgres is not published.** Only the containers reach it, on the project network. That avoids the
  5432 clash with `auto-reel-ng-dev-db`, as measured: "5442 was never used, since Postgres was not published".
- **Restart policy:** `unless-stopped` for `db`, `server` and `worker`, and `"no"` for the one-shots. The
  spike measured: "After `os.kill(1, SIGKILL)` … the container came back (`RestartCount=1`, state
  running)."
- **No server healthcheck.** "The API answered about 2 s after `up` returned", and nothing in the stack
  depends on the server.

### GPU: `/dev/dri` on the worker only, no group, CPU override file

Spike evidence (`captest.py` calls the engine's own `detect_capabilities` and `select_profile`):

| podman opts | selected profile |
|---|---|
| `--device /dev/dri/renderD128` | VaapiProfile, h264/hevc/av1 `_vaapi`, `pad_vaapi`, pad_fill_ok=false |
| `--device /dev/dri` | same |
| `--device /dev/dri --security-opt label=disable` | same |
| `--device /dev/dri --group-add keep-groups` | same |
| none | CPUProfile (auto fallback) |

`vainfo` in the container reports "Mesa Gallium driver 26.0.8 for AMD Radeon 860M Graphics (radeonsi,
krackan1 …)". The render node is `0666` on this host, so "**no `group_add` is needed on this host**".

**Decision:**

- The worker gets `devices: [/dev/dri:/dev/dri]`, with no `group_add`.
- `server` gets no device. It only reads the engine identity, and thumbnails run on the CPU.
- `compose.cpu.yaml` holds the CPU-only override:

  ```yaml
  services:
    worker:
      devices: !reset []
      command: [worker, /data/library, --device, cpu]
  ```

  The spike measured: "the `!reset` tag works with docker-compose v5.5.1 … the worker logs `profile=cpu
  render_node=None`".

The README documents the case of a host whose render node is `0660`: add `group_add: [keep-groups]` (crun)
or the render GID. That is documented but **not proven in compose**: the spike tested `keep-groups` with
`podman run` only, where it was harmless. It is not set by default for that reason.

**What the CPU fallback path does (Principle III).** Two cases, both the engine's existing behaviour:

- **No `/dev/dri` passed, or an unusable GPU.** Auto-selection picks `CPUProfile`, with
  libx264/libx265/libsvtav1.
- **A GPU that passes the self-test but cannot decode one clip's codec.** That job fails. There is no
  per-job fallback (spike finding 7).

The stack does not change either case. A host *without* `/dev/dri` cannot start the default compose file,
because the `devices:` entry fails (inferred). That host uses `-f compose.yaml -f compose.cpu.yaml`.

### The seed: a writable `year-event` library of symlinks over the read-only fixture

`scripts/seed_compose_library.py` is the spike's `seed.py`, generalized in one way and typed. It runs in the
app image (system Python 3.13, stdlib only):

```python
def seed(media: Path, library: Path, output: Path, *, reset: bool = False) -> SeedCounts: ...
def main(argv: list[str] | None = None) -> int:   # paths from /media/auto-reel-media, /data/library, /data/library-output
```

Layout:

- **The fixture's events.** `media/input/<year>/<event>/` becomes `library/<year>/<event>/`.
  - The event-root `reel.yaml` is a **real copy**, because GUI saves write there.
  - Every other entry is mirrored. A directory becomes a real directory, which keeps a chapter subfolder
    such as `Kvällen/`. A file becomes an **absolute** symlink to its fixture path.
  - The fixture's `.auto-reel/` directory is never carried.
- **The samples.** `media/samples/*`, except names that start with `legacy-`, becomes
  `library/2025/2025-01-15 - Provklipp/`. The `legacy-*` names become `library/2025/2025-01-16 - Gammal
  rendering/`.
- **Outputs.** `output` (`library-output/`) is created, so the server's default output directory exists.

The one change from the spike is mirroring subfolders. The spike's `seed.py` linked only an event's
top-level files, so a fixture event with a chapter folder would have lost those clips without a word. The
fixture has no subfolder today. The generalization costs a few lines and a test, and it means
`AR_MEDIA_DIR` can point at a richer copy of the fixture.

Symlink targets resolve inside every container, because seed, server and worker mount the fixture at the
same path. The media API serves them: "`api/media.py` checks containment lexically and never calls
`resolve()`, by design."

**Idempotency.** The seed creates only missing directories and links, and copies `reel.yaml` only when the
scratch event has none. An existing entry is never replaced, so a GUI edit, the engine's generated
`reel.yaml` and its `.auto-reel/` cache all survive. The spike measured the second run: "`{'reel_copied':
0, 'reel_kept': 1, 'link_new': 0, 'link_kept': 14}`". The seed prints its counts as one line.

**Reset.** `--reset` empties `library/` and `library-output/` first, and then seeds. Two more facts:

- The DB keeps its job rows across a library reset. The spike saw the list show "last done" for events with
  no output. The documented reset is therefore `podman compose down -v`, then `podman compose run --rm seed
  --reset`, then `podman compose up -d`.
- It runs inside the container, so it works for any file owner. Rootful Docker would own `./data` as root,
  and a host `rm -rf` would fail there.

**Failure.** The seed fails loud:

- If `media/input` is not a directory, it exits 1 with `seed: /media/auto-reel-media/input not found — is
  auto-reel-media mounted?`.
- Any `OSError` while seeding propagates. The process exits non-zero, compose does not start `server` or
  `worker`, and the error is in `podman compose logs seed`.

A partly seeded library is fine, because the next run completes it.

**Alternative considered: `scripts/make_dev_library.py`.** It already builds a GUI dev library, so the
question is whether the stack should run it. It does not fit the request:
- it cuts 6-second stream copies of one event's clips, so it does not link the fixture in;
- it needs ffmpeg, the database and a running worker at seed time;
- it rebuilds its destination from scratch on every run, which would discard GUI edits on each `up`.

It remains the tool for a library that shows every GUI state. Pointing the stack at its output is a possible
follow-up and is not part of this change.

**Dangling links.** A fixture file that disappears leaves a dangling link in the scratch event. The seed
does not prune it (it never deletes outside `--reset`). A reset is the documented remedy.

### Idempotency of the stack as a whole

- **A re-run of `up -d`.** The image is rebuilt from cache. `migrate` is a no-op at head. `seed` creates
  nothing new. `server` and `worker` are recreated only if their config or the image changed. A recreate
  during a render stops the worker, and the engine requeues the job on restart (below).
- **A `--force` run.** `podman compose exec server auto-reel enqueue /data/library --force` uses the
  engine's existing gate bypass. Nothing in the stack changes it.
- **A worker restart mid-render.** This is the engine's existing behaviour: requeue-on-restart, and the
  atomic `.part` → verify → rename finalize. A killed worker leaves no file that looks rendered, and the
  restarted worker takes the job again.

### Verification harness (tasks only, never committed)

GUI checks follow the spike's `pw/check.py`:

- **Browser image.** It runs in `localhost/playback-research:chrome` (Playwright, `channel="chrome"`,
  `--network host`).
- **Routes.** Only the write glob `**/api/v1/events/**/reel` is routed, observing non-GET methods and
  continuing. There is no catch-all route.
- **The script.** It lives in the session scratchpad.

The spike measured:

- the movie: `{"readyState": 4, "w": 1920, "h": 1080, "t": 2.008, "dur": 149.76, "err": null}`
- the clip preview: `{"readyState": 4, … "t": 1.55, "dur": 61.44}`
- the save: `PUT …/reel` returned 200

It also hit one gotcha: "right after a save, the movie panel re-mounts its `<video>` … A `play()` issued at
that moment rejects … The script waits 1.5 s and retries."

The fixture check uses a marker and a listing taken **before** anything starts, both stored in the
scratchpad and never inside the fixture.

## Research & Decisions

### The repo's Containerfile cannot build
**Context**: D-1 says the container bundles jellyfin-ffmpeg. The existing `Containerfile` was never built.
**Explored**: The spike ran:
- `podman pull docker.io/jellyfin/jellyfin-ffmpeg:latest` → "requested access to the resource is denied"
- `skopeo list-tags` on `docker.io/jellyfin/ffmpeg` → the same error
- `ghcr.io/jellyfin/jellyfin-ffmpeg` → "name unknown"
- `python3 -m auto_reel_ng` → "No module named auto_reel_ng.__main__"
**Decision**: Debian trixie-slim plus the Jellyfin apt repo, with `jellyfin-ffmpeg8=8.1.3-1-trixie` pinned
by ARG, and `ENTRYPOINT ["auto-reel"]`.
**Rationale**: It is the only way Jellyfin ships the binary, it gives the version pin D-1 asks for, and
trixie provides Python 3.13.

### VAAPI inside a rootless container on SELinux
**Context**: §4.12 requires `/dev/dri` passthrough for AMD/Intel. The brief asked whether jellyfin-ffmpeg
bundles a new enough Mesa, and which group and label settings are needed.
**Explored**: `vainfo` and the engine's `detect_capabilities`/`select_profile` under five podman option sets
(table above). Then real renders:
- the 9-clip Provklipp event in "**47 s** … `tag:encoder=Lavc62.28.103 h264_vaapi`";
- grillning in about 5 s, by guarded stream-copy concat;
- `gpu_busy_percent` read 8–32 % during the VAAPI renders.
**Decision**: The worker gets `devices: [/dev/dri:/dev/dri]`, with no `group_add` and no host VA packages.
`compose.cpu.yaml` is the CPU-only path.
**Rationale**: The bundled Mesa 26.0.8 radeonsi works with device passthrough alone, and
`container_use_devices` was off throughout. RDNA4 (the RX 9070 XT) was **not** tested, because that card is
not in this host. The inference is that "RDNA4 VA-API support has been in radeonsi since Mesa 25.0".

### Reading the fixture without changing it
**Context**: CLAUDE.md says the fixture is "never mutate it", and SELinux blocks `container_t` from
`user_home_t`.
**Explored**: plain `:ro` (denied), `label=disable` + `:ro` (readable, writes refused), and the contexts
before and after. The spike ran `find auto-reel-media -newer .media-marker` after the GUI save, after the
renders and at the end, and it "printed **nothing**". The 24-entry listing diff was identical, and every
context stayed `user_home_t`.
**Decision**: `label=disable` plus a read-only mount, behind a scratch library of symlinks with copied
`reel.yaml`.
**Rationale**: This is the only measured way to read the fixture without relabeling it. The engine and GUI
need a writable library: they write `reel.yaml`, `.auto-reel/cache/` and a generated `reel.yaml`.

### Serving the web client
**Context**: `web_dist_dir()` finds nothing for a normal install.
**Explored**: an editable install against a `--target` install, measured outside `/app` so the working
directory could not shadow the import (spike §4 gotcha).
**Decision**: an editable install, with no code change (Decisions above).
**Rationale**: It is proven, needs zero code, and respects the docstring's no-settings-key rule. A wheel that
carries the client is left to the publishing slice.

### Build context and pulls under the docker-compose provider
**Context**: The spike built with `podman build` and started compose from a pre-built image. So it never
showed what `podman compose up` itself sends to the build, or whether it tries to pull a tag that another
service builds.
**Explored**: In review, a scratch compose project ran under docker-compose v5.5.1 against the podman
socket, then was torn down. Results:
- with `.containerignore`, the context was 629.3MB; with `.dockerignore`, 418B;
- with the default pull policy, an `Image localhost/… Error connection refused` pull attempt came before
  the build;
- with `pull_policy: build` plus `never`, there was no pull attempt, a cached rebuild on each `up`, and a
  recreate after a source change.
**Decision**: `.dockerignore`; `pull_policy: build` on `server` and `never` on the other app services.
**Rationale**: It is the only ignore file the compose client reads. And the stack never pulls a local tag
or runs an image older than the checkout.

### Findings filed, not fixed here
**Context**: The spike found four problems outside this change's scope.
**Explored**:
1. The VAAPI normalize has no software-decode + `hwupload` path for a codec without HW decode. The spike
   saw `-38 Function not implemented` on `legacy-render-mpeg4-mp3.mp4`, and `vainfo` lists no MPEG-4 Part 2
   profile. The same clip rendered on the CPU in 9 m 25 s, as part of the 10-clip event.
2. Job progress is non-monotonic, 0.904 → 0.297, during "re-encoding 1 copied segment(s)".
3. `jellyfin-ffmpeg8` 8.1.3 has `--enable-libfdk-aac`, and `libfdk_aac` is listed in `-encoders`. That
   conflicts with D-1's "never bundle the nonfree/fdk-aac variant in a published image".
4. The `CLAUDE.md` host note (RX 9070 XT) is wrong for this machine.
**Decision**:
- (1) and (2) are proposed as follow-up changes.
- (3) goes into the HLD (D-1 note and D-17) as a blocker before any publish.
- (4) is reported to the user. `CLAUDE.md` is outside this repo.
**Rationale**: Each one needs its own change, and none of them blocks a local test stack. The seed puts the
MPEG-4 clip in an event of its own, so (1) fails one event and does not sink the sample event, which is
Principle I's per-event isolation working as intended.

### HLD fold-back (D-17)
**Context**: These decisions outlive the change. They cover how the local stack treats the fixture, where
state lives and how the client is served.
**Decision**: The HLD gains:
- **D-17 — Local compose stack**: the read-only fixture behind a seeded scratch library, `label=disable`
  rather than relabeling, editable install for the web client, Postgres unpublished, the GUI on loopback
  only, and the image rebuilt from the checkout on every `up` (`pull_policy: build`, `.dockerignore`);
- in §4.12, the facts on obtaining jellyfin-ffmpeg (apt `jellyfin-ffmpeg8`, pinned; no image exists), the
  bundled VA driver tree, and the fdk-aac pre-publish blocker;
- the §4.10 `web/dist` line, updated to "served from the local image via the editable install; the
  wheel/published image is still phase 11";
- a §6 phase 11 note: "slice 1: local compose stack (`compose-stack`)".

## Risks / Trade-offs

- **[The image is never published, but it does contain `libfdk_aac`.]** → It is built locally and tagged
  `localhost/`, which is D-1's "dev-only" case. The Containerfile header and the HLD state that it MUST NOT
  be pushed. Publishing waits for a D-1 revisit: a jellyfin build without fdk, or a different binary.
- **[`label=disable` turns off SELinux confinement for seed, server and worker.]** → They run rootless as
  the user and see only the mounts listed. The fixture mount is read-only. This is the trade the spike
  measured as the only one that avoids relabeling. `db` and `migrate` stay confined.
- **[An unauthenticated write API.]** → The port binds `127.0.0.1` only, and the README says so.
- **[Containers do not come back after a reboot.]** → "`podman-restart.service` (user) is **disabled** on
  this host". The README gives `systemctl --user enable podman-restart.service`. Nothing on the host is
  changed by this change.
- **[Rootful Docker writes root-owned files under `./data`.]** → Documented as untested. The reset works
  through the seed container, whatever the ownership.
- **[A seeded event fails by design on the GPU (`Gammal rendering`).]** → The README says why, and how to
  render it with the CPU override. It shows per-event failure reporting, which is Principle I working as
  intended.
- **[The editable install ties the image to `/app` as source.]** → It is fine for a locally built image, and
  the Containerfile comment says so. The publishing slice revisits it.
- **[Long-syntax `create_host_path: false` may behave differently under the podman provider.]** → It did:
  task 4.2 measured the podman API creating the missing directory anyway, so the stated fallback (short
  syntax) is in `compose.yaml`. The build-once and pull behaviour was measured in review
  (above).
- **[Every `up` rebuilds the image.]** → It is a cached rebuild, under a second in the measurement. A
  source edit recreates `server` and `worker`, and an in-flight render is requeued. This is the price of
  never running a stale image.
- **[A CPU render is slow on real footage.]** → The CPU override is for hosts without a GPU, and the README
  says it is slow. Measured: 9 m 25 s for the 10-clip sample event, against 47 s on VAAPI for the 9 clips.

## Migration Plan

This change adds files only. There is nothing to migrate in an existing install. The stack's database is
its own, `auto-reel-stack_pgdata`, and starts empty.

Rollback is `podman compose down -v`, then removing `./data` (or `podman compose run --rm seed --reset`
first, for rootful hosts) and the image `localhost/auto-reel-ng:compose`. After that the repo files can be
reverted.

## Open Questions

- **RDNA4 (RX 9070 XT) VAAPI in the container** needs one run on the card. The spike's host has only the
  Radeon 860M. Expected to work (Mesa 26.0.8 ≥ 25.0). A failure would show as the worker selecting the CPU
  profile, which the specs already cover.
- **Reboot behaviour with `podman-restart.service` enabled** was not tested. Documenting the command is
  enough for a local test stack.
