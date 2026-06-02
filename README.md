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

## Development

```bash
pip install -e ".[dev]"
pytest                 # tests build synthetic clips via ffmpeg lavfi; no real media needed
black . && isort . && mypy auto_reel_ng && pylint auto_reel_ng
```
