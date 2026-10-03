import type { Clip } from '../api/event.ts'

/*
 * Which file a clip's preview plays, and the words that say so (D-16, D-21): the
 * clip's preview copy when the event detail says one is ready, else the original.
 * The choice is a function of the detail alone, made when the preview opens, so a
 * clip with no usable copy costs no request. Pure: no DOM, no React, and type-only
 * imports, so `npm test` runs it as it is.
 */

/** A clip's proxy as the event detail gives it (the generated schema's `ProxyOut`). */
export type ClipProxy = NonNullable<Clip['proxy']>

/** Why the original plays when it is what the detail leads to. */
export type OriginalWhy = 'absent' | 'stale' | 'failed' | 'unusable'

/**
 * The file the detail leads to: the copy, with the clip's length in whole milliseconds
 * (the facts' duration: the original's, as the engine probed it), or the original and why.
 */
export type PreviewSource =
  { kind: 'copy'; durationMs: number } | { kind: 'original'; why: OriginalWhy }

/**
 * Whole milliseconds of the facts' duration (seconds), or null when it is not a finite
 * number above zero. Never defaulted or guessed (Principle I).
 */
export function copyLengthMs(facts: { duration?: unknown } | null | undefined): number | null {
  const seconds = facts?.duration
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds <= 0) {
    return null
  }
  const ms = Math.round(seconds * 1000)
  return ms > 0 ? ms : null
}

/**
 * The copy when the state is `ready` and its facts give a usable duration; else the
 * original: `stale` and `failed` as such, a `ready` state without a usable duration as
 * `unusable` (a contract break, told and not guessed), and everything else, a detail
 * with no proxy and a state this client does not know included, as `absent`.
 */
export function previewSource(proxy: ClipProxy | null | undefined): PreviewSource {
  switch (proxy?.state) {
    case 'ready': {
      const durationMs = copyLengthMs(proxy.facts)
      return durationMs === null
        ? { kind: 'original', why: 'unusable' }
        : { kind: 'copy', durationMs }
    }
    case 'stale':
      return { kind: 'original', why: 'stale' }
    case 'failed':
      return { kind: 'original', why: 'failed' }
    default:
      return { kind: 'original', why: 'absent' }
  }
}

// The words. `<name>` is the clip's name as its row names it.

export const SOURCE_COPY = 'Playing the preview copy'
export const SOURCE_ORIGINAL = 'Playing the original'
export const PLAY_ORIGINAL = 'Play original'
export const PLAY_COPY = 'Play preview copy'

/** Why the original plays by default; `absent` is the common case and says nothing more. */
export const ORIGINAL_WHY: Record<Exclude<OriginalWhy, 'absent'>, string> = {
  stale: 'its preview copy is out of date',
  failed: 'its preview copy could not be built',
  unusable: 'its preview copy has no usable length',
}

/**
 * The line under the picture. The reason is given only when the original plays because
 * the detail leads there (`why`), not when the operator chose it over a ready copy.
 */
export function sourceLine(plays: 'copy' | 'original', why: OriginalWhy | null): string {
  if (plays === 'copy') {
    return SOURCE_COPY
  }
  return why === null || why === 'absent'
    ? SOURCE_ORIGINAL
    : `${SOURCE_ORIGINAL}: ${ORIGINAL_WHY[why]}.`
}

export const playOriginalName = (name: string) => `${PLAY_ORIGINAL} of ${name}`
export const playCopyName = (name: string) => `${PLAY_COPY} of ${name}`

/** Announced after the control is pressed: `Playing the original of s1710001.mp4.` */
export const playingOriginalWords = (name: string) => `${SOURCE_ORIGINAL} of ${name}.`
export const playingCopyWords = (name: string) => `${SOURCE_COPY} of ${name}.`

/** What the no-sound note adds while a ready copy exists: the way to the sound. */
export const COPY_HAS_SOUND = `The preview copy plays with sound. Press ${PLAY_COPY}.`

/** The no-sound note's detail, with the way to the sound added when a copy is ready. */
export const withCopySentence = (detail: string, copyReady: boolean) =>
  copyReady ? `${detail} ${COPY_HAS_SOUND}` : detail

// A copy that cannot be played: titles name the preview copy, never "changed on disk".

const OWN_FILE = "Play original plays the clip's own file."

export const copyGoneTitle = (name: string) => `The preview copy of ${name} is no longer there.`
/** The service's detail, ended as a sentence (the 404's has no full stop), then the way out. */
export const copyGoneDetail = (detail: string) => {
  const said = detail.trim()
  return `${/[.!?]$/.test(said) ? said : `${said}.`} ${OWN_FILE}`
}

export const copyUnreadableTitle = (name: string) =>
  `The preview copy of ${name} could not be read.`

export const copyEmptyTitle = (name: string) => `The preview copy of ${name} is empty.`
export const copyEmptyDetail = `There is nothing to play. ${OWN_FILE}`

export const copyCannotPlayTitle = (name: string) =>
  `This browser cannot play the preview copy of ${name}.`
export const copyCannotPlayDetail = `The service serves it and this browser refuses it. ${OWN_FILE}`
