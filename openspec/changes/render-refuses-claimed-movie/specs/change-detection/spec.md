## MODIFIED Requirements

### Requirement: A renamed event keeps its previous movie
When an event's output path has changed since its last render, because its title, date or location changed under
the output-naming rule, the engine MUST NOT delete, move, rename or overwrite the movie that render wrote, except
as stated below.

The next successful render of the event SHALL:
- write its movie at the new expected output path;
- record the new file name in the manifest;
- leave the previous movie on disk, unchanged.

The event then evaluates fresh. The previous movie is an ordinary file in the output directory, and no later verdict
refers to it. Removing it is the operator's decision. This SHALL hold for a forced render too, and for every render
path: the CLI's `render` and the worker.

A render still replaces whatever file is at its own expected output path, as every render of a stale event does.
That covers two cases:
- a movie an earlier render of the event left under the name the event has again;
- a case-only change of name on a case-insensitive filesystem, where the new path names the previous movie's own
  file.

In both cases the expected output already exists, so the gate cites neither `output` nor `output_renamed`.

Another event whose current name is the renamed event's old name is not a third case: the kept movie is recorded
in the renamed event's manifest, so that other event's render is refused unless forced ("A render refuses to
replace a movie another event records"). A forced render of it does replace the kept movie, and the renamed
event's verdict then still cites `output_renamed`, although the file under its old name is now the other
event's movie.

#### Scenario: A render after a retitle writes beside the old movie
- **WHEN** the retitled `2024-06-27 - Grillning med grannar` is rendered
- **THEN** `<output>/2024/2024-06-27 - Grillkväll med grannarna.mp4` is written and verified
- **AND** `<output>/2024/2024-06-27 - Grillning med Grannar.mp4` still exists, with its size and modification time
  unchanged
- **AND** the manifest records `2024-06-27 - Grillkväll med grannarna.mp4`
- **AND** the next verdict for the event is fresh

#### Scenario: A forced render keeps the old movie too
- **WHEN** a renamed event is rendered with force
- **THEN** the new movie is written at the expected path and the previous movie is left unchanged

#### Scenario: A failed render after a rename changes nothing
- **WHEN** the render of a renamed event fails or is cancelled
- **THEN** the previous movie and the manifest are unchanged, no file exists at the new expected path, and the
  verdict still cites `output_renamed`

#### Scenario: Another event taking the old name does not replace the kept movie
- **WHEN** `2024-06-27 - Grillning med grannar` was retitled and not yet rendered, so its manifest still records
  the old name, and a different event is retitled to that old name and rendered without force while the old movie
  is on disk
- **THEN** the other event's render is refused with the claimed-movie error naming the renamed event, and the old
  movie is unchanged

## ADDED Requirements

### Requirement: A render refuses to replace a movie another event records

Before a render replaces a regular file at its event's expected output path, and unless the render is forced, the
engine SHALL check whether the render manifest of any *other* event of the project records exactly that file as
its output. The events checked are those of the project's own layout walk, whole: the CLI's `--years` filter
narrows what is rendered, never who may claim. The comparison is on the full path,
NFC-normalised and case-insensitive, and an event's recorded name is placed by the naming rule
(`recorded_output_path`), so a recorded name is a match only when it is a bare file name. A manifest that cannot
be read claims nothing. The event being rendered is never its own claimant, and a file its own manifest records is its own movie, so
it is not refused even while another event's manifest still records the same file. An unparseable or unprocessable
`reel.yaml` of the other event does not stop its manifest from claiming.

When another event claims the file, the render SHALL fail that event with a typed engine error that names the
file and the claiming event(s) and says that a forced render replaces it. The refusal SHALL be decided before
anything is rendered or probed for the event: no `.part`, no manifest and no ffmpeg invocation, and, in the
worker, no clip adopted into its `reel.yaml`. (The CLI's reconcile step runs before its gate for every event, so
it may already have seeded or adopted into `reel.yaml`, as it does for an event refused by the collision rule; the
refusal itself writes nothing.) It SHALL NOT stop the other events of a batch. It SHALL hold for the CLI's `render` and for
the worker; a forced render (`--force`, a job's `force`) SHALL skip the check, and so SHALL a dry run, which
checks nothing on disk. A render that would create a new file, or whose output path holds a file nobody records,
replaces nothing and is unaffected. The engine SHALL NOT delete, move or rename the claimed movie in any case.

This rule is separate from the output-collision rule: two events whose *current* paths are equal remain refused
whether or not the render is forced.

The claim holds for as long as the other event's manifest records the file; it ends when that event renders
under another name, or when the file is gone. The refusal is evaluated against the manifests as they are when the
event is built, so in one batch an event taking the old name of a renamed event that is also in the batch is
refused, and succeeds in a later run.

#### Scenario: An event taking a renamed event's old name is refused
- **WHEN** `2024-06-27 - Grillning med grannar` was rendered, then retitled `Grillkväll` and not yet re-rendered,
  and a second event dated `2024-06-27` is titled `Grillning med grannar` and rendered without force
- **THEN** the second event fails with an error naming `2024/2024-06-27 - Grillning med grannar.mp4` and the
  retitled event, the file is unchanged with no `.part` beside it, no manifest is written for the second event,
  and the exit status of `render` is non-zero

#### Scenario: The owner of a movie is not refused for a stale record
- **WHEN** a forced render gave event A the movie `F`, event B's manifest still records `F` too, and A is rendered
  again without force
- **THEN** A is not refused, in the CLI or the worker

#### Scenario: A claimant outside the years filter still claims
- **WHEN** `render --years 2024` renders an event whose output file is recorded by an event filed under a
  folder the filter excludes
- **THEN** the render is refused and names that event

#### Scenario: The other events of the batch still render
- **WHEN** the refused event shares a `render` batch with a renderable third event
- **THEN** the third event is rendered and reported, and the refused one is reported as failed

#### Scenario: Force replaces the claimed movie
- **WHEN** the same render is requested with `--force`, or the worker claims a job with `force` set
- **THEN** the file is replaced by the second event's movie and the second event's manifest is written

#### Scenario: A worker job is refused with the same text
- **WHEN** the worker claims a job for the second event without force
- **THEN** the job ends `failed` with the claimed-movie text as its error, and its `reel.yaml` is unchanged

#### Scenario: Once the renamed event re-renders the name is free
- **WHEN** the retitled event is rendered under its new name, and the second event is then rendered without force
- **THEN** the second event replaces the old-named file, because no manifest records it any longer

#### Scenario: A file nobody records is replaced as before
- **WHEN** an event's stale output path holds a movie that no other event's manifest records
- **THEN** an unforced render replaces it

#### Scenario: A case-insensitive match is a claim
- **WHEN** the other event's manifest records `2024-06-27 - grillning med grannar.mp4` and the file at the
  render's path differs from it only in case
- **THEN** the render is refused

#### Scenario: An unreadable manifest claims nothing
- **WHEN** the other event's `render-manifest.json` is not valid JSON
- **THEN** the render is not refused on its account

#### Scenario: A recorded path is not a match
- **WHEN** another event's manifest records `..` or a name containing a path separator
- **THEN** it claims no file

#### Scenario: An unparseable reel.yaml does not hide a claim
- **WHEN** the other event's `reel.yaml` does not parse but its manifest records the file
- **THEN** the render is refused and names that event

#### Scenario: A walk that fails refuses the worker job
- **WHEN** the layout walk of the project fails while the worker checks a replacing job
- **THEN** the job fails with the walk's error and renders nothing
