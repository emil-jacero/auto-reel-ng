## 1. render/

- [x] 1.1 In `render/title/decorator.py`, make `title_decorator` anchor a chapter's card at its title clip's
  first segment when that clip has any segment, otherwise at the chapter's first non-synthetic segment, and
  insert nothing when the chapter has no non-synthetic segment; update the function and module docstrings.
  Verify with the existing `tests/test_title_card.py` decorator tests (unchanged results) still passing.
- [x] 1.2 Test, title clip fully cut: plan `Ch1 = [a.mp4 (title, 10 s), b.mp4]` with `Trim(0, 10.0)` on
  `a.mp4`, built via `build_segments` with clip facts; assert the segment order is `title, b.mp4`, the card's
  chapter is `Ch1`, and its content heading is the chapter name.
- [x] 1.3 Test, chapter fully cut: two chapters, the first with every clip wholly cut; assert no synthetic
  segment and no segment for the first chapter, and that the second chapter's card stays before its title
  clip.
- [x] 1.4 Test, partial cut unchanged: title clip with a cut over its first seconds; assert the card sits
  immediately before the clip's first kept span, and that a title clip with two kept spans still yields
  exactly one card. Also cover an explicit `title: true` on a later clip that is wholly cut (card moves to the
  chapter's first surviving segment) and a chapter with no title clip whose clips are cut (no card).

## 2. staleness/

- [x] 2.1 Bump `RENDER_GRAPH_VERSION` from 3 to 4 in `staleness/fingerprint.py` and add the history line
  `4: title-card-whole-clip-cut (...)` to its comment. In `tests/test_staleness_fingerprint.py` re-pin
  `PINNED_ENGINE` and `PINNED_COMBINED` (the editorial, defaults and clip-set hashes must not move) and add
  a version-3 manifest test beside `test_version_2_manifest_is_engine_stale` asserting an output recorded
  under version 3 is stale for the engine reason alone. Verify with `tests/test_staleness_fingerprint.py`.

## 3. Validation gates

- [x] 3.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` (only the known
  cairo `no-member` noise remains), and verify all are clean.
- [x] 3.2 Run `.venv/bin/python -m pytest` (podman available; otherwise `-m "not requires_db"` and say so) and
  verify the full suite passes, including `tests/test_title_card.py` and the staleness tests.
