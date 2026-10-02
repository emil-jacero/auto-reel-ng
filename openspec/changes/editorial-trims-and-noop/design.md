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

### 2. Cut spans: each desired span takes an existing node; edit differing ones in place

**Context**: `_apply_trims` must change as few lines as the user's edit does, and keep each span's comments
with that span, the same promise the identity lists already make (`_rewrite_identity_list`).

**Explored**: (a) pair by index and mutate every pair; simple, but removing a middle span moves later
content into earlier nodes while the comments stay behind, attaching `# shake` to the wrong span. (b) match
by exact content only, rebuild the rest fresh; keeps style for unchanged spans but still reformats the one
edited span (the bug's second half). (c) align with `difflib.SequenceMatcher`; keeps order but, for a
removal plus an edit in one save, pairs the wrong spans by index inside the differing run (found while
implementing: the edit landed on the span before the removed one). (d) match each desired span to an
existing node by value, then by shared bound, then in order; keep, edit in place, add or drop.

**Decision**: (d).

1. Normalise each span to `(float(in), float(out), reason)`; the comparison is numeric, so `0 == 0.0` and a
   JSON float never counts as a change. A non-number stays comparable (by `repr`), so a bad value still
   reaches `build_document`'s own validation.
2. Each desired span, in order, takes the first unclaimed existing span of equal value; the spans left take,
   by the same rule, one with the same `in`, then one with the same `out` (a bound that was nudged); what
   remains pairs in order, as an edit. A node is claimed at most once. An equal span keeps its node
   untouched (flow style, scalar spelling, comments); a paired node is edited in place, setting `in`/`out`
   only if numerically different and `reason` added, changed or removed; a span with no node to take is
   fresh (`_trim_entry`); an unclaimed node is dropped.
3. The list keeps its `CommentedSeq` (and the key's own comment). Comments follow the node, wherever it
   lands: a retained, moved or in-place-edited span keeps its end-of-line comment and the own-line comments
   above it; a dropped span takes only its own; a fresh span has none; lines after the last span stay at the
   end. ruamel files the comments of a flow-style span in `seq.ca.items` by index (the lines between two
   entries in the earlier entry's token), and those of a block-mapping span on its last key. The identity
   lists' helpers were generalised for this rather than copied: `_entry_comments` is now a keyed view of
   `_list_comments` (entries in order), and `_rewrite_identity_list` is `_refill_list` plus the identity
   bookkeeping. For a block-mapping entry the lines after it are lifted from, and written back to, its last
   key (`_node_tail` / `_set_node_tail`); its own end-of-line comment never leaves the node. A flow-style
   span with no end-of-line comment has the lines after it filed differently: as the *pre* comment of the
   entry below it (slot 1 of its row), or after the last entry as the list's end comment. `_list_comments`
   reads both (the pre lines join the previous entry's trailing lines as the `above` of the entry below),
   so an own-line comment between two bare flow spans survives an append, a removal or an edit. When
   writing back, the lines after a bare flow span go in the next entry's pre slot if that entry is a block
   mapping (a token on the flow span itself there makes ruamel emit the block span on one line), else on
   the span's own token as before.
4. A span mapping with no `reason` and a desired `reason: None` stays reason-less; a fresh mapping omits
   `reason` when `None` (as `_trim_entry` does).
5. A fresh span is written in the style of the span before it (flow `{in: 30, out: 31}` after a flow span,
   a block mapping after a block one). Besides matching the hand-written list, this avoids a ruamel emitter
   fault: a block mapping appended after flow-style spans under a header comment is emitted on one line
   (`- in: 30.0 out: 31.0`), which does not parse. A hand-authored list that mixes the two styles under a
   header comment already trips that fault in `document_to_data`, before this change.

   The fault has more triggers than an appended span: a header comment, a flow span that carries a comment
   first, and a block span later, whatever put them in that order. A reorder or removal can build that
   shape from a list that did not have it (the new first span is the flow one). So after refilling a
   cut list `_apply_trims` dumps a copy of the clip entry and loads it back; if ruamel cannot read what it
   wrote, the list's header is given up (the lines above the new first span), and if that is not enough
   the list is rebuilt plain, without comments (what main did for every list change). Both are last
   resorts for a shape ruamel cannot emit; a list in one style never reaches them. A hand-authored file
   already in that shape cannot be re-emitted at all: `apply_editorial_write` turns ruamel's `YAMLError`
   into a `ReelError` (the PUT route answers 400, the file is untouched) rather than leaking a 500.
   Separately, ruamel drops on load an own-line comment between a bare flow span and a flow span that has
   an end-of-line comment; that comment is not in the loaded document, so no write can keep it.
6. If every desired span took its own node, in order (only in-place edits), `entry["trims"]` is not
   refilled, so comments stay where they are; an unchanged list is not touched at all (today's behaviour,
   kept).

**Rationale**: the user's mental model of an edit is "this span moved, that one stays"; matching by value
gives that for the common cases (edit one bound, add, remove, remove-and-edit, reorder, split) with the
stdlib only. A nudged span keeps its comment because it is paired by its other bound; a span whose two
bounds both changed is paired in order, which is the right call when nothing else identifies it.

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

- The one new failure is ruamel being unable to re-emit a document (Decision 2.5): `ReelError`, nothing
  written. Validation, `require_processable` and the filesystem errors keep their types and
  order; the no-op return happens after validation and before any file operation.
- Re-running a save: the first real change writes, every identical repeat is a no-op (no write, no sweep).
  `--force` has no meaning here. A worker restart is unaffected (the write never touches jobs).
- Interrupted write: `.reel.yaml` is untouched until the rename; a leftover temporary is removed by a later
  write once it is 24 hours old.
- Concurrency: two simultaneous saves each use a unique temporary; the sweep's age floor makes it
  irrelevant to either.

## Risks / Trade-offs

- [A span whose bounds both change is paired in order, so its comment may stay on the wrong span when
  several change at once] -> accepted; nothing else identifies such a span, and a single edit is exact.
- [Comment-token surgery on spans is fiddly in ruamel] -> reuse the identity-list token-splitting code;
  tests cover eol comment, own-line comment above, a comment between spans, and the last-span trailing
  lines before and after each operation.
- [The gate renames or reshapes the comment helpers] -> implement after it merges; the task list names the
  reuse, not a function signature.
- [A skipped write leaves a legacy-format file as is] -> deliberate, stated in Decision 1; the importer is
  the migration path.
- [Sweep deletes something a user wanted] -> only strictly engine-named hidden files older than a day, never
  read as the document.
