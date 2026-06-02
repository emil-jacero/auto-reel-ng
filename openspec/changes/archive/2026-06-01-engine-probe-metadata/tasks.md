## 1. Package skeleton & tooling

- [x] 1.1 Create the `auto_reel_ng` package layout (`auto_reel_ng/`, `auto_reel_ng/ffmpeg/`, `tests/`) and `pyproject.toml` (hatchling, Python ≥ 3.13).
- [x] 1.2 Configure tooling to match conventions: black + isort (line length 100), strict mypy, pylint, pytest; fix the coverage target to `auto_reel_ng` (auto-reel's `--cov` pointed at the wrong package).
- [x] 1.3 Add a typed error hierarchy module (base `EngineError`; `FfmpegError`, `FfmpegVersionError`, `ProbeError`).
- [x] 1.4 Add a logging context helper (thread/movie/clip tags) carried over from auto-reel, and a `conftest.py` with a synthetic-clip fixture factory built from `ffmpeg lavfi` (testsrc/sine) so tests need no real media.

## 2. ffmpeg-runtime: discovery & version gate

- [x] 2.1 Implement `FfmpegRuntime` binary resolution in precedence order: explicit arg/env (`AUTO_REEL_NG_FFMPEG`/`_FFPROBE`) → bundled jellyfin-ffmpeg path → PATH; expose resolved paths; raise `FfmpegError` naming the missing binary. (spec: Binary discovery and configuration)
- [x] 2.2 Parse `ffmpeg -version` and assert ≥ 7.1; raise `FfmpegVersionError` stating detected vs required on old/unparseable versions. (spec: Minimum version enforcement)
- [x] 2.3 Tests: explicit-over-PATH precedence, PATH fallback, missing-binary error, accept 7.1+, reject old/unparseable (mock `-version` output).

## 3. ffmpeg-runtime: execution, progress, capability text

- [x] 3.1 Implement `run()` (captured `subprocess.run`, no shell) raising `FfmpegError` with exit code + command + stderr on non-zero; return captured output on success. (spec: Command execution with structured errors)
- [x] 3.2 Implement `run_with_progress()` (`Popen` + `-progress` line parsing) invoking an optional callback with a non-decreasing 0.0–1.0 fraction from `out_time`/duration. (spec: Progress reporting)
- [x] 3.3 Implement raw capability accessors returning unmodified text of `-hwaccels`/`-encoders`/`-decoders`/`-filters`. (spec: Raw capability text exposure)
- [x] 3.4 Tests: non-zero exit surfaces details; success returns output; progress callback receives monotonic fractions on a real short lavfi encode; capability accessors return non-empty text.

## 4. media-probe: typed model & extraction

- [x] 4.1 Define the immutable `ClipMetadata` frozen dataclass with all spec fields; model absent audio and absent rotation as explicit `None`/sentinel (never fabricated).
- [x] 4.2 Implement `probe_media(path)`: single `ffprobe -show_format -show_streams -print_format json` (no sleeps) → `ClipMetadata`; map video/audio streams + format. (spec: Single-pass typed metadata extraction)
- [x] 4.3 Implement fps resolution: `avg_frame_rate` → `r_frame_rate`, rational parse, bounds (0 < fps ≤ 1000) else `ProbeError`. (spec: Frame-rate resolution)
- [x] 4.4 Implement rotation (display-matrix/`rotation` tag) + SAR/DAR capture. (spec: Rotation and aspect-ratio capture)
- [x] 4.5 Implement HDR flag from color transfer (`smpte2084`/`arib-std-b67`) and expose the transfer value. (spec: HDR detection)
- [x] 4.6 Implement creation-time from ffprobe tags with an explicit (off-by-default) exiftool fallback. (spec: Audio and creation-time handling)

## 5. media-probe: fail-loud behavior

- [x] 5.1 Raise `ProbeError` for missing file, zero-byte file, no video stream, and unparseable ffprobe output; never substitute assumed values. (spec: Fail loud, never fabricate)
- [x] 5.2 Provide a thin batch helper that probes many files, skipping and reporting failures while continuing. (spec scenario: Batch continues past a bad file)
- [x] 5.3 Tests using synthetic fixtures: complete metadata for a valid clip; exactly one ffprobe per file; empty/missing/no-video/garbage → `ProbeError`; rotated clip reports 90°; non-1:1 SAR reported; PQ flagged HDR / bt709 not; video-only clip reports no audio; creation time from tag without spawning exiftool; batch continues past a bad file.

## 6. Wire-up & docs

- [x] 6.1 Expose `FfmpegRuntime`, `probe_media`, `ClipMetadata`, and the error types from the package's public `__init__`.
- [x] 6.2 Add a short module README/docstring noting the ffmpeg ≥ 7.1 requirement (D-1) and the fail-loud guarantee; ensure `task lint:check` and `pytest` pass clean.
