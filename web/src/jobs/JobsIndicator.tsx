import './jobs.css'

import { JOB_STATUS_LOOK } from '../events/tones'
import { Icon } from '../ui/Icon'
import type { IconName } from '../ui/Icon'
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
 * icon and the number show; the words stay for assistive technology. A render
 * count takes its status's icon; the analysis count has its own (`scan`).
 */
function Count({ count, icon, word }: { count: number; icon: IconName; word: string }) {
  return (
    <span className="jobs-count">
      <Icon name={icon} />
      {count}
      <span className="jobs-count-word"> {word}</span>
    </span>
  )
}

/**
 * The jobs connection in the header's status slot: Live, Connecting… or
 * Reconnecting… in words (a dot or a loader beside them, never color alone),
 * and, only while live, how many jobs render and wait, and how many events
 * have an analysis queued or running — counts from a lost connection are not
 * current. Plain text, not a live region: the page regions
 * announce what changed. The shell always mounts it, so the connection is open
 * while the app is, and it imports the jobs stylesheet for the whole slice. For
 * the same reason it holds the slice's hidden status region (`announce.ts`).
 */
export function JobsIndicator() {
  const { status, rendering, queued, analyzing } = useConnection()
  const said = useAnnouncement()
  const counted = status === 'live' && (rendering > 0 || queued > 0 || analyzing > 0)
  return (
    <div className="jobs-indicator" data-connection={status}>
      <span className="pill" data-tone={CONNECTION_TONE[status]}>
        {status === 'live' ? (
          <span className="live-dot" aria-hidden="true" />
        ) : (
          <Icon name="loader" />
        )}
        <span>
          <span className="visually-hidden">Jobs: </span>
          {CONNECTION_LABEL[status]}
        </span>
      </span>
      {counted && (
        <span className="jobs-counts">
          {rendering > 0 && (
            <Count count={rendering} icon={JOB_STATUS_LOOK.running.icon} word="rendering" />
          )}
          {queued > 0 && <Count count={queued} icon={JOB_STATUS_LOOK.queued.icon} word="queued" />}
          {analyzing > 0 && <Count count={analyzing} icon="scan" word="to analyze" />}
        </span>
      )}
      <p role="status" className="visually-hidden">
        {said !== null && <span key={said.id}>{said.message}</span>}
      </p>
    </div>
  )
}
