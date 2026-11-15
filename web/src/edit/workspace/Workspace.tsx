import './workspace.css'

import { useEffect, useMemo, useState } from 'react'
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

  useEffect(() => {
    const root = document.documentElement
    root.dataset.workspace = ''
    return () => {
      delete root.dataset.workspace
    }
  }, [])

  const panes = useMemo<TimelinePanes>(
    () => ({ viewer: viewerPane, cut: cutPane, onCutSelected: () => undefined }),
    [viewerPane, cutPane],
  )

  return (
    <TimelinePanesContext value={panes}>
      <div className="ws">
        <div className="ws-top">{top}</div>
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
