## RENAMED Requirements

- FROM: `### Requirement: Cooperative cancellation between segments`
- TO: `### Requirement: Cooperative cancellation of a running render`

## MODIFIED Requirements

### Requirement: Cooperative cancellation of a running render
The worker SHALL check the job's `cancel_requested` flag at segment boundaries during a render, and SHALL
also check it while a segment is being encoded, about once a second. When set, the worker SHALL stop the
render — before the next segment starts, or by terminating the running ffmpeg process if a segment is in
progress — clean up its scratch work, and transition the job `running → canceled`. The worker SHALL remain
the sole writer of job status transitions.

#### Scenario: Running job is canceled at a segment boundary
- **WHEN** `cancel_requested` is set while a job is rendering segment k of n (k < n)
- **THEN** no segment after k is started, no output appears at the final path, and the job ends `canceled`

#### Scenario: Running job is canceled inside a segment
- **WHEN** `cancel_requested` is set while ffmpeg is encoding a long clip's segment k of n
- **THEN** within about a second that ffmpeg process is terminated rather than allowed to finish the segment,
  no segment after k is started, no output and no `.part` file remain at the final path, and the job ends
  `canceled`

## ADDED Requirements

### Requirement: A stalled render fails its job
A render whose segment encode makes no progress for ten minutes SHALL be terminated and its job SHALL
transition `running → failed` with an error that names the segment and says ffmpeg stalled, through the same
path as any other render failure. The worker MUST release the job's capacity token and MUST NOT stop or
delay other jobs. No output SHALL appear at the final path and no render manifest SHALL be written, so the
event remains stale and can be enqueued again. A job that makes steady progress SHALL NOT be failed for
taking long, however long it takes.

#### Scenario: Hung ffmpeg fails the job and frees the device
- **WHEN** a job's ffmpeg for segment 2 of `2024/2024-10-05 - Trasig` stops reporting output time and ten
  minutes pass
- **THEN** the job is `failed` with an error naming segment 2 and the stall, the GPU token it held is
  released so the next queued job on that device can start, and no movie or `.part` file exists at the
  output path

#### Scenario: A stalled event can be re-enqueued
- **WHEN** a job failed because its render stalled and the operator enqueues the same event again
- **THEN** the event is still stale (no manifest was written) and a new job is created and rendered normally

#### Scenario: A long healthy render is not failed
- **WHEN** a segment takes 45 minutes to encode and ffmpeg advances its output time throughout
- **THEN** the job is not failed for its duration and completes `done`
