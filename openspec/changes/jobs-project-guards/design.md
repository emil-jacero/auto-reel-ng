## Context

See proposal.md, "Why". This change was written against `main` at `541c44c`, before `jobs-client-contract`
(C2) landed. Task 1.1 re-read every line number below against the code as C2 left it (C2 archived), and
corrected the ones C2 moved in `api/`, `persistence/` and the tests. The `cli/`, `render/`, `event/` and
`reel/` references are unchanged: C2 did not edit those packages.

**The collision rule already lives in the engine, and the CLI only composes it:**
- `render/orchestrator.py:125-160` holds the whole rule:
  - `output_relpath(metadata)` gives `<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`, or the bare name
    when the event is undated.
  - `_collision_key` applies NFC normalization, then `casefold`.
  - `find_output_collisions(claims)` is pure and generic over its keys. It maps each colliding key to the
    other keys.
- `cli/commands.py:224-240`: `_output_collisions(metadata_by_event)` is two lines of composition, a
  `{key: output_relpath(md)}` map passed to `find_output_collisions`, plus the CLI's own message:
  `output path <p> is also claimed by <folder names>; set a distinct title or location in reel.yaml`.
- **Who can claim a path in the CLI:**
  - `enqueue` and `adopt-renders` use the events that `_checked_documents` accepts
    (`cli/commands.py:124-155`): `load_or_seed` plus `require_processable`. A failing event "can never
    claim a path" (`commands.py:629`, `881`).
  - `render` uses the candidates plus the fresh events, after its staleness filter (`commands.py:193-195`).
  - In every case the set is the selected events: the layout walk, narrowed by `--years`.
  - "Failing" means a `ReelError` only: `_checked_document` catches `EventMetadataError` and `ReelError`
    (`commands.py:133-139`). An unreadable `reel.yaml` is a `ReelParseError` (`reel/parser.py:41-43`), so it
    is covered. An `OSError` is not: an event folder that cannot be listed raises from `seed_document`
    (a folder that cannot be searched hides its `reel.yaml` from the loader's existence check, so this
    holds whether or not it has one), and `cli/main.py:267-274` catches only `EngineError`,
    `FileNotFoundError` and `NotADirectoryError`. A `PermissionError` therefore aborts the whole `enqueue`
    run with a traceback, and nothing is enqueued.
- **The API side:**
  - `load_or_seed` is `load_event_document` (`cli/adoption.py:65-67`, `event/metadata.py:66-69`), the loader
    the events reads already use (`api/events_read.py:121-122`).
  - `_list_event_refs(settings)` (`events_read.py:103-106`) is the same layout walk from `settings.walk_root`.
    The events list uses it, and its failures (`ReelError`, `LayoutError`, `OSError`) are the list's
    scan-failure 502 (`api/routes/events.py:128-130`).

**`POST /api/v1/jobs` as C2 left it** (`api/routes/jobs.py:34-110`):
1. It resolves the event. An unknown event is a 404.
2. It checks for an active job. One found is a 409 `conflict(..., job_id=...)` (C2 renamed the untyped
   `id=` to `job_id`).
3. It loads the event (`load_or_seed`), computes the fingerprint and runs the gate. A fresh event is the
   200 `FreshResult`.
4. It calls C2's `store.submit`, which answers 201 when it created the job. When the insertion falls back
   to an existing job (the race), it is C2's second 409, with that job's `job_id`.

No collision check runs. The event's own document is loaded without `require_processable`.

**The project boundary in the store and the service:**
- `Job.project_root` is a nullable `Text` column (`persistence/models.py:70`). Every writer sets it:
  - the CLI `enqueue` (`commands.py:626`, the resolved root)
  - the API (`jobs.py:63`, `str(settings.project_root)`, which `serve` resolves at `commands.py:581`)
  - the dev library script
- The events reads already scope to it: `latest_by_project(str(settings.project_root))`
  (`events_read.py:163,381`).
- The jobs routes and the hub do not:
  - `list_by_status(status)` has no project filter (`job_store.py:249-253`), and neither has C2's
    `list_finished_since(since, *, overlap)` (`job_store.py:255-271`).
  - `GET /jobs` (`jobs.py:113-124`) and the hub's `_fetch_active_snapshot` (`ws.py:253-261`) call the
    first; the hub's `_fetch_finished` (`ws.py:268-271`, at poller start and on every tick) calls the
    second.
  - `GET /jobs/{id}` and cancel take any id (`jobs.py:127-151`).
- `claim_next` is global on purpose (`job_store.py:175`): the worker queue is shared.
- The hub is built in `create_app` with only the store and the poll interval (`api/app.py:68`).
- `tests/test_api_ws_hub.py:55-85` has a `FakeStore` with `list_by_status(status)` and
  `list_finished_since(since, *, overlap)`, one test replaces `list_by_status` with a
  `lambda status: ...` (`:366`), and there are thirteen direct `JobsHub(store, poll_interval=...)`
  constructions (`:125-440`). The hub's new keyword call breaks all three, so task 4.2 extends them.
- C2 adds tests this change meets:
  - C2 task 3.4 adds an OpenAPI case asserting that `POST /jobs` declares *exactly* 200, 404 and 409
    besides 201 and 422. Task 3.3 here adds `502` to it.
  - C2 task 3.2 adds a stale-read cancel test: it keeps a `queued` copy from `store.get`, lets the job be
    claimed, then monkeypatches the app's `store.get` to return that stale copy, and the cancel must still
    answer `flagged-running` with status `running`. It passes unchanged with `_served_job` (task 4.1),
    because the stale copy carries the served project root.
  - C2 task 3.3 adds hub tests for the `cancel_requested` delta and for jobs that became terminal since
    the previous tick, and gives the hub test's `FakeStore` a `list_finished_since(since, *, overlap)`.
    Their `JobsHub(...)` calls gain `project_root=`, and both `FakeStore` listings gain the keyword
    (task 4.2).

## Goals / Non-Goals

**Goals:**

- For any event, `POST /api/v1/jobs` refuses an output collision exactly when `auto-reel enqueue <root>`
  would, through the same engine functions. The one difference is a sibling that raises `OSError`. The CLI
  aborts its whole run on it, while the API skips it as a claimant (see "Which events claim a path").
- A client can tell the two enqueue conflicts apart from the published type alone.
- Every jobs view the service offers agrees with the events reads about which project it serves.

**Non-Goals:**

- A new engine function or any CLI edit. The rule is already shared (see the first decision).
- Scoping the CLI's `jobs` commands, or the worker's claim.
- Collision flags on the events list.
- The follow-ups the proposal lists under Non-goals, each with its consequence: canonical event ids on
  enqueue, a published 503 on the jobs routes, one engine function for claimant selection, a claim-time
  collision recheck in the worker, and the route's handling of its *own* unprocessable or unparseable
  event.

## Research & Decisions

### Where the shared rule lives

**Context**: The brief asks for the collision rule to move into the engine package that owns output paths,
so that the CLI and the API call the same function and the CLI stays byte-identical.

**Explored**:
- `render/orchestrator.py:125-160` already holds `output_relpath` and `find_output_collisions`, both
  exported from `render/__init__.py` (imports at `:48-50`, `__all__` at `:76-77`). Tests for them are in
  `tests/test_render.py:731-760`.
- Two options were considered:
  - **(a)** Add `render.output_collisions(metadata_by_key)` (the `{k: output_relpath(md)}` composition) and
    point `cli/_output_collisions` at it.
  - **(b)** Have the API call the two existing engine functions, exactly as the CLI does.

**Decision**: (b). The API builds its claims with `render.output_relpath` and groups them with
`render.find_output_collisions`. `cli/` and `render/` are not edited.

**Rationale**:
- The rule, meaning the path shape and the case- and normalization-insensitive key, is already one engine
  function that both clients call.
- The part that stays duplicated is the claimant selection: load the document, require it processable,
  and let a failure claim nothing. It is composed twice from the same engine calls
  (`load_event_document` and `require_processable`), in `cli/_checked_document` and in the API's
  `_output_claim` below. The two differ on purpose on `OSError` (see "Which events claim a path").
  Lifting the selection into one engine function would touch `cli/` and `render/` or `event/`, so it is left
  to a follow-up and recorded in Risks.
- (a) would move a one-line dict comprehension into a third package. That is a speculative abstraction
  (Principle VII), and it would put `cli/` and `render/` in a change whose behaviour is API-only
  (Principle VIII: ≤ 2 packages).
- Leaving `cli/` untouched is the strongest guarantee that the CLI's messages and exit codes stay identical.

### Which events claim a path

**Context**: The CLI checks the events it selected. The service has no selection. It serves one project,
whose events are exactly what `GET /api/v1/events` lists (api-service "Factory serves a configured
project root").

**Decision**:
- A read-model helper in `api/events_read.py` walks the configured layout, as the events list does.
- Each event gets a claim with the loader and processability rule the CLI and the events reads share.
- The named event is always added, even when the walk does not reach it. `resolve_event_dir` accepts any
  folder under the root, and a folder outside `input` still claims its own path.

```python
@dataclass(frozen=True)
class OutputCollision:
    """The named event's output path and the other events that claim it."""

    output_path: PurePosixPath          # relative to the output directory
    claimed_by: Tuple[str, ...]         # the other claimants' event ids, sorted


def _output_claim(event_dir: Path, order: ClipOrder, today: DateValue) -> Optional[PurePosixPath]:
    """The event's output path, or None when it fails on its own and claims nothing."""
    try:
        document, _seeded = load_event_document(event_dir, order=order)
        require_processable(event_dir, document.metadata, today=today)
    except (ReelError, OSError):        # EventMetadataError is a ReelError
        return None
    return output_relpath(document.metadata)


def output_collision(
    settings: ApiSettings, event_dir: Path, *, today: DateValue
) -> Optional[OutputCollision]:
    """The collision ``event_dir`` is part of, over every event of the served project.

    The layout walk's own failure propagates: the caller must not enqueue unchecked.
    """
    event_dir = event_dir.resolve()                 # a no-op for resolve_event_dir's result
    target = _output_claim(event_dir, settings.clip_order, today)
    if target is None:
        return None
    claims: Dict[Path, PurePosixPath] = {event_dir: target}
    ids: Dict[Path, str] = {}
    for ref in _list_event_refs(settings):          # LayoutError / OSError / ReelError propagate
        if ref.event_dir.resolve() == event_dir:
            continue                                # the named event itself, however spelled
        claim = _output_claim(ref.event_dir, settings.clip_order, today)
        if claim is not None:
            claims[ref.event_dir] = claim           # keyed by the walk's own path, as the CLI
            ids[ref.event_dir] = event_id_for(settings, ref.event_dir)   # the list's own id
    others = find_output_collisions(claims).get(event_dir, ())
    if not others:
        return None
    # Every other claimant came from the walk, so each one has an id.
    return OutputCollision(output_path=target, claimed_by=tuple(sorted(ids[o] for o in others)))
```

**Rationale**:
- **Keys:** a walked event that resolves to the named event's folder is the named event itself, however
  the walk spells it, so it never collides with itself. This holds even when `settings.project_root` was
  built unresolved, as tests build it. Every other walked event claims under its own walk path, as the
  CLI's `_output_collisions` keys it and as each events-list row stands on its own.
  - *Corrected during apply (task 3.2):* the first draft keyed every claimant by its resolved folder. Two
    list rows aliasing one folder under different names (an in-project symlink, such as
    `2024/2024-07-20 - Fest` pointing at `2024/2024-07-14 - Kalas`) then shared one key, and the one
    walked later silently replaced the other's claim. A `POST` for the case-only twin `2024-07-14 - kalas`
    found no collision and would have been enqueued over `Kalas.mp4`, where `auto-reel enqueue` refuses
    it. Keying by the walk's path keeps both claims.
- **Ids:** each id is `event_id_for` on the walk's unresolved path, the exact string `GET /api/v1/events`
  lists and a client links to. Deriving it from the resolved key would be wrong in two ways:
  - A symlinked year or event folder that points outside the root would make `relative_to` raise
    `ValueError`, a 500 on every enqueue in the project.
  - A symlink inside the root would get its target's id rather than the list's.
- **What claims a path:** the loader and the rule are those of `_checked_document`, so an event that the
  CLI reports as `ERROR` (a `ReelError`: unparseable or unreadable `reel.yaml`, or no real date or title)
  claims nothing here either. Both the headless-cli spec and the events list's error row already describe
  such an event as failing on its own.
- **`OSError` differs from the CLI, deliberately:** a sibling folder without `reel.yaml` that cannot be
  listed makes the CLI abort its whole run (see Context). Here it claims nothing and the check goes on. It
  is the events list's per-event isolation (`unreadable_disk` row) and Principle I's one tolerated
  softening. Aborting would let one unreadable folder block every Render click in the project. The residual
  risk is in Risks.
- **`today`:** it is a parameter, as in `apply_editorial_write`, so tests are deterministic.
- **Cost:** a full project walk for each enqueue is one `reel.yaml` parse or folder seed per event. That
  is less than the `GET /events` the client already issues to show its Render button, because the walk
  here does no reconcile and no fingerprint. See Risks.

### Order of the checks, and the answers

**Decision**: `create_job` runs the checks in this order, building on C2's version:

```python
event_dir = events_read.resolve_event_dir(settings, payload.event_id)             # 404
try:
    collision = events_read.output_collision(settings, event_dir, today=date.today())
except (ReelError, LayoutError, OSError) as exc:                                 # the list's 502
    return bad_gateway(f"event scan failed: {exc}")
if collision is not None:
    others = ", ".join(collision.claimed_by)
    return conflict(
        f"output path {collision.output_path} is also claimed by {others}; "
        "set a distinct title or location in reel.yaml",
        event_id=payload.event_id,
        conflict=EnqueueConflict.OUTPUT_COLLISION.value,
        claimed_by=list(collision.claimed_by),
    )
existing = store.active_job(project_root, payload.event_id)                      # C2's 409 …
#   … and C2's enqueue-race 409 both gain conflict=EnqueueConflict.ACTIVE_JOB.value
# gate → 200 FreshResult, else enqueue → 201 (unchanged)
```

`responses=` on `POST /jobs` gains `502: {"model": ProblemOut}`.

**Rationale**:
- **Collision first:** the CLI decides a collision before anything else. In `enqueue`, a refused event is
  never gated and never reported as "already queued" (`commands.py:631-639`). Doing the same here keeps
  the two clients' answers identical, and it protects a fresh event's movie
  (`2024-07-14 - Kalas`) instead of answering "fresh".
- **When an event both collides and has an active job:** the operator needs the collision more than a
  progress bar. The 409 is `output_collision` and carries no `job_id`. The job itself stays visible on the
  WebSocket and in the list's job cell. This can only happen to a job queued before its twin appeared (see
  Risks).
- **The detail:** it reuses the CLI's wording, with event ids in place of folder names. Ids are what the
  client links to, and folder names can repeat across years.
- **The 502:** a failed walk leaves the rule unevaluated. Enqueueing anyway would guess
  (Principle I).

### The conflict vocabulary and its owner

**Context**: The HLD (§4.10, the closed-vocabulary rule) says a closed set belongs to the layer that owns
the vocabulary.

**Explored**:
- The engine has no notion of "why an enqueue was refused": the store answers with a job id, and render
  answers with a collision map.
- The classification is the API's, just as `EventFailure` (the API's classification of engine errors)
  lives in `api/schemas.py:107-115`.

**Decision**: `class EnqueueConflict(StrEnum)` in `api/schemas.py`, with `ACTIVE_JOB = "active_job"` and
`OUTPUT_COLLISION = "output_collision"`. `ProblemOut` gains two fields:
- `conflict: Optional[EnqueueConflict] = None`
- `claimed_by: Optional[List[str]] = None`

Both have field comments in the style of `failure`. The names are fixed by the brief.

**Rationale**:
- One published enumeration gives the client an exhaustive union.
- `claimed_by` is a list because a three-way collision is possible (`tests/test_render.py:753-758`).
- An `output_path` field is not added. The detail names the path, and no client needs it as data yet
  (Principle VII).

### Project scoping at the store

**Context**: The service must list the jobs of one project.

**Explored**:
- **(a)** Filter in `api/` after a global `list_by_status`. This touches no second package, but it pulls
  every project's history across the connection on each `GET /jobs`, and it puts a query in the API
  layer.
- **(b)** A keyword-only filter on the store's existing listing.

**Decision**: (b), on both of the store's listings that a jobs view reads.

```python
def list_by_status(self, status: JobStatus, *, project_root: Optional[str] = None) -> list[Job]:
    """List jobs with ``status`` (optionally of one project), ordered by ``created_at`` ascending."""
    stmt = select(Job).where(Job.status == status)
    if project_root is not None:
        stmt = stmt.where(Job.project_root == project_root)
    ...

def list_finished_since(self, since: Optional[datetime], *, overlap: timedelta,
                        project_root: Optional[str] = None) -> FinishedJobs:   # C2's read, narrowed
    ...
```

**Rationale**:
- `latest_by_project` already filters the same column in SQL, so the scoping is one idea in one layer.
- A `NULL` root never equals a string, so legacy rows without a root are excluded without a special case.
- The existing callers (the CLI's `jobs list`, the dev library script and the tests) pass nothing, and
  keep global results.
- No index is added. The status index narrows first, and the jobs table is small.

### Scoping detail, cancel and the WebSocket

**Decision**:
- **Detail and cancel:** the routes call one helper, `_served_job(store, settings, job_id)`. It returns
  `store.get(job_id)` only when `job.project_root == str(settings.project_root)`, and `None` otherwise.
  - A foreign or unknown id then gets the same 404, with C2's `job_id` field.
  - The helper runs before cancel's store call. `project_root` is never updated after insert (no store
    verb writes it), so this read-then-act has no race.
  - The pre-read decides only *whether* the service may cancel the job. The outcome and status still come
    from C2's single `store.cancel` transaction, so C2's requirement that the outcome "SHALL NOT be derived
    from an earlier read" still holds. C2's stale-read test (C2 task 3.2) already proves it in a form the
    scope read does not break: the app's `store.get` returns a stale `queued` copy of a job the store holds
    as `running`, and the cancel must still answer `flagged-running`. `_served_job` reads that stale copy,
    finds the served root on it, and lets the cancel through, so the test passes unchanged.
- **The hub:** `JobsHub(job_store, *, project_root: str, poll_interval, queue_maxsize=...)`.
  - `_fetch_active_snapshot` passes `project_root=` to `list_by_status`, through `functools.partial` on
    the executor.
  - C2's `list_finished_since(since, *, overlap)`, the read of jobs that became terminal since the
    previous tick (round-2 rule 5: a job whose whole active life fell between two polls, such as
    `2024-10-05 - Trasig` failing at probe), gets the same keyword-only `project_root=`, both at poller
    start (the read that seeds `_terminal_sent`) and on every tick. Unscoped, it would send another
    project's short-lived job once, the leak this change closes for the snapshot. C2's design already
    names this seam ("C3 adds `project_root` to `list_finished_since` exactly as it does to
    `list_by_status`"). The watermark `as_of` is database time either way, so scoping changes no timing.
  - A vanished job is fetched by id only when it was in the scoped snapshot, so it needs no second check.
  - `create_app` passes `str(settings.project_root)`.
  - `project_root` is required, with no default. An unscoped hub would be a second code path
    (Principle VII), and a forgotten argument would silently widen the feed. So every `JobsHub(...)` in
    `tests/test_api_ws_hub.py` gains `project_root="/proj"`, which is `FakeJob`'s default root. That covers
    all thirteen calls C2 left there.
  - The hub test's `FakeStore.list_by_status` and `FakeStore.list_finished_since` gain the keyword and
    filter on it.

**Rationale**:
- A foreign job looks like an unknown one, so the service reveals nothing about other projects.
- A client cannot cancel another library's render by guessing or copying an id.
- The WS diff runs over the scoped snapshot, and the terminal-since-previous-tick query is scoped the same
  way, so a foreign job can never produce a delta, including its terminal one.

### Spec deltas: what is modified, what is added

**Context**: C2 modifies api-service "Jobs lifecycle over REST" and "WebSocket live job updates", and
job-store "Query jobs". A MODIFIED block replaces a requirement's whole text at archive time. C3 archives
after C2 (its gate), so a MODIFIED block of C3 can be re-based on C2's archived text without losing C2's
edit.

**Explored**: ADDED-only was the first draft. It left C2's sentence "a forced request always enqueues"
standing beside C3's "`force` SHALL NOT override the check" in one archived spec, a contradiction a reader
would have to resolve by precedence.

**Decision** (supervisor round-2 rule 6):
- MODIFY api-service "Jobs lifecycle over REST", re-based in task 1.1 on C2's archived text, changing only:
  - "a forced request always enqueues" → "… unless the output-collision check refuses it"
  - every 409 of `POST /api/v1/jobs` carries `conflict` (`active_job` on the active-job 409, found
    beforehand or at insertion; `output_collision` on the collision refusal, which is checked first). The
    two active-job scenarios name `conflict`, and the force scenario states that Midsommar collides with
    nothing.
- ADD "Enqueue refuses an event whose output path another event claims" (the rule, the vocabulary, the
  502) and "The jobs surface is scoped to the served project" (which says that "the jobs" in the other
  requirements means the served project's jobs, including the WebSocket's terminal-since-previous-tick
  delta).
- Do not modify "WebSocket live job updates": the scoping requirement narrows it without changing its
  text.
- MODIFY job-store's "Query jobs", re-based in task 1.1 on C2's archived text (C2 modifies it to add the
  finished-since read): both the status listing and the finished-since read accept an optional project
  root, and nothing else in C2's text changes.

**Rationale**: the archived spec then says one thing about force and one thing about 409s. The capability
count stays two (api-service, job-store).

## Failure behavior and idempotency

- **404** (an unknown event or job, or another project's job): nothing is written or changed.
- **409 `output_collision`:** nothing is written: no row, no manifest, and the existing movie is untouched.
  Re-posting gives the same 409 until an event's title, date or location changes in `reel.yaml`. A forced
  request is refused the same way. After the fix, the next `POST` is gated and enqueued as usual.
- **409 `active_job`:** unchanged, apart from the new field.
- **502** (the walk failed): nothing is enqueued. A retry succeeds once the folder is readable.
- **A sibling that breaks between walks** is skipped as a claimant on that request. This is per-event
  isolation, as in the list.
- **A worker restart mid-render:** unaffected. This change touches neither the claim nor the render, and a
  requeued job keeps its project root.
- **Rendered output:** no `RENDER_GRAPH_VERSION` bump and no fingerprint change. No migration: the change
  only adds a filter on an existing column.

## Risks / Trade-offs

- **[A job queued before its twin appeared still renders]** If `2024-07-14 - kalas` is added while a job for
  `Kalas` is queued, the worker renders `Kalas` unchecked. → The same is true of the CLI today. A
  claim-time recheck belongs to the scheduler, and it is a named follow-up (proposal, Non-goals). This
  change stops new jobs only.
- **[A full walk on every enqueue]** The MOL archive has several hundred events, and each enqueue walks all
  of them. → The cost is below that of the `GET /events` the client already issues. Measure one
  `POST /jobs` against the archive during apply (task 3.3). If it is too slow, a later change can cache
  the claims per request batch, rather than weakening the rule.
  - *Measured during apply (task 3.3):* the MOL archive was not mounted, so one `output_collision` call
    was timed read-only against the dev library (11 walked events, local disk; library tree unchanged):
    median 8.8 ms for `2024/2024-07-14 - kalas` (a collision) and 7.8 ms for
    `2024/2024-06-27 - Grillning med grannar` (none), over 25 runs each, against a median 12.9 ms for the
    events list's own read (`list_events`, 10 runs). That is about 0.7 ms per walked event. MOL's
    141 sorted events on a USB NTFS drive are not measured: expect roughly 0.1 s from the same
    per-event cost, plus that drive's slower directory reads.
- **[The target's own failures keep today's behaviour]** An unprocessable event (`2024-02-30 - Omöjligt
  datum`) claims no path, so the collision check lets it through to today's path, which enqueues it and
  lets the worker fail it. An unparseable `reel.yaml` is still a bare 500 from `load_or_seed`
  (`jobs.py:73`). → Out of scope. A named follow-up (proposal, Non-goals).
- **[An unlistable sibling is skipped, where the CLI aborts]** If `2024-07-14 - Kalas` became unlistable,
  a `POST` for `2024-07-14 - kalas` would find no twin and enqueue it. Its render would then replace
  `Kalas.mp4`. `auto-reel enqueue` would instead crash before enqueuing anything. → The window is narrow:
  the owner's folder itself must be unlistable (an unreadable `reel.yaml` in a listable folder is a
  `ReelParseError`, which the CLI skips just the same). *Corrected during apply:* the first draft also
  required the folder to have no `reel.yaml`, but a folder that cannot be searched hides its `reel.yaml`
  from the loader, which then seeds and fails to list it; a mode-000 folder holding a `reel.yaml` raises
  `PermissionError` from the shared loader. The events list shows that folder as an
  `unreadable_disk` row. Parity belongs in a follow-up that moves the claimant selection into one engine
  function, with `OSError` as a per-event failure in both clients (proposal, Non-goals).
- **[Claimant selection composed twice]** `cli/_checked_document` and `api/_output_claim` both compose
  `load_event_document` and `require_processable`, so they could drift. → Tests pin both sides to the same
  dev-library events: task 3.3 runs `tests/test_cli_output_collisions.py` and
  `test_enqueue_refuses_colliding_events` next to the API cases. The follow-up above removes the
  duplication.
- **[Project root spelling]** A root enqueued through a symlink and served through its target are two
  projects. → Both writers resolve the root. The CLI resolves it in `_project_context` (`commands.py:93`),
  and `serve` resolves it in `_resolve_project_root` (`commands.py:581`, called at `:833`) before
  `resolve_api_settings`, which itself keeps the path as given. This is the same equality the events reads'
  latest job already relies on.
- **[The CLI shows more than the service]** `auto-reel jobs list` stays database-wide. → This is
  intentional: it is the operator's view of the shared queue. The service is a single-project view. The
  README says so.

## Migration Plan

- Implement after C2 is archived on `main`, and re-read its routes first (task 1.1).
- Regenerate `web/openapi.json` and `web/src/api/schema.d.ts`. There is no data migration.
- Rollback means reverting the route guard, the helper, the enumeration and fields, the store filter and
  the hub parameter.

## Open Questions

The supervisor decided these as follow-ups, not this change. The proposal's Non-goals states each one's
consequence:

- Canonical event ids on `POST /api/v1/jobs` (refuse an `event_id` that is not `event_id_for` of a walked
  event). Adopting it here would also change task 3.2's "folder outside `input` still collides" case.
- A published 503 (`check: database`) on the four jobs routes.
- One engine function for claimant selection ("load, require processable, a failure claims nothing"),
  called by both `cli/` and `api/`, with `OSError` a per-event failure in both.
- A claim-time output-collision recheck in the worker.
- `POST /api/v1/jobs` answering its own unprocessable event as the CLI's `ERROR`, and an unparseable
  `reel.yaml` as the events reads' 502, instead of enqueueing or a 500.

Still open, deferrable, and not affecting this change's specs or tasks:

- Should `auto-reel jobs list|show|cancel <root>` scope to `<root>`, to match the service? Kept
  database-wide: it is the operator's view of the shared queue.
