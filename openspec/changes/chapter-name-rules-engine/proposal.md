## Why

The engine accepts chapter names the GUI refuses, so a `reel.yaml` edited by hand or by the CLI can reach states
the GUI cannot repair (HLD §4.1 reel schema, **D-2** disk is the source of truth; **D-12** adoption by folder;
**D-13** chapters edited in the GUI; Principle I, fail loud). Executed on `origin/main`: `loads_document` loads
chapters named `"  "`, `"Party"`, `"party"` and `" Party"` without error, because `_parse_chapters`
(`reel/schema.py`) requires only a string and rejects exact duplicates. The GUI's `checkName`
(`web/src/edit/chapterNames.ts`) trims, refuses an empty name and compares case-insensitively, and its comment
says "the engine checks exact duplicates only; this is stricter, never looser". Adoption is exact
(`ReelDocument.chapter` compares `chapter.name == name`) while discovery already treats the originals folder
case-insensitively, so a folder `party/` does not reach a chapter `Party`: its new clips fall into the default
chapter.

**USER DECISION (2026-10-02), "Enforce in engine (Recommended)":** the engine enforces the rules, rather than
leaving the GUI the only stricter gate. The risk that existing `reel.yaml` files stop loading is tiny for hand
authored files and fail-loud.

This belongs to the 2026-10-02 bug round after HLD §6 phase 8; it depends on no open §8 research item.

## What Changes

- **Load rules** (`reel/schema.py`, `_parse_chapters`): a chapter name other than `""` MUST be non-blank and
  MUST equal its own `str.strip()`; chapter names are unique under `str.casefold()`. A violation raises the
  existing `ReelParseError`, naming `chapters[i]`, and for a duplicate both chapters and both names. `""` stays
  the default chapter's name. Nothing is trimmed or folded to make a document load.
- **Write rules** (`reel/writer.py`, `write_document`): the same rules are checked on the typed chapters before
  anything is written, so a seeded document built from folders `Party/` and `party/` (or a folder with a
  trailing space) fails loud instead of writing a `reel.yaml` that no longer loads.
- **Chapter lookup** (`reel/document.py`, `ReelDocument.chapter`): exact name first, then `str.casefold()`.
  Unambiguous because names are casefold-unique.
- **Adoption** (`cli/adoption.py`, `place_disk_clips`): a folder reaches a chapter by that lookup, and the clip
  is listed under the chapter's own name. A padded folder name matches nothing and falls back to the default
  chapter, as any folder without a chapter does. `api/events_read.py` reads placement from the same function and
  needs no change.
- **HLD**: amend **D-12** (adoption match) and the §4.1 `chapters` schema note with the date and the user's
  answer.
- Specs: ADDED requirement to `reel-document`; MODIFIED "NEW-clip adoption policy" in `headless-cli`. (The
  triage named `event-reconcile`; the adoption policy lives in `headless-cli`, and seeding is covered by the
  `reel-document` writer rule, so `event-reconcile` is unchanged.)

Rendered output for identical **valid** inputs is unchanged: no `RENDER_GRAPH_VERSION` bump, and no
fingerprint input changes. The schema stays `version: 0` (stricter validation only); no `config.yaml` change, no
Alembic migration, no rescan. CLI and API gain no surface: both reach the rules through `reel/`, and a failing
event is reported as the existing unparseable `reel.yaml` error. **Migration note:** a `reel.yaml` that today
holds case-variant duplicate or padded chapter names will fail to load until one chapter is renamed; clip
identities are paths, so renaming a chapter in the file breaks nothing else.

Packages: `reel/`, `cli/`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reel-document`: chapter names unpadded, non-blank and unique ignoring case, at load and at write.
- `headless-cli`: "NEW-clip adoption policy" matches a folder to a chapter exactly, then ignoring case.

## Non-goals

- The GUI (`web/src/edit/chapterNames.ts`): aligning its fold (`toLocaleLowerCase` against `casefold`) and trim
  is the separate change `chapter-name-rules-web`.
- Unicode normalization (NFC/NFD) of names, and trimming interior whitespace.
- Rewriting existing files or offering an automatic repair; the load error names the fix.
- Case-insensitive clip identities or changes to discovery's folder rules.
- A per-event or per-project switch for the rules (Principle VII).

## Impact

`auto_reel_ng/reel/schema.py`, `reel/writer.py`, `reel/document.py`, `cli/adoption.py`; tests in
`tests/test_reel_parser.py`, `tests/test_reel_writer.py`, `tests/test_cli_adoption.py`;
`docs/high-level-design.md` (D-12, §4.1). No new dependencies.
