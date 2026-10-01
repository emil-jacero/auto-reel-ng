import './jobs.css'

import type { JobStatus } from '../api/jobs'
import { JOB_STATUS_LOOK } from '../events/tones'
import { Icon } from '../ui/Icon'
import type { Tone } from '../ui/Pill'
import { useAnnouncement } from './announce'
import { CONNECTION_LABEL } from './labels'
import type { ConnectionStatus } from './store'
import { useConnection } from './useJob'

// The connection's tone: live is ok; a first connect is neutral; a lost one warns.
const CONNECTION_TONE: Record<ConnectionStatus, Tone> = {
  live: 'ok',
  connecting: 'idle',
  reconnecting: 'warn',
}

/**
 * One count, a unit that never breaks: "1 rendering". At phone width only the
 * status's icon and the number show; the words stay for assistive technology.
 */
function Count({ count, status, word }: { count: number; status: JobStatus; word: string }) {
  return (
    <span className="jobs-count">
      <Icon name={JOB_STATUS_LOOK[status].icon} />
      {count}
      <span className="jobs-count-word"> {word}</span>
    </span>
  )
}

/**
 * The jobs connection in the header's status slot: Live, Connecting… or
 * Reconnecting… in words (a dot or a loader beside them, never color alone),
 * and, only while live, how many jobs render and wait — counts from a lost
 * connection are not current. Plain text, not a live region: the page regions
 * announce what changed. The shell always mounts it, so the connection is open
 * while the app is, and it imports the jobs stylesheet for the whole slice. For
 * the same reason it holds the slice's hidden status region (`announce.ts`).
 */
export function JobsIndicator() {
  const { status, rendering, queued } = useConnection()
  const said = useAnnouncement()
  const counted = status === 'live' && (rendering > 0 || queued > 0)
  return (
    <div className="jobs-indicator" data-connection={status}>
      <span className="pill" data-tone={CONNECTION_TONE[status]}>
        {status === 'live' ? (
          <span className="live-dot" aria-hidden="true" />
        ) : (
          <Icon name="loader" />
        )}
        <span>
          <span className="visually-hidden">Render jobs: </span>
          {CONNECTION_LABEL[status]}
        </span>
      </span>
      {counted && (
        <span className="jobs-counts">
          {rendering > 0 && <Count count={rendering} status="running" word="rendering" />}
          {queued > 0 && <Count count={queued} status="queued" word="queued" />}
        </span>
      )}
      <p role="status" className="visually-hidden">
        {said !== null && <span key={said.id}>{said.message}</span>}
      </p>
    </div>
  )
}
