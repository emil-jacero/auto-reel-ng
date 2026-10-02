## MODIFIED Requirements

### Requirement: Jobs lifecycle over REST
The service SHALL expose the job store thinly: `POST /api/v1/jobs` enqueues an event (device optional,
default `auto`; `force` optional, default false) after applying the staleness gate — returning 201 with
the job on creation, **409 with the existing job's id** when an active job already exists for the event,
and a distinct **"fresh — not enqueued" outcome** (200 with the fresh verdict and its manifest reference)
when the event is fresh and `force` is false; a forced request always enqueues unless the
output-collision check or the missing-clip check refuses it. The enqueued job carries the event's
fingerprint and the force flag.
`GET /api/v1/jobs` lists jobs (filterable by status); `GET /api/v1/jobs/{id}` returns one job's detail
(status, progress, device, worker, force, fingerprint, timestamps, error, requeue count);
`POST /api/v1/jobs/{id}/cancel` invokes the store's cancel request (flag a running job, cancel a queued one
directly, no-op reported for terminal jobs). The API MUST NOT transition job status itself.

A 201 SHALL mean that this request created the job. Whether a job was created SHALL be decided by the store
at the moment of insertion, not by an earlier read: an enqueue that finds, at insertion, an active job
created by a concurrent request SHALL answer 409 with that job's id, exactly like an enqueue that finds it
beforehand, and never 201.

The job id a problem body is about SHALL be carried in a typed `job_id` field of the shared problem body:
the active job's id on the enqueue 409, and the requested id on the 404 of the job detail and of cancel. The
404 of an enqueue for an unknown event SHALL name the event in `event_id`.

Every 409 that `POST /api/v1/jobs` returns SHALL carry the conflict kind in a `conflict` field, drawn from
the published enumeration of "Enqueue refuses an event whose output path another event claims":
`active_job` on the active-job 409, whether the job was found beforehand or at insertion,
`output_collision` on that requirement's refusal, which is checked first, and `missing_clips` on the
refusal of "Enqueue refuses an event that plays a clip missing from disk".

A cancellation's reported outcome SHALL be the one the store applied in the same transaction that applied
it (see the job store's cancel request): `flagged-running`, `canceled-queued` or `no-op-terminal`, together
with the job's status after that transaction. It SHALL NOT be derived from an earlier read of the job.

A job's `event_dir` SHALL be the event's root-relative id: a job enqueued with an event id that the events
routes returned as `event_id` SHALL carry exactly that value as its `event_dir`, so a client matches jobs
to events by equality. The schema SHALL describe the field so.

The service's OpenAPI schema SHALL publish every one of these responses: for the enqueue, the 201 job, the
200 fresh result (whose `status` is the constant `fresh`), and the 404 and 409 problem bodies; for the job
detail and for cancel, the 404 problem body. Every published problem response SHALL use the shared problem
body shape.

#### Scenario: Enqueue over REST
- **WHEN** `POST /api/v1/jobs` names `2024/2024-06-27 - Grillning med grannar`, whose title was edited
  after its last render, and it has no active job
- **THEN** a `queued` job row exists carrying the event's fingerprint, and the response is 201 with the
  job, whose `event_dir` is `2024/2024-06-27 - Grillning med grannar`

#### Scenario: Fresh event is not enqueued
- **WHEN** `POST /api/v1/jobs` names the rendered, unchanged `2023/2023-06-23 - Midsommar - Dalarna`
  without `force`
- **THEN** no job is created, and the response is 200 with `status` `fresh`, the event id, its fingerprint
  and its manifest reference

#### Scenario: Force enqueues a fresh event
- **WHEN** `POST /api/v1/jobs` names `2023/2023-06-23 - Midsommar - Dalarna`, whose output path no other
  event claims, with `"force": true`
- **THEN** a `queued` job with `force = true` is created and the response is 201

#### Scenario: Duplicate enqueue is a visible conflict
- **WHEN** `POST /api/v1/jobs` names `2024/Blandat`, which already has a `queued` job that no worker has
  claimed
- **THEN** the response is 409 with `conflict` `active_job` whose `job_id` is that queued job's id, and no
  new row is inserted

#### Scenario: An enqueue that loses a race is a conflict, not a creation
- **WHEN** two `POST /api/v1/jobs` requests for `2024/2024-06-27 - Grillning med grannar` both pass the
  active-job check before either inserts
- **THEN** exactly one response is 201, the other is 409 with `conflict` `active_job` whose `job_id` is the
  job the 201 returned, and one job row exists

#### Scenario: Unknown event on enqueue
- **WHEN** `POST /api/v1/jobs` names `2024/2024-12-24 - Finns inte`, which is not a directory under the
  project root
- **THEN** the response is 404 with the shared problem body naming the event in `event_id`

#### Scenario: Unknown job id
- **WHEN** `GET /api/v1/jobs/{id}` or `POST /api/v1/jobs/{id}/cancel` names a well-formed id that no job has
- **THEN** the response is 404 with the shared problem body whose `job_id` is the requested id, and no row
  changes

#### Scenario: Cancel a running job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the `running` job a worker is rendering for
  `2024/2024-08-02 - Badutflykt - Varberg`
- **THEN** the job's `cancel_requested` flag is set, its status is unchanged, and the response's outcome is
  `flagged-running` with status `running`

#### Scenario: Cancel a queued job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the unclaimed `queued` job of `2024/Blandat`
- **THEN** the job is `canceled`, and the response's outcome is `canceled-queued` with status `canceled`

#### Scenario: Cancel a finished job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the `failed` job of `2024/2024-10-05 - Trasig`
- **THEN** nothing changes, and the response's outcome is `no-op-terminal` with status `failed`

#### Scenario: A cancel racing a claim reports what it did
- **WHEN** a worker claims the `queued` job of `2024/Blandat` while a cancel request for it is in flight
- **THEN** the response's outcome and status agree: either `canceled-queued` with `canceled` (the cancel
  applied first, and the worker never claims the job), or `flagged-running` with `running` and
  `cancel_requested` set (the claim applied first); never `canceled-queued` with `running`

#### Scenario: The schema publishes the jobs responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the enqueue declares its 201 job, its 200 fresh result with `status` the required constant
  `fresh`, and its 404 and 409 problem bodies; the job detail and cancel each declare a 404 problem body;
  the problem body declares `job_id`; and the job's `event_dir` carries a description naming it the event id

### Requirement: Enqueue refuses an event whose output path another event claims
`POST /api/v1/jobs` SHALL apply the output-collision rule the batch commands apply (D-9). The event it names
SHALL be refused when its output path is also the output path of another event of the served project. Paths
SHALL be compared exactly as the batch commands compare them: case-insensitively and after Unicode
normalization. The claimants SHALL be every event the configured layout walks from the served root, the
same events the events list shows; the named event is one of them, because the route only accepts a listed
id and has already found it processable ("Enqueue names an event the events list shows and refuses one it
cannot process"). There is no selection: the check covers the whole project, as `auto-reel enqueue <root>`
does without `--years`. An event whose `reel.yaml` cannot be read, whose files cannot be listed, or whose
resolved metadata lacks a real date or a title (or carries a future date) SHALL claim no path. Such an
event fails on its own, as the events list's error row already reports. The service SHALL choose claimants by
the one rule the batch commands state ("headless-cli"), so that an event which cannot be read or listed
claims no path and is never the reason the check fails; the failure of a claimant other than the named
event SHALL NOT fail the check.

The check SHALL run after the named event is found processable, before the active-job check and before
the staleness gate. An event that collides and also has an active job SHALL therefore be answered as a
collision. `force` SHALL NOT override the check,
and it SHALL apply whether the event is fresh or stale. A refused event SHALL be answered with **409** and
a problem body that:

- names the event (`event_id`)
- carries the conflict kind `output_collision`
- lists the other claimants' event ids in `claimed_by`, sorted
- has a detail that states the shared output path, names the other claimants, and names the fix: a
  distinct title or location in `reel.yaml`

For a refused event nothing SHALL be written: no job row, no render manifest, and no change to an output
file that already exists at the shared path. A refusal SHALL NOT be resolved by renaming, suffixing or
skipping one side.

The `conflict` field that every 409 of `POST /api/v1/jobs` carries ("Jobs lifecycle over REST") SHALL take
its value from a closed set that the service's OpenAPI schema publishes as an enumeration:

- `active_job`: an active (`queued` or `running`) job already exists for the event. The body carries that
  job's id.
- `output_collision`: as above.
- `missing_clips`: the event plays a clip that is missing from disk (see "Enqueue refuses an event that
  plays a clip missing from disk"). The body carries the clips' identities in `missing`.

A client can therefore choose its reaction from the published type alone, never from the detail text.

When the project walk itself fails, the collision cannot be checked. The endpoint SHALL then answer with the
scan-failure 502 that the events list uses, and SHALL NOT enqueue. The schema SHALL publish that 502, and the
`conflict`, `claimed_by` and `missing` fields of the shared problem body.

#### Scenario: A case-only twin is refused
- **WHEN** `POST /api/v1/jobs` names `2024/2024-07-14 - kalas` in the dev library, whose folder name
  differs from `2024/2024-07-14 - Kalas` only in letter case, so that both events resolve to the output
  path `2024/2024-07-14 - Kalas.mp4` (a title taken from a folder name is title-cased)
- **THEN** the response is 409 with `conflict` `output_collision` and `claimed_by`
  `["2024/2024-07-14 - Kalas"]`
- **AND** its detail names `2024/2024-07-14 - Kalas.mp4` and says to set a distinct title or location in
  `reel.yaml`
- **AND** no job row is inserted

#### Scenario: A rendered event's movie is protected
- **WHEN** `POST /api/v1/jobs` names the fresh, already rendered `2024/2024-07-14 - Kalas` without `force`
- **THEN** the response is 409 with `conflict` `output_collision` naming `2024/2024-07-14 - kalas`, not the
  200 "fresh" outcome
- **AND** `2024/2024-07-14 - Kalas.mp4` in the output directory is byte-for-byte unchanged, and no job row
  or manifest is written

#### Scenario: Force does not override a collision
- **WHEN** `POST /api/v1/jobs` names `2024/2024-07-14 - kalas` with `"force": true`
- **THEN** the response is the same 409 `output_collision`, and no job row is inserted

#### Scenario: An event outside any collision enqueues as before
- **WHEN** `POST /api/v1/jobs` names the stale `2024/2024-06-27 - Grillning med grannar`, whose output path
  no other event claims
- **THEN** the response is 201 with the queued job, as before this change

#### Scenario: An event that fails on its own claims no path
- **WHEN** the dev library holds `2024/2024-02-30 - Omöjligt datum`, whose folder date is impossible, and
  an event whose `reel.yaml` cannot be parsed is added beside it
- **THEN** neither is counted as a claimant, the check does not fail because of them, and
  `POST /api/v1/jobs` for `2024/2024-06-27 - Grillning med grannar` answers 201

#### Scenario: A sibling that cannot be listed claims no path
- **WHEN** `2024/2024-07-14 - kalas`, which would collide with `2024/2024-07-14 - Kalas`, has mode `0000`,
  and `POST /api/v1/jobs` names `2024/2024-07-14 - Kalas`
- **THEN** the sibling claims no path, the check does not fail because of it, and the response is not an
  unshaped server error

#### Scenario: The CLI and the service refuse the same events
- **WHEN** `auto-reel enqueue <library>` runs over the dev library
- **THEN** it reports `2024-07-14 - Kalas` and `2024-07-14 - kalas` as colliding with each other, exactly as
  before this change
- **AND** `POST /api/v1/jobs` for either event answers 409 `output_collision`, whose `claimed_by` names the
  other

#### Scenario: A walk that fails refuses to enqueue
- **WHEN** a year folder of the served project cannot be listed while `POST /api/v1/jobs` names an event
  in another year
- **THEN** the response is the scan-failure 502 problem body, and no job row is inserted

#### Scenario: The schema publishes the conflict vocabulary
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the shared problem body's `conflict` field is the enumeration of exactly `active_job`,
  `output_collision` and `missing_clips`, and `claimed_by` and `missing` are lists of strings
- **AND** `POST /api/v1/jobs` declares its 409 and 502 responses in that shape

## ADDED Requirements

### Requirement: Enqueue refuses an event that plays a clip missing from disk
`POST /api/v1/jobs` SHALL refuse an event that plays a clip which is absent from disk. A clip is played
when `reel.yaml` references it in a chapter and does not exclude it. A referenced clip that `reel.yaml`
excludes is not played: a render skips it and never probes it, so its absence SHALL NOT refuse the
enqueue. A clip on disk that `reel.yaml` does not reference (NEW) or lists in `ignore` (IGNORED) is not
missing, and SHALL NOT refuse it. The refusal SHALL name exactly the clips that the event's detail
publishes as blocking a render (`blocking_missing`), so that a client's guard and the server's refusal
cannot disagree about which clips matter.

The check SHALL run after the output-collision check and the active-job check, and before the staleness
gate. An event that has an active job SHALL therefore be answered as an active job (a client follows that
job). `force` SHALL NOT override this check, because the render it would queue fails at probe, and the
staleness verdict SHALL NOT matter to it. A refused event SHALL be answered with **409** and a
problem body that:

- names the event (`event_id`)
- carries the conflict kind `missing_clips`
- lists the played, missing clips' identities in `missing`, sorted
- has a detail that names those clips and says to restore them, or remove them from `reel.yaml`

For a refused event nothing SHALL be written: no job row, no render manifest, no change to `reel.yaml`,
and no change to an output file that already exists. The service SHALL NOT remove the clips from
`reel.yaml` itself, as removing a clip is an editorial write that the operator makes.

The check reads the event's folder listing and its `reel.yaml`; it SHALL NOT probe any clip. A clip that is
present when the request is checked and gone when the worker probes it still fails that job at probe, with
the engine's own error, as before this change. When the event's folder cannot be listed, the clips cannot be
checked, and the endpoint SHALL answer with the scan-failure 502 that the events list uses and SHALL NOT
enqueue. The schema SHALL publish the 409 in the shared problem body shape, with `missing` a list of strings.

#### Scenario: A stale event that plays a missing clip is refused
- **WHEN** `POST /api/v1/jobs` names `2024/2024-09-01 - Sommarlov`, whose `reel.yaml` lists `s1710002.mp4`,
  `s1710004.mp4` and the absent `borttagen.mp4` without excluding any of them
- **THEN** the response is 409 with `conflict` `missing_clips`, `event_id` `2024/2024-09-01 - Sommarlov`
  and `missing` `["borttagen.mp4"]`
- **AND** its detail names `borttagen.mp4` and says to restore it or remove it from `reel.yaml`
- **AND** no job row is inserted and no manifest is written

#### Scenario: Force does not override the refusal
- **WHEN** `POST /api/v1/jobs` names `2024/2024-09-01 - Sommarlov` with `"force": true`
- **THEN** the response is the same 409 `missing_clips`, and no job row is inserted

#### Scenario: Several missing clips are all named, sorted
- **WHEN** `POST /api/v1/jobs` names an event whose `reel.yaml` plays two absent clips, `gone-b.mp4` in
  its root chapter and `Kväll/gone-a.mp4` in its `Kväll` chapter
- **THEN** the response is 409 `missing_clips` with `missing` `["Kväll/gone-a.mp4", "gone-b.mp4"]`

#### Scenario: A missing clip that reel.yaml excludes does not refuse
- **WHEN** `POST /api/v1/jobs` names an event whose `reel.yaml` lists the absent `borta.mp4` with
  `exclude: true` and no other absent clip
- **THEN** the response is 201 with the queued job, and the job carries the event's fingerprint

#### Scenario: Excluded and played missing clips together name only the played one
- **WHEN** `POST /api/v1/jobs` names an event whose `reel.yaml` lists the absent `borta.mp4` (excluded) and
  the absent `saknas.mp4` (not excluded)
- **THEN** the response is 409 `missing_clips` with `missing` `["saknas.mp4"]`

#### Scenario: A NEW or IGNORED clip is not missing
- **WHEN** `POST /api/v1/jobs` names `2024/2024-08-20 - Två kapitel - Tjörn`, which holds a NEW clip and an
  IGNORED clip on disk and references no absent clip
- **THEN** the response is 201, as before this change

#### Scenario: An active job is followed, not refused
- **WHEN** `2024/2024-09-01 - Sommarlov` already has a `queued` job and `POST /api/v1/jobs` names it
- **THEN** the response is 409 with `conflict` `active_job` and that job's id, not `missing_clips`

#### Scenario: A collision outranks the refusal
- **WHEN** `POST /api/v1/jobs` names an event that plays a missing clip and also shares its output path
  with another event
- **THEN** the response is 409 `output_collision`

#### Scenario: A folder that cannot be listed is a scan failure
- **WHEN** the event's folder cannot be listed while `POST /api/v1/jobs` names it
- **THEN** the response is the scan-failure 502 problem body, and no job row is inserted

#### Scenario: The schema publishes the refusal
- **WHEN** the service's OpenAPI schema is generated
- **THEN** `POST /api/v1/jobs` declares its 409 and 502 responses in the shared problem body shape, and that
  body's `conflict` enumeration includes `missing_clips` and its `missing` field is a list of strings
