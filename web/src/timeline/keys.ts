/*
 * The playhead's keys (spec: "operable by keyboard, a frame at a time"). Which key
 * moves it how far; the position arithmetic is `position.ts`. Pure.
 */

export type KeyAction =
  // this many frames of the clip the playhead is in, across boundaries (negative: back)
  | { kind: 'frames'; n: number }
  // this many ms along the whole timeline
  | { kind: 'ms'; ms: number }
  | { kind: 'to'; where: 'start' | 'end' }
  | { kind: 'toggle' }

/** One second with Shift, five with Page Up and Page Down. */
export const SECOND_MS = 1000
export const PAGE_MS = 5000

/** What a key does to the playhead, or null for a key that is not its own. */
export function playheadKey(key: string, shift: boolean): KeyAction | null {
  switch (key) {
    case 'ArrowLeft':
    case 'ArrowDown':
      return shift ? { kind: 'ms', ms: -SECOND_MS } : { kind: 'frames', n: -1 }
    case 'ArrowRight':
    case 'ArrowUp':
      return shift ? { kind: 'ms', ms: SECOND_MS } : { kind: 'frames', n: 1 }
    case 'PageDown':
      return { kind: 'ms', ms: -PAGE_MS }
    case 'PageUp':
      return { kind: 'ms', ms: PAGE_MS }
    case 'Home':
      return { kind: 'to', where: 'start' }
    case 'End':
      return { kind: 'to', where: 'end' }
    case ' ':
    case 'Spacebar':
      return { kind: 'toggle' }
    default:
      return null
  }
}
