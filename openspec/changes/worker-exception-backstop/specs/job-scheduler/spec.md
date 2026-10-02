## MODIFIED Requirements

### Requirement: Per-job failure isolation
A failure building or rendering one job (missing event dir, probe error, render error) SHALL transition
that job to `failed` with the error message recorded, and MUST NOT stop the worker or affect other jobs —
mirroring the CLI batch's per-event isolation. This SHALL hold for any failure while a claimed job is
processed, not only for the engine's own typed errors: an unexpected exception (an I/O error reading the
event, a defect in the build or render, a failed progress or cancel-flag write) SHALL also transition that
job to `failed`, with the error recorded as the exception's type and message, and the job's capacity token
MUST be released. A job MUST NOT be left `running` by a failure of its own processing. If recording the
failure itself fails (for example the database is unreachable), the worker SHALL log it and keep running;
the row is then left for startup reconciliation. A cancellation SHALL still end `canceled`, and a requeue
by graceful shutdown SHALL still end `queued`, rather than being rewritten as `failed`.

#### Scenario: Failed plan rebuild fails only that job
- **WHEN** a claimed job's event directory no longer exists
- **THEN** the job is marked `failed` with the cause and the worker continues claiming other jobs

#### Scenario: Unexpected error while building fails the job
- **WHEN** rebuilding a claimed job's plan raises an error that is not one of the engine's typed errors
  (for example `OSError: disk gone`)
- **THEN** the job is marked `failed` with the error `OSError: disk gone`, not left `running`, and the
  worker continues claiming other jobs

#### Scenario: Unexpected error while rendering fails the job and frees its token
- **WHEN** the render of a claimed job raises an error that is not one of the engine's typed errors
  (for example `TypeError: boom`)
- **THEN** the job is marked `failed` with the error `TypeError: boom`, its capacity token is released so a
  following job can start, and the event can be enqueued again

#### Scenario: Failed progress write fails the job
- **WHEN** persisting a render's progress raises while the job renders
- **THEN** the job is marked `failed` with that error rather than left `running`

#### Scenario: Failure to record the failure does not stop the worker
- **WHEN** a job fails unexpectedly and the transition to `failed` itself raises
- **THEN** the failure is logged, the worker does not stop, and the row is left for the next startup
  reconciliation to requeue

#### Scenario: Cancellation and shutdown requeue keep their own outcome
- **WHEN** a job is canceled mid-render, or gracefully shut down and requeued while an unexpected error ends
  its processing
- **THEN** the canceled job ends `canceled` and the requeued job stays `queued`, neither is rewritten as
  `failed`
