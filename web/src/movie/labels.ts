import { VERDICT_LOOK } from '../events/tones'
import type { StatusLook } from '../events/tones'
import type { Tone } from '../ui/Pill'

/*
 * The movie section's words and looks (`MoviePanel.tsx`). Each map is a `Record`
 * over its closed vocabulary, so a member added or removed fails `tsc --noEmit`
 * until it has its words.
 */

/** How the movie relates to the event, from `staleness.stale`. */
export type MovieAge = 'current' | 'outdated'

export const MOVIE_AGE_LABEL: Record<MovieAge, string> = {
  current: 'Current',
  outdated: 'Outdated',
}

/** The render verdict's looks: the movie's age is that verdict, so the two pills match. */
export const MOVIE_AGE_LOOK: Record<MovieAge, StatusLook> = {
  current: VERDICT_LOOK.fresh,
  outdated: VERDICT_LOOK.stale,
}

/** Under an outdated movie; the render region above lists the reasons. */
export const OUTDATED_NOTE =
  'Rendered before the latest changes to this event. Render it again to bring the movie up to date.'

/**
 * Why the section cannot offer or play the movie. The first three answer the
 * one-byte probe and replace the player; the last four follow Play and sit
 * under it. A probe with no usable answer uses the page's own words instead
 * (`unansweredFailure`).
 */
export type MovieTrouble =
  | 'no_file'
  | 'unreadable'
  | 'empty'
  | 'no_picture'
  | 'cannot_play'
  | 'load_failed'
  | 'changed'

export const MOVIE_TROUBLE: Record<MovieTrouble, { title: string; tone: Tone }> = {
  no_file: { title: 'The service has no movie file for this event.', tone: 'warn' },
  unreadable: { title: 'The movie could not be read.', tone: 'err' },
  empty: { title: 'The movie file is empty.', tone: 'err' },
  no_picture: {
    title: "This browser cannot show this movie's picture. It plays the sound only.",
    tone: 'warn',
  },
  cannot_play: { title: 'This browser could not play the movie.', tone: 'err' },
  // MediaError 2: the loading broke off, which is not the browser's doing
  load_failed: { title: 'The movie could not be loaded.', tone: 'err' },
  changed: { title: 'The movie file changed while it played.', tone: 'info' },
}

/** The detail under `no_picture`, and under `changed`. */
export const NO_PICTURE_DETAIL = 'Download it to watch it in another player.'
export const CHANGED_DETAIL = 'The file on disk is not the one that started playing.'

/** `MediaError.code`'s four values, in words. */
export type MediaErrorCode = 1 | 2 | 3 | 4

export const MEDIA_ERROR_WORDS: Record<MediaErrorCode, string> = {
  1: 'Loading was stopped',
  2: 'A network error interrupted loading',
  3: 'The movie could not be decoded',
  4: 'The browser does not support the file or its format',
}

/** A `MediaError` in words, then the browser's own message when it gave one. */
export function mediaErrorWords(code: number, message: string): string {
  const words =
    code === 1 || code === 2 || code === 3 || code === 4
      ? MEDIA_ERROR_WORDS[code]
      : `MediaError ${code}`
  return message.trim() === '' ? words : `${words}: ${message.trim()}`
}
