## Context

See proposal.md, "Why". Written against `origin/main` at `6a7fe16`, **before** its four gates merged, and re-checked on
`d683264` (task 1.1): the gates are in, and the corrections are recorded where they apply. Line numbers
below are approximate.

**`create_job` today** (`api/routes/jobs.py:61-155`), in order:
1. `events_read.named_event_dir(settings, payload.event_id)`: `resolve_event_dir` (a directory inside the
   root) and `(project_root / id).is_dir()`. `Path` joins drop a `./` segment and a trailing `/`, so many
   spellings reach the same folder. `EventNotFoundError` is a 404.
2. `events_read.output_collision(...)`: `ReelError` / `LayoutError` / `OSError` are the scan-failure 502
   (`bad_gateway("event scan failed: ...")`); a collision is a typed 409.
3. `store.active_job(project_root, payload.event_id)`: keyed on the id **verbatim**.
4. `load_or_seed(event_dir, ...)`: **uncaught**. `compute_fingerprint`, then the staleness gate (200 fresh),
   then `store.submit(project_root, payload.event_id, ...)` (201, or the race's 409).

**What the lookup should be already exists.** `events_read.listed_event_dir` (`events_read.py:~122-145`)
is the media and thumbnail routes' lookup: it calls `named_event_dir`, then lists the id's year with the
configured layout and requires `any(event_id_for(settings, ref.event_dir) == event_id ...)`. The comparison
is against the id **as sent**, so it is the canonical-id check. A scratch project on `6a7fe16` shows it
refusing `2024/./A`, `2024/A/`, `2024/A/original`, `2024/A/../A`, `2024` and `` while accepting the id
itself, and listing `2024/NoDate` (an event with an error row, which is why the processable check is a
separate item). A symbolic link inside the project is listed by the walk under its own in-root id, so an
in-project alias still resolves, as `jobs-project-guards` requires.

**What a processable load looks like.** `api/media.py:~190-200` already does, for the movie route:
`load_event_document` + `require_processable`, `except (ReelError, OSError)` -> `EventReadError(event_id,
str(exc), classify_event_failure(exc))`. `routes/events.py:_event_read_failed` maps an `EventReadError` to
`bad_gateway(detail, event_id=..., failure=kind)`. `load_or_seed` (`cli/adoption.py:81`) is
`load_event_document`, so the document `create_job` fingerprints today is the document that must be checked.

**What the gates leave** (read their triage entries; contracts assumed here, verified in task 1.1):
- `engine-output-claims`: `event/claims.py` with `checked_claim(event_dir, order, today) -> (document |
  None, reason | None)` (maps `ReelError`, `EventMetadataError`, `OSError` to a reason; a failure claims
  nothing) and a layout-aware `output_collision(event_dir, *, walk_root, layout, order, today)` in `render/claims.py`
  that takes no `ApiSettings` and returns `OutputCollision(output_path, claimed_by: Tuple[Path, ...])`
  (claimant directories as the layout yields them, sorted by path). **It migrates no caller:** the CLI's
  `_checked_document` still catches `ReelError` only (`cli-batch-isolation-and-claims` migrates it), and
  the API's `_output_claim` is still here.
- `event-permission-errors`: `reel_exists(path)`, true/false from `stat()`, `PermissionError` propagates;
  `scan_event` raises `PermissionError` for a folder that cannot be searched; `load_authored_document`
  uses it. So `load_event_document` on an unsearchable folder now raises `OSError`.
- `api-jobs-db-outage-503`: the four jobs routes wrapped to answer `SQLAlchemyError` with 503 (a local
  decorator in `routes/jobs.py`). This change edits the body of `create_job` inside that wrapper and adds
  nothing to it.
- `api-event-lookup-scope`: `get_analysis` and `put_reel` in `events_read.py` / `routes/events.py`; this
  change does not touch either.

## Goals / Non-Goals

**Goals:**
- Exactly one job id per event, and it is the id the events list shows.
- An event that cannot be processed gets the events reads' 502 with the same failure kind, never a 500 or a
  doomed job.
- The API selects collision claimants with the engine's function, so it and the CLI cannot drift again.
- An unsearchable event folder is an error on the editorial read, not an empty document.

**Non-Goals:** the missing-clips 409; the 503; any edit to `event/`, `render/`, `cli/`; changing what the
events list or the media routes answer; a canonical-id redirect (the 404 is the answer, see below).

## Research & Decisions

### Resolve with the list's lookup, answer 404 for a non-canonical spelling

**Context**: Item 1. A non-canonical id must not reach `store.submit`. The triage sketch allowed a 404 or a
400 that carries the canonical id.

**Explored**: `listed_event_dir` (above); `named_event_dir`'s only callers are `listed_event_dir`, the
collision tests and `create_job`. A 400 with the canonical id needs a second function that computes the
canonical spelling of an arbitrary path, which the walk does not give; and the GUI only sends ids the list
returned.

**Decision**: `create_job` resolves with `listed_event_dir`. Anything it does not return is the 404 an
unknown event gets (`event_id` as sent). `named_event_dir` stays (it is `listed_event_dir`'s first step).

**Rationale**: One rule across the jobs, media and thumbnail routes: an id is an event when the list shows
it. No new code path; a `..` spelling, a trailing `/`, `original/`, the year folder and a `.reelignore`d
event stop being enqueueable with no special cases. In-project symlinks keep working because the walk lists
them. The cost is one year's listing per enqueue, which the collision check already exceeds (it lists the
whole project).

**Consequence worth stating:** the "a `..` spelling is a claimant of its own" and "a folder outside
`input` still claims its own path" behaviours of `jobs-project-guards` become unreachable through the route.
They were defences for ids the route should never have accepted. The function-level tests that pinned them
are replaced (task 3.1), not kept alongside.

### One read-model function: lookup, then load and require processable

**Decision**: add to `api/events_read.py`

```python
def enqueue_target(
    settings: ApiSettings, event_id: str, *, today: DateValue
) -> tuple[Path, ReelDocument]:
    """The listed event ``event_id`` names and its processable document (resolved metadata).

    Raises: EventNotFoundError (not an id the list shows); OSError / LayoutError (the lookup's walk
    failed: the caller's scan-failure 502); EventReadError (the event itself cannot be processed, with
    ``classify_event_failure``'s kind).
    """
    event_dir = listed_event_dir(settings, event_id)
    try:
        document, _seeded = load_event_document(event_dir, order=settings.clip_order)
        require_processable(event_dir, document.metadata, today=today)
    except (ReelError, OSError) as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc
    return event_dir, document
```

`create_job` becomes: `enqueue_target` -> collision -> active job -> fingerprint of the **returned**
document -> gate -> submit. The route maps: `EventNotFoundError` -> `not_found` (as today);
`(LayoutError, OSError)` from the lookup -> the existing `bad_gateway("event scan failed: ...")`;
`EventReadError` -> `bad_gateway(exc.detail, event_id=event_id, failure=kind)`. That last mapping is the
three lines of `routes/events.py:_event_read_failed`; the route writes them locally rather than importing a
private helper from another router module (`api-event-lookup-scope` edits that module).

**Alternatives**: put the load in the route (as today), which repeats the media route's try/except a third
time; or make `listed_event_dir` load (it is used by routes that must not read `reel.yaml`, e.g. the
thumbnail, whose spec says so). Neither. A new function keeps `listed_event_dir`'s contract unchanged.

**Why the lookup's `OSError` and the load's differ**: a year folder that cannot be listed is the walk
failing (the list's scan-failure 502, which names no event and no kind, exactly as for the collision walk).
An event whose own `reel.yaml` or folder cannot be read is that event's failure (502 with `event_id` and
`unreadable_disk`), which is what the list shows as its error row. `enqueue_target` keeps them apart by
type: the lookup's `OSError` propagates raw; only the load's is wrapped.

### Order of the checks

lookup (404, walk 502) -> processable (502 + kind) -> collision (409; walk 502) -> active job (409) ->
gate (200 fresh) -> submit (201, or the race's 409).

**Rationale for processable before collision**: an event that fails on its own claims no path, so the
collision check could only ever answer "no collision" for it; asking first gives the actionable answer.
**Rationale for processable before the active-job check**: nothing is gained by attaching a client to a
job of an event that cannot be processed; the job would fail in the worker too. The only observable change
(an unprocessable event with an active job was 409 and is 502) is a corner of a corner and is specified
(scenario "A failing event outranks an active job").

### Claimants through the engine's one function

**Context**: Item 3. `events_read._output_claim` (`:~375-395`) and the walk in `output_collision`
(`:~398-430`) are the API's copy of the selection; `engine-output-claims` supplies the engine's.

**Decision**: delete `_output_claim`; `events_read.output_collision(settings, event_dir, *, today)` stays as
the adapter from `ApiSettings` (project root, configured layout, walk root, clip order) to the engine's
layout-aware `output_collision`, and shapes the result as the API's `OutputCollision(output_path,
claimed_by)` with ids from `event_id_for`. The merged engine `OutputCollision` carries `claimed_by` as directories, not ids, so the adapter keeps the
API's own `OutputCollision` (ids, sorted) and maps each directory through `event_id_for`.

**What changes semantically**: (a) the `ValueError` guard disappears. Its own comment says every
`reel.yaml` failure is a `ReelParseError` (bad dates and non-UTF-8 bytes included) and that a stray
`ValueError` "is a bug in reading some other event"; keeping it in one client only is how the two copies
diverged, and a latent bug failing loudly (Principle I) is better than being absorbed. The existing
parametrised tests (`unparseable`, `impossible-yaml-date`, `not-utf-8`) pin that the real cases are
`ReelError`s. (b) the named event is always a walked event, so the "plus the named event" special case in
the adapter is dropped with the test that pinned it.

**Failure behaviour**: the walk's `ReelError` / `LayoutError` / `OSError` still propagate to the route's
scan-failure 502; a claimant's own failure claims nothing; nothing is written.

### The `reel.yaml` existence test on the editorial read

**Decision**: in `get_reel`, `reel_exists(reel_path)` replaces `reel_path.exists()` and is moved **inside**
the existing `try`, whose `except (ReelError, OSError)` already builds the `EventReadError` with
`classify_event_failure`: a `PermissionError` is `unreadable_disk`. `resolve_event_dir` still resolves the
folder with `is_dir()`, which needs only the parent's search permission, so a `0600` folder reaches the
read. `get_analysis`'s `exists()` (`:504`) is a clip-file test, not a `reel.yaml` test, and is
`api-event-lookup-scope`'s.

**Other `exists()` sites** (`event/editorial.py`, `cli/commands.py`, `cli/adoption.py`) are owned by
`editorial-chapter-comments` and `cli-batch-isolation-and-claims`; this change does not edit them. The PUT
route's pre-read goes through `editorial.py` and gets the same behaviour when that lands.

## Risks / Trade-offs

- **A client sending a non-canonical id now gets a 404.** Intended; the GUI sends list ids. A scripted
  `curl` that appended `/` breaks loudly rather than creating a job the GUI never sees. The 404 detail
  names the id as sent.
- **A listed event costs one extra document load before the collision walk's** (the named event is loaded
  by `enqueue_target` and again by the engine's claim). One small YAML read; not cached (a per-request
  value, D-A3).
- **Gate drift**: the engine functions' exact signatures, and whether `api-jobs-db-outage-503` reshapes the
  route body, are assumed from triage. Task 1.1 re-reads them and corrects this design and the MODIFIED
  blocks (re-based on the specs as the gates leave them) before any edit. If `reel_exists` or
  `checked_claim` has not merged, stop and report; do not re-implement them here.
- **`.reelignore`d events are no longer enqueueable through the API.** That matches the CLI (the layout
  never yields them) and the list (it never shows them). Previously a client could name one.
- **Unreadable disk on the lookup year versus on the event**: two 502 shapes (no `event_id` / with
  `event_id` and `failure`). Both are existing shapes; a client that handles the events reads handles both.

## Migration Plan

None: no schema, config or data change. Rollback is reverting the commit. Existing queued jobs with a
non-canonical `event_dir` (if any were created) are not rewritten; they are rendered as before and are
visible only through `GET /jobs`.

## Open Questions

None that change the specs or tasks.
