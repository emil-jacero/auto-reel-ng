## 1. Gate

- [x] 1.1 Gate: none; `event-edit-screen` waits for this change. Verify `git diff 541c44c -- auto_reel_ng/event/editorial.py openspec/specs/editorial-write/spec.md` prints nothing; if the spec differs, re-base the MODIFIED block before implementing.

## 2. event/ — keep each list entry's comments

- [x] 2.1 Leave an unchanged list untouched (design "Leave an unchanged list untouched"). First add two commented fixtures and their tests to `tests/test_event_editorial.py`, and see the tests fail on the current code:
  - `SOMMARLOV`: the dev library's `2024-09-01 - Sommarlov` `reel.yaml`, copied byte for byte from `scripts/make_dev_library.py` (`- borttagen.mp4  # MISSING`)
  - `SOMMARLOV_ANNOTATED`, the spec's fixture:
    - a comment on the chapter name
    - an own-line `# the opening shot` above the first clip
    - `- s1710002.mp4   # first`
    - `# before second`
    - `- s1710004.mp4   # second`
    - `- borttagen.mp4  # MISSING`
    - `# between chapters`, then a `Kvällen` chapter with two clips, one of them commented
    - a block-style `ignore` list holding `- junk.mp4  # never render`
  - the tests, each through `apply_editorial_write` with `_desired_from(load_document(...))`:
    - `SOMMARLOV` round-trips byte-identical
    - so does `SOMMARLOV_ANNOTATED`
    - so does an ignore-only fixture
    - reordering only `Kvällen`'s clips leaves every line of the root chapter's clip list unchanged

  Then, in `event/editorial.py`, make `_apply_chapters` and `_apply_ignore` skip the empty-and-refill when the stored list already equals the desired one.

  Verify:
  - before the code change, `.venv/bin/python -m pytest tests/test_event_editorial.py -k "noop or no_op or untouched"` fails only on the new tests, and the diff shows the dropped `# MISSING`
  - after it, `.venv/bin/python -m pytest tests/test_event_editorial.py` passes, the existing tests unchanged
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
- [x] 2.2 Keep each entry's comments in a changed list. Add `_EntryComments`, `_entry_comments` and `_rewrite_identity_list` with design "The helper" steps 1, 2, 4 and 5, taking the 2.1 check as step 1 and the header from `parent.ca.items[key][3]` or `seq.ca.comment[1]`. Then:
  - `_apply_chapters`: collect every existing chapter's comments and trailing text before any mutation, then rewrite each reused chapter's `clips` through the helper
  - `_apply_ignore`: rewrite through the helper
  - remove both `del …[:]` / `extend` refills
  - update the module docstring's round-trip sentence to cover list entries

  Add one test per scenario below from the `editorial-write` delta. Each compares the whole persisted file to an expected string over `SOMMARLOV_ANNOTATED`:
  - a reorder moves each clip's comments, at the original columns, and `# the opening shot` travels with `s1710002.mp4`
  - a clip moved to `Kvällen` keeps `# MISSING`
  - removing `s1710002.mp4` drops only `# first` and `# the opening shot`
  - an added `ny.mp4` carries no comment
  - `# between chapters` stays after the root chapter's new last clip
  - a renamed chapter is written fresh, without clip comments

  Also assert that `editorial_hash` of the document each write returns equals `editorial_hash(load_document(...))` of a comment-free copy of the same state, so comments never move the fingerprint or the `ETag`.

  Verify:
  - `.venv/bin/python -m pytest tests/test_event_editorial.py` passes
  - each test applies its desired state a second time and asserts the file is byte-identical
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
- [x] 2.3 Handle ruamel's other storage layouts: design "The helper" steps 3 and 6, the key token's first-line trim in step 2, and the key token's tail as the third header source in `_entry_comments`. Add a test for each, comparing the whole persisted file to an expected string:
  - `SOMMARLOV_ANNOTATED`: moving every root clip to `Kvällen` persists `clips: []`, still followed by `# between chapters`
  - a variant with `Kvällen` in flow style: a commented clip moved in turns the list block style, and the file loads back with the same chapters
  - a variant with `clips:   # root list` on the root chapter: a reorder keeps `# root list` on the key line, `# the opening shot` travels with `s1710002.mp4`, and reversing the reorder restores the original bytes

  Verify:
  - `.venv/bin/python -m pytest tests/test_event_editorial.py` passes, the 2.1 and 2.2 tests unchanged
  - `.venv/bin/python -m mypy auto_reel_ng` is clean

## 3. api/ — the unmodified-save scenario

- [x] 3.1 Add a case to `tests/test_api_editorial_write.py` (`requires_db`). The event is `2024/2024-09-01 - Sommarlov`, its `reel.yaml` is the `SOMMARLOV` text, `s1710002.mp4` and `s1710004.mp4` are touched files, and `borttagen.mp4` is absent:
  1. `GET …/reel`
  2. `PUT` its body back with the read's `ETag` in `If-Match`

  Verify:
  - the response is 200
  - `reel.yaml` is byte-for-byte unchanged, `# MISSING` included
  - the write's `ETag` equals the read's

## 4. Validation

- [x] 4.1 Run the validation gates:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, including `requires_db`

  Verify: all are clean or green, apart from the known cairo `no-member` noise and the environmental title-card skips. `RENDER_GRAPH_VERSION` in `staleness/fingerprint.py` is unchanged (still 3).
