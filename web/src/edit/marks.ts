/*
 * Marks: the clips the operator picked to move together (`clip-group-select-drag`). Pure
 * functions over a set of identities and the words Edit mode says about them, with no runtime
 * imports so `npm test` covers them. The set lives in the editor's state beside the draft, never
 * in it: marking is not an edit, so it cannot make the page dirty (draft.ts `isDirty` reads the
 * draft alone).
 */

/** One shared empty set: a state with no marks keeps the same object. */
export const NO_MARKS: ReadonlySet<string> = new Set()

/** `marked` with `identity` marked (`on`) or unmarked; the same set when nothing changes. */
export function toggleMark(
  marked: ReadonlySet<string>,
  identity: string,
  on: boolean,
): ReadonlySet<string> {
  if (marked.has(identity) === on) {
    return marked
  }
  const next = new Set(marked)
  if (on) {
    next.add(identity)
  } else {
    next.delete(identity)
  }
  return next.size === 0 ? NO_MARKS : next
}

/** No marks. */
export function clearMarks(marked: ReadonlySet<string>): ReadonlySet<string> {
  return marked.size === 0 ? marked : NO_MARKS
}

/**
 * `marked` less every identity not in `playedOnDisk` (the clips a listed chapter plays that are
 * on disk): a stale or missing or ignored identity is dropped. The same set when none is.
 */
export function pruneMarks(
  marked: ReadonlySet<string>,
  playedOnDisk: ReadonlySet<string>,
): ReadonlySet<string> {
  const kept = [...marked].filter((identity) => playedOnDisk.has(identity))
  return kept.length === marked.size ? marked : kept.length === 0 ? NO_MARKS : new Set(kept)
}

/** `marked` less the clips a move took; the same set when it took none of them. */
export function afterMove(
  marked: ReadonlySet<string>,
  moved: Iterable<string>,
): ReadonlySet<string> {
  const gone = new Set(moved)
  const kept = [...marked].filter((identity) => !gone.has(identity))
  return kept.length === marked.size ? marked : kept.length === 0 ? NO_MARKS : new Set(kept)
}

function clips(count: number): string {
  return `${count} ${count === 1 ? 'clip' : 'clips'}`
}

/** "No clips marked", "1 clip marked", "3 clips marked": the marks line's count. */
export function countWords(count: number): string {
  return count === 0 ? 'No clips marked' : `${clips(count)} marked`
}

/** What marking or unmarking a clip says: "s1710003.mp4 marked. 2 clips marked." */
export function markWords(name: string, on: boolean, count: number): string {
  return `${name} ${on ? 'marked' : 'unmarked'}. ${countWords(count)}.`
}

export const CLEARED_WORDS = 'Marks cleared.'

/** The marks line's sentence: how clips are marked and what a marked clip's handle does. */
export const MARK_HINT =
  'Mark clips with the box at the top right of their frames; dragging a marked clip’s handle, ' +
  'or Move marked to…, moves all marked clips together. Missing and ignored clips cannot be marked.'

/** What Move marked to… says: "3 clips moved to “Dag 2”." (the singular for one clip). */
export function movedWords(count: number, chapter: string): string {
  return `${clips(count)} moved to “${chapter}”.`
}

/** What a press that changes nothing says. */
export const NOTHING_MOVED = 'Nothing moved.'

/** Why Move is unavailable, in words; null when it is available. */
export type MoveReason = 'busy' | 'no-marks' | 'no-chapter'

export const MOVE_REASON_WORDS: Record<MoveReason, string> = {
  busy: 'Unavailable while saving.',
  'no-marks': 'Mark a clip to move it.',
  'no-chapter': 'Choose a chapter.',
}

/** The first reason Move cannot act (a save first, then marks, then chapter); null when it can. */
export function moveReason(marks: number, chosen: boolean, busy = false): MoveReason | null {
  if (busy) {
    return 'busy'
  }
  return marks === 0 ? 'no-marks' : chosen ? null : 'no-chapter'
}

/** The sentence added to the keyboard instructions while two or more clips are marked. */
export const GROUP_INSTRUCTIONS =
  ' A marked clip moves with all the marked clips; an unmarked clip moves alone.'

/** "starting at position 1 of 3": where a group's run starts and how many clips are there then. */
function startsAt(position: number, total: number): string {
  return `starting at position ${position} of ${total}`
}

/** What the group drag says. `heading` is null within the group's only chapter (no name). */
export const groupWords = {
  /** "Picked up 3 marked clips." */
  lift: (count: number): string => `Picked up ${count} marked clips.`,
  /** "3 marked clips are over “Main”, starting at position 1 of 4." */
  over: (count: number, heading: string | null, position: number, total: number): string =>
    heading === null
      ? `${count} marked clips are over this chapter, ${startsAt(position, total)}.`
      : `${count} marked clips are over “${heading}”, ${startsAt(position, total)}.`,
  /** "3 clips moved to “Main”, starting at position 1 of 4." */
  drop: (count: number, heading: string | null, position: number, total: number): string =>
    heading === null
      ? `${count} clips moved, ${startsAt(position, total)}.`
      : `${count} clips moved to “${heading}”, ${startsAt(position, total)}.`,
  /** "3 marked clips dropped, unchanged." */
  unchanged: (count: number): string => `${count} marked clips dropped, unchanged.`,
  /** "Move cancelled. 3 marked clips are back where they were." */
  cancel: (count: number): string =>
    `Move cancelled. ${count} marked clips are back where they were.`,
  /** The copy's badge: "3 clips to “Main”, starting at position 1 of 4" (no name: no "to"). */
  badge: (count: number, heading: string | null, position: number, total: number): string =>
    heading === null
      ? `${count} clips, ${startsAt(position, total)}`
      : `${count} clips to “${heading}”, ${startsAt(position, total)}`,
  /** A held row's words for assistive technology. */
  held: 'Held with the marked clips.',
}
