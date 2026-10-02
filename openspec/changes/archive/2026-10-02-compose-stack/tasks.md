Conventions for every task below:

- `$SP` is the applying session's scratchpad. All commands run from the checkout root (`$REPO`).
- `$MEDIA` is the fixture, `/var/home/emil/dev/larnet/auto-reel-project/auto-reel-media`. If
  `../auto-reel-media` does not resolve to `$MEDIA` from `$REPO` (a worktree somewhere else), put
  `AR_MEDIA_DIR=$MEDIA` in `$REPO/.env`. Never write, touch, `chcon` or `:z`/`:Z` anything under `$MEDIA`.
- Port **8132** is this change's. The compose project is **`auto-reel-stack`**. Never stop, remove or
  `down` any other project's containers or volumes: `auto-reel-ng-dev-db`, `auto-reel-ng-test-pg-*`, or
  other worktrees' stacks. Never use host ports 8080, 5173 or 5432.

## 1. Baseline

- [x] 1.1 Confirm the code this change was designed against, and take the fixture snapshot **before
  anything else runs**. Stop and report if a check fails in a way the design does not cover.
  - `git diff fed5065 -- Containerfile .gitignore README.md docs/high-level-design.md auto_reel_ng/api/app.py`
    prints nothing. `web_dist_dir()` still returns `…parent.parent.parent / "web" / "dist"`.
  - `podman --version` reports 5.x. `podman compose version` reports the docker-compose provider (spike:
    v5.5.1). `ls -l /dev/dri/renderD*` lists the render node and its mode. Note the mode: `0660` means the
    README's `group_add` note applies to this host.
  - `ss -ltn | grep -c ':8132 '` prints 0, and `podman ps -a --filter name=auto-reel-stack -q` prints
    nothing.
  - `touch $SP/.media-marker`
  - `find $MEDIA -printf '%p %s %T@ %M %Z\n' | sort > $SP/media-before.txt`. The spike counted 24
    entries.

  Verify: every check holds. `media-before.txt` exists, and every line carries `user_home_t`.

## 2. Image (`Containerfile`, `.dockerignore`, `.gitignore`)

- [x] 2.1 Rewrite `Containerfile` as in the design ("Image: Debian trixie + …"):
  - the `node:22` web stage;
  - `debian:trixie-slim` with the Jellyfin deb822 source, and `jellyfin-ffmpeg8=${JELLYFIN_FFMPEG_VERSION}`
    under `ARG JELLYFIN_FFMPEG_VERSION=8.1.3-1-trixie`;
  - `ENV PATH=/usr/lib/jellyfin-ffmpeg:${PATH}`;
  - the dependency layer (`pyproject.toml` plus stubs, then `pip install -e .`), then `COPY . /app` and
    `COPY --from=web /web/dist /app/web/dist`;
  - `ENTRYPOINT ["auto-reel"]`;
  - the existing Cairo/Pango comment kept, plus a header. The header says the image is local-only, MUST NOT
    be published while D-1's fdk-aac blocker stands, and why `/app` must stay the source tree.

  Add `.dockerignore` (**not** `.containerignore`; design, "Build context"), listing:
  - `data/`, `.env`, `.git/`, `.venv/`, `.claude/`, `.mypy_cache/`, `.pytest_cache/` and `**/__pycache__/`;
  - `web/node_modules/` and `web/dist/`;
  - `experiments/`, `docs/`, `openspec/` and `tests/`;
  - after the Phase 1 review: `README.md` and the coverage artifacts (design, "Build context").

  Add `/data/` and `/.env` to `.gitignore`.

  Verify:
  - `time podman build -t localhost/auto-reel-ng:compose -f Containerfile .` succeeds in about 2 min from
    a cold cache.
  - `podman images localhost/auto-reel-ng:compose` shows about 520 MB (spike: 521 MB).
  - `podman run --rm localhost/auto-reel-ng:compose --help` lists the subcommands and exits 0.
  - `podman run --rm --entrypoint ffmpeg localhost/auto-reel-ng:compose -version | head -1` shows
    `8.1.3-Jellyfin`.
  - `podman run --rm --entrypoint python3 localhost/auto-reel-ng:compose -c "from auto_reel_ng.api.app import web_dist_dir as w; print(w(), (w()/'index.html').is_file())"`
    prints `/app/web/dist True`.
  - `podman run --rm --entrypoint sh localhost/auto-reel-ng:compose -c 'ls /app/experiments /app/data 2>&1; fc-match "DejaVu Sans"'`
    shows both paths missing and `DejaVuSans.ttf`.
  - **Dependency layer.** Write a throwaway `auto_reel_ng/_layer_probe.py` (a content change; a bare
    `touch` does not invalidate the cache), then rebuild. The `pip install` step reports `Using cache`, and
    `--help` still lists the subcommands. Delete the probe afterwards. If the editable install does not see the later
    sources, apply the design's fallback order and say so in the design.
  - **D-1 evidence for the HLD note.** Record `ffmpeg -L 2>&1 | head -3`, and whether `ffmpeg -buildconf`
    lists `--enable-nonfree` and `--enable-libfdk-aac`, in the scratchpad.
  - `test ! -e .containerignore`. `git status --short` shows no `web/dist` and no `data/`.

## 3. Seed (`scripts/`, `tests/`)

- [x] 3.1 Add the seed and its test together, test first.

  **The test.** Add `tests/test_seed_compose_library.py`. It has no marker, loads
  `scripts/seed_compose_library.py` with `importlib.util.spec_from_file_location`, and builds a fake fixture
  under `tmp_path`:
  - `input/2024/2024-06-27 - grillning med grannar/` with two small files, `reel.yaml` and `.auto-reel/cache/x`
  - `input/2024/2024-08-20 - Två kapitel/` with `s1.mp4` and `Kvällen/s2.mp4`
  - `samples/` with `a.mp4`, `b.mov` and `legacy-x.mp4`

  The cases are:
  - **Layout.** Clips are absolute symlinks to the fixture. `reel.yaml` is a regular file with the same
    bytes. There is no `.auto-reel` anywhere in the library. `Kvällen/` is a real directory that holds a
    link. `2025/2025-01-15 - Provklipp` links `a.mp4` and `b.mov` only. `2025/2025-01-16 - Gammal rendering`
    links `legacy-x.mp4` only. `library-output/` exists.
  - **Idempotent.** A second `seed()` returns zero copied and zero new links. A `reel.yaml` edited between
    the runs, and an extra file the engine wrote (`.auto-reel/cache/render-manifest.json`), are both
    unchanged.
  - **Reset.** `reset=True` empties the library and the output (a stray file in `library-output/` is gone),
    restores the fixture's `reel.yaml`, and leaves the fake fixture byte-identical. Removing a clip symlink
    never follows it.
  - **Missing fixture.** With no `input/`, `main()` returns 1 and stderr names `<media>/input`.
  - **The fixture is only read.** The fake fixture's sorted `(path, size, mtime_ns)` listing is the same
    before and after every case.

  Run `.venv/bin/python -m pytest tests/test_seed_compose_library.py` with no script present, and see it
  fail on the missing file.

  **The script.** Add `scripts/seed_compose_library.py` as in the design ("The seed: …"):
  - it starts from the spike's `seed.py`;
  - it is typed and stdlib-only, with `seed(media, library, output, *, reset=False) -> SeedCounts`, a
    dataclass whose fields are `reel_copied`, `reel_kept`, `link_new` and `link_kept` (plus `events`, the
    count the printed line names);
  - `main(argv)` takes `--reset` (and `--media`/`--library`/`--output`, defaulting to the container paths, so
    the test can point it at `tmp_path`) and prints one line, `seed: N events under /data/library: …`;
  - subfolders are mirrored, and `.auto-reel` is skipped at any depth;
  - the module docstring holds the layout diagram.

  Verify:
  - `.venv/bin/python -m pytest tests/test_seed_compose_library.py` passes;
  - black and isort are clean on `scripts/seed_compose_library.py` and the test (line length 100);
  - `.venv/bin/python -m mypy --strict scripts/seed_compose_library.py` is clean;
  - `podman run --rm --entrypoint python3 localhost/auto-reel-ng:compose -c "import ast,sys; ast.parse(open('/app/scripts/seed_compose_library.py').read())"`
    succeeds after a rebuild. The image's Python 3.13 parses it, because the script uses no 3.14 syntax.

## 4. Compose (`compose.yaml`, `compose.cpu.yaml`, `.env.example`)

- [x] 4.1 Write `compose.yaml` as in the design ("Compose services and start-up order", "Media mount"):
  - project `auto-reel-stack`;
  - the `x-app` anchor;
  - the long-syntax read-only media mount with `create_host_path: false` (replaced by the design's
    short-syntax fallback after 4.2 measured the provider ignoring it);
  - `build:` on `server` only, with `pull_policy: build`, and `pull_policy: never` in `x-app`;
  - `db` with `POSTGRES_USER`/`POSTGRES_DB` set to `auto_reel_ng`, `POSTGRES_PASSWORD` set to
    `${AR_DB_PASSWORD:-auto_reel_ng}`, and the `pg_isready` healthcheck;
  - `security_opt: [label=disable]` on `seed`, `server` and `worker`, while `migrate` resets `volumes: []`
    and `security_opt: []`;
  - `/dev/dri` on `worker` only;
  - `127.0.0.1:${AR_PORT:-8132}:8080`;
  - `pgdata`;
  - a header comment with the up, open, reset and down commands.

  Write `compose.cpu.yaml`, with `devices: !reset []` and `--device cpu`. Write `.env.example`, with the four
  variables and their defaults, and one comment line each.

  Verify:
  - `podman compose config` and `podman compose -f compose.yaml -f compose.cpu.yaml config` both render.
    In the second, `worker` has no `devices` and its command ends in `--device cpu`.
  - `grep -nE ':(z|Z)\b|,z\b|,Z\b' compose.yaml compose.cpu.yaml` prints nothing.
  - `podman compose config | grep -n 'published'` shows only `8132` on `127.0.0.1`.
  - `podman compose config | grep -n 'pull_policy'` shows `build` once (server) and `never` for `migrate`,
    `seed` and `worker`.
- [x] 4.2 Up from a clean state (spec: "First start from a clean state").
  1. Make sure no project state exists: `podman compose down -v` (project-scoped),
     `podman rmi -f localhost/auto-reel-ng:compose`, and no `$REPO/data`.
  2. Run `time podman compose up -d 2>&1 | tee $SP/up1.log`.

  Verify:
  - The log shows **one** image build, and `grep -E 'auto-reel-ng:compose.*(Pulling|connection refused)'
    $SP/up1.log` prints nothing. Postgres may be pulled.
  - `grep 'Sending build context' $SP/up1.log` reports a few MB at most.
  - `podman compose ps -a` shows `migrate` and `seed` Exited (0), and `db`, `server` and `worker` running.
  - `podman compose logs migrate` ends at the head revision `505f2d2c5ca1`, unless `alembic heads` names a
    newer one.
  - `podman compose logs seed` prints `3 events` (grillning, Provklipp, Gammal rendering) and its counts.
  - `curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1:8132/` prints `200`.
  - `podman compose logs server | grep 'serving the built web client from /app/web/dist'` matches.
  - `podman port auto-reel-stack-db-1` prints nothing.
  - `podman ps --filter name=auto-reel-ng-dev-db` is still Up.
  - `ls -lZd data/library` shows the user as owner.
  - A second `podman compose up -d` rebuilds entirely from cache and does not recreate `server` or
    `worker`. Migrate is at head, and the seed counts are all `kept`.
  - Spec "The next up runs the changed code": write the throwaway `auto_reel_ng/_layer_probe.py` and run
    `podman compose up -d`.
    - The pip step is `Using cache`.
    - `server` and `worker` are recreated.
    - `podman compose exec server ls /app/auto_reel_ng/_layer_probe.py` succeeds.
    - Nothing is pulled.

    Delete the probe and run `up -d` once more.

  Then check the missing-fixture case with a throwaway env:
  - `AR_MEDIA_DIR=$SP/no-such-media podman compose run --rm seed` fails.
  - `test -e $SP/no-such-media` is false. If the provider created it, apply the design's fallback and
    document it.
  - With an existing empty `$SP/empty-media`, the seed exits 1 naming `/media/auto-reel-media/input`.

## 5. End-to-end verification (scratch only, nothing committed)

- [x] 5.1 GPU render (spec: "An AMD render node gives a VAAPI render", "A codec without VAAPI decode fails
  its own event only"). `podman compose logs worker` shows
  `profile=amd render_node=/dev/dri/renderD128`, and the device named by the bundled `vainfo`
  ("AMD Radeon 860M Graphics" on this host, not "AMD GPU"). That confirms that `PATH` set in the image is
  enough.

  Run `podman compose exec server auto-reel enqueue /data/library`. Then poll
  `podman compose exec server auto-reel jobs list /data/library` until no job is `queued` or `running`, with
  a 10 min cap.

  Verify:
  - grillning ends `done` (spike: about 5 s, stream copy).
  - `2025-01-15 - Provklipp` ends `done` (spike: 47 s).
  - `2025-01-16 - Gammal rendering` ends `failed`, and `jobs show` names the normalize failure with
    `Function not implemented`.
  - `podman compose exec server ffprobe -v error -select_streams v:0 -show_entries stream_tags=encoder -of default=nw=1 "/data/library-output/<Provklipp movie>"`
    shows `h264_vaapi`.
  - Optionally, `cat /sys/class/drm/card*/device/gpu_busy_percent` is above idle during the Provklipp
    render.
  - `find $MEDIA -newer $SP/.media-marker` prints nothing.
- [x] 5.2 GUI on 8132 (spec: "The GUI loads on the stack's port", "A GUI save and a render leave the fixture
  untouched").
  - Copy the spike's `spike-compose/pw/check.py` to `$SP/pw/`. It routes **only**
    `**/api/v1/events/**/reel`, observing non-GET and continuing, with no catch-all route.
  - Run it with `podman run --rm --network host --security-opt label=disable -v $SP/pw:/pw:ro -v $SP/shots:/shots localhost/playback-research:chrome python3 /pw/check.py`.
    It uses `channel="chrome"` and the default `BASE=http://127.0.0.1:8132` and grillning `EVENT`.
  - Run it again as `… python3 /pw/check.py dark` with `-e EVENT='2025/2025-01-15 - Provklipp' -e LISTTEXT=Provklipp`.
    The `dark` mode plays the movie only and skips the save, so Provklipp stays fresh for 5.3's
    `--years 2025` enqueue.

  Verify:
  - the list loads;
  - the grillning movie reaches `readyState 4`, `t > 2`, `dur ≈ 149.76`, `err null`;
  - the `s1710001.mp4` clip preview reaches `t > 1.5`, `dur ≈ 61.44`;
  - the Provklipp movie plays (`dur ≈ 202.8`);
  - the save PUT returns 200;
  - `diff "$MEDIA/input/2024/2024-06-27 - grillning med grannar/reel.yaml" "data/library/2024/2024-06-27 - grillning med grannar/reel.yaml"`
    shows only the title line;
  - console errors are at most `favicon.ico 404`;
  - `find $MEDIA -newer $SP/.media-marker` prints nothing.

  Keep the screenshots in `$SP/shots/`.
- [x] 5.3 Lifecycle, CPU override, reset and the final fixture check (spec: "Stop exits zero", "Down and up
  keep edits and renders", "A worker that crashes comes back", "A host without a usable GPU renders on the
  CPU", "Reset restores the fixture's editorial state", "A write through the mount is refused").
  - **Write refused.** `podman compose exec worker touch /media/auto-reel-media/x` fails with "Read-only
    file system".
  - **Crash restart.** `kill -KILL $(podman inspect -f '{{.State.Pid}}' auto-reel-stack-worker-1)`, then
    `podman inspect -f '{{.RestartCount}} {{.State.Status}}' auto-reel-stack-worker-1` shows `1 running`
    within a few seconds.
  - **Stop.** `podman compose stop server worker`, then
    `podman inspect -f '{{.State.ExitCode}}' auto-reel-stack-server-1 auto-reel-stack-worker-1` shows `0`
    and `0`. The logs show "stopped cleanly" and "Application shutdown complete".
  - **Down/up.** `podman compose down && podman compose up -d`. Verify:
    - the seed counts are all `kept`;
    - the edited title is in `data/library/…/reel.yaml` and in the GUI list;
    - `jobs list` still holds the 5.1 jobs;
    - grillning shows a staleness reason that includes `editorial`;
    - the grillning movie still plays (`check.py dark` mode, movie only).
  - **Build context with real data.** With rendered movies now in `data/library-output`, run
    `podman compose build server 2>&1 | grep 'Sending build context'`. It reports a few MB at most, and
    `podman run --rm --entrypoint ls localhost/auto-reel-ng:compose /app/data` fails (spec: "Scratch data is
    not sent to the build").
  - **CPU override.** `podman compose -f compose.yaml -f compose.cpu.yaml up -d worker`. Then the worker log
    shows `profile=cpu render_node=None`.
    - First, `podman compose exec server auto-reel scan /data/library --years 2025` should show Provklipp
      fresh and `Gammal rendering` stale.
    - `podman compose exec server auto-reel enqueue /data/library --years 2025` then enqueues only
      `Gammal rendering`. If Provklipp is enqueued too, cancel its job with `auto-reel jobs cancel <id>`
      and note why it was stale.
    - Wait for the job, with a 15 min cap.

    Verify:
    - the job is `done`;
    - `ffprobe` of its movie shows `libx264`.

    Then `podman compose up -d worker` restores the GPU worker.
  - **Reset.** `podman compose down -v && podman compose run --rm seed --reset && podman compose up -d`.
    Verify:
    - `cmp` of each scratch `reel.yaml` against the fixture's succeeds, with the title edit gone;
    - `data/library-output/` is empty;
    - `jobs list` is empty.
  - **Final fixture check.**
    - `find $MEDIA -newer $SP/.media-marker` prints nothing;
    - `find $MEDIA -printf '%p %s %T@ %M %Z\n' | sort | diff $SP/media-before.txt -` prints nothing, which
      covers paths, sizes, mtimes, modes and SELinux contexts.
  - **Teardown.**
    - `podman compose down -v`, then `rm -rf data` (rootless, so every file is user-owned);
    - keep the image `localhost/auto-reel-ng:compose`;
    - port 8132 is free again;
    - `auto-reel-ng-dev-db` and every `auto-reel-ng-test-pg-*` container are still in their prior state.

## 6. Docs

- [x] 6.1 Write the README section "Run the stack with compose", after "API service (`serve`)" or under
  "Development". It covers:
  - prerequisites: rootless podman with `podman compose`, and the sibling `auto-reel-media`;
  - `cp .env.example .env`, which is optional. `AR_PORT` changes the GUI port. `AR_DB_PASSWORD` applies
    only to a fresh `pgdata`, so changing it needs `down -v`;
  - `podman compose up -d` and opening `http://127.0.0.1:8132/`. Every `up` rebuilds from the checkout
    (cached), so after a `git pull` the same command runs the new code;
  - `podman compose logs -f worker`;
  - rendering through the GUI or `podman compose exec server auto-reel enqueue /data/library`;
  - where things live: `./data/library`, `library-output` and `cache`, plus the `pgdata` volume;
  - that the fixture is mounted read-only and never relabeled, and why `label=disable`;
  - `down`, which keeps edits, and the reset sequence;
  - the CPU override, and that it is slow;
  - GPU notes:
    - `/dev/dri` with no group needed when the render node is `0666`;
    - `group_add: [keep-groups]` for `0660` (untested in compose);
    - RDNA4 untested;
    - the expected `Gammal rendering` failure on VAAPI;
  - `systemctl --user enable podman-restart.service` for restart after reboot;
  - rootful Docker untested;
  - that the GUI binds loopback because the API has no auth.

  Update `docs/high-level-design.md` as in the design ("HLD fold-back (D-17)"):
  - add **D-17** in §7 and in the §4.12 "Deployment" text;
  - add the D-1 facts note: apt `jellyfin-ffmpeg8` pinned; no `jellyfin/jellyfin-ffmpeg` image exists;
    bundled libva and radeonsi/iHD/i965; `libfdk_aac` present in 8.1.3, a blocker before any publish;
  - update the §4.10 `web/dist` line;
  - add the §6 phase 11 note "slice 1: local compose stack (`compose-stack`)";
  - add a §8.12 data point: VAAPI userspace bundled; NVIDIA still open.

  Verify:
  - every command in the README section is one that 4.2 to 5.3 actually ran;
  - `grep -n "jellyfin/jellyfin-ffmpeg:latest\|python3 -m auto_reel_ng" README.md docs/high-level-design.md Containerfile`
    prints only text that describes them as wrong.

## 7. Validation

- [x] 7.1 Run the gates:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`;
  - `.venv/bin/python -m mypy auto_reel_ng`;
  - `.venv/bin/python -m pylint auto_reel_ng`;
  - the full `.venv/bin/python -m pytest`, including `requires_db` (podman);
  - then `openspec validate compose-stack --strict`.

  Verify: all are clean or green, apart from the known cairo `no-member` noise and the five font-dependent
  skips. `git status --short` lists only the files named in the proposal's Impact, and no `data/`, `.env`
  or `web/dist`.
