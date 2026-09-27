## 1. accel/ — detect the faulty fill

- [x] 1.1 Add `expect` to `Probe` and apply it after a zero exit in `accel/selftest.py`. Add the `amd.pad_fill` probe (design "Detecting a faulty fill"). Verify with unit tests on mocked `run` output in `tests/test_accel_selftest.py`:
  - `UAVG=128`/`VAVG=128` → working
  - `UAVG=0` → unsupported, with a reason
  - a non-zero exit → unsupported, as before
- [x] 1.2 Add `pad_fill_ok: bool` to `AcceleratorCapabilities` (`to_dict` and cache load included), set it in `accel/detection.py`, and add `_CACHE_SCHEMA` to the fingerprint. Verify:
  - `tests/test_accel_detection.py`: `pad_fill_ok` follows the probe for AMD and is `True` for NVIDIA/Intel
  - `tests/test_accel_cache.py`: a cache file without `pad_fill_ok`, or with an old schema, triggers re-detection

## 2. accel/ + render/ — pad where correct, share the device

- [x] 2.1 Add `needs_pad` to `OpParams`, and compute it in `render/normalize.py` with `_needs_pad` (design "Deciding per clip…"). Make `VaapiProfile._normalize` choose between `scale_vaapi` only, `scale_vaapi,pad_vaapi` and the CPU fallback. Verify with golden tests in `tests/test_render.py` and `tests/test_accel_profiles.py`:
  - `pad_fill_ok=False` with a 1440×1920 clip gives a CPU `scale,pad` with `hwdownload…hwupload` around it
  - a 3840×2160 clip gives `scale_vaapi` alone, with no transfer
  - a 1920×1088 clip counts as `needs_pad`
  - `pad_fill_ok=True` with a 1440×1920 clip gives `scale_vaapi,pad_vaapi`
- [x] 2.2 Change `VaapiProfile._decode` to the shared named device (design "Sharing the device…"), and update every VAAPI golden command string. Verify that exactly one `-init_hw_device` appears in both the hardware-decode and the software-decode (`upload_device_flags`) command builds.

## 3. staleness/ — version

- [x] 3.1 Set `RENDER_GRAPH_VERSION = 3`, with a comment naming `vaapi-pad-fill`. Verify that a version-2 manifest evaluates stale with reason `engine`.

## 4. GPU verification (on this host)

- [x] 4.1 Add `gpu`-marked tests in `tests/test_render.py`. Verify all pass here:
  - detection on this host reports `pad_fill_ok is False` (the known Mesa behavior; skip with a message if another GPU is present)
  - a lavfi 360×640 portrait clip rendered via the detected profile into 640×360 has a black padded corner (`crop` plus `signalstats` `UAVG` within 128 ± 8)
  - a lavfi clip with `rotate=90` renders through the VAAPI profile without the "hardware device reference" error, and comes out upright at the target size
- [x] 4.2 **Only if** the MOL drive is mounted (the test library's clips are symlinks to it; nothing is written to the drive, and `ro` is fine), re-render the real-footage test library (`../auto-reel-real-test`) with `--force`. If it is not mounted, record the task as deferred. Verify:
  - "Olika Djur" at about 156.7 s shows black side bars (grab a frame and check the corner pixel)
  - the other four movies still match the checks in `../auto-reel-real-test/verify.py`

## 5. Docs and experiment record

- [x] 5.1 Write `experiments/006-vaapi-pad-fill/report.md` in the running-experiments format (hypothesis, the four `color=` readings, the device-sharing result, the conclusion). Correct HLD §8.2 and the §4.1 AMD cell to point at it. Verify by rereading both against the design.

## 6. Validation

- [x] 6.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`, including the `gpu` marker. Verify all are clean or green, apart from the known cairo `no-member` noise.
