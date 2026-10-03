## 1. render/

- [x] 1.1 In `render/normalize.py` add the pure `display_turn(clip)` (`(360 - (clip.rotation or 0)) % 360`,
  clockwise) and `total_turn(clip, rotate)` (`(display_turn + (rotate or 0)) % 360`), make `_needs_pad` take
  the total turn instead of `rotate`, and update the module and `_needs_pad` docstrings and `Segment.rotate`'s
  ("an extra clockwise turn on top of the display rotation") in `render/segments.py`. Verify in
  `tests/test_render.py`: `display_turn` for probed `None`/90/270 gives 0/270/90, `total_turn` composes and wraps
  (90+270 = 0, 270+180 = 90), and `test_needs_pad` is re-parametrized for the composed rule (the old "segment
  rotate wins" case becomes display 90 + `rotate: 90` = 180 = no swap; display 90 + `rotate: 270` = 0 = stored
  shape, no pad for a 16:9 clip).
- [x] 1.2 In `build_normalize_command` feed `_canvas_stages` the total turn (a total of 0 emits no stage), emit
  `-noautorotate` as an input option before `-ss`/`-i` of the source only when `display_turn(clip) != 0`, and log
  the clip, both values and the total at info level when both are non-zero. Verify with golden-argument tests in
  `tests/test_render.py` for the CPU profile and the AMD VAAPI profile (hardware decode: `hwdownload,format=nv12,
  transpose=1,...,hwupload`; software-decode MPEG-4: transpose then `format=nv12,hwupload`): probed 270 with
  no `rotate` (one `transpose=1`), with `rotate: 90` (two), with `rotate: 270` (none, and `scale_vaapi` with no
  download), no display rotation with `rotate` 90/180/270 (arguments identical to today, no
  `-noautorotate`), an overlaid trimmed segment (the flag precedes only the clip's input, overlay inputs
  unchanged), and a `caplog` check of the info line. The existing rotation tests stay green.
- [x] 1.3 Make `copy_eligible` return `False` when `display_turn(clip) != 0` or `(segment.rotate or 0) % 360 != 0`.
  Verify with unit tests: an otherwise conforming clip with probed rotation 270 is ineligible; the same with
  `rotate: 180` is ineligible; with `rotate: 0` or `360` and no display rotation it is eligible; display 90 with
  `rotate: 270` (total 0) is ineligible.
- [x] 1.4 Real-render orientation tests in a new `tests/test_render_rotate.py` (`has_ffmpeg`): a synthetic 1280x720
  30 fps AAC 48 kHz stereo clip with a white left half and a black right half and a display rotation of 90 via
  `make_clip(rotate=...)`, rendered through `render_movie` as a one-clip event whose target is 1280x720 on the CPU
  profile, for `rotate` unset, 90, 180, 270: assert with `signalstats` crops that the half-turns land where the
  total turn puts them, and that the output has no display matrix and is not the stream-copy path (this is the
  case `exp3.py` showed carrying `rotation=90`). Repeat the four turns on the samples `h264-720p-rotate90-aac.mp4`,
  `hevc-mov-rotate90-aac.mov` and `h264-portrait-1080x1920-aac.mp4` from `auto-reel-media/samples/` (skip when the
  sample is absent, as `tests/test_proxies_ffmpeg.py` does), comparing the first frame by SSIM with the source's
  autorotated frame turned by `rotate` (best reference wins, as `exp.py`). Mark the VAAPI run `gpu` (it uses
  `_hardware_profile`); the CPU run needs no marker.

## 2. reel/

- [x] 2.1 In `reel/schema.py` check `rotate` when a clip's properties are parsed: after `_opt_int`, an integer that
  is not a multiple of 90 raises `ReelParseError` naming the clip and `rotate` (`-90`, `0` and `360` still load,
  and the value is kept as written). Verify in `tests/test_reel_parser.py` (45 and 100 refused with the
  identity in the message; 0, 90, 180, 270, -90, 360 accepted; `90.0`, `"90"`, `true` refused as today),
  `tests/test_event_editorial.py` (an editorial write of `rotate: 100` raises and leaves `reel.yaml` byte-identical;
  a write of `rotate: 90` lands in `clips.<identity>.rotate`) and `tests/test_reel_writer.py` (a document with
  `rotate: 270` and a trailing comment round-trips byte-for-byte).

## 3. staleness/

- [x] 3.1 Bump `RENDER_GRAPH_VERSION` from 5 to 6 in `staleness/fingerprint.py` with the history line
  `6: clip-rotate-engine (a display rotation is applied by the engine on every profile and adds to rotate; a
  display-rotated clip is never stream-copied)`. In `tests/test_staleness_fingerprint.py` re-pin `PINNED_ENGINE`
  and `PINNED_COMBINED` (the editorial, defaults, clip-set and fallback hashes must not move) and add a
  version-4 manifest test beside the existing older-version one asserting an output recorded under version 4 is
  stale for the engine reason alone. Verify with `tests/test_staleness_fingerprint.py` and
  `tests/test_staleness_gate.py`.

## 4. Docs

- [x] 4.1 Update `docs/high-level-design.md`: §4.3 step 2 (the display rotation and `rotate` compose, applied by
  the engine on every profile, rotated clips never stream-copied); §4.6's example line `rotate: auto  # or
  0/90/180/270 override` becomes `rotate: 90  # an extra clockwise turn on top of the display rotation`; a new
  decision entry in §7 (the next free D number on `main` when this is applied, D-23 today; say that D-20 and D-21
  keep the timeline and the proxy contract) recording the meaning, the clockwise/counter-clockwise rule, the
  `-noautorotate` choice, the version bump and the migration statement from design.md "Fingerprint and
  migration"; a §4.10 note that the proxies and thumbnails stay the file's and the GUI turns what it shows
  (D-20, D-21), and a §6 phase 9 note that `clip-rotate-engine` has landed and `clip-rotate-gui` follows.
  Verify with a read-through that no other HLD line still calls `rotate` an override
  (`grep -n "rotate" docs/high-level-design.md`) and that the D number used is unused.

## 5. Validation gates

- [x] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` (only the known
  cairo `no-member` noise remains), and verify all are clean.
- [x] 5.2 Run `.venv/bin/python -m pytest` (podman for the DB tests; the `gpu` tests run on this AMD host) and
  verify it passes; `openspec validate clip-rotate-engine --strict` passes.
