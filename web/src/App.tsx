import './app.css'

import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import { EventDetail } from './events/EventDetail'
import { EventList } from './events/EventList'
import { useRoute } from './route'

/**
 * The route switch. The list mounts the first time it is shown and then stays
 * mounted, hidden while an event page is open, so returning to it keeps its
 * filter and scroll and makes no new request. An event page mounts per event,
 * so a deep link to one never scans the whole library.
 */
export function App() {
  const route = useRoute()
  const onList = route.page === 'list'
  const [listMounted, setListMounted] = useState(onList)
  if (onList && !listMounted) {
    setListMounted(true)
  }
  const listScroll = useRef(0)

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
  }, [onList, route])

  return (
    <>
      {listMounted && <EventList hidden={!onList} />}
      {route.page === 'event' && <EventDetail key={route.eventId} eventId={route.eventId} />}
    </>
  )
}
