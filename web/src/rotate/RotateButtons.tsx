import './rotate.css'

import { memo } from 'react'

import { Icon } from '../ui/Icon'
import type { Way } from './turn.ts'

/** Constant elements: React skips them on the re-render every row gets per drag step. */
const LEFT = <Icon name="rotate-ccw" />
const RIGHT = <Icon name="rotate-cw" />

export type RotateHandler = (identity: string, way: Way) => void

/**
 * A clip's Rotate left and Rotate right (`clip-rotation`): two icon buttons that set the clip's
 * turn in the draft. Named "Rotate <name> left" / "right". Busy-control rule: while a save or a
 * move is pending they are aria-disabled and ignore presses (never `disabled`, which would
 * drop the focus). They start no drag and do not mark; memoised so a drag step re-renders neither.
 */
export const RotateButtons = memo(function RotateButtons({
  identity,
  name,
  locked,
  onRotate,
}: {
  identity: string
  name: string
  locked: boolean
  onRotate: RotateHandler
}) {
  return (
    <span className="clip-rotate">
      <button
        type="button"
        className="btn btn-ghost btn-icon rotate-left"
        aria-label={`Rotate ${name} left`}
        aria-disabled={locked || undefined}
        onClick={() => {
          if (!locked) {
            onRotate(identity, 'left')
          }
        }}
      >
        {LEFT}
      </button>
      <button
        type="button"
        className="btn btn-ghost btn-icon rotate-right"
        aria-label={`Rotate ${name} right`}
        aria-disabled={locked || undefined}
        onClick={() => {
          if (!locked) {
            onRotate(identity, 'right')
          }
        }}
      >
        {RIGHT}
      </button>
    </span>
  )
})
