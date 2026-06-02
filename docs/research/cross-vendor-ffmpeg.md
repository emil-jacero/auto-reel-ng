# Research note — Cross-vendor GPU ffmpeg (distribution, libplacebo, VAAPI/QSV pad, concat)

> Literature research (web, primary sources) complementing the hardware spikes in `experiments/`.
> Date: 2026-06-01. Every claim below is backed by a cited source; see links inline.

## TL;DR decisions

1. **Distribution: standardize on `jellyfin-ffmpeg`** *(LOCKED as HLD Decision D-1, §4.12 — bundled default,
   engine binary-agnostic, ffmpeg ≥ 7.1 asserted at startup)* for the Linux container — the only single build shipping
   NVENC/NVDEC + QSV + VAAPI + AMF(Win) + libplacebo, actively maintained for exactly this multi-vendor use.
   `BtbN/FFmpeg-Builds` (`gpl`) is the static-binary/Windows alternative. Avoid distro ffmpeg (stale, missing
   bits). **The Fedora dev host's own ffmpeg 7.1.3 already has all of this** — fine for development.
2. **Licensing:** any build with x264/x265 or hw encoders is effectively **GPL** → redistributing it in an
   image obliges you to publish the exact source + configure line. The **`nonfree` (fdk-aac) variant is NOT
   redistributable** — never ship it. ([FFmpeg legal](https://www.ffmpeg.org/legal.html))
3. **AMD pad = native `scale_vaapi,pad_vaapi`** (matches exp 003). `pad_vaapi` is new in **FFmpeg 7.1**
   (Sep 2024). ([7.1 Changelog](https://git.ffmpeg.org/gitweb/ffmpeg.git/blob/refs/heads/release/7.1:/Changelog))
4. **⚠️ Correction: `vpp_qsv` CANNOT pad.** It does scale + **crop** only (`w/h` scale, `cw/ch/cx/cy` crop) —
   no pad/letterbox/fillcolor param. For Intel QSV letterboxing use **libplacebo** or a CPU `pad` bridge.
   ([vf_vpp_qsv source](https://ffmpeg.org/doxygen/trunk/vf__vpp__qsv_8c_source.html))
5. **⚠️ Correction: libplacebo pad syntax** is `normalize_sar=1` + `pad_crop_ratio=0.0` + `fillcolor` — NOT the
   `pad_w/pad_h/pad_color` options some sources invent. ([ffmpeg-filters](https://ffmpeg.org/ffmpeg-filters.html))

## libplacebo as a cross-vendor filter (scale + pad + tonemap in one)

- Vulkan-based → same syntax on NVIDIA/Intel/AMD. One instance scales, letterboxes, and tonemaps HDR→SDR.
- Letterbox via `w/h` + `force_original_aspect_ratio=decrease` + `normalize_sar=1` + `pad_crop_ratio=0.0`
  - `fillcolor=black`. Tonemap via `tonemapping=bt.2390` (+ `colorspace/color_primaries/color_trc/range`).
- **Interop:** must derive the Vulkan device from the decode device to share frames:
  - NVIDIA: `-init_hw_device cuda=cu -init_hw_device vulkan=vk@cu -filter_hw_device vk` (+ `format=nv12` before NVENC).
  - VAAPI: `-init_hw_device vaapi=va:/dev/dri/renderD128 -init_hw_device vulkan=vk@va -filter_hw_device vk`.
- **Gotchas (relevant to our exp 002 failure on AMD/radv):**
  - **Device init order matters** (decode device → `vulkan@source` → `-filter_hw_device`). ([trac #11229](https://trac.ffmpeg.org/ticket/11229))
  - **Vulkan video is gated behind driver env vars**: AMD/RADV `RADV_PERFTEST=video_decode`, Intel/ANV
    `ANV_DEBUG=video-decode`, Mesa ≥ 24.1. ([mpv #13909](https://github.com/mpv-player/mpv/discussions/13909))
    → **our exp 002 did not set `RADV_PERFTEST` — worth one retry before declaring AMD libplacebo dead.**
  - **Intel-via-Vulkan is the least reliable**; native QSV usually more robust.
  - Not guaranteed zero-copy; wrong config silently falls back to copies + sub-realtime. Be explicit with `format=`.

## VAAPI / QSV padding summary

| Vendor | On-GPU letterbox | Notes |
|---|---|---|
| AMD VAAPI | ✅ `scale_vaapi,pad_vaapi` (FFmpeg ≥ 7.1) | verified in exp 003; fastest path |
| Intel QSV | ❌ no native pad — **libplacebo** or `vpp_qsv` scale → hwdownload → `pad` → hwupload | `vpp_qsv` scales+crops only |
| Any (< 7.1 or missing) | `scale_* → hwdownload → pad → hwupload` | PCIe bridge cost ~25–30%, worse at 4K |

## Stream-copy concat — detectability (refines exp 001)

`ffprobe -show_streams -show_format -print_format json` **does** surface: codec, profile, level, width/height,
SAR/DAR, pix_fmt, color_range/space, time_base, frame rate, audio codec/sample_rate/channel_layout/bit-depth.

It **does NOT** reliably surface — and these are exactly what cause silent copy-concat glitches:

- **GOP open vs closed** & B-frame reference structure (needs `-show_packets`/`-show_frames` keyframe analysis;
  x264 defaults closed, **x265 defaults open** → `open-gop=0` to fix). ([open/closed GOP](https://streaminglearningcenter.com/blogs/open-and-closed-gops-all-you-need-to-know.html))
- **MOV edit lists** (container timing offsets). ([trac #2325](https://trac.ffmpeg.org/ticket/2325))
- **AAC priming / encoder delay** (in extradata → cumulative drift; matches the 256-sample gap seen in exp 001).
  ([Apple AAC priming](https://developer.apple.com/documentation/quicktime-file-format/appendix_g_audio_priming_handling_encoder_delay_in_aac))

→ Design consequence: the copy fast-path's probe check is **necessary but not sufficient**. Either (a) restrict
copy to same-encoder/same-source clips, (b) add a keyframe/GOP packet check, or (c) just **normalize** (default).
Audio should be normalized/re-encoded at joins regardless.

## Sources

Distribution/licensing: [jellyfin HW accel](https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/) ·
[jellyfin-ffmpeg](https://github.com/jellyfin/jellyfin-ffmpeg) · [BtbN builds](https://github.com/BtbN/FFmpeg-Builds) ·
[FFmpeg legal](https://www.ffmpeg.org/legal.html). libplacebo: [ffmpeg-filters](https://ffmpeg.org/ffmpeg-filters.html) ·
[trac #11229](https://trac.ffmpeg.org/ticket/11229) · [mpv #13909](https://github.com/mpv-player/mpv/discussions/13909) ·
[NVIDIA ffmpeg guide](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/ffmpeg-with-nvidia-gpu/index.html).
Pad: [pad_vaapi commit](https://ffmpeg.org/pipermail/ffmpeg-cvslog/2024-April/142630.html) ·
[7.1 Changelog](https://git.ffmpeg.org/gitweb/ffmpeg.git/blob/refs/heads/release/7.1:/Changelog) ·
[vf_vpp_qsv source](https://ffmpeg.org/doxygen/trunk/vf__vpp__qsv_8c_source.html).
Concat: [trac Concatenate](https://trac.ffmpeg.org/wiki/Concatenate) · [ffmpeg-formats](https://ffmpeg.org/ffmpeg-formats.html) ·
[trac #2325](https://trac.ffmpeg.org/ticket/2325).
