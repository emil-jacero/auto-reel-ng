import type { CancelOutcome } from '../api/jobs'
import { folderName } from '../events/common'
import type { ConnectionStatus } from './store'

/*
 * Words for this slice's vocabularies, as `events/labels.ts` has for the
 * events': a `Record` over the union fails `tsc --noEmit` when the union gains,
 * loses or renames a member, so a slug can never reach the screen verbatim.
 */

// A cancel's answer, told by a toast that ends with the event's name (`eventName`):
// '<label>: “Grillkväll med grannarna” · 2024-06-27'.
export const CANCEL_OUTCOME_LABEL: Record<CancelOutcome, string> = {
  'flagged-running': 'Render stopping at the next segment',
  'canceled-queued': 'Render canceled before it started',
  'no-op-terminal': 'Render had already finished',
}

export const CONNECTION_LABEL: Record<ConnectionStatus, string> = {
  live: 'Live',
  connecting: 'Connecting…',
  reconnecting: 'Reconnecting…',
}

// A toast's text is a string: these keep its line breaks out of the name's date.
const NO_BREAK_SPACE = '\u00a0'
const WORD_JOINER = '\u2060' // invisible; no line break before or after it

/**
 * How a toast names an event: its title, as the screens show it, then its date,
 * since titles repeat (two Midsommar events); with no title, its folder name,
 * which already starts with the date. The date is the event's `YYYY-MM-DD`, as the
 * screens write it. A toast puts the name last or before a colon, so its "·"
 * never sits inside a sentence. A wrapping toast never leaves the "·" at a line's
 * end or start, and never breaks the date at its hyphens.
 */
export function eventName(
  eventId: string,
  title: string | null | undefined,
  date: string | null | undefined,
): string {
  if (title == null) {
    return `“${folderName(eventId)}”`
  }
  if (date == null) {
    return `“${title}”`
  }
  const unbroken = date.split('-').join(`-${WORD_JOINER}`)
  return `“${title}”${NO_BREAK_SPACE}·${NO_BREAK_SPACE}${unbroken}`
}

/** The sentences the event page and the list rows both use for the same enqueue answer. */
export const NOT_QUEUED = 'The render was not queued.'
export const NOT_CONFIRMED = 'The cancel was not confirmed.'
export const SCAN_FAILED = 'The project could not be scanned, so the render was not queued.'
export const COLLISION_FIX = 'Give one of them a distinct title or location in its reel.yaml.'

/** The sentence after the clip names when a refused enqueue says what to do about them. */
export const MISSING_CLIPS_FIX = 'Restore them, or remove them in Edit mode.'

/**
 * The clips a refused enqueue names: every one, or with `limit` the first few and how many
 * more there are ("a.mp4, b.mp4, c.mp4 and 2 more"), for a toast that has little room.
 */
export function missingClipNames(missing: readonly string[], limit = missing.length): string {
  if (missing.length <= limit) {
    return missing.join(', ')
  }
  const more = missing.length - limit
  return `${missing.slice(0, limit).join(', ')} and ${more} more`
}

/** Why the page holds a render back while reel.yaml lists clips missing from disk, if it does. */
export function missingClipsReason(missing: readonly string[]): string | undefined {
  if (missing.length === 0) {
    return undefined
  }
  return missing.length === 1
    ? `${missing[0]} is missing from disk. Restore it, or remove it in Edit mode.`
    : `${missing.length} clips are missing from disk. Restore them, or remove them in Edit mode.`
}

/** A row's words in place of Render while its event lists a missing clip. */
export const MISSING_BLOCKS_ROW = 'Blocked by missing clips'
