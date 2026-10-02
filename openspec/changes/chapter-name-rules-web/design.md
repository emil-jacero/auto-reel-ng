## Context

See proposal.md for why. `chapterNames.ts` is pure (type-only imports) and is the single place the name rules
live: `checkName` (accept or refuse a typed name), `laterClipNotes`/`nameDialogNote` (what a name means for
clips added later), `ignoredStaying`. It uses `String.prototype.trim()` and `toLocaleLowerCase()`, and
compares chapter names with a folder's with `===`.

The rule it mirrors, from `chapter-name-rules-engine` (user decision 2026-10-02): a non-default chapter name
MUST NOT be blank or differ from its own `strip()`; two names equal under `casefold()` are duplicates; `''`
is the default chapter; a folder matches a chapter by exact name, then by casefold. The engine also places
NEW and ignored clips for the events detail with that same rule (`place_disk_clips`), so what the page shows
as "where this clip will go" depends on it.

## Goals / Non-Goals

**Goals:**
- Any name `checkName` accepts is a name the engine loads; any pair the engine calls duplicates, `checkName`
  refuses (except the `Main` rule, where the page is stricter).
- The later-clip notes agree with where the engine puts a clip.

**Non-Goals:**
- Mirroring the engine's error text, or validating in any place but the name dialog (a chapter name only
  enters the draft through `checkName`; names read from `reel.yaml` are already valid).

## Decisions

### Trim: an explicit Python `strip()` set, not `trim()`
**Context**: `trim()` removes U+FEFF and not U+001C..U+001F or U+0085; `str.strip()` is the reverse.
**Explored**: the two sets, by `chr(c).isspace()` against ECMAScript WhiteSpace and LineTerminator.
**Decision**: a `stripLikePython(s)` in `chapterNames.ts` removes, from both ends, exactly: U+0009..U+000D,
U+001C..U+001F, U+0020, U+0085, U+00A0, U+1680, U+2000..U+200A, U+2028, U+2029, U+202F, U+205F, U+3000.
**Rationale**: the only way a padded name reaches `reel.yaml` is through this function, so being equal to
`strip()` is what makes the engine's "no padding" rule unreachable from the GUI. U+FEFF is left alone, as
Python leaves it; it then counts as a name character, as in the engine.

### Casefold: a generated table for full case folding, not `toLowerCase`
**Context**: JavaScript has no `casefold`. `toUpperCase().toLowerCase()` handles `ß` but gets `ẞ`, the dotless
`ı` and Cherokee wrong, and `toLocaleLowerCase()` depends on the browser's locale.
**Explored**: round-trips of lower/upper/lower against the full `CaseFolding.txt` statuses C and F (Python's
`str.casefold` uses them; status T is excluded).
**Decision**: `casefold.ts` exports `casefold(s)`: for each code point, replace it by its full folding from a
table, else keep it. The table is every code point `c` where `chr(c).casefold() != chr(c)`, as `[code, folded]`
pairs (about 1,500 entries), generated from the engine's own Python with a documented one-liner kept in the
file's header (with the Python and Unicode versions it was generated with). It holds no locale logic.
**Rationale**: exactness is the user's decision ("the same rule"), and a table is the only way to get it
without a dependency (Principle VII: no new third-party package). The test pins it: spot cases (`ß`, `ẞ`, `ſ`,
final `ς`, `ı`, `İ`, `ﬃ`, Cherokee, Greek with ypogegrammeni) and a property check that `casefold` is
idempotent and that every table entry folds to itself.
**Alternatives**: `Intl.Collator({ sensitivity: 'accent' })` (locale-dependent, and also folds accents, which
the engine does not); `normalize('NFKC')` (changes more than case); a dependency (rejected).

### Folder matching: fold equality, not exact-then-fold
**Context**: the engine tries an exact name, then a casefold. Among chapter names that pass the engine's
duplicate rule, at most one chapter folds equal to a folder, so for choosing the chapter "exact first" and
"fold equal" give the same answer. Exact-first only matters between chapters, which cannot clash.
**Decision**: `chapterForFolder(listed, folder)` finds the listed chapter whose folded name equals the folded
folder. `laterClipNotes`, `ignoredStaying` and `homeOf` use it. Two folders on disk that fold equal (`a/` and
`A/` on a case-sensitive file system) both join that chapter, as the engine places them.
A note names the folder as the disk spells it; for several spellings, the exact one if it is among them, else
the first in code-unit order.
**Consequence for the notes**: a chapter renamed between two spellings of a folder's name (`Kvällen` to
`kvällen`) changes nothing for later clips, so the note rules compare "matched the folder before" with
"matches it after" by fold, and say nothing for such a rename.

### Refusal text
**Decision**: the `taken` refusal reads: `A chapter called “<clash>” already exists. Names that differ only in
letter case, such as ß and ss, count as the same.` (it replaces "Names are compared ignoring case."). The
`taken-deleted`, `empty` and `reserved` texts are unchanged, and so is `NameRefusal`, so `ChapterDialogs.tsx`
does not change.
**Rationale**: the old sentence promised "ignoring case", which a reader takes to mean `A`/`a` only; the
example says what the fold does without describing the algorithm.

## Risks / Trade-offs

- [The table follows Python's Unicode version; the engine host's Python upgrade could add folds] → the header
  records the generating version; a drift makes the page accept a name the engine rejects, which the save
  reports through the engine's existing refusal of an invalid `reel.yaml` (fail loud, nothing is written).
- [The gate's final wording of folder matching differs from the summary above] → the first task re-reads
  `place_disk_clips` and `Document.chapter` on `main` and adapts `chapterForFolder` to it before writing code.
- [Fold-equal folders or chapters make the notes ambiguous] → covered by the one-chapter-per-fold property
  and a unit test with `a/` and `A/`.
- [A bigger bundle: about 25 KB for the table] → acceptable for the Edit-mode chunk; checked in the build
  output size (no limit is set by the web-app spec).

## Migration Plan

None: no data changes. Chapter names already in a `reel.yaml` pass the engine's rules, so they pass the page's.
Rollback is a revert.
