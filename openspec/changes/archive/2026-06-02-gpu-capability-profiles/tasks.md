## 1. Package & data model

- [x] 1.1 Create `auto_reel_ng/accel/` package (`detection.py`, `devices.py`, `profiles/`, `selftest.py`, `selection.py`) and an `AccelError` in the error hierarchy. *(Also added `models.py` for the typed models and `profiles/base.py` + `profiles/hardware.py` for the profile interface and shared CPU-fallback routing.)*
- [x] 1.2 Define typed models: `Device {id, vendor, name, render_node}`, `CapabilityInventory` (encoders/decoders/hwaccels/filters + per-accelerator flags), and `OpClass`/`FrameLocation` enums. Frozen/immutable, with `to_dict()` for logging.
- [x] 1.3 Define the `OpFragment` type (input flags, filter snippet, output/encoder flags, `frames_in`/`frames_out`).

## 2. Capability detection

- [x] 2.1 Parse ffmpeg `-hwaccels/-encoders/-decoders/-filters` text (from `ffmpeg-runtime`) into the inventory. (spec: Accelerator and device enumeration)
- [x] 2.2 Enumerate devices: `/dev/dri/renderD*` nodes, optional `nvidia-smi -L`, optional `vainfo` per render node, optional OpenCL list; merge into `Device` list with stable ids; absence of any tool degrades gracefully. (spec scenarios: multiple GPUs; optional tool absence) *(OpenCL enumeration intentionally deferred: render-node + PCI-vendor discovery already identifies every GPU as a `Device` — including the dual-AMD OpenCL devices from exp 004, which surface as `renderD128`/`renderD129` — so a `clinfo` source would add no devices not already found. It can be added later purely as name enrichment if needed.)*
- [x] 2.3 Tests: inventory reflects a mocked encoders listing; two render nodes → two devices; missing `nvidia-smi` still succeeds.

## 3. Startup self-test

- [x] 3.1 Build tiny synthetic 1-frame clips via `ffmpeg lavfi` for use as self-test inputs.
- [x] 3.2 Implement `selftest` that runs each candidate op (decode/normalize/overlay/tonemap/encode) **in a child process with a timeout**, classifying result as working / unsupported / faulting; a crash or hang is contained and recorded, never fatal. (spec: Empirical self-test; faulting op excluded)
- [x] 3.3 Fold self-test results into the inventory: only self-test-passing ops become usable; presence-without-pass is excluded. (spec: Presence alone is insufficient)
- [x] 3.4 Compute capability flags (`pad_filter`, `can_overlay_hw`, `can_tonemap_hw`, usable encoders by codec, decode method) from self-test results. (spec: Capability flags for downstream stages)
- [x] 3.5 Tests on the real host: AMD reports `pad_vaapi` usable, `can_overlay_hw=false`, `can_tonemap_hw=false`, h264/hevc/av1 VAAPI encoders usable (asserts the exp 002–004 findings); a deliberately-bad op is classified unsupported/faulting without crashing the suite.

## 4. Acceleration profiles

- [x] 4.1 Define the `AccelProfile` interface: `fragment(op, params) -> OpFragment` per logical op, plus the op-coverage it claims.
- [x] 4.2 Implement the **CPU profile** (complete + always usable): `scale,pad`, `overlay`, `zscale,tonemap`, `libx264/libx265/svtav1` encoders, decode = software.
- [x] 4.3 Implement the **AMD/VAAPI profile** from verified results: decode `-hwaccel vaapi -hwaccel_output_format vaapi`; normalize `scale_vaapi,pad_vaapi`; encode `h264/hevc/av1_vaapi`; overlay+tonemap delegate to CPU fallback. (spec: AMD normalize; tonemap falls back to CPU)
- [x] 4.4 Implement **NVIDIA** and **Intel** profiles as best-guess fragments (NVENC + `scale_cuda`; QSV + `vpp_qsv` scale, pad via libplacebo/CPU per research), each op gated by the self-test before use.
- [x] 4.5 Implement frame-location tracking on every emitted op and a helper that inserts `hwupload`/`hwdownload` markers where adjacent ops' locations disagree. (spec: Frame-location tracking)
- [x] 4.6 Golden-fragment tests (no GPU needed): assert the exact argument strings each profile emits per op, including AMD `scale_vaapi,pad_vaapi` and CPU fallbacks.

## 5. Selection

- [x] 5.1 Implement best-accelerator selection: rank usable profiles, prefer hardware over CPU, honor an explicit vendor/device override or fail clearly. (spec: Best-accelerator selection)
- [x] 5.2 Add the per-request `device` selector (default `auto`); v1 picks the first usable device; reserve for D-4. (spec: Device selector defaults to auto)
- [x] 5.3 Tests: auto-pick chooses hardware over CPU when available; override honored / clear error when unusable; CPU-only host yields a complete profile; default selector requires no caller input.

## 6. Caching & wire-up

- [x] 6.1 Cache inventory+self-test in-process and optionally to a file keyed by a host fingerprint (ffmpeg version + device set); a flag forces refresh; fingerprint mismatch invalidates the cache.
- [x] 6.2 Expose `detect_capabilities()`, `select_profile()`, the profile classes, models, and `AccelError` from the package public API; ensure `task lint:check` and `pytest` pass clean.
