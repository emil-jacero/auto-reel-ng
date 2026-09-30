## Why

GUI v1 slice **D** (HLD **§6 phase 8**, §4.10) is the first screen that *writes*: reorder clips and edit
metadata, saved through `PUT /api/v1/events/{event_id}/reel` after a `GET …/reel`, with `If-Match` and
`412` for conflicts (`editorial-write-api`, `editorial-read-api`). A form must tell the operator what went
wrong, and in which of three very different situations:

- **"Your edit is invalid"**: show it at the form.
- **"Someone changed this event since you opened it"**: re-read and re-apply.
- **"This event's file on disk is broken"**: nothing the form can fix.

Planning slice D against the shipped endpoints found four gaps. As with the previous screens, they are closed
in `api/` and the engine first, so slice D stays a pure `web/` change (Principle VIII):

1. **The editorial endpoints' problem responses are unpublished.** The read's 404/502 and the write's
   400/404/412/502 exist but are not in the OpenAPI schema, so the client would have to declare their shape
   by hand, which the `web-app` spec forbids. The `ETag` response header, which the conditional write depends
   on, is also undocumented.
2. **A write onto a broken file blames the request.** Without `If-Match`, a `PUT` onto an event whose
   existing `reel.yaml` cannot be parsed returns **400 "bad request"**. The request was fine: the disk is
   the problem. The reads already call this a 502 with a `failure` kind, and the conditional path already
   answers 502. The two write paths disagree with each other and with the reads.
3. **The editorial read's 502 carries no `failure` kind.** This was deferred here by
   `event-detail-client-contract`.
4. **A write can leave the event unprocessable, and succeed.** Clearing the date of an event whose folder
   name has none, or typing a future date, is persisted. The event then silently becomes a "Needs
   attention" row (`event-metadata-resolution`). The engine should refuse the state instead, and say why.
   The inverse is the point: setting a real date through the form is how the GUI gives a date to the three
   archive events whose folder names have no usable one (`2004 - Yngve…`, `2016 - Kents film…`,
   `2019-04-31 - Golfträning…`).

5. **A save can corrupt `reel.yaml`, and a failed save is unshaped.** `reel/writer.write_document` is
   `Path.write_text`, which truncates the file and then writes it. A failure mid-write (a full disk, or the
   archive's USB drive disconnecting, which it did once on 2026-09-26) leaves a truncated `reel.yaml`, the
   editorial source of truth (Principle II). A save the filesystem refuses (the archive mounted read-only,
   its normal safe mode) surfaces as an unshaped 500, which the web client reports as "service not
   reachable". Slice D is the first feature that writes `reel.yaml` interactively.

One more point is documentation rather than a defect. The write body is the **complete** editorial state
(D-E2), so a body that omits `ignore` clears the event's ignore list. That is by design (a client preserves
it by writing back what it read), but it is easy to misread as data loss: it was, while planning this change.
The spec states it only implicitly, so it gains an explicit scenario.

## What Changes

- **Both editorial endpoints publish their problem responses and the `ETag` header** in the schema:
  - the read: 404 and 502
  - the write: 400, 404, 412 and 502
  - both: the `ETag` response header on 200
- **A broken existing document is a 502 on the write, with its `failure` kind.** The write reads the event's
  current document first on every path, not only with `If-Match`. A document that cannot be read is answered
  with the scan-failure 502 carrying the `failure` kind the reads use, and nothing is written. **400 is
  reserved for an invalid submitted state.**
- **The editorial read's 502 carries the `failure` kind**, classified exactly as the list and the detail
  classify it.
- **The engine refuses an editorial state that would leave the event unprocessable.**
  `apply_editorial_write` validates the merged document's **resolved** metadata (reel.yaml over folder name)
  against the event rule: a real date, a title, and not in the future. When the rule fails, it raises naming
  the problem, and nothing is written. The write endpoint answers **400 with `failure: unusable_metadata`**,
  so a form can point at the date or title field.
- **`reel.yaml` is replaced atomically.** The writer writes a temporary file in the same folder,
  `fsync`s it, and renames it over the original. A failed save, or one interrupted before the final rename,
  leaves the previous document intact, never a partial one. This is shared by every writer: the editorial save, adoption on render, and
  `import`.
- **A save the filesystem refuses is a 502 naming the OS error**, for example "Read-only file system",
  not an unshaped 500.
- **The spec states the complete-state semantics outright:** omitting a section clears it, and writing back
  what was read preserves everything, `ignore` included.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.** No client code reads these responses
  yet.

## Non-goals

- **No partial-update semantics.** D-E2's coarse write stays. A client sends everything it read.
- **No per-event `sort` in the editorial body.** A write already preserves it, because the merge never
  touches it. No slice edits it yet (Principle VII), and it is added when one does.
- **No jobs-route contract work** (slice E).
- **No screen** (slice D).
- **No refusal of states that are merely unusual.** Only the event rule (real date, title, not future)
  refuses. Titles, locations and clip orders the operator types are theirs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - `Requirement: Editorial write endpoint`: published responses, 400 vs 502 by cause, the unusable-metadata
    refusal, and explicit complete-state semantics
  - `Requirement: Editorial document read endpoint`: a 502 with the failure kind, and the published responses
- `editorial-write`: `Requirement: Editorial writes are validated fail-loud and atomic in effect` also
  validates that the resolved metadata keeps the event processable, and makes the file replacement itself
  atomic

## Impact

- **Packages:**
  - `event/`: `editorial.py`'s `apply_editorial_write` gains the resolved-metadata check. It takes a
    `today`, which defaults to the current day.
  - `api/`:
    - `routes/events.py`: `responses=` on both routes, the pre-read on every write path, and the 400/502
      mapping
    - `events_read.get_reel`: classification
  - `reel/`: `writer.write_document` does the atomic replace.
  - Regenerated `web/` artifacts.
- **CLI vs API (Principle V):** the refusal lives in the engine operation, so any caller, CLI included, gets
  it. The API only maps it to a status code.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan.
- **Wire:**
  - a write onto a broken file changes from 400 to 502
  - a write that would clear an event's only date changes from 200 to 400
  - the read's 502 gains `failure`
  - a save the filesystem refuses changes from 500 to 502
  - every other response is unchanged
- **Dependencies:** none.
- **Size (Principle VIII):** two route declarations, one pre-read, one engine validation step, one atomic
  write helper, two capability deltas.
