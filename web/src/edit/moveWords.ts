/*
 * What Edit mode says about moving clips: the count of a Move to…, the press that changes
 * nothing, and why a move control is unavailable. No imports, so `npm test` covers them without
 * React. The Clip tab's Move to… (`timeline/moveTo.ts`) and the editor's announcements use them.
 */

function clips(count: number): string {
  return `${count} ${count === 1 ? 'clip' : 'clips'}`
}

/** What Move to… says: "3 clips moved to “Dag 2”." (the singular for one clip). */
export function movedWords(count: number, chapter: string): string {
  return `${clips(count)} moved to “${chapter}”.`
}

/** What a press that changes nothing says. */
export const NOTHING_MOVED = 'Nothing moved.'

/** What an Ignore that ignores nothing says (every clip missing from disk or not played). */
export const NOTHING_IGNORED = 'Nothing ignored.'

/**
 * What a drop of a selected group on the video track says: one ignored clip's row of several
 * selected drags the clip, and a group is not dropped there (`plain-clip-bin`, "A marked group is
 * not dropped on the video track"). The Clip tab's Include clips includes them.
 */
export const GROUP_DROP_WORDS =
  'A group of clips cannot be dropped on the video track. Nothing moved. Include clips in the Clip tab includes them.'

/** Why a move control is unavailable while a save is in flight. */
export const SAVING_WORDS = 'Unavailable while saving.'

/** Why Move to… is unavailable until a chapter is chosen. */
export const CHOOSE_CHAPTER_WORDS = 'Choose a chapter.'

/**
 * What a control says while only the move of the selected clips (Move to…) is pending and nothing
 * is saving: the clips are moving, so it is not "saving" (`clip-multi-select` D6).
 */
export const MOVING_WORDS = 'Unavailable while the clips move.'
