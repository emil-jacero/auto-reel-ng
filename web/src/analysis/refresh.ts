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
 * Whether the read a job change causes also forgets the page's dismissals: any end of the
 * event's analysis job this page saw active, live or reconciled, found the suggestions again,
 * so Re-analyze brings dismissed ones back (the Timeline help's promise). A cancel analysed
 * nothing to be trusted, so the dismissals stay.
 */
export function clearsDismissals(change: JobChange): boolean {
  return change.reload && change.endedAs !== 'canceled'
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

/**
 * The job id to record when the read is to be taken once more because a job started: the
 * event's newest analysis job is active and trusted (live, or the one this page queued), the
 * read answered before it (it names no job, or another), and no re-read was made for this job
 * yet (`checked`). The service then reports which clips the job analyzes, and how many, which
 * a read older than the job cannot. One read per job start, never a timer.
 */
export function startKey(
  read: AnalysisRead,
  job: Observed,
  trusted: boolean,
  checked: string | null,
): string | null {
  if (job === null || !trusted || !active(job.status) || read.status !== 'ok') {
    return null
  }
  if (read.analysis.job?.id === job.id || checked === job.id) {
    return null
  }
  return job.id
}

function clips(count: number): string {
  return count === 1 ? '1 clip' : `${count} clips`
}

/**
 * What the status region says once the read after a seen end answers: the clips the new read
 * reports as failed, whatever the job's own end (a job whose every clip failed ends failed);
 * else how the job ended.
 */
export function endWords(endedAs: JobStatus, analysis: Analysis | null): string {
  if (endedAs === 'canceled') {
    return 'Analysis canceled.'
  }
  const failed =
    analysis === null
      ? 0
      : Object.values(analysis.clips ?? {}).filter((clip) => clip.state === 'failed').length
  if (failed > 0) {
    return `Analysis failed for ${clips(failed)}.`
  }
  return endedAs === 'failed' ? 'Analysis failed.' : 'Analysis finished.'
}
