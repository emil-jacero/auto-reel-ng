## 1. staleness/

- [x] 1.1 Extract `editorial_hash(document: ReelDocument) -> str` in `staleness/fingerprint.py` from the
      inline expression in `compute_fingerprint`, and call it from there (D-R1). Ship a regression test that
      pins a known document's four component hashes **and** its combined hash, proving the refactor leaves
      every fingerprint bit-identical and makes no event stale.

## 2. api/

- [x] 2.1 Add `GET /api/v1/events/{event_id:path}/reel` returning `EditorialDocumentBody` built by the
      existing `serialize.document_to_body`. Register it **before** the greedy `{event_id:path}` detail route,
      as the `/analysis` route already documents. Tests: an event whose `reel.yaml` carries trims, `ignore`
      and `look` returns all three; an unknown event returns 404 with a problem body.
- [x] 2.2 Cover the read's two edge cases (D-R2): an event directory with clips but **no** `reel.yaml` returns
      200 with the empty document and creates no file; an unparseable `reel.yaml` fails loud with a problem
      body rather than an empty or partial document. Tests for both.
- [x] 2.3 Emit an `ETag` on the read response from `editorial_hash`. Tests: a comment-only edit to
      `reel.yaml` leaves the ETag unchanged, while a metadata edit changes it.
- [x] 2.4 Honor `If-Match` on `PUT /api/v1/events/{event_id}/reel`, evaluated before the engine operation
      runs (D-R3). Tests: a matching tag writes; `*` writes; a non-matching tag returns 412 with a problem
      body and leaves `reel.yaml` byte-for-byte unchanged; an absent header stays unconditional.
- [x] 2.5 Test the two guarantees the GUI depends on: the read response submitted verbatim to the write
      endpoint leaves `reel.yaml` byte-for-byte unchanged with an unchanged staleness verdict; and the detail
      view diverges observably from the editorial read (a disk clip absent from `reel.yaml` appears as NEW in
      the detail response only), with a detail-shaped body rejected by the write endpoint as a validation
      problem.

## 3. docs

- [x] 3.1 Document the read endpoint and the optional `If-Match` precondition in `README.md`'s API section,
      next to the existing `PUT /api/v1/events/{event_id}/reel` entry — including the rule that a write body
      comes from the editorial read, never from the events detail response.

## 4. Validation gates

- [x] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
- [x] 4.2 `.venv/bin/python -m mypy auto_reel_ng`
- [x] 4.3 `.venv/bin/python -m pylint auto_reel_ng` (pre-existing cairo `no-member` noise is not a failure)
- [x] 4.4 `.venv/bin/python -m pytest` (podman required; the five title-card skips are environmental)
