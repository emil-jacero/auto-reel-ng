import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { ZOOM, zoomValueText } from './labels'
import { SLIDER_STEPS, ppsToSlider } from './model'

/*
 * The Zoom slider (`timeline-zoom-slider`, design D1/D2): a native range input whose left end is
 * Fit and whose right end is MAX_PPS, logarithmic between. Its position is derived from the scale
 * on every render, so the buttons, keys, wheel and a Fit that follows a resized view move it too.
 * While it is dragged it shows the position under the pointer at once (a render of this input
 * only) and asks the Timeline for one zoom per animation frame, the latest position winning. The
 * native input's own keys apply: arrows one step, Page Up and Page Down a larger one, Home Fit,
 * End the maximum.
 */

export function ZoomSlider({
  pps,
  fit,
  fitted,
  disabled,
  onZoom,
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
}) {
  const [dragged, setDragged] = useState<number | null>(null)
  const latest = useRef<number | null>(null)
  const frame = useRef(0)
  const zoom = useRef(onZoom)
  zoom.current = onZoom
  useEffect(
    () => () => {
      if (frame.current !== 0) {
        cancelAnimationFrame(frame.current)
      }
    },
    [],
  )
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
    />
  )
}
