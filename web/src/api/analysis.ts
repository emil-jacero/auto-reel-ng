import { encodeEventId } from '../route'
import { isProblem, readJson, unpublishedAnswer } from './http'
import type { Problem, Unanswered } from './http'
import type { components } from './schema'

/**
 * The event's cached analysis read: the only module that knows its URL and its status
 * codes. It reads what `auto-reel analyze` left in the sidecar cache and starts nothing.
 *
 * Aliases into the generated schema, never re-declared shapes (see `events.ts`).
 */

export type Analysis = components['schemas']['AnalysisOut']
export type Segment = components['schemas']['SegmentOut']

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
  const url = `/api/v1/events/${encodeEventId(eventId)}/analysis`
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
