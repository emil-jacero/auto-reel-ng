# Experiment 004 — AMD HDR→SDR tonemap paths (OpenCL / VAAPI / Vulkan / CPU)

- **Date:** 2026-06-01
- **Author:** auto-reel-ng (spike)
- **Time-box:** ≤ 1h   **Status:** **Refuted** for GPU paths on AMD — only CPU tonemap works here
- **Unblocks:** HLD §4.1, §4.3, new HDR research item; OpenSpec #2 & #4 (HDR handling)

## Hypothesis
After `tonemap_vaapi` failed in exp 003, we believe **`tonemap_opencl`** (OpenCL is available on this AMD
card) gives a working on-GPU HDR→SDR path, with CPU `zscale,tonemap` as the fallback.

## Why this matters
Phone/camera HDR (HLG/PQ) footage must be tonemapped to SDR before merging with SDR clips, or colors blow
out. We need to know the cost and which path works per vendor.

## Environment
- Same host: ffmpeg 7.1.3; **dual AMD GPU** — OpenCL platform "AMD Accelerated Parallel Processing" exposes
  **Device #0 `gfx1201` (RX 9070 XT, dGPU = `/dev/dri/renderD128`)** and **Device #1 `gfx1103` (Radeon 780M
  iGPU = `/dev/dri/renderD129`)**. Mesa 26.0.4; OpenCL via rusticl. NVIDIA/Intel absent.
- Synthetic **HDR** source: `testsrc2`, `yuv420p10le`, tagged `bt2020nc / smpte2084 (PQ) / bt2020`. See `run.sh`.

## Results

| Path | Result |
|---|---|
| `tonemap_vaapi` (exp 003) | ❌ `VAAPI driver doesn't support HDR` |
| `libplacebo` Vulkan (exp 002) | ❌ VAAPI↔Vulkan interop broken on radv |
| `tonemap_opencl` → hwdownload → VAAPI encode | ❌ format negotiation fails at OpenCL→VAAPI handoff |
| `tonemap_opencl` → hwdownload → **libx264** (isolated) | ❌ **`Memory access fault by GPU node-1` — GPU crash (signal 6)** |
| **CPU `zscale=linear, tonemap=hable, zscale=bt709`** | ✅ **works**, `h264 bt709`, **1.77 s / 5 s clip (~0.35× realtime)** |

OpenCL device init needs explicit selection (`opencl=ocl:0.0`) because two devices are present; selection
worked, but the filter itself **faults the GPU** on this rusticl stack.

## Verdict
**Refuted for all GPU paths on this AMD/Mesa stack.** None of `tonemap_vaapi`, libplacebo (Vulkan), or
`tonemap_opencl` produce a working HDR→SDR result here — the OpenCL path actively **crashes the GPU**. The
**only working AMD HDR path is CPU** `zscale,tonemap`, which is correct but **slower than realtime** (~0.35×).

This is hardware/driver-specific (Mesa 26 / rusticl / radv on RDNA4). NVIDIA (CUDA `tonemap`/libplacebo) and
Intel are reportedly fine but **untested here**.

## Decision & next action
- **HDR tonemap is the weakest link on AMD.** The render pipeline must:
  1. **Detect HDR** from probe (`color_transfer ∈ {smpte2084, arib-std-b67}`), and
  2. tonemap via a **capability-ranked chain**: try the vendor GPU filter → **fall back to CPU `zscale,tonemap`**
     (the only thing that worked on AMD), and **never assume a GPU HDR path exists**.
- Because CPU tonemap is sub-realtime, **flag HDR clips in the GUI** (they cost more) and tonemap only the
  affected clips, not the whole timeline.
- Treat OpenCL tonemap as **disabled on AMD/rusticl** until a driver that doesn't fault is confirmed; gate it
  behind the startup self-test (a faulting filter must be caught and excluded).
- **Multi-GPU is real on this host** (dGPU + iGPU, two render nodes) — confirms the §4.8 decision to model GPUs
  as enumerated devices. The capability probe must list per-render-node devices and let jobs target one.

## Open questions / follow-ups
- Re-test all HDR paths on **NVIDIA** (CUDA `tonemap`, libplacebo) and **Intel** (`tonemap_vaapi`/QSV) — the
  GPU HDR story may be fine there; AMD is the outlier.
- Revisit `tonemap_opencl` on a newer Mesa/rusticl or with the AMDGPU-PRO OpenCL stack (the fault may be a
  rusticl bug, not a hardware limit).
- Decide default tonemap operator (hable vs mobius vs bt.2390) and peak-luminance handling.
