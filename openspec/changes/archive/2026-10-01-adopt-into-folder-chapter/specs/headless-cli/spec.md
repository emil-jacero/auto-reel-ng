## MODIFIED Requirements

### Requirement: NEW-clip adoption policy

When an event directory has no `reel.yaml`, the system SHALL seed one from disk structure. When an
event has a `reel.yaml` and disk contains `NEW` clips, `render` SHALL adopt every `NEW` clip so an added
clip is not silently dropped, while `MISSING` clips SHALL be reported loudly and never silently removed
from the document. A render that the job-scheduler worker runs, such as the one the GUI's Render starts,
SHALL adopt exactly as `render` does.

Each `NEW` clip SHALL be adopted into the chapter named after the folder it was found in. A clip in the
event folder itself goes into the default chapter. A clip in a chapter subfolder goes into the chapter with
that subfolder's name. When `reel.yaml` names no chapter of that name, the clip SHALL be adopted into the
default chapter instead. When `reel.yaml` does not name the default chapter and a clip enters it, the
default chapter SHALL be added after the chapters `reel.yaml` names.

A `reel.yaml` that names no chapters at all SHALL be adopted into as first discovery seeds a new event.
Each `NEW` clip SHALL enter the chapter named after its folder, the default chapter for the event folder's
clips. Those chapters SHALL be added in seeding order: the default chapter first, then the subfolders'
chapters by name. The result SHALL be the chapters and clip order that seeding the same event would write
under the same sort rule.

Apart from these, adoption SHALL NOT create any chapter. It SHALL NOT move, remove or re-order a clip that
`reel.yaml` already lists, wherever an earlier adoption or a hand edit put it. The adoption target is set by
this rule alone and is not configurable.

The clips entering one chapter SHALL be appended after the clips that chapter already lists. Among
themselves they SHALL be in the sort rule's order (event-reconcile, "Clips enter a document in the
configured sort order"), whichever folders they came from.

#### Scenario: First scan seeds a document

- **WHEN** `render` runs on an event with no `reel.yaml`
- **THEN** a document is seeded from folder structure and the event renders

#### Scenario: Newly added clip is adopted, not dropped

- **WHEN** an event's `reel.yaml` lists `s1710001.mp4` in its default chapter, and `s1710002.mp4` appears in
  the event folder
- **THEN** `render` appends `s1710002.mp4` to the default chapter and includes it in the output

#### Scenario: A new clip joins its folder's chapter

- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `s1710001.mp4` in its default chapter
  and `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` in `Kvällen`, and `Kvällen/s1710004.mp4` appears on
  disk
- **THEN** after `render`, `reel.yaml` lists `Kvällen` as `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4`,
  `Kvällen/s1710004.mp4` and the default chapter as `s1710001.mp4` alone, and the movie's `Kvällen` chapter
  plays the three clips

#### Scenario: A folder without a chapter falls back to the default chapter

- **WHEN** an event's `reel.yaml` names only the default chapter, listing `s1710001.mp4`, and
  `Dag 2/s1710002.mp4` and `Dag 2/s1710003.mp4` appear on disk
- **THEN** `render` appends both to the default chapter after `s1710001.mp4`, in the sort rule's order, and
  `reel.yaml` names no `Dag 2` chapter

#### Scenario: Clips from two folders entering one chapter are ordered together

- **WHEN** the sort rule is `datetime`, and an event's `reel.yaml` names only `Kvällen`, listing
  `Kvällen/a.mp4`. Then `b.mp4` (modified 12:00) appears in the event folder and `Dag 2/c.mp4` (modified
  11:00) in a folder with no chapter.
- **THEN** `render` adds the default chapter after `Kvällen`, listing `Dag 2/c.mp4` then `b.mp4`, and leaves
  `Kvällen` as `Kvällen/a.mp4` alone

#### Scenario: A document that names no chapters is seeded like a new event

- **WHEN** an event's `reel.yaml` holds only `metadata`, as `import` writes a legacy document or as a
  metadata-only first save from the GUI writes it, and the event holds `s1710001.mp4` in its folder and
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4` in a subfolder
- **THEN** `render` writes the default chapter listing `s1710001.mp4`, then a `Kvällen` chapter listing
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4` in the sort rule's order, which are the chapters a first
  render of the event without a `reel.yaml` seeds, and the movie has both chapters
- **AND** `reel.yaml` keeps its `metadata` as written

#### Scenario: A clip adopted earlier stays where it is

- **WHEN** an event's `reel.yaml` lists `Kvällen/s1710004.mp4` in its default chapter, as an earlier
  render's adoption left it, while its `Kvällen` chapter lists `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, and no clip is NEW
- **THEN** `render` adopts nothing and does not rewrite `reel.yaml`, and `Kvällen/s1710004.mp4` still plays in
  the default chapter

#### Scenario: A GUI render adopts as the CLI does

- **WHEN** the operator presses Render on `2024-08-20 - Två kapitel - Tjörn` while `Kvällen/s1710004.mp4` is
  NEW, and the worker runs the job
- **THEN** the worker writes the `reel.yaml` that `render` would write, with `Kvällen/s1710004.mp4` third in
  `Kvällen`

#### Scenario: Missing clip is reported, not silently removed

- **WHEN** a `reel.yaml` references a clip that no longer exists on disk
- **THEN** the system reports the `MISSING` clip and does not remove it from the document
