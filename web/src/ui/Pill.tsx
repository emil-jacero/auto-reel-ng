import type { ReactNode } from 'react'

import { Icon } from './Icon'
import type { IconName } from './Icon'

/** The five status tones of `tokens.css`. */
export type Tone = 'ok' | 'warn' | 'err' | 'info' | 'idle'

/**
 * A status label: an icon and the words, on the tone's colors. The words carry
 * the meaning; the tone and icon only repeat it, so no state is told by color
 * alone.
 */
export function Pill({ tone, icon, children }: { tone: Tone; icon: IconName; children: ReactNode }) {
  return (
    <span className="pill" data-tone={tone}>
      <Icon name={icon} />
      <span>{children}</span>
    </span>
  )
}
