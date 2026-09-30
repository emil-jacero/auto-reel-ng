## Why

GUI v1 slice **E** (HLD **§6 phase 8**, §4.10: schedule a render, watch it live, cancel it) puts a Render
button on every event and a live job feed in the shell. `jobs-client-contract` publishes the jobs routes'
shapes. Planning slice E against the code found two gaps in *what* those routes answer. Both let the web client show
or do something the rest of the system refuses. As with every previous screen, they are closed in the API
first, so slice E stays a pure `web/` change (Principle VIII).

1. **`POST /api/v1/jobs` enqueues an event whose output path another event claims.** The batch commands
   refuse every such event (**D-9**; `headless-cli` "Batch commands refuse colliding output paths"):
   `render`, `enqueue` and `adopt-renders` all run `_output_collisions` (`cli/commands.py:224-240`) over
   `render.find_output_collisions`, which compares paths case-insensitively. The route never runs it
   (`api/routes/jobs.py:52-110`). This is a real case in the dev library: `2024/2024-07-14 - Kalas` has been
   rendered to `2024/2024-07-14 - Kalas.mp4`, and `2024/2024-07-14 - kalas` resolves to the same file on
   the case-insensitive archive filesystem. `auto-reel enqueue` refuses both events. A Render click on
   `kalas` would queue a job whose render overwrites the other event's movie. This is exactly the silent
   data loss D-9 exists to prevent, and it would reach the screen that makes rendering one click away. Once
   the route refuses it with a 409, the client must also be able to tell that refusal apart from "a job is
   already active", which is a 409 too. Slice E answers the two differently: it attaches to the running job
   in one case, and tells the operator to fix `reel.yaml` in the other.
2. **The jobs views show every project in the database.** `GET /api/v1/jobs` and the WebSocket hub both
   list jobs through `JobStore.list_by_status`, which has no project filter (`api/routes/jobs.py:113-124`,
   `api/ws.py:253-261`, `persistence/job_store.py:249-253`). `GET /jobs/{id}` and cancel accept any id.
   The events reads, meanwhile, report each event's latest job *for the served project only*
   (`JobStore.latest_by_project`, `api/events_read.py:163,381`). One database holding several projects is
   ordinary. `DATABASE_URL` comes from the environment, then `config.yaml`, then one built-in dev default
   (`persistence/config.py:27-45`), so every project without its own setting shares one database. The dev
   library script already filters the store's listing by project by hand
   (`scripts/make_dev_library.py:126-131`), and it leaves a queued `2024/Blandat` job in every library it
   builds. The service is built for exactly one project root (api-service design **D-A1**,
   `ApiSettings.project_root`), and a job's `event_dir` is root-relative (**D-A2**), so it is unique only
   within its project. The shell's "2 rendering · 1 queued" indicator would therefore count other projects'
   jobs, and the list would show another library's `2024/Blandat` progress against this library's row.

## What Changes

- **`POST /api/v1/jobs` refuses an event whose output path is shared** with another event of the served
  project:
  - It answers **409** with a problem body that names the shared path, the other claimants as event ids
    in a new `claimed_by` list, and the fix (a distinct title or location in `reel.yaml`).
  - The refusal holds with and without `force`, and whether the event is fresh or stale.
  - Nothing is written: no job row, no manifest, no file.
  - The rule is the CLI's rule, run through the same engine functions (`render.output_relpath` and
    `render.find_output_collisions`) over the served project's events.
  - An event that cannot be read, or that has no real date and title, claims no path.
- **"Jobs lifecycle over REST" is corrected where the collision check changes it:** a forced request always
  enqueues *unless the output-collision check refuses it*, and every 409 of `POST /api/v1/jobs` carries
  `conflict`. Nothing else in `jobs-client-contract`'s text changes.
- **Every 409 from `POST /api/v1/jobs` says which conflict it is.** A new `conflict` problem field holds a
  value from a closed, published enumeration `EnqueueConflict`: `active_job` or `output_collision`. The
  existing active-job 409 carries `conflict: active_job` next to its `job_id` from `jobs-client-contract`.
- **A project walk that fails is a 502 on enqueue**, in the events list's shape. The API never enqueues
  an event whose collision it could not check.
- **The jobs surface is scoped to the served project.** This covers:
  - `GET /api/v1/jobs`, with or without a status filter
  - the WebSocket snapshot and every delta, including the one-time delta `jobs-client-contract` adds for a
    job that became terminal since the previous poll without any earlier frame carrying it
  - `GET /api/v1/jobs/{id}` and `POST /api/v1/jobs/{id}/cancel`

  These cover only jobs whose project root is the served root. Another project's job is answered as an
  unknown id (404), and a cancel changes nothing. The worker queue stays shared: claiming is not scoped.
- **The job store can list by status, and list finished jobs, within one project.** Both
  `list_by_status` and `jobs-client-contract`'s `list_finished_since` gain an optional project root.
  Callers that pass no project, such as the CLI's `jobs list`, are unchanged.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.** No client code reads these
  responses yet.

## Non-goals

- **No list-level collision flag in `GET /api/v1/events`.** A collision is reported when the event is
  enqueued, not flagged on its row. That is a follow-up.
- **No CLI change.** `render`, `enqueue` and `adopt-renders` keep their messages, selection and exit codes
  byte for byte. `jobs list|show|cancel` stay database-wide. Their `<root>` argument only selects the
  database today (`cli/commands.py:744-816`).
- **No worker change.** `claim_next` stays global: the queue is shared by design.
- **No new vocabulary beyond the conflict kind.** No output path field on `JobOut`, and no ETA.
- **No `web/` code.** That is slice E, `render-progress-screen`.

**Follow-ups, deliberately not in this change, and what each leaves as it is:**

- **Canonical event ids on enqueue.** `resolve_event_dir` accepts any directory under the root, spelled any
  way, and the route stores the id verbatim as `event_dir`.
  - *Consequence:* `2024/./Blandat` or `2024/Blandat/` gets a job whose `event_dir` differs from the
    list's `2024/Blandat`. It bypasses the one-active-job index (a duplicate render of one event is
    possible), and it never matches the GUI's `event_dir === event_id`. `2024` or `.` is accepted as an
    event. The collision check itself is not fooled: its keys are resolved folders.
  - *Why it is safe for now:* the GUI only sends ids that `GET /api/v1/events` returned.
- **A published 503 on the jobs routes.** A database failure on `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`
  or cancel stays an unshaped 500, where the events reads answer 503 with `check: database`.
  - *Consequence:* a client can only say "the service failed", not "the database is down".
    `render-progress-screen` handles a bare 500.
- **One engine function for claimant selection, shared by the CLI and the API.** Today "load, require
  processable, a failure claims nothing" is composed twice (`cli/_checked_document`, `api/_output_claim`)
  from the same engine calls, while the rule itself (`render.output_relpath`, `render.find_output_collisions`)
  is already one engine function both call.
  - *Consequence:* the two differ on `OSError`. A sibling folder that cannot be listed (with or without a
    `reel.yaml`, which such a folder hides) aborts `auto-reel enqueue` with a traceback, while the API
    skips it as a claimant. If that folder owns a
    path, a `POST` for its twin is enqueued and its render replaces the owner's movie (design, Risks).
- **A claim-time collision recheck in the worker.**
  - *Consequence:* a job queued before its twin appeared still renders, and can overwrite the twin's movie.
    The CLI has the same gap today. This change stops new jobs only.
- **`POST /api/v1/jobs` on its own unprocessable or unparseable event.**
  - *Consequence:* an unprocessable event (`2024/2024-02-30 - Omöjligt datum`) is still enqueued and fails
    in the worker. An unparseable `reel.yaml` is still a bare 500 (`api/routes/jobs.py:73`), not the events
    reads' 502 with a failure kind.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - ADDED `Requirement: Enqueue refuses an event whose output path another event claims`: the collision
    409, the conflict vocabulary on every enqueue 409, and the 502 on a failed walk.
  - ADDED `Requirement: The jobs surface is scoped to the served project`: list, detail, cancel and
    WebSocket.
  - MODIFIED `Requirement: Jobs lifecycle over REST`, re-based on `jobs-client-contract`'s archived text
    (task 1.1). It changes only two things: a forced request always enqueues unless the output-collision
    check refuses it, and every 409 of `POST /api/v1/jobs` carries `conflict`.
  - "WebSocket live job updates" is not modified. The scoping requirement narrows it, including its
    terminal-since-previous-poll delta.
- `job-store`: MODIFIED `Requirement: Query jobs`, re-based on `jobs-client-contract`'s archived text (which
  adds the finished-since read): the status listing and the finished-since read can each be narrowed to one
  project root.

## Impact

- **Dependencies (gate):** `jobs-client-contract` must be archived on `main` first. This change builds on
  its `job_id` problem field, its published `POST /jobs` responses, its reworked cancel route, its archived
  "Jobs lifecycle over REST" text and its hub query for jobs that became terminal since the previous poll.
- **Packages:**
  - `persistence/`: `job_store.list_by_status` and `job_store.list_finished_since` gain a keyword-only
    `project_root` filter.
  - `api/`:
    - `events_read.py`: the output-claim walk over the served project.
    - `routes/jobs.py`: the collision 409, the `conflict` field, the 502, the project scope on list,
      detail and cancel, and the `502` in `responses=`.
    - `ws.py`: the hub is bound to the served project root, for its active snapshot and for its
      terminal-since-previous-poll query.
    - `app.py`: passes that root to the hub.
    - `schemas.py`: `EnqueueConflict`, `ProblemOut.conflict` and `ProblemOut.claimed_by`.
  - `render/` is not changed: the rule already lives there.
  - `cli/` is not changed.
  - Regenerated `web/` artifacts. `README.md` and the HLD (D-9, §4.9) are updated.
- **CLI vs API (Principle V):** the collision rule (`render.output_relpath` and
  `render.find_output_collisions`) is the engine's, and both clients call it.
  - `auto-reel enqueue <root>` refuses the same events the API refuses for that root.
  - Which events claim a path is composed in each client from the same engine loader and rule
    (`load_event_document` and `require_processable`). The API skips a sibling that raises `OSError`,
    where the CLI aborts its run. Lifting that selection into one engine function is a follow-up (Non-goals,
    follow-ups), because it would add `cli/` and an engine package to this change.
  - Project scoping is a store query that the CLI can also call. The API uses it because it serves exactly
    one project (`ApiSettings.project_root`).
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change. **No Alembic migration** (a query filter only), and
  no rescan.
- **Wire:**
  - `POST /jobs` for a colliding event changes from 201 or 200 to 409.
  - A 409 gains `conflict`.
  - A failed walk on enqueue is a 502.
  - Other projects' jobs disappear from the list and the WebSocket, and answer 404 by id.
  - Every other response is unchanged.
- **Runtime dependencies:** none.
- **Size (Principle VIII):**
  - one store filter, on two listings
  - one read-model helper
  - one route guard
  - one enumeration with two problem fields
  - one hub parameter, applied to both hub queries
  - two capability deltas, two packages (`persistence/`, `api/`), 10 tasks
