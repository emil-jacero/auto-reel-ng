## Context

`apply_editorial_write(event_dir, desired_data)` (decision D-E1) loads the event's document, merges the
desired state onto its ruamel round-trip structure, validates, and calls `write_document`. Two facts shape
the fixes:

- `write_document` always dumps through `reel/writer._yaml()` with
  `indent(mapping=2, sequence=4, offset=2)`. A document loaded from foreign indentation therefore dumps
  differently from its bytes even with no edit. Checked on main (6a7fe16, re-checked on 651627d): dumping a document loaded from
  4-space/un-indented text, and dumping the document `apply_editorial_write` builds from its unmodified
  state, give identical strings (the canonical dump is idempotent, comments included).
- `_apply_trims` already skips the rewrite when `_trims_equal` (compares `in`/`out`/`reason`; Python
  `0 == 0.0`) says the whole list is unchanged. Any difference at all replaces the list with a fresh
  `CommentedSeq` of block `CommentedMap`s, which is what loses style, comments and scalar spelling. The
  `in: 0` to `0.0` effect is that replacement taking the API's float.

**Gate (merged).** `editorial-chapter-comments` is on origin/main (651627d) and edits the same file:
it pairs renamed chapters with existing nodes, keys comments by node identity and re-attaches trailing
comment tokens, and re-emits stored quoting for retained identity entries. This change touches none of
`_apply_chapters`, `_rewrite_identity_list`, `_apply_ignore`; it edits `apply_editorial_write` (a few lines
before the `write_document` call), `_apply_trims`, `_trims_equal`, and `_trim_entry`. Implementation starts from that
origin/main and reuses the gate's comment-lifting helpers (`_entry_comments`, `_render_tokens`,
`_header_text`, `_set_trailing`; see Decision 2) instead of copying them.

## Goals / Non-Goals

**Goals:**

- A save that changes nothing leaves the file's bytes and mtime alone, whatever its indentation.
- A save that changes one span of a cut list changes only that span's lines.
- A killed write's hidden temporary does not live forever.

**Non-Goals:**

- Foreign-indent preservation on a real change; float normalisation; overlap policy; the thumbnail temp
  sweep. See the proposal.

## Decisions

### 1. Unchanged means equal canonical dumps, checked only when a `reel.yaml` exists

**Context**: `apply_editorial_write` must know whether anything changed without comparing against file
bytes, which a foreign style never matches.

**Explored**: (a) compare the new dump with the file's bytes; false "changed" for every foreign file, which
is the bug. (b) compare `editorial_hash` of old and new; blind to comments and key order, so a
comment-only difference (not reachable today, but cheap to get wrong) would be dropped. (c) compare
`dumps_document(current)` with `dumps_document(document)`, both through the one canonical dumper.

**Decision**: (c). After `build_document` and the event-processable check, and only when `reel_path` existed,
return `document` without calling `write_document` if the two canonical dumps are equal. The validation and
`require_processable` run first, so a state that would be refused is still refused. An event without a
`reel.yaml` always writes (the scenario "Event without a reel.yaml is written fresh" keeps holding, even for
an empty state).

**Rationale**: the dump is the single definition of "what we would write", comments and key order included,
so nothing a write could change is missed. Cost is two dumps of a small document.

**Legacy files.** A version-less (auto-reel legacy) `reel.yaml` loads through the importer, and its dump
equals the dump of the same unmodified state. Such a file is therefore left as it is by an unmodified save,
and converted to `version: 0` only by a save that changes something (as before) or by `auto-reel import`.
This is deliberate: "an unmodified save writes nothing" has no exception, and legacy files stay readable
through the same importer on every load.

**Consequence for callers.** The returned document is the merged one, as today. The PUT route echoes it and
its `ETag` (`editorial_hash`) is unchanged, so the existing scenario "An unmodified save returns the tag it
was given" still holds. `reel.yaml`'s mtime no longer moves on a no-op; nothing reads that mtime
(staleness hashes typed fields and clip signals).

### 2. Cut spans: align, keep retained nodes, edit differing ones in place

**Context**: `_apply_trims` must change as few lines as the user's edit does, and keep each span's comments
with that span, the same promise the identity lists already make (`_rewrite_identity_list`).

**Explored**: (a) pair by index and mutate every pair; simple, but removing a middle span moves later
content into earlier nodes while the comments stay behind, attaching `# shake` to the wrong span. (b) match
by exact content only, rebuild the rest fresh; keeps style for unchanged spans but still reformats the one
edited span (the bug's second half). (c) align old and new spans, then keep, edit in place, insert or
remove.

**Decision**: (c).

1. Normalise each span to `(float(in), float(out), reason)`; the comparison is numeric, so `0 == 0.0` and a
   JSON float never counts as a change.
2. Align current and desired normalised lists with `difflib.SequenceMatcher(autojunk=False)`. `equal`
   blocks retain the existing `CommentedMap` node untouched (flow style, scalar spelling, comments).
   Within a `replace` block, spans pair by index: a paired node is mutated in place, setting `in`/`out`
   only if numerically different and `reason` added, changed or removed; surplus desired spans become fresh
   block mappings (`_trim_entry`), surplus current spans are dropped. `insert` makes fresh mappings;
   `delete` drops nodes.
3. The list keeps its `CommentedSeq` (and the key's own comment). Comments follow the node: a retained or
   in-place-edited span keeps its end-of-line comment and the own-line comments above it; a dropped span
   takes only its own; a fresh span has none; lines after the last span stay at the end. ruamel files
   these in `seq.ca.items` by index and puts the lines between two entries into the earlier entry's token,
   so the list's comment tokens are rebuilt from per-node comments exactly as `_rewrite_identity_list` does
   for identities. The helper that lifts them (`_entry_comments`) is keyed by identity scalar today; if the
   gate leaves it so, add an index-keyed variant beside it that shares the token-splitting code rather than
   duplicating it.
4. A span mapping with no `reason` and a desired `reason: None` stays reason-less; a fresh mapping omits
   `reason` when `None` (as `_trim_entry` does).
5. If the aligned result equals the current list node for node, `entry["trims"]` is not assigned at all, so
   an unchanged list keeps its bytes (today's behaviour, kept).

**Rationale**: the user's mental model of an edit is "this span moved, that one stays"; alignment gives
that for the common cases (edit one bound, add, remove, split) without a diff library beyond the stdlib.
An in-place edit keeps the comment at that position, which is the right call when the user nudged a span's
bound; it is wrong only for a pure reorder, where the `replace` block pairs by index and each span's
comment stays at its position. That limitation is accepted (spans are ordered cuts; the GUI does not
reorder them) and written in the spec scenarios.

### 3. Sweep: after a successful replace, strict name, age floor, best effort

**Context**: `write_document` names its temporary `.reel.yaml.<uuid4().hex>.tmp` and cleans up only on
exceptions it survives.

**Decision**: after `os.replace` succeeds, list the target's folder and `unlink` every entry that is a
regular file (not a symlink), whose name matches `^\.<name>\.[0-9a-f]{32}\.tmp$` for the target's file
name, and whose `st_mtime` is older than 24 hours (module constant, no config key). `OSError` while
listing, statting or unlinking is swallowed and logged at debug level.

**Rationale**: housekeeping must never fail or undo a save that already succeeded, and it is not editorial
data, so this is not a fabrication or a loud-failure matter (Principles I and II): nothing the user wrote is
lost, only abandoned scratch files. It runs after the replace so a refused or failed write (read-only
folder, disk error) touches nothing, as the existing scenarios require. The 24-hour floor and the strict
`[0-9a-f]{32}` pattern keep a concurrent writer's live temporary and any user file (`.reel.yaml.bak`,
`.reel.yaml.1234.tmp`) safe. A no-op save does not sweep (it does not write); the next real write does.
Cost: one `listdir` of one event folder per write.

### 4. Where the delta lives

Three ADDED requirements in `editorial-write`, none MODIFIED. The gate rewrites "Comments and key order
survive an editorial write" and its scenario "A renamed chapter is a new chapter"; copying that requirement
here would make the later archive conflict or silently revert the gate's text. The new rules sit beside
the atomic-write requirement because they belong to how the file is persisted.

## Failure behavior and idempotency

- Nothing new raises. Validation, `require_processable` and the filesystem errors keep their types and
  order; the no-op return happens after validation and before any file operation.
- Re-running a save: the first real change writes, every identical repeat is a no-op (no write, no sweep).
  `--force` has no meaning here. A worker restart is unaffected (the write never touches jobs).
- Interrupted write: `.reel.yaml` is untouched until the rename; a leftover temporary is removed by a later
  write once it is 24 hours old.
- Concurrency: two simultaneous saves each use a unique temporary; the sweep's age floor makes it
  irrelevant to either.

## Risks / Trade-offs

- [Alignment leaves a comment on the wrong span after a pure reorder] -> accepted and specified; spans are
  not reordered by any client today.
- [Comment-token surgery on spans is fiddly in ruamel] -> reuse the identity-list token-splitting code;
  tests cover eol comment, own-line comment above, a comment between spans, and the last-span trailing
  lines before and after each operation.
- [The gate renames or reshapes the comment helpers] -> implement after it merges; the task list names the
  reuse, not a function signature.
- [A skipped write leaves a legacy-format file as is] -> deliberate, stated in Decision 1; the importer is
  the migration path.
- [Sweep deletes something a user wanted] -> only strictly engine-named hidden files older than a day, never
  read as the document.
