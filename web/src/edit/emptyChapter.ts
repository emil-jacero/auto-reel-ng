/*
 * What a chapter that plays no clip says in Edit mode (ClipOrderList.tsx). Kept apart, with
 * no imports, so it can be tested without React.
 */

const LEFT_OUT = 'A chapter without clips is left out of the movie.'
const MOVE_IN = 'Drag clips here, or move them here with Move marked to….'

/**
 * `alone`: the event lists no other chapter, so no chapter has a clip to drag here and the
 * page offers no Move marked to… (it needs a second chapter). `wholly`: nothing is
 * listed in the chapter at all, no removed or ignored clip either ("No clips."), else it
 * only "plays no clip".
 */
export function emptyChapterWords(alone: boolean, wholly: boolean): string {
  const lead = wholly ? 'No clips.' : 'It plays no clip.'
  return alone ? `${lead} ${LEFT_OUT}` : `${lead} ${MOVE_IN} ${LEFT_OUT}`
}
