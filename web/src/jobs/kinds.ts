import type { JobOut } from '../api/jobs'
import { createdAt } from './shownJob'

/*
 * The store holds jobs of every kind (the socket carries them all), but a screen
 * about renders (the event row, the event page, the render control, the header's
 * count) shows renders only: a proxy job of an event is not its render, and its
 * end must never read as the render's. Pure, so `npm test` runs it.
 */

/** Whether the job is a render. Anything else, a kind this build does not know included, is not. */
export function isRender(job: Pick<JobOut, 'kind'>): boolean {
  return job.kind === 'render'
}

/** Whether the job is a proxy job: the Timeline's Prepare state shows these and only these. */
export function isProxy(job: Pick<JobOut, 'kind'>): boolean {
  return job.kind === 'proxy'
}

/** The newest job per event id (`event_dir`) among those `keep` accepts. */
function newestBy(jobs: Iterable<JobOut>, keep: (job: JobOut) => boolean): Map<string, JobOut> {
  const index = new Map<string, JobOut>()
  for (const job of jobs) {
    if (!keep(job)) {
      continue
    }
    const held = index.get(job.event_dir)
    if (held === undefined || createdAt(job) > createdAt(held)) {
      index.set(job.event_dir, job)
    }
  }
  return index
}

/** The newest render per event id (`event_dir`); jobs of other kinds are skipped. */
export function newestRenderByEvent(jobs: Iterable<JobOut>): Map<string, JobOut> {
  return newestBy(jobs, isRender)
}

/** The newest proxy job per event id; renders and other kinds are skipped. */
export function newestProxyByEvent(jobs: Iterable<JobOut>): Map<string, JobOut> {
  return newestBy(jobs, isProxy)
}

/** How many renders run and how many wait; proxy jobs are counted in neither. */
export function countRenders(jobs: Iterable<JobOut>): { rendering: number; queued: number } {
  let rendering = 0
  let queued = 0
  for (const job of jobs) {
    if (!isRender(job)) {
      continue
    }
    if (job.status === 'running') {
      rendering += 1
    } else if (job.status === 'queued') {
      queued += 1
    }
  }
  return { rendering, queued }
}
