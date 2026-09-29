import type { components } from './schema'

/**
 * The events read: the only module that knows its URL and its status codes.
 *
 * Every shape here is an alias into the generated schema, never a re-declared
 * one, so a field the service stops publishing is a `tsc --noEmit` error at the
 * line that reads it.
 */

export type EventSummary = components['schemas']['EventSummaryOut']
export type EventError = components['schemas']['EventErrorOut']
export type EventFailure = components['schemas']['EventFailure']
/** One list row: a summary, or an event that could not be read, told apart by `kind`. */
export type EventRow = EventSummary | EventError
export type Staleness = components['schemas']['StalenessOut']
export type StalenessReason = components['schemas']['StalenessReason']
export type JobSummary = components['schemas']['JobSummaryOut']
export type JobStatus = components['schemas']['JobStatus']
export type Problem = components['schemas']['ProblemOut']

/**
 * How a read ended. Expected failures are values, not exceptions, so every
 * caller must handle all three outcomes.
 */
export type EventsResult =
  | { kind: 'ok'; events: EventRow[] }
  // 502/503 in the published ProblemOut shape
  | { kind: 'problem'; problem: Problem }
  // fetch rejected, or a status or body that carries no published shape
  | { kind: 'unreachable'; message: string }

const EVENTS_URL = '/api/v1/events'

// The failure statuses the service declares for this read (see the schema).
const PROBLEM_STATUSES = new Set([502, 503])

function isProblem(body: unknown): body is Problem {
  if (typeof body !== 'object' || body === null) {
    return false
  }
  const fields = body as Record<string, unknown>
  return (
    typeof fields.title === 'string' &&
    typeof fields.status === 'number' &&
    typeof fields.detail === 'string'
  )
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    return undefined
  }
}

/**
 * Read the events list. Rethrows `AbortError` — an abort is the caller's own
 * doing, not a failure to report.
 */
export async function fetchEvents(signal: AbortSignal): Promise<EventsResult> {
  let response: Response
  try {
    response = await fetch(EVENTS_URL, { signal })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }

  const body = await readJson(response)
  if (response.status === 200 && Array.isArray(body)) {
    return { kind: 'ok', events: body as EventRow[] }
  }
  if (PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return {
    kind: 'unreachable',
    message: `GET ${EVENTS_URL} answered ${response.status} ${response.statusText}`.trimEnd(),
  }
}
