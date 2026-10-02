import { isProblem, readJson } from './http'
import type { Problem } from './http'
import type { components } from './schema'

/**
 * The jobs routes and the jobs WebSocket: the only module that knows their URLs
 * and status codes.
 *
 * Aliases into the generated schema, never re-declared shapes (see `events.ts`).
 * Expected failures are values, as in the reads: every caller handles every kind.
 */

export type JobOut = components['schemas']['JobOut']
export type JobStatus = components['schemas']['JobStatus']
export type FreshResult = components['schemas']['FreshResult']
export type CancelResult = components['schemas']['CancelResult']
export type CancelOutcome = components['schemas']['CancelOutcome']
export type EnqueueConflict = components['schemas']['EnqueueConflict']
export type WsMessage = components['schemas']['WsMessage']
export type WsMessageType = components['schemas']['WsMessageType']
type EnqueueRequest = components['schemas']['EnqueueRequest']
export type { Problem }

/** How an enqueue ended: one kind per answer `POST /api/v1/jobs` publishes. */
export type EnqueueResult =
  // 201: the job was created
  | { kind: 'enqueued'; job: JobOut }
  // 200: the event is up to date, nothing was enqueued
  | { kind: 'fresh'; fresh: FreshResult }
  // 409 `active_job`: a job for the event is already queued or running
  | { kind: 'active'; jobId: string; problem: Problem }
  // 409 `output_collision`: other events claim the same movie file
  | { kind: 'collision'; claimedBy: string[]; problem: Problem }
  // 404 (unknown event) or 502 (the project walk failed), in the ProblemOut shape
  | { kind: 'problem'; problem: Problem }
  // 503 naming the database as the failing dependency: the job's creation was not confirmed
  | { kind: 'database'; problem: Problem }
  // no answer at all: fetch rejected (the message is the error)
  | { kind: 'unreachable'; message: string }
  // an answer whose status or body the route does not publish (the message names it)
  | { kind: 'unpublished'; message: string }

/** How a job read ended. */
export type JobResult =
  | { kind: 'ok'; job: JobOut }
  // 404: no such job in the served project
  | { kind: 'problem'; problem: Problem }
  // 503 naming the database as the failing dependency
  | { kind: 'database'; problem: Problem }
  | { kind: 'unreachable'; message: string }
  | { kind: 'unpublished'; message: string }

/** How a cancel request ended. */
export type CancelAnswer =
  | { kind: 'ok'; result: CancelResult }
  // 404: no such job in the served project
  | { kind: 'problem'; problem: Problem }
  // 503 naming the database as the failing dependency: no outcome was applied or reported
  | { kind: 'database'; problem: Problem }
  | { kind: 'unreachable'; message: string }
  | { kind: 'unpublished'; message: string }

const JOBS_URL = '/api/v1/jobs'
const SOCKET_PATH = '/api/v1/ws/jobs'

// The problem statuses each route publishes (see the schema). 409 is not here:
// the enqueue answer's conflict kind decides what it means. 503 is not here
// either: it is a `database` kind only when its `check` field says so, and any
// other 503 (a proxy's, or one without the field) stays unpublished, so the
// client never claims a cause the answer does not carry.
const ENQUEUE_PROBLEM_STATUSES = new Set([404, 502])
const JOB_PROBLEM_STATUSES = new Set([404])

/** A 503 whose problem body names the database as the failing dependency. */
function isDatabaseDown(response: Response, body: unknown): body is Problem {
  return response.status === 503 && isProblem(body) && body.check === 'database'
}

function unpublished(method: string, url: string, response: Response): string {
  return `${method} ${url} answered ${response.status} ${response.statusText}`.trimEnd()
}

/**
 * Enqueue a render of one event; `force` bypasses the staleness gate (never the
 * output-collision check). The device is left to the service's default. Not
 * abortable: it is a write, and its answer still matters after the caller leaves.
 */
export async function enqueueJob(eventId: string, force: boolean): Promise<EnqueueResult> {
  const request: Pick<EnqueueRequest, 'event_id' | 'force'> = { event_id: eventId, force }
  let response: Response
  try {
    response = await fetch(JOBS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
  } catch (error) {
    return { kind: 'unreachable', message: String(error) }
  }

  const body = await readJson(response)
  const isObject = typeof body === 'object' && body !== null
  if (response.status === 201 && isObject) {
    return { kind: 'enqueued', job: body as JobOut }
  }
  if (response.status === 200 && isObject) {
    return { kind: 'fresh', fresh: body as FreshResult }
  }
  if (isDatabaseDown(response, body)) {
    return { kind: 'database', problem: body }
  }
  if (response.status === 409 && isProblem(body)) {
    // A 409 means only what its conflict kind says; one without the kind, or
    // without the field its kind promises, is unpublished, never guessed as
    // "already active".
    const conflict = body.conflict
    if (conflict != null) {
      switch (conflict) {
        case 'active_job':
          if (typeof body.job_id === 'string') {
            return { kind: 'active', jobId: body.job_id, problem: body }
          }
          break
        case 'output_collision':
          if (Array.isArray(body.claimed_by)) {
            return { kind: 'collision', claimedBy: body.claimed_by, problem: body }
          }
          break
        default: {
          // A new conflict kind is a `tsc --noEmit` error here until it is handled.
          const unhandled: never = conflict
          return {
            kind: 'unpublished',
            message: `${unpublished('POST', JOBS_URL, response)}: conflict ${String(unhandled)}`,
          }
        }
      }
    }
  }
  if (ENQUEUE_PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return { kind: 'unpublished', message: unpublished('POST', JOBS_URL, response) }
}

/** Read one job. Rethrows `AbortError` when `signal` aborted it. */
export async function fetchJob(jobId: string, signal?: AbortSignal): Promise<JobResult> {
  const url = `${JOBS_URL}/${encodeURIComponent(jobId)}`
  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (error) {
    if (signal?.aborted === true) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }

  const body = await readJson(response)
  if (response.status === 200 && typeof body === 'object' && body !== null) {
    return { kind: 'ok', job: body as JobOut }
  }
  if (isDatabaseDown(response, body)) {
    return { kind: 'database', problem: body }
  }
  if (JOB_PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return { kind: 'unpublished', message: unpublished('GET', url, response) }
}

/** Ask the service to cancel one job. A write, so not abortable (see `enqueueJob`). */
export async function cancelJob(jobId: string): Promise<CancelAnswer> {
  const url = `${JOBS_URL}/${encodeURIComponent(jobId)}/cancel`
  let response: Response
  try {
    response = await fetch(url, { method: 'POST' })
  } catch (error) {
    return { kind: 'unreachable', message: String(error) }
  }

  const body = await readJson(response)
  if (response.status === 200 && typeof body === 'object' && body !== null) {
    return { kind: 'ok', result: body as CancelResult }
  }
  if (isDatabaseDown(response, body)) {
    return { kind: 'database', problem: body }
  }
  if (JOB_PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return { kind: 'unpublished', message: unpublished('POST', url, response) }
}

/**
 * The jobs WebSocket's URL, by path on the serving origin (the dev proxy forwards
 * it with `ws: true`), `wss:` when the page itself is served over TLS.
 */
export function jobsSocketUrl(): string {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${scheme}//${window.location.host}${SOCKET_PATH}`
}
