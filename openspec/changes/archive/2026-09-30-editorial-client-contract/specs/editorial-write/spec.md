## MODIFIED Requirements

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
