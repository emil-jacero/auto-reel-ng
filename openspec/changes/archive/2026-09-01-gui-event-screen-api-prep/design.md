## Context

See `proposal.md` — Why. The relevant current state:

- `put_reel` (`api/routes/events.py`) computes `_etag(current)` only on the `If-Match` path, then returns
  `EditorialWriteResult` with no header. `_etag` wraps `editorial_hash`, extracted into
  `staleness/fingerprint.py` by `editorial-read-api` precisely so both sides could share it.
- `_build_chapters` (`api/events_read.py`) builds `ClipOut`s from a `DiskListing` (identities only) and a
  `ReconcileResult` (identity → status). It never sees the event directory, so it cannot touch a file today.
- A clip **identity is the event-relative POSIX path** (`_video_identities` → `path.relative_to(event_root)`),
  so `event_dir / identity` is the clip file — the same mapping `render/segments.py:176` uses.
- `compute_fingerprint` reads each clip's size+mtime through `analysis.cache.clip_signal` for the probe-free
  fingerprint, but on a later call and in a different shape.

## Goals / Non-Goals

**Goals:**
- A client can chain conditional writes with no intervening read.
- A clip in the detail response carries enough to be recognised and time-ordered by a human, with no decode.
- Both halves are additive: no existing response field changes type or meaning, and no existing client breaks.

**Non-Goals:**
- Any second source for the facts (no caching, no DB column, no sidecar). The `stat` is cheap; storing it
  would be derived state that Principle II says must stay rebuildable and D-A3 says is scanned per request.
- Reusing the *fingerprint's* clip signals as the response's source (see Decision 2).

## Decisions

### Decision 1 — The write's ETag is computed from the document it echoes, not re-read from disk

```python
document = apply_editorial_write(event_dir, desired_data)
response.headers["ETag"] = _etag(document)     # the same helper get_reel uses
```

`apply_editorial_write` returns the persisted `ReelDocument`, and `editorial_hash` is canonical over typed
fields — so the tag matches what a subsequent `get_reel` computes **by construction**, with no second parse
and no window in which the two could disagree. The alternative, re-reading `reel.yaml` after the write to tag
it, buys nothing and reintroduces the round trip this change removes.

`FastAPI` supplies the `Response` object by parameter injection, exactly as `get_reel` already does — the
route keeps returning its `EditorialWriteResult` model.

**No `ETag` on the 412 path.** The refusal already returns a `problem.py` response object, so nothing is
added there; a test pins the absence. Handing back the *current* tag would let a client retry immediately
and overwrite a change it never looked at — the lost update the precondition exists to stop.

### Decision 2 — File facts come from a direct `stat`, not from the staleness clip signals

```python
def _file_facts(path: Path) -> tuple[Optional[int], Optional[datetime]]:
    """(size, mtime UTC) for a clip on disk; (None, None) if it is not there."""
```

Reusing `analysis.cache.clip_signal` was considered and rejected: with `use_hash=True` it returns
`{size, sha256}` and **drops mtime entirely**, so the response's shape would silently depend on a staleness
configuration switch. The read model would also start importing a staleness/analysis internal for a
presentation concern. A `Path.stat()` at the point of use has neither problem and is the same syscall.

`_build_chapters` gains `event_dir: Path` and resolves `event_dir / identity`. MISSING clips are known from
`result.classification` and are **not** statted — there is no file to stat, and the requirement says report
null.

### Decision 3 — `mtime` is a timezone-aware UTC `datetime`, not an integer

`datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)`. Pydantic serialises it to ISO-8601 and OpenAPI types
it as `string(date-time)`, so the GUI's generated TypeScript gets a parseable value rather than a raw epoch
it must guess the unit of. `st_mtime_ns` (the fingerprint's form) is deliberately not exposed: it is a change
*signal*, and pinning the response to nanosecond precision would make it one.

`size` is a plain `int` (bytes). Formatting is the client's job.

### Decision 4 — A clip that vanishes mid-request reports null, and does not fail the request

The scan and the `stat` are separate syscalls; a clip can be deleted between them. `OSError` from the `stat`
is caught and yields `(None, None)` — the same representation as MISSING.

This is not fabrication (Principle I): null is the honest statement that the facts are unavailable, and it is
the same answer the client would have got a moment later. Failing the whole event's detail because one clip
moved during the read would be worse behaviour, and the reconcile status the client also receives is subject
to the identical race today.

### Decision 5 — The boundary rule goes back into the HLD

"The events read model is probe-free: file facts come from `stat`; media facts (duration, dimensions,
codec) require the analysis cache and never a per-request probe." That outlives this change — it is the rule
that will be quoted when someone asks for `duration` — so it lands as a sentence in `docs/high-level-design.md`
§4.9, not only here. It does not warrant a new `D-n`: it is a consequence of D-A3 plus Principle IV, not a
new decision.

## Research & Decisions

### Cost of the events read path

**Context**: Before adding a per-clip syscall to the detail response — and before designing a GUI list view
on top of a scan-on-request API — we needed to know what that path already costs.

**Explored**: A synthetic library of **300 events × 25 clips** (7500 files), each with a `reel.yaml`, timed
through the exact functions `list_events` calls (layout walk → `load_document` → `scan_event` → `reconcile`),
warm page cache, on this host:

```
walk (layout)                3 ms
scan + reconcile + load    490 ms      ~1.6 ms per event
   load_document (ruamel)    392 ms      80% of it
   scan_event (disk)          87 ms
   reconcile                   2 ms
```

`ruamel` with `typ="safe"` instead of the round-trip parser was measured at 248 ms vs 446 ms for the same 300
files — only 1.8×, and it costs the comment preservation Principle II requires.

**Decision**: Add the `stat` without hesitation, and change nothing else about the read path.

**Rationale**: A `stat` is microseconds against ~1.6 ms per event already spent, and it is confined to the
detail endpoint (one event), not the list. The list's cost is dominated by YAML parsing, is linear (~0.5 s at
300 events, ~1.6 s at 1000), and has an already-designed remedy if it ever matters — the D-7 Postgres index,
which holds derived state and is rebuildable from disk. Swapping the parser is not that remedy. None of this
is a GUI v1 concern.

## Risks / Trade-offs

- **`mtime` is not shoot time.** A copy, a restore, or `rsync` without `-t` rewrites it, so the ordering the
  GUI derives can be wrong for a moved library → Mitigated by scope, not by code: the clip's real creation
  time lives in container metadata and needs a probe, which this change explicitly refuses. The GUI presents
  it as file modification time, not "recorded", and the honest fix is the v2 thumbnail/probe slice.
- **Two extra `stat`s per clip per request** (this one, plus the fingerprint's) → Accepted: measured as noise
  against the parse cost, and deduplicating them would couple the read model to staleness internals for no
  measurable gain.
- **A client could treat the write's ETag as a licence never to re-read** and drift from a `reel.yaml` edited
  by `analyze` under it → Not a regression: the tag is only a precondition, and the next mismatched write
  still gets its 412. The requirement keeps 412 tag-less so the client is forced back to a read.
- **Additive OpenAPI change** → No mitigation needed; no field changes type, and generated clients recompile.

## Migration Plan

No migration. No Alembic revision, no rescan, no `RENDER_GRAPH_VERSION` bump, no `reel.yaml` or `config.yaml`
change. Every existing client keeps working: the new `ETag` is a header clients may ignore, and the two clip
fields are additive and nullable.

Rollback is reverting the commit; nothing on disk or in the database records that this shipped.
