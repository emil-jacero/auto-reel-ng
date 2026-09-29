import { useEffect, useState } from 'react'

/**
 * The client's pages, addressed by the URL hash — no router library (D-8).
 *
 * A hash route needs no server configuration and gives Back, Forward, reload
 * and bookmarks for free. An event id keeps its `/` separators; every segment
 * is `encodeURIComponent`'d, so spaces, `,`, `&`, `#`, `?`, `%` and non-ASCII
 * letters round-trip.
 */

export type Route = { page: 'list' } | { page: 'event'; eventId: string }

const EVENT_PREFIX = '#/event/'

/** Encode an event id per segment, keeping `/` as the separator. */
export function encodeEventId(eventId: string): string {
  return eventId.split('/').map(encodeURIComponent).join('/')
}

/** '#/event/<id segments, each encodeURIComponent'd>' -> event; anything else -> list. */
export function parseRoute(hash: string): Route {
  if (!hash.startsWith(EVENT_PREFIX)) {
    return { page: 'list' }
  }
  const encoded = hash.slice(EVENT_PREFIX.length)
  if (encoded === '') {
    return { page: 'list' }
  }
  try {
    return { page: 'event', eventId: encoded.split('/').map(decodeURIComponent).join('/') }
  } catch (error) {
    if (error instanceof URIError) {
      return { page: 'list' }
    }
    throw error
  }
}

/** The href for an event page; '/' separators kept, every segment encoded. */
export function eventHref(eventId: string): string {
  return EVENT_PREFIX + encodeEventId(eventId)
}

/** The href for the list. */
export const LIST_HREF = '#/'

/** The current route, updated on 'hashchange'. */
export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const update = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  return route
}
