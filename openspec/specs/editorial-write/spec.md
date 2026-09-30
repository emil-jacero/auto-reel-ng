# editorial-write Specification

## Purpose

Apply a desired editorial state — metadata, ordered chapters with their clip order, per-clip properties,
the `ignore` list, and the `look` override — onto an event's existing `reel.yaml`, as a
transport-independent engine operation the CLI can also reach. The state is merged onto the document's
loaded round-trip structure so the author's comments and key order survive, validated exactly as a loaded
document is (schema + cross-references) before anything is written, and persisted fail-loud with no partial
write. The operation renders nothing, enqueues nothing, and probes no media; it writes no render manifest,
leaving a save's staleness consequence to emerge from the fingerprint's editorial component.

## Requirements

### Requirement: Apply a desired editorial state onto an event's document
The system SHALL provide an engine-level operation that takes an event and a desired editorial state —
metadata, ordered chapters with their clip order, per-clip properties, the `ignore` list, and the `look`
override — applies it onto the event's **existing** document, validates the result, and persists it to the
event's `reel.yaml`. The operation MUST be transport-independent (callable without the API) and MUST NOT
render, enqueue, or probe media.

#### Scenario: Metadata edit is persisted
- **WHEN** a desired state changes an event's title and location
- **THEN** the event's `reel.yaml` on disk carries the new title and location, and a subsequent load returns
  them

#### Scenario: Clip reorder is persisted
- **WHEN** a desired state reorders clips within a chapter and moves a clip to another chapter
- **THEN** the persisted document's chapter/clip order matches the desired state

#### Scenario: Look override is persisted
- **WHEN** a desired state sets a `look` override on an event whose document had none
- **THEN** the persisted `reel.yaml` carries the `look` map, and resolution layers it over the project
  `config.yaml` defaults

#### Scenario: Nothing is rendered or enqueued
- **WHEN** the operation runs
- **THEN** no ffmpeg process starts, no job row is created, and no media file is read

### Requirement: Comments and key order survive an editorial write
The operation SHALL apply the desired state onto the document's loaded round-trip structure so that
persisting preserves the author's comments and key order — only the lines that actually changed may differ.
It MUST NOT serialize from a mapping constructed out of the request/desired state alone, which would emit a
structure stripped of comments. For an event with no `reel.yaml` yet (no loaded structure), the operation
SHALL fall back to building the document from its typed fields.

#### Scenario: Hand-authored comments survive a save
- **WHEN** a desired state changes only the title of a hand-authored `reel.yaml` containing comments
- **THEN** the persisted file retains every comment and its key order, and differs only in the title line

#### Scenario: Round-tripping an unmodified state is a no-op
- **WHEN** a desired state identical to the document's current state is applied
- **THEN** the persisted file is byte-for-byte unchanged

#### Scenario: Event without a reel.yaml is written fresh
- **WHEN** the operation applies a desired state to an event that has no `reel.yaml` on disk
- **THEN** a valid `reel.yaml` is created from the typed fields in canonical order

### Requirement: Editorial writes are validated fail-loud and atomic in effect
The merged document SHALL be validated exactly as a loaded document is — schema (version, metadata, look,
chapters, clips, ignore) and cross-references — before anything is written. It SHALL also be validated as
an **event**: its metadata, resolved field by field over the event's folder name as every other consumer
resolves it, SHALL have a real date and a title, and the date SHALL NOT be after the current day. A
validation failure SHALL raise loudly, naming the offending part, and MUST leave the existing `reel.yaml`
untouched (no partial write). A failure of the event rule SHALL name the missing or invalid field and how to
supply it.

Persisting the validated document SHALL replace `reel.yaml` atomically. The new content SHALL be written in
full to a temporary file in the same folder and made durable, and only then moved over the original in a
single rename, so a failed or refused write, or one interrupted before that rename, leaves the previous
document intact and never a truncated or partial one. A write the filesystem refuses SHALL raise loudly naming the operating-system error. The temporary file
SHALL be removed whenever the filesystem still allows it. One left behind by an interruption that prevents
its removal, such as a disconnected drive, SHALL never be read as the document.

#### Scenario: Invalid state is rejected without writing
- **WHEN** a desired state fails cross-reference validation (a chapter references a clip the document does
  not define)
- **THEN** the operation fails loudly naming the problem and the existing `reel.yaml` is unchanged

#### Scenario: Referencing a clip absent from disk is allowed
- **WHEN** a desired state references a clip that is not present on disk
- **THEN** the write succeeds and the reference is preserved (it is a MISSING clip for reconcile to report,
  never a validation error and never silently dropped)

#### Scenario: Clearing the only date is refused
- **WHEN** a desired state for the event folder `2024/Blandat`, whose name carries no date, sets no
  `metadata.date`
- **THEN** the operation fails loudly stating the event would have no date, and the existing `reel.yaml`
  is unchanged

#### Scenario: A date typed into the future is refused
- **WHEN** a desired state sets `metadata.date` to a day after the current day
- **THEN** the operation fails loudly naming that date as in the future, and nothing is written

#### Scenario: Setting a real date fixes an unprocessable event
- **WHEN** the event folder `2004/2004 - Yngve berättar om skövde`, which has a year only, receives a desired
  state with `metadata.date: 2004-05-01`
- **THEN** the write succeeds, and the event is processable from then on, listed as a summary rather than
  needing attention

#### Scenario: The folder name still supplies what the document leaves unset
- **WHEN** a desired state for the event folder `2024-06-21 - Trip` sets a title but no date
- **THEN** the write succeeds, because the resolved date comes from the folder name

#### Scenario: An interrupted write leaves the old document
- **WHEN** persisting an edited document fails after writing part of the new content, for example with a
  write error mid-file
- **THEN** `reel.yaml` still holds the complete previous document, and the temporary file has been removed

#### Scenario: A read-only archive refuses the save loudly
- **WHEN** an editorial write targets an event on a filesystem mounted read-only
- **THEN** the operation raises naming the read-only error, and `reel.yaml` is unchanged

### Requirement: An editorial write records no render state
The operation SHALL NOT write, update, or delete a render manifest, and SHALL NOT mark an event rendered.
The staleness consequence of the write MUST be left to emerge from the fingerprint: because the editorial
component changed, the event becomes stale.

#### Scenario: Save makes the event stale
- **WHEN** a fresh (previously rendered, unchanged) event receives an editorial write
- **THEN** no manifest is written and the event subsequently evaluates stale citing the editorial component

#### Scenario: Save is not render
- **WHEN** an editorial write completes
- **THEN** the event's output file (if any) is unchanged and no job exists as a result of the write
