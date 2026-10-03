## ADDED Requirements

### Requirement: A claimed job is dispatched by its kind
After claiming a job, the worker SHALL process it according to its `kind`. A `render` job SHALL follow the
render path unchanged: the claim-time recheck, collision checks, capacity tokens, progress, cancellation and
output behaviour of the requirements above apply to it exactly as before, whatever other kinds exist. A job of
any other kind SHALL be processed by the handler registered for that kind when the worker was constructed, and
a handler cannot replace the `render` path.

A job whose `kind` has no registered handler, whether a kind this system defines but the worker does not
handle or a value it has never heard of, SHALL transition to `failed` with a reason that names the kind. It
SHALL be failed before a capacity token is taken and before the event, its project configuration, ffprobe or
ffmpeg is touched, SHALL NOT be requeued, and SHALL NOT stop the worker or delay other jobs.

A handler that returns normally SHALL end its job `done` with progress `1.0`. A handler that raises the engine's
cancellation SHALL end its job `canceled`; one that raises one of the engine's typed errors SHALL end it
`failed` with that error's message; any other exception SHALL end it `failed` with the exception's type and
message, as for a render ("Per-job failure isolation"). Graceful shutdown, startup reconciliation and the
claim loop's in-flight bound SHALL treat a job of any kind as they treat a render.

#### Scenario: A render job is processed as before
- **WHEN** a worker with a `proxy` handler registered claims a `render` job for
  `2024/2024-06-27 - Grillning med grannar`
- **THEN** the job renders (or completes as fresh) through the render path, the `proxy` handler is not
  called, and the outcome, progress and capacity token use are those of a worker with no handlers

#### Scenario: A job of a handled kind runs its handler
- **WHEN** a worker with a handler registered for `proxy` claims a `proxy` job and the handler returns
- **THEN** the handler is called with that job, and the job ends `done` with progress `1.0`

#### Scenario: A job of a known kind with no handler fails loud
- **WHEN** a worker with no `proxy` handler claims a `proxy` job
- **THEN** the job is `failed` with a reason naming `proxy`, no capacity token was taken, no ffprobe or ffmpeg
  process ran and no file in the event folder was written, and the worker goes on to claim the next job

#### Scenario: A job of an unknown kind fails loud
- **WHEN** a worker claims a job whose `kind` is `thumbnails`, which no build of this system defines
- **THEN** the job is `failed` with a reason naming `thumbnails`, it is not requeued, and a `render` job
  queued behind it is claimed and rendered normally

#### Scenario: A handler's failure is isolated and typed
- **WHEN** a `proxy` handler raises an engine error with message `no audio stream` and a later `proxy`
  handler call raises `TypeError: boom`
- **THEN** the first job is `failed` with `no audio stream`, the second is `failed` with `TypeError: boom`,
  and the worker keeps claiming

#### Scenario: A handler's cancellation ends the job canceled
- **WHEN** a `proxy` handler raises the engine's cancellation
- **THEN** the job ends `canceled`

#### Scenario: A handler cannot take over the render path
- **WHEN** a worker is constructed with a handler registered under `render`
- **THEN** construction is refused, and no worker with that mapping exists

#### Scenario: A requeued proxy job is dispatched again
- **WHEN** a worker restarts while a `proxy` job is `running`
- **THEN** startup reconciliation requeues it, and the next claim dispatches it to the `proxy` handler again

## MODIFIED Requirements

### Requirement: A claimed job is refused while another running job writes its output
After claiming a job, and before the worker rebuilds its plan (so before it writes the event's `reel.yaml`,
probes a clip or starts ffmpeg), the worker SHALL refuse the job when a different `render` job that is `running` in
the job store writes the same output path, whichever project that job belongs to. A job's output path is its
project's output directory plus the file name its event's current metadata gives it; paths SHALL be compared
case-insensitively, after Unicode normalization, as for the batch commands' collision rule. The refused job
SHALL transition to `failed` with a reason that names the shared output path and the running job's event,
and SHALL NOT render, write the event's `reel.yaml`, write a render manifest or an `<output>.part` file, or
touch an output file that exists at that path. The running job is never interrupted. The check applies to a
`force` job as to any other, and a requeued job (for example after a worker restart) SHALL be checked again at
its next claim.

A job's own row, which is `running` from the moment it is claimed, SHALL NOT count as another running job. A
running job of any kind other than `render` writes no movie and SHALL NOT count, whatever its event. A
running job whose project configuration or event cannot be loaded, or whose event is not processable, claims
no path and SHALL NOT refuse the claimed job. When the claimed job's own output path cannot be resolved the
check refuses nothing, and the plan rebuild fails the job with its own reason as before. The disk rule of the
same-project collision is "Claim-time output-collision recheck"; this requirement adds the store-wide check
the disk rule cannot make (another project with the same output directory, an event the layout walk does not
reach). When the claimed job's output is also claimed on disk by another event of its project, the refusal SHALL be the disk rule's (the shared sentence), not this requirement's, because that rival is itself refused and writes nothing. Two jobs claimed at the same moment MAY both be refused, and at most one of them renders.

#### Scenario: A running job in another project holds the same output
- **WHEN** a job of project P1 is `running` and renders `<shared output>/2024/2024-06-21 - Midsommar.mp4`,
  and a worker then claims a job of project P2 whose `config.yaml` names the same output directory and whose
  event resolves to the same path
- **THEN** the P2 job is `failed` with a reason naming that path and the running job's event, the P1 job is
  not touched and finishes `done`, and the P2 event can be enqueued again once the P1 job has ended

#### Scenario: A refusal writes nothing into the event
- **WHEN** a claimed job is refused because of a running job and its event folder holds a clip that
  `reel.yaml` does not yet list
- **THEN** the job fails, `reel.yaml` is not rewritten to adopt that clip, and no ffprobe or ffmpeg process
  runs for it

#### Scenario: Force does not override a running job's output
- **WHEN** a job with `force = true` is claimed while another job writes its output path
- **THEN** the job is `failed` with the reason and nothing is rendered

#### Scenario: A running job with a different output does not block
- **WHEN** another job is `running` and resolves a different output path
- **THEN** the claimed job is not refused

#### Scenario: A running proxy job does not hold an output
- **WHEN** a `proxy` job for `2024/2024-06-21 - Midsommar` is `running`, and a worker claims the `render` job
  of the same event
- **THEN** the render job is not refused because of it

#### Scenario: A job's own row never blocks itself
- **WHEN** a worker claims a job, which makes its own row `running`
- **THEN** that row is not counted as another running job

#### Scenario: A running job whose event cannot be loaded claims nothing
- **WHEN** another `running` job's event folder has since been deleted, and a worker claims a job
- **THEN** the claimed job is not refused because of it

#### Scenario: A refusal does not hold a capacity token
- **WHEN** a claimed job is refused because of a running job
- **THEN** no capacity token was taken for it, and a following job can start at once
