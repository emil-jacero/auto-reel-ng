## Why

HLD **§6 phase 8** (GUI v1). Slice D (`event-edit-screen`, HLD §4.10) saves an event by sending its **whole**
editorial state back through `PUT /api/v1/events/{event_id}/reel` (D-E2: a coarse, complete-state write).
Every chapter is resent on every save, including the chapters the operator never touched.

`reel.yaml` is written by hand as well as by the engine. Decision **D-G** (`reel-yaml-editorial-model`,
"reel.yaml-first writes; round-trip YAML") chose ruamel's round-trip mode so that a machine write keeps the
author's comments, and rejected PyYAML because it drops them. Principle II makes it binding: "Round-tripping
`reel.yaml` MUST preserve user comments and key order". Two shipped scenarios make it concrete:

- `editorial-write`: "Round-tripping an unmodified state is a no-op" (byte-for-byte)
- `api-service`: "Saving an unmodified document is a no-op"

**Both are false today for any list entry that carries a comment.** `event/editorial.py` handles each list
the same way:

- `_apply_chapters` empties and refills every chapter's `clips` sequence (`del existing_clips[:]`, then
  `existing_clips.extend(clips)`)
- `_apply_ignore` does the same to `ignore`

ruamel stores a list entry's comment in the sequence's per-index comment table. Emptying the sequence
deletes those comments, and refilling it does not restore them.

Reproduced on a scratch copy by applying an unmodified state read back from the file:

```diff
 chapters:
   - name: ''
     clips:
       - s1710002.mp4
       - s1710004.mp4
-      - borttagen.mp4  # MISSING
+      - borttagen.mp4
```

This is the dev library's `2024-09-01 - Sommarlov` `reel.yaml`, byte for byte. The same save also drops:

- an own-line comment between two clips
- a comment after a chapter's last clip, such as one introducing the next chapter, or one above the next
  top-level key (ruamel files `# property overrides` above `clips:` under the last chapter's last clip)
- `- junk.mp4  # never render` in `ignore`

The comment on the chapter name, the metadata comments, and the comments in the `clips` property map
survive, because those nodes are reused.

Slice D would make every save do this, so this change is a gate of `event-edit-screen`.

## What Changes

- **An unchanged list is left alone.** If a chapter keeps the same name and the same entries, as written on
  disk, in the same order, the write does not touch its `clips` node, so its bytes are unchanged. The same holds for an unchanged
  `ignore` list. An unmodified save is then byte-for-byte a no-op, as both specs already require.
- **A changed list keeps each entry's own comments.** When a chapter's clips are reordered, or some are
  added or removed, the entries the write keeps are moved together with their own comments:
  - the end-of-line comment (`- borttagen.mp4  # MISSING`), at its original column
  - the own-line comments and blank lines directly above the entry
  - a clip moved to another existing chapter takes its comments with it
- **Other entries:**
  - a removed entry drops only its own comments
  - an added entry gets no comment
  - comment lines after a list's last entry stay at the end of that list, because they introduce what
    follows (for example the next chapter). They stay there when the list is left empty (`clips: []`).
  - a flow-style list (`[a.mp4, b.mp4]`) that must carry a comment is written in block style
- **The `ignore` list gets the same treatment.** It has the same defect in the same file.
- **Chapters that are renamed, added or removed behave as they do today.** An existing chapter is still
  matched by name, a new name still gets a fresh node, and a dropped chapter is still dropped.
- The shipped no-op scenarios gain a commented fixture, in tests and in the spec.

## Non-goals

- **No change to how chapters are matched.** A renamed chapter is still a new node, and its clip comments
  are not carried over. A rename is a different chapter under D-E2, and the GUI v1 slice does not rename
  chapters.
- **No re-homing of comments when chapters are reordered.** A reordered chapter keeps its node, and an
  unchanged clip list keeps its lines. A comment that ruamel files under a chapter's last clip therefore
  moves with that chapter, even when it introduces the next chapter or the next top-level key. Today such a
  comment is lost on every save. Chapter reorder is not part of slice D.
- **No change to `metadata`, `look` or the `clips` property map.** They already reuse their nodes and survive
  an unmodified save (verified on the scratch copy).
- **No comment editing through the API.** Comments are the author's, and the API neither reads nor writes
  them.
- **No `reel.yaml` style normalisation.** The writer's fixed indentation (D-G) is unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `editorial-write`: `Requirement: Comments and key order survive an editorial write`:
  - unchanged lists are left untouched
  - an entry's own comments follow it through a reorder or a move
  - removed and added entries, trailing lines, emptied lists and flow-style lists behave as described above
  - a commented fixture is added to the no-op scenario

## Impact

- **Packages:**
  - `event/`: `editorial.py`, where `_apply_chapters` and `_apply_ignore` share one list-rewrite helper
  - `tests/`: `test_event_editorial.py`, plus one API round-trip case in `test_api_editorial_write.py`
  - nothing else changes
- **CLI vs API (Principle V):**
  - the fix is in the engine operation `apply_editorial_write`, so every caller gets it
  - its only caller today is the API's `PUT …/reel` (`api/routes/events.py`); no CLI subcommand calls it
  - `import` and render adoption write through `reel/writer.write_document`, which is not touched, and do
    not merge desired states, so their behavior is unchanged
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.**
- **Fingerprint:** inputs unchanged. The editorial component, `staleness/fingerprint.editorial_hash`, is
  `_hash_json(document.to_dict())`, a hash over the typed fields, and comments are not typed fields. The
  editorial-read `ETag` is the same hash, so it does not move either.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan.
- **Wire:** no status code, body or header changes. Only the bytes the write persists change, and only where
  they used to lose comments.
- **Dependencies:**
  - no new library: ruamel.yaml 0.19.1, already a dependency, provides the comment table
  - no gate: this change can start now
  - **`event-edit-screen` (C4) is gated on this change** (and on `web-design-system`), because its editor
    resends every chapter on each save
- **Size (Principle VIII):** one helper and two call sites in one module, one capability delta, and tests.
