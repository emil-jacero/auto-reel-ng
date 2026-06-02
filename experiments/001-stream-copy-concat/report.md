# Experiment 001 — Stream-copy concat constraints

- **Date:** 2026-06-01
- **Author:** auto-reel-ng (spike)
- **Time-box:** ≤ 1h   **Status:** **Confirmed (with caveats)**
- **Unblocks:** HLD §4.3 (render pipeline), §8.4 (research item), OpenSpec change #4 (render pipeline)

## Hypothesis
We believe the ffmpeg **concat demuxer with `-c copy`** produces a clean, A/V-synced movie **only when all
input clips share** codec, profile, resolution, SAR, pixel format, and **timebase/framerate** (plus matching
audio params). We will know we're right if mismatched clips either fail or produce a player-broken/desynced
file, while matched clips concatenate cleanly — and if the mismatches are detectable from `ffprobe`.

## Why this matters
The chosen render strategy is "normalize on GPU + **stream-copy concat** when clips already match." We need
to know exactly when the zero-re-encode fast path is safe, so the pre-flight equivalence check is correct
and we don't silently ship broken movies.

## Environment
- Fedora 43, kernel 6.17.7; ffmpeg **7.1.3** (system build).
- Vendor-neutral test — no GPU involved (pure mux/copy). Results apply to all platforms.
- Synthetic inputs only (`lavfi testsrc2` + `sine`), 2s each. See `run.sh`.

## Method
Generated five 1080p/720p H.264+AAC clips differing in one property each (A baseline; B identical; C 720p;
D 25fps; E SAR 3:1). Ran `concat` demuxer with `-c copy` on A+{B,C,D,E} and inspected output frame count
(expect ~120 for clean 2×2s@30) and duration. Also ran the `concat` **filter** (re-encode) fallback on the
mismatched pair. Full script: `run.sh`.

## Results
Per-clip `time_base` tracked framerate: 30fps → `1/15360`, 25fps → `1/12800` (i.e. **fps determines timebase**).

| Pair | Difference | `-c copy` outcome | Frames | Notes |
|---|---|---|---|---|
| A+B | none (identical) | **clean video** | 120 | only an **audio** "Non-monotonic DTS" at the boundary |
| A+C | resolution 1080→720 | muxes "successfully", **no error** | 120 | variable-resolution stream → **breaks most players** (silent failure) |
| A+D | fps/timebase 30→25 | **mangled** | **110** | many video "Non-monotonic DTS"; frames lost/desync |
| A+E | SAR 1:1→3:1 | muxes "successfully", no error | 120 | aspect changes mid-stream → **display broken** (silent failure) |
| A+C | concat **filter** (re-encode) | clean | — | 4.01s, correct — the robust fallback |

Key observation: every boundary emitted an **AAC audio** `Non-monotonic DTS` (`96256` vs `96000`, a **256-sample**
discrepancy = AAC encoder priming/delay), **even for identical clips**.

## Verdict
**Confirmed.** Stream-copy concat is clean only when **timebase matches** (which requires identical fps) and
resolution/SAR/pix_fmt/codec all match. Two failure shapes:
1. **Hard failure** (different timebase/fps): dropped frames, non-monotonic DTS, desync.
2. **Dangerous silent failure** (different resolution or SAR): ffmpeg returns **exit 0** and writes a file,
   but it's a variable-resolution/aspect stream that breaks playback. **Exit code cannot be trusted** — the
   pre-flight check must catch these.
Additionally, **AAC priming** injects a small (~256-sample ≈ 5.3 ms) timestamp discontinuity at every join
even for identical clips.

Not tested: long-chain accumulation of audio priming drift; MP4 edit-lists; B-frame/open-GOP boundary effects
across real camera files (synthetic clips are closed-GOP-ish).

## Decision & next action
- The render pipeline's fast path must be **guarded by a strict ffprobe equivalence check** over:
  `codec_name, profile, width, height, sample_aspect_ratio, pix_fmt, time_base` (and audio
  `codec_name, sample_rate, channels, channel_layout`). **All must match** → copy; otherwise **normalize**.
- Because resolution/SAR mismatches mux without error, **never rely on ffmpeg's exit code** to validate the
  copy path — validate from probe data *before* choosing it, and ideally verify the output.
- For audio, prefer **re-encoding/normalizing audio** (or `aresample=async=1` / `apad`+atrim) at the join to
  avoid AAC-priming gaps; pure audio stream-copy concat is risky. Cheap because audio re-encode is fast.
- This makes the **normalize pass the common path** and the copy path a narrow optimization for already-uniform
  exports (e.g. same-camera clips). Spec #4 should treat normalize as default, copy as detected fast path.

## Open questions / follow-ups
- Measure audio-priming drift over many (10+) joins to decide if audio re-encode is mandatory.
- Test with real camera files (variable GOP, rotation metadata, MP4 edit lists) before trusting the fast path.
