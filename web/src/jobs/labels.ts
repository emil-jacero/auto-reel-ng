import type { CancelOutcome } from '../api/jobs'
import type { ConnectionStatus } from './store'

/*
 * Words for this slice's vocabularies, as `events/labels.ts` has for the
 * events': a `Record` over the union fails `tsc --noEmit` when the union gains,
 * loses or renames a member, so a slug can never reach the screen verbatim.
 */

export const CANCEL_OUTCOME_LABEL: Record<CancelOutcome, string> = {
  'flagged-running': 'Cancelling — the worker stops at the next segment.',
  'canceled-queued': 'Canceled before it started.',
  'no-op-terminal': 'The job had already finished.',
}

export const CONNECTION_LABEL: Record<ConnectionStatus, string> = {
  live: 'Live',
  connecting: 'Connecting…',
  reconnecting: 'Reconnecting…',
}

/** The sentences the event page and the list rows both use for the same enqueue answer. */
export const NOT_QUEUED = 'The render was not queued.'
export const NOT_CONFIRMED = 'The cancel was not confirmed.'
export const SCAN_FAILED = 'The project could not be scanned, so the render was not queued.'
export const COLLISION_FIX = 'Give one of them a distinct title or location in its reel.yaml.'

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
