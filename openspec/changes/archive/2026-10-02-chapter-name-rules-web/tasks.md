## 1. web/src/edit: the engine's two rules

- [x] 1.1 Re-read `chapter-name-rules-engine` on `main` (its design, `Document.chapter`, `place_disk_clips`)
  and confirm the strip, casefold and folder-matching rules this change's design mirrors; adapt the design
  and specs here if the merged wording differs. Verify by `openspec validate chapter-name-rules-web --strict`.
- [x] 1.2 Add `casefold.ts` exporting `casefold(s)` from a generated full-case-folding table, with the
  generating one-liner, Python and Unicode versions in its header. Verify with `casefold.test.ts` (`node:test`):
  `ß`, `ẞ`, `ſ`, final `ς`, `ı` (kept apart from `i`), `İ`, `ﬃ`, Cherokee, Greek with ypogegrammeni against
  values taken from Python 3.14 `str.casefold`; idempotence; every table entry folds to itself.
- [x] 1.3 In `chapterNames.ts` add `stripLikePython` (the set in the design) and use it in `checkName` in
  place of `trim()`. Verify with `chapterNames.test.ts`: U+0085, U+001C and U+3000 padding are removed, U+FEFF
  is not, a name of only those characters is refused as `empty`, and `trim()` and `stripLikePython` are shown
  to differ on U+0085 and U+FEFF.
- [x] 1.4 Replace `toLocaleLowerCase` with `casefold` in `checkName`'s duplicate and `Main` checks, keep the
  deleted-chapter clash and the own-name-back acceptance, and reword the `taken` refusal. Verify in
  `chapterNames.test.ts`: `STRASSE`, `strasse` and `ẞ` clash with `Straße` (`taken`, naming it); a deleted
  `Straße` gives `taken-deleted`; `ı` does not clash with `i`; `main`, `MAIN` still give `reserved`; renaming
  `Kvällen` to `KVÄLLEN` is accepted.

## 2. web/src/edit: folders follow the fold

- [x] 2.1 Add `chapterForFolder` and use it in `laterClipNotes` (including its before/after comparison and the
  folder's own spelling in the message), `homeOf` and `ignoredStaying`. Verify in `chapterNames.test.ts`: a
  folder `kvällen` is taken by chapter `Kvällen`; renaming `Kvällen` to `kvällen` yields no note; renaming it
  to `Kväll` yields the "no chapter will be named after the folder" note, in the folder's spelling; folders
  `a` and `A` both join chapter `a`; an ignored clip of `kvällen/` stays with `Kvällen`; the existing
  note tests still pass.
- [x] 2.2 Update the comments in `chapterNames.ts` ("the engine checks exact duplicates only", "names compared
  exactly") to state the shared rules and that `Main` is the page's alone, and amend HLD D-13 with a sentence
  that the page follows the engine's chapter-name rules (date, change name, the user's answer). Verify by
  reading the diff for no remaining claim of exact folder matching: `grep -n "exact" web/src/edit/chapterNames.ts`.

## 3. Validation

- [x] 3.1 Run `npm test`, `npx tsc --noEmit` and `npm run build` in the node container. Verify all three exit
  zero and that the new test files run (test count rises).
- [x] 3.2 Playwright check (scratch script, real browser, light and dark at 1280 and 390, writes intercepted)
  on a scratch dev-library event with chapters `Straße` and a folder `Kvällen`: adding `STRASSE` and renaming
  to `strasse` show the new `taken` message at the name field with focus kept; a name padded with U+0085 is
  added trimmed; renaming `Kvällen` to `kvällen` shows no later-clips note; adding `KVÄLLEN` after renaming
  `Kvällen` to `Kväll` shows the "will join this chapter" note. Verify by looking at the screenshots.
