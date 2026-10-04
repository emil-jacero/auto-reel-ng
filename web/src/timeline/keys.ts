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

/** The track's zoom keys: zoom in, out, Fit, and Fit and back (`\\`). */
export const TRACK_ZOOM_KEYS: readonly string[] = ['+', '=', '-', '_', '0', '\\']

/** What `trackZoomKey` reads of a keydown (`altGraph` is `getModifierState('AltGraph')`). */
export type ZoomKeyPress = {
  key: string
  ctrlKey: boolean
  altKey: boolean
  metaKey: boolean
  altGraph: boolean
}

/**
 * The track zoom key a keydown is, or null. Cmd never (the browser's own zoom), Ctrl alone never
 * (Ctrl+`-` and Ctrl+`0` are the browser's zoom too). A character typed with AltGr is the key it
 * typed: Linux reports AltGraph, Windows reports AltGr as Ctrl+Alt together. `\` alone also takes
 * Alt, because macOS types it with Option on many layouts (Swedish, German: Shift+Option+7).
 */
export function trackZoomKey(press: ZoomKeyPress): string | null {
  const { key, ctrlKey, altKey, metaKey, altGraph } = press
  if (metaKey || !TRACK_ZOOM_KEYS.includes(key)) {
    return null
  }
  if (!ctrlKey && !altKey) {
    return key
  }
  if (altGraph || (ctrlKey && altKey)) {
    return key
  }
  return key === '\\' && altKey ? key : null
}
