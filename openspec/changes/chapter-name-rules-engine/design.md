## Context

`_parse_chapters` accepts any string name and rejects only exact duplicates. `ReelDocument.chapter(name)` is
exact. `place_disk_clips` (`cli/adoption.py`, shared by `prepare_event` and the events detail via
`api/events_read.py`) buckets each NEW clip by its folder name and asks `document.chapter(folder)`. The seeded
document (`discovery.seed_document`) names chapters after folders and is written with `write_document`, which
does not validate; executed on `origin/main`, folders `Party/` and `party/` seed and load today.

## Research & Decisions

### Where the rules live
**Context**: the rules must hold for hand-edited files, for documents the engine builds (adoption, GUI saves
through `build_document`) and for the seeded document, which is built in memory and never parsed.
**Explored**: `schema.py` (`build_document` is the one validator for parsed data), `writer.py`
(`write_document` writes whatever it is given), `discovery.seed_document` (builds `Chapter` objects directly).
**Decision**: one function in `reel/schema.py`, `check_chapter_names(names, *, source)`, called by
`_parse_chapters` and by `write_document` on `doc.chapters`. No change to `discovery/` (a third package).
**Rationale**: loading and writing then cannot disagree, and the seed fails at its first write rather than
producing a file that bricks the event on the next scan (Principle I). `_ensure_chapter` in `cli/adoption.py`
already goes through `build_document`, so adoption into folders `Party/` and `party/` fails there with no
extra code.

### The rules
**Decision**: for each chapter in order, with `name`:
1. `name == ""` is the default chapter: valid, but still unique (two `""` are a duplicate).
2. otherwise `name.strip() == ""` raises "blank"; `name != name.strip()` raises "leading or trailing
   whitespace"; both name `chapters[i]` and show the name with `repr`.
3. `key = name.casefold()`; a repeat raises
   `chapters[j]: duplicate chapter name 'party' (same as chapters[i] 'Party', ignoring case)`.
No `unicodedata.normalize`. The prefix `duplicate chapter name` of today's message is kept, so exact
duplicates read as before. Nothing is rewritten: the typed model keeps the name as written.
**Rationale**: `str.casefold()` is the user's decision and folds `ß` to `ss`, which `toLocaleLowerCase` does
not; the web change aligns to it. Normalization would be a second rule nobody asked for (Principle VII).

### Lookup and adoption
**Decision**: `ReelDocument.chapter(name)` returns the exact match, else the chapter whose
`str.casefold()` equals the argument's (at most one, by the uniqueness rule). `place_disk_clips` keys its buckets by the **matched
chapter's name** (`matched.name`), not the folder's spelling, so `names`, `_ensure_chapter` and `add_clip`
see one spelling and `events_read._build_chapters` extends the right `ChapterOut`.
**Rationale**: exact first is a defensive ordering that cannot change the result for a loaded document (names are casefold-unique); its precedence is proved only on an in-memory document (`tests/test_reel_document.py`). It keeps documents loaded before this change (none can hold two casefold-equal
names after it) behaving identically; the casefold step only adds a match where there was none. A folder
spelled with padding is not stripped: padded names are invalid for chapters, so it has no chapter and falls
to the default chapter, the rule for any folder without one. The default chapter `""` is found exactly.

## Failure behavior

- Load: `ReelParseError` from the one validator, so the CLI `ERROR <event>` line, the events list's
  `unparseable_reel_yaml` row and the detail's 502 report it as they report any bad `reel.yaml`; other events
  are untouched (Principle I, per-event isolation).
- Write: `write_document` raises `ReelParseError` before opening the temporary file, so the previous
  `reel.yaml` is untouched and no `.tmp` is left.
- Seeding: the seeded document is built in memory and checked only when it is written, so for an event
  with no `reel.yaml` and folders `Party/` and `party/` the read paths (scan, the staleness fingerprint,
  the events read model) still show the seed as two chapters; `render`, `enqueue` and the worker fail at
  persist time. This fail-late behaviour is accepted: the requirement is that the write fails and leaves
  no file.
- Adoption: a `NEW` clip in a folder that would create a duplicate raises through `_ensure_chapter`; nothing
  is persisted (`persist` runs after `prepare_event`).

## Idempotency

A re-run, a `--force` run and a worker restart see the same document: a valid document loads, adopts and
rewrites exactly as before; an invalid one fails at load every time until fixed. No state is stored.
Adoption by casefold is stable: after it, the clip is listed, so it is no longer NEW.

## Risks / Trade-offs

- A `reel.yaml` with case-variant or padded chapter names stops loading. Mitigation: the message names both
  chapters and the file is hand-editable; the user accepted this.
- The GUI, until `chapter-name-rules-web` lands, trims with `trim()` and folds with `toLocaleLowerCase`; the
  engine is the stricter gate where the folds differ (`ß`): a name the GUI accepts there fails when the
  document is next loaded or written, loudly and naming both chapters.

## HLD

Amend **D-12** with an "Amended 2026-10-02" paragraph: adoption matches a folder to a chapter by exact name,
then `str.casefold()`; and add a sentence under the §4.6 `chapters` schema block: names other than `""` are
unpadded and non-blank, and unique under `str.casefold()` (user decision 2026-10-02, change
`chapter-name-rules-engine`).
