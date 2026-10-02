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

### Requirement: An editorial write that changes nothing leaves reel.yaml untouched
When the event already has a `reel.yaml` and the desired state, merged onto it and validated, yields the
same document the file already holds, the operation SHALL return that document without writing. "The same
document" means the document the writer would emit for the merged state is identical, comments and key
order included, to the one it would emit for the loaded file. The file's bytes, its modification time and
its directory entry MUST be left as they were, and no temporary file may be created. This holds whatever
indentation the file was authored in: a file written in a style other than the engine's canonical one
(2-space mappings, 4-space sequences, offset 2) stays exactly as authored when a save changes nothing.

Validation (schema, cross-references, the event rule on date and title) SHALL still run first, so a state
that would be refused is refused whether or not it differs from the file. An event without a `reel.yaml`
SHALL always be written, even for an empty desired state. A save that changes anything SHALL write the
whole document in the canonical style, as it does today; keeping a foreign style through a real change is
not required.

A version-less (auto-reel legacy) `reel.yaml` that a save leaves unchanged SHALL stay as it is; it is
converted to `version: 0` by a save that changes something, or by `auto-reel import`.

The returned document, and the editorial-read `ETag` computed from it, SHALL be the same whether or not a
write happened.

#### Scenario: A foreign-indented file survives an unmodified save
- **WHEN** the event `2024/2024-06-21 - Midsommar` has a hand-authored `reel.yaml` with 4-space mappings, an
  un-indented `-   name: ''` chapter sequence and `title: Midsommar   # keep`, and its current state is
  applied unmodified
- **THEN** `reel.yaml` is byte-for-byte unchanged, its modification time is unchanged, and no hidden
  temporary file was created in the event folder

#### Scenario: PUT of the document just read changes nothing on disk
- **WHEN** a client reads `GET /api/v1/events/{event_id}/reel` for that foreign-indented event and PUTs the
  body back with `If-Match` set to the `ETag` it received
- **THEN** the response is 200 echoing the same document with the same `ETag`, and `reel.yaml` is
  byte-for-byte unchanged

#### Scenario: A real change to a foreign-indented file is written in the canonical style
- **WHEN** the same event receives a desired state that changes only the title
- **THEN** the persisted file carries the new title and is written in the canonical style, with every
  comment and the key order kept

#### Scenario: An invalid unmodified-looking state is still refused
- **WHEN** a desired state equal to the file's content except that a chapter references a clip the document
  does not define is applied
- **THEN** the operation fails loudly naming the problem, as before, and the file is unchanged

#### Scenario: An empty state for an event with no reel.yaml still creates one
- **WHEN** the event `2024/2024-06-21 - Trip`, which has no `reel.yaml`, receives an empty desired state
- **THEN** a `reel.yaml` declaring `version: 0` is written

#### Scenario: An unmodified save leaves a legacy file alone
- **WHEN** an event's `reel.yaml` is in the auto-reel legacy format (no `version` key, a top-level
  `title`) and its current state is applied unmodified
- **THEN** the file is byte-for-byte unchanged, and a later save that changes the title writes it as
  `version: 0`

### Requirement: A changed cut list edits only the spans that differ
When a clip's desired `trims` differ from those on disk, the operation SHALL change only the spans that
differ and leave every other span exactly as authored. Spans are compared by value: `in` and `out` as
numbers (so an integer `0` and a float `0.0` are equal), and `reason`.

- **A span whose value is unchanged SHALL keep its form.** Its flow or block style, the spelling of its
  numbers (`in: 0` stays `in: 0`, never `0.0`), its end-of-line comment at its column, and the own-line
  comments and blank lines directly above it are persisted as they were, wherever the span lands in the
  list.
- **A span that is edited SHALL be edited in place.** A desired span is matched to the existing span of
  equal value, else one with the same `in`, else one with the same `out`, else the next one left, so a
  span with one bound changed is the same span. Only the keys whose value differs are rewritten (a
  key whose value is numerically equal keeps its stored spelling); a `reason` that is added, changed or
  removed changes only that key. The span keeps its style and its comments.
- **A removed span SHALL take only its own comments with it**, and no other span's comment is lost.
- **An added span SHALL carry no comment** and is written with `in`, `out` and, when set, `reason`, in the
  style of the span before it: a flow mapping after a flow-style span, a block mapping after a block one.
- **Comment lines after the last span SHALL stay at the end of the list.**
- **A list that is unchanged by value SHALL be persisted exactly as it was.**

Changing a clip's other properties (`title`, `rotate`, `exclude`) leaves its `trims` untouched. The
operation leaves overlapping or adjacent spans exactly as given: whether cuts overlap is the renderer's
concern, not the writer's, and the engine continues to treat overlapping cuts as their union. A span that
moves takes its comments with it.

None of this changes the editorial state a write persists, so it never moves the event's staleness verdict
or its editorial-read `ETag`.

#### Scenario: Editing one span leaves the others as authored
- **WHEN** a clip `00400.mp4` has `trims:` holding `- {in: 0, out: 3.2, reason: black}  # black start` and
  `- {in: 10, out: 12}  # shake`, and a desired state changes only the second span's `out` to 13
- **THEN** the first span line is persisted byte-for-byte as written, flow style and `# black start`
  included, and the second span keeps its flow style and `# shake` with `out` now 13

#### Scenario: An API float does not respell an unchanged number
- **WHEN** the same clip receives its trims over the API as JSON, so `in` arrives as `0.0` and `10.0`, with
  only the second span's `out` changed
- **THEN** the first span still reads `in: 0` in the persisted file, and the second reads `in: 10`

#### Scenario: Removing a middle span drops only its comment
- **WHEN** a clip has three commented spans `# first`, `# second`, `# third` and a desired state removes the
  second
- **THEN** the persisted list holds the first and third spans, each with its own comment, and `# second` is
  gone

#### Scenario: A moved span takes its comments with it
- **WHEN** a desired state swaps the first and third of three commented spans
- **THEN** each span is persisted with its own end-of-line comment and the own-line comments that were above
  it, at its new position

#### Scenario: Removing one span while editing another edits the right one
- **WHEN** a clip has three commented block-style spans and a desired state removes the second and changes
  the third span's `out`
- **THEN** the first span is persisted as written, the third span carries the new `out` and its own
  comment, and the second span and its comments are gone

#### Scenario: Adding a span leaves the existing ones untouched
- **WHEN** a desired state appends a third span `{in: 20, out: 22, reason: manual}` to a clip with two
  commented flow-style spans
- **THEN** the two existing span lines are persisted unchanged, and the new span is a flow mapping, like
  the spans before it, with no comment

#### Scenario: Changing another property leaves the trims alone
- **WHEN** a desired state changes only a clip's `title` while its flow-style commented trims are
  unchanged
- **THEN** the trims lines are persisted byte-for-byte as written

#### Scenario: A reason added to one span touches only that span
- **WHEN** a desired state adds `reason: manual` to the second of two spans and changes nothing else
- **THEN** only the second span's mapping changes, and the first span's line and comment are unchanged

#### Scenario: Overlapping spans are written as given
- **WHEN** a desired state lists the spans `{in: 5, out: 9}` and `{in: 7, out: 12}` on one clip
- **THEN** both are persisted unchanged and nothing is merged, split or refused at write time

### Requirement: Writing reel.yaml sweeps abandoned temporaries
After `reel.yaml` has been replaced successfully, the writer SHALL remove from the same folder the hidden
temporary files an earlier write left behind: regular files, not symbolic links, named exactly
`.reel.yaml.<32 lowercase hex digits>.tmp`, whose modification time is more than 24 hours old. It MUST
NOT remove a younger one (a concurrent write in progress) or any file with another name, including other
hidden `.reel.yaml.*` files. Removing one is housekeeping: a failure to list, inspect or remove SHALL NOT
fail or undo the write that already succeeded.

A write that fails or is refused SHALL NOT sweep. A save that changes nothing writes nothing and so does
not sweep. The rule applies to every write of a `reel.yaml` through the writer, the API's and the
`auto-reel import` command's alike.

#### Scenario: A day-old temporary left by a killed write is removed
- **WHEN** the event folder holds `.reel.yaml.0123456789abcdef0123456789abcdef.tmp` last modified two days
  ago, and a save that changes the title succeeds
- **THEN** that file is gone afterwards and `reel.yaml` holds the new title

#### Scenario: A young temporary is left alone
- **WHEN** the folder holds `.reel.yaml.fedcba9876543210fedcba9876543210.tmp` modified a minute ago and a
  save succeeds
- **THEN** that file is still there

#### Scenario: Other hidden files are never touched
- **WHEN** the folder holds a three-day-old `.reel.yaml.bak`, `.reel.yaml.1234.tmp` and
  `.other.0123456789abcdef0123456789abcdef.tmp`, and a save succeeds
- **THEN** all three are still there

#### Scenario: A refused write sweeps nothing
- **WHEN** a save on an event whose folder is mounted read-only is refused, and an old temporary sits in it
- **THEN** the operation raises naming the read-only error, and the old temporary is still there

#### Scenario: A sweep that cannot remove a file does not fail the save
- **WHEN** a save succeeds but the old temporary cannot be removed (the folder forbids the removal)
- **THEN** the save is reported successful, and the new `reel.yaml` is in place
