## Context

This is the first code change for auto-reel-ng. It lays the engine foundation that every later change
(capability profiles, render pipeline, analysis, service/GUI) depends on. The reference design is
`docs/high-level-design.md`; the relevant locked decision is **D-1** (default jellyfin-ffmpeg, but a
binary-agnostic engine that asserts ffmpeg ≥ 7.1). The auto-reel learnings this change directly repairs:
per-clip `time.sleep(1)`, separate exiftool+ffprobe subprocesses, instantiating an ffmpeg wrapper per object,
and — most importantly — **silently fabricating metadata** (1920×1080/25fps) on probe failure.

The dev host has ffmpeg 7.1.3 (with VAAPI/QSV/NVENC/AMF/libplacebo) so this change is fully testable locally
without GPUs (probe + runtime are CPU/subprocess concerns).

## Goals / Non-Goals

**Goals:**
- A `auto_reel_ng` engine package with packaging, strict typing/lint, and tests from the first commit.
- `FfmpegRuntime`: one place that resolves the binaries, gates the version, runs commands with structured
  errors, and parses progress — reused everywhere (no per-object wrappers).
- `probe_media()`: one ffprobe call → an immutable typed metadata object; fail loud; capture rotation, SAR/DAR,
  HDR transfer, and explicit "no audio".

**Non-Goals:**
- Interpreting `-hwaccels/-encoders/-filters` into acceleration profiles (change #2 — this change only exposes
  the raw text).
- Any transcode/normalize/concat (#4), title rendering (#5), reel.yaml/config schema (#3/#6), DB/API/GUI (#7+).

## Decisions

- **Single `FfmpegRuntime` object, injected.** Binary resolution + version assertion happen once at
  construction; commands run through its methods. Rationale: auto-reel created an `FFmpegWrapper()` per `Clip`
  and `Movie`, re-running `shutil.which` constantly and giving no place to enforce the version gate.
  *Alternative considered:* free functions reading a global — rejected (untestable, hidden state).
- **Binary resolution order: explicit config/env → bundled jellyfin-ffmpeg → PATH** (D-1). An env var
  (e.g. `AUTO_REEL_NG_FFMPEG`) and a constructor arg both override. *Alternative:* PATH-only (auto-reel) —
  rejected; gives no version guarantee and no way to pin jellyfin-ffmpeg.
- **Version gate ≥ 7.1, parsed from `ffmpeg -version`.** Hard-fail early with a precise message. Rationale:
  later changes rely on 7.1-only filters (`pad_vaapi`); failing at startup beats a cryptic filter error mid-render.
- **Typed, immutable metadata (frozen dataclass).** Fields mirror the `media-probe` spec. Optional/absent data
  (no audio, no rotation) is modeled with explicit `None`/sentinel, never fabricated defaults.
- **Probe failures raise typed errors; batching is the caller's job.** `probe_media()` raises `ProbeError`;
  higher layers catch-and-skip per file. Rationale: keeps the probe pure and the fail-loud guarantee intact
  while still allowing a batch to continue (spec scenario "Batch continues past a bad file").
- **fps: `avg_frame_rate` → `r_frame_rate`, rational-parsed, bounds-checked (0 < fps ≤ 1000), else raise.**
- **Creation time from ffprobe tags by default; exiftool only behind an explicit flag.** Removes auto-reel's
  per-clip exiftool subprocess from the hot path.
- **Subprocess execution:** `subprocess.run` with captured output for probe/short commands; `Popen` + line
  reader for `-progress` on long encodes. No shell.

## Risks / Trade-offs

- **jellyfin-ffmpeg not present in dev/CI** → Mitigation: PATH fallback makes the system ffmpeg 7.1.3 work; CI
  installs an ffmpeg ≥ 7.1.
- **ffprobe field variance across codecs/containers** (rotation in side-data vs tag; bitrate sometimes absent)
  → Mitigation: tolerant parsing for genuinely-optional fields (bitrate may be `None`), strict only for fields
  the spec marks required (dimensions, fps); broad fixture coverage with real-camera samples.
- **Version-string parsing edge cases** (distro/`N-…` git builds) → Mitigation: parse leading `major.minor`,
  and on unparTable strings fail with the raw version echoed so the user can override.
- **"Exactly one ffprobe per file" vs optional exiftool** → Mitigation: exiftool is off by default and, when
  on, is a separate documented call; the single-probe guarantee is about ffprobe specifically.

## Migration Plan

Greenfield package — no migration. Deploys as the base the next change imports. Rollback = revert the change;
nothing else depends on it yet.

## Open Questions

- Final package name (`auto_reel_ng` vs `autoreel_ng`) and the env-var prefix — cosmetic, settle in tasks.
- Whether to expose parsed capability *structures* now or strictly raw text (leaning raw-text-only to keep
  interpretation wholly in change #2).
