## 1. Deterministic test input

- [x] 1.1 In `tests/test_api_thumbnails.py`, replace `os.urandom(20_000)` with a module constant holding the fixed text pattern, rename the clip `random.mp4` to `not-media.mp4` everywhere in that test (request keys, `detail.startswith` prefix, log lookup), update the docstring, and drop the `os` import if nothing else uses it. Verify with `.venv/bin/python -m pytest tests/test_api_thumbnails.py -k undecodable -q` passing and `grep -n "urandom\|random.mp4" tests/test_api_thumbnails.py` printing nothing.
- [x] 1.2 Keep the assertions for the non-media clip exact: 502, `thumbnail_failure == "thumbnail_failed"`, a detail beginning `not-media.mp4: ffprobe could not read`, no `/` and no newline in the cause, and a warning log carrying `Command exited` and `stderr:`. Verify by temporarily making the constant empty bytes in a scratch run and seeing the test fail on the wording assertion (it must not pass vacuously), then restoring it.

## 2. Stability

- [x] 2.1 Run the single test 50 times in a row with `TMPDIR` set, e.g. `for i in $(seq 50); do .venv/bin/python -m pytest tests/test_api_thumbnails.py -k undecodable -q -p no:cacheprovider || break; done`, and verify all 50 runs pass and the loop does not break.
- [x] 2.2 Run `.venv/bin/python -m pytest tests/test_api_thumbnails.py -q`, then `black --check`, `isort --check` and `mypy` on `tests/test_api_thumbnails.py`, and verify all pass.
