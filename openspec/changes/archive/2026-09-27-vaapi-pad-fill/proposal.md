## Why

The first test render of real archive footage (5 events, GPU, 2026-09-27) produced **green bars** beside every
portrait phone clip. The AMD path's native normalize, `scale_vaapi,pad_vaapi`, fits a 1440×1920 clip into the
1920×1080 canvas correctly, but **`pad_vaapi` ignores its fill colour on this Mesa/radeonsi stack**. Every
`color=` syntax tried (`black`, `0x000000`, `0x000000FF`, `black@1.0`) paints RGB (0, 136, 0), which is
all-zero YUV. The CPU `pad` paints (0, 0, 0).

- **Experiment 003** (HLD §8.2, "VAAPI padding ✅ RESOLVED") verified that `pad_vaapi` *runs* and produces the
  right geometry, but never read back a padded pixel.
- **The startup self-test** checks only the exit code, so it marks the operation working.

This is exactly the "presence is not capability" failure Principle III exists for. Here it is one level
deeper: "runs" is not "correct".

Fixing it exposed a second, latent defect. A GPU chain that needs a CPU stage between a VAAPI decode and a
VAAPI encode cannot upload its frames back: `hwupload` reports "A hardware device reference is required".
`-hwaccel_device` does not make its device available to the filter graph. The affected stages are:

- a CPU pad
- CPU rotation (`transpose`)
- CPU tonemap (the only HDR path on AMD, exp 004)
- the CPU overlay bridge

The spec requires every one of these to work (`clip-normalize`), but none had ever run on the GPU with real
footage. The archive happens to contain no rotated or HDR clips, which is why the render did not fail. A
manual test showed that one named device shared by decode and filters
(`-init_hw_device vaapi=va:<node> -filter_hw_device va -hwaccel vaapi -hwaccel_device va`) fixes both the
bridge (true black) and leaves the all-GPU path working.

This corrects HLD §8.2 and the §4.1 AMD column. It is part of HLD **§6 phase 2/4** (capabilities and render),
and it blocks the first library-wide render: every portrait clip would carry green bars.

## What Changes

- **The self-test verifies the hardware pad's fill, not just its exit code.** A new probe pads a
  non-16:9 synthetic frame with `pad_vaapi` in black, reads the padded region back through `signalstats`, and
  records a new capability flag, **`pad_fill_ok`**, true only when the padded pixels are black. On this host
  it is false.
- **Normalize pads on the GPU only when that is correct.** The render layer tells the profile whether a clip
  needs bars at all: its display aspect, after rotation and sample aspect ratio, differs from the canvas's
  exact aspect.
  - A clip that fills the canvas exactly (every 16:9 clip) keeps the all-GPU `scale_vaapi` path.
  - A clip that needs bars takes the all-GPU path only when `pad_fill_ok`, and otherwise falls back to the
    CPU scale and pad, with explicit transfers.
- **A VAAPI decode shares a named device with the filter graph.** Every CPU stage between a GPU decode and a
  GPU encode can then upload again: pad, rotation, tonemap and overlay.
- **The capability cache gains a schema version**, so an inventory cached before `pad_fill_ok` existed is
  re-detected rather than misread.
- **`RENDER_GRAPH_VERSION` becomes 3**, because padded clips render black instead of green.
- **HLD §8.2 and the §4.1 table are corrected**, and the manual test is recorded as **experiment 006**.

## Non-goals

- **No GPU-side fill workaround** (overlaying onto a black GPU surface). `overlay_vaapi` is unsupported on
  this stack (exp 003), and libplacebo interop is broken on radv (exp 002).
- **No change to NVIDIA or Intel paths.** Both already pad on the CPU (`cuda_normalize_filter`,
  `qsv_normalize_filter`). Their decode fragments are unchanged, because no bug has been observed there and
  there is no hardware to verify a change.
- **No clip-order fix.** The test render also showed clips ordered by case-sensitive filename. That is a
  separate decision.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `capability-detection`: new `Requirement: Hardware padding is verified by its output`.
- `acceleration-profile`:
  - new `Requirement: Clips are padded where the fill is correct`
  - new `Requirement: A hardware decode shares its device with the filter graph`

## Impact

- **Packages:**
  - `accel/`:
    - `selftest.py`: a probe with an output check
    - `models.py`: `pad_fill_ok` on `AcceleratorCapabilities`, and `needs_pad` on `OpParams`
    - `detection.py`: the flag and the cache schema
    - `profiles/vaapi.py`: the decode flags and the normalize choice
  - `render/`: `normalize.py` computes `needs_pad`.
  - `staleness/`: the version.
- **CLI vs API (Principle V):** neither gains a surface. Both render through the same engine.
- **Rendered output:** changes for clips that need bars on a host where `pad_fill_ok` is false (black bars
  instead of green). **`RENDER_GRAPH_VERSION` → 3.** The real archive has no NG renders yet, and dev libraries
  re-render once.
- **Performance:** unchanged for clips that fill the canvas, which is most of the archive (16:9). Clips that
  need bars run a CPU scale and pad with a download and upload, the experiment-002 "bridge" cost of about
  +40% for those clips only.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**. The capability cache file is
  invalidated once.
- **Dependencies:** none.
- **Size (Principle VIII):** one probe, one flag, one per-clip decision, one decode-flag change, two
  capability deltas.
