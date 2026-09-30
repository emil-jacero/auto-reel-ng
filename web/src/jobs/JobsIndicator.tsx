import './jobs.css'

import { Icon } from '../ui/Icon'
import type { Tone } from '../ui/Pill'
import { CONNECTION_LABEL } from './labels'
import type { ConnectionStatus } from './store'
import { useConnection } from './useJob'

// The connection's tone: live is ok; a first connect is neutral; a lost one warns.
const CONNECTION_TONE: Record<ConnectionStatus, Tone> = {
  live: 'ok',
  connecting: 'idle',
  reconnecting: 'warn',
}

/** "1 rendering · 2 queued", zero parts left out; empty when nothing is active. */
function activity(rendering: number, queued: number): string {
  const parts: string[] = []
  if (rendering > 0) {
    parts.push(`${rendering} rendering`)
  }
  if (queued > 0) {
    parts.push(`${queued} queued`)
  }
  return parts.join(' · ')
}

/**
 * The jobs connection in the header's status slot: Live, Connecting… or
 * Reconnecting… in words (a dot or a loader beside them, never color alone),
 * and, only while live, how many jobs render and wait — counts from a lost
 * connection are not current. Plain text, not a live region: the page regions
 * announce what changed. The shell always mounts it, so the connection is open
 * while the app is, and it imports the jobs stylesheet for the whole slice.
 */
export function JobsIndicator() {
  const { status, rendering, queued } = useConnection()
  const counts = status === 'live' ? activity(rendering, queued) : ''
  return (
    <div className="jobs-indicator" data-connection={status}>
      <span className="pill" data-tone={CONNECTION_TONE[status]}>
        {status === 'live' ? <span className="live-dot" aria-hidden="true" /> : <Icon name="loader" />}
        <span>
          <span className="visually-hidden">Render jobs: </span>
          {CONNECTION_LABEL[status]}
        </span>
      </span>
      {counts !== '' && <span className="jobs-counts">{counts}</span>}
    </div>
  )
}
