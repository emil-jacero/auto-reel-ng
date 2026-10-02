## Why

Two editorial-write defects show a save changing more of `reel.yaml` than the user edited, which breaks
the round-trip promise of Principle II ("round-tripping `reel.yaml` MUST preserve user comments and key
order") and HLD §4.6/§4.7 (the GUI writes `reel.yaml`, and the author's file stays the author's):

1. **Changing one cut span reformats the others.** A clip with
   `trims: [{in: 0, out: 3.2, reason: black}  # black start, {in: 10, out: 12}  # shake]` has only its second
   span's `out` changed to 13. `_apply_trims` sees the lists differ and replaces the whole list with fresh
   block mappings, so the untouched first span loses its flow style and `# black start`, and the second loses
   `# shake`. Over the API, where JSON numbers arrive as floats, every span in the rewritten list also turns
   `in: 0` into `in: 0.0`.
2. **Saving an unmodified document rewrites a hand-authored file.** `apply_editorial_write` always calls
   `write_document`. A `reel.yaml` written with 4-space mappings and an un-indented `- name` sequence, read
   with `GET .../reel` and PUT back unchanged with `If-Match`, comes back re-indented (mapping indent 4 to
   2, sequences nested two deeper, end-of-line comment spacing re-padded). The existing `api-service`
   scenario "Saving an unmodified document is a no-op" promises byte-for-byte unchanged; it only holds for
   files already in the canonical style.

A third, small hygiene gap shares the file: `write_document` removes its `.reel.yaml.<hex>.tmp` only on a
failure it survives. A SIGKILL or power loss between creating and renaming leaves the hidden file behind
forever.

This is a bug-round change (triage ids `changing-clip-cuts-reformats-other-trims`,
`put-reindents-foreign-style-reel-yaml`, and the `reel.yaml` half of
`thumbnail-cache-disk-full-and-tmp-sweep`). It belongs to HLD §6 phase 8 (GUI v1 + editorial write API), the
phase that introduced the editorial write. No §8 research item is involved.

## What Changes

- **An editorial write that changes nothing writes nothing.** When the event already has a `reel.yaml` and
  the merged document is structurally and textually identical, in the canonical dump, to the loaded one,
  `apply_editorial_write` returns the document without touching the file. A foreign-indented file stays
  byte-for-byte as authored. A write that does change something still emits the canonical style, as before.
- **A changed cut list is diffed per span.** Spans whose content (numeric `in`/`out`, `reason`) is unchanged
  keep their node, flow/block style, scalar spelling (`0` stays `0`) and comments. Only spans that differ
  are edited in place, added or removed; a removed span takes only its own comments.
- **`write_document` sweeps abandoned temporaries.** After a successful write it deletes, from the same
  folder, regular files named `.reel.yaml.<32 hex>.tmp` whose mtime is more than 24 hours old.
  Younger ones (a concurrent writer) and every other name are never touched.
- Packages: `auto_reel_ng/event` (editorial) and `auto_reel_ng/reel` (writer). The write is shared, so the
  CLI (`import`, `adopt`) gets the sweep and the API and engine get the no-op; no CLI or API code changes
  (Principle V).
- Tests: `tests/test_event_editorial.py`, `tests/test_api_editorial_write.py`, `tests/test_reel_writer.py`.

**Non-goals**

- Preserving a foreign file's indentation when a save really changes it. ruamel cannot do this without
  guessing indent per file (`load_yaml_guess_indent`); the canonical style stays the constraint stated in
  `reel-document` ("Round-trip preserving writer"). A changed foreign file is rewritten in canonical style,
  as today.
- Normalising floats. A new or changed span value from the API is written as the number received
  (`out: 13.0`); only unchanged values keep their stored spelling.
- Overlapping-cut handling, chapter renames and quote styles (separate bug groups; chapter comment fixes are
  the gate `editorial-chapter-comments`).
- The thumbnail-cache half of the temp-file sweep (change `thumbs-hdr-and-cache-hygiene`).

**Rendered output and fingerprint.** No rendered byte changes for identical inputs: `RENDER_GRAPH_VERSION`
is not bumped. The fingerprint's editorial component is `editorial_hash` over the document's typed fields,
so neither style nor spelling (`0` vs `0.0`) ever moved it; it is unchanged. No `reel.yaml` or `config.yaml`
schema change, no Alembic migration, no rescan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `editorial-write`: three ADDED requirements (an unchanged write touches nothing, a changed cut list
  edits only the spans that differ, an abandoned temporary is swept). They are added rather than
  MODIFIED because the gate `editorial-chapter-comments` rewrites the neighbouring requirement
  "Comments and key order survive an editorial write"; this change leaves that text alone.

## Impact

- `auto_reel_ng/event/editorial.py`: the no-op check in `apply_editorial_write`; `_apply_trims` and
  `_trims_equal` replaced by a per-span diff. **Gate:** `editorial-chapter-comments` edits the same file
  (`_apply_chapters`, `_rewrite_identity_list`, the comment-lifting helpers) and must be merged first.
- `auto_reel_ng/reel/writer.py`: `write_document` gains the sweep.
- Callers unchanged: `api/routes/events.py` (PUT), `cli/commands.py` (`import`), `cli/adoption.py`.
- Existing scenario "Round-tripping an unmodified state is a no-op" and the `api-service` scenarios on
  unmodified saves keep holding; no `api-service` delta is needed because they already state the contract.
