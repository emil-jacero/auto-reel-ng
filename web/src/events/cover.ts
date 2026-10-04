import type { EventPoster } from '../api/poster'
import { CHOSEN_WORDS, DEFAULT_WORDS } from '../edit/poster.ts'

/* The words around an event's cover image: pure, so `npm test` covers them. */

export const NO_POSTER = 'No poster'

/** A list row's cover: the alternative text names the event; the placeholder says there is none. */
export function rowCoverWords(name: string): { alt: string; none: string } {
  return { alt: `Poster of ${name}`, none: `No poster for ${name}` }
}

/** The page's cover: the alternative text also says whether the frame is the default or chosen. */
export function pageCoverWords(
  name: string,
  poster: Pick<EventPoster, 'source'> | null,
): { alt: string; none: string; caption: string } {
  const caption = poster === null ? NO_POSTER : poster.source === 'event' ? CHOSEN_WORDS : DEFAULT_WORDS
  return {
    alt:
      poster === null
        ? `Poster of ${name}`
        : `Poster of ${name}, ${poster.source === 'event' ? 'a chosen frame' : 'the default frame, the first clip'}`,
    none: `No poster for ${name}`,
    caption,
  }
}
