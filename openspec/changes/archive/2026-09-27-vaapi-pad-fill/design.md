## Context

See proposal.md — Why. The facts that shape the approach, all verified on the dev host (RX 9070 XT,
Mesa/radeonsi, ffmpeg 8.1) on 2026-09-27:

- **`pad_vaapi` paints its padded region all-zero YUV**, which shows as RGB (0, 136, 0) green, for every
  `color=` syntax. The CPU `pad` with `black` paints (0, 0, 0).
- **The fill is measurable as text.** `…,hwdownload,format=nv12,crop=16:8:0:0,signalstats,metadata=mode=print:key=lavfi.signalstats.UAVG:file=-`
  prints `UAVG=0` for the faulty GPU pad and `UAVG=128` for true black. Chroma of 128 is neutral, whether
  the video uses the limited or full value range.
- **The GPU decode has no device the filters can use.** `-hwaccel vaapi -hwaccel_device <node>` followed by a
  CPU stage and `hwupload` fails: "A hardware device reference is required to upload frames to".
  `-init_hw_device vaapi=va:<node> -filter_hw_device va -hwaccel vaapi -hwaccel_device va -hwaccel_output_format vaapi`
  succeeds: the CPU-padded bridge gives true black, and the pure-GPU `scale_vaapi` path still works.
- **Code:**
  - `accel/selftest.py` classifies a probe by exit code only.
  - The VAAPI normalize probe is keyed `amd.normalize`.
  - `detection._PAD_FILTER` sets `pad_filter` from that probe.
  - `profiles/vaapi.py` has `_decode` (with `-hwaccel_device node`) and `_normalize` (`scale_vaapi,pad_vaapi`
    whenever `pad_filter` is set).
  - `render/normalize.py:_canvas_stages` asks the profile for `NORMALIZE`, with `OpParams(width, height,
    fill_color, …)` and no knowledge of the clip.
  - The capability cache's fingerprint is `(ffmpeg_version, device ids)`.

## Goals / Non-Goals

**Goals:**

- No coloured bars, on any vendor.
- Clips that fill the canvas keep the fastest path.
- Every CPU mid-stage works between a GPU decode and a GPU encode.

**Non-Goals:**

- A GPU-side black fill workaround (proposal: Non-goals).
- Changing NVIDIA/QSV decode flags without hardware to verify them.

## Research & Decisions

### Detecting a faulty fill

**Decision**:
- `Probe` gains an optional `expect: Callable[[str], bool]` that is applied to the probe's stdout after a
  zero exit. `False` classifies the probe `UNSUPPORTED`, with a reason.
- A new probe `amd.pad_fill` scales a 64×36 synthetic frame into 64×64 with `scale_vaapi` and `pad_vaapi`
  (`color=black`). It downloads the frame, crops the top padded band, and prints `signalstats` `UAVG` and
  `VAVG`.
- `expect` passes when both are within 128 ± 8.
- `detection` sets `AcceleratorCapabilities.pad_fill_ok = works("amd.pad_fill")` for VAAPI. It is `True` for
  the NVENC and QSV profiles, whose pads are CPU `pad` inside their filter strings, and it is ignored by the
  CPU profile.

**Rationale**:
- A pixel-level check is the only thing that catches "runs but wrong".
- Chroma, not luma, is the robust signal. Black is chroma 128 in any value range, while the faulty fill is
  chroma 0.
- Keeping `amd.normalize` separate preserves "scale works" for the 16:9 path, which is most of the archive.

### Deciding per clip whether padding is needed

**Decision**:
- `OpParams` gains `needs_pad: bool = False`.
- `render/normalize.py` computes it from the clip's facts before asking for `NORMALIZE`:

  ```python
  def _needs_pad(clip: ClipMetadata, rotate: Optional[int], target: TargetSpec) -> bool:
      w, h = (clip.height, clip.width) if (rotate or clip.rotation or 0) % 180 == 90 else (clip.width, clip.height)
      canvas = Fraction(target.width, target.height)
      sar = Fraction(_normalize_sar(clip.sample_aspect_ratio).replace(":", "/"))
      return Fraction(w, h) != canvas or Fraction(w, h) * sar != canvas
  ```

  Both the pixel and the display aspect must match. `scale_vaapi` (like CPU `scale`) fits by pixel aspect and
  ignores SAR (exp 006: a 1440×1080 SAR 4:3 frame stays 1440×1080), so a display-aspect-only check would send
  an anamorphic 16:9 clip down the pad-less path and emit a wrong-size frame.

  Exact `Fraction` comparison means a 1920×1088 clip (30/17) counts as needing padding, and 3840×2160,
  1920×1080 and 1280×720 (all exactly 16/9) do not.
- `VaapiProfile._normalize`:
  - No `pad_filter`: `None`, the CPU fallback, as today.
  - `needs_pad` and not `pad_fill_ok`: `None`, so the CPU scale and pad run for this clip, and the existing
    composer inserts `hwdownload` and `hwupload`.
  - `not needs_pad`: `scale_vaapi=w=W:h=H:force_original_aspect_ratio=decrease` alone. An exact-aspect scale
    fills the canvas, so a pad would be a no-op.
  - Otherwise, with `pad_fill_ok`: `scale_vaapi,pad_vaapi` as today.

**Rationale**: The profile stays vendor-knowledgeable and the render layer stays vendor-free (Principle III):
`render/` states a geometric fact about the clip, and only `accel/` knows that a particular pad is faulty.

**Alternative rejected**: the CPU pad for every clip on this host. That costs the bridge (about +40%, exp 002)
on the 16:9 majority for no visible benefit.

### Sharing the device between decode and filters

**Decision**: `VaapiProfile._decode` emits
`-init_hw_device vaapi=va:<node> -filter_hw_device va -hwaccel vaapi -hwaccel_device va -hwaccel_output_format vaapi`.
The node falls back to `vaapi=va` when unknown, as `upload_device_flags` already does.

`render/normalize.py`'s software-decode branch keeps using `upload_device_flags`, because it has no decode
device. The hardware-decode branch now carries its own named device, so no command ever initializes two.

**Rationale**:
- It is the verified working form.
- Naming the device once removes the reliance on ffmpeg auto-selecting "the only device" for filters, which
  it does not do for a `-hwaccel_device` created at decoder open.
- It fixes pad, rotation, tonemap and overlay bridges in one place.

### Cache schema

**Decision**: A module constant `_CACHE_SCHEMA = 2` is prepended to `_fingerprint(...)`. `_load_cache` also
treats a missing `pad_fill_ok` key as a mismatch (belt and braces).

**Rationale**: The fingerprint was only the ffmpeg version and devices, so a code change to what is detected
had no way to invalidate it.

### Recording the finding

**Decision**: The manual verification becomes **experiment 006, `vaapi-pad-fill`**, in `experiments/`, per
the project's running-experiments convention. It includes:
- the hypothesis ("pad_vaapi honours `color`")
- the four `color=` syntaxes and their readings
- the device-sharing test
- the conclusion

HLD §8.2 is changed from "✅ RESOLVED" to name the fill defect and point at exp 006. The §4.1 AMD cell
becomes `scale_vaapi` ✅, `pad_vaapi` ⚠️ (geometry correct, fill ignored on Mesa; the self-test decides).

## Failure behavior and idempotency

- **A probe whose `expect` fails** is `UNSUPPORTED` with a reason, so detection still returns an inventory.
- **A clip on the CPU fallback path** is slower but correct. There's no new render failure mode.
- **Renders stay deterministic** for a given inventory.
- **Re-detection** after the cache schema bump happens once.
- **`--force`** re-renders, as usual.
- **Worker restart:** a requeued job gets the same decisions.
- **`RENDER_GRAPH_VERSION` → 3.** Output for padded clips changes on hosts with a faulty fill.

## Risks / Trade-offs

- **[A driver update fixes `pad_vaapi`'s fill]** → The self-test notices on its next re-detection (a new
  ffmpeg version, or the schema), and GPU padding comes back automatically.
- **[The shared-device flags change every VAAPI golden command]** → The expected strings are updated in the
  same change. The GPU-marked end-to-end tests are the real proof.
- **[SAR strings like `N/A` or `0:1`]** → `_normalize_sar` already maps these to 1:1.
- **[Rotation metadata in both the clip and the segment override]** → The segment's explicit `rotate` wins,
  matching `_canvas_stages`, which applies `segment.rotate`.

## Migration Plan

Deploy. The capability cache re-detects once. Dev libraries re-render once (engine stale). On the real
archive, the first library render produces black bars. Rollback means reverting the probe, flag and flags,
plus the version.
