import { encodeEventId } from '../route'
import { isProblem, readJson } from './http'
import type { Problem } from './http'
import type { components } from './schema'

/**
 * The one-event read: the only module that knows its URL and its status codes.
 *
 * Aliases into the generated schema, never re-declared shapes (see `events.ts`).
 */

export type EventDetail = components['schemas']['EventDetailOut']
export type Chapter = components['schemas']['ChapterOut']
export type Clip = components['schemas']['ClipOut']
export type ClipStatus = components['schemas']['ClipStatus']

/** How a read ended; expected failures are values, as in `fetchEvents`. */
export type EventResult =
  | { kind: 'ok'; event: EventDetail }
  // 404/502/503 in the published ProblemOut shape
  | { kind: 'problem'; problem: Problem }
  // fetch rejected, or a status or body that carries no published shape
  | { kind: 'unreachable'; message: string }

// The failure statuses the service declares for this read (see the schema).
const PROBLEM_STATUSES = new Set([404, 502, 503])

/**
 * Read one event. Its id's segments are encoded one by one, matching the
 * service's `{event_id:path}` route. Rethrows `AbortError`.
 */
export async function fetchEvent(eventId: string, signal: AbortSignal): Promise<EventResult> {
  const url = `/api/v1/events/${encodeEventId(eventId)}`
  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (error) {
    if (signal.aborted) {
      throw error
    }
    return { kind: 'unreachable', message: String(error) }
  }

  const body = await readJson(response)
  if (response.status === 200 && typeof body === 'object' && body !== null) {
    return { kind: 'ok', event: body as EventDetail }
  }
  if (PROBLEM_STATUSES.has(response.status) && isProblem(body)) {
    return { kind: 'problem', problem: body }
  }
  return {
    kind: 'unreachable',
    message: `GET ${url} answered ${response.status} ${response.statusText}`.trimEnd(),
  }
}
