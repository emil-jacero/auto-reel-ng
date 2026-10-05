import { encodeEventId } from '../route'
import { isProblem, readJson, unpublishedAnswer } from './http'
import type { Problem, Unanswered } from './http'
import type { JobOut } from './jobs'
import type { components, paths } from './schema'

/**
 * The event's analysis: the cached read, the event's enqueue (Re-analyze) and Analyze all.
 * The only module that knows their URLs and status codes. The read starts nothing; the two
 * writes only queue `analysis` jobs, which the worker runs.
 *
 * Aliases into the generated schema, never re-declared shapes (see `events.ts`).
 */

export type Analysis = components['schemas']['AnalysisOut']
export type Segment = components['schemas']['SegmentOut']
export type AnalysisState = components['schemas']['AnalysisState']
export type ClipAnalysis = components['schemas']['ClipAnalysisOut']
export type AnalysisFreshResult = components['schemas']['AnalysisFreshResult']
export type AnalyzeAllResult = components['schemas']['AnalyzeAllResult']
type AnalysisEnqueueRequest = components['schemas']['AnalysisEnqueueRequest']

const EVENT_ANALYSIS_PATH = '/api/v1/events/{event_id}/analysis' satisfies keyof paths
const ANALYZE_ALL_PATH = '/api/v1/analysis' satisfies keyof paths

/** How a read ended; expected failures are values, as in `fetchEvent`. */
export type AnalysisResult =
  | { kind: 'ok'; analysis: Analysis }
  // 404/502/503 in the published ProblemOut shape (503: the job store, `check` `database`)
  | { kind: 'problem'; problem: Problem }
  | Unanswered

// The failure statuses the service declares for this read (see the schema).
const PROBLEM_STATUSES = new Set([404, 502, 503])

/**
 * Read one event's analysis. Its id's segments are encoded one by one, matching the
 * service's `{event_id:path}` route. Rethrows `AbortError`.
 */
export async function fetchAnalysis(
  eventId: string,
  signal: AbortSignal,
): Promise<AnalysisResult> {
  const url = eventAnalysisUrl(eventId)
  let response: Response
  try {
    // Never from the browser's cache: a re-run of `auto-reel analyze` must show on the next opening.
    response = await fetch(url, { signal, cache: 'no-store' })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }

  const body = await readJson(response)
  if (response.status === 200 && typeof body === 'object' && body !== null) {
    return { kind: 'ok', analysis: body as Analysis }
  }
  if (PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return unpublishedAnswer('GET', url, response)
}

function eventAnalysisUrl(eventId: string): string {
  return EVENT_ANALYSIS_PATH.replace('{event_id}', () => encodeEventId(eventId))
}

/** How an event's enqueue ended: one kind per answer `POST …/analysis` publishes. */
export type EnqueueAnalysisResult =
  // 201: the analysis job was created
  | { kind: 'enqueued'; job: JobOut }
  // 200: no clip needs analysis (unforced), or the folder lists no clip; nothing was enqueued
  | { kind: 'fresh'; fresh: AnalysisFreshResult }
  // 409 `active_job`: an analysis job of the event is queued or running; `forced` is
  // whether that job carries `force` (false: a running unforced job, not a re-analysis)
  | { kind: 'active'; jobId: string; forced: boolean | null; problem: Problem }
  // 404 (unknown event) or 502 (the folder, a clip or a cache entry cannot be read)
  | { kind: 'problem'; problem: Problem }
  // 503 naming the database: the job's creation was not confirmed
  | { kind: 'database'; problem: Problem }
  | Unanswered

const ENQUEUE_PROBLEM_STATUSES = new Set([404, 502])

/**
 * Queue the event's analysis; `force` is Re-analyze (every clip again, cached results and
 * recorded failures overridden when the job runs). A write, so not abortable: its answer
 * still matters after the caller leaves. A 503 is a `database` answer only when its
 * problem names the database; a 409 only when its conflict kind and job id are there.
 */
export async function enqueueAnalysis(
  eventId: string,
  { force }: { force: boolean },
): Promise<EnqueueAnalysisResult> {
  const url = eventAnalysisUrl(eventId)
  const request: AnalysisEnqueueRequest = { force }
  let response: Response
  try {
    response = await fetch(url, {
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
  if (response.status === 200 && isObject && (body as { status?: unknown }).status === 'fresh') {
    return { kind: 'fresh', fresh: body as AnalysisFreshResult }
  }
  if (response.status === 503 && isProblem(body) && body.check === 'database') {
    return { kind: 'database', problem: body }
  }
  if (response.status === 409 && isProblem(body)) {
    if (body.conflict === 'active_job' && typeof body.job_id === 'string') {
      const forced = typeof body.forced === 'boolean' ? body.forced : null
      return { kind: 'active', jobId: body.job_id, forced, problem: body }
    }
  } else if (ENQUEUE_PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return unpublishedAnswer('POST', url, response)
}

/** How Analyze all ended: one kind per answer `POST /api/v1/analysis` publishes. */
export type AnalyzeAllAnswer =
  // 200: what happened to each event the list shows
  | { kind: 'counted'; result: AnalyzeAllResult }
  // 502: the project walk failed; nothing was enqueued
  | { kind: 'problem'; problem: Problem }
  // 503 naming the database: jobs inserted before it stay queued, the rest were not
  | { kind: 'database'; problem: Problem }
  | Unanswered

function isAnalyzeAllResult(body: unknown): body is AnalyzeAllResult {
  if (typeof body !== 'object' || body === null) {
    return false
  }
  const fields = body as Record<string, unknown>
  return (
    typeof fields.queued === 'number' &&
    typeof fields.fresh === 'number' &&
    typeof fields.active === 'number' &&
    Array.isArray(fields.unreadable)
  )
}

/**
 * Analyze all: queue an unforced analysis job for every event that needs one. No body;
 * a write, so not abortable.
 */
export async function analyzeAll(): Promise<AnalyzeAllAnswer> {
  const url = ANALYZE_ALL_PATH
  let response: Response
  try {
    response = await fetch(url, { method: 'POST' })
  } catch (error) {
    return { kind: 'unreachable', message: String(error) }
  }
  const body = await readJson(response)
  if (response.status === 200 && isAnalyzeAllResult(body)) {
    return { kind: 'counted', result: body }
  }
  if (response.status === 503 && isProblem(body) && body.check === 'database') {
    return { kind: 'database', problem: body }
  }
  if (response.status === 502 && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return unpublishedAnswer('POST', url, response)
}
