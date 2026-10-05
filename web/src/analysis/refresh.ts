import type { Analysis } from '../api/analysis'
import type { JobStatus } from '../api/jobs'
import type { AnalysisRead } from './badge'

/*
 * When the event page reads its analysis again by itself (`analysis-web-controls`, D3): pure,
 * so `npm test` decides every transition. The page reads on opening, on Refresh, and here:
 * when the event's analysis job ends, and once when the read says analyzing but the live
 * connection carries no active analysis job of the event. Never on a timer.
 */

/** The event's newest analysis job as the page last saw it, or null for none. */
export type Observed = { id: string; status: JobStatus } | null

export type JobChange =
  | { reload: false }
  // `announce`: the end was seen live, so the status region says how it went once the read
  // answers; a reconciled end (learned after a lost connection) is read again silently.
  | { reload: true; announce: boolean; endedAs: JobStatus }

function active(status: JobStatus): boolean {
  return status === 'queued' || status === 'running'
}

/**
 * The newest job moved from `before` to `after`. Only an end the page saw happen reloads: a
 * job first seen already ended (the read that opened the page is newer), or a newer job
 * replacing an active one while active itself, does not.
 */
export function onJobChange(before: Observed, after: Observed, reconciled: boolean): JobChange {
  if (before === null || after === null || !active(before.status) || active(after.status)) {
    return { reload: false }
  }
  return { reload: true, announce: !reconciled, endedAs: after.status }
}

/**
 * The key to record when the read is to be checked again, else null: the read says analyzing,
 * the connection is live and carries no active analysis job of the event, and no re-read was
 * made for this read's job yet (`checked`), so a service whose answer stays the same cannot
 * make the page loop.
 */
export function recheckKey(
  read: AnalysisRead,
  liveActive: boolean,
  live: boolean,
  checked: string | null,
): string | null {
  if (read.status !== 'ok' || read.analysis.state !== 'analyzing' || liveActive || !live) {
    return null
  }
  const key = read.analysis.job?.id ?? ''
  return key === checked ? null : key
}

function clips(count: number): string {
  return count === 1 ? '1 clip' : `${count} clips`
}

/** What the status region says once the read after a seen end answers. */
export function endWords(endedAs: JobStatus, analysis: Analysis | null): string {
  if (endedAs === 'canceled') {
    return 'Analysis canceled.'
  }
  if (endedAs === 'failed') {
    return 'Analysis failed.'
  }
  const failed =
    analysis === null
      ? 0
      : Object.values(analysis.clips ?? {}).filter((clip) => clip.state === 'failed').length
  return failed > 0 ? `Analysis failed for ${clips(failed)}.` : 'Analysis finished.'
}
