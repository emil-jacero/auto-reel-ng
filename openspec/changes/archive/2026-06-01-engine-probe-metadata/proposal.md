## Why

Everything in auto-reel-ng (capability profiles, render pipeline, analysis, GUI) builds on two foundations
that auto-reel got wrong: a **reliable way to run a known-good ffmpeg** and a **trustworthy media-probe
layer**. auto-reel hardcoded `ffmpeg` from PATH with no version guarantee, and its probe layer slept 1s per
clip, shelled out to exiftool+ffprobe separately, and — worst — **silently fabricated metadata** (assumed
1920×1080/25fps) on probe failure, which can corrupt output. This change establishes the engine skeleton, a
binary-agnostic ffmpeg runtime (D-1), and a fail-loud probe layer, so later changes have a solid base.

## What Changes

- New Python package `auto_reel_ng` (engine library) with packaging, strict typing/lint, and a test suite
  from day one. Directory is spelled `ffmpeg` (auto-reel's `ffmepg` typo is **not** carried over).
- **ffmpeg runtime (binary-agnostic, D-1):** discover `ffmpeg`/`ffprobe` from explicit config/env first, else
  a bundled-jellyfin-ffmpeg default, else PATH; **assert ffmpeg ≥ 7.1 at startup** (required by later filter
  work) and fail with a clear message otherwise; run commands with structured errors and a progress hook
  parsed from `ffmpeg -progress`. Expose the raw `-version/-hwaccels/-encoders/-decoders/-filters` text for a
  later change to interpret (capability detection is **out of scope** here).
- **Media probe (fail-loud):** a single `ffprobe -show_format -show_streams -print_format json` per file →
  a typed, immutable metadata model capturing duration, fps (avg→r_frame_rate), codec/profile, width/height,
  **SAR/DAR**, **rotation/display-matrix**, pix_fmt, **color transfer (HDR flag)**, bitrate, and audio
  codec/sample-rate/channels/layout, plus creation time. **BREAKING vs auto-reel behavior:** on probe failure
  the clip is **skipped with an error** — metadata is never fabricated.
- No `sleep`-based timing hacks; creation-date extraction uses ffprobe tags with an optional, explicit
  exiftool fallback (not a per-clip subprocess by default).

## Capabilities

### New Capabilities
- `ffmpeg-runtime`: locate/configure the ffmpeg & ffprobe binaries, assert minimum version, and execute
  commands with structured error and progress reporting.
- `media-probe`: extract validated, typed metadata from a single media file, failing loudly (never
  fabricating) when the file cannot be probed.

### Modified Capabilities
<!-- none — this is the first change; no existing specs. -->

## Impact

- **New code:** `auto_reel_ng/` package (engine), `tests/`, `pyproject.toml`, lint/type config.
- **Runtime dependency:** an ffmpeg ≥ 7.1 build (default jellyfin-ffmpeg per D-1; the dev host's system
  ffmpeg 7.1.3 satisfies this). ffprobe from the same build.
- **No** database, API, GUI, or GPU/codec selection yet — those are later changes that depend on this one.

## Non-goals

- Capability detection & acceleration-profile selection (separate change #2) — this change only *exposes* the
  raw ffmpeg capability text, it does not interpret it.
- The render/normalize/concat pipeline (#4) and title/overlay (#5).
- `reel.yaml`/`config.yaml` schema and ingest-layout parsing (#3/#6).
- Postgres, FastAPI service, scheduler, and the web GUI.
- HDR tonemapping, analysis (black/white/freeze), and ML — later changes.
