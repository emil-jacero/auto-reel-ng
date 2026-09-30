import type { JobOut } from '../api/jobs'

/*
 * The time-left estimate of a running render, computed in the client: the service
 * reports only `progress` (0..1), and only when it changes. The store calls
 * `nextSample` from its frame and read handlers — never from render — and passes
 * the time in, so every function here is pure.
 *
 * The rate is an exponentially weighted moving average of Δprogress/Δt over the
 * observed increases. The estimate stays hidden until the job is past 5% with
 * at least three observations, and once shown it never grows: each new estimate
 * can only lower it, so it holds while progress stalls instead of jumping back up.
 */

export type Sample = {
  /** When `p` was observed: milliseconds on a monotonic clock. */
  readonly t: number
  readonly p: number
  /** Progress per millisecond, or null until progress has increased once. */
  readonly rate: number | null
  /** Observations of this run of the job so far. */
  readonly n: number
  /** The estimate in effect (milliseconds left), or null while it is hidden. */
  readonly shown: number | null
}

const ALPHA = 0.3
const MIN_PROGRESS = 0.05
const MIN_OBSERVATIONS = 3

/**
 * The sample after observing `job` at `now`. Only a running job is sampled: any
 * other status discards the sample, and progress lower than the last observation
 * (the job was requeued and claimed again) starts a new one.
 */
export function nextSample(
  previous: Sample | undefined,
  job: JobOut,
  now: number,
): Sample | undefined {
  if (job.status !== 'running') {
    return undefined
  }
  const p = job.progress
  if (previous === undefined || p < previous.p) {
    return { t: now, p, rate: null, n: 1, shown: null }
  }
  if (p === previous.p || now <= previous.t) {
    return previous
  }
  const observed = (p - previous.p) / (now - previous.t)
  const rate = previous.rate === null ? observed : ALPHA * observed + (1 - ALPHA) * previous.rate
  const n = previous.n + 1
  const estimate = (1 - p) / rate
  const trusted = p > MIN_PROGRESS && n >= MIN_OBSERVATIONS
  return {
    t: now,
    p,
    rate,
    n,
    shown: trusted ? Math.min(previous.shown ?? estimate, estimate) : null,
  }
}

/** Milliseconds left to show for `job`, or null: hidden, not running, or cancelling. */
export function etaMs(sample: Sample, job: JobOut): number | null {
  return job.status === 'running' && !job.cancel_requested ? sample.shown : null
}

/** "less than a minute left", "about 4 min left", "about 1 h 5 min left": never seconds. */
export function formatEta(ms: number): string {
  if (ms < 60_000) {
    return 'less than a minute left'
  }
  const minutes = Math.round(ms / 60_000)
  if (minutes < 60) {
    return `about ${minutes} min left`
  }
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `about ${hours} h left` : `about ${hours} h ${rest} min left`
}
