import type { JobSummary, Staleness } from '../api/events'
import { JOB_STATUS_LABEL, REASON_LABEL } from './labels'

/** Helpers both event screens share. */

/** The failure sentences both screens use, so the same cause reads the same. */
export const DATABASE_CAUSE = "The service can't reach its database."
export const UNREACHABLE_CAUSE = 'The service is not reachable.'

/** The event folder's name: the last segment of its id. */
export function folderName(eventId: string): string {
  return eventId.split('/').pop() ?? eventId
}

export function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`
}

const BYTE_UNITS = ['KiB', 'MiB', 'GiB', 'TiB']

/** A byte count, 1024-based: whole bytes below 1 KiB, one decimal from KiB up. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(1)} ${BYTE_UNITS[unit]}`
}

export function JobCell({ job }: { job: JobSummary | null | undefined }) {
  if (job == null) {
    return null
  }
  const when = new Date(job.created_at).toLocaleString()
  return (
    <>
      <span className={`job job-${job.status}`}>{JOB_STATUS_LABEL[job.status]}</span>
      {job.status === 'running' && <> {Math.round(job.progress * 100)}%</>}
      <div className="muted">{when}</div>
    </>
  )
}

/** The render verdict: a pill, and every reason in words when stale. */
export function StalenessCell({ staleness }: { staleness: Staleness }) {
  return (
    <>
      <span className={staleness.stale ? 'pill pill-stale' : 'pill pill-fresh'}>
        {staleness.stale ? 'Needs render' : 'Up to date'}
      </span>
      {staleness.stale && staleness.reasons.length > 0 && (
        <span className="reasons">
          {staleness.reasons.map((reason) => REASON_LABEL[reason]).join(', ')}
        </span>
      )}
    </>
  )
}
