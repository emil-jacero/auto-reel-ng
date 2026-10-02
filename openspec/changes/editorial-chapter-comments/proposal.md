## Why

HLD **§6 phase 8** (GUI v1, §4.10). Decision **D-G** (`reel-yaml-editorial-model`) chose ruamel round-trip so a
machine write keeps the author's comments, and Principle II makes it binding: "Round-tripping `reel.yaml`
MUST preserve user comments and key order". `editorial-chapter-roundtrip` made that true for the entries of a
list, but left two gaps that it recorded as non-goals or follow-ups. The GUI's chapter management (D-13) will
reach both on its first rename or reorder, so they are fixed before it lands. Both reproduced on a commented
`reel.yaml` through `apply_editorial_write`:

1. **A chapter rename, move or removal loses comments.** Renaming `Reception` to `Party` with the same
   clips drops both clip comments (`# keep me: the best shot`, the own-line comment above `b.mp4`), while
   the untouched `Dinner` chapter keeps its `# dinner clip`. The cause is `_apply_chapters` matching existing
   chapters by name only: an unmatched name gets a fresh node, so everything on the old node is gone. A
   second loss comes from the outer sequence: any change that is not "every chapter keeps its place, new ones
   appended" assigns a new `chapters` sequence, and the lines between two chapters that follow a flow clip
   list (`clips: [a.mp4]`, then `# --- the B section ---`) live on the old sequence by index, so swapping
   chapters, removing one, or renaming one drops them. Renaming `B` also flipped `clips: [b.mp4]` to block
   style, for the same reason (fresh node).
2. **A changed list drops the quotes of the entries it keeps.** A chapter holding `["a.mp4", 'b.mp4']` that
   gains `c.mp4` is written back as `- a.mp4`, `- b.mp4`, `- c.mp4`. `preserve_quotes` loads them as quoted
   scalar objects, but `_rewrite_identity_list` refills the sequence with the plain `str` identities. The
   previous change listed this as a follow-up ("refill with the stored scalars").

## What Changes

- **A chapter that is not matched by name is paired with an existing chapter by its clips.** After the by-name
  pass, each remaining desired chapter takes an unclaimed existing chapter whose clip list equals its own, and
  then the unclaimed existing chapter it shares the most clips with. The paired chapter is the existing node
  renamed, so its name-line comment, its clip comments and the style of its lists survive the rename, with or
  without clip edits in the same save. A chapter that pairs with nothing is written fresh; an existing chapter
  nothing claims is dropped with its own comments, as before.
- **The lines between chapters follow the chapter below them.** Own-line comments and blank lines directly
  above a chapter stay with that chapter through a swap, a move, a rename or the removal of another chapter,
  wherever ruamel filed them (the previous chapter's last clip, its flow list's key token, or the `chapters`
  sequence). A removed chapter takes only the lines above itself. The lines after the last chapter stay after
  the last chapter, and the lines under `chapters:` go with the first one.
- **Retained entries of a changed list keep their quotes.** A retained chapter clip or `ignore` entry is
  written with the scalar it was stored as (`"a.mp4"` stays double-quoted, `'b.mp4'` single-quoted); added
  entries are plain.
- **Editorial writes read `reel.yaml` through the permission-safe existence check.** The `exists()` call in
  `apply_editorial_write` is swapped for the helper that `event-permission-errors` adds, so an unreadable
  event folder is an error, not "no document yet". This is the editorial.py call-site swap that change's
  triage assigns to this one.
- No wire, schema or fingerprint change: only the bytes a write persists change, and only where they used to
  lose comments or quotes.

## Non-goals

- **No change to how a desired state is read.** Chapters are still identified by `name` in the request; the
  pairing is internal to the write and persists nothing the typed fields do not already say.
- **No guess for empty chapters.** A desired chapter with no clips is never paired, so renaming an empty
  chapter is still a fresh node.
- **No comment editing through the API**, and no change to `metadata`, `look` or the property-map `clips`.
- **No normalisation of foreign layouts.** A comment written after a flow list's `]` still moves to the key
  line when the list turns block (documented limitation from `editorial-chapter-roundtrip`).
- **Chapter-name strictness in the engine and pruning of superseded renamed movies** are held for the user
  and are not touched.
- **Sibling bug groups on `editorial.py`** (`editorial-trims-and-noop`: trims diff and no-op write) are a
  separate change that follows this one.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `editorial-write`:
  - `Requirement: Comments and key order survive an editorial write` gains chapter pairing, the
    between-chapter comment rule and quote retention (the "A renamed chapter is a new chapter" scenario is
    replaced).
  - New `Requirement: An editorial write does not mistake an unreadable event for an empty one`.

## Impact

- **Packages:** `auto_reel_ng/event` (`editorial.py` only) and `tests/` (`test_event_editorial.py`, plus one
  API round-trip case in `test_api_editorial_write.py`). Nothing else changes.
- **CLI vs API (Principle V):** the fix is in the engine operation `apply_editorial_write`; its only caller
  today is `PUT /api/v1/events/{event_id}/reel`, so the API gets it with no endpoint change.
- **Rendered output:** unchanged for identical inputs, so **no `RENDER_GRAPH_VERSION` bump** (stays 4).
- **Fingerprint and `ETag`:** inputs unchanged. `editorial_hash` hashes the typed fields; comments, quote
  style and node identity are not typed fields, and a rename was and is a different `name` in the request.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan.
- **Dependencies:** no new library (ruamel.yaml, already a dependency). **Gate:** `event-permission-errors`
  (added the `reel_exists` helper in `event/metadata.py`, which this change calls) merged first. `editorial-trims-and-noop` follows this
  change in the same module.
- **Size (Principle VIII):** one module, one capability delta, 7 tasks.
