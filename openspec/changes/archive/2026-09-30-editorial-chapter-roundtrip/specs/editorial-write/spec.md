## MODIFIED Requirements

### Requirement: Comments and key order survive an editorial write
The operation SHALL apply the desired state onto the document's loaded round-trip structure so that
persisting preserves the author's comments and key order — only the lines that actually changed may differ.
It MUST NOT serialize from a mapping constructed out of the request/desired state alone, which would emit a
structure stripped of comments. For an event with no `reel.yaml` yet (no loaded structure), the operation
SHALL fall back to building the document from its typed fields.

This holds for the entries of a list as well as for mapping keys. It applies to each chapter's ordered
clips and to the `ignore` list:

- **An unchanged list SHALL be persisted exactly as it was on disk.** A list is unchanged when the desired
  entries equal its entries as written on disk, in the same order; a chapter must also keep its name. Its
  lines keep every comment and blank line, byte for byte. An entry written in a non-canonical form, such as
  `./a.mp4`, differs from its identity `a.mp4`, so its list counts as changed.
- **Within a changed list, each retained entry SHALL keep its own comments:**
  - its end-of-line comment, at the column it was written at
  - the own-line comments and blank lines directly above it, back to the previous entry or the list's start

  They stay with the entry wherever it lands, including when a clip moves to another existing chapter.
- **A removed entry SHALL take only its own comments with it.** No other entry's comment is lost.
- **An added entry SHALL carry no comment.**
- **Comment lines after a list's last entry SHALL stay at the end of that list.** They introduce what follows
  the list, whichever entry ends up last, and they stay after the list when it is left empty. The lines
  after the last chapter's clips introduce what follows the chapters, so when chapters are appended they
  move to the end of the new last chapter's clips.
- **A list written in flow style (`[a.mp4, b.mp4]`) SHALL be persisted in block style when it must carry an
  entry's comment**, and SHALL otherwise keep its style.

Chapters themselves are matched by name as before: a chapter whose name is new is written fresh, and a
chapter absent from the desired state is dropped. None of this changes the editorial state a write
persists, so it never moves the event's staleness verdict or its editorial-read `ETag`.

#### Scenario: Hand-authored comments survive a save
- **WHEN** a desired state changes only the title of a hand-authored `reel.yaml` containing comments
- **THEN** the persisted file retains every comment and its key order, and differs only in the title line

#### Scenario: Round-tripping an unmodified state is a no-op
- **WHEN** a desired state identical to the document's current state is applied
- **THEN** the persisted file is byte-for-byte unchanged

#### Scenario: An unmodified save keeps a comment on a clip entry
- **WHEN** the event `2024/2024-09-01 - Sommarlov`, whose `reel.yaml` lists `- borttagen.mp4  # MISSING`
  after `s1710002.mp4` and `s1710004.mp4`, receives its current state unmodified
- **THEN** the persisted file is byte-for-byte unchanged, and the `# MISSING` comment is still on the
  `borttagen.mp4` line

#### Scenario: Comments in an untouched chapter survive an edit elsewhere
- **WHEN** a document has a commented root chapter and a named chapter `Kvällen`, and a desired state
  reorders only the clips of `Kvällen`
- **THEN** every line of the root chapter's clip list, comments and blank lines included, is persisted
  unchanged

#### Scenario: A reorder moves each clip's comments with it
- **WHEN** an annotated Sommarlov root chapter holds an own-line `# the opening shot`, then
  `s1710002.mp4   # first`, then an own-line `# before second`, then `s1710004.mp4   # second`, then
  `borttagen.mp4  # MISSING`, and a desired state orders it `borttagen.mp4`, `s1710004.mp4`, `s1710002.mp4`
- **THEN** the persisted list reads `- borttagen.mp4  # MISSING`, then `# before second` directly above
  `- s1710004.mp4   # second`, then `# the opening shot` directly above `- s1710002.mp4   # first`, each
  end-of-line comment at its original column

#### Scenario: A clip moved to another chapter keeps its comment
- **WHEN** a desired state moves `borttagen.mp4  # MISSING` from the root chapter to the start of the
  existing chapter `Kvällen`
- **THEN** `Kvällen` lists `- borttagen.mp4  # MISSING` first, and the root chapter no longer holds it

#### Scenario: Removing a clip drops only its own comment
- **WHEN** a desired state removes `s1710002.mp4` (end-of-line comment `# first`) from the Sommarlov root
  chapter
- **THEN** `# first` and any own-line comment directly above `s1710002.mp4` are gone, and `# before second`
  and `# MISSING` are persisted on their own entries

#### Scenario: An added clip carries no comment
- **WHEN** a desired state inserts `ny.mp4` between two commented clips
- **THEN** `ny.mp4` is persisted on its own line with no comment, and both neighbours keep theirs

#### Scenario: A comment introducing the next chapter stays between the chapters
- **WHEN** an own-line comment `# between chapters` follows the root chapter's last clip, and a desired
  state moves that last clip to the front of the root chapter
- **THEN** `# between chapters` is still persisted after the root chapter's new last clip, directly above
  the next chapter

#### Scenario: An emptied chapter keeps the comment that follows it
- **WHEN** a desired state moves every clip of the Sommarlov root chapter to the existing chapter `Kvällen`,
  and `# between chapters` follows the root chapter's last clip
- **THEN** the root chapter is persisted as `clips: []`, still followed by `# between chapters` directly
  above `Kvällen`, and each moved clip keeps its own comments in `Kvällen`

#### Scenario: A commented clip moved into a flow-style list
- **WHEN** `Kvällen` lists its clips in flow style (`clips: [Kvällen/b.mp4, Kvällen/c.mp4]`), and a desired
  state moves `s1710002.mp4   # first` between them
- **THEN** `Kvällen`'s clips are persisted as a block list, with `- s1710002.mp4   # first` on its own line,
  and the file loads back with the same chapters

#### Scenario: An unmodified ignore list keeps its comments
- **WHEN** a document's `ignore` list holds `- junk.mp4  # never render`, and its current state is applied
  unmodified
- **THEN** the persisted file is byte-for-byte unchanged

#### Scenario: A renamed chapter is a new chapter
- **WHEN** a desired state renames the chapter `Kvällen` to `Natten`, keeping its clips
- **THEN** `Natten` is persisted as a new chapter with those clips and no clip comments, as before this
  requirement

#### Scenario: Event without a reel.yaml is written fresh
- **WHEN** the operation applies a desired state to an event that has no `reel.yaml` on disk
- **THEN** a valid `reel.yaml` is created from the typed fields in canonical order
