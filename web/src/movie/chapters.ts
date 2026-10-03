import { formatTime } from '../cuts/times.ts'

/*
 * The rendered movie's chapters, as the event detail gives them (`facts.ts`): which
 * list may be relied on, which chapter a position is in, and how a jump is named.
 *
 * Pure, with no browser and no React, so `npm test` runs it under Node as it is. A
 * start is only ever read from the detail: nothing here computes, sums or estimates
 * one (a list with one wrong start is worse than none).
 */

/** One chapter of the movie as rendered: its recorded name (`""` is the default chapter) and start. */
export type ChapterMark = { name: string; start: number }

/** Whether a name is one the render could have recorded: empty, or not only spaces. */
function usableName(name: unknown): name is string {
  return typeof name === 'string' && (name === '' || name.trim() !== '')
}

/**
 * The chapters when every one of them can be relied on, otherwise `null`: at least
 * one; each start a finite number of seconds, not negative; the starts strictly
 * increasing; each name text that is empty (the default chapter) or not only spaces.
 * The array comes back as it is, never sorted, filtered or repaired.
 */
export function usableChapters(raw: unknown): ChapterMark[] | null {
  if (!Array.isArray(raw) || raw.length === 0) {
    return null
  }
  let previous = -Infinity
  for (const entry of raw as unknown[]) {
    if (typeof entry !== 'object' || entry === null) {
      return null
    }
    const { name, start } = entry as { name?: unknown; start?: unknown }
    if (!usableName(name) || typeof start !== 'number' || !Number.isFinite(start) || start < 0) {
      return null
    }
    if (start <= previous) {
      return null
    }
    previous = start
  }
  return raw as ChapterMark[]
}

/** A list needs a place to jump from and one to jump to. */
const LEAST_LISTED = 2

/**
 * The chapters the list shows: the usable ones when there are two or more. A movie
 * of one chapter (the archive's usual event: one default chapter) has nothing to
 * jump between.
 */
export function listedChapters(raw: unknown): ChapterMark[] | null {
  const usable = usableChapters(raw)
  return usable !== null && usable.length >= LEAST_LISTED ? usable : null
}

/**
 * The index of the chapter `position` (seconds) is in: the last whose start is at or
 * before it, where up to `slack` seconds short of a start counts as at it (a browser's
 * seek may land a frame short). `null` before the first. Compared in whole
 * milliseconds, as the engine records them, so `start - slack` has no rounding drift.
 */
export function currentChapterIndex(
  chapters: readonly ChapterMark[],
  position: number,
  slack = 0.06,
): number | null {
  if (!Number.isFinite(position)) {
    return null
  }
  const at = Math.round(position * 1000)
  const room = Math.round(slack * 1000)
  let found: number | null = null
  for (let i = 0; i < chapters.length; i += 1) {
    if (at >= Math.round(chapters[i].start * 1000) - room) {
      found = i
    } else {
      break
    }
  }
  return found
}

/**
 * A jump button's accessible name: `Jump to chapter 2, Majstången, at 1:14`. For the
 * chapter the player is in, `mark` (the words the row shows) follows, so every visible
 * word of the button is also in its name (WCAG 2.5.3, Label in Name).
 */
export function jumpLabel(index: number, title: string, start: number, mark?: string): string {
  const label = `Jump to chapter ${index + 1}, ${title}, at ${formatTime(start)}`
  return mark === undefined ? label : `${label}, ${mark.toLowerCase()}`
}
