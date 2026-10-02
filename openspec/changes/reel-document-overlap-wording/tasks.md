## 1. render/

- [x] 1.1 Reword the `kept_spans` docstring in `auto_reel_ng/render/segments.py` to say that overlapping or
  touching cuts are joined as one removal (union) and that listed order does not matter; no logic change.
  Verify: `git diff` of the file shows only the docstring, and `tests/test_render.py` still passes.
- [x] 1.2 Extend `test_kept_spans_complement` in `tests/test_render.py` (or add a sibling test) with the
  overlap `Trim(1.0, 3.0), Trim(2.0, 5.0)` on 10 s giving `[(0.0, 1.0), (5.0, 10.0)]`; touching
  `Trim(1.0, 3.0), Trim(3.0, 5.0)` giving the same list with no zero-length span; nested
  `Trim(1.0, 9.0), Trim(2.0, 3.0)` giving `[(0.0, 1.0), (9.0, 10.0)]`; and unsorted
  `Trim(5.0, 8.0), Trim(1.0, 3.0), Trim(2.0, 6.0)` giving `[(0.0, 1.0), (8.0, 10.0)]`.
  Verify: the test passes, and fails if the sort is removed, if the merged end is not the maximum, or if a
  cut overlapping the previous one is dropped. (Changing `start <=` to `<` is an equivalent mutant: the
  complement loop already yields the same kept spans for touching cuts.)
- [x] 1.3 Add a `build_segments` test in `tests/test_render.py` for a trimmed clip whose cuts overlap
  (`Trim(1.0, 3.0), Trim(2.0, 5.0)`, probed duration 10 s): the segments are `(0.0, 1.0)` and `(5.0, 10.0)`,
  all `is_trimmed`, in source order, and the segment spans do not overlap each other.
  Verify: the test passes under `-m "not requires_db"`.

## 2. reel/

- [x] 2.1 Add parser tests in `tests/test_reel_parser.py`: a `reel.yaml` with trims
  `[{in: 1, out: 3}, {in: 2, out: 5}]` and one with `[{in: 1, out: 3}, {in: 3, out: 5}]` parse without error
  and the clip's `trims` hold both spans in the written order with the written times; a document with
  `[{in: 1, out: 3}, {in: 2, out: 2}]` fails with a `ReelParseError` naming `trims[1]`.
  Verify: the three tests pass, and the first two fail if `_parse_trims` is made to reject or merge overlap.

## 3. Docs

- [x] 3.1 Add one sentence to HLD D-14 in `docs/high-level-design.md`: the GUI's refusal of a new overlapping
  cut is an editing aid, the engine and `reel.yaml` accept overlap and join overlapping or touching cuts as one
  removal. Verify: the sentence is present, and D-14 still says that read overlaps show as their union.

## 4. Gates

- [x] 4.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  and verify they report no change after the edits.
- [x] 4.2 Run `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` and verify
  no new finding (the known cairo `no-member` noise aside).
- [x] 4.3 Run `.venv/bin/python -m pytest` (or `-m "not requires_db"` with a stated reason if podman is
  unavailable) and verify it passes; confirm `RENDER_GRAPH_VERSION` is unchanged, since rendered output for
  identical inputs does not change.
