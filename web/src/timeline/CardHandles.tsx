import { memo, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { CSSProperties, KeyboardEvent, MouseEvent, PointerEvent } from 'react'

import { ClockTime } from '../ui/Clock'
import {
  cardCell,
  cardKey,
  cardTenthsAt,
  cardValueText,
  releasedWords,
  tenthsToSeconds,
} from './cardLength'
import type { Tenths } from './cardLength'
import { cardSubject, cardWidthMs, visibleHandles } from './cards'
import type { CardHandle } from './cards'
import type { DragStore } from './dragStore'
import { bareMousePress } from './handles'
import type { ShiftFrom } from './Track'
import { timeToPx } from './model'

/*
 * The card handles (D-20, `title-card-duration-drag`): one on the end edge of each title-card
 * block in the Edit-mode Timeline. A handle is a slider, built like a trim handle: it is moved
 * by the distance the pointer moves from where the edge was, snaps to whole seconds within
 * 8 px, and while it is dragged the length lives in the drag store (the Timeline lays the
 * blocks out from it); the draft is written once, on release, by `onSet`. A key press is its
 * own edit. It lies in the card lane, a row of its own above the clips, so its area never covers a trim
 * handle's: no press hand-over is needed.
 *
 * The handles are one layer after the playhead and before the clip handles, so Tab reaches
 * them in time order; only those in the track's window are drawn.
 */

/** A press this close to where it began (px) is a click, not a drag. */
const SLOP_PX = 3
export const CARD_KEYS =
  'Left and Down shorten the card by 0.1 s, Right and Up lengthen it, Shift makes it a whole second, Home is the shortest, End the longest.'

export function CardHandles({
  handles,
  pps,
  window,
  drag,
  shifting = null,
  locked,
  keysId,
  selected,
  onSelect,
  onSet,
}: {
  handles: readonly CardHandle[]
  pps: number
  window: { from: number; to: number }
  drag: DragStore
  /** A black card's drag in progress: the handles behind the card move. */
  shifting?: ShiftFrom | null
  locked: boolean
  keysId: string
  /** The selected card's chapter (saved name) or null. */
  selected: string | null
  onSelect: (chapter: string) => void
  onSet: (chapter: string, seconds: number, words: string | null) => void
}) {
  const range = visibleHandles(handles, (window.from / pps) * 1000, (window.to / pps) * 1000)
  const nodes = []
  if (range !== null) {
    for (let index = range[0]; index <= range[1]; index += 1) {
      const handle = handles[index]
      nodes.push(
        <CardHandleSlider
          key={handle.chapter}
          handle={handle}
          pps={pps}
          drag={drag}
          behind={shifting !== null && handle.startMs >= shifting.fromMs - 0.5}
          locked={locked}
          keysId={keysId}
          selected={selected === handle.chapter}
          onSelect={onSelect}
          onSet={onSet}
        />,
      )
    }
  }
  return <div className="tl-card-handles">{nodes}</div>
}

const CardHandleSlider = memo(function CardHandleSlider({
  handle,
  pps,
  drag,
  behind,
  locked,
  keysId,
  selected,
  onSelect,
  onSet,
}: {
  handle: CardHandle
  pps: number
  drag: DragStore
  /** Behind a black card being dragged: moved with it. */
  behind: boolean
  locked: boolean
  keysId: string
  selected: boolean
  onSelect: (chapter: string) => void
  onSet: (chapter: string, seconds: number, words: string | null) => void
}) {
  const { chapter, background, tenths, range: committed } = handle
  const el = useRef<HTMLDivElement>(null)
  const tip = useRef<HTMLSpanElement>(null)
  const active = useRef<{
    pointerId: number
    startX: number
    startMs: number
    startTenths: Tenths
    range: { min: Tenths; max: Tenths }
    moved: boolean
  } | null>(null)
  const ppsRef = useRef(pps)
  ppsRef.current = pps
  const pointerSeen = useRef(false)
  const [focused, setFocused] = useState(false)
  const subject = cardSubject(chapter)

  // The edge in the air, or null: only the dragged handle shows it.
  const live = useSyncExternalStore(drag.subscribe, () => {
    const d = drag.getCard()
    return d !== null && d.chapter === chapter ? d : null
  })
  const shown = live === null ? tenths : live.tenths
  const frozen = active.current?.range
  const rangeNow: { min: Tenths; max: Tenths } | null = !committed.adjustable
    ? null
    : (frozen ?? committed)
  const edgeMs = handle.startMs + cardWidthMs(handle, shown)
  const x = timeToPx(edgeMs, pps)

  const cancel = () => {
    const a = active.current
    active.current = null
    if (a === null || drag.owns(a)) {
      drag.setCard(null)
    }
    if (a !== null) {
      drag.unclaim(a)
      if (el.current?.hasPointerCapture(a.pointerId)) {
        el.current.releasePointerCapture(a.pointerId)
      }
    }
  }

  // The tip hangs centred on the edge; near an end of the track it slides back inside. The
  // sizes it needs (its width, the viewport's width and scroll) are read when the tip appears,
  // and again when a key moves the edge, never on each move of a drag: a read after the
  // commit forces a layout of everything that moved, a black card's drag included.
  const showTip = live !== null || focused
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
  }, [showTip, live === null ? x : 0])
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

  // A save that starts ends a drag in progress, as if Escape were pressed.
  useEffect(() => {
    if (locked) {
      cancel()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locked])
  // Gone from the window mid-drag: its own edge in the air goes with it, no one else's.
  useEffect(
    () => () => {
      const d = drag.getCard()
      if (d !== null && d.chapter === chapter) {
        drag.setCard(null)
      }
      if (active.current !== null) {
        drag.unclaim(active.current)
        active.current = null
      }
    },
    [drag, chapter],
  )

  const begin = (event: PointerEvent<HTMLElement>) => {
    const target = el.current
    if (target === null || !committed.adjustable) {
      return
    }
    const next = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startMs: cardWidthMs(handle, tenths),
      startTenths: tenths,
      range: { min: committed.min, max: committed.max },
      moved: false,
    }
    if (!drag.claim(next)) {
      return
    }
    target.setPointerCapture(event.pointerId)
    target.focus({ preventScroll: true })
    onSelect(chapter)
    active.current = next
  }

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
    const wanted = Math.max(0, a.startMs + (dx * 1000) / ppsRef.current)
    const placed = cardTenthsAt(wanted, ppsRef.current, a.range)
    drag.setCard({
      chapter,
      tenths: placed.tenths,
      snapped: placed.snapped,
      words: placed.snapped ? 'Whole second' : '',
    })
  }

  const release = (event: PointerEvent<HTMLElement>) => {
    const a = active.current
    if (a === null || a.pointerId !== event.pointerId) {
      return
    }
    const d = drag.getCard()
    const last = d !== null && d.chapter === chapter ? d : null
    cancel()
    if (a.moved && last !== null && last.tenths !== a.startTenths) {
      onSet(
        chapter,
        tenthsToSeconds(last.tenths),
        releasedWords(subject, last.tenths, a.startTenths, background),
      )
    }
  }

  const keyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape' && active.current !== null) {
      event.preventDefault()
      event.stopPropagation()
      cancel()
      return
    }
    if (event.ctrlKey || event.altKey || event.metaKey) {
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      // Selecting is an activation, never a side effect of focus alone (WCAG 3.2.1).
      event.preventDefault()
      onSelect(chapter)
      return
    }
    const wanted =
      rangeNow === null || active.current !== null
        ? null
        : cardKey(event.key, event.shiftKey, tenths, rangeNow)
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
      return
    }
    // A handle's key: never scrolls the page, whether or not it changes anything.
    event.preventDefault()
    if (locked || wanted === null || wanted === tenths) {
      return
    }
    onSet(chapter, tenthsToSeconds(wanted), null)
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

  const disabledReason = committed.adjustable ? null : committed.reason
  const reasonId = `${keysId}-r-${handle.index}`
  const longer = committed.adjustable && handle.clamped
  const reasonText =
    disabledReason ?? (longer ? 'Longer than the footage under it; it can only be made shorter.' : null)
  const lowest = rangeNow === null ? tenths : rangeNow.min
  const highest = rangeNow === null ? tenths : rangeNow.max
  const bareMouseDown = (event: MouseEvent<HTMLElement>) => {
    if (!bareMousePress(pointerSeen.current, event.button)) {
      return
    }
    event.preventDefault()
    if (!locked) {
      el.current?.focus({ preventScroll: true })
      onSelect(chapter)
    }
  }

  return (
    <div
      ref={el}
      className="tl-card-handle"
      role="slider"
      tabIndex={0}
      aria-label={`Title card length, ${subject}`}
      aria-orientation="horizontal"
      aria-valuemin={tenthsToSeconds(lowest)}
      aria-valuemax={tenthsToSeconds(highest)}
      aria-valuenow={tenthsToSeconds(shown)}
      aria-valuetext={cardValueText(shown)}
      aria-describedby={reasonText === null ? keysId : `${keysId} ${reasonId}`}
      aria-disabled={locked || disabledReason !== null || undefined}
      data-dragging={live !== null || undefined}
      data-snapped={(live !== null && live.snapped) || undefined}
      data-selected={selected || undefined}
      data-after={behind || undefined}
      style={{ '--x': `${x}px` } as CSSProperties}
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
        event.preventDefault()
        if (locked || disabledReason !== null) {
          return
        }
        begin(event)
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
        keepInView()
      }}
      onBlur={() => setFocused(false)}
    >
      <span className="tl-card-handle-bar" aria-hidden="true" />
      {reasonText !== null && (
        <span id={reasonId} className="visually-hidden">
          {reasonText}
        </span>
      )}
      {showTip && (
        <span
          className="tl-card-handle-tip"
          aria-hidden="true"
          ref={tip}
          style={{ '--tip-shift': `${tipShift}px` } as CSSProperties}
        >
          Card <ClockTime cell={cardCell(shown)} /> s
          {live !== null && live.words !== '' && (
            <span className="tl-card-snap-words">
              {' · '}
              {live.words}
            </span>
          )}
        </span>
      )}
      {live !== null && live.snapped && <span className="tl-card-snap-line" aria-hidden="true" />}
    </div>
  )
})

