# media-analysis Specification

## Purpose

Analyze a single clip for dead footage — black, white, and freeze spans — using ffmpeg detection filters run through `FfmpegRuntime`, returning typed `Segment` suggestions with calibrated, configurable thresholds. Black/white spans take precedence over overlapping freeze spans so each region is reported under exactly one kind. The pass is suggestion-only: it never mutates `reel.yaml` or applies trims, fails loud on undecodable clips, and carries a coarse confidence per segment in v1.

## Requirements

### Requirement: Detect black, white, and freeze spans in a clip

The system SHALL analyze a single clip with ffmpeg detection filters and return a list of
`Segment` values, each carrying `start`, `end` (seconds, `end > start`), `kind`
(`black`, `white`, or `freeze`), and `confidence`. Detection SHALL use `FfmpegRuntime` to run
the filters and parse the resulting log lines; it SHALL NOT use a Python ffmpeg binding.

#### Scenario: Black span detected

- **WHEN** a clip contains a span where the `blackdetect` filter reports `black_start`/`black_end`
  at or above the configured thresholds and at least the minimum duration
- **THEN** the result contains a `Segment` with `kind = black` whose `start`/`end` match the
  reported timestamps

#### Scenario: White span detected via inverted blackdetect

- **WHEN** a clip contains a fully white span
- **THEN** the system detects it by running `negate,blackdetect` and emits a `Segment` with
  `kind = white` at the reported timestamps

#### Scenario: Freeze span detected

- **WHEN** the `freezedetect` filter reports a `freeze_start`/`freeze_end` span of at least the
  minimum duration
- **THEN** the result contains a `Segment` with `kind = freeze` at the reported timestamps

#### Scenario: No dead footage

- **WHEN** a clip contains only ordinary moving footage with no qualifying span
- **THEN** the result is an empty list of segments

### Requirement: Two-pass filter invocation

The system SHALL run black and freeze detection together in one ffmpeg pass and white detection
(`negate,blackdetect`) in a separate pass, because `negate` rewrites the stream and cannot share
a filter chain with the un-negated black/freeze detection.

#### Scenario: White pass is isolated

- **WHEN** the analysis runs on a clip
- **THEN** exactly two ffmpeg invocations are issued per clip: one for `blackdetect`+`freezedetect`
  and one for `negate,blackdetect`

### Requirement: Calibrated default thresholds, all configurable

The system SHALL default to the experiment-005 thresholds and SHALL allow each to be overridden:
black/white `pic_th = 0.98` and `pix_th = 0.10`; freeze `n = 0.003`; minimum duration `d = 2.0`
seconds for all three kinds.

#### Scenario: Defaults applied when unconfigured

- **WHEN** analysis runs with no threshold overrides
- **THEN** the emitted ffmpeg filter arguments use `pic_th=0.98`, `pix_th=0.10`, freeze `n=0.003`,
  and `d=2.0` for each detector

#### Scenario: Overrides honored

- **WHEN** analysis runs with an overridden minimum duration
- **THEN** the emitted ffmpeg filter arguments use the overridden value and spans shorter than it
  are not reported

### Requirement: Resolve black/white over freeze overlap

A static black or white span is also frozen, so `freezedetect` will report it. The system SHALL
resolve overlapping spans with precedence `black`/`white` over `freeze`, so that a region of the
clip is reported under exactly one `kind` and never double-counted.

#### Scenario: Freeze overlapping a black span is suppressed

- **WHEN** a freeze span and a black span cover the same region of the clip
- **THEN** the region is reported only as `kind = black` and the overlapping freeze span is not
  emitted for that region

#### Scenario: Freeze outside any black/white span is kept

- **WHEN** a freeze span does not overlap any black or white span
- **THEN** it is emitted as `kind = freeze`

### Requirement: Suggestions only — no editorial mutation

Detected segments are suggestions. The analysis pass SHALL NOT write to `reel.yaml` and SHALL NOT
apply trims; it only returns and caches segments. Mapping a `Segment` to an approved `Trim` is the
responsibility of a future consumer.

#### Scenario: reel.yaml untouched by analysis

- **WHEN** analysis runs on an event whose directory contains a `reel.yaml`
- **THEN** the `reel.yaml` file is not modified

### Requirement: Fail loud on undecodable clips

Consistent with the engine-wide rule, the system SHALL raise a typed error when a clip cannot be
analyzed (e.g. ffmpeg fails or the file is undecodable) and SHALL NOT return fabricated or empty
results that hide the failure.

#### Scenario: Undecodable clip raises

- **WHEN** ffmpeg exits non-zero while analyzing a clip
- **THEN** the system raises a typed analysis error identifying the clip, rather than returning an
  empty segment list

### Requirement: Coarse confidence in v1

The system SHALL populate each `Segment.confidence` with a coarse value in v1 (the detector firing
constitutes the signal). A richer `signalstats`-derived confidence is reserved for later and the
field SHALL remain present in the type.

#### Scenario: Confidence present on every segment

- **WHEN** any segment is emitted
- **THEN** it carries a `confidence` value in the range `0.0`–`1.0`
