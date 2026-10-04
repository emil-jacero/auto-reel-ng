## 1. render/ split

- [x] 1.1 In `render/card_window.py` add the pure function `split_segment(segment, fps, length) -> tuple[Segment, ...]`
  implementing the rule in design.md (N = ceil(W*fps - 1e-6), H = N/fps, no split when the tail is under 1.0 s or the
  window covers the segment, head keeps the overlay, tail has none, both `is_full_clip=False`,
  `copy_eligible=False`). Verify with tests in `tests/test_card_window.py` (the scenarios in `render-segments`): 180 s
  clip + 7 s card at 30 fps (head 0-7, tail 7-180), 7.01 s card at 30 fps (split at 211/30), a trimmed anchor 12-60 s
  (12-19 + 19-60), 7.5 s segment unsplit, 3 s segment unsplit, 23.976 fps (H is a multiple of 1001/24000),
  no-overlay, untimed, mixed and synthetic segments unchanged, a tail never `copy_eligible`.
- [x] 1.2 In `render/orchestrator.py` add `_plan_encodes`: materialize the overlays first (so the window is known,
  once), split, and return a head encode, a tail encode and a join, or the one whole encode; `_normalize_segment` runs
  them (per-piece software-decode retry, cancel polled between pieces, progress share per piece) and `_plan_only` lists
  them. Verify with tests: a fake producer is called once per card in a dry run; the dry run lists head (with the card
  input), tail (no card input, no `-filter_complex`) and join; a short segment plans one command; the progress shares
  sum to the segment's weight; a missing clip fact or an unregistered producer still raises the `RenderError` it did.

## 2. render/ command shape

- [x] 2.1 Add `audio=False` to `build_normalize_command` (video-only: no audio map or silence input, `-an`) and
  `build_join_command` in `render/card_window.py` (concat list copy for video, audio cut from the source over the whole
  span and encoded once, silence for a clip without audio). In `tests/test_card_window.py` add golden-argument tests
  for the two pieces on the AMD profile (head: `-ss 0 -t 7`, `hwdownload,format=nv12`,
  `overlay=...:enable='between(t,0,7)'`, `format=nv12,hwupload`; tail: `-ss 7 -t 173`, `-vf` with
  `scale_vaapi`/`pad_vaapi` only, no `hwdownload`, no `hwupload`, no card input), the CPU profile (head with overlay
  and no transfers, tail plain) and an NVENC-style `can_overlay_hw=True` profile (head still the CPU `overlay`), the
  pieces being video-only, and the join (a seek for a trimmed span, none for a whole clip, silence without audio).
  The existing overlay and copy-eligibility tests pass unchanged.

## 3. render/ join correctness (has_ffmpeg)

- [x] 3.1 Add `has_ffmpeg` + `has_fonts` tests that render a 20 s generated clip (a flat luma that encodes the frame
  number, continuous 440 Hz `sine` audio, 30 fps) under a 7 s `video` card on the CPU profile, split and unsplit, and
  assert: ffprobe frame counts equal (600); frame pts a constant 1/30 grid equal to the unsplit render's; the burned-in
  frame number consecutive through the join and equal to the unsplit render's; movie duration within one frame; audio
  length within 1024 samples; no sample step at the join above twice the tone's maximum step. Add the same with a clip
  that has no audio track (silence, length equal). A `gpu` test does the VAAPI frame and audio comparison and asserts
  the tail's planned command has no `hwdownload`.
- [x] 3.2 The first plan was to cut the head's audio to exactly `round(H * rate)` samples; building 3.1 showed the
  failure is the tail's AAC delay, not the head's length (design.md, "Audio continuity"), so the pieces are video-only
  and the join encodes the audio once. Verify by 3.1 passing on the CPU profile and again under the `gpu` marker.

## 4. render/ + staleness/ version bump

- [x] 4.1 In `staleness/fingerprint.py` bump `RENDER_GRAPH_VERSION` 9 -> 10 (or the next free number if another
  merged change took 9) and add the history line `9: video-card-bridge-window (...)` in the comment block. Verify
  with the existing fingerprint tests updated for the new value (engine component differs from version 8 for the
  same event) and a manifest test showing an event rendered under 8 reads stale with reason `engine`.

## 5. docs

- [x] 5.1 Update `docs/high-level-design.md`: 4.4 (replace "the anchor segment is re-encoded through the CPU
  bridge for its whole length" with the card-window split: head through the bridge, tail on the GPU path) and the
  D-24 entry (the split rule, the 1 s floor, the frame-grid rule, `RENDER_GRAPH_VERSION` 9), plus the measured
  before/after encode times from 5.2. Add the docs test (house pattern: `tests/test_docs*.py`, bounded by
  heading) asserting 4.4 no longer says "for its whole length" and D-24 names the split. No new D-number; 4.10/6
  need no edit (no user-visible surface), say so in the commit body, not a task.
- [x] 5.2 Measure and record (SCRATCH script, not committed): wall-clock encode time of the anchor segment for a
  180 s first clip (record codec/resolution/fps) under a 7 s video card, before (origin/main worktree) and after,
  VAAPI and CPU profiles, three runs each, median; write the numbers into the D-24 paragraph from 5.1. A `gpu`
  test asserts only that the VAAPI tail command has no `hwdownload`; timing is not asserted in CI.

## 6. Validation gates

- [x] 6.1 `black` and `isort` clean on `auto_reel_ng` and `tests`; `mypy auto_reel_ng` strict clean; `pylint
  auto_reel_ng` clean (cairo `no-member` noise excepted).
- [x] 6.2 Full `.venv/bin/python -m pytest` passes (`requires_db` via podman; the five title-card tests skip only
  without Cairo/Pango).
