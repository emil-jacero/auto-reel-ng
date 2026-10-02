import { useEffect, useMemo, useSyncExternalStore } from 'react'

import type { JobSummary } from '../api/events'
import type { JobOut } from '../api/jobs'
import { choose, createdAt } from './shownJob'
import type { ShownJob } from './shownJob'
import { getState, isActive, load, subscribe } from './store'
import type { ConnectionStatus } from './store'

export type { ShownJob }

/*
 * Which job an event shows. A job reaches a screen from its last read
 * (`latest_job`, a `JobSummaryOut`), from the store's live `JobOut`s, and from
 * single-job reads; they disagree for a while after every transition.
 */

// The newest store job per event id, rebuilt once per `jobs` map: every row's
// selector then returns the same object until its own job changes.
let indexed: ReadonlyMap<string, JobOut> | null = null
let newestByEvent = new Map<string, JobOut>()

function newestJobOf(eventId: string): JobOut | undefined {
  const { jobs } = getState()
  if (jobs !== indexed) {
    const index = new Map<string, JobOut>()
    for (const job of jobs.values()) {
      const held = index.get(job.event_dir)
      if (held === undefined || createdAt(job) > createdAt(held)) {
        index.set(job.event_dir, job)
      }
    }
    indexed = jobs
    newestByEvent = index
  }
  return newestByEvent.get(eventId)
}

/**
 * The job to show for `eventId`: the store's newest (`event_dir` is the event
 * id), or the read's `latest`. A screen never keeps showing the read's active job
 * as current after it ended: when the read's job wins while active and the live
 * connection lacks it, or the store holds as active what the read shows ended,
 * the job is read once from the service (a reconciled end: no toast).
 */
export function useEventJob(
  eventId: string,
  latest: JobSummary | null | undefined,
): ShownJob | null {
  const live = useSyncExternalStore(subscribe, () => newestJobOf(eventId))
  const connection = useSyncExternalStore(subscribe, () => getState().connection)
  const shown = useMemo(
    () => choose(live, latest, connection === 'live'),
    [live, latest, connection],
  )

  const latestId = latest?.id
  const latestStatus = latest?.status
  const readWins = shown !== null && shown.source === 'read'
  useEffect(() => {
    if (latestId === undefined || latestStatus === undefined) {
      return
    }
    const stored = getState().jobs.get(latestId)
    if (stored === undefined) {
      // Live, so the snapshot would carry the job were it still active.
      if (readWins && isActive(latestStatus) && connection === 'live') {
        load(latestId, { knownActive: true })
      }
    } else if (isActive(stored.status) && !isActive(latestStatus)) {
      load(latestId, { knownActive: true, force: true })
    }
  }, [latestId, latestStatus, readWins, connection, live])

  return shown
}

/** The connection's state, and how many of the served project's jobs render and wait. */
export function useConnection(): { status: ConnectionStatus; rendering: number; queued: number } {
  const state = useSyncExternalStore(subscribe, getState)
  return useMemo(() => {
    let rendering = 0
    let queued = 0
    for (const job of state.jobs.values()) {
      if (job.status === 'running') {
        rendering += 1
      } else if (job.status === 'queued') {
        queued += 1
      }
    }
    return { status: state.connection, rendering, queued }
  }, [state])
}
