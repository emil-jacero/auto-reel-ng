import './rotate.css'

import { Icon } from '../ui/Icon'
import { turnWords } from './turn.ts'
import type { Turn } from './turn.ts'

/**
 * The read view's tag for a turned clip: "Rotated 90 degrees" in words with an icon, so the
 * state is not told by colour alone. Nothing for a clip with no turn.
 */
export function TurnTag({ turn }: { turn: Turn }) {
  if (turn === 0) {
    return null
  }
  return (
    <span className="turn-tag">
      <Icon name="rotate-cw" />
      {turnWords(turn)}
    </span>
  )
}
