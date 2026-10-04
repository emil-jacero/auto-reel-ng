import type { EventDetail } from '../api/event'
import type { ReelDocument } from '../api/reel'

/*
 * The event's poster in the editor, as pure functions (event-poster-gui). `reel.yaml` holds
 * `poster: {clip, at}`: a clip identity and seconds into that clip, before its cuts. The draft
 * holds it three ways: `undefined` (as read), `null` (removed: the default frame) or a pick.
 * An entry equal to what was read is dropped, so an untouched poster writes nothing.
 */

/** A chosen frame: a clip and a time in it, in seconds to the millisecond. */
export type PosterPick = { clip: string; at: number }

/** The draft's poster: as read (`undefined`), removed (`null`) or chosen. */
export type PosterDraft = PosterPick | null | undefined

export const POSTER_CHANGED = 'poster changed'
export const DEFAULT_WORDS = 'Default: first clip'
export const CHOSEN_WORDS = 'Chosen frame'
export const UNSAVED_WORDS = 'Chosen frame, not saved'
export const USE_AS_POSTER = 'Use as poster'
export const USE_DEFAULT = 'Use default'
export const NOT_PLAYED_WORDS = 'This clip does not play, the default is used.'

/** The poster `reel.yaml` holds, or null. */
export function readPoster(read: ReelDocument): PosterPick | null {
  const poster = read.poster
  return poster == null ? null : { clip: poster.clip, at: poster.at }
}

export function samePoster(a: PosterPick | null, b: PosterPick | null): boolean {
  return a === b || (a !== null && b !== null && a.clip === b.clip && a.at === b.at)
}

/** The poster the draft has now. */
export function posterNow(read: ReelDocument, draft: PosterDraft): PosterPick | null {
  return draft === undefined ? readPoster(read) : draft
}

/** `next` as a draft entry: `undefined` when it is what was read. */
export function posterEntry(read: ReelDocument, next: PosterPick | null): PosterDraft {
  return samePoster(next, readPoster(read)) ? undefined : next
}

/** Whether the draft's poster differs from the one read. */
export function posterChanged(read: ReelDocument, draft: PosterDraft): boolean {
  return draft !== undefined && !samePoster(draft, readPoster(read))
}

/** The write body's `poster`: only when it changed (`null` removes it); absent keeps it. */
export function posterBody(read: ReelDocument, draft: PosterDraft): { poster?: PosterPick | null } {
  return posterChanged(read, draft) ? { poster: draft } : {}
}

export type PosterState = 'default' | 'chosen' | 'unsaved'

/**
 * What the poster area says. A saved poster the detail reports as `default` (its clip does not
 * play) is the default. A draft pick that differs from the saved one is "not saved".
 */
export function posterState(read: ReelDocument, draft: PosterDraft, event: EventDetail): PosterState {
  const now = posterNow(read, draft)
  if (now === null) {
    return 'default'
  }
  if (posterChanged(read, draft)) {
    return 'unsaved'
  }
  return event.poster?.source === 'event' ? 'chosen' : 'default'
}

export function posterStateWords(state: PosterState): string {
  return state === 'default' ? DEFAULT_WORDS : state === 'chosen' ? CHOSEN_WORDS : UNSAVED_WORDS
}

/** Whether the pick's clip is still played by the draft (listed in a chapter's order). */
export function playedInDraft(pick: PosterPick, orders: ReadonlyMap<string, readonly string[]>): boolean {
  for (const order of orders.values()) {
    if (order.includes(pick.clip)) {
      return true
    }
  }
  return false
}

/** Why Use as poster is off, or null when it can act. */
export type PosterBlock = { why: string }

export type PosterContext = {
  /** A save is in flight, or a move of marked clips is pending. */
  locked: boolean
  /** Another video holds the page (an open clip preview): the Timeline shows none. */
  held: boolean
  /** The video holds a decoded frame at the playhead. */
  frame: boolean
}

export const WHY_LOCKED = 'Wait for the save to finish.'
export const WHY_HELD = 'Close the clip preview to use the Timeline’s picture.'
export const WHY_NO_FRAME = 'The picture is still loading.'
export const WHY_IN_CARD = 'The playhead is in a title card. Move it onto a clip.'
export const WHY_NO_CLIP = 'The playhead is not on a clip.'

/**
 * The pick for the playhead at `ms` of the clip at `index` (the clip's own time, before cuts,
 * in whole milliseconds), or why not. A time inside a cut is allowed: `at` is before cuts.
 */
export function posterFromPlayhead(
  clips: readonly { identity: string; facts: { durationMs: number } }[],
  position: { clip: number; ms: number; card?: unknown },
  context: PosterContext,
): { pick: PosterPick } | PosterBlock {
  if (position.card != null) {
    return { why: WHY_IN_CARD }
  }
  const clip = clips[position.clip]
  if (clip === undefined || !Number.isFinite(position.ms) || position.ms < 0) {
    return { why: WHY_NO_CLIP }
  }
  if (context.locked) {
    return { why: WHY_LOCKED }
  }
  if (context.held) {
    return { why: WHY_HELD }
  }
  if (!context.frame) {
    return { why: WHY_NO_FRAME }
  }
  return { pick: { clip: clip.identity, at: Math.round(position.ms) / 1000 } }
}

/** The live-region words for a chosen frame. */
export function chosenWords(name: string, at: number): string {
  const total = Math.floor(at * 1000)
  const minutes = Math.floor(total / 60000)
  const seconds = ((total % 60000) / 1000).toFixed(3).padStart(6, '0')
  return `Poster set to ${name} at ${minutes}:${seconds}. Not saved.`
}

/** The first clip a render plays in the detail's chapters: on disk, not ignored or excluded. */
export function firstPlayed(event: EventDetail): EventDetail['chapters'][number]['clips'][number] | null {
  for (const chapter of event.chapters) {
    for (const clip of chapter.clips) {
      if ((clip.status === 'active' || clip.status === 'new') && clip.excluded !== true) {
        return clip
      }
    }
  }
  return null
}
