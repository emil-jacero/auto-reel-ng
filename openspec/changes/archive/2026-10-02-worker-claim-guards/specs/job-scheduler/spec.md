## ADDED Requirements

### Requirement: A claimed job is refused while another running job writes its output
After claiming a job, and before the worker rebuilds its plan (so before it writes the event's `reel.yaml`,
probes a clip or starts ffmpeg), the worker SHALL refuse the job when a different job that is `running` in
the job store writes the same output path, whichever project that job belongs to. A job's output path is its
project's output directory plus the file name its event's current metadata gives it; paths SHALL be compared
case-insensitively, after Unicode normalization, as for the batch commands' collision rule. The refused job
SHALL transition to `failed` with a reason that names the shared output path and the running job's event,
and SHALL NOT render, write the event's `reel.yaml`, write a render manifest or an `<output>.part` file, or
touch an output file that exists at that path. The running job is never interrupted. The check applies to a
`force` job as to any other, and a requeued job (for example after a worker restart) SHALL be checked again at
its next claim.

A job's own row, which is `running` from the moment it is claimed, SHALL NOT count as another running job. A
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

#### Scenario: A job's own row never blocks itself
- **WHEN** a worker claims a job, which makes its own row `running`
- **THEN** that row is not counted as another running job

#### Scenario: A running job whose event cannot be loaded claims nothing
- **WHEN** another `running` job's event folder has since been deleted, and a worker claims a job
- **THEN** the claimed job is not refused because of it

#### Scenario: A refusal does not hold a capacity token
- **WHEN** a claimed job is refused because of a running job
- **THEN** no capacity token was taken for it, and a following job can start at once
