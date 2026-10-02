## ADDED Requirements

### Requirement: Latest job per event in a project
The store SHALL expose a read that returns, for one project root, the most recent job of each event: for
every `event_dir` that has at least one job recorded with exactly that project root, the job with the
greatest `created_at`, whatever its status (`queued`, `running`, `done`, `failed` or `canceled`). The result
SHALL hold one job per event, keyed by `event_dir`, and SHALL be produced by a single query rather than one
lookup per event. A job recorded with a different project root, or with no project root, SHALL NOT appear.
An event whose jobs tie on `created_at` SHALL resolve to the same job on every read. The read MUST NOT
depend on a SQL construct that SQLAlchemy has deprecated, so it behaves identically across the supported
SQLAlchemy 2.x releases.

#### Scenario: The newest job of an event wins whatever its status
- **WHEN** `2024/2024-06-27 - Grillning med grannar` under `/dev/a/library` has a `done` job, later a
  `failed` job, and later still a `queued` job, and the latest-per-event read is made for `/dev/a/library`
- **THEN** the result holds the `queued` job for that event, and no other job of that event

#### Scenario: One job per event across several events
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has two jobs and `2024/Blandat` has one, all under
  `/dev/a/library`
- **THEN** the result has exactly two entries, keyed `2024/2024-06-27 - Grillning med grannar` (its newer
  job) and `2024/Blandat` (its only job)

#### Scenario: Other projects and unrooted jobs are excluded
- **WHEN** `2024/Blandat` has jobs under both `/dev/a/library` and `/dev/b/library`, `2024/2024-10-05 -
  Trasig` has a job with no recorded project root, and the read is made for `/dev/a/library`
- **THEN** the result holds only `/dev/a/library`'s job for `2024/Blandat`, and no entry for
  `2024/2024-10-05 - Trasig`

#### Scenario: A project with no jobs yields an empty result
- **WHEN** the read is made for a project root no job was recorded with
- **THEN** the result is empty

#### Scenario: A tie on creation time resolves the same way every time
- **WHEN** two jobs of `2024/Blandat` under `/dev/a/library` carry an identical `created_at`, and the read
  is made twice
- **THEN** both reads return the same one of those jobs
