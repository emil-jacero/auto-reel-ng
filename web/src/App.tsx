import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import { EventDetail } from './events/EventDetail'
import { EventList } from './events/EventList'
import { useRoute } from './route'
import type { Route } from './route'
import { AppShell, focusPageHeading } from './shell/AppShell'

/** Whether two routes show the same page: a new but equal route object is no move. */
function samePage(a: Route, b: Route): boolean {
  if (a.page === 'event' && b.page === 'event') {
    return a.eventId === b.eventId
  }
  return a.page === b.page
}

/**
 * The route switch, inside the app shell. The list mounts the first time it is
 * shown and then stays mounted, hidden while an event page is open, so
 * returning to it keeps its filter and scroll and makes no new request. An
 * event page mounts per event, so a deep link to one never scans the whole
 * library. After every move between pages, focus goes to the new page's heading.
 */
export function App() {
  const route = useRoute()
  const onList = route.page === 'list'
  const [listMounted, setListMounted] = useState(onList)
  if (onList && !listMounted) {
    setListMounted(true)
  }
  const listScroll = useRef(0)
  // The page shown last. Compared by value, not by a "first run" flag: StrictMode
  // runs the mount effect twice, and a fresh load must leave focus alone so the
  // first Tab reaches the skip control.
  const shownRoute = useRef(route)

  useEffect(() => {
    // The browser's own restore would race the re-render; App restores instead.
    window.history.scrollRestoration = 'manual'
  }, [])

  // Track the list's scroll while it is shown. A layout effect, so the listener
  // is gone before the shorter event page can clamp the position and fire one.
  useLayoutEffect(() => {
    if (!onList) {
      return
    }
    const save = () => {
      listScroll.current = window.scrollY
    }
    window.addEventListener('scroll', save, { passive: true })
    return () => window.removeEventListener('scroll', save)
  }, [onList])

  useLayoutEffect(() => {
    if (onList) {
      document.title = 'Events — auto-reel'
      window.scrollTo(0, listScroll.current)
    } else {
      window.scrollTo(0, 0)
    }
    // After the scroll restore, and without scrolling, so the two never fight.
    if (!samePage(route, shownRoute.current)) {
      shownRoute.current = route
      focusPageHeading({ preventScroll: true })
    }
  }, [onList, route])

  return (
    <AppShell route={route}>
      {listMounted && <EventList hidden={!onList} />}
      {route.page === 'event' && <EventDetail key={route.eventId} eventId={route.eventId} />}
    </AppShell>
  )
}
