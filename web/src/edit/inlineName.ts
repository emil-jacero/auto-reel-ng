import { stripLikePython } from './chapterNames.ts'
import type { NameRefusal } from './chapterNames.ts'

/*
 * What pressing a title and typing means (`InlineName.tsx`): the rules, pure so that they are
 * tested (`inlineName.test.ts`). A chapter's name is checked by `checkName`; the event's title,
 * which the main title card shows, is kept as typed.
 */

/** What a name check says: the name to keep, or why not (`checkName`'s answer). */
export type NameCheck =
  | { ok: true; name: string }
  | { ok: false; refusal: NameRefusal; clash: string | null }

/** What leaving the field does with the typed text. */
export type NameDecision =
  | { kind: 'keep'; name: string }
  | { kind: 'unchanged' }
  | { kind: 'refused'; refusal: NameRefusal; clash: string | null }

/**
 * Keep, close without an edit, or refuse `typed` for a title whose name is `current`. The name
 * `check` accepts that equals the current one, spaces around it aside, changes nothing.
 */
export function decideName(
  typed: string,
  current: string,
  check: (typed: string) => NameCheck,
): NameDecision {
  const result = check(typed)
  if (!result.ok) {
    return { kind: 'refused', refusal: result.refusal, clash: result.clash }
  }
  return stripLikePython(result.name) === stripLikePython(current)
    ? { kind: 'unchanged' }
    : { kind: 'keep', name: result.name }
}

/** The check for the event's title: any text is kept, as the metadata form keeps it. */
export function acceptAnything(typed: string): NameCheck {
  return { ok: true, name: typed }
}

/** Whether the field holds text that is not yet the name: the spaces around it do not count. */
export function nameUnsent(typed: string, current: string): boolean {
  return stripLikePython(typed) !== stripLikePython(current)
}

/** The title the main title card line shows, and where it comes from. */
export type TitleLine = { text: string; source: 'draft' | 'folder' | 'none' }

/** The word shown when the page has no title at all. */
export const UNTITLED = 'Untitled'

function nonBlank(value: string | null | undefined): string | null {
  return value != null && value.trim() !== '' ? value : null
}

/**
 * The draft's title when it is not blank, else the one the page resolved from the folder name,
 * else the word Untitled. The page never guesses a title.
 */
export function titleLine(draftTitle: string, resolvedTitle: string | null): TitleLine {
  const draft = nonBlank(draftTitle)
  if (draft !== null) {
    return { text: draft, source: 'draft' }
  }
  const resolved = nonBlank(resolvedTitle)
  return resolved !== null
    ? { text: resolved, source: 'folder' }
    : { text: UNTITLED, source: 'none' }
}

/** The main title card's note while the title differs from the one read: no file is named. */
export const FILE_NAME_NOTE =
  "Saving changes the movie's file name. If the movie was already rendered, the next render " +
  'saves it under the new name and the movie under its old name stays on disk.'
