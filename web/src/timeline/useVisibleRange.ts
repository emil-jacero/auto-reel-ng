import { useCallback, useLayoutEffect, useState } from 'react'
import type { RefObject } from 'react'

/** What the track's scroller shows: how far it is scrolled and how wide it is, in px. */
export type VisibleRange = { left: number; width: number }

/**
 * The scroller's range, kept in state and updated from `scroll` and resize in an
 * animation frame, so a scroll re-renders the track once per frame, not once per event.
 * `sync` reads it now (after the caller moved `scrollLeft`).
 */
export function useVisibleRange(
  ref: RefObject<HTMLElement | null>,
): [VisibleRange, () => void] {
  const [range, setRange] = useState<VisibleRange>({ left: 0, width: 0 })

  const sync = useCallback(() => {
    const el = ref.current
    if (el === null) {
      return
    }
    setRange((held) =>
      held.left === el.scrollLeft && held.width === el.clientWidth
        ? held
        : { left: el.scrollLeft, width: el.clientWidth },
    )
  }, [ref])

  useLayoutEffect(() => {
    const el = ref.current
    if (el === null) {
      return undefined
    }
    let frame = 0
    const schedule = () => {
      if (frame === 0) {
        frame = requestAnimationFrame(() => {
          frame = 0
          sync()
        })
      }
    }
    sync()
    el.addEventListener('scroll', schedule, { passive: true })
    const observer = new ResizeObserver(schedule)
    observer.observe(el)
    return () => {
      el.removeEventListener('scroll', schedule)
      observer.disconnect()
      if (frame !== 0) {
        cancelAnimationFrame(frame)
      }
    }
  }, [ref, sync])

  return [range, sync]
}
