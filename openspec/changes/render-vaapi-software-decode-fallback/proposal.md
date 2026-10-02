## Why

On this host (AMD RX 9070 XT, VAAPI profile auto-selected) an event containing one MPEG-4 Part 2 clip
(`ffmpeg -c:v mpeg4`, `.avi`) cannot be rendered at all. `auto-reel render` ends `0/1 events succeeded` with

```
[mpeg4] No support for codec mpeg4 profile 0.
Failed setup for format vaapi: hwaccel initialisation returned error
Task finished with error code: -38 (Function not implemented)
Conversion failed!
```

while `--device cpu` renders the same event. Old camcorder and phone footage in the archive (`.avi`, MPEG-4
Part 2, MJPEG, 10-bit or 4:2:2 H.264) is exactly what the hardware decoder lacks, and one such clip fails the
whole event.

The cause is that the decode fragment is chosen with no knowledge of the clip. `VaapiProfile._decode` looks
only at `capabilities.decode_method`, which the startup self-test sets from a single h264 probe clip
(`accel/selftest.py`), and `build_normalize_command` calls `profile.fragment(OpClass.DECODE, params)` with an
`OpParams` that carries no source codec. Nothing in `render/` or `accel/` retries with a software decode.

This violates Principle III (detect capabilities, never assume: "every profile MUST have a working CPU
fallback; a host with no usable GPU still renders") at the finest grain: a GPU that decodes *some* codecs is
treated as decoding *all* of them. HLD §4.1 already says the decode row is "software" for the CPU and
hardware otherwise, and the render pipeline (§4.3) already composes a system-memory decode feeding a
hardware encoder (`format=nv12,hwupload` plus `-init_hw_device`/`-filter_hw_device`, spec
`acceleration-profile`, "A hardware decode shares its device with the filter graph"; golden test
`test_software_decode_names_the_device_hwupload_needs`). That composition was proven for this failure on the
RX 9070 XT: `ffmpeg -init_hw_device vaapi=va:/dev/dri/renderD128 -filter_hw_device va -i mpeg4.avi -vf
'format=nv12,hwupload,scale_vaapi=…,pad_vaapi=…' -c:v h264_vaapi` exits 0.

HLD §6 phase: 2 (capability detection and profiles) and 4 (render pipeline), a bug fix to both; no §8
research item is open for it.

## What Changes

- **Proactive (accel).** `AcceleratorCapabilities` records, per codec, the highest bit depth the device's
  hardware decoder handles (`hw_decode`), filled from a static per-vendor table and kept only when the
  decode self-test passed. A profile answers `can_hw_decode(codec, pix_fmt)`; hardware decode requires a
  codec in the table, 4:2:0 chroma and a bit depth within the table's limit. The capability cache schema is
  bumped so an older cache is re-detected.
- **Proactive (render).** `build_normalize_command` asks the profile per clip. A clip the hardware cannot
  decode gets the software DECODE fragment, so the existing composition inserts `format=nv12,hwupload` before
  the hardware scale/pad and names the upload device. Hardware-decodable clips (and every golden string
  already in the suite) are unchanged.
- **Reactive safety net (render).** If a hardware-decode normalize fails with ffmpeg's
  `hwaccel initialisation returned error` or `Failed setup for format`, the orchestrator logs a warning,
  rebuilds that one segment with software decode and runs it once more. Any other failure, and a failure of
  the retry, is raised as before.
- Tests: golden argument strings for an `mpeg4` clip on the VAAPI profile (and the 10-bit H.264, rotated,
  and bars-needed variants); a fake-runtime retry test; one `has_ffmpeg` + `gpu` end-to-end render of an
  MPEG-4 `.avi` through VAAPI.

**Non-goals**

- No change to which clips are copy-eligible, to the staleness fingerprint, to analysis or thumbnail
  decoding (`thumbs/thumbnail.py` also passes `-hwaccel`; it is a separate item), or to `reel.yaml`.
- No per-codec hardware decode self-test probes: the self-test keeps its single h264 decode probe. The
  reactive net covers a static-table entry that is wrong on some GPU generation.
- No new CLI flag or config key. `--device cpu` stays the manual override.
- NVIDIA and Intel gain table entries and golden tests only. Their software-decode-then-upload recipe has
  no verified `upload_device_flags`, so a clip they cannot decode fails with a typed `RenderError` that
  names `--device cpu` (see design); verifying that recipe needs their hardware.

**Impact checklist (config.yaml rules)**

- Rendered output for identical inputs: unchanged for every input that rendered before. The only inputs
  whose behaviour changes are ones that previously failed. `RENDER_GRAPH_VERSION` is **not** bumped; the
  fingerprint inputs are unchanged.
- `reel.yaml` / `config.yaml` schema: unchanged. No Alembic migration, no rescan. The accel capability
  cache file (not the database) is invalidated once via `_CACHE_SCHEMA`.
- Packages: `auto_reel_ng/accel`, `auto_reel_ng/render`. CLI and API are both touched only through the
  engine they call; no new surface (Principle V).
- No new dependencies. Complexity added: one capability field, one profile query, one retry (justified by
  the reproduced failure; Principle VII).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `acceleration-profile`: a profile states which source codecs and pixel formats its hardware decoder
  handles and emits a software decode for the rest.
- `clip-normalize`: the decode is chosen per clip; a hardware-decode initialisation failure is retried once
  in software; the fail-loud requirement is clarified to cover the retry.

## Impact

- Code: `accel/models.py`, `accel/detection.py`, `accel/profiles/{base,hardware,vaapi,nvenc,qsv}.py`,
  `render/normalize.py`, `render/orchestrator.py`.
- Tests: `tests/test_accel_profiles.py`, `tests/test_accel_detection.py`, `tests/test_accel_cache.py`,
  `tests/test_render.py` (fixtures that build hardware `AcceleratorCapabilities` gain `hw_decode`).
- Docs: `docs/high-level-design.md` §4.1 decode row and a D-n entry.
- Sequencing: lands after `render-output-name-safety`, which edits other regions of `orchestrator.py`
  (`output_filename`, `render_movie`). `render-progress-monotonic` follows in the same file; see design.
