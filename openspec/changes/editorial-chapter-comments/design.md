## Context

See proposal.md, section Why. Facts about the code on `origin/main` (d683264) that shape the approach:

- **`_apply_chapters` (`event/editorial.py`)** indexes the existing chapters by `name` into
  `existing_by_name`, `comments` (per clip identity, shared across chapters so a moved clip finds its own) and
  `ends` (per chapter, **keyed by name**). A desired name with no match gets a fresh `CommentedMap`. After the
  loop, it keeps the existing `chapters` sequence only when every old node keeps its place (`in_place`),
  appending new ones; otherwise it assigns `data["chapters"] = rebuilt`.
- **Where ruamel files the lines between two chapters** (checked against the installed ruamel.yaml, as in
  `editorial-chapter-roundtrip`):
  - previous chapter has a **block** clip list: the lines are the tail of its last entry's comment token
    (`clips.ca.items[last][0]`, after the first `\n`), which `_entry_comments(...)[1].trailing` already
    returns
  - previous chapter has a **flow** clip list with a comment after the `]`: the tail of the key's token
    (`chapter.ca.items["clips"][2]`), also `trailing`
  - previous chapter has a **flow** clip list with no comment after the `]`: a *pre-comment of the next
    chapter on the outer sequence*, `chapters.ca.items[i][1]` (a list of tokens, each an unindented comment
    line plus the blank lines after it, with its `column`)
  - after the **last** chapter: the last clip token's tail (block), the key token's tail (flow with a
    comment), or the outer sequence's end comment `chapters.ca.end` (flow without one)
  - between `chapters:` and the first chapter: `data.ca.items["chapters"][3]`, else `chapters.ca.comment[1]`,
    else the key token's tail; this is what `_header_text` / `_key_token_tail` read for a block list
- **The mechanisms to write them back already exist** in the same module: `_set_trailing` (a list's lines
  after its last entry, by style), `_set_header` (the lines between a key and its list).
- **The dumper emits an outer-sequence pre-comment (`seq.ca.items[i] = [None, [CommentToken(text,
  CommentMark(0))], None, None]`) correctly in front of item `i` whatever the previous chapter's list style
  is**, as long as that chapter's own trailing text was cleared. A throwaway prototype of the whole design
  (not committed) reproduced every scenario in the delta spec byte for byte on block, flow and
  flow-with-comment fixtures; the tasks' tests pin the same cases.
- **The previous change recorded both gaps**: "No re-homing of comments when chapters are reordered" and
  "Quote style of retained entries ... Follow-up: refill with the stored scalars".

## Goals / Non-Goals

**Goals:**

- A chapter rename (with or without clip edits in the same save) keeps the chapter's node, so it keeps every
  comment and list style it had.
- A chapter swap, move or removal keeps each remaining chapter's "lines above" with it, and the lines after
  the last chapter after the last chapter.
- A changed list re-emits the stored scalar for every retained entry.
- Re-applying the same desired state afterwards is a byte-for-byte no-op (idempotent).

**Non-Goals:**

- Matching chapters by anything the request does not carry. The request names chapters and their clips; the
  pairing uses only those two facts.
- Guessing for empty chapters, or pairing by position.
- Re-flowing or restyling anything. A foreign layout the loader cannot round-trip byte-stable stays a
  documented limitation.
- Any change to `reel/`: the writer and parser are untouched.

## Research & Decisions

### Pair chapters by clips, after names

**Context**: The request is the complete desired structure (D-E2) and identifies chapters only by `name`. A
rename arrives as "a name that was not there, with some clips that were", which today reads as "drop one
chapter, add another". The GUI's chapter management (D-13) will send exactly this.

**Explored**:
- **(a) A stable chapter id in the request.** It would be exact, but it changes the wire contract and the
  `reel.yaml` schema for a comment-preservation detail (Principle VII).
- **(b) Pair by position.** A rename in place is easy, but a reorder plus a rename would pair wrongly, and
  position says nothing about which comments belong.
- **(c) Pair by clips: exact list first, then by shared clips.** Clips are the one thing a chapter is made
  of, and a clip identity appears in at most one chapter, so overlap is unambiguous evidence.

**Decision**: (c), in `_apply_chapters`, as a small module-private function over the existing nodes and the
desired chapters:
1. By name, as today. Those existing chapters are *claimed*.
2. For each desired chapter with no match and at least one clip, collect candidate (desired, existing) pairs
   among the unclaimed existing chapters: **equal** clip lists (same order) rank first; the rest rank by
   **larger overlap** (shared identities, at least one).
3. Sort candidates by (exact first, larger overlap, desired index, existing index) and take them greedily,
   each existing chapter once and each desired chapter once.
4. A paired desired chapter reuses the existing node: set `entry["name"] = name` (ruamel keeps the name
   line's end-of-line comment and the key position) and rewrite its `clips` through `_rewrite_identity_list`
   as for a name match.
5. An unpaired desired chapter is a fresh node; an unclaimed existing chapter is dropped.

**Rationale**:
- Deterministic and order-independent of dict iteration; the sort key is total.
- A "wrong" pairing is harmless: it can only attach a dropped chapter's comments to a new chapter that took
  over its clips, which is what a rename is. A pairing needs a real shared clip, so an unrelated new chapter
  stays fresh.
- `ends` is re-keyed from the chapter *name* to the chapter *node* (`id(node)`), because after a rename the
  node's list comments are looked up by the node, not by a name that no longer exists.

### The lines above a chapter travel with it

**Context**: The previous change decided, for list entries, that an own-line comment belongs to the entry
**below** it ("Whose comment is it", option (b)), although ruamel files it under the entry above. Chapters
are entries of the `chapters` list and need the same convention, and for the same reason: a
`# --- the B section ---` line is about `B`.

**Explored**: Keeping a between-chapters line positional (it stays at the same index) versus carrying it
with the chapter below. Positional is what the in-place path does, and is fine when no chapter moves; the
moment one does, the comment ends up above a different chapter.

**Decision**: When the outer sequence cannot be kept (`in_place` is false), collect before any mutation, per
existing chapter node, the text **above** it:
- chapter 0: the lines under `chapters:` (the header sources above)
- chapter `i > 0`: the previous chapter's clip-list `trailing` followed by the outer sequence's
  pre-comment `chapters.ca.items[i][1]`, rendered verbatim with indentation like `_header_text`

and the text **after the last chapter** (the old last chapter's `trailing`, plus `chapters.ca.end`, which is
positional and is copied to the new sequence as it stands). Then:
1. After the clip rewrites, clear `trailing` on every reused node's clip list (`_set_trailing(entry,
   "clips", "")`); the text now lives in step 3, once.
2. Assign `data["chapters"] = rebuilt`.
3. For the chapter at index 0, `_set_header(data, "chapters", rebuilt, above)`; for index `i > 0` with a
   non-empty `above`, set `rebuilt.ca.items[i] = [None, [CommentToken(above, CommentMark(0))], None, None]`.
   A fresh node has no `above`.
4. Put the after-last text back with `_set_trailing(rebuilt[-1], "clips", after)`. If the new last chapter's
   `clips` is not a sequence (a bare `clips:` or none) and there is text to carry, it becomes `clips: []`, so
   the text survives; with no text, such a chapter stays as written.

An unchanged or append-only sequence still takes the existing `in_place` path (nothing moved, nothing to
re-home), so an unmodified save stays byte-identical.

**Rationale**:
- One rule for clips and for chapters (the line above an entry belongs to that entry), and it reuses the
  helpers that already write these slots.
- A removed chapter takes only the lines above itself: `A, B, C` minus `B` keeps `# --- the C section ---`
  above `C` and drops `# --- the B section ---`. Minus `A` leaves `# --- the B section ---` directly above
  `B`, now first, under `chapters:`.
- A comment sitting under `chapters:` before a swap goes with the chapter it sat above. This is the same
  trade-off the previous change accepted for the first clip of a list.

### Retained entries re-emit their stored scalar

**Context**: `_rewrite_identity_list` refills the sequence with `str` identities. `preserve_quotes` stores
`"a.mp4"` / `'b.mp4'` as `DoubleQuotedScalarString` / `SingleQuotedScalarString`; refilling discards them.

**Decision**: `_EntryComments` gains the stored scalar (`stored: Any`, default `None`), filled by
`_entry_comments` from the sequence item itself. `_rewrite_identity_list` extends with
`comments[identity].stored` when present, else the plain identity. The `comments` mapping is already shared
across chapters, so a clip moved to another chapter keeps its quotes too, with no new mapping to thread
through. The early `list(seq) == desired` return stays (a quoted scalar equals its identity as a `str`), so
an unchanged list is still untouched.

**Rationale**: smallest change that covers chapters and `ignore` (both go through the same function); an
entry whose stored spelling differs from its identity (`./a.mp4`) has no stored scalar for the identity
`a.mp4`, so it is written plain, which the existing `non_canonical_entry` test requires.

### Permission-safe existence check

**Context**: `apply_editorial_write` decides "no document yet" with `reel_path.exists()`. On Python 3.14
`Path.exists()` swallows `EACCES`, so an unsearchable folder reads as "no `reel.yaml`".
`event-permission-errors` added a `reel_exists` helper in `event/metadata.py` (`stat()`; `False` only for `FileNotFoundError` /
`NotADirectoryError`) and assigns this call site to this change.

**Decision**: replace `reel_path.exists()` with that helper. The permission error it raises is not caught
here, so it reaches the caller (the API's existing error mapping) before any validation or write.

### No fingerprint or render impact

**Decision**: No `RENDER_GRAPH_VERSION` bump; no fingerprint, `ETag` or schema change.

**Rationale**: `editorial_hash` hashes `document.to_dict()`, built by `build_document` from the same merged
data. Comments, quote style and which node carries a chapter are not typed fields. The tests assert the
verdict and `ETag` of a rename write equal those of the same state written onto a comment-free file.

## Failure behavior and idempotency

- **Validation and atomicity are unchanged.** The pairing and comment moves mutate only the in-memory copy
  that `document_to_data` returned, before `build_document`, `require_processable` and the atomic
  `write_document`; a validation failure still writes nothing.
- **Nothing new can fail.** Every new step is dictionary, list and token manipulation on structures the
  function already inspects; an unexpected node type (a non-`CommentedMap` chapter) is skipped as today. A
  permission error from the existence check is the one new loud failure, by design.
- **A re-run is idempotent.** Applying a state that was just written is the unmodified-save path: every
  chapter matches by name, the sequence is `in_place`, and unchanged lists are not touched, so the second
  write is byte-for-byte equal to the first. Tests apply each scenario's desired state twice.
- **No render, job or manifest effect;** `--force` and worker restarts are unaffected (engine write only).

## Risks / Trade-offs

- **[ruamel's comment layout is internal]** The slots read and written here (`ca.items[i][1]`, `ca.end`,
  `ca.comment`) are not a public API, and `pyproject.toml` allows ruamel from 0.18. → Every layout (block,
  flow, flow with a comment after the `]`) has a test comparing the whole persisted file, so an upgrade
  that moves a slot fails in CI instead of dropping comments.
- **[Mis-pairing on a large rewrite]** A save that removes a chapter and adds one that happens to take over
  some of its clips is treated as a rename. → That is the only reading of the request that keeps data, and
  the result is the same typed document either way; only comments differ, and in the direction of keeping
  them.
- **[Header comment travels]** A comment directly under `chapters:` moves with the first chapter on a swap.
  → Same convention as for clips; stated in the spec.
- **[Flow list that turns block]** A renamed chapter whose flow list gains a commented clip still turns
  block style, and a comment after its `]` moves to the key line (known, cosmetic).
- **[Duplicate identities in `ignore`]** Comments and stored scalars are looked up by identity, so duplicates
  share one. → Unchanged from the previous change; rare.

## Migration Plan

No data or schema migration. Files already stripped by earlier saves stay as they are. Rollback is reverting
`event/editorial.py` and the tests.
