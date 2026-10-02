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
- **Within a changed list, each retained entry SHALL keep its own comments and its quoting:**
  - its end-of-line comment, at the column it was written at
  - the own-line comments and blank lines directly above it, back to the previous entry or the list's start
  - the way its scalar was written: an entry stored as `"a.mp4"` or `'a.mp4'` stays double- or
    single-quoted (the quotes are part of how the author wrote it, and are not needed to read it back)

  They stay with the entry wherever it lands, including when a clip moves to another existing chapter. An
  added entry, and an entry whose stored spelling differs from its identity (`./a.mp4`), is written plain.
- **A removed entry SHALL take only its own comments with it.** No other entry's comment is lost.
- **An added entry SHALL carry no comment.**
- **Comment lines after a list's last entry SHALL stay at the end of that list.** They introduce what follows
  the list, whichever entry ends up last, and they stay after the list when it is left empty. The lines
  after the last chapter's clips introduce what follows the chapters, so when chapters are appended they
  move to the end of the new last chapter's clips.
- **A list written in flow style (`[a.mp4, b.mp4]`) SHALL be persisted in block style when it must carry an
  entry's comment**, and SHALL otherwise keep its style.

Chapters are matched to the document's existing chapters in two steps:

- **By name first.** A desired chapter keeps the existing chapter of the same name.
- **Then by clips, for a name that matches nothing.** An existing chapter that no desired chapter matched by
  name is *unclaimed*. A desired chapter with at least one clip and no name match SHALL take the unclaimed
  existing chapter whose clip list equals its own, in the same order; failing that, the unclaimed existing
  chapter that shares the most clip identities with it (at least one; a tie goes to the earlier existing
  chapter). Each existing chapter is taken at most once, and the pairing is deterministic: exact matches
  first, then the largest overlaps, ties broken by desired order, then by existing order. A chapter so
  paired is the existing chapter **renamed**: it keeps its name line's end-of-line comment, its clips'
  comments and quoting, and the style of its lists, whether or not its clips changed in the same write.

A desired chapter that takes no existing chapter is written fresh, and an existing chapter that no desired
chapter takes is dropped with its own comments.

The own-line comments and blank lines **directly above a chapter** stay with that chapter wherever it lands:
swapped, moved, renamed, or left in place while another chapter is removed. This holds wherever the file
holds them: after the previous chapter's last clip, after that chapter's flow clip list, or between
chapters generally. A removed chapter takes only the lines directly above itself. The lines between
`chapters:` and the first chapter are the lines above the first chapter. The lines after the last chapter's
clips stay at the end of the chapters, after whichever chapter ends up last, as before.

None of this changes the editorial state a write persists, so it never moves the event's staleness verdict
or its editorial-read `ETag`.

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

#### Scenario: A renamed chapter keeps its comments
- **WHEN** a commented chapter `Reception` lists `- a.mp4  # keep me: the best shot`, then an own-line
  `# before b`, then `- b.mp4`, and a desired state renames it to `Party`, keeping its clips
- **THEN** `Party` is persisted with `- a.mp4  # keep me: the best shot` and `# before b` above `- b.mp4`,
  its name line's own comment, and its list style; only the name differs, and an untouched neighbouring
  chapter's lines are unchanged

#### Scenario: A chapter renamed and edited in one save keeps its comments
- **WHEN** a desired state renames `Kvällen` (clips `Kvällen/b.mp4  # sunset`, `Kvällen/c.mp4`) to `Natten`
  and gives it the clips `Kvällen/b.mp4`, `Kvällen/c.mp4` and `Kvällen/d.mp4`
- **THEN** `Natten` shares two clips with `Kvällen` and no other chapter is unclaimed, so it is the renamed
  `Kvällen`: `Kvällen/b.mp4  # sunset` keeps its comment and `Kvällen/d.mp4` is added without one

#### Scenario: A renamed chapter with different clips pairs with the one it overlaps most
- **WHEN** the chapters `A` (clips `a1.mp4`, `a2.mp4`) and `B` (clips `b1.mp4`, `b2.mp4`, `b3.mp4`) are
  renamed in one save to `X` (clips `b1.mp4`, `b2.mp4`) and `Y` (clips `a1.mp4`, `a2.mp4`)
- **THEN** `X` is persisted on `B`'s node and `Y` on `A`'s, so each keeps its own clips' comments, and no
  existing chapter is taken twice

#### Scenario: A chapter with no clips is not paired
- **WHEN** a desired state renames an existing chapter with no clips to a new name
- **THEN** the new name is persisted as a fresh chapter and the old one is dropped, as for any name that
  matches nothing

#### Scenario: A renamed chapter is a new chapter
- **WHEN** a desired state replaces the chapter `Kvällen` with a chapter `Natten` whose clips share no clip
  with `Kvällen` or any other unclaimed existing chapter
- **THEN** `Natten` is persisted as a new chapter with those clips and no comments, and `Kvällen` is
  dropped with its own comments, as before this requirement

#### Scenario: A comment between chapters follows the chapter below it through a swap
- **WHEN** the chapters `A` (`clips: [a.mp4]`, flow), `B` and `C` are separated by own-line comments
  `# --- the B section ---` above `B` and `# --- the C section ---` above `C`, and a desired state
  orders them `C`, `B`, `A`
- **THEN** each comment is persisted directly above the chapter it introduced, so `# --- the C section ---`
  is above `C`, now first, and `# --- the B section ---` stays above `B`

#### Scenario: Removing a chapter drops only the lines above it
- **WHEN** a desired state removes the chapter `B`, which has `# --- the B section ---` above it, from the
  chapters `A`, `B`, `C` (with `# --- the C section ---` above `C`)
- **THEN** `# --- the B section ---` is gone, `# --- the C section ---` is persisted directly above `C`, and
  every comment in `A` and `C` is retained

#### Scenario: Removing the first chapter keeps the comment above the next one
- **WHEN** a desired state removes the chapter `A` from `A` and `B`, where `# --- the B section ---` follows
  `A`'s flow clip list and introduces `B`
- **THEN** `# --- the B section ---` is persisted directly above `B`, which is now the first chapter

#### Scenario: The lines after the last chapter stay after the last chapter
- **WHEN** `# dismissed clips` follows the last chapter's clips, and a desired state removes that chapter
- **THEN** `# dismissed clips` is persisted after the chapter that is now last

#### Scenario: Retained entries keep their quotes
- **WHEN** a chapter lists `- "a.mp4"` and `- 'b.mp4'`, and a desired state appends `c.mp4`
- **THEN** the persisted list reads `- "a.mp4"`, `- 'b.mp4'`, `- c.mp4`, each with the quoting it had

#### Scenario: A quoted clip moved to another chapter keeps its quotes
- **WHEN** a desired state moves `- "a.mp4"  # first` from the root chapter into the existing chapter `Kvällen`
- **THEN** `Kvällen` lists `- "a.mp4"  # first` with both its quotes and its comment

#### Scenario: A quoted ignore entry keeps its quotes
- **WHEN** an `ignore` list holds `- "junk.mp4"  # never render` and a desired state adds `ny.mp4`
- **THEN** the persisted list reads `- "junk.mp4"  # never render` and `- ny.mp4`

#### Scenario: Event without a reel.yaml is written fresh
- **WHEN** the operation applies a desired state to an event that has no `reel.yaml` on disk
- **THEN** a valid `reel.yaml` is created from the typed fields in canonical order

## ADDED Requirements

### Requirement: An editorial write does not mistake an unreadable event for an empty one
The operation SHALL decide whether an event already has a `reel.yaml` by examining the file itself, and
SHALL treat only a file that is absent (or an event path that is not a directory) as "no document yet". An
event folder the process may not search, or a `reel.yaml` it may not examine, SHALL raise the permission error
loudly naming the path and write nothing, instead of being treated as an event with no document and
fabricating one from the folder name.

#### Scenario: An unsearchable event folder refuses the write
- **WHEN** an editorial write targets an event folder whose `reel.yaml` cannot be examined because the folder
  has no search permission for the process
- **THEN** the operation raises a permission error naming the path, and nothing is created or replaced

#### Scenario: An event without a reel.yaml is still written fresh
- **WHEN** an editorial write targets a searchable event folder that has no `reel.yaml`
- **THEN** a valid `reel.yaml` is created from the typed fields, as before
