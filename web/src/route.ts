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

const INDEX_KEY = 'autoReelIndex'
type NavigationGuard = (proceed: () => void) => boolean
let navigationGuard: NavigationGuard | null = null
// The shown route's hash, and its entry's place in history (kept in history.state).
let acceptedHash = window.location.hash
let acceptedIndex = entryIndex() ?? stampEntry(0)

function entryIndex(): number | undefined {
  const index: unknown = (window.history.state as Record<string, unknown> | null)?.[INDEX_KEY]
  return typeof index === 'number' ? index : undefined
}

function stampEntry(index: number): number {
  window.history.replaceState({ ...window.history.state, [INDEX_KEY]: index }, '')
  return index
}

/**
 * Ask `guard` before the route follows a hash change (Back, Forward, a link, a typed
 * address); `null` removes it. On false the move is undone and the page stays; the
 * guard's `proceed` redoes it.
 */
export function setNavigationGuard(guard: NavigationGuard | null): void {
  navigationGuard = guard
}

function sameRoute(a: Route, b: Route): boolean {
  return a.page === 'event' && b.page === 'event' ? a.eventId === b.eventId : a.page === b.page
}

/** The current route, updated on 'hashchange'. */
export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    // An undo lands back on the accepted hash: its own hashchange changes nothing.
    const update = () => {
      const hash = window.location.hash
      const index = entryIndex()
      if (hash !== acceptedHash && navigationGuard !== null) {
        // Back or Forward lands on an indexed entry; a link or typed address pushes a new one.
        const delta = index === undefined ? 0 : index - acceptedIndex
        const redo = () => (delta ? window.history.go(delta) : (window.location.hash = hash))
        if (!navigationGuard(redo)) {
          window.history.go(delta ? -delta : -1)
          return
        }
      }
      acceptedHash = hash
      acceptedIndex = index ?? stampEntry(acceptedIndex + 1)
      const next = parseRoute(hash)
      // An equal route keeps its object, so nothing remounts, scrolls or moves focus.
      setRoute((shown) => (sameRoute(shown, next) ? shown : next))
    }
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  return route
}
