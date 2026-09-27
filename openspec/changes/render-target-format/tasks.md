## 1. render/ — the target canvas

- [x] 1.1 In `render/target.py`, change `derive_target` to take `clips: Sequence[ClipMetadata]`, and add `DEFAULT_TARGET_RESOLUTION`, `_resolution(look)` and `_fps(look, clips)` with the validation in design "Validation". In `render/orchestrator.py`, make `resolve_target` pass every plan clip's facts, failing loud on a missing one, and remove `_first_clip_facts`. Update the existing `derive_target`/`resolve_target` call sites in `tests/test_render.py`. Verify with new cases there:
  - no look keys with a 720×1280 first clip → 1920×1080
  - mixed 3840×2160 and 1920×1080 → 1920×1080
  - clips at 25, 50 and 30 fps with the 25 first → 50 fps
  - `fps: 30` over clips at 25 → 30
  - `target_resolution: [3840, 2160]` → 3840×2160
  - `fps: "fifty"`, `fps: 0`, `fps: true` and `target_resolution: [1920, 0]` each raise a `RenderError` naming the key
  - an all-1920×1080-at-50 plan leaves every source segment copy-eligible (`decide_copy_eligibility`)
- [x] 1.2 Add a `has_ffmpeg` end-to-end test in `tests/test_render.py`: a CPU render of a plan whose first clip is lavfi 360×640 at 25 fps, followed by 640×360 at 50 fps, with `look.target_resolution: [640, 360]` to keep it fast. Verify the output re-probes at 640×360 and 50 fps.

## 2. staleness/ — the version

- [x] 2.1 Set `RENDER_GRAPH_VERSION = 2` in `staleness/fingerprint.py`, with a comment line naming `render-target-format`. Verify with a test in `tests/test_staleness_fingerprint.py` that a manifest written under version 1 (`engine_identity` with `render_graph_version=1`) evaluates stale with reason `engine`.

## 3. Docs

- [x] 3.1 Correct `README.md`'s `config.yaml` example: `look.resolution: 1080p` becomes `target_resolution: [1920, 1080]`, with a commented `fps: 25` override. Add one sentence each on the defaults (1920×1080, the highest clip fps) and the per-event override in `reel.yaml`. In `docs/high-level-design.md` §4.3, add one line recording the canvas defaults and that clip order never decides them. Verify by rereading both against the spec.

## 4. Validation

- [x] 4.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`, including the `gpu`-marked test. Verify all are clean or green, apart from the known cairo `no-member` noise.
- [x] 4.2 Rebuild the dev library (`scripts/make_dev_library.py ../auto-reel-dev`) and run `auto-reel render ../auto-reel-dev/library --dry-run`. The dev library's clips are all 1920×1080 at 50 fps, so the defaults equal their format. Verify:
  - every renderable event plans exactly one command, the concat, with no normalize or `-r` (the stream-copy fast path is preserved)
  - the dev library's intended `ERROR`s are unchanged: the empty Trasig clip and the Kalas same-date collision
