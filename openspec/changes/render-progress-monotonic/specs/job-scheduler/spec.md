## MODIFIED Requirements

### Requirement: Progress is persisted, throttled
The worker SHALL forward the engine's `on_progress` fraction into the job row via `set_progress`,
throttled (a minimum delta and/or minimum interval between writes) so progress updates do not flood the
database. The stored progress MUST reach 1.0 no later than the job's terminal transition to `done`.
The forwarding callback SHALL NOT write a fraction lower than the highest one it has already received for
that job run: a lower fraction is dropped, not written, so the stored value never decreases while a job runs
even if the engine delivers one; the terminal `1.0` is never dropped.

#### Scenario: Progress advances during a render
- **WHEN** a job is rendering
- **THEN** its stored `progress` increases monotonically toward 1.0 without a write per ffmpeg progress line

#### Scenario: A lower fraction is never written
- **WHEN** the callback has received `0.80` and then receives `0.19`, even after the throttle interval has
  elapsed
- **THEN** no write is made for `0.19`, the stored `progress` stays at `0.80`, and a later `0.85` is written
  normally

#### Scenario: The terminal fraction is not throttled or dropped
- **WHEN** the callback has received `0.999` and then receives `1.0` within the throttle interval
- **THEN** `1.0` is written
