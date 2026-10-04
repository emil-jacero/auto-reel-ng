## 1. Pre-flight compares SAR normalized

- [x] 1.1 Move the unset-SAR rule (`None`/`""`/`N/A`/`0:1` → `1:1`) out of `render/normalize.py` `_normalize_sar` into one shared helper used by both `copy_eligible`/`_needs_pad` and `render/concat.py` `probe_copy_fields`, so `CopyFields.sample_aspect_ratio` holds the normalized value; verify with unit tests in `tests/test_render.py` (or the existing concat tests) that `is_copy_uniform` is True for fields differing only by `N/A`/`0:1`/missing vs `1:1`, False for `4:3` vs `1:1`, and the existing copy-eligibility tests still pass.
- [x] 1.2 Add a `has_ffmpeg` test that encodes two tiny mp4s with the CPU encoder (one with SAR left unset, one with `setsar=1`; assert the first really probes `N/A`/`0:1` so the test is not vacuous) and asserts `is_copy_uniform` over them is True.

## 2. Every normalize path sets SAR 1:1

- [x] 2.1 In `accel/profiles/vaapi.py` make the VAAPI normalize fragment end in `,setsar=1` for both the scale-only and the scale+pad filter (no transfer added; the self-test strings unchanged); update the VAAPI goldens in `tests/test_accel_profiles.py` / `tests/test_render.py` and verify they pass.
- [x] 2.2 Golden-graph tests: every VAAPI normalize command contains `setsar=1` — overlay-free (total turn 0 with an `N/A`-SAR clip, a turned clip, a padded clip with and without `pad_fill_ok`, a lead-in segment) and both video-card bridge commands (head with the CPU overlay, tail on the GPU; extend `tests/test_card_window.py`), and the head's `setsar` sits before its `hwdownload`/overlay with no extra transfer; plus a parametrized test that the CPU, QSV and NVENC normalize fragments (pad and no pad) end in `setsar=1`.

## 3. Real renders

- [x] 3.1 In `tests/test_render_rotate.py` style add the minimal repro (`chapters: [{name: '', clips: [h264-1080p25-aac.mp4, hevc-mov-rotate90-aac.mov]}]`, `clips: {hevc-mov-rotate90-aac.mov: {rotate: 270}}`, samples symlinked into a tmp library, never written) rendered on the CPU profile (`has_ffmpeg`) and on VAAPI (`gpu`, skipped when absent), each with `--force` semantics: assert the render succeeds and every intermediate segment and the final movie probe `sample_aspect_ratio` `1:1`; confirm the VAAPI variant fails on `origin/main` before the fix (red → green), with `TMPDIR` set to a path that does not contain the word "rotate".
- [x] 3.2 Re-render the full Provklipp `reel.yaml` from the debug report against a scratch copy of its clips (symlinks; never the user's library or `auto-reel-media`) on VAAPI and on CPU; record both results (success, final movie SAR, any warnings) for the PR body.

## 4. Version, docs, gates

- [x] 4.1 Bump `RENDER_GRAPH_VERSION` to 12 in `staleness/fingerprint.py` with the history line `12: vaapi-sar-uniform (every VAAPI normalize sets SAR 1:1; the concat pre-flight treats an unset SAR as 1:1).`; re-pin the ENGINE/COMBINED goldens in `tests/test_staleness_fingerprint.py` (comment updated) and add a test that an output fingerprinted under 11 reports stale; verify the fingerprint tests pass.
- [x] 4.2 HLD (`docs/high-level-design.md`): §4 normalize/concat pipeline (the "fix rotation/SAR" and "Concat" steps) states every normalize path sets SAR 1:1 and the pre-flight compares SAR normalized; the AMD column of the profile table shows `…,setsar=1`; add a dated addendum under D-23 (a net-zero turn leaves a pure `scale_vaapi` chain, hence the explicit SAR); §6 roadmap note "`vaapi-sar-uniform` (bug fix, `RENDER_GRAPH_VERSION` 12)". Verify by reading the diff.
- [ ] 4.3 Gates: `.venv/bin/python -m pytest` (full, background), black/isort, strict mypy, pylint clean on the touched modules; `openspec validate vaapi-sar-uniform --strict` passes.
