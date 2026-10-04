import { stripLikePython } from './chapterNames.ts'
import type { NameRefusal } from './chapterNames.ts'

/*
 * What typing a name means (`card/NameField.tsx`, `card/nameField.ts`): the decision, pure so
 * that it is tested (`inlineName.test.ts`). A chapter's name is checked by `checkName`; the
 * event's title is kept as typed.
 */

/** What a name check says: the name to keep, or why not (`checkName`'s answer). */
export type NameCheck =
  | { ok: true; name: string }
  | { ok: false; refusal: NameRefusal; clash: string | null }

/** What the typed text does to the name. */
export type NameDecision =
  | { kind: 'keep'; name: string }
  | { kind: 'unchanged' }
  | { kind: 'refused'; refusal: NameRefusal; clash: string | null }

/**
 * Keep, change nothing, or refuse `typed` for a name that is `current`. The name `check`
 * accepts that equals the current one, spaces around it aside, changes nothing.
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

/** The word shown when the page has no title at all. */
export const UNTITLED = 'Untitled'

/** The note while the event's title differs from the one read: no file is named. */
export const FILE_NAME_NOTE =
  "Saving changes the movie's file name. If the movie was already rendered, the next render " +
  'saves it under the new name and the movie under its old name stays on disk.'
