import { OWN_CHAPTER_NOTE } from './chapterNames.ts'
import { MARK_HINT } from './marks.ts'

/*
 * The Clips section's Help (`help-text-declutter`): the words that used to sit above and beside
 * the chapters, in the order they were read. Pure, so the sentences are tested without the page.
 */

export const REORDER_SEVERAL =
  'Drag a clip by its handle, or use its arrows, to reorder it. Drag it into another chapter to ' +
  'move it there; mark clips and use Move marked to… to move several at once.'

export const REORDER_ONE =
  'Drag a clip by its handle, or use its arrows. To split the event into chapters, use Add ' +
  'chapter below the chapters; clips can then be dragged between them.'

export const IGNORED_NOTE = 'Ignored clips are not played and cannot be moved.'

export const MISSING_NOTE =
  'A missing clip is not on disk and stays in its chapter: restore the file, or remove it from reel.yaml.'

export function clipsHelpLines(opts: {
  /** The event lists more than one chapter. */
  several: boolean
  hasIgnored: boolean
  hasMissing: boolean
  /** The event's own chapter is listed (its tools row used to carry OWN_CHAPTER_NOTE). */
  ownChapter: boolean
}): string[] {
  const lines = [opts.several ? REORDER_SEVERAL : REORDER_ONE]
  if (opts.hasIgnored) {
    lines.push(IGNORED_NOTE)
  }
  if (opts.hasMissing) {
    lines.push(MISSING_NOTE)
  }
  lines.push(MARK_HINT)
  if (opts.ownChapter && opts.several) {
    lines.push(OWN_CHAPTER_NOTE)
  }
  return lines
}

/**
 * What saving will add, as a line of its own while any new clip exists; the state stays visible.
 * `adopted` is the count that saving writes into reel.yaml, `waiting` whether a new clip waits
 * for one of the saves that writes it.
 */
export function newClipsLine(adopted: number, waiting: boolean, adoptedWords: string): string | null {
  if (adopted > 0) {
    return `Saving adds ${adoptedWords} to reel.yaml.`
  }
  return waiting
    ? 'A new clip joins reel.yaml once its chapter’s order, one of its cuts, or the list of chapters is saved.'
    : null
}
