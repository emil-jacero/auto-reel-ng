## 1. api/ — the write endpoint's ETag

- [x] 1.1 Emit `ETag` on a successful `PUT /api/v1/events/{event_id}/reel`, computed by the existing `_etag`
      helper from the `ReelDocument` `apply_editorial_write` returns (Decision 1) — injected `Response`, as
      `get_reel` already does. Tests in `tests/test_api_editorial_write.py` (`requires_db`): the write's tag
      equals the tag a following `GET .../reel` returns; an unmodified save returns the tag it was given.
- [x] 1.2 Test the chained-write guarantee the GUI depends on: two consecutive conditional writes, the second
      using the `ETag` the first returned, both applied, with **no** read of `/reel` between them.
- [x] 1.3 Test that a 412 refusal carries **no** `ETag` (Decision 1), and still leaves `reel.yaml`
      byte-for-byte unchanged.

## 2. api/ — per-clip file facts

- [x] 2.1 Add optional `size: Optional[int]` and `mtime: Optional[datetime]` to `ClipOut` in
      `api/schemas.py` (Decision 3), documented as file facts, never media facts.
- [x] 2.2 Populate them in `api/events_read.py`: `_build_chapters` takes `event_dir` and resolves
      `event_dir / identity` (the mapping `render/segments.py` uses); MISSING clips are not statted and
      report `(None, None)` (Decision 2). Tests in `tests/test_api_events.py` (`requires_db`): an ACTIVE clip
      and a disk-only NEW clip both carry size and a UTC-aware mtime; a clip referenced by `reel.yaml` but
      absent from disk reports both null while still reporting MISSING.
- [x] 2.3 Cover the two edge cases: a clip inside a **named chapter subdirectory** is statted at its
      event-relative identity path (not the event root); and a `stat` that raises `OSError` mid-request
      yields `(None, None)` rather than failing the event's detail (Decision 4).
- [x] 2.4 Test that the facts cost no probe — an event whose clip files are truncated/undecodable still
      returns their size and mtime — and that `GET /api/v1/events` is unchanged (no per-clip facts on the
      list response).

## 3. docs

- [x] 3.1 Document the write response's `ETag` in `README.md`'s API section, next to the existing `If-Match`
      entry, including the rule that a 412 carries none and forces a re-read.
- [x] 3.2 Record the boundary rule in `docs/high-level-design.md` §4.9 (Decision 5): the events read model is
      probe-free — file facts come from `stat`, media facts (duration, dimensions, codec) require the
      analysis cache and never a per-request probe.

## 4. Validation gates

- [x] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
- [x] 4.2 `.venv/bin/python -m mypy auto_reel_ng`
- [x] 4.3 `.venv/bin/python -m pylint auto_reel_ng` (pre-existing cairo `no-member` noise is not a failure)
- [x] 4.4 `.venv/bin/python -m pytest` (podman required; the five title-card skips are environmental)
