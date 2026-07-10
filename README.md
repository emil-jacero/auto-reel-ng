# auto-reel-ng (engine)

The engine foundation for auto-reel-ng: a binary-agnostic **ffmpeg runtime** and a
**fail-loud media-probe** layer. Every later change (capability profiles, render
pipeline, analysis, service/GUI) builds on this package.

## Requirements

- **ffmpeg / ffprobe ≥ 7.1** (locked decision **D-1**). Later filter work relies on
  7.1-only filters, so `FfmpegRuntime` asserts the version at construction and fails
  loud with a clear message rather than producing a cryptic error mid-render.
- Python ≥ 3.13.

The runtime resolves the binaries in a fixed precedence order:

1. explicit constructor argument,
2. `AUTO_REEL_NG_FFMPEG` / `AUTO_REEL_NG_FFPROBE` environment variables,
3. bundled jellyfin-ffmpeg (`/usr/lib/jellyfin-ffmpeg`),
4. system `PATH`.

## Fail-loud guarantee

`probe_media()` runs **exactly one** `ffprobe` per file and returns an immutable
`ClipMetadata`. If a file is missing, empty, has no video stream, is unparseable, or
reports an implausible frame rate, it raises `ProbeError`. It **never fabricates
metadata** (no assumed 1920×1080 / 25 fps). Absent audio and absent rotation are modeled
as explicit `None`, never invented defaults. Use `probe_many()` to probe a batch while
skipping and reporting failures.

## Quick start

```python
from auto_reel_ng import FfmpegRuntime, probe_media

runtime = FfmpegRuntime()           # resolves binaries, asserts ffmpeg >= 7.1
meta = probe_media("clip.mp4", runtime=runtime)
print(meta.width, meta.height, meta.fps, meta.is_hdr, meta.has_audio)
```

## Command line (`auto-reel`)

Installing the package provides an `auto-reel` entry point that drives the whole
pipeline headless. It takes a **project root** (the directory an ingest layout
walks; defaults to the current directory) and writes one movie per event.

```bash
auto-reel render  <root> -o out           # scan -> reconcile -> probe -> resolve -> render
auto-reel scan    <root>                  # inventory: events + NEW/ACTIVE/IGNORED/MISSING clips
auto-reel analyze <root>                  # detect black/white/freeze segments, cache suggestions
auto-reel import  <root>                  # adopt auto-reel legacy metadata into a v2 reel.yaml
```

Shared options: `--years 2023,2024` (year-event layout), `--layout flat|year-event`,
and `-o/--output`. `render` also takes `--dry-run` (print the ffmpeg commands and
write nothing), `--overwrite`, and `--device <amd|nvidia|intel|cpu|device-id>`.

- **Layouts** map the project root to event directories: `year-event`
  (`<root>/<year>/<event>/`, the default) and `flat` (events directly under the root).
- **Adoption policy:** an event with no `reel.yaml` is seeded from its folder
  structure; on later runs `render` adopts any newly added clip into the default
  chapter (so it is never silently dropped) and reports clips that went `MISSING`.
- **Per-event isolation:** one event failing to render is reported with its cause
  and does not abort the rest; the exit code is non-zero if any event errored.

### Project `config.yaml`

An optional `config.yaml` at the project root supplies shared defaults. Every field
is optional; a command-line flag overrides it, and an event's `reel.yaml` overrides
the project `look`.

```yaml
# config.yaml
layout: year-event        # ingest layout name
input: media              # walk root, relative to the project root (optional)
output: out               # default output directory (optional)
look:                     # opaque defaults passed to resolve() as look_defaults
  resolution: 1080p
  video_codec: h264
```

## Development

```bash
pip install -e ".[dev]"
pytest                 # tests build synthetic clips via ffmpeg lavfi; no real media needed
black . && isort . && mypy auto_reel_ng && pylint auto_reel_ng
```

The persistence suite (`requires_db`-marked tests) needs **podman** on `PATH`: a
session-scoped fixture starts a throwaway Postgres container per test run and tears
it down after. Tests not marked `requires_db` run without it.

To provision a database by hand (dev default is
`postgresql+psycopg://auto_reel_ng:auto_reel_ng@localhost:5432/auto_reel_ng`, overridden
by `DATABASE_URL` or `config.yaml`'s `database.url` — see
`auto_reel_ng/persistence/config.py`):

```bash
DATABASE_URL=postgresql+psycopg://... alembic upgrade head
```
