## Context

See proposal.md for the failure and its evidence. Facts about the code on `origin/main` that shape the fix:

- `HardwareProfile.fragment(OpClass.DECODE, params)` returns the vendor builder's fragment when
  `capabilities.decode_method` is set, else the CPU profile's `OpFragment(op=DECODE)` (no flags,
  `frames_out=SYSTEM`).
- `build_normalize_command` (`render/normalize.py`) already handles a system-memory decode feeding a
  hardware encoder: `_compose_linear(stages, decode.frames_out, encode.frames_in)` inserts
  `format=nv12,hwupload` where the frame locations disagree, and when `decode.frames_out is SYSTEM` and the
  chain contains `hwupload` it prepends `profile.upload_device_flags(params)` (`-init_hw_device
  vaapi=va:<node> -filter_hw_device va` on VAAPI; `()` on NVENC/QSV, which makes `_upload_device_flags`
  raise `RenderError`). `test_software_decode_names_the_device_hwupload_needs` pins the VAAPI string. So
  forcing the CPU DECODE fragment for a clip is enough; no new graph shape is needed.
- `OpParams` carries no source facts; `ClipMetadata` has `video_codec`, `pix_fmt`, `profile`.
- The decode self-test (`accel/selftest.py`) runs one h264 clip. `AcceleratorCapabilities.decode_method` is
  therefore "h264 hardware decode works", not "all codecs decode".
- `FfmpegError` for a failed command carries `Command exited <rc>: <cmd>\nstderr:\n<stderr>`.
  `_normalize_segment` wraps any `EngineError` in a `RenderError` naming the segment.
- Capabilities are cached on disk (`accel/detection.py`, `_CACHE_SCHEMA = 2`); `_accelerator_from_dict`
  indexes every key, so a cache written before a new field exists fails with `KeyError` and is
  re-detected; the schema number is bumped as well so the intent is explicit.

## Goals / Non-Goals

**Goals:**

- A clip whose codec or pixel format the hardware decoder lacks renders on a GPU host, decoded in
  software, encoded on the GPU (the proven command), with no manual flag.
- A static-table mistake (a GPU generation that lacks a codec the table lists) costs one logged retry, not a
  failed event.
- Hardware-decodable clips emit byte-identical commands to today.

**Non-Goals:** see proposal.md. In addition: the table is not a performance heuristic. A clip that decodes
in hardware but slowly stays on hardware.

## Decisions

### Research & Decisions

#### Decide per clip, in the profile, from a capability field

**Context**: `render/` must not name vendors (Principle III), yet only the vendor knows which codecs its
decoder handles.
**Explored**: (a) a codec set in `render/`; (b) measured per-codec self-test probes; (c) a static
per-vendor table on `AcceleratorCapabilities`, queried through the profile.
**Decision**: (c). New field `hw_decode: Mapping[str, int]` (codec name -> highest bit depth the hardware
decodes), default empty. `compute_accelerator` fills it from a module table `_HW_DECODE[vendor]` only when
`works(f"{prefix}.decode")`; so `decode_method is None` implies an empty mapping. New query on `AccelProfile`:

```python
def can_hw_decode(self, codec: str, pix_fmt: Optional[str]) -> bool: ...
```

`CPUProfile` returns `False` (it has no hardware decode; its DECODE fragment is already software).
`HardwareProfile` returns true iff `decode_method` is set, `codec in hw_decode`, and, when `pix_fmt` is
known, the pixel format is 4:2:0 and its bit depth is `<= hw_decode[codec]`. An unknown `pix_fmt` (`None`)
is decided by the codec alone: the engine does not guess a format the probe did not report (Principle I),
and the reactive net below covers the difference. `OpParams` gains `software_decode: bool = False`;
`HardwareProfile.fragment(OpClass.DECODE, params)` returns the CPU profile's DECODE fragment when it is
set, before consulting the vendor builder.
**Rationale**: (a) leaks vendor knowledge into `render/`. (b) is the more truthful design but multiplies
startup self-test cost per vendor and needs a sample clip per codec; the reactive net gives most of its
safety for none of its cost. (c) keeps the self-test unchanged and the decision pure and golden-testable.

The AMD table is limited to what the Mesa VAAPI stack on the dev GPU is known to decode; an entry that is
missing costs speed (software decode), an entry that is wrong costs one retry. Initial tables, all
unverified except the AMD h264/mpeg4 facts from the reproduction:

| Vendor | `hw_decode` (codec: max bit depth) |
|---|---|
| AMD (VAAPI) | h264: 8, hevc: 10, vp9: 10, av1: 10 |
| NVIDIA (NVDEC) | h264: 8, hevc: 10, vp9: 10, av1: 10, mpeg2video: 8, vc1: 8, mpeg4: 8, mjpeg: 8 |
| Intel (QSV) | h264: 8, hevc: 10, vp9: 10, av1: 10, mpeg2video: 8, vc1: 8, mjpeg: 8 |

`mpeg4`, `mjpeg`, `mpeg2video` and `vc1` are deliberately absent for AMD: VCN generations differ and only
`mpeg4` was reproduced as failing. Chroma and depth come from a small pure function
`pix_fmt_traits(pix_fmt) -> (bit_depth, is_420)` in `accel/` (`yuv420p`, `yuvj420p`, `nv12` -> 8-bit 4:2:0;
`yuv420p10le`, `p010le` -> 10-bit 4:2:0; `yuv422p`, `yuv444p10le` -> not 4:2:0).

#### Software decode on a hardware encode uses the existing composition

**Context**: the question is whether to add a new graph path.
**Decision**: no. `build_normalize_command(..., force_software_decode=False)` builds
`OpParams(..., software_decode=force_software_decode or not profile.can_hw_decode(clip.video_codec,
clip.pix_fmt))` and requests DECODE once. Everything after that is today's code. Emitted VAAPI command for
an `mpeg4` 1280x720 `.avi` clip (16:9, so no pad is needed):

```
-y -init_hw_device vaapi=va:/dev/dri/renderD128 -filter_hw_device va -i clip.avi
-vf format=nv12,hwupload,scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease
-map 0:v:0 -map 0:a:0 -r 30 -c:v h264_vaapi -c:a aac …
```

A clip that needs bars on a host with `pad_fill_ok` true appends `,pad_vaapi=…` after the scale; with `pad_fill_ok` false the chain is `scale=…,pad=…,setsar=1,format=nv12,hwupload`. A hardware-decodable h264
clip still gets `-hwaccel vaapi -hwaccel_device va -hwaccel_output_format vaapi` and no `format=nv12,hwupload`.
**CPU fallback path (Principle III)**: unchanged and complete; on a CPU profile `can_hw_decode` is false and
the CPU fragment is what was already emitted.
**10-bit and 4:2:2 sources**: `format=nv12` in the upload bridge converts to 8-bit 4:2:0, which is what the
target pixel format (`yuv420p`) is anyway. HDR sources still tonemap on the CPU as today.

#### Reactive retry in `_normalize_segment`

**Context**: the table can be wrong, and a driver can reject a stream the table accepts (a profile or level
the decoder lacks).
**Decision**: in `_normalize_segment`, catch `FfmpegError` around `run_with_progress`. If the segment is a
source segment, the failed command was a hardware decode (`NormalizeCommand.hardware_decode`, true when
the DECODE fragment's `frames_out` is not `SYSTEM`) and `str(exc)` contains `hwaccel initialisation
returned error` or `Failed setup for format`, then log a warning
(`segment <label>: hardware decode failed, retrying with software decode: <first stderr line that matches>`),
rebuild the command with `force_software_decode=True` and run it once. The retry's warning is also appended
to the returned warnings so it reaches `RenderResult.warnings`. The match is on those two phrases only: the
`-38` code appears in the same message but is not matched on its own, since `-38` is a generic errno.

`NormalizeCommand` gains `hardware_decode: bool = False`. `_build_segment_command` gains
`force_software_decode: bool = False` and passes it for source segments only; synthetic segments have no
decode and are never retried.

**Failure behaviour (Principle I)**: any other `EngineError` raises `RenderError` exactly as today. If the
retry itself fails, the raised `RenderError` names the segment and carries the retry's ffmpeg failure, and
says that the hardware-decode attempt failed first. If rebuilding the command raises a `RenderError`
(NVENC/QSV: no verified upload device), that error propagates chained from the original failure; the
original failure is never swallowed. A segment is never dropped or replaced.
**Idempotency**: the retry writes the same `seg_NNN.mp4` in the scratch directory with `-y`, overwriting any
partial file from the failed attempt; the final `.part` -> verify -> rename is untouched, so a killed process
at any point leaves no file that looks rendered. A re-run or `--force` run repeats the decision (and, if
the table is wrong, the one retry); a worker restart mid-render re-renders from the start. Nothing is
persisted about the retry.
**Progress**: the retry restarts the segment's local fraction at 0, so `on_progress` can step backwards
within that segment. This is not fixed here; `render-progress-monotonic`, which follows in `orchestrator.py`,
owns monotonic progress and its test should cover a retried segment.
**Cancel**: cancel is polled between segments, not between attempts; a retry adds no new cancel point.
(`render-stall-watchdog` will add mid-segment polling.)

#### Where this meets the NVENC/QSV profiles

`NvencProfile` and `QsvProfile` need no code beyond inheriting the `HardwareProfile` behaviour, because the
routing sits in the base class. Their NORMALIZE fragments take `CUDA`/`QSV` frames, so a software-decoded
clip is composed as `format=nv12,hwupload,scale_cuda…`, which requires an upload device they cannot name
(`upload_device_flags` returns `()`). `_upload_device_flags` then raises its existing loud `RenderError`
("…render with --device cpu"). That is no worse than today's opaque ffmpeg failure and is honest about the
gap; a verified recipe is future work on that hardware.

### Fold-back

The decision outlives the change (accelerator capability field, per-clip decode choice, retry rule), so the
change folds it into `docs/high-level-design.md`: the AMD decode cell of the §4.1 matrix notes "for codecs
the hardware decodes, else software + `hwupload`", and a new D-n (next free number at apply time) records
"decode is chosen per clip from `hw_decode`; a hardware-decode init failure retries once in software".

## Risks / Trade-offs

- **Static table wrong for a GPU generation** -> too small: some clips decode in software when hardware
  could (slower, correct). Too large: one logged retry per such segment, then correct. Neither fails an
  event. Entries are only added for codecs observed to work.
- **Retry hides a real hardware fault** -> the match is limited to the two initialisation phrases; every
  other failure, including a failed retry, raises with full ffmpeg detail and the warning is logged and
  returned in the result.
- **Doubled time on a wrong-table segment** -> a failed hardware init exits within the first second, so the
  cost is the software decode itself.
- **10-bit -> 8-bit via `format=nv12`** -> same bit depth the target already requires; HDR still tonemaps
  on the CPU first.
- **Capability cache invalidated once** -> `_CACHE_SCHEMA` 2 -> 3 re-runs the startup self-test on first
  start after upgrade; the cost is the normal first-run detection.
- **Progress can step backwards on a retried segment** -> deferred to `render-progress-monotonic` as above.
- **Existing fixtures** that build hardware `AcceleratorCapabilities` by hand will treat every clip as
  software-decoded until they set `hw_decode`; the golden strings in `test_render.py` and
  `test_accel_profiles.py` pin that the AMD fixture lists h264.

## Migration Plan

None. Rollback is reverting the change; the cache file with schema 3 is ignored by older code (it keys on
`_CACHE_SCHEMA`) and regenerated.
