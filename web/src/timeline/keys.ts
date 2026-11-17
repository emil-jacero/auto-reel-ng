/*
 * The playhead's keys (spec: "operable by keyboard, a frame at a time"). Which key
 * moves it how far; the position arithmetic is `position.ts`. Pure.
 */

import { slotWords } from './reorder.ts'
import type { DrawnChapter, DropSlot } from './reorder.ts'

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

/** What `clipMoveKey` reads of a keydown. */
export type MoveKeyPress = {
  key: string
  altKey: boolean
  ctrlKey: boolean
  metaKey: boolean
  shiftKey: boolean
  altGraph: boolean
}

/**
 * Alt+Left (-1) or Alt+Right (+1) moves the selected clip one place (`track-drag-edit`, D4); null
 * for anything else. Alt alone: with Ctrl, Cmd, Shift or AltGr it is another chord (AltGr
 * is Ctrl+Alt on Windows), and the playhead's arrows, with no Alt, stay the playhead's. The
 * handler calls `preventDefault` only for a non-null answer it acts on, so the browser's Alt+Arrow
 * history keys work wherever no clip is selected.
 */
export function clipMoveKey(press: MoveKeyPress): -1 | 1 | null {
  if (!press.altKey || press.ctrlKey || press.metaKey || press.shiftKey || press.altGraph) {
    return null
  }
  if (press.key === 'ArrowLeft') {
    return -1
  }
  return press.key === 'ArrowRight' ? 1 : null
}

/** A neighbouring place for the clip: the slot (as `applyDrop` takes it) and its words. */
export type StepResult =
  | { kind: 'slot'; slot: DropSlot }
  | { kind: 'edge'; words: string }
  | null

/**
 * The slot one place `way` from `identity` in the drawn order: the next boundary in its chapter,
 * or, off a chapter's end, the neighbour chapter's other end (the last clip of "Main" with +1
 * becomes the first of "Kvällen"). `edge` when it is already the first or the last clip of the
 * lay; null when it is in no drawn chapter.
 */
export function stepSlot(
  chapters: readonly DrawnChapter[],
  identity: string,
  way: -1 | 1,
): StepResult {
  const at = chapters.findIndex((chapter) => chapter.identities.includes(identity))
  if (at === -1) {
    return null
  }
  const chapter = chapters[at]
  const place = chapter.identities.indexOf(identity)
  const name = (c: DrawnChapter) => c.name ?? c.key
  const base = identity.slice(identity.lastIndexOf('/') + 1)
  const slot = (target: DrawnChapter, index: number, rest: readonly string[]): StepResult => {
    const beforeIdentity = rest[index] ?? null
    return {
      kind: 'slot',
      slot: { chapter: target.key, index, beforeIdentity, words: slotWords(beforeIdentity, name(target)) },
    }
  }
  const others = chapter.identities.filter((id) => id !== identity)
  if (way === 1) {
    if (place < chapter.identities.length - 1) {
      return slot(chapter, place + 1, others)
    }
    const next = chapters[at + 1]
    return next === undefined
      ? { kind: 'edge', words: `${base} is already the last clip.` }
      : slot(next, 0, next.identities)
  }
  if (place > 0) {
    return slot(chapter, place - 1, others)
  }
  const previous = chapters[at - 1]
  return previous === undefined
    ? { kind: 'edge', words: `${base} is already the first clip.` }
    : slot(previous, previous.identities.length, previous.identities)
}
