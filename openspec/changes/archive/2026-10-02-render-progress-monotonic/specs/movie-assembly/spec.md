## ADDED Requirements

### Requirement: Render progress is non-decreasing and weighted by expected work

The engine's overall render progress, delivered to `on_progress` as a fraction in `[0.0, 1.0]`, SHALL never
decrease: a callback value MUST be strictly greater than every value delivered before it for the same render,
and a value that would not exceed the highest one so far MUST NOT be delivered. This holds whatever re-runs
the pipeline performs — the re-normalization of stream-copied segments after a failed equivalence pre-flight,
or a segment whose normalize is attempted again — because only forward movement of the whole render counts.

Progress SHALL be weighted by expected work, not by step count:

- a segment that is normalized weighs its intended duration (the kept span, a synthetic segment's duration, or
  the clip's probed duration for a whole clip);
- a stream-copied segment weighs nothing and SHALL NOT report progress of its own;
- the final concat SHALL own a fixed small share at the top of the span, and `1.0` is delivered when the
  concat has finished;
- when at least one segment is copy-eligible, the engine SHALL reserve a share of the span for the possible
  re-encode pass, between the normalize pass and the concat share. The re-encode pass SHALL move progress
  forward from the highest value so far to the end of that share, weighted by the duration of the segments it
  re-encodes. When the pre-flight passes and no re-encode is needed, progress advances to the start of the
  concat share only after the pre-flight has passed. When no segment is copy-eligible, no share is reserved.

The weights are an estimate of work, not of wall-clock time; the guarantee of this requirement is monotonic,
bounded progress that reaches `1.0` only at the end of the concat, not linearity.

#### Scenario: Re-encode after a failed pre-flight does not move progress backwards
- **WHEN** four copy-eligible clips are stream-copied, the equivalence pre-flight then finds the set not
  uniform, and the four are re-normalized
- **THEN** the delivered fractions form a non-decreasing sequence, the re-encode pass moves progress forward
  from where the normalize pass stopped, and the sequence ends at `1.0`

#### Scenario: An all-copy event does not jump early
- **WHEN** an event of 32 copy-eligible clips renders and the pre-flight passes
- **THEN** no fraction is delivered before the pre-flight has passed, the next delivered value is the start of
  the concat share (not `32/33`), and `1.0` is delivered when the concat finishes

#### Scenario: Long and short segments are weighted by duration
- **WHEN** an event with no copy-eligible segment normalizes a 10-second segment and then a 30-second segment
- **THEN** progress after the first segment is one quarter of the way to the start of the concat share, not
  one half

#### Scenario: A retried segment does not move progress backwards
- **WHEN** a segment's normalize is attempted a second time after the first attempt reported part of its
  progress, and the second attempt reports from `0.0` again
- **THEN** no value below the highest already delivered is passed to `on_progress`, and progress resumes once
  the retry passes that point

#### Scenario: A mixed event spends its re-encode share only when needed
- **WHEN** an event with one title card, two normalized clips and three copy-eligible clips renders and the
  pre-flight passes on the first check
- **THEN** progress ends the normalize pass at the end of its share, advances to the start of the concat share
  once the pre-flight has passed, and no value is delivered inside the reserved re-encode share
