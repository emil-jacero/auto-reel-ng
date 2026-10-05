import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, PointerEvent } from 'react'

import { ZOOM, zoomValueText } from './labels'
import { SLIDER_STEPS, ppsToSlider } from './model'

/*
 * The Zoom slider (`timeline-zoom-slider`, design D1/D2): a native range input whose left end is
 * Fit and whose right end is MAX_PPS, logarithmic between. Its position is derived from the scale
 * on every render, so the buttons, keys, wheel and a Fit that follows a resized view move it too.
 * While it is dragged it shows the position under the pointer at once (a render of this input
 * only) and asks the Timeline for one zoom per animation frame, the latest position winning. The
 * native input's own keys apply: arrows one step, Page Up and Page Down a larger one, Home Fit,
 * End the maximum. A press and its release are reported (`onPress`, `onRelease`; design D6 of
 * `edit-list-paint-cost`): the release comes after the last position is zoomed to, wherever the
 * pointer is let go. Only a primary press counts: a right press opens the context menu, which takes
 * its release, so it would leave the zoom open. A context menu that a primary press opens (Ctrl+click
 * on macOS) or the window losing focus ends the press too.
 */

export function ZoomSlider({
  pps,
  fit,
  fitted,
  disabled,
  onZoom,
  onPress,
  onRelease,
}: {
  /** The scale shown now. */
  pps: number
  /** Fit's scale now: the slider's left end. */
  fit: number
  fitted: boolean
  /** Fit is already the maximum: nothing to zoom. */
  disabled: boolean
  /** A position to zoom to (0 is Fit), at most once per animation frame. */
  onZoom: (position: number) => void
  /** The thumb or track is pressed. */
  onPress?: () => void
  /** That press ends (pointer up or cancelled, anywhere), after its last zoom. */
  onRelease?: () => void
}) {
  const [dragged, setDragged] = useState<number | null>(null)
  const latest = useRef<number | null>(null)
  const frame = useRef(0)
  const zoom = useRef(onZoom)
  zoom.current = onZoom
  const release = useRef(onRelease)
  release.current = onRelease
  // The window listeners of a press in progress, removed on its release or on unmount.
  const unlisten = useRef<(() => void) | null>(null)
  useEffect(
    () => () => {
      if (frame.current !== 0) {
        cancelAnimationFrame(frame.current)
      }
      unlisten.current?.()
    },
    [],
  )
  const onPointerDown = (event: PointerEvent<HTMLInputElement>) => {
    if (event.button !== 0 || !event.isPrimary || unlisten.current !== null) {
      return
    }
    const end = () => {
      unlisten.current?.()
      // The position of the last move, not yet zoomed to (it waits for the next frame), goes first.
      if (frame.current !== 0) {
        cancelAnimationFrame(frame.current)
        frame.current = 0
        const at = latest.current
        latest.current = null
        setDragged(null)
        if (at !== null) {
          zoom.current(at)
        }
      }
      release.current?.()
    }
    window.addEventListener('pointerup', end, true)
    window.addEventListener('pointercancel', end, true)
    window.addEventListener('contextmenu', end, true)
    window.addEventListener('blur', end)
    unlisten.current = () => {
      window.removeEventListener('pointerup', end, true)
      window.removeEventListener('pointercancel', end, true)
      window.removeEventListener('contextmenu', end, true)
      window.removeEventListener('blur', end)
      unlisten.current = null
    }
    onPress?.()
  }
  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    const position = Number(event.currentTarget.value)
    latest.current = position
    setDragged(position)
    if (frame.current === 0) {
      frame.current = requestAnimationFrame(() => {
        frame.current = 0
        const at = latest.current
        latest.current = null
        setDragged(null)
        if (at !== null) {
          zoom.current(at)
        }
      })
    }
  }
  const position = dragged ?? (fitted ? 0 : ppsToSlider(pps, fit))
  return (
    <input
      type="range"
      className="tl-zoom-slider"
      aria-label={ZOOM}
      title={ZOOM}
      min={0}
      max={SLIDER_STEPS}
      step={1}
      value={disabled ? 0 : position}
      aria-valuetext={zoomValueText(pps, fitted || disabled)}
      disabled={disabled}
      onChange={onChange}
      onPointerDown={onPointerDown}
    />
  )
}
