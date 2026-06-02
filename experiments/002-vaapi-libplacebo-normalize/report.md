# Experiment 002 — VAAPI + libplacebo GPU normalize (scale/pad/tonemap) on AMD

- **Date:** 2026-06-01
- **Author:** auto-reel-ng (spike)
- **Time-box:** ≤ 1.5h   **Status:** **Partial** (libplacebo works; fully-GPU-resident AMD chain refuted)
- **Unblocks:** HLD §4.1 (accel profiles), §4.3 (render pipeline), §8.1 + §8.2 (research items), OpenSpec change #2

## Hypothesis
We believe that on AMD (VAAPI via Mesa) we can build a **GPU-resident normalize pass** — VAAPI-decode →
**libplacebo** (Vulkan) scale+pad+SAR-normalize+tonemap → VAAPI-encode — with frames never leaving the GPU,
using libplacebo as the single cross-vendor filter that VAAPI alone can't provide (VAAPI can't pad).

## Why this matters
The whole differentiator is GPU-first, cross-vendor processing. libplacebo (Vulkan) is the candidate to
unify scale/pad/tonemap across NVIDIA/Intel/AMD. We need to know whether it actually composes with hardware
decode/encode without expensive CPU round-trips — this shapes the acceleration-profile design.

## Environment
- Fedora 43, kernel 6.17.7; ffmpeg **7.1.3** (built `--enable-libplacebo --enable-vulkan --enable-vaapi`).
- GPU: **AMD Radeon RX 9070 XT (RDNA4, gfx1201)**, Mesa **26.0.4** radeonsi + **radv** Vulkan; libva 2.23.
- Render nodes: `/dev/dri/renderD128`, `renderD129`. **No NVIDIA/Intel present — those paths untested.**
- ffmpeg emits `WARNING: radv is not a conformant Vulkan implementation, testing use only.`
- VAAPI on this card supports H264/HEVC/HEVC-Main10/**AV1** encode (`VAEntrypointEncSlice`) + VPP.
- Synthetic inputs (`lavfi testsrc2`). See `run.sh`.

## Method
Five tests: T1 libplacebo scale+pad with software I/O (correctness); T2 `scale_vaapi` alone (confirm it can't
pad); T3 fully-GPU `vaapi→hwmap vulkan→libplacebo→hwmap vaapi→hevc_vaapi`; B1/B2 "bridge" variants with a
`hwdownload→hwupload` round trip; and timing of CPU vs pure-VAAPI vs bridge over a 30s 720p→1080p job.

## Results
**Filter capability (from `-h filter=...`):** `scale_vaapi` exposes only `w/h` (**no pad**). `libplacebo`
exposes `w`, `h`, `force_original_aspect_ratio`, `normalize_sar`, `pad_crop_ratio`, `tonemapping`, `colorspace`,
`range` — i.e. **scale + letterbox-pad + SAR-normalize + HDR→SDR tonemap in one filter**.

| Test | Path | Result |
|---|---|---|
| **T1** | libplacebo, software in/out | ✅ **works** — output `1920x1080, SAR 1:1`, correctly letterboxed |
| **T2** | `scale_vaapi=1920:1080` | ⚠️ produces 1920×1080 but **stretched** (no pad) — confirms VAAPI can't letterbox |
| **T3** | vaapi→vulkan→libplacebo→**vulkan→vaapi**→encode | ❌ **fails**: `hardware pixel format 'vaapi' is not supported by device type 'Vulkan'` — **reverse Vulkan→VAAPI map unimplemented** |
| **B1** | vaapi→vulkan→libplacebo→hwdownload→hwupload→encode | ❌ `hwdownload: input must have a hardware frame reference` (graph negotiation fails on radv) |
| **B2** | sw→vulkan libplacebo→hwdownload→hwupload→encode | ❌ `Impossible to convert between formats` (hwupload negotiation) |

**Timing (30s, 720p→1080p):**

| Path | Wall time | vs realtime |
|---|---|---|
| [a] CPU all (`libx264`, `scale,pad`) | **3.64 s** | ~8× |
| [b] Pure VAAPI (`scale_vaapi` + `hevc_vaapi`) | **1.95 s** | ~15× |
| [c] Bridge VAAPI+libplacebo | — | failed to construct graph |

## Verdict
**Partial.**
- ✅ **libplacebo does scale+pad+SAR-normalize+tonemap in one filter** — strong cross-vendor candidate, works
  software-side here.
- ✅ **VAAPI decode+encode is real and fast** on AMD (~1.9× faster than CPU on a trivial op, and frees the CPU).
- ❌ **The fully-GPU-resident libplacebo↔VAAPI chain does NOT work out-of-the-box on AMD/radv.** The
  Vulkan→VAAPI reverse map is unimplemented, and `hwdownload/hwupload` bridge graphs failed format negotiation.
  The `radv is not conformant` warning indicates Vulkan-video interop here is immature.
- **Not tested (hardware-limited):** NVIDIA (CUDA↔libplacebo interop is reportedly more mature) and Intel QSV
  (`vpp_qsv` reportedly scales **and pads** in one filter — would avoid libplacebo entirely on Intel).

## Decision & next action
- **Do not assume one all-GPU graph via libplacebo+VAAPI in the acceleration-profile abstraction.** Model two
  strategies per profile and pick by capability probe:
  1. **Single-API graph** (preferred when possible): keep frames in one hw API. On Intel, `vpp_qsv` scales+pads.
     On AMD/VAAPI, padding needs research (composite via `overlay_vaapi` onto a black background, or accept a bridge).
  2. **Bridge** (`hw-decode → hwdownload → CPU/vulkan scale+pad+tonemap → hwupload → hw-encode`): still offloads
     decode+encode to the GPU; loses "fully resident." Must get the graph to actually build (B1/B2 are unsolved
     on radv — needs a working recipe or newer Mesa).
- **libplacebo is the best-quality scaler/tonemapper** and a great software/Vulkan path; treat its *hardware
  interop* as **driver/vendor-version-sensitive** and gate it behind a runtime capability test, not an assumption.
- **AMD letterboxing without libplacebo** is an open spec question — research `overlay_vaapi`-onto-background or
  whether newer Mesa adds `pad_vaapi`.
- Concretely feeds the §4.1 spec: the profile interface needs a `normalize(scale,pad,tonemap)` capability flag
  with a **per-vendor implementation and a guaranteed CPU/bridge fallback**, plus a startup self-test that runs
  a tiny clip through the chosen chain and falls back if it errors (exactly how T3/B1 failed).

## Open questions / follow-ups
- Working `hwdownload→hwupload` bridge recipe on AMD/radv (try newer Mesa; try `format=nv12` placement; try
  `-filter_hw_device` permutations). The interop, not the concept, is the blocker.
- Re-run T3/B1 on **NVIDIA (CUDA)** and **Intel (QSV/`vpp_qsv`)** — the abstraction must be validated per vendor.
- Confirm `overlay_vaapi`-onto-black as the AMD pad strategy; measure its cost.
- Compare libplacebo (Vulkan) scaler **quality** vs `scale_vaapi`/`scale_cuda` to justify the interop complexity.
