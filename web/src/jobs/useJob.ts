import { useEffect, useMemo, useSyncExternalStore } from 'react'

import type { JobSummary } from '../api/events'
import type { JobOut } from '../api/jobs'
import { countRenders, newestRenderByEvent } from './kinds'
import { choose } from './shownJob'
import type { ShownJob } from './shownJob'
import { getState, isActive, load, subscribe } from './store'
import type { ConnectionStatus } from './store'

export type { ShownJob }

/*
 * Which job an event shows. A job reaches a screen from its last read
 * (`latest_job`, a `JobSummaryOut`), from the store's live `JobOut`s, and from
 * single-job reads; they disagree for a while after every transition.
 */

// The newest store render per event id (a proxy job of the event is not its render),
// rebuilt once per `jobs` map: every row's selector then returns the same object
// until its own job changes.
let indexed: ReadonlyMap<string, JobOut> | null = null
let newestByEvent = new Map<string, JobOut>()

function newestJobOf(eventId: string): JobOut | undefined {
  const { jobs } = getState()
  if (jobs !== indexed) {
    indexed = jobs
    newestByEvent = newestRenderByEvent(jobs.values())
  }
  return newestByEvent.get(eventId)
}

/**
 * The job to show for `eventId`: the store's newest render (`event_dir` is the event
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

/** The connection's state, and how many of the served project's renders run and wait. */
export function useConnection(): { status: ConnectionStatus; rendering: number; queued: number } {
  const state = useSyncExternalStore(subscribe, getState)
  return useMemo(() => {
    return { status: state.connection, ...countRenders(state.jobs.values()) }
  }, [state])
}
