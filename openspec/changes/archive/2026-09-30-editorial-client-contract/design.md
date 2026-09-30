## Context

See proposal.md — Why. The code facts that shape the approach:

- **`api/routes/events.get_reel`** has no `responses=`. It maps `EventNotFoundError` to 404 and
  `EventReadError` to `bad_gateway(f"event {id!r}: {detail}", event_id=...)`, which has a prefix and no
  `failure`. It sets `ETag` from `_etag`. The detail route already answers with the unprefixed form:
  `bad_gateway(exc.detail, event_id=..., failure=exc.failure.value if exc.failure is not None else None)`.
- **`api/events_read.get_reel`** returns an empty `ReelDocument()` when `reel.yaml` is absent (D-R2). It
  catches only `ReelParseError`, as `EventReadError` without a failure kind. An `OSError` escapes as a 500.
- **`api/routes/events.put_reel`** is a sync route, so FastAPI runs it in a threadpool, and two saves can
  run at once in one process. It has no `responses=`:
  - it resolves the event: 404
  - with `If-Match` only, it pre-reads the current document: `EventReadError` becomes a prefixed 502
    without a kind, and a mismatch becomes 412
  - it calls `apply_editorial_write(event_dir, payload.model_dump(by_alias=True))`
  - it maps any `ReelError` to `bad_request` (400). That includes the `ReelParseError` that
    `apply_editorial_write` raises when the **existing** file is unparseable
  - an `OSError` from the write is uncaught: a bare 500
- **`event/editorial.apply_editorial_write`:** load current or empty → `document_to_data` → merge the
  sections → `build_document` (schema and cross-reference validation) → `write_document`. The
  processability rule is never consulted.
- **`reel/writer.write_document`** is `Path(path).write_text(dumps_document(doc))`: truncate, then write.
  Its callers:
  - `apply_editorial_write`
  - `cli/adoption.persist`, through `prepare_and_persist`: the render staleness filter, render-job
    building, and the worker
  - `import` (`_import_event`)
- **Shared pieces already exist:**
  - `event/metadata.py`: `with_resolved_metadata(document, event_dir)` (the resolution every consumer
    uses, over `event/discovery.parse_folder_name`, which never raises) and
    `require_processable(event_dir, metadata, *, today)`, which raises `EventMetadataError`
  - `errors.EventMetadataError` is a **subclass of `ReelError`**
  - `api/events_read.py`: `classify_event_failure`, which already tests `EventMetadataError` before
    `ReelError`, and `EventReadError(..., failure)`
  - `api/schemas.py`: `ProblemOut.failure`
- **Semantics (D-E2):** the write body is the complete state. `model_dump` always includes every section
  (defaults: empty metadata, `look` `{}`, `chapters` `[]`, `clips` `{}`, `ignore` `[]`), so an omitted
  section clears. This is intended, and specified here explicitly.

## Goals / Non-Goals

**Goals:**

- Each editorial failure has one published status and shape, by cause (400 request, 412 race, 502 disk),
  identical on both write paths.
- The engine never persists an unprocessable event state, and never a partial `reel.yaml`.

**Non-Goals:**

- Patch semantics.
- `sort` in the body.
- The jobs routes.
- The screen.

## Research & Decisions

### Status by cause, and one pre-read

**Decision**: `put_reel` reads the current document through `events_read.get_reel` on every request, then
checks the precondition, then applies:

```python
try:
    current = events_read.get_reel(settings, event_id)
except events_read.EventReadError as exc:
    failure = exc.failure.value if exc.failure is not None else None
    return bad_gateway(exc.detail, event_id=event_id, failure=failure)
if if_match is not None and not _if_match_satisfied(if_match, _etag(current)):
    return precondition_failed(...)                      # unchanged
try:
    document = apply_editorial_write(event_dir, desired_data)
except EventMetadataError as exc:                        # before ReelError: it is a subclass
    return bad_request(str(exc), event_id=event_id, failure=EventFailure.UNUSABLE_METADATA.value)
except ReelError as exc:                                 # the submitted state is invalid
    return bad_request(str(exc), event_id=event_id)
except OSError as exc:                                   # the filesystem refused the save
    return bad_gateway(f"reel.yaml could not be saved: {exc}", event_id=event_id)
```

The `OSError` 502 has no `failure`. The kinds describe why an event cannot be *read*; this is a refused
save. Its detail names the OS error, for example `[Errno 30] Read-only file system`.

**Rationale**:
- A 400 means "fix your request". A broken file on disk is not the request's fault, and the reads already
  call it a 502 with a kind.
- Pre-reading on both paths costs one parse and makes the two paths agree by construction.
- If the file breaks between the pre-read and the apply (a race), the apply's own load still raises. That
  surfaces as 400, which is rare and documented as a risk.

### The editorial read's classification

**Decision**:
- `events_read.get_reel` catches `(ReelError, OSError)` into
  `EventReadError(event_id, str(exc), failure=classify_event_failure(exc))`.
- The route's 502 takes the detail route's unprefixed form, so the three reads agree word for word.
- An absent `reel.yaml` is still 200 with the empty document, even for an event whose folder name is
  unusable. That is how the GUI fixes it.

### Refusing unprocessable states in the engine

**Decision**: `apply_editorial_write(event_dir, desired_data, *, today: Optional[date] = None)`. After
`build_document`, it resolves the metadata exactly as every consumer does and checks it before writing:

```python
resolved = with_resolved_metadata(document, event_dir).metadata
require_processable(event_dir, resolved, today=today or date.today())  # raises EventMetadataError
write_document(document, reel_path)                                    # the authored document
```

**Rationale**:
- The rule lives in the engine operation, so a future CLI editorial command inherits it (Principle V).
  The API only maps it to a status code.
- Resolution is never written back: the persisted document stays as authored.
- A body without a date is fine for `2024-06-21 - Trip`, and refused only where nothing supplies a date.
  `parse_folder_name` never raises, so an authored date also rescues `2019-04-31 - Golfträning…`, whose
  folder date is impossible.
- `require_processable` already words the refusal: "no date: folder name has a year only (2004); set
  metadata.date in reel.yaml or correct the folder name".
- `today` is injectable for deterministic tests.

### Atomic `reel.yaml` replacement

**Decision**: `reel/writer.write_document` serializes first, then writes a uniquely named hidden sibling,
makes it durable, and renames it over the original:

```python
def write_document(doc: ReelDocument, path: Union[str, Path]) -> None:
    path = Path(path)
    text = dumps_document(doc)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)  # the umask applies
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
```

**Rationale**:
- **Unique names:** the API's threadpool can run two saves in one process, so a per-pid name could be
  shared and interleaved. A random name with `O_EXCL` cannot.
- **Rename:** on POSIX filesystems, `os.replace` within one folder is atomic: a reader sees the old file or
  the new one.
- **Read-only mount:** the temporary file's `os.open` fails first, so nothing is touched, and the
  `OSError` propagates to the 502 above.
- **Leftovers are never read:** the loader reads only `reel.yaml`, and clip discovery takes only
  `VIDEO_EXTENSIONS`.
- **Permissions:** mode `0o666` minus the umask gives the permissions `write_text` gave a new file.
- **No folder `fsync`:** if a power loss drops the rename, the old document remains, beside a leftover
  temporary file.

## Failure behavior and idempotency

- **400** (an invalid state or an unusable resulting metadata): nothing written.
- **404**: nothing written.
- **412**: nothing written.
- **502** (an unreadable current file): nothing written.
- **502** (the filesystem refused the save): nothing written, and the temporary file is removed.
- **Re-submitting** the same body is idempotent (the unmodified-save scenario holds). A retry after a 502
  save failure succeeds once the filesystem allows it.
- **The render and import paths** gain atomicity for free, and their behavior is otherwise unchanged.
- **No `RENDER_GRAPH_VERSION` bump**, and no fingerprint change.

## Risks / Trade-offs

- **[NTFS replaces in steps]** On the archive's NTFS mount, the driver emulates a rename over an existing
  file in more than one step (ntfs-3g moves the old name aside first). A disconnect at that exact instant
  can leave both versions under other names and no `reel.yaml`, but never a truncated file. → Accepted: the
  window is a few metadata operations, versus the whole write today. The README says how to recover: rename
  the leftover `.reel.yaml.*.tmp` to `reel.yaml`.
- **[The replaced file changes owner]** The replaced file takes the writer's owner and default permissions,
  not the old file's. → On the NTFS archive, both come from mount options anyway. Elsewhere, this matches a
  newly created `reel.yaml`.
- **[A race between the pre-read and the apply]** A file broken in between yields 400 instead of 502. →
  This is rare and harmless: nothing is written, and a re-read reports the 502.
- **[Existing tests]** The editorial tests' documents and folder names all carry dates, so none should
  change. → A test that does fail gets a date, never a weaker rule.
- **[`os.fsync` cost]** One fsync per save or adoption. → That's negligible next to a render.

## Migration Plan

Regenerate `web/openapi.json` and `web/src/api/schema.d.ts`. There is no data migration. Rollback means
reverting the pre-read, the validation step, the writer and the declarations.
