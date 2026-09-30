## 1. reel/ + event/ — safe, validated editorial writes

- [x] 1.1 Make `reel/writer.write_document` replace `reel.yaml` atomically under a unique temporary name (design "Atomic `reel.yaml` replacement"). Verify with tests in `tests/test_reel_writer.py`:
  - a successful write leaves no `.reel.yaml.*.tmp` file
  - two writes use different temporary names (record `os.replace`'s source)
  - with `os.fsync` monkeypatched to raise, the previous content survives byte-for-byte, the temporary file is removed, and the error is re-raised
  - a directory made read-only (`chmod`, restored in `finally`; skipped as root) raises `OSError`, leaves the file unchanged, and leaves no temporary file
- [x] 1.2 Add the resolved-metadata check, with an injectable `today`, to `event/editorial.apply_editorial_write` (design "Refusing unprocessable states in the engine"). Verify with tests in `tests/test_event_editorial.py`:
  - a `Blandat` folder with a state that has no date raises `EventMetadataError` naming the missing date, and the file is unchanged
  - a date after the injected `today` raises, and nothing is written
  - `2004 - Yngve berättar om skövde` with `metadata.date: 2004-05-01` is written, and `load_event_document` plus `require_processable` then pass
  - `2019-04-31 - Golfträning med Emil - Tjörn` with a real date is written
  - `2024-06-21 - Trip` with a title only is written
  - the existing tests pass unchanged

## 2. api/ — status by cause, published

- [x] 2.1 Classify `events_read.get_reel` failures as `(ReelError, OSError)` with a `failure` kind, and give the read route's 502 the detail route's unprefixed form (design "The editorial read's classification"). Verify with `tests/test_api_editorial_read.py`:
  - an unparseable `reel.yaml` gives a 502 with `failure == "unparseable_reel_yaml"`
  - an absent `reel.yaml` in `2004/2004 - Yngve berättar om skövde` gives 200 with an `ETag`, and no file is created
  - the existing tests pass, adjusted only where they assert the old prefixed detail
- [x] 2.2 Rework `put_reel` as the design's "Status by cause, and one pre-read" shows: pre-read on every request, `EventMetadataError` before `ReelError`, and `OSError` as a 502. Verify with `tests/test_api_editorial_write.py`:
  - a write without `If-Match` onto an unparseable existing file gives 502 with `unparseable_reel_yaml` (it was 400), and the file is untouched
  - a `2024/Blandat` body without a date gives 400 with `unusable_metadata`, and the detail names the missing date
  - a read-only event directory gives 502 whose detail names the error, with the file unchanged
  - a body omitting `ignore` clears it, and one carrying the read's `ignore` preserves it
  - 404 and 412 are unchanged
- [x] 2.3 Declare `responses=` on both routes, then regenerate `web/openapi.json` and `web/src/api/schema.d.ts` with the `web/README.md` commands:
  - read: 200 with the `ETag` header, then 404 and 502
  - write: 200 with the `ETag` header, then 400, 404, 412 and 502
  - every problem response as `ProblemOut`

  Verify:
  - a new `tests/test_api_openapi.py` case asserts exactly those codes and both `ETag` headers
  - the schema staleness test passes
  - `npx tsc --noEmit` passes in the node:22 container with no client change

## 3. Docs

- [x] 3.1 Update the `GET`/`PUT …/reel` entries in `README.md`'s API service section. Verify by rereading them against the specs.
  - the write body is the complete state: omitting a section clears it, so write back what you read
  - the status meanings: 400 request, 404, 412 race, and 502 disk, with `failure` when the file cannot be read
  - `reel.yaml` is replaced atomically. A leftover `.reel.yaml.*.tmp` holds a save that did not finish: if `reel.yaml` is missing, rename the leftover back to `reel.yaml`; otherwise delete it

## 4. Validation

- [x] 4.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`, including `requires_db`. Verify all are clean or green, apart from the known cairo `no-member` noise.
