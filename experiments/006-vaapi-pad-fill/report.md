# Experiment 006 — `pad_vaapi` fill colour and the VAAPI decode/filter device

- **Date:** 2026-09-27
- **Author:** auto-reel-ng (vaapi-pad-fill change)
- **Time-box:** ≤ 1h   **Status:** **Refuted** (`pad_vaapi` ignores `color`) **+ a latent device defect found and fixed**
- **Corrects:** exp 003 verdict, HLD §4.1 AMD "scale + pad" cell, HLD §8.2. **Change:** `openspec/changes/vaapi-pad-fill`

## Hypothesis
Exp 003 recorded `scale_vaapi,pad_vaapi` as the verified AMD normalize. It checked that the chain *runs* and
yields the right geometry (`hevc 1920×1080 SAR 1:1`), but never read a padded pixel back. We believed
**`pad_vaapi` honours its `color` option**, so its bars are the requested fill. We will know we're right if
a `pad_vaapi … color=black` band measures as black: chroma U/V ≈ 128 (neutral in both limited and full range).

## Why this matters
The first real-archive test render (5 events, 2026-09-27) showed **green bars beside every portrait phone
clip**. Any clip whose aspect differs from the 16:9 canvas is padded, so the whole archive's phone footage
was affected. The startup self-test classified the op by exit code only, so it was marked working.

## Environment
- ffmpeg **8.1.2**, Mesa **26.2.1** radeonsi (VAAPI), kernel 7.2.0, render node `/dev/dri/renderD128`.
- Observed first on the **RX 9070 XT** (the test render); the readings below were re-measured on
  **Radeon 860M** (PCI 1002:1114, `renderD128` at the time of writing). The defect reproduces on both, so it
  is a radeonsi VAAPI behaviour, not one card's.
- Source: `lavfi color=white:size=64x36` uploaded with `hwupload`, scaled into 64×64 with
  `scale_vaapi=…:force_original_aspect_ratio=decrease`, padded with `pad_vaapi=w=64:h=64:x=(ow-iw)/2:y=(oh-ih)/2:color=<c>`,
  downloaded, and the top padded band measured with `crop=16:8:0:0,signalstats`.

## Results

### Fill colour

| Pad | `color=` | Top-left pixel (RGB) | `signalstats` Y / U / V |
|---|---|---|---|
| `pad_vaapi` | `black` | (0, 135, 0) — green | 0 / 0 / 0 |
| `pad_vaapi` | `0x000000` | (0, 135, 0) | 0 / 0 / 0 |
| `pad_vaapi` | `0x000000FF` | (0, 135, 0) | 0 / 0 / 0 |
| `pad_vaapi` | `black@1.0` | (0, 135, 0) | 0 / 0 / 0 |
| CPU `pad` | `black` | (0, 0, 0) | 16 / 128 / 128 |

Every syntax paints **all-zero YUV**, which converts to green. The option is accepted and ignored. Chroma is
the robust signal: the faulty fill is U = V = 0, true black is U = V = 128 in any value range.

### Decode/filter device sharing
Fixing the fill means padding such clips on the CPU between a VAAPI decode and a VAAPI encode. The profile's
decode used `-hwaccel vaapi -hwaccel_device <node> -hwaccel_output_format vaapi`. With a CPU stage
(`hwdownload,…,transpose=1,scale,pad,…,hwupload`) in between:

| Decode flags | Result |
|---|---|
| `-hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi` | ❌ exit 234: `[hwupload] A hardware device reference is required to upload frames to.` |
| `-init_hw_device vaapi=va:/dev/dri/renderD128 -filter_hw_device va -hwaccel vaapi -hwaccel_device va -hwaccel_output_format vaapi` | ✅ exit 0, padded corner (0, 0, 0) |
| same shared flags, pure GPU `scale_vaapi` (no CPU stage) | ✅ exit 0, 1920×1080 |

A device created by `-hwaccel_device` at decoder open is not visible to the filter graph, so **every** CPU
mid-stage (pad, rotation `transpose`, CPU tonemap, the overlay bridge) failed to upload back. None had run
on the GPU with real footage before: the archive has no rotated or HDR clips.

### Related: `scale_vaapi` ignores SAR
`scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease` on a 1440×1080 SAR 4:3 frame outputs
1440×1080: it fits by pixel aspect, not display aspect (so does CPU `scale` by default). Whether a clip
needs padding therefore depends on its pixel aspect after rotation, not only its display aspect.

## Verdict
**Refuted.** `pad_vaapi` produces correct geometry but **ignores `color`** on Mesa radeonsi. Exp 003's
"works" was "runs". The device finding is independent and was a latent failure for every CPU bridge on AMD.

## Decision & next action (implemented in `vaapi-pad-fill`)
- The self-test gains an `amd.pad_fill` probe that reads the padded band back (`signalstats` U/V within
  128 ± 8) and sets `AcceleratorCapabilities.pad_fill_ok`. `amd.normalize` stays separate: scaling works.
- Normalize asks per clip whether bars are needed (exact `Fraction` compare of pixel and display aspect vs
  the canvas). No bars → `scale_vaapi` alone, all-GPU. Bars and `pad_fill_ok` false → CPU `scale,pad` with
  `hwdownload`/`hwupload`. Bars and `pad_fill_ok` true → `scale_vaapi,pad_vaapi`.
- The VAAPI decode names one shared device for decode and filters.
- `RENDER_GRAPH_VERSION` → 3; the capability cache gains a schema version.
- Real-archive re-render (5 events): "Olika Djur" at 156.7 s shows black pillars, corner RGB (0, 0, 0),
  U/V 128/128; all five movies pass `verify.py`; wall time 1:19 vs 1:22 before (the portrait clips are few).

## Open questions / follow-ups
- Whether a future Mesa honours `pad_vaapi`'s `color`. The self-test re-detects on an ffmpeg version change
  or a cache-schema bump; a Mesa-only upgrade keeps the cached flag until then.
- NVIDIA/Intel decode flags were not changed (no hardware to verify); they may share the same device gap.
