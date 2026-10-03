## MODIFIED Requirements

### Requirement: Race-free claim-next
The store SHALL expose a `claim_next` operation that atomically selects the next
`queued` job eligible for the caller's device filter, in the order given below, and transitions it to `running`, stamping `worker_id`
and `started_at`. Two workers calling `claim_next` concurrently MUST NEVER claim the same job; selection
MUST use `FOR UPDATE SKIP LOCKED` rather than locking the whole queue. Ordering MUST be `render` jobs
before jobs of any other kind, then `priority` descending, then `created_at` ascending (FIFO within a
priority and kind), so a queued render is claimed before any other job however old that job is and whatever
its `priority`. The operation MAY be given a set of kinds that are not eligible for this call; a `queued` job
of such a kind is skipped, not claimed and not changed, and a kind that is not named is eligible, including a
kind this build has never heard of.

#### Scenario: Two workers never claim the same job
- **WHEN** two workers call `claim_next` concurrently against a queue with one eligible job
- **THEN** exactly one worker receives the job (now `running` with its `worker_id`) and the other receives
  nothing, with neither blocking on the other

#### Scenario: FIFO within priority
- **WHEN** several `queued` jobs of one kind share the default priority
- **THEN** `claim_next` returns them in ascending `created_at` order

#### Scenario: Device filter excludes ineligible jobs
- **WHEN** a worker claims with a device filter that a `queued` job's `device` does not satisfy
- **THEN** that job is not returned to this worker

#### Scenario: A render is claimed before an older job of another kind
- **WHEN** a `proxy` job was queued an hour ago at priority `0`, and a `render` job was queued a minute ago at
  priority `0`
- **THEN** the first `claim_next` returns the `render` job and the second returns the `proxy` job

#### Scenario: A named kind is not eligible
- **WHEN** a `queued` `proxy` job exists and `claim_next` is called with `proxy` among the kinds that are not
  eligible
- **THEN** it returns nothing for that job, the job stays `queued` and unchanged, and a later call without that
  exclusion claims it

#### Scenario: A kind that is not named is still eligible
- **WHEN** a `queued` job has a kind this build does not know and `claim_next` is called with only `proxy`
  excluded
- **THEN** that job is claimed
