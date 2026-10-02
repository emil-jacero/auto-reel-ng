## Why

On 2026-10-02 the user chose to enforce chapter-name rules in the engine ("Enforce in engine"; change
`chapter-name-rules-engine`, recorded in the HLD at D-12): `reel.yaml` loading rejects a non-default chapter
name that is blank or padded with whitespace and treats names equal under `str.casefold()` as duplicates, and
adoption matches a folder to a chapter by exact name, then by casefold. Edit mode (D-13, HLD §4.10) still has
its own, looser copy of the rule in `web/src/edit/chapterNames.ts`: it trims with JavaScript's `trim()` and
compares with `toLocaleLowerCase()`. The two disagree in both directions:

- `trim()` and Python's `strip()` remove different characters. A name the operator pads with U+0085 passes the
  page unchanged and is saved, and the engine then refuses to load the event's `reel.yaml`.
- `toLocaleLowerCase()` is not `casefold()`. `STRASSE` is accepted next to `Straße` (the engine calls them
  duplicates), while the dotless `ı` and `i` are refused as duplicates (the engine keeps them apart).

The page's notes about later clips also say a folder is matched "exactly, as the render does". After the engine
change that is no longer true: a clip in `kvällen/` joins the chapter `Kvällen`.

## What Changes

- The name dialog trims exactly the characters Python's `str.strip()` removes and refuses a name that is empty
  after that. It compares names, for duplicates, with a case fold equal to `str.casefold()`. `Main` stays
  reserved by the page alone: the engine has no such rule.
- The refusal text for a taken name says what "the same" means.
- The later-clip notes, `ignoredStaying` and the placement of an ignored clip match a folder to a chapter by
  case folding, as the engine now does, and show the folder's own spelling.
- `docs/high-level-design.md` D-13 records that the page follows the engine's rules.
- Tests: `node:test` units for the trim, the fold, `checkName` and the notes; a Playwright check of the add and
  rename messages in a real browser.

Rendered output for identical inputs does not change (no `RENDER_GRAPH_VERSION` bump), the staleness
fingerprint is untouched, `reel.yaml` and `config.yaml` schemas do not change in this change (the engine
change owns that), and no Alembic migration or rescan is needed. Only the web app is touched; neither the CLI
nor the API changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: "Edit mode adds, renames, reorders and deletes chapters" (which names are accepted) and "Edit
  mode says what a chapter's name means for clips added later" (folder matching by case folding).

## Non-goals

- The engine rules themselves, adoption and the HLD D-12 entry: `chapter-name-rules-engine`.
- Lifting the page-only `Main` reservation, or adding a name-length limit.
- Normalizing Unicode (NFC/NFD): the engine does not, so the page does not.
- A generic Unicode library or a new npm dependency.

## Impact

- `web/src/edit/chapterNames.ts`, a new `web/src/edit/casefold.ts` (with its test), `ChapterDialogs.tsx`
  only if a refusal's wording needs a parameter.
- `docs/high-level-design.md` (D-13 sentence).
- Depends on `chapter-name-rules-engine` being merged: it is the source of the rules mirrored here.
