/*
 * What a chapter that plays no clip says in Edit mode (its row in the Chapters list,
 * ChapterList.tsx). Kept apart, with no imports, so it can be tested without React.
 */

const LEFT_OUT = 'A chapter without clips is left out of the movie.'
const MOVE_IN = 'Move clips into it with Move to… (the Clip tab’s, or a clip’s menu).'

/**
 * `alone`: the event lists no other chapter, so no chapter has a clip to move into this one
 * and the page offers no Move to… (it needs a second chapter). `wholly`: nothing is
 * listed in the chapter at all, no removed or ignored clip either ("No clips."), else it
 * only "plays no clip".
 */
export function emptyChapterWords(alone: boolean, wholly: boolean): string {
  const lead = wholly ? 'No clips.' : 'It plays no clip.'
  return alone ? `${lead} ${LEFT_OUT}` : `${lead} ${MOVE_IN} ${LEFT_OUT}`
}

/**
 * Whether a chapter holds nothing at all ("No clips."), as opposed to playing no clip. An
 * ignored clip counts even when the wide bin lists it apart (`ignoredApart`), so the words
 * do not depend on where the page lists it.
 */
export function holdsNothing(played: number, removed: number, ignored: number): boolean {
  return played === 0 && removed === 0 && ignored === 0
}
