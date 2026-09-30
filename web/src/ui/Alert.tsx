import type { ReactNode } from 'react'

import { Icon } from './Icon'
import type { IconName } from './Icon'
import type { Tone } from './Pill'

const TONE_ICON: Record<Tone, IconName> = {
  ok: 'check',
  warn: 'alert-triangle',
  err: 'alert-triangle',
  info: 'info',
  idle: 'info',
}

/**
 * An inline message block: the tone's icon, a title, an optional detail and an
 * optional action (a link or buttons). `title` is a node, so a failure can keep
 * its kind's `Pill` beside the cause. An alert role by default, so a failure
 * that replaces a screen's content is announced.
 */
export function Alert({
  tone,
  title,
  detail = null,
  action,
  role = 'alert',
}: {
  tone: Tone
  title: ReactNode
  detail?: string | null
  action?: ReactNode
  role?: 'alert' | 'status' | 'note'
}) {
  return (
    <div className="alert" data-tone={tone} role={role}>
      <Icon name={TONE_ICON[tone]} size={20} />
      <div className="alert-body">
        <p className="alert-title">{title}</p>
        {detail !== null && <p className="alert-detail">{detail}</p>}
        {action !== undefined && <div className="alert-action">{action}</div>}
      </div>
    </div>
  )
}
