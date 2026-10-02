## ADDED Requirements

### Requirement: Claim-time output-collision recheck
After claiming a job and before the claim-time staleness recheck, the worker SHALL apply the output-collision
rule of the batch commands (headless-cli, "Batch commands refuse colliding output paths") to the claimed
job's event, over the whole project: the claimants are every event the configured ingest layout walks from the
project's walk root, plus the claimed event itself. Paths SHALL be compared exactly as the batch commands
compare them (case-insensitively, after Unicode normalization). An event that fails on its own (an unparseable
`reel.yaml`, no real date or title, a folder or file that cannot be listed or read) SHALL claim no path, as in
the batch commands.

A job whose event shares its output path with another event SHALL be failed with a reason that states the
shared output path, names the other claimants, and names the fix (a distinct title or location in
`reel.yaml`), the same sentence the CLI and `POST /api/v1/jobs` use. For that job the worker MUST NOT probe,
adopt clips into or otherwise write a `reel.yaml`, render, replace an existing output file, create an
`<output>.part` file, or write a render manifest. This
SHALL hold whether the event is fresh or stale and whether or not `force` is set, and the job SHALL NOT be
requeued: the operator resolves the collision by editing `reel.yaml`, then enqueues again. The worker SHALL
continue with other jobs.

A check that cannot be made, because the layout walk itself fails (an unknown layout, or the walk root cannot
be listed), SHALL fail the job with that cause; the worker MUST NOT render an event whose collision it could
not check. The check itself SHALL only read: it writes no file and no row other than the job's own terminal state.

#### Scenario: An event edited into a collision after enqueue fails at claim
- **WHEN** jobs are enqueued for `2024/2024-06-21 - Midsommar` and `2024/2024-06-21 - Midsommar 2`, each
  with its own output path, and the second event's `reel.yaml` title is then edited to `Midsommar` before a
  worker claims either job
- **THEN** each job, when claimed, is failed with a reason naming `2024/2024-06-21 - Midsommar.mp4` and the
  other event, no ffmpeg process starts for either, no file appears under `<output>/2024/`, no manifest is
  written, and neither event's `reel.yaml` is changed by the worker

#### Scenario: A fresh colliding event is not completed as done
- **WHEN** a job is claimed for an event whose render manifest matches its fingerprint and whose output exists,
  and a newly added event now resolves to the same output path
- **THEN** the job is failed with the collision reason, not completed `done`, and the existing movie is
  byte-for-byte unchanged

#### Scenario: Force does not override the collision
- **WHEN** a job with `force = true` is claimed for an event whose output path another event claims
- **THEN** the job is failed with the collision reason and nothing is rendered

#### Scenario: A case-only difference collides
- **WHEN** a claimed event resolves to `2024/2024-06-21 - Midsommar.mp4` and another event to
  `2024/2024-06-21 - midsommar.mp4`
- **THEN** the claimed job is failed with the collision reason

#### Scenario: An unreadable sibling does not fail the job
- **WHEN** a job is claimed for a uniquely named event whose sibling event folder has permissions `000`
- **THEN** the sibling claims no path, the job passes the check and is rendered or skipped as fresh by the
  staleness recheck, as it would be without the sibling

#### Scenario: A walk that cannot be made fails the job
- **WHEN** the project's configured layout names a layout that is not registered, and a job is claimed
- **THEN** the job is failed with the unknown-layout cause and nothing is rendered

#### Scenario: A uniquely named event is unaffected
- **WHEN** a job is claimed for an event whose output path no other event claims
- **THEN** the claim-time staleness recheck and the render proceed exactly as before
