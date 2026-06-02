# Experiment 003 — AMD VAAPI-native normalize (pad / overlay / tonemap / AV1)

- **Date:** 2026-06-01
- **Author:** auto-reel-ng (spike)
- **Time-box:** ≤ 1.5h   **Status:** **Confirmed** (native GPU normalize works) **+ two driver gaps found**
- **Unblocks:** HLD §4.1 (accel profiles), §4.3 (render), §4.4 (title overlay), §8.1/§8.2, OpenSpec #2 & #4

## Hypothesis
After exp 002 refuted the libplacebo↔VAAPI route on AMD, we believe a **single-API VAAPI graph** can do the
whole normalize (scale + letterbox-pad + encode) on-GPU without Vulkan or a CPU round-trip — and that it
beats both the bridge and CPU on speed. We will know we're right if `scale_vaapi,pad_vaapi → *_vaapi`
produces a correct letterboxed file faster than the alternatives.

## Why this matters
Normalize (scale+pad to a common canvas) is the per-clip workhorse of the render pipeline. If it runs
single-API on the GPU, the AMD acceleration profile is simple and fast. The title overlay and HDR paths also
need to be settled to size spec #4.

## Environment
- Same host as exp 002: Fedora 43, ffmpeg **7.1.3**, **AMD RX 9070 XT**, Mesa **26.0.4** radeonsi + radv,
  libva 2.23, render node `/dev/dri/renderD128`. **NVIDIA/Intel not present — untested.**
- Synthetic 1080×1080 (square) source so pillarboxing into 16:9 is visible. See `run.sh`.

## Results

**Filter availability (corrected from exp 002):** `pad_vaapi` **DOES exist** in ffmpeg 7.1.3 (I missed it
earlier). Options: `w, h, x, y, color, aspect`. So VAAPI *can* pad natively — the "VAAPI can't pad" claim is
true only for older ffmpeg.

| Test | Path | Result |
|---|---|---|
| **A** | `overlay_vaapi` (scaled fg onto black bg) | ❌ **`VAAPI driver doesn't support overlay`** (AMD Mesa) |
| **B** | bridge: vaapi-decode → `hwdownload` → sw `scale,pad` → `hwupload` → `hevc_vaapi` | ✅ works, `hevc 1920×1080` |
| **D** | **native `scale_vaapi,pad_vaapi` → `hevc_vaapi`** | ✅ **works, `hevc 1920×1080 SAR 1:1`** |
| **E** | native `scale_vaapi,pad_vaapi` → **`av1_vaapi`** | ✅ **works, `av1 1920×1080`** |
| **F** | `tonemap_vaapi` (HDR→SDR) | ❌ **`VAAPI driver doesn't support HDR`** (AMD Mesa) |

**Timing (30 s, 1080×1080 → 1920×1080 pillarbox):**

| Path | Wall time | Note |
|---|---|---|
| **native `scale_vaapi,pad_vaapi`** | **1.98 s** | fastest; fully GPU; ~15× realtime |
| bridge (`hwdownload`/`hwupload` + CPU pad) | 2.83 s | offloads only decode+encode; PCIe + CPU filter cost |
| CPU all (`libx264`, `scale,pad`) | 3.18 s | baseline |

## Verdict
**Confirmed** for the core path: **`scale_vaapi,pad_vaapi → {h264,hevc,av1}_vaapi` is a clean, fast,
single-API GPU normalize on AMD** — the recommended AMD render path, and it's the fastest option tested.
Two **AMD-Mesa driver gaps** found that shape the design:
- ❌ **`overlay_vaapi` unsupported** → cannot composite the title card on-GPU via VAAPI on AMD.
- ❌ **`tonemap_vaapi` unsupported** → no on-GPU HDR→SDR via VAAPI on AMD (and libplacebo interop is broken
  per exp 002).
Both gaps are **driver/vendor-specific**, not ffmpeg-wide — exactly why the profile layer must probe at runtime.

## Decision & next action
- **AMD profile normalize = `scale_vaapi,pad_vaapi`** (single API, on-GPU, fastest). Update §4.1/§4.3.
- **Title overlay (§4.4):** since `overlay_vaapi` is unavailable on AMD and there's no GPU text filter, the
  title must be composited via a **short CPU bridge** OR rendered as a **separate full-screen title segment**
  that is simply concatenated (no overlay at all). Only the title segment (a few seconds) pays any CPU cost;
  the bulk of footage stays full-GPU. **Prefer "title as its own segment" to keep the pipeline overlay-free
  and cross-vendor-friendly** — this also sidesteps NVIDIA/Intel overlay-filter differences.
- **HDR (§8 new item):** on AMD, fall back to **`tonemap_opencl`** (OpenCL is available here) or CPU
  `zscale,tonemap`. Needs its own spike with real HDR input.
- The profile interface needs capability flags `can_overlay_hw`, `can_tonemap_hw`, `pad_filter` with a
  **startup self-test** (run a 1-frame clip through the chosen chain; fall back on the exact errors seen here).
- AV1 hardware encode is viable on this card → keep AV1 as a selectable output, not a v1 blocker.

## Open questions / follow-ups
- Spike **`tonemap_opencl`** on AMD with real HDR (HLG/PQ) input — the candidate GPU HDR path.
- Validate native scale+pad equivalents on **NVIDIA** (`scale_cuda`/`scale_npp` + `pad`? overlay_cuda works?)
  and **Intel** (`vpp_qsv` does scale+pad in one filter; `overlay_qsv` availability) — the abstraction must be
  proven per vendor before §4.1 is finalized.
- Measure title-as-segment vs title-as-bridge-overlay quality/seam on real footage.
