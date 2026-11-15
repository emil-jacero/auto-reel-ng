import './workspace.css'

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { TimelinePanesContext } from '../../timeline/panes'
import type { TimelinePanes } from '../../timeline/panes'

/*
 * Edit mode's workspace (`editor-workspace-layout`, design D1): the window's full height and
 * width, the app header hidden (`data-workspace` on <html>), a top bar and four panes: the clip
 * bin (left), the viewer (centre), the inspector (right) and the Timeline (bottom). Each pane
 * scrolls on its own; below 960 CSS px the panes stack in one column (viewer, Timeline,
 * inspector, bin) and the page scrolls. The Timeline puts its picture in the viewer and its cut
 * panel in the inspector (`TimelinePanesContext`): one tree, one state, one video.
 */

/** Stacked, the top bar sticks while it takes at most this share of the window's height… */
const TOP_MAX_SHARE = 0.4
/** …and the window is at least this tall (rem), as the stacked page's save bar (`placeBar`). */
const TOP_MIN_WINDOW_REM = 28

export function Workspace({
  top,
  bin,
  inspector,
  timeline,
  viewer,
}: {
  top: ReactNode
  bin: ReactNode
  /** The inspector's Event content; the Cut content is the Timeline's cut panel. */
  inspector: ReactNode
  timeline: ReactNode
  /** What the viewer shows while the Timeline has no picture there (reading, a failure, Prepare). */
  viewer: ReactNode
}) {
  const [viewerPane, setViewerPane] = useState<HTMLElement | null>(null)
  const [cutPane, setCutPane] = useState<HTMLElement | null>(null)
  const topRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = document.documentElement
    root.dataset.workspace = ''
    return () => {
      delete root.dataset.workspace
    }
  }, [])

  // The top bar's height as drawn (`--ws-top-measured` on <html>): where the panes stack, what
  // the page's scroll padding and the sticky headings clear. Stacked, the bar wraps and holds a
  // save's explanation in its flow; the bar without it taller than two fifths of the window, or
  // a window under 28rem tall, and it rests at the page's top instead of sticking (`data-rests`),
  // as the stacked page's save bar does. A sticking bar keeps to those two fifths: the
  // explanation gets the rest (`--ws-alert-max`) and scrolls within itself, so a save's answer
  // never makes the bar rest and leave the window. Notifications keep clear of the bar and of
  // the explanation's panel under it in the wide frame (`--ws-toast-top`).
  useLayoutEffect(() => {
    const top = topRef.current
    if (top === null) {
      return
    }
    const root = document.documentElement
    const measure = () => {
      const rem = parseFloat(getComputedStyle(root).fontSize)
      const stacked = window.matchMedia('(width < 960px)').matches
      const alert = top.querySelector<HTMLElement>('.save-bar-alert')
      // The explanation's share of the bar: none in the wide frame, where it is a panel.
      const margin =
        stacked && alert !== null ? parseFloat(getComputedStyle(alert).marginBlockStart) || 0 : 0
      const alertRoom = stacked && alert !== null ? alert.offsetHeight + margin : 0
      const bar = top.offsetHeight - alertRoom
      const share = root.clientHeight * TOP_MAX_SHARE
      const rests = stacked && (root.clientHeight < TOP_MIN_WINDOW_REM * rem || bar > share)
      const rested = top.hasAttribute('data-rests')
      top.toggleAttribute('data-rests', rests)
      if (stacked && !rests && alert !== null) {
        top.style.setProperty('--ws-alert-max', `${Math.max(share - bar - margin, 3 * rem)}px`)
      } else {
        top.style.removeProperty('--ws-alert-max')
      }
      root.style.setProperty('--ws-top-measured', `${rests ? 0 : top.offsetHeight}px`)
      const panel = !stacked && alert !== null ? alert.getBoundingClientRect().bottom : null
      const clear = panel === null ? top.offsetHeight : panel - top.getBoundingClientRect().top
      root.style.setProperty('--ws-toast-top', `${Math.ceil(clear)}px`)
      // A bar that starts to rest leaves the window with the page: its focused control (Save,
      // a save's answer) is brought back into view.
      const focused = document.activeElement
      if (rests && !rested && focused instanceof HTMLElement && top.contains(focused)) {
        focused.scrollIntoView({ block: 'nearest' })
      }
    }
    const observer = new ResizeObserver(measure)
    observer.observe(top)
    // The wide frame's panel takes no room in the bar: its coming, going and size are followed
    // on their own.
    let watched: HTMLElement | null = null
    const watch = () => {
      const alert = top.querySelector<HTMLElement>('.save-bar-alert')
      if (alert !== watched) {
        if (watched !== null) {
          observer.unobserve(watched)
        }
        if (alert !== null) {
          observer.observe(alert)
        }
        watched = alert
        measure()
      }
    }
    measure()
    watch()
    const mutations = new MutationObserver(watch)
    mutations.observe(top, { childList: true, subtree: true })
    window.addEventListener('resize', measure)
    return () => {
      window.removeEventListener('resize', measure)
      mutations.disconnect()
      observer.disconnect()
      top.style.removeProperty('--ws-alert-max')
      root.style.removeProperty('--ws-top-measured')
      root.style.removeProperty('--ws-toast-top')
    }
  }, [])

  const panes = useMemo<TimelinePanes>(
    () => ({ viewer: viewerPane, cut: cutPane, onCutSelected: () => undefined }),
    [viewerPane, cutPane],
  )

  return (
    <TimelinePanesContext value={panes}>
      <div className="ws">
        <div ref={topRef} className="ws-top">
          {top}
        </div>
        <section className="ws-pane ws-bin" aria-label="Clips" data-ws-scroll>
          {bin}
        </section>
        <section className="ws-pane ws-view" aria-label="Viewer">
          <div className="ws-view-empty">{viewer}</div>
          <div ref={setViewerPane} className="ws-view-slot" />
        </section>
        <section className="ws-pane ws-insp" aria-label="Inspector" data-ws-scroll>
          {inspector}
          <div ref={setCutPane} className="ws-cut-slot" />
        </section>
        <section className="ws-pane ws-tl" aria-label="Timeline" data-ws-scroll>
          {timeline}
        </section>
      </div>
    </TimelinePanesContext>
  )
}
