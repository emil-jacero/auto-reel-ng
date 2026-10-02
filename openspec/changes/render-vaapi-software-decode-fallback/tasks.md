## 1. accel/ capability data

- [x] 1.1 Add `hw_decode: Mapping[str, int]` (default empty) to `AcceleratorCapabilities` with `to_dict`, add the per-vendor `_HW_DECODE` tables in `accel/detection.py` filled by `compute_accelerator` only when `<vendor>.decode` is `WORKING`, round-trip it in `_accelerator_from_dict`, and bump `_CACHE_SCHEMA` to 3; verify with tests in `tests/test_accel_detection.py` (table filled on a working decode, empty when decode is unsupported or faulting) and `tests/test_accel_cache.py` (a schema-2 cache is not reused; a schema-3 cache round-trips `hw_decode`)

## 2. accel/ profile query

- [x] 2.1 Add `pix_fmt_traits(pix_fmt) -> (bit_depth, is_420)` (`None` for a format it does not recognise, which is decoded in software) in `accel/pixfmt.py`, `OpParams.software_decode`, `AccelProfile.can_hw_decode(codec, pix_fmt)` (CPU: `False`; `HardwareProfile`: decode_method set, codec in `hw_decode`, 4:2:0 and depth within limit when `pix_fmt` is known, codec alone when it is `None`), and make `HardwareProfile.fragment(OpClass.DECODE, ...)` return the CPU decode fragment when `params.software_decode` is set; verify with `tests/test_accel_profiles.py` tests for the pix_fmt table (`yuv420p`, `yuvj420p`, `nv12`, `yuv420p10le`, `p010le`, `yuv422p`, `yuv444p10le`, and unrecognised `gray`, `rgb24`), the can_hw_decode scenarios (mpeg4, h264 8-bit, h264 10-bit, hevc 10-bit, 4:2:2, `None` pix_fmt, decode self-test failed) on the VAAPI, NVENC and QSV profiles, and the CPU profile
- [x] 2.2 Give the hand-built hardware `AcceleratorCapabilities` fixtures (`tests/test_render.py` `_amd_caps`, `tests/test_accel_profiles.py` fixtures) an `hw_decode` table listing `h264: 8, hevc: 10`, and verify every existing golden string in both files still passes unchanged

## 3. render/ proactive choice

- [x] 3.1 In `build_normalize_command` add `force_software_decode: bool = False`, set `OpParams.software_decode = force or not profile.can_hw_decode(clip.video_codec, clip.pix_fmt)`, add `NormalizeCommand.hardware_decode` (true when the DECODE fragment's `frames_out` is not `SYSTEM`), and log an info line for a profile-reported software decode; verify with golden-string tests in `tests/test_render.py` for an `mpeg4` 16:9 clip on VAAPI (no `-hwaccel`, one `-init_hw_device`, `format=nv12,hwupload,scale_vaapi`), a rotated `mpeg4` clip, a 4:3 `mpeg4` clip with `pad_fill_ok` false, a 10-bit `h264` clip, an unchanged 8-bit `h264` clip, an `mpeg4` clip on the CPU profile, and an `mpeg4` clip on NVENC and QSV profiles raising the `RenderError` that names `--device cpu`

## 4. render/ reactive retry

- [x] 4.1 In `render/orchestrator.py` thread `force_software_decode` through `_build_segment_command`, and in `_normalize_segment` retry once with software decode when a source segment's hardware-decode command raises an `FfmpegError` whose message contains `hwaccel initialisation returned error` or `Failed setup for format`, logging a warning and appending it to the returned warnings; a failed retry raises a `RenderError` naming the segment, carrying the retry's detail and the first attempt's failure; a command-rebuild `RenderError` propagates chained from the original; verify with fake-runtime tests in `tests/test_render.py` for retry-success (second command has no `-hwaccel`, warning returned in `RenderResult.warnings`, other segments run once), unrelated failure not retried, already-software failure not retried, synthetic segment not retried, failed retry message, and at most two `run_with_progress` calls for the segment
- [x] 4.2 Add a `has_ffmpeg` + `gpu` test in `tests/test_render.py` that generates a short `mpeg4` `.avi` with the host ffmpeg and renders it through the auto-selected VAAPI profile to a verified movie, skipping without a usable VAAPI accelerator; verify it passes on the dev host and is deselected by `-m "not gpu"`

## 5. Docs

- [x] 5.1 In `docs/high-level-design.md` update the AMD decode cell of the §4.1 matrix to say hardware decode applies to the codecs in `hw_decode` and software decode plus `hwupload` otherwise, and add the next free D-n entry (per-clip decode choice from `hw_decode`, one software retry on a hardware-decode initialisation failure, `RENDER_GRAPH_VERSION` not bumped because only previously failing inputs change); verify the new D-n number does not collide with one already in the file

## 6. Validation gates

- [x] 6.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests` and verify no diff remains
- [x] 6.2 Run `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` and verify only the known cairo `no-member` noise remains
- [x] 6.3 Run `.venv/bin/python -m pytest` (podman for `requires_db`) and verify the suite passes, including the new `gpu` test on the dev host
