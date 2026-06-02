## Why

auto-reel's GPU support was a single boolean (`is_gpu_codec`) that only knew NVENC *encoding* — decode,
scale, pad, and overlay all ran on CPU. auto-reel-ng must instead **discover what the host can actually do**
and emit the right ffmpeg fragments per vendor. The hardware spikes (`experiments/002–004`) proved why this
can't be assumed: on AMD, native `scale_vaapi,pad_vaapi` is the fast path, but `overlay_vaapi` is unsupported
and every GPU HDR-tonemap path **fails or crashes the GPU**. So capabilities must be **probed and
empirically self-tested**, never hardcoded — with a guaranteed CPU fallback. This change turns the raw
capability text from `ffmpeg-runtime` into a usable acceleration-profile API for the render pipeline (#4).

## What Changes

- **Capability detection:** enumerate accelerators and devices — parse `ffmpeg -hwaccels/-encoders/-decoders/
  -filters` (via `ffmpeg-runtime`), discover `/dev/dri/renderD*` nodes, `nvidia-smi -L`, VAAPI (`vainfo` per
  node), and OpenCL devices — into a typed **capability inventory** and a list of **enumerated devices**
  `{id, vendor, name, render_node}` (the dev host is dual-GPU: RX 9070 XT + Radeon 780M).
- **Startup self-test:** run a 1-frame synthetic clip through each candidate decode/normalize/overlay/tonemap/
  encode operation and **mark each as working / unsupported / faulting**, excluding anything that errors or
  crashes (directly modeling the `overlay_vaapi` and `tonemap_opencl` failures). Assume nothing.
- **Acceleration profiles:** a per-vendor profile (AMD-VAAPI, NVIDIA-CUDA/NVENC, Intel-QSV/VAAPI, CPU) that,
  for each logical op (decode, normalize=scale+pad, overlay, tonemap, encode), emits the correct ffmpeg
  argument fragments and declares **where frames live** (hw frame context) so callers know when an
  `hwupload`/`hwdownload` is forced. Each op carries a **guaranteed CPU fallback**.
- **Selection:** auto-pick the best available accelerator by capability (D-3), with an explicit override; a
  per-job **device selector** field is reserved for future multi-GPU targeting (D-4).
- AMD profile is grounded in verified results (`scale_vaapi,pad_vaapi`; no hw overlay; CPU-only tonemap;
  h264/hevc/av1 VAAPI encode). NVIDIA/Intel profiles are best-guess **gated entirely by the self-test**.

## Capabilities

### New Capabilities
- `capability-detection`: probe the host into a typed capability inventory + enumerated device list, and
  empirically self-test each candidate operation, excluding unsupported/faulting ones.
- `acceleration-profile`: per-vendor profiles that emit ffmpeg argument fragments per logical op with frame-
  location tracking, a guaranteed CPU fallback, and best-accelerator selection with override.

### Modified Capabilities
- `ffmpeg-runtime`: no requirement change — its raw capability-text accessors are consumed as-is.

## Impact

- **New code:** `auto_reel_ng/accel/` (detection, devices, profiles, self-test); tests with synthetic clips.
- **Consumes:** `ffmpeg-runtime` (capability text, command execution) and `media-probe` types.
- **Consumed by:** the future render pipeline (#4), which asks a selected profile for op fragments.
- **External tools (optional, probed if present):** `nvidia-smi`, `vainfo`; absence degrades gracefully to
  whatever ffmpeg reports + the self-test result. No new Python runtime dependencies.

## Non-goals

- Building the actual render filter-graph or concat (#4) — this change only **provides** the fragments/profile API.
- The HDR tonemap pipeline and title-overlay compositing logic (#4/#5) — detection exposes the capability flags
  (`can_tonemap_hw`, `can_overlay_hw`) but does not implement those stages.
- Persisting capabilities to Postgres (a service concern) — results are computed at startup with an optional
  in-process/file cache only.
- The GPU-aware job scheduler and multi-GPU balancing logic (#7); this change only **reserves** the device-selector field.
