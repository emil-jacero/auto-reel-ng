import { OWN_CHAPTER_NOTE } from './chapterNames.ts'

/*
 * The Clips section's Help (`help-text-declutter`): the words that used to sit above and beside
 * the chapters, in the order they were read. Pure, so the sentences are tested without the page.
 */

export const SELECT_NOTE = 'Press a clip to select it; Ctrl or Cmd adds one, Shift selects a range.'

export const MENU_NOTE = 'Right-click a clip, or press Shift+F10, for its menu.'

export const MOVE_NOTE =
  'Move clips on the Timeline, or with Move earlier, Move later and Move to… in the Clip tab.'

export const IGNORED_NOTE =
  'Ignored clips are not played; drag one onto the Timeline to include it.'

export const MISSING_NOTE =
  'A missing clip is not on disk and stays in its chapter: restore the file, or remove it from reel.yaml.'

export const NEW_CLIP_NOTE =
  'A new clip joins reel.yaml once its chapter’s order, one of its cuts, or the list of chapters is saved.'

export function clipsHelpLines(opts: {
  /** The event lists more than one chapter (the own chapter's note is for those). */
  several: boolean
  hasIgnored: boolean
  hasMissing: boolean
  /** The event's own chapter is listed (its tools row used to carry OWN_CHAPTER_NOTE). */
  ownChapter: boolean
  /** A new clip waits (the workspace drops the bin's own line for it). */
  hasNewClip?: boolean
}): string[] {
  const lines = [SELECT_NOTE, MENU_NOTE, MOVE_NOTE]
  if (opts.hasIgnored) {
    lines.push(IGNORED_NOTE)
  }
  if (opts.hasMissing) {
    lines.push(MISSING_NOTE)
  }
  if (opts.ownChapter && opts.several) {
    lines.push(OWN_CHAPTER_NOTE)
  }
  if (opts.hasNewClip) {
    lines.push(NEW_CLIP_NOTE)
  }
  return lines
}

/**
 * The stacked page's line about new clips: what saving will add while a save adds any
 * (`adopted` of them, as `adoptedWords`), else `NEW_CLIP_NOTE` while one waits for a save that
 * writes it (`waiting`), else null. The workspace's bin shows no such line: the same note is in
 * the Clips help (`clipsHelpLines`) and the top bar's summary says what saving adds.
 */
export function newClipsLine(adopted: number, waiting: boolean, adoptedWords: string): string | null {
  if (adopted > 0) {
    return `Saving adds ${adoptedWords} to reel.yaml.`
  }
  return waiting ? NEW_CLIP_NOTE : null
}
