## Context

See proposal.md — Why. The code facts that shape the approach:

- **`event/reconcile.py`:** `class ClipStatus(enum.Enum)` has `NEW`/`MISSING`/`ACTIVE`/`IGNORED`. Its uses
  are `is` comparisons (`api/events_read._clip_out`, and the `event/discovery.seed_document` assertion),
  dictionary values in `ReconcileResult.classification`, and the CLI's `classification[identity].value`.
  Nothing formats a member with `str()`.
- **`api/schemas.py`:**
  - `ClipOut.status: str`, filled with `status.value` by `_clip_out`
  - `EventFailure(StrEnum)` (three kinds), used by the list's `EventErrorOut`
  - `ProblemOut` publishes `title`/`status`/`detail`, plus optional `check` and `event_id`, and allows extras
- **`api/events_read.py`:**
  - `list_events` classifies per event inline: `EventMetadataError` → `UNUSABLE_METADATA`, then
    `ReelError` → `UNPARSEABLE_REEL_YAML`, then `OSError` → `UNREADABLE_DISK`
  - `get_event` catches only `(ReelParseError, EventMetadataError)` into `EventReadError(event_id, detail)`
  - `ReelImportError`, `ReconcileError` and `OSError` escape, for example from `scan_event`, or from
    `order_clips`' `os.stat` under the `datetime` rule, and become a bare 500
  - `_file_facts` already turns a per-clip `stat` failure into nulls, by design
- **`api/routes/events.get_event`** maps `EventReadError` to `bad_gateway(..., event_id=...)`.
- **The web client** (`web/src/api/events.ts`) reads `ProblemOut.check`/`event_id` only. Nothing reads
  `ClipOut` yet.

## Goals / Non-Goals

**Goals:**

- The clip status reaches generated types as a union.
- One classification rule for per-event failures, used by both events reads.
- No per-event failure is ever an unshaped 500.

**Non-Goals:**

- The detail screen (slice C).
- Jobs-route contracts (slice E).
- The editorial read's 502 (slice D).

## Research & Decisions

### The clip status vocabulary

**Decision**:
- `ClipStatus(StrEnum)`, with values unchanged.
- `ClipOut.status: ClipStatus`.
- `_clip_out` passes the member instead of `.value`.

**Rationale**:
- This is §4.10's rule: a closed set is typed by the enumeration its owning layer defines, and `event/`
  owns reconcile.
- `StrEnum` matches `StalenessReason`. Members are `str`, so the few string comparisons in tests and
  clients keep working, `is` comparisons are unaffected, and serialization is the same string.
- No `api/` duplicate is created.

### One classifier for both reads

**Decision**:

```python
# api/events_read.py
def classify_event_failure(exc: BaseException) -> Optional[EventFailure]:
    """The API's kind for a per-event engine failure, or None when it is not one."""
    if isinstance(exc, EventMetadataError):   # before ReelError: it is a subclass
        return EventFailure.UNUSABLE_METADATA
    if isinstance(exc, ReelError):
        return EventFailure.UNPARSEABLE_REEL_YAML
    if isinstance(exc, OSError):
        return EventFailure.UNREADABLE_DISK
    return None
```

- **`list_events`:** its three inline branches become one `except (ReelError, OSError) as exc`, which calls
  the classifier. The behavior is unchanged: its tests are the proof.
- **`get_event`:** after `resolve_event_dir` (so a 404 stays a 404), the load, reconcile, chapters and
  staleness run inside `except (ReelError, OSError) as exc`. That raises
  `EventReadError(event_id, str(exc), failure=classify_event_failure(exc))`. `EventReadError` gains
  `failure: Optional[EventFailure] = None`, and the editorial read keeps raising it without a kind.
- **The detail route** returns `bad_gateway(exc.detail, event_id=event_id, failure=exc.failure.value)`
  when a kind is present. `detail` is the engine's text **unprefixed**, exactly the list row's `detail`, and
  the event is named by `event_id`. Today's `event '<id>': …` prefix is dropped, because it would make the
  same failure read differently on the two screens. No test pins the prefix.
- `ProblemOut` gains `failure: Optional[EventFailure] = None`, which is schema-only, like its other fields.

**Rationale**:
- A single function is the only way "the two reads never disagree" holds by construction rather than by
  care.
- Catching only `ReelError` and `OSError` keeps Principle I intact: `SQLAlchemyError` still becomes the 503,
  and anything unanticipated is still a 500.
- `resolve_event_dir` stays outside the catch, so an unknown ID is never misreported as unreadable.

**Alternative rejected**: a FastAPI exception handler for `ReelError`/`OSError` across all event routes. It
would change the editorial and analysis routes' behavior too, outside this change's specs.

### Test for the list/detail agreement

**Decision**: For each of the three kinds, a test builds one broken event and asserts that the list's error
row and the detail's 502 carry an equal `failure` and an equal detail.

The three broken events:
- an unparseable `reel.yaml`
- the `2019-04-31 …` folder name
- an unreadable directory (`chmod 000` on a tmp event dir, restored in `finally`, skipped when running as
  root)

**Rationale**: It asserts the requirement directly: agreement by construction, not two parallel tests that
could drift.

## Failure behavior and idempotency

- **Nothing new is written:** both reads stay read-only.
- **A per-event failure** on the detail is a 502 with its kind. The database is still a 503, and an unknown
  event is still a 404.
- **Re-requests** give the same classification for unchanged disk.
- **No `RENDER_GRAPH_VERSION` bump**, and no fingerprint change.

## Risks / Trade-offs

- **[`ClipStatus` changes base class]** Code relying on a member *not* equalling its string would change
  behavior. → A search shows no such use. The engine's own reconcile and adoption tests are the proof, and
  they must pass unmodified.
- **[A new optional field on `ProblemOut`]** It is additive, and the web client's `isProblem` guard checks
  only `title`/`status`/`detail`.
- **[`OSError` on the detail now a 502 rather than a 500]** This is intended, and it is exactly the list's
  behavior for the same event.

## Migration Plan

Additive and wire-compatible. Regenerate `web/openapi.json` and `web/src/api/schema.d.ts` with the
`web/README.md` commands. There is no data migration and no rescan. Rollback means reverting the enum
base, the annotation, the classifier's use in `get_event`, and the problem field.
