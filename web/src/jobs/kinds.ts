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

/** Whether the job is an analysis job: the analysis badge and the header's own count show these. */
export function isAnalysis(job: Pick<JobOut, 'kind'>): boolean {
  return job.kind === 'analysis'
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

/** The newest analysis job per event id; renders, proxy jobs and other kinds are skipped. */
export function newestAnalysisByEvent(jobs: Iterable<JobOut>): Map<string, JobOut> {
  return newestBy(jobs, isAnalysis)
}

/**
 * How many events have an analysis job queued or running: the header's "N to analyze". The
 * store may hold ended rows of an event beside its active one; only active ones count, and an
 * event counts once (the service holds at most one active analysis job per event).
 */
export function countAnalysis(jobs: Iterable<JobOut>): number {
  const events = new Set<string>()
  for (const job of jobs) {
    if (isAnalysis(job) && (job.status === 'queued' || job.status === 'running')) {
      events.add(job.event_dir)
    }
  }
  return events.size
}

/** How many renders run and how many wait; proxy and analysis jobs are counted in neither. */
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
