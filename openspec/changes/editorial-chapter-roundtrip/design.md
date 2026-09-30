## Context

See proposal.md, section Why. Four code facts shape the approach:

- **The merge works on a copy of the loaded structure.** `event/editorial.apply_editorial_write` calls
  `reel/writer.document_to_data`, which reloads the dumped source, so it gets a fresh copy with every
  comment token. It then merges each section into that copy in place. `metadata`, `look` and the `clips`
  property map reuse their nodes, and an unmodified save leaves them byte-identical (verified).
- **`_apply_chapters` (`editorial.py:157-195`)** reuses an existing chapter's mapping by `name`. It then
  empties and refills that chapter's `clips` `CommentedSeq`, or builds a fresh node for a new name, and
  assigns a new outer `CommentedSeq` of chapter nodes.
- **`_apply_ignore` (`:142-154`)** empties and refills `ignore` in the same way.
- **The precedent is in the same module.** `_apply_trims` (`:235-251`) compares by content and leaves an
  unchanged node alone, so its original formatting survives.

What ruamel.yaml 0.19.1 (the installed version; `pyproject.toml` asks for `>=0.18.0`) does with list-entry
comments. This was established with a throwaway prototype on scratch copies. The prototype is not committed:
the facts are restated here, and the tests in tasks 2.1 to 2.3 pin them.

- **Entry `i`'s comments** live in `seq.ca.items[i][0]`, a single `CommentToken`. Its `value` holds:
  - the entry's end-of-line comment, up to the first `\n`: `'# first'`, or nothing when the entry has none
    (then the value starts with `\n`)
  - everything after that newline: the own-line comments and blank lines that follow the entry, up to the
    next entry, with their indentation

  Examples:
  - `'# first\n      # before b\n'`
  - `'\n\n'` (no comment, one blank line)
  - `'\n      # before c\n'`

  The token's `column` is where the `#` of the end-of-line comment was written.
- **The last entry's token** also holds the comment lines after the list, for example
  `'# MISSING\n    # trailing\n  # between chapters\n'`. Those lines introduce whatever follows the list.
- **Lines above the first entry** are stored twice:
  - on the list, in `seq.ca.comment[1]`: a list of tokens, each with an unindented value and a `column`
    (`# one\n\n# two` above `- junk.mp4` is two tokens, `'# one\n\n'` and `'# two\n'`, both at column 2)
  - on the parent mapping, in `parent.ca.items[key][3]`

  The dumper emits the parent's copy when there is one, and falls back to the list's. A single token with
  column 0, whose value carries its own indentation, is emitted verbatim.
- **Unless the key line has its own comment.** For `clips:   # root list`, the lines above the first entry
  are the tail of the key's end-of-line token instead: `parent.ca.items[key][2]`, value
  `'# root list\n      # the opening shot\n\n'`. That token is the same object as `seq.ca.comment[0]`, and slot
  `[3]` and `seq.ca.comment[1]` are empty.
- **A comment after an empty list** round-trips when the list is flow style (`clips: []`) and the comment is
  the value of the key's end-of-line token after a leading `\n`. With a block-style empty list, the same token
  corrupts the output (`- name: Kvällen clips:`).
- **A flow-style list cannot hold entry tokens.** Tokens set on a flow list's items are emitted inside the
  brackets as `[a.mp4\n      # note\n, b.mp4  # x\n]`. It parses, but the author would not recognise it.
  `seq.fa.set_block_style()` emits the same list, tokens included, as a clean block list.
- **Deleting items loses their comments.** `del seq[:]` deletes item by item and drops each index's comment.
  `extend` adds items with none. That is the defect: see the diff in proposal.md.

## Goals / Non-Goals

**Goals:**

- An unmodified save is byte-identical for every `reel.yaml` that round-trips byte-stable on load and spells
  its clip identities canonically, including comments on list entries. A non-canonical spelling (`./a.mp4`)
  already fails the no-op today, in the `clips` map too, and is not addressed here.
- A changed list keeps each retained entry's comments on that entry.
- One small helper serves both lists, with no second code path.

**Non-Goals:**

- Matching chapters by anything other than `name`.
- Re-homing comments when chapters are reordered.
- Comments inside a flow list's brackets. A changed flow list with no comment to carry keeps today's
  behavior: its items are replaced, and it stays flow style.
- Any change to `reel/`.

## Research & Decisions

### Leave an unchanged list untouched

**Context**: The no-op scenarios require byte identity. The cheapest way to get it is not to touch what did
not change.

**Explored**: Rebuilding the list and restoring every token versus skipping it. `_apply_trims` already
compares by content and skips.

**Decision**: The list rewrite MUST return without mutating the node when `list(seq) == desired`. The
comparison is by item value, in order.

**Rationale**:
- It makes the no-op scenario hold by construction.
- A commented chapter that the GUI resends unchanged is never rewritten.

### Whose comment is it: the convention

**Context**: The requirement says a clip keeps "its own" comments. ruamel files an own-line comment under
the entry **above** it, while a reader takes it as describing the entry **below** it.

**Explored**:
- **(a) Move each whole token with its entry.** This is simplest, but it detaches `# before second` from the
  clip it introduces. It also moves `# between chapters` into the middle of a list whenever the last clip
  moves, so the last token has to be split anyway.
- **(b) Split every token at the first newline.** The end-of-line part belongs to its entry. The rest belongs
  to the next entry, as the lines above it. After the last entry, the rest is the list's trailing text.
- **(c) Keep the lines above the first entry fixed at the top of the list** (as its header), and apply (b)
  between entries. This is inconsistent: the first clip's own-line comment would be the only one that
  does not travel.

**Decision**: (b). For each entry:
- the end-of-line comment is kept with the column it was written at
- the lines above it are kept verbatim, indentation included
- the lines above the first entry come from the parent's slot, else from the list's copy, else from the tail
  of the key's own end-of-line comment

**Rationale**:
- This is how the file reads to a human.
- It is the only option under which "removed drops its own comment" and "trailing text stays at the end"
  both hold.
- The scratch prototype reproduced every spec scenario with it, the original
  end-of-line columns included.

### The helper

**Decision**: two module-private functions in `event/editorial.py`, and a small frozen dataclass:

```python
@dataclass(frozen=True)
class _EntryComments:
    above: str = ""   # own-line comments / blank lines above the entry, verbatim (indented)
    eol: str = ""     # end-of-line comment text, e.g. "# MISSING" ("" when none)
    column: int = 0   # the column the eol comment's '#' was written at


def _entry_comments(parent: CommentedMap, key: str) -> tuple[dict[str, _EntryComments], str]:
    """Split parent[key]'s per-entry comments by identity; also return the list's trailing text."""


def _rewrite_identity_list(
    parent: CommentedMap,
    key: str,
    desired: list[str],
    comments: Mapping[str, _EntryComments],
    trailing: str,
) -> None:
    """Make parent[key] (a CommentedSeq) hold ``desired``, keeping each entry's comments."""
```

`_rewrite_identity_list` does the following:

1. **Unchanged:** if `list(seq) == desired`, it returns.
2. **Refill:** it runs `del seq[:]`, then `seq.ca.items.clear()`, then `seq.extend(desired)`, reusing the
   same node, so the list's own position and the parent key's other comment slots stay. If the key has an
   end-of-line token, the token keeps only its first line (`'# root list\n'`), because its tail was the old
   first entry's `above` text.
3. **Emptied:** if `desired` is empty, the list keeps no entry tokens. When `trailing` is not empty, the list
   is set to flow style (`seq.fa.set_flow_style()`), and `trailing` is appended to the key's end-of-line token
   after its `\n`. If the key has no such token, one is created at column 0 with the value `"\n" + trailing`.
   The helper then returns.
4. **Rebuild the tokens:** for each new index `k`, let `c = comments.get(desired[k], _EntryComments())`.
   Let `below` be the `above` text of the entry at `k + 1`, or `trailing` after the last entry. Then:

   ```python
   value = (c.eol + "\n" if c.eol else "\n") + below
   if value != "\n":
       seq.ca.items[k] = [CommentToken(value, CommentMark(c.column if c.eol else 0)), None, None, None]
   ```

5. **Header:** it sets the first entry's `above` text as one column-0 token, in both copies the loader
   fills: `seq.ca.comment[1]` and `parent.ca.items[key][3]`. It creates the slot if it is missing, keeps the
   slot's other indices, and writes `None` to both copies when there is no text.
6. **Style:** if the list is flow style and step 4 or 5 wrote any token, it is switched to block style
   (`seq.fa.set_block_style()`). A flow list with nothing to carry stays flow.

`_entry_comments` reads a token's `column` only when it has an end-of-line part. It takes the lines above the
first entry from `parent.ca.items[key][3]`, then from `seq.ca.comment[1]`, and then from the tail of the key's
end-of-line token, after its first `\n`. For header tokens, it turns the `(column, value)` pairs into verbatim
indented text.

The scratch prototype of these six steps reproduced every scenario in the spec delta. Each changed write,
applied a second time, was a byte-for-byte no-op. Reversing a reorder restored the original bytes, for the
key-comment variant as well.

Call sites:
- **`_apply_chapters`** first collects the comments of **every** existing chapter's `clips` into one
  identity map, before mutating anything. Identities are unique across chapters (`reel/schema`: "an
  identity may appear in chapters at most once"), so a clip moved between existing chapters finds its
  comments. It records each chapter's trailing text by chapter name. It then calls
  `_rewrite_identity_list(entry, "clips", clips, comments, trailing[name])` where the old code emptied and
  refilled. A fresh chapter is still `CommentedSeq(clips)`.
- **`_apply_ignore`** calls the helper with the `ignore` list's own map, where its code emptied and refilled.
  It still drops the key when the desired list is empty.

**Rationale**:
- **One helper, two call sites (Principle VII).** The token format is ruamel's documented comment
  attribute (`.ca`), used through the same types the module already imports.
- **Comparison uses the stored item.** It compares against the stored item, not the normalized identity.
  A hand-written `./a.mp4`, which the desired state carries as `a.mp4`, therefore counts as a change. It is
  rewritten in canonical form without its comment, which is harmless and rare.

### Where the convention is recorded

**Context**: The config rule asks that a decision which outlives the change be folded into the HLD as a D-n
entry.

**Decision**: The `editorial-write` spec states the attachment convention as observable behaviour. No HLD
D-n is added.

**Rationale**: It is not a graph shape, a fingerprint input or a schema change. It sharpens Principle II's
existing round-trip guarantee.

### No fingerprint or render impact

**Decision**: No `RENDER_GRAPH_VERSION` bump. No fingerprint change.

**Rationale**:
- `staleness/fingerprint.editorial_hash` hashes `document.to_dict()`, the typed fields. The persisted
  document is built by `build_document` from the same merged data, so its typed fields are identical with or
  without comments.
- The editorial-read `ETag` is the same hash.
- The tests assert the verdict and `ETag` are unchanged by a comment-only difference.

## Failure behavior and idempotency

- **Validation and atomicity are unchanged:** `build_document` validates, then `require_processable`, then
  the atomic `write_document`. The helper only mutates the in-memory copy that `document_to_data` returned,
  so a validation failure after it still writes nothing.
- **The helper does not add a new way to fail.** It raises only where the code it replaces could raise, such
  as a non-sequence `clips` node, which keeps today's `else: entry["clips"] = CommentedSeq(clips)` branch.
- **A re-run is idempotent:** re-applying the same desired state is a byte-for-byte no-op, which is the fix
  itself.
- **Nothing else changes:** no render, no job, no manifest. `--force` and worker restarts are unaffected.

## Risks / Trade-offs

- **[ruamel's comment layout is internal]** `ca.items`, the doubled header slot and the key token's tail are
  not a stable public API, and `pyproject.toml` allows any version from 0.18. → The tests pin every behavior
  (no-op, reorder, move, remove, add, trailing, emptied, header, key comment, flow), so an upgrade that
  changes the layout fails loudly in CI instead of silently dropping comments.
- **[The convention is a choice]** An author who meant an own-line comment as a note on the entry above it
  will see it travel with the entry below. → It matches how YAML is normally read, and it is stated in the
  spec. Unchanged lists are never affected.
- **[The last clip's trailing text stays with its chapter]** When a chapter's last clip moves to another
  chapter, `# between chapters` stays at the end of the source chapter, which is still directly above the
  next chapter. When chapters are reordered, it moves with its chapter: a `# property overrides` line above
  `clips:` can then land between two chapters. Today that line is lost on every save. Re-homing it is a
  non-goal, and slice D does not reorder chapters.
- **[Column after a move to a deeper indent]** Today all chapters' clips share one indentation, so a moved
  clip's comment column is exact. If the item's line gets longer, ruamel falls back to one space before `#`.
  The same happens to a key comment after `clips: []` (`clips: [] # root list`). → This is cosmetic only.
- **[A flow list turns block]** A flow-style clip list that receives a commented clip is rewritten in block
  style. → The list changed anyway, and the writer's own style is block (D-G). A flow list with nothing to
  carry keeps its style.

## Migration Plan

There is no data or schema migration. Files already stripped by earlier saves stay as they are: the lost
comments cannot be recovered. Rollback means reverting `event/editorial.py` and the tests.
