import type { JobSummary } from '../api/events'
import type { JobOut } from '../api/jobs'
import { isActive } from './status'

/*
 * Which version of an event's job a screen shows, as pure rules (no React, no
 * socket) so `npm test` runs them. A job reaches a screen from its last read
 * (`latest_job`, a `JobSummaryOut`) and from the store's live `JobOut`s; they
 * disagree for a while after every transition.
 */

export type ShownJob =
  | { source: 'live'; job: JobOut } // from the store
  | { source: 'refreshed'; job: JobOut } // the store's copy, brought forward by a read (not live)
  | { source: 'read'; job: JobSummary } // `latest_job` from the screen's last read

export function createdAt(job: { created_at: string }): number {
  return Date.parse(job.created_at)
}

/**
 * How far along an active version of a job is, from the job's own recorded
 * fields (no client clock): running beyond queued, then a later run (a claim
 * after a requeue) beyond an earlier one, then more progress.
 */
function standing(job: JobSummary | JobOut): [number, number, number] {
  return [
    job.status === 'running' ? 1 : 0,
    job.started_at == null ? 0 : Date.parse(job.started_at),
    job.progress,
  ]
}

/** Whether `a` is further along than `b`, comparing their standings in order. */
function isFurther(a: JobSummary | JobOut, b: JobSummary | JobOut): boolean {
  const left = standing(a)
  const right = standing(b)
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) {
      return left[index] > right[index]
    }
  }
  return false
}

/**
 * The newest job known for the event. For one and the same job an ended version
 * beats an active one, since ended states are final. Between two active
 * versions the store's copy wins while the connection is live: it carries every
 * change. While it is not, the store's copy is only last known. A newer read
 * brings it forward: one with a higher `requeue_count` (the job went back to
 * the queue, the opposite of further along), a cancel request the copy lacks,
 * or the job further along. A read with a lower `requeue_count` is older and
 * never does. What a read lacks (the error, the worker) stays from the held copy.
 */
export function choose(
  live: JobOut | undefined,
  latest: JobSummary | null | undefined,
  connectionLive: boolean,
): ShownJob | null {
  if (latest == null) {
    return live === undefined ? null : { source: 'live', job: live }
  }
  if (live === undefined) {
    return { source: 'read', job: latest }
  }
  if (live.id === latest.id) {
    if (isActive(live.status) && !isActive(latest.status)) {
      return { source: 'read', job: latest }
    }
    if (
      !connectionLive &&
      isActive(live.status) &&
      isActive(latest.status) &&
      latest.requeue_count >= live.requeue_count &&
      (latest.requeue_count > live.requeue_count ||
        (latest.cancel_requested && !live.cancel_requested) ||
        isFurther(latest, live))
    ) {
      const { status, progress, started_at, finished_at, cancel_requested, requeue_count } = latest
      return {
        source: 'refreshed',
        job: {
          ...live,
          status,
          progress,
          started_at,
          finished_at,
          cancel_requested,
          requeue_count,
        },
      }
    }
    return { source: 'live', job: live }
  }
  return createdAt(live) >= createdAt(latest)
    ? { source: 'live', job: live }
    : { source: 'read', job: latest }
}
