import { useCallback, useLayoutEffect, useState } from 'react'
import type { RefObject } from 'react'

/** What the track's scroller shows: how far it is scrolled and how wide it is, in px. */
export type VisibleRange = { left: number; width: number }

/**
 * The scroller's range, kept in state and updated from `scroll` and resize in an
 * animation frame, so a scroll re-renders the track once per frame, not once per event.
 * `sync` reads it now (after the caller moved `scrollLeft`). `expect` sets the left a zoom is
 * about to scroll to, in the same render as the zoom: the browser's rounding of `scrollLeft`
 * (under a pixel) then reads as no change, and a zoom renders the track once, not twice.
 */
export function useVisibleRange(
  ref: RefObject<HTMLElement | null>,
): [VisibleRange, () => void, (left: number) => void] {
  const [range, setRange] = useState<VisibleRange>({ left: 0, width: 0 })

  const sync = useCallback(() => {
    const el = ref.current
    if (el === null) {
      return
    }
    setRange((held) =>
      Math.abs(held.left - el.scrollLeft) < 1 && held.width === el.clientWidth
        ? held
        : { left: el.scrollLeft, width: el.clientWidth },
    )
  }, [ref])

  const expect = useCallback(
    (left: number) =>
      setRange((held) => (held.left === left ? held : { left, width: held.width })),
    [],
  )

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

  return [range, sync, expect]
}
