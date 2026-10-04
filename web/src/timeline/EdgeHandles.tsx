import { memo, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { CSSProperties, KeyboardEvent, MouseEvent, PointerEvent, RefObject } from 'react'

import type { DraftCut } from '../edit/draft'
import type { DragStore } from './dragStore'
import {
  edgeAnnouncement,
  edgeAt,
  edgeCutOf,
  edgeEdit,
  edgeKey,
  edgeKeyWords,
  edgeLimits,
  edgeName,
  edgeNotes,
  edgePlaces,
  edgeTip,
  edgeValueText,
  playedMs,
} from './edgeTrim'
import type { EdgeLimits, Side } from './edgeTrim'
import type { EditBinding } from './editing'
import { bareMousePress, nearestHandle } from './handles'
import type { ClipFacts, Extent, Ms } from './model'
import { extentMs, timeToPx } from './model'
import type { Playhead } from './playhead'

/*
 * The clip edge tools (`clip-edge-trim`, D-20): Trim In on the left edge of each clip block the
 * Edit-mode Timeline draws with its detail, Trim Out on its right edge. A tool is a slider
 * (`role="slider"`): its value is the edge's place in the clip, its keys move it a frame or a
 * second, and a pointer drags it by the distance it moves (`edgeAt`: snapping, joining, limits).
 * While it is dragged the edge lives in the drag store: the clip's block is drawn live by the
 * track and everything after it moves by the change of its width (`ShiftFrom`); the draft is
 * written once, on release (`onEdge`), with the one edit `edgeEdit` gives.
 *
 * A tool's pointer zone lies inside its own block (8 px fine, 24 px coarse, at most a third of
 * the block), so at a boundary the left clip's Trim Out and the right clip's Trim In lie side by
 * side. Where a zone and a cut handle's area overlap, the press goes to the nearer edge: the
 * track's press targets (`PressTargets`) hold both kinds.
 */

/** A press this close to where it began (px) is a click, not a drag. */
const SLOP_PX = 3
/** An edge tool's zone, inside the block, by pointer. */
const ZONE_FINE_PX = 8
const ZONE_COARSE_PX = 24
/** The press reach of the nearest-wins test (a cut handle's area is 24 px fine, 44 coarse). */
const REACH_FINE_PX = 24
const REACH_COARSE_PX = 44

export function coarsePointer(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches
}

/** What a press target (a cut handle or an edge tool) offers the track's one hit test. */
export type PressTarget = {
  el: HTMLElement
  /** Its edge, in px from the canvas's left. */
  px: () => number
  begin: (event: PointerEvent<HTMLElement>) => void
  choose: () => void
}

/** Every cut handle and edge tool the track draws, by id: one nearest-wins test across them. */
export type PressTargets = Map<string, PressTarget>

/**
 * Which target a press at `clientX` on target `id` belongs to: among the targets whose area holds
 * the press, the one whose edge is nearest (the earlier on a tie, `nearestHandle`); `id` itself
 * when none is nearer.
 */
export function pressWinner(targets: PressTargets, clientX: number, id: string): string {
  const own = targets.get(id)
  const canvas = own?.el.closest('.tl-canvas')?.getBoundingClientRect()
  if (own === undefined || canvas === undefined) {
    return id
  }
  const contenders: { id: string; px: number }[] = []
  for (const [key, target] of targets) {
    const area = target.el.getBoundingClientRect()
    if (clientX >= area.left && clientX <= area.right) {
      contenders.push({ id: key, px: target.px() })
    }
  }
  const reach = coarsePointer() ? REACH_COARSE_PX : REACH_FINE_PX
  return nearestHandle(clientX - canvas.left, contenders, reach) ?? id
}

export const edgeTargetId = (identity: string, side: Side) => `${identity}|edge:${side}`

/** The snapping switch of the edge drags (`S`), held by the Timeline for the page visit. */
export type SnapSwitch = { current: boolean }

export const EdgeTool = memo(function EdgeTool({
  identity,
  name,
  clipIndex,
  side,
  facts,
  kept,
  listed,
  blockLeft,
  widthPx,
  pps,
  after,
  playhead,
  drag,
  locked,
  keysId,
  lockedId,
  selectedKey,
  targets,
  snapping,
  onSelect,
  onEdge,
  onFocusChange,
  fallbackRef,
}: {
  identity: string
  name: string
  /** The clip's place among the shown clips: the playhead's `clip`. */
  clipIndex: number
  side: Side
  facts: ClipFacts
  /** The clip's kept extent as committed. */
  kept: Extent
  listed: readonly DraftCut[]
  /** The block's left edge on the canvas and its width, in px. */
  blockLeft: number
  widthPx: number
  pps: number
  /** Behind a dragged card or clip edge: moved with it (`data-after`). */
  after: boolean
  playhead: Playhead
  drag: DragStore
  locked: boolean
  keysId: string
  /** The words that say the tools are unavailable (`locked`). */
  lockedId: string
  /** The selected cut's key, when it is this clip's. */
  selectedKey: string | null
  targets: PressTargets
  snapping: SnapSwitch
  onSelect: (identity: string, key: string) => void
  onEdge: EditBinding['onEdge']
  /** Focus arrived on this tool (its clip) or left it (null). */
  onFocusChange: (identity: string | null) => void
  fallbackRef: RefObject<HTMLElement | null>
}) {
  const id = edgeTargetId(identity, side)
  const el = useRef<HTMLDivElement>(null)
  const tip = useRef<HTMLSpanElement>(null)
  const active = useRef<{
    pointerId: number
    startX: number
    startPlace: Ms
    limits: EdgeLimits
    moved: boolean
  } | null>(null)
  const ppsRef = useRef(pps)
  ppsRef.current = pps
  const pointerSeen = useRef(false)
  const [focused, setFocused] = useState(false)

  // This clip's edge in the air (either side: the block's right edge follows a Trim In too).
  const live = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.getEdge()
    return d !== null && d.identity === identity ? d : null
  })
  const own = live !== null && live.side === side ? live : null
  const d = facts.durationMs
  const limits = edgeLimits(listed, side, facts)
  const places = edgePlaces(listed, d)
  const place = own === null ? places[side] : own.place
  const plays = own === null ? playedMs(listed, d) : own.playsMs
  const width = live === null ? widthPx : timeToPx(extentMs(live.extent), pps)
  const zone = Math.max(1, Math.min(coarsePointer() ? ZONE_COARSE_PX : ZONE_FINE_PX, width / 3))
  // The edge on the canvas: a Trim In stays at the block's left (the block keeps its left side).
  const x = side === 'start' ? blockLeft : blockLeft + width
  const edgeCut = edgeCutOf(listed, side, d)

  const cancel = () => {
    const a = active.current
    active.current = null
    if (a === null || drag.owns(a)) {
      const now = drag.getEdge()
      if (now !== null && now.identity === identity && now.side === side) {
        drag.setEdge(null)
      }
    }
    if (a !== null) {
      drag.unclaim(a)
      if (el.current?.hasPointerCapture(a.pointerId)) {
        el.current.releasePointerCapture(a.pointerId)
      }
    }
  }

  // A save that starts ends a drag in progress, as if Escape were pressed.
  useEffect(() => {
    if (locked) {
      cancel()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locked])
  // Gone from the window mid-drag: its own edge in the air goes with it.
  useEffect(
    () => () => {
      const now = drag.getEdge()
      if (now !== null && now.identity === identity && now.side === side) {
        drag.setEdge(null)
      }
      if (active.current !== null) {
        drag.unclaim(active.current)
        active.current = null
      }
    },
    [drag, identity, side],
  )
  // A tool that goes away while it holds focus hands focus to the playhead's grip (WCAG 2.4.3).
  useLayoutEffect(() => {
    const node = el.current
    return () => {
      if (node === null || node !== document.activeElement) {
        return
      }
      queueMicrotask(() => {
        const grip = fallbackRef.current
        const lost = document.activeElement === null || document.activeElement === document.body
        if (lost && grip !== null && grip.isConnected) {
          grip.focus({ preventScroll: true })
        }
      })
    }
  }, [fallbackRef])

  // The tip hangs over the edge; near an end of the view it slides back inside. Measured when it
  // appears (and when a key moves the edge), never on each move of a drag.
  const showTip = own !== null || focused
  const room = useRef<{ tip: number; view: number; scroll: number } | null>(null)
  const [, measured] = useState(0)
  useLayoutEffect(() => {
    const box = tip.current
    const view = box?.closest<HTMLElement>('.tl-viewport')
    if (!box || !view) {
      room.current = null
      return
    }
    room.current = { tip: box.offsetWidth, view: view.clientWidth, scroll: view.scrollLeft }
    measured((n) => n + 1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showTip, own === null ? x : 0])
  const tipShift = (() => {
    const r = room.current
    if (r === null) {
      return 0
    }
    const centre = x - r.scroll
    const lo = centre - r.tip / 2
    const hi = centre + r.tip / 2
    return Math.round(lo < 0 ? -lo : hi > r.view ? r.view - hi : 0)
  })()

  const playheadMs = (): Ms | null => {
    const p = playhead.get()
    return p.card == null && p.clip === clipIndex ? p.ms : null
  }

  const selectEdgeCut = () => {
    if (edgeCut !== null) {
      onSelect(identity, edgeCut.cut.key)
    }
  }

  // A key or a release that gives the focused edge its edge cut (or another one) selects it too.
  const edgeKeyNow = edgeCut?.cut.key ?? null
  useEffect(() => {
    if (edgeKeyNow !== null && el.current !== null && el.current === document.activeElement) {
      onSelect(identity, edgeKeyNow)
    }
  }, [edgeKeyNow, identity, onSelect])

  const begin = (event: PointerEvent<HTMLElement>) => {
    const target = el.current
    if (target === null || locked) {
      return
    }
    const next = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startPlace: places[side],
      limits: edgeLimits(listed, side, facts),
      moved: false,
    }
    // One drag at a time: a second finger is refused, not mixed in.
    if (!drag.claim(next)) {
      return
    }
    target.setPointerCapture(event.pointerId)
    target.focus({ preventScroll: true })
    selectEdgeCut()
    active.current = next
  }
  const choose = () => {
    el.current?.focus({ preventScroll: true })
    selectEdgeCut()
  }
  useEffect(() => {
    targets.set(id, { el: el.current as HTMLElement, px: () => x, begin, choose })
    return () => {
      targets.delete(id)
    }
  })

  const move = (event: PointerEvent<HTMLElement>) => {
    const a = active.current
    if (a === null || a.pointerId !== event.pointerId) {
      return
    }
    const dx = event.clientX - a.startX
    if (!a.moved && Math.abs(dx) < SLOP_PX) {
      return
    }
    a.moved = true
    const wanted = a.startPlace + Math.round((dx * 1000) / ppsRef.current)
    const at = edgeAt(
      listed,
      side,
      wanted,
      facts,
      ppsRef.current,
      { playheadMs: playheadMs(), snapping: snapping.current && !event.altKey },
      a.limits,
    )
    drag.setEdge({
      identity,
      side,
      x: at.x,
      place: at.place,
      snappedTo: at.snappedTo,
      joined: at.joined,
      changeMs: at.changeMs,
      playsMs: at.playsMs,
      extent: at.extent,
      limit: at.limit,
      deltaMs: extentMs(at.extent) - extentMs(kept),
      cuts: at.cuts,
      tip: edgeTip(at),
      notes: edgeNotes(side, at, a.limits.holdingCut),
    })
  }

  const release = (event: PointerEvent<HTMLElement>) => {
    const a = active.current
    if (a === null || a.pointerId !== event.pointerId) {
      return
    }
    const now = drag.getEdge()
    const last = now !== null && now.identity === identity && now.side === side ? now : null
    cancel()
    if (!a.moved || last === null) {
      return
    }
    const edit = edgeEdit(listed, side, last.x, facts)
    if (edit.kind !== 'none') {
      onEdge(identity, edit, edgeAnnouncement(name, side, last, d))
    }
  }

  const keyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape' && active.current !== null) {
      event.preventDefault()
      event.stopPropagation()
      cancel()
      return
    }
    if (event.ctrlKey || event.altKey || event.metaKey || active.current !== null) {
      return
    }
    const wanted = edgeKey(event.key, event.shiftKey, listed, side, facts, limits)
    if (wanted === null) {
      return
    }
    // An edge's key: never scrolls the page, whether or not it changes anything.
    event.preventDefault()
    if (locked) {
      return
    }
    const at = edgeAt(listed, side, wanted, facts, pps, { playheadMs: null, snapping: false }, limits)
    const edit = edgeEdit(listed, side, at.x, facts)
    if (edit.kind === 'none') {
      return
    }
    onEdge(identity, edit, edgeKeyWords(side, at, limits.holdingCut))
  }

  const keepInView = () => {
    const viewport = el.current?.closest<HTMLElement>('.tl-viewport')
    if (viewport === null || viewport === undefined) {
      return
    }
    if (x < viewport.scrollLeft || x > viewport.scrollLeft + viewport.clientWidth) {
      viewport.scrollLeft = Math.max(0, x - viewport.clientWidth / 2)
    }
  }

  const bareMouseDown = (event: MouseEvent<HTMLElement>) => {
    if (!bareMousePress(pointerSeen.current, event.button)) {
      return
    }
    event.preventDefault()
    if (!locked) {
      targets.get(pressWinner(targets, event.clientX, id))?.choose()
    }
  }

  const fileLimit = own !== null && own.limit === 'file'
  return (
    <div
      ref={el}
      className="tl-edge"
      role="slider"
      tabIndex={0}
      aria-label={edgeName(side, name)}
      aria-orientation="horizontal"
      aria-valuemin={limits.lowest / 1000}
      aria-valuemax={Math.max(limits.highest, place) / 1000}
      aria-valuenow={place / 1000}
      aria-valuetext={edgeValueText(side, place, d, plays)}
      aria-describedby={locked ? `${keysId} ${lockedId}` : keysId}
      aria-disabled={locked || undefined}
      data-side={side}
      data-identity={identity}
      data-dragging={own !== null || undefined}
      data-limit={own?.limit ?? undefined}
      data-snapped={(own !== null && own.snappedTo !== null) || undefined}
      data-selected={(edgeCut !== null && selectedKey === edgeCut.cut.key) || undefined}
      data-after={after || undefined}
      style={{ '--x': `${x}px`, '--zone': `${zone}px` } as CSSProperties}
      onPointerDownCapture={() => {
        pointerSeen.current = true
      }}
      onPointerUpCapture={() => {
        pointerSeen.current = false
      }}
      onPointerCancelCapture={() => {
        pointerSeen.current = false
      }}
      onMouseDown={bareMouseDown}
      onPointerDown={(event) => {
        if (event.button !== 0 && event.pointerType === 'mouse') {
          return
        }
        // A press on an edge is the edge's: no text selection, no native drag, no scrub.
        event.preventDefault()
        if (locked) {
          return
        }
        targets.get(pressWinner(targets, event.clientX, id))?.begin(event)
      }}
      onPointerMove={move}
      onPointerUp={release}
      onPointerCancel={cancel}
      onLostPointerCapture={() => {
        if (active.current !== null) {
          cancel()
        }
      }}
      onKeyDown={keyDown}
      onFocus={(event) => {
        setFocused(event.currentTarget.matches(':focus-visible'))
        onFocusChange(identity)
        selectEdgeCut()
        keepInView()
      }}
      onBlur={() => {
        setFocused(false)
        onFocusChange(null)
      }}
    >
      <span className="tl-edge-bracket" aria-hidden="true" />
      {own !== null && own.snappedTo !== null && <span className="tl-edge-snap-line" aria-hidden="true" />}
      {showTip && (
        <span
          className="tl-edge-tip"
          aria-hidden="true"
          ref={tip}
          style={{ '--tip-shift': `${tipShift}px` } as CSSProperties}
        >
          <span className="tl-edge-tip-time">
            {own === null ? edgeValueText(side, place, d, plays) : own.tip}
          </span>
          {own !== null &&
            own.notes.map((note) => (
              <span key={note} className="tl-edge-note" data-file={(fileLimit && note.endsWith('of the file')) || undefined}>
                {note}
              </span>
            ))}
        </span>
      )}
    </div>
  )
})
