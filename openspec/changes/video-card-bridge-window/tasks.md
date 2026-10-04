## 1. render/ split

- [ ] 1.1 In `render/segments.py` (or a sibling module `render/card_window.py` if the file grows past its limit)
  add the pure function `split_timed_overlays(segments, fps, durations) -> tuple[Segment, ...]` implementing the
  rule in design.md (N = ceil(W*fps - 1e-6), H = N/fps, no split when the tail is under 1.0 s or the window
  covers the segment, head keeps the overlay, tail has none, both `is_full_clip=False`, `copy_eligible=False`),
  where `durations` gives each full-clip segment's probed length. Verify with tests in `tests/test_render.py`
  (the scenarios in `render-segments`): 180 s clip + 7 s card at 30 fps (head 0-7, tail 7-180), 7.01 s card at 30
  fps (split at 211/30), a trimmed anchor 12-60 s (12-19 + 19-60), 7.5 s segment unsplit, 3 s segment unsplit,
  23.976 fps (H is a multiple of 1001/24000), no-overlay and untimed-overlay segments unchanged, a tail never
  `copy_eligible`.
- [ ] 1.2 In `render/orchestrator.py` materialize the overlay before the split (so the window is known), then
  call the function once at the top of both `_execute` and `_plan_only`, before `_plan_progress`; materialize
  once only (the head carries the already-materialized overlay, so `_build_segment_command` does not render the
  card twice and the PNG name stays `card_<index>_<n>.png` for the expanded index). Verify with tests: a fake
  producer is called once per card in run and in `_plan_only`; `_plan_only` lists head command (with the card
  input) and tail command (no card input, no `-filter_complex`); progress weights sum to the unsplit total;
  `aggregate_chapter_durations` and `chapter_times` give the same chapter times for the split and unsplit
  plans within one frame; a missing clip fact or an unregistered producer still raises the `RenderError` it did.

## 2. render/ command shape

- [ ] 2.1 In `tests/test_render.py` add golden-argument tests for the two commands on the AMD profile (head:
  `-ss 0 -t 7`, `hwdownload,format=nv12`, `overlay=...:enable='between(t,0,7)'`, `format=nv12,hwupload`; tail:
  `-ss 7 -t 173`, `-vf` with `scale_vaapi`/`pad_vaapi` only, no `hwdownload`, no `hwupload`, no card input),
  the CPU profile (head with overlay and no transfers, tail plain) and an NVENC-style `can_overlay_hw=True`
  profile (head still uses the CPU `overlay`); the existing `test_overlay_uses_cpu_bridge_filter_complex`,
  timed-overlay and copy-eligibility tests pass unchanged. Fix whatever in `render/normalize.py` the tail needs
  (it should need nothing: it is an ordinary trimmed segment).

## 3. render/ join correctness (has_ffmpeg)

- [ ] 3.1 Add a `has_ffmpeg` test that renders a 20 s generated clip (`testsrc2` with `drawtext` frame counter,
  continuous 440 Hz `sine` audio, 30 fps) under a 7 s `video` card on the CPU profile, split and unsplit, and
  asserts: ffprobe `nb_read_frames` equal; frame pts a constant 1/30 grid; the burned-in counter (read by
  sampling frames at the join, 209-212) consecutive; movie and chapter durations within one frame; audio length
  within 1024 samples; no sample step at the join above twice the tone's maximum step. Add the same with a clip
  that has no audio track (silence on both pieces, length equal). Needs `has_fonts` for the card text.
- [ ] 3.2 Make the audio cut exact in the normalize audio chain if 3.1 shows more than one AAC frame of error:
  limit the head's audio to `round(H * rate)` samples and start the tail's audio at the same sample. Verify by
  3.1 passing on the CPU profile and again under the `gpu` marker on VAAPI.

## 4. render/ + staleness/ version bump

- [ ] 4.1 In `staleness/fingerprint.py` bump `RENDER_GRAPH_VERSION` 8 -> 9 (or the next free number if another
  merged change took 9) and add the history line `9: video-card-bridge-window (...)` in the comment block. Verify
  with the existing fingerprint tests updated for the new value (engine component differs from version 8 for the
  same event) and a manifest test showing an event rendered under 8 reads stale with reason `engine`.

## 5. docs

- [ ] 5.1 Update `docs/high-level-design.md`: 4.4 (replace "the anchor segment is re-encoded through the CPU
  bridge for its whole length" with the card-window split: head through the bridge, tail on the GPU path) and the
  D-24 entry (the split rule, the 1 s floor, the frame-grid rule, `RENDER_GRAPH_VERSION` 9), plus the measured
  before/after encode times from 5.2. Add the docs test (house pattern: `tests/test_docs*.py`, bounded by
  heading) asserting 4.4 no longer says "for its whole length" and D-24 names the split. No new D-number; 4.10/6
  need no edit (no user-visible surface), say so in the commit body, not a task.
- [ ] 5.2 Measure and record (SCRATCH script, not committed): wall-clock encode time of the anchor segment for a
  180 s first clip (record codec/resolution/fps) under a 7 s video card, before (origin/main worktree) and after,
  VAAPI and CPU profiles, three runs each, median; write the numbers into the D-24 paragraph from 5.1. A `gpu`
  test asserts only that the VAAPI tail command has no `hwdownload`; timing is not asserted in CI.

## 6. Validation gates

- [ ] 6.1 `black` and `isort` clean on `auto_reel_ng` and `tests`; `mypy auto_reel_ng` strict clean; `pylint
  auto_reel_ng` clean (cairo `no-member` noise excepted).
- [ ] 6.2 Full `.venv/bin/python -m pytest` passes (`requires_db` via podman; the five title-card tests skip only
  without Cairo/Pango).
