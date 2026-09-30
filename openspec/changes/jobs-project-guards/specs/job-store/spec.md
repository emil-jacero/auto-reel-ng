## MODIFIED Requirements

### Requirement: Query jobs
The store SHALL expose read operations to fetch a job by id and to list jobs filtered by status, ordered
by `created_at`. These back the later API/GUI without granting them write access to the queue mechanics.

The store SHALL also expose a read of the jobs that finished since a given instant: every job whose
`finished_at` (stamped only by a terminal transition) is at or after that instant minus a caller-given
overlap, ordered by `finished_at` ascending, returned together with the database's current time as seen by
the same read. When no instant is given, the database's current time is the instant. The instant and the
returned time SHALL be database time, the same clock that stamps `finished_at`, so a caller that passes
back the time it received never depends on the application host's clock.

The status listing and the finished-since read SHALL each accept an optional project root. When one is
given, the read SHALL return only jobs recorded with exactly that project root, and never a job with no
recorded project root; the returned database time is unaffected. When none is given, it SHALL return every
project's jobs, as before.

#### Scenario: Fetch by id
- **WHEN** a job's id is queried
- **THEN** its current row (status, progress, timestamps, error) is returned, or null if absent

#### Scenario: List by status
- **WHEN** jobs are listed filtered to `queued`
- **THEN** only `queued` jobs are returned, ordered by `created_at` ascending

#### Scenario: List jobs finished since an instant
- **WHEN** the finished-since read returns time `T` with no overlap, then the `running` job of
  `2024/2024-10-05 - Trasig` is transitioned to `failed`, and the read is made again from `T` with no
  overlap
- **THEN** the second read returns the Trasig job with status `failed`, returns no `queued` or `running`
  job, and returns no job that finished before `T`

#### Scenario: The overlap reaches back before the instant
- **WHEN** a job finished shortly before time `T`, and the finished-since read is made from `T` with an
  overlap longer than that gap
- **THEN** the job is returned

#### Scenario: List by status within one project
- **WHEN** `queued` jobs exist for `2024/Blandat` under both `/dev/a/library` and `/dev/b/library`, and
  `queued` jobs are listed narrowed to `/dev/a/library`
- **THEN** only `/dev/a/library`'s job is returned
- **AND** the same listing without the project narrowing returns both jobs, ordered by `created_at`
  ascending

#### Scenario: Finished jobs within one project
- **WHEN** the finished-since read returns time `T`, then `running` jobs of `2024/2024-10-05 - Trasig` under
  both `/dev/a/library` and `/dev/b/library` are transitioned to `failed`, and the read is made again from
  `T` narrowed to `/dev/a/library`
- **THEN** only `/dev/a/library`'s job is returned
- **AND** the same read without the project narrowing returns both jobs

#### Scenario: A job with no recorded project root is never in a narrowed listing
- **WHEN** a `queued` job row has no recorded project root, and `queued` jobs are listed narrowed to
  `/dev/a/library`
- **THEN** that job is not returned, and the listing without narrowing still returns it
