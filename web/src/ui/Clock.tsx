import './clock.css'

import type { CSSProperties } from 'react'

import type { ClockCell } from '../clock'

/**
 * One time of a readout in its cell: the width is the scale's (`--ch`, a digit of the
 * mono face), so the cell does not change width as the time changes. No layout is done
 * in script: the inline style only sets the property.
 */
export function ClockTime({ cell }: { cell: ClockCell }) {
  return (
    <span className="clock-cell" style={{ '--ch': cell.ch } as CSSProperties}>
      {cell.text}
    </span>
  )
}

/** `Clip 0:00.96 of 0:39.84`: a word for what the pair is, the time, then its total. */
export function ClockGroup({
  label,
  time,
  length,
}: {
  label: string
  time: ClockCell
  length: ClockCell
}) {
  return (
    <span className="clock-group">
      <span className="clock-key">{label}</span> <ClockTime cell={time} />{' '}
      <span className="clock-of">of</span> <ClockTime cell={length} />
    </span>
  )
}
