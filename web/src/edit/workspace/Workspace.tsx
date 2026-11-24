import './workspace.css'

import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { TimelinePanesContext } from '../../timeline/panes'
import type { TimelinePanes } from '../../timeline/panes'
import { Inspector } from './Inspector.tsx'
import { useModalityTracking } from './modality.ts'
import type { InspectorTab } from './inspectorTabs.ts'
import { PaneSeparator } from './PaneSeparator.tsx'
import {
  PANES,
  commitPanes,
  effectiveSizes,
  limits,
  sameFrame,
} from './paneSizes.ts'
import type { Frame, PaneAction, PaneId, PaneProperty } from './paneSizes.ts'
import {
  isStacked,
  panePrefs,
  registerPaneShower,
  setPanePrefs,
  usePanePrefs,
  useStacked,
} from './paneSizesPref.ts'

/*
 * Edit mode's workspace (`editor-workspace-layout`, design D1): the window's full height and
 * width, the app header hidden (`data-workspace` on <html>), a top bar and four panes: the clip
 * bin (left), the viewer (centre), the inspector (right) and the Timeline (bottom). Each pane
 * scrolls on its own; below 960 CSS px the panes stack in one column (viewer, Timeline,
 * inspector, bin) and the page scrolls. The Timeline puts its picture in the viewer, its
 * track-only part of the Clip tab in the editor's Clip tab and its suggestion panel in the
 * Suggestion tab (`TimelinePanesContext`): one tree, one state, one video. The inspector
 * (`Inspector.tsx`) follows the page's selection without moving focus.
 *
 * Wide, the three pane borders are separators (`PaneSeparator.tsx`): dragged, or moved by keys,
 * they size the bin, the inspector and the Timeline (`resizable-panes`); a pane dragged past half
 * its least size hides, its border staying at the window's edge to bring it back. The sizes and
 * the hidden panes are kept in the browser (`paneSizesPref.ts`) over today's default rules and
 * fitted to the window (`paneSizes.ts`). The drawn sizes are custom properties on <html>, written
 * imperatively (`applyPane`) so a drag renders nothing; a hidden pane stays mounted, `inert` and
 * out of sight (`data-hidden`), so the Timeline keeps playing and the inspector keeps its portals.
 */

const PROPERTY: Record<PaneId, PaneProperty> = {
  bin: '--ws-bin-w',
  insp: '--ws-insp-w',
  tl: '--ws-tl-h',
}

const NAMES: Record<PaneId, string> = {
  bin: 'Resize the clip bin',
  insp: 'Resize the inspector',
  tl: 'Resize the Timeline',
}

/** The window's numbers `paneSizes.ts` lays out by; the top bar's height is measured by the caller. */
function readFrame(top: number): Frame {
  const root = document.documentElement
  return {
    width: root.clientWidth,
    height: root.clientHeight,
    rem: parseFloat(getComputedStyle(root).fontSize) || 16,
    top,
  }
}

/** Stacked, the top bar sticks while it takes at most this share of the window's height… */
const TOP_MAX_SHARE = 0.4
/** …and the window is at least this tall (rem), as the stacked page's save bar (`placeBar`). */
const TOP_MIN_WINDOW_REM = 28

export function Workspace({
  top,
  player,
  bin,
  info,
  event,
  clip,
  clipSlot,
  timeline,
  viewer,
  tab,
  onTab,
}: {
  top: ReactNode
  /** The bin's player (`BinPlayer`): above the bin's scroll box, so it never scrolls away. */
  player: ReactNode
  bin: ReactNode
  /** The bin's information (`ClipInfo`): under the bin's scroll box, capped at 30 % of the bin's height. */
  info: ReactNode
  /** The inspector's Event tab. */
  event: ReactNode
  /**
   * The inspector's Clip tab, built by the editor (`ClipInspector`, `ClipGroupTab`); null while no
   * clip is selected, which shows the tab's hint.
   */
  clip: ReactNode
  /** The node the Clip tab holds for the Timeline's track-only part (`ClipInspector`'s slot), or null. */
  clipSlot: HTMLElement | null
  timeline: ReactNode
  /** What the viewer shows while the Timeline has no picture there (reading, a failure, Prepare). */
  viewer: ReactNode
  /**
   * The inspector's shown tab, held by the editor (`useInspectorTab`): what needs the operator's
   * eye in the Event tab (a save's refusal at the Details fields) shows that tab first.
   */
  tab: InspectorTab
  onTab: (tab: InspectorTab) => void
}) {
  const [viewerPane, setViewerPane] = useState<HTMLElement | null>(null)
  const [suggestionPane, setSuggestionPane] = useState<HTMLElement | null>(null)
  const [cardPane, setCardPane] = useState<HTMLElement | null>(null)
  const topRef = useRef<HTMLDivElement>(null)
  const binRef = useRef<HTMLElement>(null)
  const inspRef = useRef<HTMLElement>(null)
  const tlRef = useRef<HTMLElement>(null)
  const ids = { bin: useId(), insp: useId(), tl: useId() }
  const prefs = usePanePrefs()
  const stacked = useStacked()
  const [frame, setFrame] = useState<Frame>(() => readFrame(0))
  const frameRef = useRef(frame)
  const measureRef = useRef<(() => void) | null>(null)
  // The pane a border is dragging now: the apply effect leaves it to the live writes.
  const draggingRef = useRef<PaneId | null>(null)
  // The last input (Tab or a pointer press) for Space on a focused control (`editor-shortcuts`).
  useModalityTracking()

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
  // never makes the bar rest and leave the window. Wide, the explanation is a panel under the
  // bar that ends above the Timeline (`--ws-alert-max` as well). Notifications keep clear of the
  // bar and of the explanation's panel under it in the wide frame (`--ws-toast-top`).
  useLayoutEffect(() => {
    const top = topRef.current
    if (top === null) {
      return
    }
    const root = document.documentElement
    const measure = () => {
      const rem = parseFloat(getComputedStyle(root).fontSize)
      const stacked = isStacked()
      // The frame the panes are laid out by: state only when its four numbers changed, so a drag
      // of the Timeline's border (which changes none of them) renders nothing (design D3).
      const next = readFrame(top.offsetHeight)
      if (!sameFrame(frameRef.current, next)) {
        frameRef.current = next
        setFrame(next)
      }
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
      // Wide, the panel is capped at the Timeline's top (and at two fifths of the window), the
      // same gap above the Timeline as under the bar: in a short window it scrolls in what is
      // left above the Timeline rather than covering it.
      const timeline =
        !stacked && alert !== null ? top.parentElement?.querySelector('.ws-tl') : null
      if (stacked && !rests && alert !== null) {
        top.style.setProperty('--ws-alert-max', `${Math.max(share - bar - margin, 3 * rem)}px`)
      } else if (alert !== null && timeline instanceof HTMLElement) {
        const panelTop = alert.getBoundingClientRect().top
        const gap = Math.max(panelTop - top.getBoundingClientRect().bottom, 0)
        const room = timeline.getBoundingClientRect().top - gap - panelTop
        const most = Math.max(Math.min(root.clientHeight * TOP_MAX_SHARE, room), 0)
        top.style.setProperty('--ws-alert-max', `${Math.floor(most)}px`)
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
    measureRef.current = measure
    const observer = new ResizeObserver(measure)
    observer.observe(top)
    // The explanation's cap ends above the Timeline: its height changes follow too (design D7).
    const timelineSection = top.parentElement?.querySelector('.ws-tl')
    if (timelineSection instanceof HTMLElement) {
      observer.observe(timelineSection)
    }
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
      measureRef.current = null
      mutations.disconnect()
      observer.disconnect()
      top.style.removeProperty('--ws-alert-max')
      root.style.removeProperty('--ws-top-measured')
      root.style.removeProperty('--ws-toast-top')
    }
  }, [])

  const drawn = useMemo(() => effectiveSizes(prefs, frame), [prefs, frame])
  const drawnRef = useRef(drawn)
  drawnRef.current = drawn

  // What a pane's size decides, together: its track, and `data-hidden` and `inert` on its section
  // when it is 0 (focus inside it is blurred to the page first, where the workspace's keys act).
  // React owns neither, so a render never undoes a live drag write (design D3).
  // A live (mid-drag) write is transient: it only sizes the pane to 0 and marks it
  // `data-collapsing`, which the CSS lays out like a hidden pane but never makes `visibility:
  // hidden` (a focused element that stops being visible is blurred by the browser, which would
  // fire the `blur` commit of a half-typed trim or cut field). Blur, `inert` and `data-hidden`
  // wait for the commit.
  const applyPane = useCallback((pane: PaneId, px: number, transient = false) => {
    document.documentElement.style.setProperty(PROPERTY[pane], `${px}px`)
    const section = { bin: binRef, insp: inspRef, tl: tlRef }[pane].current
    if (section !== null) {
      if (px === 0 && transient) {
        section.setAttribute('data-collapsing', '')
      } else if (px === 0) {
        const focused = document.activeElement
        if (focused instanceof HTMLElement && section.contains(focused)) {
          focused.blur()
        }
        section.inert = true
        section.removeAttribute('data-collapsing')
        section.setAttribute('data-hidden', '')
      } else {
        section.removeAttribute('data-collapsing')
        section.removeAttribute('data-hidden')
        section.inert = false
      }
    }
    if (pane === 'tl') {
      measureRef.current?.()
    }
  }, [])

  const clearPanes = useCallback(() => {
    for (const pane of PANES) {
      document.documentElement.style.removeProperty(PROPERTY[pane])
      const section = { bin: binRef, insp: inspRef, tl: tlRef }[pane].current
      section?.removeAttribute('data-hidden')
      section?.removeAttribute('data-collapsing')
      if (section !== null && section !== undefined) {
        section.inert = false
      }
    }
  }, [])

  // The drawn sizes, wide; stacked there are none. Primitive dependencies only, and the dragged
  // pane is skipped, so a re-run from another cause never writes over a live drag.
  useLayoutEffect(() => {
    if (stacked) {
      clearPanes()
      return
    }
    for (const pane of PANES) {
      if (draggingRef.current !== pane) {
        applyPane(pane, drawn[pane])
      }
    }
  }, [drawn.bin, drawn.insp, drawn.tl, stacked, applyPane, clearPanes]) // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => clearPanes, [clearPanes])

  // A commit stores what `commitPanes` says and applies the committed pane itself: the effect
  // above would not re-run when the size equals the one drawn before the drag (design D3).
  const commit = useCallback(
    (pane: PaneId, action: PaneAction) => {
      const next = commitPanes(pane, action, panePrefs(), drawnRef.current, frameRef.current)
      setPanePrefs(next)
      draggingRef.current = null
      applyPane(pane, effectiveSizes(next, frameRef.current)[pane])
    },
    [applyPane],
  )
  const live = useCallback(
    (pane: PaneId, px: number) => {
      draggingRef.current = pane
      applyPane(pane, px, true)
    },
    [applyPane],
  )
  const cancel = useCallback(
    (pane: PaneId) => {
      draggingRef.current = null
      applyPane(pane, drawnRef.current[pane])
    },
    [applyPane],
  )

  // Showing a hidden pane from outside (a save refused at an inspector field), by the same path.
  useLayoutEffect(
    () =>
      registerPaneShower((pane) => {
        const kept = panePrefs()
        if (isStacked() || !kept.hidden.includes(pane)) {
          return
        }
        commit(pane, { kind: 'show' })
      }),
    [commit],
  )

  const lim = {
    bin: limits('bin', drawn, frame),
    insp: limits('insp', drawn, frame),
    tl: limits('tl', drawn, frame),
  }
  const separator = (pane: PaneId) => (
    <PaneSeparator
      pane={pane}
      controls={ids[pane]}
      label={NAMES[pane]}
      size={drawn[pane]}
      limits={lim[pane]}
      onLive={(px) => live(pane, px)}
      onCommit={(action) => commit(pane, action)}
      onCancel={() => cancel(pane)}
    />
  )

  const panes = useMemo<TimelinePanes>(
    () => ({ viewer: viewerPane, clip: clipSlot, suggestion: suggestionPane, card: cardPane }),
    [viewerPane, clipSlot, suggestionPane, cardPane],
  )

  return (
    <TimelinePanesContext value={panes}>
      <div className="ws">
        <div ref={topRef} className="ws-top">
          {top}
        </div>
        <section ref={binRef} id={ids.bin} className="ws-binbox" aria-label="Clips">
          {player}
          <div className="ws-pane ws-bin" data-ws-scroll>
            {bin}
          </div>
          {info}
        </section>
        {separator('bin')}
        <section className="ws-pane ws-view" aria-label="Viewer">
          <div className="ws-view-empty">{viewer}</div>
          <div ref={setViewerPane} className="ws-view-slot" />
        </section>
        {separator('insp')}
        <section
          ref={inspRef}
          id={ids.insp}
          className="ws-pane ws-insp"
          aria-label="Inspector"
          data-ws-scroll
        >
          <Inspector
            tab={tab}
            onTab={onTab}
            event={event}
            clip={clip}
            suggestionSlot={setSuggestionPane}
            cardSlot={setCardPane}
          />
        </section>
        {separator('tl')}
        <section
          ref={tlRef}
          id={ids.tl}
          className="ws-pane ws-tl"
          aria-label="Timeline"
          data-ws-scroll
        >
          {timeline}
        </section>
      </div>
    </TimelinePanesContext>
  )
}
