import type { ChapterKey } from '../edit/draft.ts'
import { MOVE_REASON_WORDS, MOVING_WORDS, moveReason } from '../edit/marks.ts'
import type { MoveReason } from '../edit/marks.ts'

/*
 * What the Clip tab's Move to… offers and says (`clip-multi-select` D5), for one clip and for
 * several. Pure: no DOM, no React.
 */

export type MoveChoice = { key: ChapterKey; name: string }

/**
 * The chapters the picker lists, in order: every drawn chapter, less `own` for one clip (a clip
 * is already in its own chapter; several clips may be gathered at the end of any chapter).
 */
export function moveChoices(
  chapters: readonly { key: ChapterKey; name?: string }[],
  own: ChapterKey | null,
): MoveChoice[] {
  return chapters
    .filter((chapter) => chapter.key !== own)
    .map((chapter) => ({ key: chapter.key, name: chapter.name ?? chapter.key }))
}

/** `value` when the picker still lists it, else '' (a chosen chapter the clip then moved into). */
export function chosenOf(choices: readonly MoveChoice[], value: string): ChapterKey | '' {
  return choices.some((choice) => choice.key === value) ? value : ''
}

/**
 * Why Move cannot act, in words (a save or move first, then no chapter); null when it can.
 * `moving`: only a Move to… is pending, so the words say the clips move, not that a save runs.
 */
export function moveWhy(chosen: boolean, busy: boolean, moving = false): string | null {
  const reason: MoveReason | null = moveReason(1, chosen, busy)
  if (reason === null) {
    return null
  }
  return reason === 'busy' && moving ? MOVING_WORDS : MOVE_REASON_WORDS[reason]
}

/** What a group tab's Rotate and Ignore say while a save or a move is pending. */
export function groupBusy(moving: boolean): string {
  return moving ? MOVING_WORDS : MOVE_REASON_WORDS.busy
}

/** "3 clips selected". */
export function groupHeading(count: number): string {
  return `${count} clips selected`
}

/** Up to five names, then how many more: names "a, b, c, d, e" and "and 2 more". */
export function groupNames(names: readonly string[]): { shown: string[]; more: string | null } {
  const shown = names.slice(0, 5)
  const rest = names.length - shown.length
  return { shown, more: rest > 0 ? `and ${rest} more` : null }
}
